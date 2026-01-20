"""
Conviction Engine - Scores tokens based on multiple signals
UPDATED: Tiered scoring system with FREE pre-grad distribution via unique buyers
"""
from typing import Dict
from datetime import datetime
from loguru import logger
import config


class ConvictionEngine:
    """
    Analyzes tokens and calculates conviction scores (0-100)
    
    TIERED SCORING STRATEGY:
    
    TIER 1 (FREE - 0 credits):
    - Smart Wallet Activity: 0-40 points
    - Volume Velocity: 0-10 points
    - Price Momentum: 0-10 points
    Max FREE score: 60 points
    
    TIER 2 (CONDITIONAL - 0 or 10 credits):
    - If base_score >= 50:
      - Pre-graduation: Unique Buyers 0-15 points (FREE)
      - Post-graduation: Real Holders 0-15 points (10 credits)
    - If base_score < 50: Skip (save credits)
    
    Total possible: 0-75 points
    
    Signal Thresholds:
    - Pre-graduation (40-60% bonding): 80+ points required (higher risk)
    - Post-graduation (100% graduated): 75+ points required (safer)
    """
    
    def __init__(self, smart_wallet_tracker, helius_client=None):
        self.smart_wallet_tracker = smart_wallet_tracker
        self.helius_client = helius_client
        
    async def analyze_token(self, token_address: str, token_data: Dict) -> Dict:
        """
        Analyze a token and return conviction score with breakdown
        
        Uses tiered scoring to minimize API calls:
        1. Calculate FREE base score first
        2. Only fetch expensive data if base score warrants it
        
        Args:
            token_address: Token mint address
            token_data: Token data from PumpPortal (includes unique_buyers for pre-grad)
            
        Returns:
            Dict with score and detailed breakdown
        """
        try:
            symbol = token_data.get('token_symbol', 'UNKNOWN')
            bonding_pct = token_data.get('bonding_curve_pct', 0)
            is_pre_grad = bonding_pct < 100
            
            logger.info(f"🔍 Analyzing ${symbol} ({token_address[:8]}...) - {'PRE' if is_pre_grad else 'POST'}-GRAD")
            
            # Initialize scores
            scores = {
                'smart_wallet': 0,
                'volume_velocity': 0,
                'momentum': 0,
                'distribution': 0,
                'total': 0
            }
            
            # ============================================================
            # TIER 1: FREE BASE SCORE CALCULATION (0 credits)
            # ============================================================
            
            # 1. Smart Wallet Activity (0-40 points)
            smart_wallet_data = await self.smart_wallet_tracker.get_smart_wallet_activity(
                token_address, 
                hours=24
            )
            scores['smart_wallet'] = smart_wallet_data.get('score', 0)
            logger.info(f"   👑 Smart Wallets: {scores['smart_wallet']}/40 points")
            
            # 2. Volume Velocity (0-10 points)
            scores['volume_velocity'] = self._score_volume_velocity(token_data)
            logger.info(f"   📊 Volume Velocity: {scores['volume_velocity']}/10 points")
            
            # 3. Price Momentum (0-10 points)
            scores['momentum'] = self._score_momentum(token_data)
            logger.info(f"   🚀 Price Momentum: {scores['momentum']}/10 points")
            
            # Calculate base score (no API calls made yet!)
            base_score = (
                scores['smart_wallet'] + 
                scores['volume_velocity'] + 
                scores['momentum']
            )
            
            logger.info(f"   💰 BASE SCORE: {base_score}/60 (FREE)")
            
            # ============================================================
            # TIER 2: CONDITIONAL DISTRIBUTION CHECK
            # ============================================================
            
            if base_score >= 50:
                # Token has strong signals - worth investigating distribution
                
                if is_pre_grad:
                    # PRE-GRADUATION: Use unique buyers (FREE!)
                    unique_buyers = token_data.get('unique_buyers', 0)
                    tracking_mins = token_data.get('buyer_tracking_minutes', 0)
                    
                    scores['distribution'] = self._score_unique_buyers(unique_buyers)
                    logger.info(f"   👥 Unique Buyers ({unique_buyers} in {tracking_mins:.1f}min): {scores['distribution']}/15 points (FREE)")
                
                else:
                    # POST-GRADUATION: Use real holders (10 credits)
                    holder_count = token_data.get('holder_count', 0)
                    
                    if holder_count == 0 and self.helius_client:
                        # Need to fetch from Helius
                        holder_count = await self._fetch_holders_from_helius(token_address)
                        logger.info(f"   👥 Holders fetched from Helius: {holder_count} (10 credits)")
                    
                    scores['distribution'] = self._score_holders(holder_count)
                    logger.info(f"   👥 Holders ({holder_count}): {scores['distribution']}/15 points (10 credits)")
            
            else:
                # Base score too low - skip distribution check to save credits
                logger.info(f"   ⏭️ Skipped distribution check (base {base_score} < 50) - SAVED CREDITS")
            
            # ============================================================
            # FINAL SCORE CALCULATION
            # ============================================================
            
            scores['total'] = sum(scores.values()) - scores['total']  # Subtract total itself
            
            # Check threshold based on graduation status
            meets_threshold = self._check_threshold(scores['total'], bonding_pct)
            threshold = 80 if is_pre_grad else 75
            
            if meets_threshold:
                logger.success(f"   🎯 CONVICTION: {scores['total']}/100 - MEETS THRESHOLD ({threshold}+)")
            else:
                logger.info(f"   💎 CONVICTION: {scores['total']}/100 - Below threshold ({threshold}+)")
            
            # Prepare detailed response
            return {
                'score': scores['total'],
                'breakdown': scores,
                'smart_wallet_data': smart_wallet_data,
                'token_data': token_data,
                'unique_buyers': token_data.get('unique_buyers', 0),
                'holder_count': token_data.get('holder_count', 0),
                'is_pre_graduation': is_pre_grad,
                'threshold': threshold,
                'meets_threshold': meets_threshold
            }
            
        except Exception as e:
            logger.error(f"❌ Error analyzing token: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'score': 0,
                'breakdown': {},
                'error': str(e),
                'meets_threshold': False
            }
    
    def _score_unique_buyers(self, buyer_count: int) -> int:
        """
        Score based on unique buyer count (pre-grad proxy for distribution)
        
        This is a FREE metric from PumpPortal WebSocket that correlates 
        strongly with organic interest during bonding curve.
        
        Many unique buyers = good distribution building
        Few unique buyers = possible coordinated/whale play
        
        Args:
            buyer_count: Number of unique buyers tracked
            
        Returns:
            Score (0-15 points)
        """
        if buyer_count >= 50:
            return 15  # Strong organic interest
        elif buyer_count >= 30:
            return 10  # Medium interest
        elif buyer_count >= 15:
            return 5   # Weak interest
        else:
            return 0   # Too few = coordinated/whale play
    
    def _score_holders(self, holder_count: int) -> int:
        """
        Score based on holder count (post-grad - costs 10 credits)
        
        Only called for graduated tokens where holder data is accurate
        and the play is safer (liquidity locked in Raydium).
        
        Args:
            holder_count: Number of unique holders
            
        Returns:
            Score (0-15 points)
        """
        if holder_count >= 100:
            return 15  # Strong distribution
        elif holder_count >= 50:
            return 10  # Medium distribution
        elif holder_count >= 20:
            return 5   # Weak distribution
        else:
            return 0   # Below minimum - possible rug
    
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
                    logger.debug(f"      📈 Volume spike: {volume_5m:.0f} vs expected {avg_5m_volume:.0f}")
                    return 10
                    
                elif volume_5m >= avg_5m_volume * 1.25:
                    # Volume growing (1.25x expected rate)
                    logger.debug(f"      📈 Volume growing: {volume_5m:.0f} vs expected {avg_5m_volume:.0f}")
                    return 5
            
            # Method 2: Fallback - check volume/liquidity ratio
            # High ratio = lots of trading activity
            if liquidity > 0:
                vol_liq_ratio = volume_24h / liquidity
                
                if vol_liq_ratio >= 3.0:
                    # Very high trading volume relative to liquidity
                    logger.debug(f"      📈 High vol/liq ratio: {vol_liq_ratio:.2f}")
                    return 5
            
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
                return 10
            elif price_change_5m >= 20:
                # Strong momentum (+20% in 5min)
                return 5
            else:
                return 0
                
        except Exception as e:
            logger.error(f"❌ Error scoring momentum: {e}")
            return 0
    
    async def _fetch_holders_from_helius(self, token_address: str) -> int:
        """
        Fetch holder count from Helius API (POST-GRADUATION ONLY - 10 credits)
        
        This should ONLY be called for graduated tokens where the base score
        is high enough to warrant the credit cost.
        
        Args:
            token_address: Token mint address
            
        Returns:
            Number of holders (0 if error)
        """
        if not self.helius_client:
            logger.warning("⚠️ Helius client not configured, cannot fetch holders")
            return 0
        
        try:
            import aiohttp
            
            url = f"https://mainnet.helius-rpc.com/?api-key={config.HELIUS_API_KEY}"
            
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenAccounts",
                "params": {
                    "mint": token_address,
                    "options": {
                        "showZeroBalance": False
                    }
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 429:
                        logger.warning(f"⚠️ Helius rate limited (429)")
                        return 0
                    
                    if resp.status != 200:
                        logger.warning(f"⚠️ Helius returned {resp.status}")
                        return 0
                    
                    data = await resp.json()
                    
                    # Check for errors
                    if 'error' in data:
                        logger.warning(f"⚠️ Helius error: {data['error']}")
                        return 0
                    
                    # Get token accounts
                    token_accounts = data.get('result', {}).get('token_accounts', [])
                    holder_count = len(token_accounts)
                    
                    return holder_count
                    
        except Exception as e:
            logger.warning(f"⚠️ Error fetching holders from Helius: {e}")
            return 0
    
    def _check_threshold(self, score: int, bonding_pct: float) -> bool:
        """
        Check if score meets threshold based on graduation status
        
        Args:
            score: Total conviction score
            bonding_pct: Bonding curve percentage (0-100)
            
        Returns:
            True if meets threshold, False otherwise
        """
        if bonding_pct < 100:
            # Pre-graduation: Higher threshold (riskier play)
            return score >= config.MIN_CONVICTION_SCORE  # Should be 80
        else:
            # Post-graduation: Lower threshold (safer play, liquidity locked)
            return score >= 75
