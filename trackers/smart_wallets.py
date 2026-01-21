"""
Smart Wallet Tracker - Updated with GMGN metadata auto-fetching
Auto-fetches wallet stats (win_rate, pnl_30d, name) from GMGN.ai via Apify
"""
from typing import Dict, List
from datetime import datetime, timedelta
from loguru import logger
from data.curated_wallets import get_all_tracked_wallets, get_wallet_info
from gmgn_wallet_fetcher import get_gmgn_fetcher


class SmartWalletTracker:
    """Tracks wallet activity of known successful traders via Helius webhooks"""
    
    def __init__(self):
        self.tracked_wallets = {}
        self.recent_buys: Dict[str, List[dict]] = {}  # token -> [{wallet, info, time}]
        self.db = None  # Set externally after initialization
        self.save_failures = 0
        self.save_successes = 0
        
    async def start(self):
        """Initialize smart wallet tracking"""
        self.tracked_wallets = get_all_tracked_wallets()
        
        if not self.tracked_wallets:
            logger.warning("⚠️ No smart wallets configured")
            return False
        
        elite_count = sum(1 for w in self.tracked_wallets.values() if w.get('tier') == 'elite')
        top_kol_count = sum(1 for w in self.tracked_wallets.values() if w.get('tier') == 'top_kol')
        
        logger.info(f"✅ Smart Wallet Tracker initialized")
        logger.info(f"   🏆 Elite wallets: {elite_count}")
        logger.info(f"   👑 Top KOLs: {top_kol_count}")
        logger.info(f"   📊 Total tracked: {len(self.tracked_wallets)}")
        logger.info(f"   💾 Database: {'enabled' if self.db else 'NOT SET (memory-only)'}")
        
        return True
    
    async def process_webhook(self, webhook_data: List[Dict]) -> None:
        """Process Helius webhook data for smart wallet transactions"""
        try:
            logger.debug(f"📥 Processing webhook with {len(webhook_data)} transactions")
            
            for transaction in webhook_data:
                await self._process_transaction(transaction)
                
        except Exception as e:
            logger.error(f"❌ Error processing smart wallet webhook: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def _process_transaction(self, tx_data: Dict) -> None:
        """Process a single transaction from webhook"""
        try:
            # Get the wallet that made the transaction
            fee_payer = tx_data.get('feePayer', '')
            
            # Check if this is a tracked wallet
            if fee_payer not in self.tracked_wallets:
                logger.debug(f"⏭️  Skipping non-tracked wallet: {fee_payer[:8]}...")
                return
            
            wallet_info = get_wallet_info(fee_payer)
            if not wallet_info:
                logger.warning(f"⚠️ No wallet info for tracked wallet: {fee_payer[:8]}")
                return
            
            # Get token transfers
            token_transfers = tx_data.get('tokenTransfers', [])
            signature = tx_data.get('signature', '')
            timestamp = tx_data.get('timestamp', datetime.utcnow().timestamp())
            tx_time = datetime.fromtimestamp(timestamp)
            
            if not token_transfers:
                logger.debug(f"⏭️  No token transfers in transaction {signature[:8]}")
                return
            
            # Look for token buys (receiving tokens)
            for transfer in token_transfers:
                to_address = transfer.get('toUserAccount', '')
                
                if to_address == fee_payer:
                    token_address = transfer.get('mint', '')
                    amount = transfer.get('tokenAmount', 0)
                    
                    if token_address and amount > 0:
                        # Record the buy
                        success = await self._record_buy(
                            wallet_address=fee_payer,
                            wallet_info=wallet_info,
                            token_address=token_address,
                            amount=amount,
                            timestamp=tx_time,
                            signature=signature
                        )
                        
                        status_emoji = "✅" if success else "⚠️"
                        logger.info(f"👑 {wallet_info['name']} ({wallet_info['tier']}) bought {token_address[:8]}... {status_emoji}")
            
        except Exception as e:
            logger.error(f"❌ Error processing transaction: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def _record_buy(
        self,
        wallet_address: str,
        wallet_info: dict,
        token_address: str,
        amount: float,
        timestamp: datetime,
        signature: str
    ) -> bool:
        """Record a smart wallet buy. Returns True if saved to DB successfully."""

        # Auto-fetch metadata from GMGN if enabled
        if wallet_info.get('fetch_metadata', False):
            gmgn = get_gmgn_fetcher()
            live_metadata = await gmgn.get_wallet_metadata(wallet_address, chain='sol')

            if live_metadata:
                # Merge live data with curated data
                wallet_info = {
                    **wallet_info,  # Keep tier and fetch_metadata flag
                    'name': live_metadata['name'],
                    'win_rate': live_metadata['win_rate'],
                    'pnl_30d': live_metadata['pnl_30d']
                }
                logger.info(f"✅ Auto-fetched metadata: {live_metadata['name']} ({live_metadata['win_rate']*100:.0f}% WR, ${live_metadata['pnl_30d']/1000:.0f}k PnL)")
            else:
                logger.warning(f"⚠️ Failed to fetch GMGN metadata for {wallet_address[:8]}, using defaults")
                # Use fallback values
                wallet_info = {
                    **wallet_info,
                    'name': wallet_info.get('name') or f"KOL_{wallet_address[:6]}",
                    'win_rate': wallet_info.get('win_rate', 0),
                    'pnl_30d': wallet_info.get('pnl_30d', 0)
                }

        # Add to in-memory cache ALWAYS (this is fast)
        if token_address not in self.recent_buys:
            self.recent_buys[token_address] = []

        self.recent_buys[token_address].append({
            'wallet': wallet_address,
            'name': wallet_info['name'],
            'tier': wallet_info['tier'],
            'win_rate': wallet_info.get('win_rate', 0),
            'pnl_30d': wallet_info.get('pnl_30d', 0),
            'amount': amount,
            'timestamp': timestamp,
            'signature': signature
        })
        
        # Keep only last 20 buys per token in memory
        if len(self.recent_buys[token_address]) > 20:
            self.recent_buys[token_address] = self.recent_buys[token_address][-20:]
        
        logger.debug(f"📝 Added to memory: {wallet_info['name']} -> {token_address[:8]}")
        
        # Try to persist to database
        if not self.db:
            logger.debug(f"⚠️ No database configured - memory only")
            return False
        
        try:
            logger.debug(f"💾 Attempting database save...")
            logger.debug(f"   Wallet: {wallet_address}")
            logger.debug(f"   Name: {wallet_info['name']}")
            logger.debug(f"   Token: {token_address}")
            logger.debug(f"   Signature: {signature}")
            
            # Call the database insert method with KOL metadata
            await self.db.insert_smart_wallet_activity(
                wallet_address=wallet_address,
                wallet_name=wallet_info['name'],
                wallet_tier=wallet_info['tier'],
                token_address=token_address,
                transaction_type='buy',  # Always 'buy' for KOL purchases
                amount=amount,
                transaction_signature=signature,
                timestamp=timestamp,
                win_rate=wallet_info.get('win_rate'),  # Save win rate from curated_wallets
                pnl_30d=wallet_info.get('pnl_30d')     # Save 30d PnL from curated_wallets
            )
            
            self.save_successes += 1
            logger.info(f"💾 ✅ Saved to database (total: {self.save_successes})")
            
            # Log stats every 10 saves
            if self.save_successes % 10 == 0:
                logger.info(f"📊 Database stats: {self.save_successes} saves, {self.save_failures} failures")
            
            return True
            
        except AttributeError as e:
            logger.error(f"❌ Database method missing: {e}")
            logger.error(f"   Your Database class needs an 'insert_kol_buy()' method!")
            self.save_failures += 1
            return False
            
        except Exception as e:
            logger.error(f"❌ Database save FAILED: {e}")
            logger.error(f"   Error type: {type(e).__name__}")
            
            # Show full traceback for first few failures
            if self.save_failures < 3:
                import traceback
                logger.error(traceback.format_exc())
            
            self.save_failures += 1
            
            # Alert every 10 failures
            if self.save_failures % 10 == 0:
                logger.error(f"🚨 Total database failures: {self.save_failures}")
            
            return False
    
    async def get_smart_wallet_activity(self, token_address: str, hours: int = 24) -> Dict:
        """
        Get smart wallet activity for a token
        Returns scoring data and wallet details
        """
        # Try in-memory cache first (fast)
        if token_address in self.recent_buys and self.recent_buys[token_address]:
            buys = self.recent_buys[token_address]
            # Update tiers from current tracked_wallets (in case they changed)
            for buy in buys:
                wallet_addr = buy['wallet']
                if wallet_addr in self.tracked_wallets:
                    buy['tier'] = self.tracked_wallets[wallet_addr].get('tier', buy['tier'])
            logger.debug(f"📊 Found {len(buys)} buys in memory for {token_address[:8]}")
        
        # Fall back to database
        elif self.db:
            try:
                logger.debug(f"📊 Checking database for {token_address[:8]}...")
                db_activity = await self.db.get_smart_wallet_activity(token_address, hours=hours)
                
                buys = [
                    {
                        'wallet': row['wallet_address'],
                        'name': row['wallet_name'],
                        # Use CURRENT tier from tracked_wallets (not stale DB tier)
                        'tier': self.tracked_wallets.get(row['wallet_address'], {}).get('tier', row['wallet_tier']),
                        'win_rate': row.get('win_rate', 0),  # Get from DB or default to 0
                        'pnl_30d': row.get('pnl_30d', 0),    # Get from DB or default to 0
                        'amount': row['amount'],
                        'timestamp': row['timestamp'],
                        'signature': row['transaction_signature']
                    }
                    for row in db_activity
                ]
                
                logger.debug(f"📊 Found {len(buys)} buys in database for {token_address[:8]}")
            except Exception as e:
                logger.error(f"❌ Database lookup failed: {e}")
                buys = []
        else:
            buys = []
        
        if not buys:
            return {
                'has_activity': False,
                'wallet_count': 0,
                'elite_count': 0,
                'top_kol_count': 0,
                'wallets': [],
                'score': 0
            }
        
        # Get unique wallets
        unique_wallets = {}
        for buy in buys:
            wallet = buy['wallet']
            if wallet not in unique_wallets:
                unique_wallets[wallet] = {
                    'name': buy['name'],
                    'tier': buy['tier'],
                    'win_rate': buy.get('win_rate', 0),
                    'pnl_30d': buy.get('pnl_30d', 0),
                    'first_buy': buy['timestamp'],
                    'amount': buy['amount']
                }
        
        # Count by tier
        elite_count = sum(1 for w in unique_wallets.values() if w['tier'] == 'elite')
        top_kol_count = sum(1 for w in unique_wallets.values() if w['tier'] == 'top_kol')
        
        # Calculate score (use your config weights)
        from config import WEIGHTS
        score = 0
        score += elite_count * WEIGHTS.get('smart_wallet_elite', 15)
        score += top_kol_count * WEIGHTS.get('smart_wallet_kol', 10)
        score = min(score, 40)  # Cap at 40
        
        logger.debug(f"📊 Smart wallet score for {token_address[:8]}: {score} points")
        logger.debug(f"   Elite: {elite_count}, Top KOLs: {top_kol_count}")
        
        return {
            'has_activity': True,
            'wallet_count': len(unique_wallets),
            'elite_count': elite_count,
            'top_kol_count': top_kol_count,
            'wallets': [
                {
                    'name': info['name'],
                    'tier': info['tier'],
                    'win_rate': info['win_rate'],
                    'minutes_ago': (datetime.utcnow() - info['first_buy']).total_seconds() / 60
                }
                for info in list(unique_wallets.values())[:5]  # Top 5
            ],
            'score': score
        }
    
    def cleanup_old_data(self):
        """Remove old buy data from in-memory cache"""
        cutoff = datetime.utcnow() - timedelta(hours=24)
        
        for token_address in list(self.recent_buys.keys()):
            self.recent_buys[token_address] = [
                buy for buy in self.recent_buys[token_address]
                if buy['timestamp'] > cutoff
            ]
            
            if not self.recent_buys[token_address]:
                del self.recent_buys[token_address]
        
        logger.debug(f"🧹 Cleaned in-memory cache, {len(self.recent_buys)} tokens remaining")
