"""
Conviction Engine - Scores tokens based on multiple signals
UPDATED: Integrated rug detection + LunarCrush social sentiment
"""
from typing import Dict, Optional
from datetime import datetime, timedelta
from loguru import logger
import config
from rug_detector import RugDetector
from lunarcrush_fetcher import get_lunarcrush_fetcher
from twitter_fetcher import get_twitter_fetcher


class ConvictionEngine:
    """
    Analyzes tokens and calculates conviction scores (0-100)

    Scoring breakdown (with rug detection):
    - Smart Wallet Activity: 0-40 points
    - Narrative Detection: 0-25 points (if enabled)
    - Unique Buyers: 0-15 points
    - Volume Velocity: 0-10 points
    - Price Momentum: 0-10 points
    - LunarCrush Social: 0-20 points (if enabled)
    - Twitter Buzz: 0-15 points (if enabled)
    - Bundle Penalty: -5 to -40 points (with overrides)
    - Holder Concentration: -15 to -40 points (with KOL bonus)
    Total: 0-135+ points (can exceed with bonuses)
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

        # Initialize LunarCrush fetcher
        self.lunarcrush = get_lunarcrush_fetcher()

        # Initialize Twitter fetcher
        self.twitter = get_twitter_fetcher()
        
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
                if base_scores['narrative'] > 0:
                    logger.info(f"   🎯 Narratives: {base_scores['narrative']} points (matched: {narrative_data.get('primary_narrative', 'N/A')})")
                else:
                    logger.info(f"   🎯 Narratives: 0 points (no narrative match)")
            else:
                base_scores['narrative'] = 0
                logger.info(f"   🎯 Narratives: DISABLED (0 points)")
            
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

            # ================================================================
            # PHASE 3: UNIQUE BUYERS (FREE)
            # ================================================================

            unique_buyers_score = 0
            if self.active_tracker:
                unique_buyers = len(self.active_tracker.unique_buyers.get(token_address, set()))
                unique_buyers_score = self._score_unique_buyers(unique_buyers)
                if unique_buyers_score > 0:
                    logger.info(f"   👥 Unique Buyers ({unique_buyers}): +{unique_buyers_score} points")
                else:
                    logger.info(f"   👥 Unique Buyers ({unique_buyers}): 0 points (need 5+ for scoring)")
            else:
                logger.info(f"   👥 Unique Buyers: DISABLED (active_tracker not initialized)")

            mid_total = adjusted_base + unique_buyers_score
            logger.info(f"   💎 MID SCORE: {mid_total}/100")

            # Early exit if mid score (base + bundle + unique buyers) too low
            # LOWERED: Was 50, now 20 to allow Twitter/social checks on early tokens
            if mid_total < 20:
                logger.info(f"   ⏭️  Mid Score: {mid_total}/100 - Too low for further analysis")
                return {
                    'score': mid_total,
                    'passed': False,
                    'reason': 'Score too low after unique buyers',
                    'token_address': token_address,  # FIXED: Include for logging
                    'token_data': token_data,  # FIXED: Include token data
                    'breakdown': {
                        **base_scores,
                        'bundle_penalty': bundle_result['penalty'],
                        'unique_buyers': unique_buyers_score,
                        'total': mid_total
                    }
                }

            # ================================================================
            # PHASE 3.5: SOCIAL SENTIMENT (LUNARCRUSH) - FREE
            # ================================================================

            social_score = 0
            social_data = {}

            if config.ENABLE_LUNARCRUSH:
                social_data = await self._score_social_sentiment(token_symbol)
                social_score = social_data.get('score', 0)

                if social_score > 0:
                    logger.info(f"   🌙 LunarCrush: +{social_score} points")
                    if social_data.get('is_trending'):
                        logger.info(f"      📈 TRENDING in top {social_data['trending_rank']}")
                    if social_data.get('sentiment', 0) > 3.5:
                        logger.info(f"      😊 Bullish sentiment: {social_data['sentiment']}/5")

            mid_total += social_score

            # ================================================================
            # PHASE 3.6: TWITTER BUZZ (FREE TIER) - FREE
            # ================================================================
            # SELECTIVE: Check when token is at 40%+ bonding AND 25+ conviction
            # LOWERED: Was 60%/70, now 40%/25 to catch early KOL plays
            # Free tier: 100 tweet reads/month with max_results=5 = ~5 calls/week

            twitter_score = 0
            twitter_data = {}

            if config.ENABLE_TWITTER and bonding_pct >= 40 and mid_total >= 25:
                logger.info(f"   🐦 Checking Twitter (bonding: {bonding_pct}%, score: {mid_total})...")
                twitter_data = await self._score_twitter_buzz(token_symbol, token_address)
                twitter_score = twitter_data.get('score', 0)

                if twitter_score > 0:
                    logger.info(f"   🐦 Twitter: +{twitter_score} points")
                    if twitter_data.get('has_buzz'):
                        logger.info(f"      🔥 BUZZ: {twitter_data['mention_count']} mentions, {twitter_data['total_engagement']} engagement")
                else:
                    logger.info(f"   🐦 Twitter: No buzz detected")

            mid_total += twitter_score

            # ================================================================
            # PHASE 3.7: SOCIAL CONFIRMATION (TELEGRAM CALLS) - FREE
            # ================================================================
            # Check Telegram calls as soon as KOL buys any token
            # Variable scoring based on mention intensity and recency

            social_confirmation_score = 0
            telegram_call_data = {}

            if config.ENABLE_TELEGRAM_SCRAPER:
                try:
                    # Import from main
                    from main import telegram_calls_cache

                    logger.info(f"   📡 Checking Telegram calls for {token_address[:8]}...")
                    logger.info(f"      Cache has {len(telegram_calls_cache)} token(s)")

                    if token_address in telegram_calls_cache:
                        call_data = telegram_calls_cache[token_address]
                        now = datetime.now()

                        # Get recent mentions (last 10 min)
                        recent_cutoff = now - timedelta(minutes=10)
                        recent_mentions = [
                            m for m in call_data['mentions']
                            if m['timestamp'] > recent_cutoff
                        ]

                        # Get very recent mentions (last 5 min) for intensity check
                        very_recent_cutoff = now - timedelta(minutes=5)
                        very_recent_mentions = [
                            m for m in call_data['mentions']
                            if m['timestamp'] > very_recent_cutoff
                        ]

                        mention_count = len(recent_mentions)
                        very_recent_count = len(very_recent_mentions)
                        group_count = len(call_data['groups'])

                        # Calculate call age (time since first mention)
                        call_age = now - call_data['first_seen']
                        call_age_minutes = call_age.total_seconds() / 60

                        # Variable scoring based on Grok's recommendations
                        if mention_count >= 6 or group_count >= 3:
                            # High intensity: 6+ mentions OR 3+ groups
                            social_confirmation_score = 15
                            telegram_call_data['intensity'] = 'high'
                        elif mention_count >= 3 or (very_recent_count >= 2 and group_count >= 2):
                            # Medium intensity: 3-5 mentions OR growing buzz
                            social_confirmation_score = 10
                            telegram_call_data['intensity'] = 'medium'
                        elif mention_count >= 1:
                            # Low intensity: 1-2 mentions
                            social_confirmation_score = 5
                            telegram_call_data['intensity'] = 'low'

                        # Age decay: reduce points if call is old
                        if call_age_minutes > 120:  # >2 hours old
                            social_confirmation_score = int(social_confirmation_score * 0.5)
                            telegram_call_data['aged'] = True

                        if social_confirmation_score > 0:
                            logger.info(f"   🔥 TELEGRAM CALL BONUS: +{social_confirmation_score} pts")
                            logger.info(f"      {mention_count} mention(s) from {group_count} group(s) ({call_age_minutes:.0f}m ago)")

                            telegram_call_data.update({
                                'mentions': mention_count,
                                'groups': group_count,
                                'call_age_minutes': call_age_minutes,
                                'score': social_confirmation_score
                            })
                    else:
                        logger.info(f"      ❌ No Telegram calls found for this token")

                except Exception as e:
                    logger.error(f"   ❌ Error checking Telegram calls: {e}")
                    social_confirmation_score = 0

            # Cap total social score (Twitter + Telegram) at 25 pts
            # This prevents over-scoring noisy hype
            total_social = twitter_score + social_confirmation_score
            if total_social > 25:
                excess = total_social - 25
                social_confirmation_score -= excess
                logger.info(f"   ⚖️  Social cap applied: reduced Telegram by {excess} pts (max 25 total)")
                telegram_call_data['capped'] = True

            mid_total += social_confirmation_score

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
                            'token_address': token_address,  # FIXED: Include token address
                            'token_data': token_data,  # FIXED: Include token data
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

            # Debug: Log token metadata being returned
            logger.info(f"   🏷️  Token metadata: {token_data.get('token_symbol')} / {token_data.get('token_name')}")

            return {
                'score': final_score,
                'passed': passed,
                'threshold': threshold,
                'is_pre_grad': is_pre_grad,
                'token_address': token_address,  # FIXED: Include token address for links
                'token_data': token_data,  # FIXED: Include full token data
                'breakdown': {
                    'smart_wallet': base_scores['smart_wallet'],
                    'narrative': base_scores['narrative'],
                    'volume': base_scores['volume'],
                    'momentum': base_scores['momentum'],
                    'bundle_penalty': bundle_result['penalty'],
                    'unique_buyers': unique_buyers_score,
                    'social_sentiment': social_score,
                    'twitter_buzz': twitter_score,
                    'telegram_calls': social_confirmation_score,
                    'holder_penalty': holder_result['penalty'],
                    'kol_bonus': holder_result['kol_bonus'],
                    'total': final_score
                },
                'rug_checks': {
                    'bundle': bundle_result,
                    'holder_concentration': holder_result
                },
                'social_data': social_data,
                'twitter_data': twitter_data,
                'telegram_call_data': telegram_call_data,
                'smart_wallet_data': smart_wallet_data  # FIXED: Include wallet data for display
            }
            
        except Exception as e:
            logger.error(f"❌ Error analyzing token: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'score': 0,
                'passed': False,
                'reason': f'Analysis error: {str(e)}',
                'token_address': token_address if 'token_address' in locals() else 'N/A',  # FIXED: Include if available
                'token_data': token_data if 'token_data' in locals() else {}  # FIXED: Include if available
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

        if unique_buyers >= 50:
            return weights['exceptional']
        elif unique_buyers >= 30:
            return weights['high']
        elif unique_buyers >= 15:
            return weights['medium']
        elif unique_buyers >= 5:
            return weights['low']
        else:
            return weights['minimal']

    async def _score_social_sentiment(self, token_symbol: str) -> Dict:
        """
        Score based on LunarCrush social sentiment (0-20 points)

        Scoring breakdown:
        - Trending in top 50: +10 points
        - Bullish sentiment (>3.5): +5 points
        - High social volume growth (>50%): +5 points

        Returns:
            Dict with score and metrics
        """
        try:
            metrics = await self.lunarcrush.get_coin_social_metrics(token_symbol)

            if not metrics:
                return {'score': 0}

            score = 0
            is_trending = False

            # 1. Trending bonus (0-10 points)
            trending_rank = metrics.get('trending_rank', 999)
            if trending_rank <= 20:
                score += 10
                is_trending = True
            elif trending_rank <= 50:
                score += 7
                is_trending = True
            elif trending_rank <= 100:
                score += 3
                is_trending = True

            # 2. Sentiment bonus (0-5 points)
            sentiment = metrics.get('sentiment', 0)
            if sentiment >= 4.0:  # Very bullish
                score += 5
            elif sentiment >= 3.5:  # Bullish
                score += 3

            # 3. Social volume growth (0-5 points)
            volume_change = metrics.get('social_volume_24h_change', 0)
            if volume_change >= 100:  # 100%+ growth
                score += 5
            elif volume_change >= 50:  # 50%+ growth
                score += 3

            return {
                'score': score,
                'is_trending': is_trending,
                'trending_rank': trending_rank,
                'sentiment': sentiment,
                'social_volume': metrics.get('social_volume', 0),
                'volume_change_24h': volume_change,
                'galaxy_score': metrics.get('galaxy_score', 0)
            }

        except Exception as e:
            logger.error(f"❌ Error scoring social sentiment: {e}")
            return {'score': 0}

    async def _score_twitter_buzz(self, token_symbol: str, token_address: str) -> Dict:
        """
        Score based on Twitter buzz (0-15 points)

        Scoring breakdown:
        - High buzz (5+ mentions, 10+ avg engagement): +15 points
        - Medium buzz (3+ mentions, decent engagement): +10 points
        - Low buzz (some mentions): +5 points

        Returns:
            Dict with score and metrics
        """
        try:
            metrics = await self.twitter.get_token_twitter_metrics(
                token_symbol,
                ca=token_address
            )

            if not metrics:
                return {'score': 0}

            score = 0

            # 1. Buzz detection (0-15 points)
            if metrics.get('has_buzz'):
                # High engagement detected
                score += 15
            elif metrics['mention_count'] >= 3:
                # Medium buzz
                score += 10
            elif metrics['mention_count'] >= 1:
                # Low buzz
                score += 5

            # 2. Top tweet bonus (viral tweet detected)
            if metrics['top_tweet_likes'] >= 100:
                score = max(score, 12)  # At least 12 points if viral tweet

            return {
                'score': score,
                'mention_count': metrics['mention_count'],
                'total_engagement': metrics['total_engagement'],
                'avg_engagement': metrics['avg_engagement'],
                'has_buzz': metrics['has_buzz'],
                'top_tweet_likes': metrics['top_tweet_likes']
            }

        except Exception as e:
            logger.error(f"❌ Error scoring Twitter buzz: {e}")
            return {'score': 0}
