"""
Smart Wallet Tracker - Monitor elite trader transactions via Helius webhooks
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from loguru import logger
from data.curated_wallets import get_all_tracked_wallets, get_wallet_info
from database import SmartWalletActivity, get_session


class SmartWalletTracker:
    """Tracks wallet activity of known successful traders via Helius webhooks"""
    
    def __init__(self):
        self.tracked_wallets = {}
        self.recent_buys: Dict[str, List[dict]] = {}  # token -> [{wallet, info, time}]
        
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
        
        return True
    
    async def process_webhook(self, webhook_data: List[Dict]) -> None:
        """
        Process Helius webhook data for smart wallet transactions
        webhook_data is a list of enhanced transaction objects
        """
        try:
            for transaction in webhook_data:
                await self._process_transaction(transaction)
        except Exception as e:
            logger.error(f"❌ Error processing smart wallet webhook: {e}")
    
    async def _process_transaction(self, tx_data: Dict) -> None:
        """Process a single transaction from webhook"""
        try:
            # Get the wallet that made the transaction
            fee_payer = tx_data.get('feePayer', '')
            
            # Check if this is a tracked wallet
            if fee_payer not in self.tracked_wallets:
                return
            
            wallet_info = get_wallet_info(fee_payer)
            if not wallet_info:
                return
            
            # Get token transfers
            token_transfers = tx_data.get('tokenTransfers', [])
            signature = tx_data.get('signature', '')
            timestamp = tx_data.get('timestamp', datetime.utcnow().timestamp())
            tx_time = datetime.fromtimestamp(timestamp)
            
            # Look for token buys (receiving tokens)
            for transfer in token_transfers:
                to_address = transfer.get('toUserAccount', '')
                
                if to_address == fee_payer:
                    token_address = transfer.get('mint', '')
                    amount = transfer.get('tokenAmount', 0)
                    
                    if token_address and amount > 0:
                        # Record the buy
                        await self._record_buy(
                            wallet_address=fee_payer,
                            wallet_info=wallet_info,
                            token_address=token_address,
                            amount=amount,
                            timestamp=tx_time,
                            signature=signature
                        )
                        
                        logger.info(f"👑 {wallet_info['name']} ({wallet_info['tier']}) bought {token_address[:8]}...")
            
        except Exception as e:
            logger.error(f"❌ Error processing transaction: {e}")
    
    async def _record_buy(
        self,
        wallet_address: str,
        wallet_info: dict,
        token_address: str,
        amount: float,
        timestamp: datetime,
        signature: str
    ) -> None:
        """Record a smart wallet buy"""
        
        # Add to recent buys cache
        if token_address not in self.recent_buys:
            self.recent_buys[token_address] = []
        
        self.recent_buys[token_address].append({
            'wallet': wallet_address,
            'name': wallet_info['name'],
            'tier': wallet_info['tier'],
            'win_rate': wallet_info.get('win_rate', 0),
            'amount': amount,
            'timestamp': timestamp
        })
        
        # Keep only last 20 buys per token
        if len(self.recent_buys[token_address]) > 20:
            self.recent_buys[token_address] = self.recent_buys[token_address][-20:]
        
        # Save to database
        session = get_session()
        if session:
            try:
                activity = SmartWalletActivity(
                    wallet_address=wallet_address,
                    wallet_name=wallet_info['name'],
                    wallet_tier=wallet_info['tier'],
                    token_address=token_address,
                    transaction_type='buy',
                    amount=amount,
                    timestamp=timestamp,
                    signature=signature
                )
                session.add(activity)
                session.commit()
            except Exception as e:
                logger.error(f"❌ Error saving wallet activity: {e}")
                session.rollback()
            finally:
                session.close()
    
    def get_smart_wallet_activity(self, token_address: str) -> Dict:
        """
        Get smart wallet activity for a token
        Returns scoring data and wallet details
        """
        if token_address not in self.recent_buys:
            return {
                'has_activity': False,
                'wallet_count': 0,
                'elite_count': 0,
                'top_kol_count': 0,
                'wallets': [],
                'score': 0
            }
        
        buys = self.recent_buys[token_address]
        
        # Get unique wallets
        unique_wallets = {}
        for buy in buys:
            wallet = buy['wallet']
            if wallet not in unique_wallets:
                unique_wallets[wallet] = {
                    'name': buy['name'],
                    'tier': buy['tier'],
                    'win_rate': buy.get('win_rate', 0),
                    'first_buy': buy['timestamp'],
                    'amount': buy['amount']
                }
        
        # Count by tier
        elite_count = sum(1 for w in unique_wallets.values() if w['tier'] == 'elite')
        top_kol_count = sum(1 for w in unique_wallets.values() if w['tier'] == 'top_kol')
        
        # Calculate score (max 40 points)
        from config import WEIGHTS
        score = 0
        score += elite_count * WEIGHTS['smart_wallet_elite']  # +15 per elite
        score += top_kol_count * WEIGHTS['smart_wallet_kol']  # +10 per top KOL
        score = min(score, 40)  # Cap at 40
        
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
        """Remove buy data older than 24 hours"""
        cutoff = datetime.utcnow() - timedelta(hours=24)
        
        for token_address in list(self.recent_buys.keys()):
            self.recent_buys[token_address] = [
                buy for buy in self.recent_buys[token_address]
                if buy['timestamp'] > cutoff
            ]
            
            if not self.recent_buys[token_address]:
                del self.recent_buys[token_address]
