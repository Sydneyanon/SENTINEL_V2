"""
Rug Detector - Anti-scam filters with smart overrides
Detects bundled buys and holder concentration to avoid rugs
"""
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from loguru import logger
from collections import defaultdict


class RugDetector:
    """
    Detects rug pull patterns:
    1. Bundled transactions (coordinated buys)
    2. Top holder concentration (dev/whale control)
    
    Includes smart overrides to avoid filtering legitimate pumps
    """
    
    def __init__(self, smart_wallet_tracker=None):
        self.smart_wallet_tracker = smart_wallet_tracker
        self.bundle_cache = {}  # token -> last bundle check
        self.holder_cache = {}  # token -> last holder check
    
    def detect_bundles(
        self, 
        token_address: str, 
        trades: List[Dict],
        unique_buyers: int = 0
    ) -> Dict:
        """
        Detect bundled buy transactions from PumpPortal trade data
        
        Bundles = Multiple buys in same block/second (coordinated sniping)
        
        Args:
            token_address: Token mint address
            trades: List of trades from PumpPortal
            unique_buyers: Current unique buyer count (for override logic)
        
        Returns:
            {
                'severity': 'none'|'minor'|'medium'|'massive',
                'penalty': -5 to -40 points,
                'same_block_count': int,
                'override_applied': bool,
                'reason': str
            }
        """
        if not trades or len(trades) < 5:
            return {
                'severity': 'none',
                'penalty': 0,
                'same_block_count': 0,
                'override_applied': False,
                'reason': 'Not enough trades to detect bundles'
            }
        
        # Group trades by block/slot
        blocks = defaultdict(list)
        
        for trade in trades:
            # Use slot (block number) or timestamp
            slot = trade.get('slot')
            if not slot:
                # Fallback: group by second
                timestamp = trade.get('timestamp', 0)
                slot = int(timestamp)
            
            blocks[slot].append(trade)
        
        # Find largest bundle
        max_bundle_size = max(len(txs) for txs in blocks.values()) if blocks else 0
        total_bundled = sum(1 for txs in blocks.values() if len(txs) > 3)
        
        # Classify severity
        if max_bundle_size <= 3:
            severity = 'none'
            base_penalty = 0
        elif max_bundle_size <= 10:
            severity = 'minor'
            base_penalty = -10
        elif max_bundle_size <= 20:
            severity = 'medium'
            base_penalty = -25
        else:
            severity = 'massive'
            base_penalty = -40
        
        # SMART OVERRIDE: High unique buyers = organic interest
        override_applied = False
        final_penalty = base_penalty
        
        if unique_buyers > 100 and base_penalty < 0:
            # Many unique buyers despite bundle = pump continuation
            final_penalty = base_penalty // 2  # Cut penalty in half
            override_applied = True
            logger.info(f"   🔓 Bundle penalty override: {unique_buyers} unique buyers (reduced {base_penalty} → {final_penalty})")
        
        elif unique_buyers > 50 and base_penalty <= -25:
            # Moderate buyers = reduce severe penalties
            final_penalty = base_penalty + 10  # Reduce by 10
            override_applied = True
            logger.debug(f"   🔓 Minor bundle override: {unique_buyers} buyers")
        
        return {
            'severity': severity,
            'penalty': final_penalty,
            'same_block_count': max_bundle_size,
            'total_bundled_blocks': total_bundled,
            'override_applied': override_applied,
            'reason': f'{severity.upper()} bundle: {max_bundle_size} same-block txs'
        }
    
    async def check_holder_concentration(
        self,
        token_address: str,
        helius_fetcher,
        kol_wallets: Optional[Set[str]] = None
    ) -> Dict:
        """
        Check if top holders control too much supply (rug risk)
        
        EXPENSIVE: Uses 10 Helius credits - only call if base score >= 65!
        
        Args:
            token_address: Token mint address
            helius_fetcher: HeliusDataFetcher instance
            kol_wallets: Set of tracked KOL wallet addresses
        
        Returns:
            {
                'top_10_percentage': float,
                'penalty': -15 to -40 or -999 (hard drop),
                'kol_bonus': 0-20 points,
                'has_kol_holders': bool,
                'hard_drop': bool,
                'reason': str
            }
        """
        try:
            # Fetch top 10 holders (10 credits)
            logger.info(f"   💰 Checking holder concentration (10 credits)")
            holders_data = await helius_fetcher.get_token_holders(token_address, limit=10)
            
            if not holders_data or 'holders' not in holders_data:
                logger.warning(f"   ⚠️ No holder data returned")
                return {
                    'top_10_percentage': 0,
                    'penalty': 0,
                    'kol_bonus': 0,
                    'has_kol_holders': False,
                    'hard_drop': False,
                    'reason': 'No holder data available'
                }
            
            holders = holders_data['holders']
            total_supply = holders_data.get('total_supply', 0)
            
            if not total_supply or len(holders) == 0:
                return {
                    'top_10_percentage': 0,
                    'penalty': 0,
                    'kol_bonus': 0,
                    'has_kol_holders': False,
                    'hard_drop': False,
                    'reason': 'Invalid holder data'
                }
            
            # Calculate top 10 percentage
            top_10_supply = sum(h.get('amount', 0) for h in holders[:10])
            top_10_pct = (top_10_supply / total_supply) * 100
            
            # Check for KOL holders (BONUS)
            kol_count = 0
            kol_names = []
            
            if kol_wallets or self.smart_wallet_tracker:
                tracked = kol_wallets or set(self.smart_wallet_tracker.tracked_wallets.keys())
                
                for holder in holders[:10]:
                    holder_addr = holder.get('address', '')
                    if holder_addr in tracked:
                        kol_count += 1
                        if self.smart_wallet_tracker:
                            wallet_info = self.smart_wallet_tracker.tracked_wallets.get(holder_addr, {})
                            kol_names.append(wallet_info.get('name', holder_addr[:8]))
            
            # Base penalty calculation
            if top_10_pct > 80:
                # EXTREME concentration = auto-drop
                return {
                    'top_10_percentage': top_10_pct,
                    'penalty': -999,
                    'kol_bonus': 0,
                    'has_kol_holders': kol_count > 0,
                    'kol_holders': kol_names,
                    'hard_drop': True,
                    'reason': f'HARD DROP: Top 10 hold {top_10_pct:.1f}% (extreme rug risk)'
                }
            
            elif top_10_pct > 70:
                base_penalty = -35
            elif top_10_pct > 50:
                base_penalty = -20
            elif top_10_pct > 40:
                base_penalty = -10
            else:
                base_penalty = 0
            
            # KOL BONUS: Smart money in top holders = good sign
            kol_bonus = 0
            final_penalty = base_penalty
            
            if kol_count > 0:
                kol_bonus = kol_count * 10  # +10 per KOL
                final_penalty = max(0, base_penalty + (kol_count * 5))  # Reduce penalty
                
                logger.info(f"   👑 {kol_count} KOLs in top 10: {', '.join(kol_names)}")
                logger.info(f"   💎 KOL bonus: +{kol_bonus} pts | Penalty reduced: {base_penalty} → {final_penalty}")
            
            return {
                'top_10_percentage': top_10_pct,
                'penalty': final_penalty,
                'kol_bonus': kol_bonus,
                'has_kol_holders': kol_count > 0,
                'kol_holders': kol_names,
                'kol_count': kol_count,
                'hard_drop': False,
                'reason': f'Top 10: {top_10_pct:.1f}% | KOLs: {kol_count}'
            }
            
        except Exception as e:
            logger.error(f"   ❌ Error checking holder concentration: {e}")
            return {
                'top_10_percentage': 0,
                'penalty': 0,
                'kol_bonus': 0,
                'has_kol_holders': False,
                'hard_drop': False,
                'reason': f'Check failed: {str(e)}'
            }
    
    def should_check_holders(
        self, 
        base_score: int, 
        bonding_pct: float,
        pre_grad_threshold: int = 65,
        post_grad_threshold: int = 60
    ) -> bool:
        """
        Decide if we should spend 10 credits checking holders
        
        Only check if:
        - Base score is high enough (promising token)
        - Pre-grad: base >= 65
        - Post-grad: base >= 60 (always check, more accurate data)
        """
        threshold = pre_grad_threshold if bonding_pct < 100 else post_grad_threshold
        should_check = base_score >= threshold
        
        if should_check:
            logger.debug(f"   ✅ Base score {base_score} >= {threshold} → Checking holders")
        else:
            logger.debug(f"   ⏭️  Base score {base_score} < {threshold} → Skipping holder check (save 10 credits)")
        
        return should_check
    
    def get_rug_score_adjustments(
        self,
        token_address: str,
        trades: List[Dict],
        unique_buyers: int,
        base_score: int,
        bonding_pct: float
    ) -> Dict:
        """
        Complete rug detection scoring adjustments
        
        Returns all penalties/bonuses in one dict for easy integration
        """
        # 1. Bundle detection (FREE)
        bundle_result = self.detect_bundles(token_address, trades, unique_buyers)
        
        # 2. Determine if we should check holders
        check_holders = self.should_check_holders(base_score, bonding_pct)
        
        return {
            'bundle_penalty': bundle_result['penalty'],
            'bundle_severity': bundle_result['severity'],
            'bundle_override': bundle_result['override_applied'],
            'should_check_holders': check_holders,
            'holder_check_threshold': 65 if bonding_pct < 100 else 60
        }
