"""
Conviction Engine - Scores tokens based on multiple signals
UPDATED: Added holder count and volume velocity scoring
"""
from typing import Dict
from datetime import datetime
from loguru import logger
import config


class ConvictionEngine:
    """
    Analyzes tokens and calculates conviction scores (0-100)
    
    Scoring breakdown:
    - Smart Wallet Activity: 0-40 points
    - Narrative Detection: 0-25 points
    - Holder Distribution: 0-15 points (NEW)
    - Volume Velocity: 0-10 points (NEW)
    - Price Momentum: 0-10 points
    Total: 0-100 points
    """
    
    def __init__(self, smart_wallet_tracker, narrative_detector):
        self.smart_wallet_tracker = smart_wallet_tracker
        self.narrative_detector = narrative_detector
        
    async def analyze_token(self, token_address: str, token_data: Dict) -> Dict:
        """
        Analyze a token and return conviction score with breakdown
        
        Args:
            token_address: Token mint address
            token_data: Token data from PumpPortal or DexScreener
            
        Returns:
            Dict with score and detailed breakdown
        """
        try:
            logger.info(f"🔍 Analyzing {token_data.get('token_symbol', 'UNKNOWN')} ({token_address[:8]}...)")
            
            # Initialize scores
            scores = {
                'smart_wallet': 0,
                'narrative': 0,
                'holders': 0,        # NEW
                'volume_velocity': 0, # NEW
                'momentum': 0,
                'total': 0
            }
            
            # 1. Smart Wallet Activity (0-40 points)
            smart_wallet_data = await self.smart_wallet_tracker.get_smart_wallet_activity(
                token_address, 
                hours=24
            )
            scores['smart_wallet'] = smart_wallet_data.get('score', 0)
            logger.info(f"   👑 Smart Wallets: {scores['smart_wallet']} points")
            
            # 2. Narrative Detection (0-25 points)
            narrative_data = await self.narrative_detector.detect_narratives(
                token_data.get('token_name', ''),
                token_data.get('token_symbol', '')
            )
            scores['narrative'] = narrative_data.get('score', 0)
            logger.info(f"   🎯 Narratives: {scores['narrative']} points")
            
            # 3. Holder Distribution (0-15 points) - NEW
            holder_count = token_data.get('holder_count', 0)
            scores['holders'] = self._score_holders(holder_count)
            logger.info(f"   👥 Holders ({holder_count}): {scores['holders']} points")
            
            # 4. Volume Velocity (0-10 points) - NEW
            scores['volume_velocity'] = self._score_volume_velocity(token_data)
            logger.info(f"   📊 Volume Velocity: {scores['volume_velocity']} points")
            
            # 5. Price Momentum (0-10 points)
            scores['momentum'] = self._score_momentum(token_data)
            logger.info(f"   🚀 Momentum: {scores['momentum']} points")
            
            # Calculate total
            scores['total'] = sum(scores.values()) - scores['total']  # Subtract total itself
            
            logger.info(f"   💎 TOTAL CONVICTION: {scores['total']}/100")
            
            # Prepare detailed response
            return {
                'score': scores['total'],
                'breakdown': scores,
                'smart_wallet_data': smart_wallet_data,
                'narrative_data': narrative_data,
                'token_data': token_data,
                'holder_count': holder_count,
                'meets_threshold': scores['total'] >= config.MIN_CONVICTION_SCORE
            }
            
        except Exception as e:
            logger.error(f"❌ Error analyzing token: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'score': 0,
                'breakdown': {},
                'error': str(e)
            }
    
    def _score_holders(self, holder_count: int) -> int:
        """
        Score based on holder count
        
        Args:
            holder_count: Number of unique holders
            
        Returns:
            Score (0-15 points)
        """
        if holder_count >= 100:
            return config.WEIGHTS['holders_high']  # 15 points
        elif holder_count >= 50:
            return config.WEIGHTS['holders_medium']  # 10 points
        elif holder_count >= config.MIN_HOLDERS:
            return config.WEIGHTS['holders_low']  # 5 points
        else:
            # Below minimum - token should be filtered
            return 0
    
    def _score_volume_velocity(self, token_data: Dict) -> int:
        """
        Score based on volume velocity (how fast volume is growing)
        
        Compares recent volume to liquidity and checks for spikes
        
        Args:
            token_data: Token data with volume metrics
            
        Returns:
            Score (0-10 points)
        """
        try:
            volume_5m = token_data.get('volume_5m', 0)
            volume_1h = token_data.get('volume_1h', 0)
            volume_24h = token_data.get('volume_24h', 0)
            liquidity = token_data.get('liquidity', 1)  # Avoid division by zero
            
            # Method 1: Check if volume doubled in 5 minutes
            # (Compare 5m volume to average 1h rate)
            if volume_1h > 0:
                avg_5m_volume = volume_1h / 12  # Expected volume per 5min if steady
                
                if volume_5m >= avg_5m_volume * 2:
                    # Volume spiking! (2x expected rate)
                    logger.debug(f"      📈 Volume spike detected: {volume_5m:.0f} vs expected {avg_5m_volume:.0f}")
                    return config.WEIGHTS['volume_spiking']  # 10 points
                    
                elif volume_5m >= avg_5m_volume * 1.25:
                    # Volume growing (1.25x expected rate)
                    logger.debug(f"      📈 Volume growing: {volume_5m:.0f} vs expected {avg_5m_volume:.0f}")
                    return config.WEIGHTS['volume_growing']  # 5 points
            
            # Method 2: Fallback - check volume/liquidity ratio
            # High ratio = lots of trading activity
            if liquidity > 0:
                vol_liq_ratio = volume_24h / liquidity
                
                if vol_liq_ratio >= 3.0:
                    # Very high trading volume relative to liquidity
                    logger.debug(f"      📈 High vol/liq ratio: {vol_liq_ratio:.2f}")
                    return config.WEIGHTS['volume_growing']  # 5 points
            
            return 0
            
        except Exception as e:
            logger.error(f"❌ Error scoring volume velocity: {e}")
            return 0
    
    def _score_momentum(self, token_data: Dict) -> int:
        """
        Score based on price momentum
        
        Args:
            token_data: Token data with price change metrics
            
        Returns:
            Score (0-10 points)
        """
        try:
            price_change_5m = token_data.get('price_change_5m', 0)
            
            if price_change_5m >= 50:
                # Very strong momentum (+50% in 5min)
                return config.WEIGHTS['momentum_very_strong']  # 10 points
            elif price_change_5m >= 20:
                # Strong momentum (+20% in 5min)
                return config.WEIGHTS['momentum_strong']  # 5 points
            else:
                return 0
                
        except Exception as e:
            logger.error(f"❌ Error scoring momentum: {e}")
            return 0
