"""
Conviction Engine - Scores tokens based on multiple signals
UPDATED: Integrated rug detection + LunarCrush social sentiment
"""
from typing import Dict, Optional
from datetime import datetime, timedelta
from loguru import logger
import config
from rug_detector import RugDetector
# Removed - no budget for these APIs
# from lunarcrush_fetcher import get_lunarcrush_fetcher
# from twitter_fetcher import get_twitter_fetcher
from credit_tracker import get_credit_tracker  # OPT-055: Track credit usage
from rugcheck_api import get_rugcheck_api  # RugCheck.xyz API integration
from ralph.integrate_ml import get_ml_predictor  # ML predictions for conviction scoring


class ConvictionEngine:
    """
    Analyzes tokens and calculates conviction scores (0-100)

    Scoring breakdown (ON-CHAIN-FIRST - KOL scoring disabled):
    - Buyer Velocity: 0-30 points (strongest predictor, raised from 25)
    - Unique Buyers: 0-20 points (increased from 0-15)
    - Buy/Sell Ratio: 0-20 points (percentage-based)
    - Volume Velocity: 0-15 points (increased from 0-10)
    - Bonding Curve Speed: 0-20 points (15 base + 5 bonus at 50%+ bonding)
    - Price Momentum: 0-10 points
    - Narrative Detection: 0-15 points (RSS+BERTopic matching)
    - Telegram Calls: 0-10 points (reduced from 0-15)
    - Bundle Penalty: -5 to -40 points (with overrides)
    - Holder Concentration: -15 to -40 points
    - ML Prediction: -30 to +20 points
    Total: 0-140+ points (can exceed with bonuses)

    NOTE: Smart wallet (KOL) scoring structure preserved but disabled.
          Set config.SMART_WALLET_WEIGHTS['max_score'] > 0 to re-enable.
    """
    
    def __init__(
        self,
        smart_wallet_tracker,
        narrative_detector=None,
        helius_fetcher=None,
        active_tracker=None,
        pump_monitor=None,
        database=None
    ):
        self.smart_wallet_tracker = smart_wallet_tracker
        self.narrative_detector = narrative_detector
        self.helius_fetcher = helius_fetcher
        self.active_tracker = active_tracker
        self.pump_monitor = pump_monitor
        self.database = database

        # Initialize rug detector
        self.rug_detector = RugDetector(smart_wallet_tracker=smart_wallet_tracker)

        # LunarCrush and Twitter removed (no budget)
        # self.lunarcrush = get_lunarcrush_fetcher()
        # self.twitter = get_twitter_fetcher()

        # OPT-055: Initialize credit tracker
        self.credit_tracker = get_credit_tracker()

        # Initialize RugCheck.xyz API
        self.rugcheck = get_rugcheck_api()

        # Initialize ML predictor
        self.ml_predictor = get_ml_predictor()
        
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

            # 🎬 SCENE 4: CONVICTION SCORING ENGINE
            print("\n" + "="*80)
            print("🎬 SCENE 4: CONVICTION SCORING - THE BRAIN OF PROMETHEUS")
            print("="*80)
            print(f"🧠 Analyzing: ${token_symbol} ({token_name})")
            print(f"📍 Address: {token_address[:8]}...{token_address[-6:]}")
            print(f"📊 Status: {'🌱 PRE-GRADUATION (pump.fun)' if is_pre_grad else '🎓 POST-GRADUATION (Raydium)'}")
            print(f"⚡ Bonding Curve: {bonding_pct:.1f}%")
            print()
            print("🎯 ON-CHAIN-FIRST SCORING SYSTEM (0-140+ scale):")
            print("   ├─ 🏃 Buyer Velocity (0-30 pts)")
            print("   ├─ 👥 Unique Buyers (0-20 pts)")
            print("   ├─ 💹 Buy/Sell Ratio (0-20 pts)")
            print("   ├─ 📊 Volume Velocity (0-15 pts)")
            print("   ├─ ⚡ Bonding Curve Speed (0-20 pts)")
            print("   ├─ 🚀 Price Momentum (0-10 pts)")
            print("   ├─ 🎯 Narrative Match (0-15 pts)")
            print("   ├─ 📱 Telegram Calls (0-10 pts)")
            print("   └─ 🚨 Rug Detection Penalties (-40 to 0)")
            print()
            print("⏳ Calculating real-time conviction score...")
            print("="*80 + "\n")

            logger.info(f"🔍 Analyzing ${token_symbol} ({token_address[:8]}...) - {'PRE-GRAD' if is_pre_grad else 'POST-GRAD'}")
            
            # ================================================================
            # PHASE 1: FREE BASE SCORE (0-60 points)
            # ================================================================

            base_scores = {}

            # Initialize ML prediction result (will be populated later)
            ml_result = {'ml_enabled': False, 'ml_bonus': 0, 'prediction_class': 0,
                        'class_name': 'unknown', 'confidence': 0.0}
            
            # 1. Smart Wallet Activity (DISABLED - structure preserved for re-enable)
            smart_wallet_data = await self.smart_wallet_tracker.get_smart_wallet_activity(
                token_address,
                hours=24
            )
            # Only score if KOL scoring is enabled (max_score > 0)
            if config.SMART_WALLET_WEIGHTS.get('max_score', 0) > 0:
                base_scores['smart_wallet'] = smart_wallet_data.get('score', 0)
                logger.info(f"   👑 Smart Wallets: {base_scores['smart_wallet']} points")
            else:
                base_scores['smart_wallet'] = 0
                kol_count = smart_wallet_data.get('wallet_count', 0)
                if kol_count > 0:
                    logger.info(f"   👑 Smart Wallets: DISABLED ({kol_count} KOL(s) detected but not scored)")
                else:
                    logger.debug(f"   👑 Smart Wallets: DISABLED (on-chain-first mode)")

            # 1b. Buyer Velocity (0-25 points) - NEW: Replaces KOL scoring
            buyer_velocity_score = self._score_buyer_velocity(token_address)
            base_scores['buyer_velocity'] = buyer_velocity_score
            if buyer_velocity_score > 0:
                logger.info(f"   🏃 Buyer Velocity: {buyer_velocity_score} points")
            else:
                logger.info(f"   🏃 Buyer Velocity: 0 points (insufficient buyer activity)")

            # 1c. Bonding Curve Speed (0-15 points) - NEW: On-chain demand indicator
            bonding_speed_score = self._score_bonding_speed(token_address, token_data)
            base_scores['bonding_speed'] = bonding_speed_score
            if bonding_speed_score > 0:
                logger.info(f"   ⚡ Bonding Speed: {bonding_speed_score} points")
            else:
                logger.debug(f"   ⚡ Bonding Speed: 0 points")

            # 2. Narrative Detection (0-10 points) - if enabled (reduced from 25)
            narrative_data = {}  # Track for Telegram display
            if self.narrative_detector and config.ENABLE_NARRATIVES:
                narrative_data = self.narrative_detector.analyze_token(
                    token_symbol,
                    token_name,
                    token_data.get('description', '')
                )
                base_scores['narrative'] = min(narrative_data.get('score', 0), 15)  # Cap at 15 (RSS+BERTopic clusters)
                if base_scores['narrative'] > 0:
                    # Show which system matched (RSS+BERTopic realtime vs static)
                    realtime_score = narrative_data.get('realtime_score', 0)
                    static_score = narrative_data.get('static_score', 0)

                    if realtime_score > 0:
                        # RSS + BERTopic match
                        reason = narrative_data.get('realtime_reason', 'N/A')
                        logger.info(f"   🎯 Narratives: {base_scores['narrative']} points [RSS+BERTopic] - {reason}")
                    elif static_score > 0:
                        # Static match
                        logger.info(f"   🎯 Narratives: {base_scores['narrative']} points [Static] (matched: {narrative_data.get('primary_narrative', 'N/A')})")
                    else:
                        logger.info(f"   🎯 Narratives: {base_scores['narrative']} points")
                else:
                    logger.info(f"   🎯 Narratives: 0 points (no match)")
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

            # 5. Buy/Sell Ratio (0-20 points) - Updated: Percentage-based scoring
            buy_sell_score = self._score_buy_sell_ratio(token_data)
            base_scores['buy_sell_ratio'] = buy_sell_score
            logger.info(f"   💹 Buy/Sell Ratio: {buy_sell_score}/20 points")

            # 6. Volume/Liquidity Velocity (0-8 points) - OPT-044: High velocity = early momentum
            velocity_score = self._score_volume_liquidity_velocity(token_data)
            base_scores['volume_liquidity_velocity'] = velocity_score
            logger.info(f"   ⚡ Volume/Liquidity Velocity: {velocity_score} points")

            # 7. MCAP Penalty (0 to -20 points) - OPT-044: Avoid late entries
            mcap_penalty = self._score_mcap_penalty(token_data)
            base_scores['mcap_penalty'] = mcap_penalty
            if mcap_penalty < 0:
                logger.warning(f"   📉 MCAP Penalty: {mcap_penalty} points (too late to enter)")

            # 8. Velocity Spike Bonus (0-10 points) - PRE-GRAD ONLY
            # Detects FOMO acceleration: >2x buyer count in 60s after 50% bonding
            velocity_spike_bonus = 0
            if is_pre_grad and self.pump_monitor:
                velocity_spike = self.pump_monitor.get_velocity_spike(token_address)
                if velocity_spike:
                    velocity_spike_bonus = velocity_spike['bonus_points']
                    logger.info(f"   🚀 VELOCITY SPIKE: +{velocity_spike_bonus} pts (FOMO at {velocity_spike['spike_at_pct']}% bonding)")
            base_scores['velocity_spike'] = velocity_spike_bonus

            # 9. Graduation Speed Bonus (-10 to +15 points) - POST-GRAD ONLY
            # Fast graduation = strong demand signal; slow + low growth = weak
            grad_speed_bonus = 0
            if not is_pre_grad:
                grad_speed_bonus = self._score_graduation_speed(token_address, token_data)
                if grad_speed_bonus > 0:
                    logger.info(f"   🎓 Graduation Speed: +{grad_speed_bonus} pts (fast grad = strong demand)")
                elif grad_speed_bonus < 0:
                    logger.warning(f"   🎓 Graduation Speed: {grad_speed_bonus} pts (slow grad + low growth)")
            base_scores['graduation_speed'] = grad_speed_bonus

            base_total = sum(base_scores.values())
            logger.info(f"   💰 BASE SCORE: {base_total}/148")
            
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

            # Social sentiment removed (no budget)
            social_score = 0
            twitter_score = 0
            social_data = {}
            twitter_data = {}

            # ================================================================
            # PHASE 3.5: TELEGRAM CALLS - FREE (moved before early exit)
            # ================================================================
            # FIX: Was Phase 3.7 AFTER early exit - $STARTUP missed because
            # TG groups called it but early exit at mid_total < 20 skipped the check
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

                        # Variable scoring based on intensity (reads from config)
                        tg_weights = config.TELEGRAM_CONFIRMATION_WEIGHTS
                        if mention_count >= 6 or group_count >= 3:
                            # High intensity: 6+ mentions OR 3+ groups
                            social_confirmation_score = tg_weights['high_intensity']
                            telegram_call_data['intensity'] = 'high'
                        elif mention_count >= 3 or (very_recent_count >= 2 and group_count >= 2):
                            # Medium intensity: 3-5 mentions OR growing buzz
                            social_confirmation_score = tg_weights['medium_intensity']
                            telegram_call_data['intensity'] = 'medium'
                        elif mention_count >= 1:
                            # Low intensity: 1-2 mentions
                            social_confirmation_score = tg_weights['low_intensity']
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

            # Cap total social score (Telegram only now) at configured max
            # This prevents over-scoring noisy hype
            max_social = config.TELEGRAM_CONFIRMATION_WEIGHTS.get('max_social_total', 15)
            total_social = social_confirmation_score  # Twitter removed
            if total_social > max_social:
                excess = total_social - max_social
                social_confirmation_score -= excess
                logger.info(f"   ⚖️  Social cap applied: reduced Telegram by {excess} pts (max 25 total)")
                telegram_call_data['capped'] = True

            mid_total += social_confirmation_score

            # ================================================================
            # PHASE 3.6: MULTI-CALL BONUS (persistent telegram data)
            # ================================================================
            # Award bonus points for repeated calls from multiple groups
            # This indicates coordinated/organic buzz across the community

            multi_call_bonus = 0

            if config.ENABLE_TELEGRAM_SCRAPER and self.database:
                try:
                    # Query persistent database for call stats (last 30 min)
                    call_stats = await self.database.get_telegram_call_stats(
                        token_address=token_address,
                        minutes=30
                    )

                    call_count = call_stats.get('call_count', 0)
                    group_count = call_stats.get('group_count', 0)

                    if call_count > 0:
                        logger.info(f"   📊 Multi-call analysis: {call_count} calls from {group_count} groups (30m)")

                        # BONUS 1: High call frequency (same CA mentioned 3+ times)
                        if call_count >= 3:
                            multi_call_bonus += 10
                            logger.info(f"      🔥 HIGH FREQUENCY BONUS: +10 pts ({call_count} calls)")

                        # BONUS 2: Multi-group confirmation (3+ different groups)
                        if group_count >= 3:
                            multi_call_bonus += 15
                            logger.info(f"      🔥 MULTI-GROUP BONUS: +15 pts ({group_count} groups)")

                        # If both bonuses apply, cap at +10 to avoid over-scoring (reduced from 20)
                        if multi_call_bonus > 10:
                            logger.info(f"      ⚖️  Multi-call bonus capped at +10 pts")
                            multi_call_bonus = 10

                        if multi_call_bonus > 0:
                            telegram_call_data['multi_call_bonus'] = multi_call_bonus

                except Exception as e:
                    logger.error(f"   ❌ Error calculating multi-call bonus: {e}")
                    multi_call_bonus = 0

            mid_total += multi_call_bonus

            # Early exit if mid score too low (now includes Telegram call boost)
            # FIX: Moved after Telegram calls so called tokens don't get early-exited
            if mid_total < 20:
                logger.info(f"   ⏭️  Mid Score: {mid_total}/100 - Too low for further analysis")
                return {
                    'score': mid_total,
                    'passed': False,
                    'reason': 'Score too low after Telegram calls',
                    'token_address': token_address,
                    'token_data': token_data,
                    'narrative_data': narrative_data,
                    'breakdown': {
                        **base_scores,
                        'bundle_penalty': bundle_result['penalty'],
                        'unique_buyers': unique_buyers_score,
                        'telegram_calls': social_confirmation_score,
                        'multi_call_bonus': multi_call_bonus,
                        'total': mid_total
                    }
                }

            # ================================================================
            # PHASE 3.8: SOCIAL VERIFICATION - FREE
            # ================================================================
            # Verify token has legitimate social presence (Twitter, Telegram, website)
            # This is different from buzz/sentiment - it's about legitimacy verification
            # Data comes from PumpPortal (pre-grad) or DexScreener (post-grad)
            #
            # SCORING ASYMMETRY (pre-grad socials matter less):
            # - Pre-grad: -10 (none) to +13 (full set) — most memecoins skip socials
            # - Post-grad: -15 (none) to +21 (full + active) — socials more meaningful once DEX listed

            social_verification_score = 0
            social_verification_data = {}

            # Check if social data is available (from PumpPortal or DexScreener)
            # If data not available yet for pre-grad, assume no socials (penalize unknown)
            if token_data.get('has_twitter') is None and is_pre_grad:
                social_verification_score = -10
                logger.warning(f"   ⚠️  PRE-GRAD: Social data not loaded yet - assuming no socials: -10 pts")
            elif token_data.get('has_twitter') is not None:
                has_website = token_data.get('has_website', False)
                has_twitter = token_data.get('has_twitter', False)
                has_telegram = token_data.get('has_telegram', False)
                has_discord = token_data.get('has_discord', False)
                social_count = token_data.get('social_count', 0)

                # Log which source provided social data (for debugging coverage)
                social_source = token_data.get('social_source', 'unknown')
                if social_source != 'unknown':
                    logger.debug(f"   📊 Social data source: {social_source}")

                # PRE-GRAD SCORING: -20 to +13 (more punitive for no socials)
                if is_pre_grad:
                    if social_count == 0:
                        # No socials pre-grad = common for memecoins, light penalty
                        # FIX: Was -20, too harsh - missed $STARTUP (+695%) runner
                        social_verification_score = -10
                        social_verification_data['anonymous'] = True
                        logger.warning(f"   ⚠️  PRE-GRAD: No socials: -10 pts (common for memecoins)")
                    elif has_telegram and not has_twitter:
                        # Only Telegram = easy to fake/spam
                        social_verification_score = 2
                        logger.info(f"   📱 PRE-GRAD: Only Telegram: +2 pts (weak signal)")
                    elif has_twitter and has_telegram:
                        # Twitter + Telegram = strong pre-grad signal
                        social_verification_score = 10
                        social_verification_data['multi_platform'] = True
                        if has_website:
                            # Twitter + TG + website = rare pre-grad, very strong
                            social_verification_score = 13
                            logger.info(f"   ✅ PRE-GRAD: Full social set: +13 pts (rare, strong)")
                        else:
                            logger.info(f"   ✅ PRE-GRAD: Twitter + Telegram: +10 pts")
                    elif has_twitter:
                        # Only Twitter = decent signal
                        social_verification_score = 6
                        logger.info(f"   🐦 PRE-GRAD: Twitter only: +6 pts")

                # POST-GRAD SCORING: -15 to +21 (socials more meaningful)
                else:
                    if social_count == 0:
                        # No socials post-grad = anonymous but less damning
                        social_verification_score = -15
                        social_verification_data['anonymous'] = True
                        logger.warning(f"   ⚠️  POST-GRAD: No socials: -15 pts (anonymous)")
                    else:
                        # Base scoring for social presence
                        if has_twitter and has_telegram:
                            # Both Twitter + Telegram = legit project
                            social_verification_score = 10
                            social_verification_data['multi_platform'] = True
                        elif has_twitter or has_telegram:
                            # At least one social = some legitimacy
                            social_verification_score = 5

                        # Additional bonuses for post-grad
                        if has_website:
                            social_verification_score += 6  # Website matters more post-grad
                        if has_discord:
                            social_verification_score += 5  # Discord community = strong signal

                        # Cap at +21 for post-grad
                        social_verification_score = min(social_verification_score, 21)

                        if social_verification_score > 0:
                            logger.info(f"   ✅ POST-GRAD: Social verification: +{social_verification_score} pts")
                            platforms = []
                            if has_twitter: platforms.append('Twitter')
                            if has_telegram: platforms.append('Telegram')
                            if has_website: platforms.append('Website')
                            if has_discord: platforms.append('Discord')
                            logger.info(f"      Platforms: {', '.join(platforms)}")

                social_verification_data.update({
                    'has_website': has_website,
                    'has_twitter': has_twitter,
                    'has_telegram': has_telegram,
                    'has_discord': has_discord,
                    'social_count': social_count,
                    'score': social_verification_score,
                    'stage': 'pre_grad' if is_pre_grad else 'post_grad'
                })
            else:
                logger.debug(f"   ℹ️  Social verification skipped (social data not available)")

            mid_total += social_verification_score

            # ================================================================
            # PHASE 3.9: BOOST DETECTION (POST-GRAD ONLY) - FREE
            # ================================================================
            # Detect coordinated pump/dump via DexScreener boost or volume spikes
            # If boosted OR sudden 5-10x volume spike in first 5min → -25 pts

            boost_penalty = 0
            boost_detection_data = {}

            if not is_pre_grad:  # Only check post-grad tokens
                is_boosted = token_data.get('is_boosted', False) or token_data.get('boost_active', 0) > 0
                volume_spike_ratio = token_data.get('volume_spike_ratio', 0)

                if is_boosted:
                    boost_penalty = -25
                    boost_detection_data['boosted'] = True
                    logger.warning(f"   🚨 BOOST DETECTED: DexScreener paid promotion - {boost_penalty} pts (coordinated dump risk)")
                elif volume_spike_ratio >= 5:
                    boost_penalty = -25
                    boost_detection_data['volume_spike'] = True
                    boost_detection_data['spike_ratio'] = round(volume_spike_ratio, 1)
                    logger.warning(f"   🚨 VOLUME SPIKE: {volume_spike_ratio:.1f}x sudden volume - {boost_penalty} pts (coordinated dump risk)")

            mid_total += boost_penalty

            # ================================================================
            # PHASE 3.10: RESERVE RATIO ANALYSIS (POST-GRAD ONLY) - FREE
            # ================================================================
            # Analyze SOL/token ratio in liquidity pool
            # High reserve ratio = balanced liquidity, low = easy dump risk
            # Scoring: >0.8 = +10 pts, <0.4 = -15 pts

            reserve_ratio_score = 0
            reserve_ratio_data = {}

            if not is_pre_grad:  # Only check post-grad tokens with DEX liquidity
                liquidity_base = token_data.get('liquidity_base', 0)  # Token reserves
                liquidity_quote = token_data.get('liquidity_quote', 0)  # SOL reserves

                if liquidity_base > 0 and liquidity_quote > 0:
                    # Calculate reserve ratio (normalized to 0-1 range)
                    # Higher ratio = more SOL relative to tokens = healthier
                    total_liquidity = liquidity_base + liquidity_quote
                    reserve_ratio = liquidity_quote / total_liquidity

                    reserve_ratio_data['reserve_ratio'] = round(reserve_ratio, 3)
                    reserve_ratio_data['sol_reserves'] = liquidity_quote
                    reserve_ratio_data['token_reserves'] = liquidity_base

                    if reserve_ratio > 0.8:
                        # High SOL reserves = balanced, healthy liquidity
                        reserve_ratio_score = 10
                        logger.info(f"   ✅ Reserve Ratio: {reserve_ratio:.2f} - Balanced liquidity: +{reserve_ratio_score} pts")
                    elif reserve_ratio < 0.4:
                        # Low SOL reserves = easy to dump, high slippage risk
                        reserve_ratio_score = -15
                        logger.warning(f"   ⚠️  Reserve Ratio: {reserve_ratio:.2f} - Low liquidity risk: {reserve_ratio_score} pts")
                    else:
                        # Medium ratio = neutral
                        logger.debug(f"   ℹ️  Reserve Ratio: {reserve_ratio:.2f} - Neutral")

            mid_total += reserve_ratio_score

            # ================================================================
            # OPT-023/OPT-055: EMERGENCY STOP - Red Flag Detection (FREE)
            # ================================================================
            # OPT-055: Check emergency flags BEFORE expensive holder check
            # Block signals with obvious rug indicators (paranoid filtering)
            # Better to miss a winner than post a rug AND save 10 credits

            emergency_blocks = []
            rugcheck_penalty = 0
            rugcheck_result = None

            # 0. RugCheck.xyz API (FREE) - Check for rug risk
            if config.RUG_DETECTION.get('enabled', True):
                logger.info(f"   🔍 Checking RugCheck.xyz API...")
                rugcheck_result = await self.rugcheck.check_token(token_address, timeout=8)

                if rugcheck_result['success']:
                    risk_level = rugcheck_result['risk_level']
                    score_norm = rugcheck_result.get('score_normalised', rugcheck_result.get('score'))
                    rugged = rugcheck_result.get('rugged', False)
                    is_honeypot = rugcheck_result.get('is_honeypot', False)

                    # ONLY BLOCK confirmed rugs/honeypots (not just high risk scores)
                    # Most pump.fun tokens are high risk by nature - that's OK
                    if rugged or is_honeypot:
                        # HARD BLOCK: Confirmed rug or honeypot
                        emergency_blocks.append(f"RugCheck: Confirmed {'RUG' if rugged else 'HONEYPOT'}")
                        logger.error(f"   🚨 RugCheck: {'RUGGED' if rugged else 'HONEYPOT'} - BLOCKING")

                    # Apply penalties for risk levels (but don't block)
                    elif risk_level == 'critical':
                        # Very high risk: -40 points (score 9-10)
                        rugcheck_penalty = -40
                        logger.warning(f"   🚨 RugCheck: VERY HIGH risk (score: {score_norm}/10) - {rugcheck_penalty} pts")

                    elif risk_level == 'high':
                        # High risk: -25 points (score 7-8)
                        rugcheck_penalty = -25
                        logger.warning(f"   ⛔ RugCheck: HIGH risk (score: {score_norm}/10) - {rugcheck_penalty} pts")

                    elif risk_level == 'medium':
                        # Moderate risk: -15 points (score 5-6)
                        rugcheck_penalty = -15
                        logger.info(f"   ⚠️  RugCheck: MEDIUM risk (score: {score_norm}/10) - {rugcheck_penalty} pts")

                    elif risk_level == 'low':
                        # Low risk: -5 points (score 3-4)
                        rugcheck_penalty = -5
                        logger.info(f"   ⚠️  RugCheck: LOW risk (score: {score_norm}/10) - {rugcheck_penalty} pts")

                    else:  # 'good'
                        # Very safe: no penalty (score 0-2)
                        logger.info(f"   ✅ RugCheck: SAFE (score: {score_norm}/10)")

                    # Log specific risk flags
                    if rugcheck_result.get('mutable_metadata'):
                        logger.info(f"      ℹ️  Mutable metadata (common for new tokens)")
                    if rugcheck_result.get('critical_risks'):
                        for risk in rugcheck_result['critical_risks'][:2]:  # Show top 2
                            logger.warning(f"      🔴 {risk.get('name', 'Unknown risk')}")

                else:
                    # RugCheck failed - light penalty for pre-grad (API may just be slow)
                    # FIX: Was -15, too harsh - missed $STARTUP (+695%) runner
                    if is_pre_grad:
                        rugcheck_penalty = -5
                        logger.warning(f"   ⚠️  RugCheck API unavailable - light penalty for pre-grad: {rugcheck_penalty} pts")
                    else:
                        logger.debug(f"   ⚠️  RugCheck API unavailable: {rugcheck_result.get('error', 'Unknown error')}")

            # Apply RugCheck penalty to mid_total
            mid_total += rugcheck_penalty

            # NOTE: DexScreener boost detection already handled in Phase 3.9
            # (was duplicated here with boost_active, causing -50 double penalty)

            # LIQUIDITY FILTERS DISABLED - User requested removal
            # Tokens below $20k max market cap will have very little liquidity by nature
            # Blocking on zero liquidity was preventing valid signals

            # 1. Liquidity check - DISABLED
            # liquidity = token_data.get('liquidity', 0)
            # if liquidity > 0 and liquidity < config.MIN_LIQUIDITY:
            #     emergency_blocks.append(f"Liquidity too low: ${liquidity:.0f} < ${config.MIN_LIQUIDITY}")

            # 2. Token age < 30 seconds (too fresh, wait for real activity)
            # REDUCED from 2min to 30sec: KOLs buy within 0-60sec, we were too late!
            # Still filters out instant rugs but allows early entry
            token_created_at = None
            created_ts = token_data.get('created_timestamp') or token_data.get('pair_created_at', 0)
            if created_ts and created_ts > 0:
                try:
                    # Handle both seconds and milliseconds timestamps
                    if created_ts > 1e12:
                        created_ts = created_ts / 1000  # ms to seconds
                    token_created_at = datetime.utcfromtimestamp(created_ts)
                except (ValueError, OSError):
                    token_created_at = None

            if token_created_at:
                token_age_seconds = (datetime.utcnow() - token_created_at).total_seconds()
                if token_age_seconds < 30:  # 30 seconds (was 2 minutes)
                    emergency_blocks.append(f"Token too new: {token_age_seconds:.0f}s old (< 30sec)")

            # 3. Zero liquidity check - DISABLED
            # if liquidity == 0 and bonding_pct < 100:
            #     emergency_blocks.append(f"Zero liquidity on pre-grad token")

            # ================================================================
            # PHASE 3.11: MINT/FREEZE AUTHORITY CHECK (1 credit) - Helius
            # ================================================================
            authority_penalty = 0
            authority_result = {}

            if self.helius_fetcher and config.HELIUS_AUTHORITY_CHECK.get('enabled', False):
                authority_result = await self.rug_detector.check_token_authority(
                    token_address,
                    self.helius_fetcher,
                    mid_score=mid_total
                )
                authority_penalty = authority_result.get('penalty', 0)
                mid_total += authority_penalty

                # Hard block if freeze authority is active (can steal your tokens)
                if 'FREEZE_ACTIVE' in authority_result.get('risk_flags', []):
                    emergency_blocks.append("Freeze authority active (can freeze your tokens)")

            # ================================================================
            # PHASE 3.12: DEV SELL DETECTION (5 credits) - Helius
            # ================================================================
            dev_sell_penalty = 0
            dev_sell_result = {}

            if self.helius_fetcher and config.HELIUS_DEV_SELL_DETECTION.get('enabled', False):
                # Get creator wallet from token data or PumpPortal
                creator_wallet = token_data.get('creator_wallet', '')
                if not creator_wallet and self.pump_monitor:
                    # Try to get from PumpPortal trade data (first buyer is often creator)
                    milestones = self.pump_monitor.bonding_milestones.get(token_address, {})
                    if milestones:
                        earliest = min(milestones.keys())
                        # Creator wallet often available from PumpPortal data
                        creator_wallet = token_data.get('deployer', '')

                token_age_minutes = 0
                if token_created_at:
                    token_age_minutes = (datetime.utcnow() - token_created_at).total_seconds() / 60

                if creator_wallet:
                    dev_sell_result = await self.rug_detector.check_dev_sells(
                        token_address,
                        creator_wallet,
                        self.helius_fetcher,
                        mid_score=mid_total,
                        token_age_minutes=token_age_minutes
                    )
                    dev_sell_penalty = dev_sell_result.get('penalty', 0)
                    mid_total += dev_sell_penalty

                    if dev_sell_result.get('hard_block'):
                        emergency_blocks.append(f"Dev dumped {dev_sell_result.get('sell_pct', 0):.0f}% of supply")

            # OPT-055: Count emergency flags for smart gating decision
            emergency_flag_count = len(emergency_blocks)

            # ================================================================
            # PHASE 4: HOLDER CONCENTRATION CHECK (10 CREDITS) ⭐
            # OPT-055: Smart gating to save 60%+ credits
            # ================================================================

            holder_result = {'penalty': 0, 'kol_bonus': 0, 'hard_drop': False}
            credits_saved = 0  # OPT-055: Track credit savings

            if config.RUG_DETECTION['enabled'] and config.RUG_DETECTION['holder_concentration']['check']:
                # OPT-055: Smart gating decision with multiple factors
                # Calculate total KOL count from smart wallet data
                kol_count = smart_wallet_data.get('wallet_count', 0)

                check_decision = self.rug_detector.should_check_holders(
                    base_score=mid_total,
                    bonding_pct=bonding_pct,
                    unique_buyers=unique_buyers,
                    kol_count=kol_count,
                    emergency_flags=emergency_flag_count
                )

                should_check = check_decision['should_check']
                credits_saved = check_decision['credits_saved']

                # OPT-055: Log decision reason
                logger.info(f"   💡 Holder check decision: {check_decision['reason']}")

                if should_check and self.helius_fetcher:
                    # OPT-055: Log credit spend
                    self.credit_tracker.log_holder_check(
                        executed=True,
                        credits=10,
                        reason=check_decision['reason'],
                        token_address=token_address
                    )

                    holder_result = await self.rug_detector.check_holder_concentration(
                        token_address,
                        self.helius_fetcher,
                        kol_wallets=set(self.smart_wallet_tracker.tracked_wallets.keys())
                    )

                    # Check for hard drop from holder concentration
                    if holder_result['hard_drop']:
                        logger.error(f"   💀 HARD DROP: {holder_result['reason']}")
                        emergency_blocks.append(f"Top holders >80% concentration")
                        emergency_flag_count += 1

                    if holder_result['penalty'] != 0:
                        logger.warning(f"   ⚠️  Holder Concentration: {holder_result['penalty']} pts")

                    if holder_result['kol_bonus'] > 0:
                        logger.info(f"   💎 KOL Bonus: +{holder_result['kol_bonus']} pts")
                        logger.info(f"      {holder_result['reason']}")
                else:
                    # OPT-055: Log credit savings
                    if credits_saved > 0:
                        self.credit_tracker.log_holder_check(
                            executed=False,
                            credits=10,
                            reason=check_decision['reason'],
                            token_address=token_address
                        )
                        logger.info(f"   💰 OPT-055: Saved {credits_saved} Helius credits by skipping holder check")

            # If any emergency blocks triggered, force score to 0
            if emergency_blocks:
                logger.warning("=" * 60)
                logger.warning(f"   🚨 EMERGENCY STOP TRIGGERED 🚨")
                for reason in emergency_blocks:
                    logger.warning(f"   ❌ {reason}")
                logger.warning(f"   💡 Blocking signal to prevent obvious rug")
                logger.warning("=" * 60)

                return {
                    'score': 0,
                    'passed': False,
                    'threshold': config.MIN_CONVICTION_SCORE,
                    'emergency_stop': True,
                    'emergency_reasons': emergency_blocks,
                    'token_address': token_address,
                    'token_data': token_data,
                    'narrative_data': narrative_data,
                    'breakdown': {},
                    'rug_checks': {
                        'rugcheck_api': rugcheck_result,
                        'bundle': bundle_result,
                        'holder_concentration': holder_result,
                        'emergency_stop': emergency_blocks
                    }
                }

            # ================================================================
            # FINAL SCORE CALCULATION (if no emergency stop)
            # ================================================================

            final_score = mid_total + holder_result['penalty'] + holder_result['kol_bonus']

            # ML Prediction - Add conviction bonus based on predicted outcome
            kol_count = smart_wallet_data.get('wallet_count', 0)
            ml_result = self.ml_predictor.predict_for_signal(token_data, kol_count=kol_count)

            if ml_result['ml_enabled']:
                logger.info(f"   🤖 ML Prediction: {ml_result['class_name']} "
                           f"({ml_result['confidence']*100:.0f}% confident)")
                logger.info(f"      Conviction bonus: {ml_result['ml_bonus']:+d} points")
                final_score += ml_result['ml_bonus']

            # Determine threshold
            threshold = config.MIN_CONVICTION_SCORE if is_pre_grad else config.POST_GRAD_THRESHOLD

            # GROK: Early trigger at 30% bonding if 200+ unique buyers
            early_trigger_applied = False
            if (is_pre_grad and
                config.TIMING_RULES['early_trigger']['enabled'] and
                bonding_pct >= config.TIMING_RULES['early_trigger']['bonding_threshold'] and
                unique_buyers >= config.TIMING_RULES['early_trigger']['min_unique_buyers']):
                # Allow signal even if slightly below threshold (good fundamentals)
                early_trigger_threshold = threshold - 5  # 5 point grace period
                if final_score >= early_trigger_threshold:
                    early_trigger_applied = True
                    logger.info(f"   ⚡ EARLY TRIGGER: {bonding_pct:.0f}% bonding, {unique_buyers} buyers (threshold relaxed to {early_trigger_threshold})")

            # Check if passed threshold (with early trigger consideration)
            passed = final_score >= threshold or early_trigger_applied

            # GROK: MCAP cap - skip if too high (avoid tops)
            mcap = token_data.get('market_cap', 0)
            mcap_cap_triggered = False
            if passed and config.TIMING_RULES['mcap_cap']['enabled']:
                max_mcap = (config.TIMING_RULES['mcap_cap']['max_mcap_pre_grad'] if is_pre_grad
                           else config.TIMING_RULES['mcap_cap']['max_mcap_post_grad'])
                if mcap > max_mcap:
                    passed = False
                    mcap_cap_triggered = True
                    if config.TIMING_RULES['mcap_cap']['log_skipped']:
                        logger.warning(f"   🚫 MCAP CAP: ${mcap:.0f} > ${max_mcap} (too late, skipping signal)")

            # MATURITY GATE: Skip if token too young or MCAP too low (avoid sniped rugs)
            maturity_gate_triggered = False
            maturity_gate_reason = ''
            maturity_cfg = config.TIMING_RULES.get('signal_maturity_gate', {})
            if passed and maturity_cfg.get('enabled', False):
                min_mcap = (maturity_cfg.get('min_mcap_pre_grad', 0) if is_pre_grad
                           else maturity_cfg.get('min_mcap_post_grad', 0))
                min_age_min = (maturity_cfg.get('min_age_minutes_pre_grad', 0) if is_pre_grad
                              else maturity_cfg.get('min_age_minutes_post_grad', 0))

                # Check minimum MCAP
                if min_mcap > 0 and mcap < min_mcap:
                    passed = False
                    maturity_gate_triggered = True
                    maturity_gate_reason = f"MCAP ${mcap:.0f} < ${min_mcap} minimum"

                # Check minimum age
                if min_age_min > 0 and token_created_at:
                    age_minutes = (datetime.utcnow() - token_created_at).total_seconds() / 60
                    if age_minutes < min_age_min:
                        passed = False
                        maturity_gate_triggered = True
                        maturity_gate_reason += ('; ' if maturity_gate_reason else '') + \
                            f"Age {age_minutes:.0f}m < {min_age_min}m minimum"

                if maturity_gate_triggered and maturity_cfg.get('log_skipped', True):
                    logger.warning(f"   🚫 MATURITY GATE: {maturity_gate_reason} (too early, needs distribution time)")

            logger.info("=" * 60)
            logger.info(f"   🎯 FINAL CONVICTION: {final_score}/100")
            logger.info(f"   📊 Threshold: {threshold} ({'PRE-GRAD' if is_pre_grad else 'POST-GRAD'})")
            if early_trigger_applied:
                logger.info(f"   ⚡ Early trigger activated!")
            if mcap_cap_triggered:
                logger.info(f"   🚫 MCAP cap triggered - signal blocked")
            if maturity_gate_triggered:
                logger.info(f"   🚫 Maturity gate triggered - {maturity_gate_reason}")
            logger.info(f"   {'✅ SIGNAL!' if passed else '⏭️  Skip'}")
            logger.info("=" * 60)

            # GROK: Log "Why no signal" breakdown if close to threshold
            if not passed and config.SIGNAL_LOGGING.get('log_why_no_signal', True):
                gap_to_threshold = threshold - final_score
                min_gap = config.SIGNAL_LOGGING.get('min_gap_to_log', 5)

                # Log if within X points of threshold or if gate triggered
                if gap_to_threshold <= min_gap or mcap_cap_triggered or maturity_gate_triggered:
                    logger.warning("\n" + "!" * 60)
                    logger.warning("   ⚠️  WHY NO SIGNAL - Breakdown:")
                    logger.warning(f"   📉 Gap to threshold: {gap_to_threshold:.1f} points")

                    if mcap_cap_triggered:
                        logger.warning(f"   🚫 MCAP too high: ${mcap:.0f} > ${max_mcap}")
                    if maturity_gate_triggered:
                        logger.warning(f"   🚫 Maturity gate: {maturity_gate_reason}")

                    # Show weakest scoring components (on-chain-first)
                    breakdown_items = [
                        ('Buyer Velocity', base_scores.get('buyer_velocity', 0), 30),
                        ('Unique Buyers', unique_buyers_score, 20),
                        ('Buy/Sell Ratio', base_scores.get('buy_sell_ratio', 0), 20),
                        ('Volume', base_scores['volume'], 15),
                        ('Bonding Speed', base_scores.get('bonding_speed', 0), 15),
                        ('Momentum', base_scores['momentum'], 10),
                        ('Narrative', base_scores['narrative'], 10),
                        ('Telegram Calls', social_confirmation_score, 10),
                    ]

                    # Sort by potential gains (max points - actual points)
                    potential_gains = [(name, max_pts - actual, actual, max_pts)
                                      for name, actual, max_pts in breakdown_items]
                    potential_gains.sort(key=lambda x: x[1], reverse=True)

                    logger.warning("   📊 Top opportunities for improvement:")
                    for i, (name, gain, actual, max_pts) in enumerate(potential_gains[:3]):
                        if gain > 0:
                            logger.warning(f"      {i+1}. {name}: {actual}/{max_pts} pts (potential +{gain})")

                    # Show penalties applied
                    penalties = []
                    if rugcheck_penalty < 0:
                        penalties.append(f"RugCheck: {rugcheck_penalty}")
                    if authority_penalty < 0:
                        penalties.append(f"Authority: {authority_penalty}")
                    if dev_sell_penalty < 0:
                        penalties.append(f"DevSell: {dev_sell_penalty}")
                    if bundle_result['penalty'] < 0:
                        penalties.append(f"Bundle: {bundle_result['penalty']}")
                    if holder_result['penalty'] < 0:
                        penalties.append(f"Holder: {holder_result['penalty']}")
                    if base_scores.get('mcap_penalty', 0) < 0:
                        penalties.append(f"MCAP: {base_scores.get('mcap_penalty', 0)}")

                    if penalties:
                        logger.warning(f"   ⚠️  Penalties applied: {', '.join(penalties)}")

                    # Recommendations
                    if config.SIGNAL_LOGGING.get('include_recommendations', True):
                        recommendations = []
                        if base_scores.get('buyer_velocity', 0) < 10:
                            recommendations.append("Need faster buyer velocity (low accumulation)")
                        if base_scores['narrative'] == 0 and config.ENABLE_NARRATIVES:
                            recommendations.append("No hot narrative match")
                        if unique_buyers_score < 10:
                            recommendations.append(f"Need more buyers ({unique_buyers} currently)")
                        if base_scores.get('bonding_speed', 0) == 0 and is_pre_grad:
                            recommendations.append("Bonding curve filling too slowly")
                        if rugcheck_penalty < -15:
                            recommendations.append("High rug risk - avoid")
                        if mcap_cap_triggered:
                            recommendations.append("Entered too late (MCAP too high)")
                        if maturity_gate_triggered:
                            recommendations.append(f"Too early: {maturity_gate_reason}")

                        if recommendations:
                            logger.warning("   💡 Recommendations:")
                            for rec in recommendations[:3]:
                                logger.warning(f"      • {rec}")

                    logger.warning("!" * 60 + "\n")

            # Debug: Log token metadata being returned
            logger.info(f"   🏷️  Token metadata: {token_data.get('token_symbol')} / {token_data.get('token_name')}")

            return {
                'score': final_score,
                'passed': passed,
                'threshold': threshold,
                'is_pre_grad': is_pre_grad,
                'early_trigger_applied': early_trigger_applied,  # GROK: Early trigger flag
                'mcap_cap_triggered': mcap_cap_triggered,        # GROK: MCAP cap flag
                'maturity_gate_triggered': maturity_gate_triggered,  # Maturity gate flag
                'maturity_gate_reason': maturity_gate_reason,
                'token_address': token_address,  # FIXED: Include token address for links
                'token_data': token_data,  # FIXED: Include full token data
                'breakdown': {
                    'buyer_velocity': base_scores.get('buyer_velocity', 0),
                    'bonding_speed': base_scores.get('bonding_speed', 0),
                    'graduation_speed': base_scores.get('graduation_speed', 0),
                    'smart_wallet': base_scores['smart_wallet'],
                    'narrative': base_scores['narrative'],
                    'volume': base_scores['volume'],
                    'momentum': base_scores['momentum'],
                    'buy_sell_ratio': base_scores.get('buy_sell_ratio', 0),
                    'volume_liquidity_velocity': base_scores.get('volume_liquidity_velocity', 0),
                    'mcap_penalty': base_scores.get('mcap_penalty', 0),
                    'bundle_penalty': bundle_result['penalty'],
                    'unique_buyers': unique_buyers_score,
                    'social_sentiment': social_score,
                    'twitter_buzz': twitter_score,
                    'telegram_calls': social_confirmation_score,
                    'social_verification': social_verification_score,
                    'rugcheck_penalty': rugcheck_penalty,
                    'authority_penalty': authority_penalty,
                    'dev_sell_penalty': dev_sell_penalty,
                    'holder_penalty': holder_result['penalty'],
                    'kol_bonus': holder_result['kol_bonus'],
                    'ml_bonus': ml_result.get('ml_bonus', 0),
                    'total': final_score
                },
                'rug_checks': {
                    'rugcheck_api': rugcheck_result,
                    'bundle': bundle_result,
                    'holder_concentration': holder_result,
                    'authority': authority_result,
                    'dev_sells': dev_sell_result,
                },
                'social_data': social_data,
                'twitter_data': twitter_data,
                'telegram_call_data': telegram_call_data,
                'social_verification_data': social_verification_data,
                'smart_wallet_data': smart_wallet_data,  # FIXED: Include wallet data for display
                'ml_prediction': ml_result,  # ML prediction with class, confidence, and bonus
                'narrative_data': narrative_data  # Narrative match data for Telegram display
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
        """
        Score based on volume velocity (0-15 points) - PHASE-AWARE

        Pre-Graduation: Uses PumpPortal WebSocket rolling SOL volume (FREE)
          - DexScreener has NO data for pre-grad tokens (volume_24h = 0, mcap = 0)
          - Instead, we track real-time SOL flow from trade events
          - Score based on: velocity ratio (current 5m / previous 5m) + absolute SOL volume

        Post-Graduation: Uses DexScreener volume/mcap ratio (existing logic)
          - volume_24h and market_cap available from DEX pools
        """
        bonding_pct = token_data.get('bonding_curve_pct', 0)
        is_pre_grad = bonding_pct < 100

        if is_pre_grad:
            return self._score_pre_grad_volume(token_data)
        else:
            return self._score_post_grad_volume(token_data)

    def _score_pre_grad_volume(self, token_data: Dict) -> int:
        """
        Pre-grad volume scoring using PumpPortal rolling SOL volume data.
        DexScreener has no data for pre-graduation tokens, so we use
        real-time SOL amounts from WebSocket trade events.

        Scoring (dual criteria - either can trigger):
        - Velocity ratio (acceleration): current 5m / previous 5m SOL volume
        - Absolute volume (raw demand): total SOL in current 5m window
        """
        if not self.pump_monitor:
            return 0

        token_address = token_data.get('token_address', '')
        if not token_address:
            return 0

        weights = config.PRE_GRAD_VOLUME_WEIGHTS
        window_seconds = weights.get('window_seconds', 300)

        vol_data = self.pump_monitor.get_rolling_sol_volume(token_address, window_seconds)
        current = vol_data['current_window']
        previous = vol_data['previous_window']
        ratio = vol_data['velocity_ratio']

        # Score based on velocity ratio (acceleration) OR absolute volume (raw demand)
        if ratio > 3.0 or current > 50:
            score = weights['spiking']   # 15 pts
        elif ratio > 1.5 or current > 20:
            score = weights['growing']   # 10 pts
        elif ratio > 1.0 or current > 5:
            score = weights['steady']    # 5 pts
        else:
            score = 0

        if score > 0:
            logger.info(f"      📊 Pre-grad SOL volume: {current:.1f} SOL (5m) | prev: {previous:.1f} SOL | ratio: {ratio:.1f}x → +{score} pts")
        else:
            logger.debug(f"      📊 Pre-grad SOL volume: {current:.1f} SOL (5m) | ratio: {ratio:.1f}x → 0 pts")

        return score

    def _score_post_grad_volume(self, token_data: Dict) -> int:
        """
        Post-grad volume scoring using DexScreener multi-timeframe data.

        Uses best of:
        1. h1 volume velocity (volume_1h / liquidity) - real-time momentum
        2. h1 volume × price_change_1h composite - momentum quality
        3. volume_24h / mcap ratio - original fallback

        This eliminates 0-scoring for recently graduated tokens where
        volume_24h hasn't accumulated but h1 activity is strong.
        """
        volume_24h = token_data.get('volume_24h', 0)
        volume_1h = token_data.get('volume_1h', 0)
        volume_6h = token_data.get('volume_6h', 0)
        mcap = token_data.get('market_cap', 1)
        liquidity = token_data.get('liquidity', 0)
        price_change_1h = token_data.get('price_change_1h', 0)

        scores = []

        # Method 1: h1 volume velocity (volume_1h / liquidity)
        # Best for recently graduated tokens with active trading
        if volume_1h > 0 and liquidity > 0:
            h1_velocity = volume_1h / liquidity
            if h1_velocity > 5.0:        # 5x liquidity traded in 1h
                scores.append(config.VOLUME_WEIGHTS['spiking'])   # 15
            elif h1_velocity > 2.0:      # 2x liquidity
                scores.append(config.VOLUME_WEIGHTS['growing'])   # 10
            elif h1_velocity > 0.5:      # Half liquidity
                scores.append(config.VOLUME_WEIGHTS.get('steady', 5))  # 5

            if scores:
                logger.debug(f"      Post-grad h1 velocity: {h1_velocity:.1f}x (vol_1h=${volume_1h:.0f} / liq=${liquidity:.0f})")

        # Method 2: h1 composite (volume + positive price = quality momentum)
        if volume_1h > 0 and price_change_1h > 0 and liquidity > 0:
            composite = (price_change_1h * volume_1h) / liquidity
            if composite > 100:
                scores.append(config.VOLUME_WEIGHTS['spiking'])   # 15
            elif composite > 30:
                scores.append(config.VOLUME_WEIGHTS['growing'])   # 10
            elif composite > 5:
                scores.append(config.VOLUME_WEIGHTS.get('steady', 5))  # 5

        # Method 3: Original volume_24h/mcap ratio (always available post-grad)
        if mcap > 0 and volume_24h > 0:
            volume_to_mcap = volume_24h / mcap
            if volume_to_mcap > 2.0:
                scores.append(config.VOLUME_WEIGHTS['spiking'])   # 15
            elif volume_to_mcap > 1.25:
                scores.append(config.VOLUME_WEIGHTS['growing'])   # 10
            elif volume_to_mcap > 1.0:
                scores.append(config.VOLUME_WEIGHTS.get('steady', 5))  # 5

        # Take the best score across all methods
        return max(scores) if scores else 0
    
    def _score_price_momentum(self, token_data: Dict) -> int:
        """
        Score based on price momentum (0-10 points base + multi-timeframe bonus)
        GROK ENHANCED: More graduated scoring (3/7/10 instead of 0/5/10)

        - Pre-grad: Uses 5m price change (0-10 pts)
        - Post-grad: Uses 5m price change + multi-timeframe bonus (1h/6h/24h, +5 pts each)
        """
        bonding_pct = token_data.get('bonding_curve_pct', 0)
        is_pre_grad = bonding_pct < 100

        # Base score from 5m price change (more graduated)
        price_change_5m = token_data.get('price_change_5m', 0)

        if price_change_5m >= 50:  # +50% in 5 min
            base_score = config.MOMENTUM_WEIGHTS['very_strong']  # 10 pts
        elif price_change_5m >= 30:  # +30% in 5 min
            base_score = config.MOMENTUM_WEIGHTS['strong']  # 7 pts
        elif price_change_5m >= 10:  # +10% in 5 min (moderate)
            base_score = config.MOMENTUM_WEIGHTS.get('moderate', 3)  # 3 pts
        else:
            base_score = 0

        # POST-GRAD ONLY: Multi-timeframe momentum bonus
        if not is_pre_grad:
            price_change_1h = token_data.get('price_change_1h', 0)
            price_change_6h = token_data.get('price_change_6h', 0)
            price_change_24h = token_data.get('price_change_24h', 0)

            timeframe_bonus = 0
            positive_timeframes = []

            # +5 pts per positive timeframe (sustained momentum)
            if price_change_1h > 0:
                timeframe_bonus += 5
                positive_timeframes.append(f"1h: +{price_change_1h:.1f}%")
            if price_change_6h > 0:
                timeframe_bonus += 5
                positive_timeframes.append(f"6h: +{price_change_6h:.1f}%")
            if price_change_24h > 0:
                timeframe_bonus += 5
                positive_timeframes.append(f"24h: +{price_change_24h:.1f}%")

            if timeframe_bonus > 0:
                logger.info(f"   📈 Multi-timeframe momentum: +{timeframe_bonus} pts ({', '.join(positive_timeframes)})")

            return base_score + timeframe_bonus

        return base_score
    
    def _score_unique_buyers(self, unique_buyers: int) -> int:
        """Score based on unique buyer count (0-20 points) - ON-CHAIN: Increased from 15"""
        weights = config.UNIQUE_BUYER_WEIGHTS

        if unique_buyers >= 100:
            return weights['exceptional']  # 20 pts
        elif unique_buyers >= 50:
            return weights['high']         # 15 pts
        elif unique_buyers >= 25:
            return weights['medium']       # 10 pts
        elif unique_buyers >= 10:
            return weights['low']          # 5 pts
        else:
            return weights['minimal']      # 0 pts

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

    def _score_buy_sell_ratio(self, token_data: Dict) -> int:
        """
        Score based on buy/sell ratio percentage (0-20 points)
        Updated 2026-01-25: Percentage-based scoring for better ML training data

        Formula: buy_percentage = (buys / (buys + sells)) * 100

        Thresholds (based on 2025-2026 Solana memecoin data):
        - >80% buys (Very Bullish): 16-20 points - Strong accumulation signal
        - 70-80% buys (Bullish): 12-16 points - Positive momentum building
        - 50-70% buys (Neutral): 8-12 points - Balanced, watch for shift
        - 30-50% buys (Bearish): 4-8 points - Caution, potential distribution
        - <30% buys (Very Bearish): 0-4 points - Red flag, heavy selling

        Edge cases:
        - Ignore if total txs < 20 (insufficient data)
        - Prefer volume-weighted for accuracy (filters bot noise)
        """
        # Get transaction counts
        buys_24h = token_data.get('buys_24h', 0)
        sells_24h = token_data.get('sells_24h', 0)

        # Get volume data (if available) for volume-weighted calculation
        buy_volume = token_data.get('buy_volume_24h', 0)
        sell_volume = token_data.get('sell_volume_24h', 0)

        # Check if we have sufficient data
        total_txs = buys_24h + sells_24h

        if total_txs < 20:
            # Insufficient data - return neutral score
            logger.debug(f"      Insufficient buy/sell data ({total_txs} txs)")
            return 8  # Neutral score (middle of range)

        # Prefer volume-weighted if available (more accurate, filters small bot txs)
        if buy_volume > 0 and sell_volume > 0:
            total_volume = buy_volume + sell_volume
            buy_percentage = (buy_volume / total_volume) * 100
            logger.debug(f"      Volume-weighted: {buy_percentage:.1f}% buys (${buy_volume:.0f}/${sell_volume:.0f})")
        else:
            # Fall back to transaction count
            buy_percentage = (buys_24h / total_txs) * 100
            logger.debug(f"      Count-based: {buy_percentage:.1f}% buys ({buys_24h}/{sells_24h})")

        # Score based on buy percentage
        if buy_percentage >= 80:
            # Very Bullish: Aggressive accumulation
            score = 16 + int((buy_percentage - 80) / 5)  # 16-20 points
            return min(score, 20)
        elif buy_percentage >= 70:
            # Bullish: Positive momentum
            score = 12 + int((buy_percentage - 70) / 2.5)  # 12-16 points
            return score
        elif buy_percentage >= 50:
            # Neutral: Balanced
            score = 8 + int((buy_percentage - 50) / 5)  # 8-12 points
            return score
        elif buy_percentage >= 30:
            # Bearish: Caution
            score = 4 + int((buy_percentage - 30) / 5)  # 4-8 points
            return score
        else:
            # Very Bearish: Heavy distribution
            score = int(buy_percentage / 7.5)  # 0-4 points
            return max(score, 0)

    def _score_volume_liquidity_velocity(self, token_data: Dict) -> int:
        """
        Score based on volume/liquidity velocity (0-10 points)
        GROK ENHANCED: More graduated scoring for moderate flows
        OPT-044: High velocity indicates hot trading activity

        Pattern from 36 runners:
        - Small runners: avg velocity = 20.67 (hot trading)
        - Mega runners: avg velocity = 0.30 (stable/mature)

        High velocity = early momentum phase (GOOD)
        Low velocity = mature/stagnant (NEUTRAL/BAD)
        """
        volume_24h = token_data.get('volume_24h', 0)
        liquidity = token_data.get('liquidity', 1)  # Avoid div by zero

        # If no data, return 0
        if volume_24h == 0 or liquidity == 0:
            return 0

        # Calculate velocity ratio
        velocity_ratio = volume_24h / max(liquidity, 1000)

        # Scoring logic (more graduated)
        if velocity_ratio > 30:  # Extremely hot trading
            return 10  # Raised from 8
        elif velocity_ratio > 20:  # Very hot trading activity (GROK: >20% flow)
            return 8  # Raised from 6
        elif velocity_ratio > 10:  # Good momentum
            return 5  # Raised from 4
        elif velocity_ratio > 5:  # Moderate activity
            return 3  # Raised from 2
        elif velocity_ratio > 2:  # Light activity
            return 1  # New tier
        elif velocity_ratio < 1:  # Low activity (red flag)
            return -3
        else:
            return 0

    def _score_mcap_penalty(self, token_data: Dict) -> int:
        """
        Penalty for late entries (0 to -20 points)
        OPT-044: Avoid tokens that already ran

        Pattern from 36 runners:
        - Small runners: avg MCAP = $220K (actively pumping, +104% 24h)
        - Mega runners: avg MCAP = $1.5B (consolidating, -2.5% 24h)

        Large MCAP = we missed the entry window (PENALIZE)
        Small MCAP = early opportunity (NEUTRAL)
        """
        mcap = token_data.get('market_cap', 0)

        # If no MCAP data, return 0 (neutral)
        if mcap == 0:
            return 0

        # Penalty scoring (avoid late entries)
        if mcap > 10_000_000:  # $10M+ (way too late)
            return -20
        elif mcap > 5_000_000:  # $5M+ (too late)
            return -15
        elif mcap > 2_000_000:  # $2M+ (getting late)
            return -8
        elif mcap > 1_000_000:  # $1M+ (borderline)
            return -3
        else:
            return 0  # Under $1M = early opportunity

    def _score_buyer_velocity(self, token_address: str) -> int:
        """
        Score based on buyer velocity (0-30 points) - NEW: Replaces KOL scoring
        Measures how fast unique buyers are accumulating in a 5-minute window.

        Uses PumpPortal buyer history data (FREE).
        """
        if not self.pump_monitor:
            return 0

        weights = config.BUYER_VELOCITY_WEIGHTS
        window_seconds = weights.get('window_seconds', 300)

        # Get buyer history from pump monitor
        history = self.pump_monitor.buyer_history.get(token_address, [])
        if not history:
            # Fallback: use total unique buyers and tracking duration
            buyer_count = len(self.pump_monitor.unique_buyers.get(token_address, set()))
            duration_min = self.pump_monitor.get_buyer_tracking_duration(token_address)
            if duration_min <= 0 or buyer_count == 0:
                return 0
            # Extrapolate to 5-min rate
            buyers_per_5min = buyer_count / max(duration_min, 0.5) * 5
        else:
            # Calculate buyers gained in the last window_seconds
            now = datetime.now()
            cutoff = now - timedelta(seconds=window_seconds)

            # Find buyer count at cutoff and now
            buyers_at_cutoff = 0
            buyers_now = 0
            for ts, count in history:
                if ts <= cutoff:
                    buyers_at_cutoff = count
                buyers_now = count  # Last entry is most recent

            if buyers_at_cutoff == 0:
                # No history at cutoff, use first entry
                if history:
                    buyers_at_cutoff = history[0][1]

            buyers_per_5min = buyers_now - buyers_at_cutoff

        # Score based on velocity thresholds
        if buyers_per_5min >= 100:
            return weights['explosive']   # 25 pts
        elif buyers_per_5min >= 50:
            return weights['very_fast']   # 20 pts
        elif buyers_per_5min >= 25:
            return weights['fast']        # 15 pts
        elif buyers_per_5min >= 15:
            return weights['moderate']    # 10 pts
        elif buyers_per_5min >= 5:
            return weights['slow']        # 5 pts
        else:
            return weights['minimal']     # 0 pts

    def _score_bonding_speed(self, token_address: str, token_data: Dict) -> int:
        """
        Score based on bonding curve fill speed (0-15 points) - NEW
        How fast the bonding curve is progressing = organic demand indicator.

        Uses bonding_velocity from PumpPortal milestone tracking (FREE).
        Only applies to pre-graduation tokens.
        """
        bonding_pct = token_data.get('bonding_curve_pct', 0)
        is_pre_grad = bonding_pct < 100

        if not is_pre_grad:
            return 0  # Post-grad tokens don't have bonding curves

        weights = config.BONDING_SPEED_WEIGHTS

        # Try to get velocity from token_data (set by PumpPortal)
        bonding_velocity = token_data.get('bonding_velocity', 0)

        # Fallback: calculate from pump_monitor milestone data
        if bonding_velocity == 0 and self.pump_monitor:
            start_time = self.pump_monitor.buyer_tracking_start.get(token_address)
            if start_time and bonding_pct > 0:
                elapsed_seconds = (datetime.now() - start_time).total_seconds()
                if elapsed_seconds > 0:
                    bonding_velocity = bonding_pct / (elapsed_seconds / 60)  # %/min

        # Score based on velocity thresholds
        if bonding_velocity >= 5.0:
            score = weights['rocket']   # 15 pts
            # BONUS: Fast fill at 50%+ bonding = very strong interest signal
            if bonding_pct >= 50:
                score += 5
                logger.info(f"      ⚡ Bonding speed bonus: +5 pts (>{bonding_velocity:.1f}%/min at {bonding_pct:.0f}% bonding)")
            return score
        elif bonding_velocity >= 2.0:
            return weights['fast']     # 12 pts
        elif bonding_velocity >= 1.0:
            return weights['steady']   # 8 pts
        elif bonding_velocity >= 0.5:
            return weights['slow']     # 4 pts
        else:
            return weights['crawl']    # 0 pts

    def _score_graduation_speed(self, token_address: str, token_data: Dict) -> int:
        """
        Score based on graduation speed (-10 to +15 points) - POST-GRAD ONLY
        Fast graduation = strong organic demand; slow graduation = weak signal.

        Uses:
        - PumpPortal bonding milestone timestamps (100% milestone = graduation)
        - token_data created_at as fallback
        - Buyer count for slow-grad penalty qualification
        """
        grad_cfg = config.GRADUATION_SPEED_BONUS

        # Calculate graduation time in minutes
        grad_minutes = None

        # Method 1: PumpPortal bonding milestones (most accurate)
        if self.pump_monitor:
            milestones = self.pump_monitor.bonding_milestones.get(token_address, {})
            # Check for 100% milestone (graduation)
            if 100 in milestones:
                grad_ts = milestones[100]['timestamp']
                # Get token creation time from earliest milestone or buyer tracking start
                start_time = self.pump_monitor.buyer_tracking_start.get(token_address)
                if start_time:
                    grad_minutes = (grad_ts - start_time).total_seconds() / 60
            # Fallback: estimate from 10% and extrapolate
            elif milestones:
                earliest_pct = min(milestones.keys())
                earliest_ts = milestones[earliest_pct]['timestamp']
                start_time = self.pump_monitor.buyer_tracking_start.get(token_address)
                if start_time and earliest_pct > 0:
                    time_to_earliest = (earliest_ts - start_time).total_seconds() / 60
                    # Extrapolate: if it took X min to reach Y%, estimate total
                    rate_per_min = earliest_pct / max(time_to_earliest, 0.1)
                    if rate_per_min > 0:
                        grad_minutes = 100 / rate_per_min

        # Method 2: token_data timestamps
        if grad_minutes is None:
            created_at = token_data.get('created_at')
            graduated_at = token_data.get('graduated_at')
            if created_at and graduated_at:
                grad_minutes = (graduated_at - created_at).total_seconds() / 60
            elif created_at:
                # Assume just graduated if post-grad
                grad_minutes = (datetime.utcnow() - created_at).total_seconds() / 60

        if grad_minutes is None:
            return 0

        # Get buyer count for slow-grad check
        buyer_count = 0
        if self.pump_monitor:
            buyer_count = len(self.pump_monitor.unique_buyers.get(token_address, set()))
        if buyer_count == 0 and self.active_tracker:
            buyer_count = len(self.active_tracker.unique_buyers.get(token_address, set()))

        # Score based on graduation speed
        fast_threshold = grad_cfg.get('fast_grad_minutes', 15)
        slow_threshold = grad_cfg.get('slow_grad_minutes', 30)

        if grad_minutes <= fast_threshold:
            score = grad_cfg.get('fast_grad_bonus', 15)
            logger.debug(f"      Grad time: {grad_minutes:.1f}m (fast, <{fast_threshold}m)")
            return score
        elif grad_minutes >= slow_threshold:
            min_buyers_for_slow = grad_cfg.get('slow_grad_min_buyers', 100)
            if buyer_count < min_buyers_for_slow:
                score = grad_cfg.get('slow_grad_penalty', -10)
                logger.debug(f"      Grad time: {grad_minutes:.1f}m (slow, >{slow_threshold}m) + low buyers ({buyer_count})")
                return score

        return 0  # Neutral (between fast and slow thresholds)
