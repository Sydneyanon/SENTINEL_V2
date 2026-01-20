"""
Conviction Engine - Scores tokens based on multiple signals
UPDATED: Integrated rug detection (bundle detection + holder concentration)
"""
from typing import Dict, Optional
from datetime import datetime
from loguru import logger
import config
from rug_detector import RugDetector


class ConvictionEngine:
    """
    Analyzes tokens and calculates conviction scores (0-100)
    
    Scoring breakdown (with rug detection):
    - Smart Wallet Activity: 0-40 points
    - Narrative Detection: 0-25 points (if enabled)
    - Unique Buyers: 0-15 points
    - Volume Velocity: 0-10 points
    - Price Momentum: 0-10 points
    - Bundle Penalty: -5 to -40 points (with overrides)
    - Holder Concentration: -15 to -40 points (with KOL bonus)
    Total: 0-100+ points (can exceed 100 with bonuses)
    """
    
    def __init__(
        self, 
        smart_wallet_tracker,
        narrative_detector=None,
        helius_fetcher=None,
        active_tracker=None
    ):
        self.smart_wallet_tracker = smart_wallet_tracker
        self.narrative_detector = narrative_detector
        self.helius_fetcher = helius_fetcher
        self.active_tracker = active_tracker
        
        # Initialize rug detector
        self.rug_detector = RugDetector(smart_wallet_tracker=smart_wallet_tracker)
        
    async def analyze_token(
        self, 
        token_address: str, 
        token_data: Dict,
        pumpportal_trades: Optional[list] = None
    ) -> Dict:
        """
        Analyze a token and return conviction score with rug detection
        
        Args:
            token_address: Token mint address
            token_data: Token data from PumpPortal/DexScreener
            pumpportal_trades: List of trades for bundle detection (optional)
            
        Returns:
            Dict with score, breakdown, and rug check results
        """
        try:
            token_symbol = token_data.get('token_symbol', 'UNKNOWN')
            token_name = token_data.get('token_name', token_symbol)
            bonding_pct = token_data.get('bonding_curve_pct', 0)
            is_pre_grad = bonding_pct < 100
            
            logger.info(f"🔍 Analyzing ${token_symbol} ({token_address[:8]}...) - {'PRE-GRAD' if is_pre_grad else 'POST-GRAD'}")
            
            # ================================================================
            # PHASE 1: FREE BASE SCORE (0-60 points)
            # ================================================================
            
            base_scores = {}
            
            # 1. Smart Wallet Activity (0-40 points)
            smart_wallet_data = await self.smart_wallet_tracker.get_smart_wallet_activity(
                token_address, 
                hours=24
            )
            base_scores['smart_wallet'] = smart_wallet_data.get('score', 0)
            logger.info(f"   👑 Smart Wallets: {base_scores['smart_wallet']} points")
            
            # 2. Narrative Detection (0-25 points) - if enabled
            if self.narrative_detector and config.ENABLE_NARRATIVES:
                narrative_data = self.narrative_detector.analyze_token(
                    token_symbol,
                    token_name,
                    token_data.get('description', '')
                )
                base_scores['narrative'] = narrative_data.get('score', 0)
                logger.info(f"   🎯 Narratives: {base_scores['narrative']} points")
            else:
                base_scores['narrative'] = 0
            
            # 3. Volume Velocity (0-10 points)
            volume_score = self._score_volume_velocity(token_data)
            base_scores['volume'] = volume_score
            logger.info(f"   📊 Volume: {volume_score} points")
            
            # 4. Price Momentum (0-10 points)
            momentum_score = self._score_price_momentum(token_data)
            base_scores['momentum'] = momentum_score
            logger.info(f"   🚀 Momentum: {momentum_score} points")
            
            base_total = sum(base_scores.values())
            logger.info(f"   💰 BASE SCORE: {base_total}/85")
            
            # ================================================================
            # PHASE 2: BUNDLE DETECTION (FREE) ⭐
            # ================================================================
            
            bundle_result = {'penalty': 0, 'severity': 'none'}
            
            if config.RUG_DETECTION['enabled'] and config.RUG_DETECTION['bundles']['detect']:
                # Get trades from active_tracker if not provided
                if pumpportal_trades is None and self.active_tracker:
                    pumpportal_trades = self.active_tracker.get_token_trades(token_address)
                
                # Get unique buyers count
                unique_buyers = 0
                if self.active_tracker:
                    unique_buyers = len(self.active_tracker.unique_buyers.get(token_address, set()))
                
                if pumpportal_trades:
                    bundle_result = self.rug_detector.detect_bundles(
                        token_address,
                        pumpportal_trades,
                        unique_buyers
                    )
                    
                    if bundle_result['penalty'] != 0:
                        logger.warning(f"   🚨 {bundle_result['severity'].upper()} BUNDLE: {bundle_result['penalty']} pts")
                        logger.info(f"      {bundle_result['reason']}")
            
            adjusted_base = base_total + bundle_result['penalty']
            
            # Early exit if base + bundle penalty too low
            if adjusted_base < 50:
                logger.info(f"   ⏭️  Base+Bundle: {adjusted_base}/100 - Too low for further analysis")
                return {
                    'score': adjusted_base,
                    'passed': False,
                    'reason': 'Base score + bundle penalty too low',
                    'breakdown': {
                        **base_scores,
                        'bundle_penalty': bundle_result['penalty'],
                        'total': adjusted_base
                    }
                }
            
            # ================================================================
            # PHASE 3: UNIQUE BUYERS (FREE)
            # ================================================================
            
            unique_buyers_score = 0
            if self.active_tracker:
                unique_buyers = len(self.active_tracker.unique_buyers.get(token_address, set()))
                unique_buyers_score = self._score_unique_buyers(unique_buyers)
                logger.info(f"   👥 Unique Buyers ({unique_buyers}): {unique_buyers_score} points")
            
            mid_total = adjusted_base + unique_buyers_score
            logger.info(f"   💎 MID SCORE: {mid_total}/100")
            
            # ================================================================
            # PHASE 4: HOLDER CONCENTRATION CHECK (10 CREDITS) ⭐
            # ================================================================
            
            holder_result = {'penalty': 0, 'kol_bonus': 0, 'hard_drop': False}
            
            if config.RUG_DETECTION['enabled'] and config.RUG_DETECTION['holder_concentration']['check']:
                # Decide if we should spend 10 credits
                should_check = self.rug_detector.should_check_holders(
                    mid_total,
                    bonding_pct
                )
                
                if should_check and self.helius_fetcher:
                    holder_result = await self.rug_detector.check_holder_concentration(
                        token_address,
                        self.helius_fetcher,
                        kol_wallets=set(self.smart_wallet_tracker.tracked_wallets.keys())
                    )
                    
                    if holder_result['hard_drop']:
                        logger.error(f"   💀 HARD DROP: {holder_result['reason']}")
                        return {
                            'score': 0,
                            'passed': False,
                            'reason': holder_result['reason'],
                            'breakdown': {
                                **base_scores,
                                'bundle_penalty': bundle_result['penalty'],
                                'unique_buyers': unique_buyers_score,
                                'holder_penalty': -999,
                                'total': 0
                            }
                        }
                    
                    if holder_result['penalty'] != 0:
                        logger.warning(f"   ⚠️  Holder Concentration: {holder_result['penalty']} pts")
                    
                    if holder_result['kol_bonus'] > 0:
                        logger.info(f"   💎 KOL Bonus: +{holder_result['kol_bonus']} pts")
                        logger.info(f"      {holder_result['reason']}")
            
            # ================================================================
            # FINAL SCORE CALCULATION
            # ================================================================
            
            final_score = mid_total + holder_result['penalty'] + holder_result['kol_bonus']
            
            # Determine threshold
            threshold = config.MIN_CONVICTION_SCORE if is_pre_grad else config.POST_GRAD_THRESHOLD
            
            passed = final_score >= threshold
            
            logger.info("=" * 60)
            logger.info(f"   🎯 FINAL CONVICTION: {final_score}/100")
            logger.info(f"   📊 Threshold: {threshold} ({'PRE-GRAD' if is_pre_grad else 'POST-GRAD'})")
            logger.info(f"   {'✅ SIGNAL!' if passed else '⏭️  Skip'}")
            logger.info("=" * 60)
            
            return {
                'score': final_score,
                'passed': passed,
                'threshold': threshold,
                'is_pre_grad': is_pre_grad,
                'breakdown': {
                    'smart_wallet': base_scores['smart_wallet'],
                    'narrative': base_scores['narrative'],
                    'volume': base_scores['volume'],
                    'momentum': base_scores['momentum'],
                    'bundle_penalty': bundle_result['penalty'],
                    'unique_buyers': unique_buyers_score,
                    'holder_penalty': holder_result['penalty'],
                    'kol_bonus': holder_result['kol_bonus'],
                    'total': final_score
                },
                'rug_checks': {
                    'bundle': bundle_result,
                    'holder_concentration': holder_result
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error analyzing token: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'score': 0,
                'passed': False,
                'reason': f'Analysis error: {str(e)}'
            }
    
    def _score_volume_velocity(self, token_data: Dict) -> int:
        """Score based on volume velocity (0-10 points)"""
        volume_24h = token_data.get('volume_24h', 0)
        mcap = token_data.get('market_cap', 1)
        
        if mcap == 0:
            return 0
        
        volume_to_mcap = volume_24h / mcap if mcap > 0 else 0
        
        # High volume relative to mcap = strong activity
        if volume_to_mcap > 2.0:  # 200%+ daily volume
            return config.VOLUME_WEIGHTS['spiking']
        elif volume_to_mcap > 1.25:  # 125%+ daily volume
            return config.VOLUME_WEIGHTS['growing']
        else:
            return 0
    
    def _score_price_momentum(self, token_data: Dict) -> int:
        """Score based on price momentum (0-10 points)"""
        # Get price change from token_data
        price_change = token_data.get('price_change_5m', 0)
        
        if price_change >= 50:  # +50% in 5 min
            return config.MOMENTUM_WEIGHTS['very_strong']
        elif price_change >= 20:  # +20% in 5 min
            return config.MOMENTUM_WEIGHTS['strong']
        else:
            return 0
    
    def _score_unique_buyers(self, unique_buyers: int) -> int:
        """Score based on unique buyer count (0-15 points)"""
        weights = config.UNIQUE_BUYER_WEIGHTS
        
        if unique_buyers >= 100:
            return weights['exceptional']
        elif unique_buyers >= 70:
            return weights['high']
        elif unique_buyers >= 40:
            return weights['medium']
        elif unique_buyers >= 20:
            return weights['low']
        else:
            return weights['minimal']
