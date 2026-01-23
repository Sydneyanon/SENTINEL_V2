"""
Wallet Auto-Discovery Module
Automatically fetch KOL metadata from wallet addresses
"""
import aiohttp
import asyncio
from typing import Dict, Optional, List
from loguru import logger
from datetime import datetime, timedelta
import config


class WalletAutoDiscovery:
    """Automatically discover and score wallets"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.gmgn_base = "https://gmgn.ai/defi/quotation/v1/smartmoney/sol"
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def discover_wallet(self, address: str) -> Optional[Dict]:
        """
        Automatically discover wallet metadata from address
        
        Returns dict with:
        - name: Display name or shortened address
        - tier: elite/top_kol/verified/unknown
        - win_rate: Calculated win rate
        - specialty: What they trade (AI, meme, DeFi, etc)
        - total_profit: USD profit
        - trade_count: Number of trades
        - avg_hold_time: Average hold time in minutes
        """
        try:
            logger.info(f"🔍 Auto-discovering wallet: {address[:8]}...")
            
            # Try multiple sources
            metadata = None
            
            # 1. Try gmgn.ai API
            metadata = await self._fetch_from_gmgn(address)
            
            if not metadata:
                # 2. Fallback: Calculate from on-chain data (Helius)
                metadata = await self._calculate_from_onchain(address)
            
            if not metadata:
                # 3. Last resort: Create basic entry
                metadata = self._create_basic_entry(address)
            
            # Assign tier based on performance
            metadata['tier'] = self._assign_tier(metadata)
            
            logger.info(f"✅ Discovered: {metadata['name']} ({metadata['tier']}, {metadata['win_rate']*100:.0f}% WR)")
            
            return metadata
            
        except Exception as e:
            logger.error(f"❌ Error discovering wallet {address[:8]}: {e}")
            return self._create_basic_entry(address)
    
    async def _fetch_from_gmgn(self, address: str) -> Optional[Dict]:
        """Fetch wallet data from gmgn.ai API"""
        try:
            # gmgn.ai has public API endpoints for wallet stats
            url = f"{self.gmgn_base}/wallet/{address}"
            
            async with self.session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    return None
                
                data = await resp.json()
                
                if not data or 'data' not in data:
                    return None
                
                wallet_data = data['data']
                
                return {
                    'address': address,
                    'name': wallet_data.get('name') or f"Trader_{address[:6]}",
                    'win_rate': wallet_data.get('win_rate', 0),
                    'total_profit': wallet_data.get('realized_profit', 0),
                    'trade_count': wallet_data.get('buy_count', 0),
                    'avg_hold_time': wallet_data.get('avg_hold_duration', 0),
                    'specialty': self._detect_specialty(wallet_data),
                    'source': 'gmgn.ai',
                    'last_updated': datetime.utcnow().isoformat(),
                    'verified': True,
                    'active': True
                }
                
        except asyncio.TimeoutError:
            logger.debug(f"⏱️ gmgn.ai timeout for {address[:8]}")
            return None
        except Exception as e:
            logger.debug(f"⚠️ gmgn.ai fetch failed for {address[:8]}: {e}")
            return None
    
    async def _calculate_from_onchain(self, address: str) -> Optional[Dict]:
        """Calculate stats from on-chain transaction history via Helius"""
        try:
            # Use Helius to get transaction history
            if not config.HELIUS_API_KEY:
                return None
            
            url = f"https://api.helius.xyz/v0/addresses/{address}/transactions"
            params = {
                'api-key': config.HELIUS_API_KEY,
                'limit': 100  # Last 100 transactions
            }
            
            async with self.session.get(url, params=params, timeout=10) as resp:
                if resp.status != 200:
                    return None
                
                transactions = await resp.json()
                
                # Calculate stats from transactions
                stats = self._analyze_transactions(address, transactions)
                
                return {
                    'address': address,
                    'name': f"Wallet_{address[:6]}",
                    'win_rate': stats['win_rate'],
                    'total_profit': stats['total_profit'],
                    'trade_count': stats['trade_count'],
                    'avg_hold_time': stats['avg_hold_time'],
                    'specialty': stats['specialty'],
                    'source': 'on-chain',
                    'last_updated': datetime.utcnow().isoformat(),
                    'verified': False,
                    'active': True
                }
                
        except Exception as e:
            logger.debug(f"⚠️ On-chain calculation failed for {address[:8]}: {e}")
            return None
    
    def _analyze_transactions(self, address: str, transactions: List[Dict]) -> Dict:
        """Analyze transaction history to calculate stats"""
        wins = 0
        losses = 0
        total_profit = 0
        hold_times = []
        token_types = []
        
        # Group buys and sells by token
        positions = {}
        
        for tx in transactions:
            # Parse transaction for buy/sell
            # This is simplified - real implementation would be more complex
            tx_type = tx.get('type', '')
            
            if 'SWAP' in tx_type:
                # Extract swap details
                token_in = tx.get('tokenTransfers', [{}])[0].get('mint')
                token_out = tx.get('tokenTransfers', [{}])[-1].get('mint')
                
                # Track positions
                # (Simplified logic)
                
        # Calculate win rate
        total_trades = wins + losses
        win_rate = wins / total_trades if total_trades > 0 else 0
        
        # Determine specialty
        specialty = 'unknown'
        if len(token_types) > 0:
            # Most common token type
            specialty = max(set(token_types), key=token_types.count)
        
        return {
            'win_rate': win_rate,
            'total_profit': total_profit,
            'trade_count': total_trades,
            'avg_hold_time': sum(hold_times) / len(hold_times) if hold_times else 0,
            'specialty': specialty
        }
    
    def _create_basic_entry(self, address: str) -> Dict:
        """Create basic entry when no data available"""
        return {
            'address': address,
            'name': f"Wallet_{address[:8]}",
            'win_rate': 0.50,  # Unknown, assume 50%
            'total_profit': 0,
            'trade_count': 0,
            'specialty': 'unknown',
            'source': 'manual',
            'last_updated': datetime.utcnow().isoformat(),
            'verified': False,
            'active': True
        }
    
    def _detect_specialty(self, wallet_data: Dict) -> str:
        """Detect what the wallet specializes in"""
        # Look at their top tokens or tags
        tags = wallet_data.get('tags', [])
        
        if any('ai' in tag.lower() for tag in tags):
            return 'AI'
        elif any('desci' in tag.lower() for tag in tags):
            return 'DeSci'
        elif any('meme' in tag.lower() for tag in tags):
            return 'Meme'
        elif any('defi' in tag.lower() for tag in tags):
            return 'DeFi'
        else:
            return 'General'
    
    def _assign_tier(self, metadata: Dict) -> str:
        """Assign tier based on performance"""
        win_rate = metadata.get('win_rate', 0)
        profit = metadata.get('total_profit', 0)
        
        # Elite: >75% WR and >$100k profit
        if win_rate >= 0.75 and profit >= 100000:
            return 'elite'
        
        # Top KOL: >65% WR and >$50k profit
        elif win_rate >= 0.65 and profit >= 50000:
            return 'top_kol'
        
        # Verified: >55% WR and >$20k profit
        elif win_rate >= 0.55 and profit >= 20000:
            return 'verified'
        
        # Emerging: >50% WR
        elif win_rate >= 0.50:
            return 'emerging'
        
        else:
            return 'unknown'
    
    async def discover_multiple(self, addresses: List[str]) -> Dict[str, Dict]:
        """Discover metadata for multiple wallets"""
        results = {}
        
        for address in addresses:
            metadata = await self.discover_wallet(address)
            if metadata:
                results[address] = metadata
            
            # Rate limiting
            await asyncio.sleep(0.5)
        
        return results
    
    async def discover_top_traders(self, limit: int = 20) -> List[Dict]:
        """Discover current top traders from gmgn.ai"""
        try:
            url = f"{self.gmgn_base}/rank/wallet"
            params = {
                'period': '7d',  # Last 7 days
                'orderby': 'profit',
                'direction': 'desc',
                'limit': limit
            }
            
            async with self.session.get(url, params=params, timeout=15) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to fetch top traders: {resp.status}")
                    return []
                
                data = await resp.json()
                wallets = data.get('data', {}).get('rank', [])
                
                # Convert to our format
                discovered = []
                for wallet in wallets:
                    metadata = {
                        'address': wallet['wallet_address'],
                        'name': wallet.get('wallet_tag') or f"Trader_{wallet['wallet_address'][:6]}",
                        'win_rate': wallet.get('win_rate', 0),
                        'total_profit': wallet.get('realized_profit', 0),
                        'trade_count': wallet.get('buy_count', 0),
                        'specialty': self._detect_specialty(wallet),
                        'tier': self._assign_tier({
                            'win_rate': wallet.get('win_rate', 0),
                            'total_profit': wallet.get('realized_profit', 0)
                        }),
                        'source': 'gmgn.ai',
                        'verified': True,
                        'active': True,
                        'last_updated': datetime.utcnow().isoformat()
                    }
                    discovered.append(metadata)
                
                logger.info(f"✅ Discovered {len(discovered)} top traders from gmgn.ai")
                return discovered
                
        except Exception as e:
            logger.error(f"❌ Error discovering top traders: {e}")
            return []


async def auto_discover_wallets(addresses: List[str]) -> Dict[str, Dict]:
    """
    Main function: Auto-discover metadata for wallet addresses
    
    Usage:
        metadata = await auto_discover_wallets(['addr1', 'addr2', ...])
    """
    async with WalletAutoDiscovery() as discovery:
        return await discovery.discover_multiple(addresses)


async def discover_top_traders(limit: int = 20) -> List[Dict]:
    """
    Discover current top traders from gmgn.ai
    
    Usage:
        top_traders = await discover_top_traders(20)
    """
    async with WalletAutoDiscovery() as discovery:
        return await discovery.discover_top_traders(limit)


# CLI for testing
if __name__ == "__main__":
    import sys
    
    async def main():
        if len(sys.argv) > 1:
            # Discover specific wallet
            address = sys.argv[1]
            async with WalletAutoDiscovery() as discovery:
                metadata = await discovery.discover_wallet(address)
                print(f"\n✅ Wallet Metadata:")
                for key, value in metadata.items():
                    print(f"  {key}: {value}")
        else:
            # Discover top 20 traders
            print("🔍 Discovering top 20 traders from gmgn.ai...")
            traders = await discover_top_traders(20)
            print(f"\n✅ Found {len(traders)} traders:\n")
            for i, trader in enumerate(traders, 1):
                print(f"{i}. {trader['name']} ({trader['tier']})")
                print(f"   Address: {trader['address']}")
                print(f"   Win Rate: {trader['win_rate']*100:.1f}%")
                print(f"   Profit: ${trader['total_profit']:,.0f}")
                print()
    
    asyncio.run(main())
