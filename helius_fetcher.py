"""
Helius Data Fetcher - Get token data from Helius RPC/API
"""
from typing import Dict, Optional
import aiohttp
from loguru import logger
import config


class HeliusDataFetcher:
    """Fetch token data from Helius API"""
    
    def __init__(self):
        self.api_key = config.HELIUS_API_KEY
        self.rpc_url = f"https://mainnet.helius-rpc.com/?api-key={self.api_key}"
        
    async def get_token_data(self, token_address: str) -> Optional[Dict]:
        """
        Get complete token data from Helius
        
        Args:
            token_address: Token mint address
            
        Returns:
            Dict with token data or None
        """
        try:
            # Get asset data from Helius DAS API
            asset_data = await self._get_asset(token_address)
            
            if not asset_data:
                logger.debug(f"   ⚠️ No asset data from Helius for {token_address[:8]}")
                return None
            
            # Extract token info
            token_data = self._parse_asset_data(token_address, asset_data)
            
            logger.debug(f"   ✅ Got Helius data: {token_data.get('token_symbol', 'UNKNOWN')}")
            
            return token_data
            
        except Exception as e:
            logger.error(f"❌ Error fetching from Helius: {e}")
            return None
    
    async def _get_asset(self, token_address: str) -> Optional[Dict]:
        """Get asset data from Helius DAS API"""
        try:
            url = f"https://api.helius.xyz/v0/token-metadata?api-key={self.api_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json={"mintAccounts": [token_address]},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status != 200:
                        return None
                    
                    data = await resp.json()
                    
                    if not data or len(data) == 0:
                        return None
                    
                    return data[0]
                    
        except Exception as e:
            logger.debug(f"   Helius asset fetch error: {e}")
            return None
    
    async def get_holder_count(self, token_address: str) -> int:
        """
        Get holder count for a token
        
        Args:
            token_address: Token mint address
            
        Returns:
            Holder count (0 if error)
        """
        try:
            # Use RPC to get token supply and holders
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.rpc_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getTokenLargestAccounts",
                        "params": [token_address]
                    },
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status != 200:
                        return 0
                    
                    data = await resp.json()
                    result = data.get('result', {})
                    value = result.get('value', [])
                    
                    # Count non-zero accounts
                    holders = len([acc for acc in value if acc.get('amount', '0') != '0'])
                    
                    return holders
                    
        except Exception as e:
            logger.debug(f"   Helius holder count error: {e}")
            return 0
    
    def _parse_asset_data(self, token_address: str, asset_data: Dict) -> Dict:
        """Parse Helius asset data into our format"""
        
        account = asset_data.get('account', token_address)
        on_chain_data = asset_data.get('onChainAccountInfo', {})
        on_chain_metadata = asset_data.get('onChainMetadata', {})
        off_chain_data = asset_data.get('offChainMetadata', {})
        
        # Get metadata
        metadata = off_chain_data.get('metadata', {})
        
        # Get name and symbol
        name = metadata.get('name', on_chain_metadata.get('data', {}).get('name', 'Unknown'))
        symbol = metadata.get('symbol', on_chain_metadata.get('data', {}).get('symbol', 'UNKNOWN'))
        
        # Clean up name/symbol (remove null bytes)
        name = name.replace('\x00', '').strip()
        symbol = symbol.replace('\x00', '').strip()
        
        # Get token info
        token_info = asset_data.get('legacyMetadata', {})
        
        return {
            'token_address': account,
            'token_name': name,
            'token_symbol': symbol,
            'price_usd': 0,  # Will get from DexScreener if graduated
            'market_cap': 0,  # Will calculate
            'liquidity': 0,  # Will calculate
            'holder_count': 0,  # Will fetch separately
            'volume_24h': 0,
            'volume_1h': 0,
            'bonding_curve_pct': 0,  # For pump.fun tokens
            'created_timestamp': 0,
            'price_change_5m': 0,
        }
    
    async def get_dexscreener_data(self, token_address: str) -> Optional[Dict]:
        """
        Get price/mcap from DexScreener for graduated tokens
        
        Args:
            token_address: Token mint address
            
        Returns:
            Dict with price/mcap data or None
        """
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        return None
                    
                    data = await resp.json()
                    pairs = data.get('pairs', [])
                    
                    if not pairs:
                        return None
                    
                    # Get Raydium pair (best liquidity usually)
                    pair = pairs[0]
                    for p in pairs:
                        if 'raydium' in p.get('dexId', '').lower():
                            pair = p
                            break
                    
                    return {
                        'price_usd': float(pair.get('priceUsd', 0)),
                        'market_cap': float(pair.get('fdv', 0)),
                        'liquidity': float(pair.get('liquidity', {}).get('usd', 0)),
                        'volume_24h': float(pair.get('volume', {}).get('h24', 0)),
                        'price_change_5m': float(pair.get('priceChange', {}).get('m5', 0)),
                    }
                    
        except Exception as e:
            logger.debug(f"   DexScreener error: {e}")
            return None
    
    async def enrich_token_data(self, token_data: Dict) -> Dict:
        """
        Enrich token data with price/mcap from DexScreener if available
        
        Args:
            token_data: Base token data
            
        Returns:
            Enriched token data
        """
        token_address = token_data.get('token_address')
        
        # Try to get DexScreener data (for graduated tokens)
        dex_data = await self.get_dexscreener_data(token_address)
        
        if dex_data:
            token_data.update(dex_data)
            logger.debug(f"   💎 Enriched with DexScreener: ${dex_data['price_usd']:.8f}")
        
        return token_data
