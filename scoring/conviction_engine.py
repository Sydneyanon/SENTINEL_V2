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

    Scoring breakdown (with rug detection):
    - Smart Wallet Activity: 0-40 points
    - Narrative Detection: 0-25 points (if enabled)
    - Buy/Sell Ratio: 0-20 points (percentage-based)
    - Unique Buyers: 0-15 points
    - Volume Velocity: 0-10 points
    - Price Momentum: 0-10 points
    - Telegram Calls: 0-20 points
    - Bundle Penalty: -5 to -40 points (with overrides)
    - Holder Concentration: -15 to -40 points (with KOL bonus)
    - ML Prediction: -30 to +20 points
    Total: 0-130+ points (can exceed with bonuses)

    NOTE: LunarCrush and Twitter scoring removed (no budget)
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
            print("🎯 MULTI-FACTOR SCORING SYSTEM (0-100+ scale):")
            print("   ├─ 👑 Elite KOL Activity (0-40 pts)")
            print("   ├─ 🎯 Narrative Match (0-25 pts)")
            print("   ├─ 💹 Buy/Sell Ratio (0-20 pts)")
            print("   ├─ 👥 Unique Buyers (0-15 pts)")
            print("   ├─ 🚀 Price Momentum (0-10 pts)")
            print("   ├─ 📊 Volume Velocity (0-10 pts)")
            print("   ├─ 📱 Telegram Calls (0-20 pts)")
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

            base_total = sum(base_scores.values())
            logger.info(f"   💰 BASE SCORE: {base_total}/133")
            
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
            # PHASE 3.5: SOCIAL SENTIMENT - REMOVED (No budget)
            # ================================================================
            # LunarCrush and Twitter scoring removed to save API costs
            # All social scoring now comes from Telegram calls only

            social_score = 0
            twitter_score = 0
            social_data = {}
            twitter_data = {}

            logger.info(f"   🌙 LunarCrush: DISABLED (no budget)")
            logger.info(f"   🐦 Twitter: DISABLED (no budget)")

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

            # Cap total social score (Telegram only now) at 25 pts
            # This prevents over-scoring noisy hype
            total_social = social_confirmation_score  # Twitter removed
            if total_social > 25:
                excess = total_social - 25
                social_confirmation_score -= excess
                logger.info(f"   ⚖️  Social cap applied: reduced Telegram by {excess} pts (max 25 total)")
                telegram_call_data['capped'] = True

            mid_total += social_confirmation_score

            # ================================================================
            # PHASE 3.7.5: MULTI-CALL BONUS (persistent telegram data)
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

                        # If both bonuses apply, cap at +20 to avoid over-scoring
                        if multi_call_bonus > 20:
                            logger.info(f"      ⚖️  Multi-call bonus capped at +20 pts")
                            multi_call_bonus = 20

                        if multi_call_bonus > 0:
                            telegram_call_data['multi_call_bonus'] = multi_call_bonus

                except Exception as e:
                    logger.error(f"   ❌ Error calculating multi-call bonus: {e}")
                    multi_call_bonus = 0

            mid_total += multi_call_bonus

            # ================================================================
            # PHASE 3.8: SOCIAL VERIFICATION - FREE
            # ================================================================
            # Verify token has legitimate social presence (Twitter, Telegram, website)
            # This is different from buzz/sentiment - it's about legitimacy verification
            # Data comes from PumpPortal (pre-grad) or DexScreener (post-grad)
            #
            # SCORING ASYMMETRY (pre-grad socials matter less):
            # - Pre-grad: -20 (none) to +13 (full set) — most pre-grad skip socials
            # - Post-grad: -15 (none) to +21 (full + active) — socials more meaningful once DEX listed

            social_verification_score = 0
            social_verification_data = {}

            # Check if social data is available (from PumpPortal or DexScreener)
            if token_data.get('has_twitter') is not None:
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
                        # No socials pre-grad = likely low-effort rug
                        social_verification_score = -20
                        social_verification_data['anonymous'] = True
                        logger.warning(f"   ⚠️  PRE-GRAD: No socials: -20 pts (low-effort rug)")
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
                is_boosted = token_data.get('is_boosted', False)
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
                    # RugCheck failed - don't block, just log
                    logger.debug(f"   ⚠️  RugCheck API unavailable: {rugcheck_result.get('error', 'Unknown error')}")

            # Apply RugCheck penalty to mid_total
            mid_total += rugcheck_penalty

            # NEW: DexScreener Boost Detection (paid promotion = dump signal)
            boost_penalty = 0
            if token_data.get('boost_active', 0) > 0:
                # Paid promotion detected - often precedes dumps
                boost_penalty = -25
                logger.warning(f"   🚨 PAID BOOST DETECTED: {boost_penalty} pts (potential pump & dump)")
                mid_total += boost_penalty

            # 1. Liquidity < $20k (too thin, likely rug)
            # OPT-044: Increased from $2k to $20k (ML shows liquidity is 3rd most important feature)
            # Higher threshold prevents rug pulls and manipulation
            liquidity = token_data.get('liquidity', 0)
            if liquidity > 0 and liquidity < config.MIN_LIQUIDITY:
                emergency_blocks.append(f"Liquidity too low: ${liquidity:.0f} < ${config.MIN_LIQUIDITY}")

            # 2. Token age < 30 seconds (too fresh, wait for real activity)
            # REDUCED from 2min to 30sec: KOLs buy within 0-60sec, we were too late!
            # Still filters out instant rugs but allows early entry
            token_created_at = token_data.get('created_at')
            if token_created_at:
                token_age_seconds = (datetime.utcnow() - token_created_at).total_seconds()
                if token_age_seconds < 30:  # 30 seconds (was 2 minutes)
                    emergency_blocks.append(f"Token too new: {token_age_seconds:.0f}s old (< 30sec)")

            # 3. No liquidity at all (pre-graduation tokens need some liquidity)
            if liquidity == 0 and bonding_pct < 100:
                emergency_blocks.append(f"Zero liquidity on pre-grad token")

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
                    'holder_penalty': holder_result['penalty'],
                    'kol_bonus': holder_result['kol_bonus'],
                    'ml_bonus': ml_result.get('ml_bonus', 0),
                    'total': final_score
                },
                'rug_checks': {
                    'rugcheck_api': rugcheck_result,
                    'bundle': bundle_result,
                    'holder_concentration': holder_result
                },
                'social_data': social_data,
                'twitter_data': twitter_data,
                'telegram_call_data': telegram_call_data,
                'social_verification_data': social_verification_data,
                'smart_wallet_data': smart_wallet_data,  # FIXED: Include wallet data for display
                'ml_prediction': ml_result  # ML prediction with class, confidence, and bonus
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
        """
        Score based on price momentum (0-10 points base + multi-timeframe bonus)

        - Pre-grad: Uses 5m price change (0-10 pts)
        - Post-grad: Uses 5m price change + multi-timeframe bonus (1h/6h/24h, +5 pts each)
        """
        bonding_pct = token_data.get('bonding_curve_pct', 0)
        is_pre_grad = bonding_pct < 100

        # Base score from 5m price change
        price_change_5m = token_data.get('price_change_5m', 0)

        if price_change_5m >= 50:  # +50% in 5 min
            base_score = config.MOMENTUM_WEIGHTS['very_strong']
        elif price_change_5m >= 20:  # +20% in 5 min
            base_score = config.MOMENTUM_WEIGHTS['strong']
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
        Score based on volume/liquidity velocity (0-8 points)
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

        # Scoring logic
        if velocity_ratio > 30:  # Extremely hot trading
            return 8
        elif velocity_ratio > 20:  # Very hot trading activity
            return 6
        elif velocity_ratio > 10:  # Good momentum
            return 4
        elif velocity_ratio > 5:  # Moderate activity
            return 2
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
