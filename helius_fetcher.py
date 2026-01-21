"""
Helius Data Fetcher - Get token data from Helius RPC/API
Now uses Birdseye API for reliable price/mcap data
Falls back to bonding curve decoder if Birdseye fails
"""
from typing import Dict, Optional
import aiohttp
from loguru import logger
import config
import base64
import struct
from datetime import datetime, timedelta
from birdseye_fetcher import get_birdseye_fetcher

# Try to import solders - log if it fails
try:
    from solders.pubkey import Pubkey
    SOLDERS_AVAILABLE = True
    logger.info("✅ solders library loaded successfully")
except ImportError as e:
    SOLDERS_AVAILABLE = False
    logger.warning(f"⚠️ solders library not available: {e}")
    logger.warning("   Bonding curve decoding will be disabled (using Birdseye instead)")
    logger.warning("   Install with: pip install solders")


# pump.fun constants
PUMP_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
TOTAL_SUPPLY = 1_000_000_000  # 1 billion tokens fixed


class HeliusDataFetcher:
    """Fetch token data from Helius API + Birdseye for price/mcap"""

    def __init__(self):
        self.api_key = config.HELIUS_API_KEY
        self.rpc_url = f"https://mainnet.helius-rpc.com/?api-key={self.api_key}"

        # Cache for holder checks (60-minute TTL to save credits)
        self.holder_cache = {}  # {token_address: {'data': {...}, 'timestamp': datetime}}
        self.cache_ttl_minutes = 60

        # Initialize Birdseye fetcher for price/mcap data
        birdseye_api_key = getattr(config, 'BIRDSEYE_API_KEY', None)
        self.birdseye = get_birdseye_fetcher(api_key=birdseye_api_key)
        logger.info("   🦅 Birdseye API initialized for price/mcap data")

        if SOLDERS_AVAILABLE:
            logger.info("   🔐 Bonding curve decoder enabled (fallback)")
        else:
            logger.warning("   ⚠️ Bonding curve decoder DISABLED (solders not installed)")
            logger.warning("      Relying on Birdseye API only")
        
    async def get_bonding_curve_data(self, token_address: str) -> Optional[Dict]:
        """
        Get bonding curve data for pump.fun token
        Decodes on-chain account to calculate price, mcap, bonding %
        
        Args:
            token_address: Token mint address
            
        Returns:
            Dict with price_usd, market_cap, liquidity, bonding_curve_pct or None
        """
        if not SOLDERS_AVAILABLE:
            logger.debug(f"   ⚠️ Bonding curve decode skipped - solders not installed")
            return None
            
        try:
            logger.debug(f"   🔐 Starting bonding curve decode...")
            
            # Derive bonding curve PDA
            mint_pubkey = Pubkey.from_string(token_address)
            program_pubkey = Pubkey.from_string(PUMP_PROGRAM_ID)
            
            bonding_curve_pda, _ = Pubkey.find_program_address(
                [b"bonding-curve", bytes(mint_pubkey)],
                program_pubkey
            )
            
            logger.debug(f"   📐 Bonding curve PDA: {str(bonding_curve_pda)[:8]}...")
            
            # Get account data from Helius
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.rpc_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getAccountInfo",
                        "params": [
                            str(bonding_curve_pda),
                            {"encoding": "base64"}
                        ]
                    },
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"   ⚠️ Helius RPC returned {resp.status}")
                        return None
                    
                    data = await resp.json()
                    result = data.get('result')
                    
                    if not result or not result.get('value'):
                        logger.warning(f"   ⚠️ No bonding curve account found")
                        return None
                    
                    account_data = result['value']['data'][0]  # Base64 encoded
                    logger.debug(f"   📦 Got account data, length: {len(account_data)}")
                    
            # Decode the account data
            decoded = self._decode_bonding_curve_account(account_data)
            
            if not decoded:
                logger.warning(f"   ⚠️ Failed to decode bonding curve")
                return None
            
            logger.debug(f"   ✅ Decoded reserves successfully")
            
            # Calculate price and mcap
            virtual_sol = decoded['virtual_sol_reserves'] / 1_000_000_000  # lamports to SOL
            virtual_token = decoded['virtual_token_reserves'] / 1_000_000  # 6 decimals
            
            logger.debug(f"   📊 virtual_sol={virtual_sol:.4f}, virtual_token={virtual_token:.0f}")
            
            # Get current SOL price (simplified - use 150 USD for now)
            sol_price_usd = 150  # TODO: Fetch live SOL price
            
            price_sol = virtual_sol / virtual_token if virtual_token > 0 else 0
            price_usd = price_sol * sol_price_usd
            
            # MCAP in SOL = virtual_sol (represents SOL value at current supply)
            mcap_sol = virtual_sol
            mcap_usd = mcap_sol * sol_price_usd
            
            # Liquidity (SOL in bonding curve)
            liquidity_usd = virtual_sol * sol_price_usd
            
            # Bonding curve progress (completes at ~85 SOL)
            bonding_pct = min((virtual_sol / 85) * 100, 100)
            
            logger.info(f"   💰 Decoded: price=${price_usd:.8f}, mcap=${mcap_usd:.0f}, bonding={bonding_pct:.1f}%")
            
            return {
                'price_usd': price_usd,
                'market_cap': mcap_usd,
                'liquidity': liquidity_usd,
                'bonding_curve_pct': bonding_pct,
                'virtual_sol_reserves': virtual_sol,
                'virtual_token_reserves': virtual_token,
            }
            
        except Exception as e:
            logger.error(f"   ❌ Bonding curve decode error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _decode_bonding_curve_account(self, base64_data: str) -> Optional[Dict]:
        """
        Decode bonding curve account data
        Simplified borsh schema - extracts virtual reserves
        
        Args:
            base64_data: Base64 encoded account data
            
        Returns:
            Dict with virtual_sol_reserves and virtual_token_reserves
        """
        try:
            # Decode base64
            data = base64.b64decode(base64_data)
            
            logger.info(f"   📦 Account data length: {len(data)} bytes")
            logger.info(f"   📦 First 32 bytes (hex): {data[:32].hex()}")
            
            # Simplified schema (full IDL has more fields)
            # Offset 8: virtual_token_reserves (u64)
            # Offset 16: virtual_sol_reserves (u64)
            # This is a simplified version - adjust offsets if needed
            
            if len(data) < 24:
                logger.warning(f"   ⚠️ Account data too short: {len(data)} bytes (need 24+)")
                return None
            
            # Try multiple offset combinations
            attempts = [
                (8, 16, "Standard (8, 16)"),
                (0, 8, "Alt 1 (0, 8)"),
                (16, 24, "Alt 2 (16, 24)"),
                (32, 40, "Alt 3 (32, 40)"),
            ]
            
            for token_offset, sol_offset, desc in attempts:
                if len(data) < sol_offset + 8:
                    continue
                    
                try:
                    # Unpack u64 values (little endian)
                    virtual_token_reserves = struct.unpack('<Q', data[token_offset:token_offset+8])[0]
                    virtual_sol_reserves = struct.unpack('<Q', data[sol_offset:sol_offset+8])[0]
                    
                    # Sanity check - reserves should be reasonable
                    token_in_millions = virtual_token_reserves / 1_000_000
                    sol_in_sol = virtual_sol_reserves / 1_000_000_000
                    
                    logger.info(f"   🧪 Trying {desc}:")
                    logger.info(f"      Token reserves: {virtual_token_reserves} ({token_in_millions:.2f}M)")
                    logger.info(f"      SOL reserves: {virtual_sol_reserves} ({sol_in_sol:.4f} SOL)")
                    
                    # Check if values are reasonable
                    # Token reserves should be ~100M-1000M (6 decimals)
                    # SOL reserves should be 0.1-85 SOL (9 decimals = 100M-85B lamports)
                    if (100_000 < virtual_token_reserves < 1_000_000_000_000 and
                        100_000_000 < virtual_sol_reserves < 100_000_000_000):
                        logger.info(f"   ✅ Found valid reserves with {desc}")
                        return {
                            'virtual_token_reserves': virtual_token_reserves,
                            'virtual_sol_reserves': virtual_sol_reserves,
                        }
                except Exception as e:
                    logger.debug(f"   Failed {desc}: {e}")
                    continue
            
            logger.warning(f"   ⚠️ No valid reserves found in any offset")
            return None
            
        except Exception as e:
            logger.error(f"   ❌ Decode error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
        
    async def get_token_data(self, token_address: str) -> Optional[Dict]:
        """
        Get complete token data (tries Birdseye first, falls back to Helius + bonding curve)

        Args:
            token_address: Token mint address

        Returns:
            Dict with token data or None
        """
        try:
            # STRATEGY: Try Birdseye first (most reliable for price/mcap)
            logger.debug(f"   🦅 Trying Birdseye first for {token_address[:8]}...")
            birdseye_data = await self.birdseye.get_token_data(token_address)

            if birdseye_data and birdseye_data.get('price_usd', 0) > 0:
                # Birdseye has all the data we need!
                logger.info(f"   ✅ Birdseye success: ${birdseye_data['token_symbol']} - ${birdseye_data['price_usd']:.8f}")
                return birdseye_data

            # FALLBACK: Birdseye failed, try Helius + bonding curve
            logger.debug(f"   ⚠️ Birdseye returned no data, falling back to Helius...")

            # Get asset data from Helius DAS API
            asset_data = await self._get_asset(token_address)

            if not asset_data:
                logger.warning(f"   ⚠️ No data from either Birdseye or Helius for {token_address[:8]}")
                return None

            # Extract token info
            token_data = self._parse_asset_data(token_address, asset_data)

            # Try to get bonding curve data (for pump.fun tokens)
            bonding_data = await self.get_bonding_curve_data(token_address)

            if bonding_data:
                # Update with bonding curve data
                token_data.update(bonding_data)
                logger.debug(f"   ✅ Got Helius data + bonding curve: {token_data.get('token_symbol', 'UNKNOWN')}")
            else:
                logger.warning(f"   ⚠️ Got Helius metadata only (no price/mcap): {token_data.get('token_symbol', 'UNKNOWN')}")

            return token_data

        except Exception as e:
            logger.error(f"❌ Error fetching token data: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    async def _get_asset(self, token_address: str) -> Optional[Dict]:
        """Get asset data from Helius DAS API"""
        try:
            url = f"https://api.helius.xyz/v0/token-metadata?api-key={self.api_key}"
            
            logger.debug(f"   🌐 Calling Helius token-metadata API...")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json={"mintAccounts": [token_address]},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"   ⚠️ Helius API returned status {resp.status}")
                        response_text = await resp.text()
                        logger.warning(f"   Response: {response_text[:200]}")
                        return None
                    
                    data = await resp.json()
                    
                    if not data or len(data) == 0:
                        logger.warning(f"   ⚠️ Helius API returned empty data")
                        logger.warning(f"   Response: {data}")
                        return None
                    
                    logger.debug(f"   ✅ Helius metadata API returned data")
                    logger.debug(f"   Keys in response: {list(data[0].keys())[:10]}")
                    return data[0]
                    
        except Exception as e:
            logger.error(f"   ❌ Helius metadata fetch error: {e}")
            import traceback
            logger.error(traceback.format_exc())
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

    async def get_token_holders(self, token_address: str, limit: int = 10) -> Optional[Dict]:
        """
        Get top token holders with 60-minute caching (saves credits!)

        COST: 10 Helius credits per call (cached for 60 minutes)

        Args:
            token_address: Token mint address
            limit: Number of top holders to return (default 10)

        Returns:
            {
                'holders': [{'address': str, 'balance': int}, ...],
                'total_supply': int,
                'cached': bool
            }
        """
        try:
            # Check cache first
            now = datetime.now()
            if token_address in self.holder_cache:
                cache_entry = self.holder_cache[token_address]
                cache_age = now - cache_entry['timestamp']

                if cache_age < timedelta(minutes=self.cache_ttl_minutes):
                    logger.debug(f"   💾 Using cached holder data (age: {cache_age.seconds // 60}m)")
                    cache_entry['data']['cached'] = True
                    return cache_entry['data']
                else:
                    logger.debug(f"   ⏰ Cache expired (age: {cache_age.seconds // 60}m), fetching fresh data")

            # Fetch fresh data from Helius (10 credits)
            logger.info(f"   🌐 Fetching top {limit} holders from Helius (10 credits)")

            async with aiohttp.ClientSession() as session:
                # Get top holders
                holders_response = await session.post(
                    self.rpc_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getTokenLargestAccounts",
                        "params": [token_address]
                    },
                    timeout=aiohttp.ClientTimeout(total=10)
                )

                if holders_response.status != 200:
                    logger.warning(f"   ⚠️ Helius RPC returned {holders_response.status}")
                    return None

                holders_data = await holders_response.json()

                # Get token supply
                supply_response = await session.post(
                    self.rpc_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "getTokenSupply",
                        "params": [token_address]
                    },
                    timeout=aiohttp.ClientTimeout(total=10)
                )

                if supply_response.status != 200:
                    logger.warning(f"   ⚠️ Failed to get token supply")
                    return None

                supply_data = await supply_response.json()

            # Parse response
            holders_result = holders_data.get('result', {})
            holders_value = holders_result.get('value', [])

            supply_result = supply_data.get('result', {})
            supply_value = supply_result.get('value', {})
            total_supply = int(supply_value.get('amount', 0))

            if not holders_value or not total_supply:
                logger.warning(f"   ⚠️ No holder data or supply returned")
                return None

            # Format holders data (top N)
            holders = []
            for i, holder in enumerate(holders_value[:limit]):
                amount = int(holder.get('amount', 0))
                # Note: We don't have wallet addresses in getTokenLargestAccounts response
                # We have account addresses (token accounts, not wallet addresses)
                holders.append({
                    'address': holder.get('address', f'holder_{i}'),
                    'amount': amount  # Use 'amount' to match rug_detector expectation
                })

            result = {
                'holders': holders,
                'total_supply': total_supply,
                'cached': False
            }

            # Store in cache
            self.holder_cache[token_address] = {
                'data': result,
                'timestamp': now
            }

            logger.info(f"   ✅ Got {len(holders)} holders, total supply: {total_supply:,}")
            logger.debug(f"   💾 Cached for {self.cache_ttl_minutes} minutes")

            return result

        except Exception as e:
            logger.error(f"   ❌ Error fetching holder data: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
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
        Enrich token data with price/mcap
        Tries Birdseye first, then bonding curve, then DexScreener as fallbacks

        Args:
            token_data: Base token data

        Returns:
            Enriched token data
        """
        token_address = token_data.get('token_address')

        # Try Birdseye first (works for all Solana tokens)
        logger.debug(f"   🦅 Trying Birdseye for enrichment...")
        birdseye_data = await self.birdseye.get_token_data(token_address)

        if birdseye_data and birdseye_data.get('price_usd', 0) > 0:
            token_data.update(birdseye_data)
            logger.debug(f"   ✅ Enriched with Birdseye: ${birdseye_data['price_usd']:.8f}")
            return token_data

        # Fallback 1: Try bonding curve (for pump.fun pre-graduation tokens)
        if token_data.get('bonding_curve_pct', 100) < 100:
            logger.debug(f"   🔐 Trying bonding curve decode...")
            bonding_data = await self.get_bonding_curve_data(token_address)
            if bonding_data:
                token_data.update(bonding_data)
                logger.debug(f"   💰 Enriched with bonding curve data")
                return token_data

        # Fallback 2: Try DexScreener (for graduated tokens)
        logger.debug(f"   📊 Trying DexScreener...")
        dex_data = await self.get_dexscreener_data(token_address)

        if dex_data:
            token_data.update(dex_data)
            logger.debug(f"   💎 Enriched with DexScreener: ${dex_data['price_usd']:.8f}")
        else:
            logger.warning(f"   ⚠️ No price data available from any source")

        return token_data
