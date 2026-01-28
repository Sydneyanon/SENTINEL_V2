"""
Telegram Publisher - Post signals to channel with Prometheus branding
"""
from typing import Dict, Any, Optional
from datetime import datetime
from loguru import logger
from telegram import Bot
from telegram.error import TelegramError
from telegram.constants import ParseMode
import asyncio
import config


class TelegramPublisher:
    """Publishes trading signals to Telegram channel"""

    def __init__(self):
        self.bot: Optional[Bot] = None
        self.channel_id = config.TELEGRAM_CHANNEL_ID
        self.enabled = config.ENABLE_TELEGRAM
        self.banner_file_id = getattr(config, 'TELEGRAM_BANNER_FILE_ID', None)

        # OPT-051: Health check tracking
        self.consecutive_failures = 0
        self.failed_signals = []  # Track failed signals for database fallback
        
    async def initialize(self):
        """Initialize Telegram bot"""
        if not self.enabled:
            logger.info("ℹ️ Telegram publishing disabled")
            return False
            
        if not config.TELEGRAM_BOT_TOKEN:
            logger.warning("⚠️ TELEGRAM_BOT_TOKEN not set")
            return False
            
        if not config.TELEGRAM_CHANNEL_ID:
            logger.warning("⚠️ TELEGRAM_CHANNEL_ID not set")
            return False
            
        try:
            self.bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
            me = await self.bot.get_me()
            logger.info(f"✅ Telegram bot initialized: @{me.username}")
            
            if self.banner_file_id:
                logger.info(f"🎨 Banner configured (file_id: {self.banner_file_id[:20]}...)")
                # Test if the file_id is still valid
                try:
                    file_info = await self.bot.get_file(self.banner_file_id)
                    logger.info(f"   ✅ Banner file_id valid (size: {file_info.file_size} bytes)")
                except TelegramError as e:
                    logger.error(f"   ❌ Banner file_id INVALID: {e}")
                    logger.error(f"   Re-upload your banner MP4/GIF to get a fresh file_id")
                    self.banner_file_id = None  # Disable broken banner
            else:
                logger.info(f"⚠️ No banner configured - signals will be text-only")
            
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize Telegram: {e}")
            return False
    
    def _format_signal(self, signal_data: Dict[str, Any]) -> str:
        """Format signal data into Telegram message (on-chain-first scoring)"""

        # Extract token data
        token_data = signal_data.get('token_data', {})

        symbol = token_data.get('token_symbol', signal_data.get('symbol', 'UNKNOWN'))
        token_address = token_data.get('token_address', signal_data.get('token_address', 'N/A'))
        conviction = signal_data.get('score', signal_data.get('conviction_score', 0))

        # Get conviction breakdown
        breakdown = signal_data.get('breakdown', {})

        # Get metrics
        price = token_data.get('price_usd', signal_data.get('price', 0))
        mcap = token_data.get('market_cap', signal_data.get('market_cap', 0))
        liquidity = token_data.get('liquidity', signal_data.get('liquidity', 0))
        bonding = token_data.get('bonding_curve_pct', 0)

        # Pre-grad vs post-grad display
        is_post_grad = bonding >= 100
        unique_buyers_count = token_data.get('unique_buyers', 0)

        if is_post_grad:
            holders = token_data.get('holder_count', signal_data.get('holders', 0))
            display_label = "Holders"
            phase_label = "POST-GRAD"
        else:
            holders = unique_buyers_count
            display_label = "Buyers"
            phase_label = f"{bonding:.0f}% BONDED"

        # Calculate age
        age_minutes = 0
        created_ts = token_data.get('created_timestamp')
        if created_ts:
            age_minutes = (datetime.utcnow().timestamp() - created_ts) / 60

        # Get narrative data
        narrative_data = signal_data.get('narrative_data', {})
        narratives = narrative_data.get('narratives', [])

        # Fire emojis based on conviction
        fire_count = min(conviction // 20, 5)
        fire_emojis = "🔥" * fire_count

        # Build message with on-chain-first branding
        message = f"""🔥 <b>PROMETHEUS SIGNAL</b> {fire_emojis}

<b>${symbol}</b> | <b>{phase_label}</b>
<b>Conviction: {conviction}/100</b>

💰 Price: ${price:.8f}
💎 MCap: ${mcap:,.0f}
💧 Liquidity: ${liquidity:,.0f}
👥 {display_label}: {holders}
"""

        if age_minutes > 0:
            message += f"⏱️ Age: {age_minutes:.0f}m\n"

        message += "\n"

        # ON-CHAIN SCORE BREAKDOWN (new format)
        if breakdown:
            message += "<b>📊 On-Chain Score:</b>\n"

            # Primary on-chain signals (positive scores only)
            score_items = [
                ('buyer_velocity', '🏃 Vel'),
                ('unique_buyers', '👥 Buyers'),
                ('buy_sell_ratio', '💹 B/S'),
                ('bonding_speed', '⚡ Bond'),
                ('acceleration', '🔥 Accel'),
                ('volume', '📊 Vol'),
                ('momentum', '🚀 Mom'),
                ('narrative', '🎯 Narr'),
                ('telegram_calls', '📱 TG'),
            ]

            for key, label in score_items:
                val = breakdown.get(key, 0)
                if val > 0:
                    message += f"{label}: +{val}\n"

            # ML bonus (if active)
            ml_bonus = breakdown.get('ml_bonus', 0)
            if ml_bonus != 0:
                message += f"🤖 ML Prediction: {ml_bonus:+d}\n"

            # Penalties (negative scores)
            penalties = []
            if breakdown.get('bundle_penalty', 0) != 0:
                penalties.append(f"Bundle: {breakdown['bundle_penalty']}")
            if breakdown.get('holder_penalty', 0) != 0:
                penalties.append(f"Holders: {breakdown['holder_penalty']}")
            if breakdown.get('authority_penalty', 0) != 0:
                penalties.append(f"Authority: {breakdown['authority_penalty']}")
            if breakdown.get('dev_sell_penalty', 0) != 0:
                penalties.append(f"Dev Sells: {breakdown['dev_sell_penalty']}")
            if breakdown.get('rugcheck_penalty', 0) != 0:
                penalties.append(f"Rugcheck: {breakdown['rugcheck_penalty']}")

            if penalties:
                message += f"⚠️ {' | '.join(penalties)}\n"

            message += f"<b>═══════════════</b>\n"
            message += f"<b>TOTAL: {breakdown.get('total', conviction)}</b>\n"
            message += "\n"

        # Narrative info
        if narratives:
            message += "<b>🎯 Narratives:</b>\n"
            for narrative in narratives[:2]:
                name = narrative.get('name', '').upper()
                message += f"• {name}\n"
            message += "\n"

        # Rug detection warnings
        rug_checks = signal_data.get('rug_checks', {})
        bundle_check = rug_checks.get('bundle', {})
        holder_check = rug_checks.get('holder_concentration', {})

        if bundle_check.get('severity') and bundle_check['severity'] != 'none':
            severity = bundle_check['severity'].upper()
            reason = bundle_check.get('reason', '')
            message += f"⚠️ <b>{severity} BUNDLE DETECTED</b>\n"
            if reason:
                message += f"   {reason}\n"
            message += "\n"

        if holder_check.get('penalty', 0) < 0:
            reason = holder_check.get('reason', '')
            message += f"⚠️ <b>HOLDER CONCENTRATION</b>\n"
            if reason:
                message += f"   {reason}\n"
            message += "\n"

        # Socials
        twitter = token_data.get('twitter', '')
        telegram_link = token_data.get('telegram', '')
        website = token_data.get('website', '')
        social_items = []
        if twitter:
            social_items.append(f'<a href="{twitter}">Twitter</a>')
        if telegram_link:
            social_items.append(f'<a href="{telegram_link}">Telegram</a>')
        if website:
            social_items.append(f'<a href="{website}">Website</a>')

        social_count = len(social_items)
        if social_items:
            message += f"🌐 <b>Socials ({social_count}/3):</b> {' | '.join(social_items)}\n\n"

        # Links
        message += f"""🔗 <a href="https://dexscreener.com/solana/{token_address}">DexScreener</a>
🔗 <a href="https://birdeye.so/token/{token_address}">Birdeye</a>
🔗 <a href="https://pump.fun/{token_address}">Pump.fun</a>

<code>{token_address}</code>

⚠️ DYOR - Not financial advice
🔥 The fire spreads."""

        return message
    
    def _format_signal_compact(self, signal_data: Dict[str, Any]) -> str:
        """Format signal as compact caption for video banner (max 1024 chars)"""
        token_data = signal_data.get('token_data', {})
        symbol = token_data.get('token_symbol', signal_data.get('symbol', 'UNKNOWN'))
        token_address = token_data.get('token_address', signal_data.get('token_address', 'N/A'))
        conviction = signal_data.get('score', signal_data.get('conviction_score', 0))
        breakdown = signal_data.get('breakdown', {})

        price = token_data.get('price_usd', signal_data.get('price', 0))
        mcap = token_data.get('market_cap', signal_data.get('market_cap', 0))
        liquidity = token_data.get('liquidity', signal_data.get('liquidity', 0))
        bonding = token_data.get('bonding_curve_pct', 0)
        is_post_grad = bonding >= 100

        if is_post_grad:
            holders = token_data.get('holder_count', signal_data.get('holders', 0))
            holder_label = "holders"
            phase = "POST-GRAD"
        else:
            holders = token_data.get('unique_buyers', 0)
            holder_label = "buyers"
            phase = f"{bonding:.0f}% bonded"

        fire_count = min(conviction // 20, 5)
        fire_emojis = "\U0001f525" * fire_count

        def fmt_k(v):
            if v >= 1_000_000:
                return f"${v/1_000_000:.1f}M"
            elif v >= 1_000:
                return f"${v/1_000:.1f}K"
            return f"${v:.0f}"

        msg = f"\U0001f525 <b>PROMETHEUS SIGNAL</b> {fire_emojis}\n\n"
        if signal_data.get('early_pump_alert'):
            msg += f"\u26a0\ufe0f <b>HIGH RISK \u2013 EARLY MOMENTUM</b> \u26a0\ufe0f\n"
        msg += f"<b>${symbol}</b> | {phase} | {conviction}/100\n\n"
        msg += f"\U0001f4b0 ${price:.8f} | \U0001f48e MCap {fmt_k(mcap)}\n"
        msg += f"\U0001f4a7 Liq {fmt_k(liquidity)} | \U0001f465 {holders} {holder_label}\n"

        age_minutes = 0
        created_ts = token_data.get('created_timestamp')
        if created_ts:
            age_minutes = (datetime.utcnow().timestamp() - created_ts) / 60
        if age_minutes > 0:
            msg += f"\u23f1\ufe0f {age_minutes:.0f}m old\n"

        # On-chain score breakdown - only non-zero
        if breakdown:
            parts = []
            score_map = [
                ('buyer_velocity', '\U0001f3c3 Vel'),
                ('unique_buyers', '\U0001f465 Buy'),
                ('buy_sell_ratio', '\U0001f4b9 B/S'),
                ('bonding_speed', '\u26a1 Bond'),
                ('acceleration', '\U0001f525 Accel'),
                ('volume', '\U0001f4ca Vol'),
                ('momentum', '\U0001f680 Mom'),
                ('narrative', '\U0001f3af Narr'),
                ('telegram_calls', '\U0001f4f1 TG'),
            ]
            for key, label in score_map:
                v = breakdown.get(key, 0)
                if v > 0:
                    parts.append(f"{label} +{v}")
            if parts:
                msg += f"\n\U0001f4ca {' | '.join(parts)}\n"

            # Penalties (compact)
            pen_parts = []
            for key in ('bundle_penalty', 'holder_penalty', 'rugcheck_penalty'):
                v = breakdown.get(key, 0)
                if v != 0:
                    pen_parts.append(f"{v}")
            if pen_parts:
                msg += f"\u26a0\ufe0f Penalties: {', '.join(pen_parts)}\n"

        # Socials
        twitter = token_data.get('twitter', '')
        telegram_link = token_data.get('telegram', '')
        website = token_data.get('website', '')
        socials = []
        if twitter:
            socials.append(f'<a href="{twitter}">𝕏</a>')
        if telegram_link:
            socials.append(f'<a href="{telegram_link}">TG</a>')
        if website:
            socials.append(f'<a href="{website}">Web</a>')
        if socials:
            msg += f"\n🌐 Socials: {' | '.join(socials)}\n"

        # Links
        msg += f'\n<a href="https://dexscreener.com/solana/{token_address}">DexS</a>'
        msg += f' | <a href="https://birdeye.so/token/{token_address}">Bird</a>'
        msg += f' | <a href="https://pump.fun/{token_address}">Pump</a>\n'
        msg += f"\n<code>{token_address}</code>"

        return msg

    async def post_signal(self, signal_data: Dict[str, Any]) -> Optional[int]:
        """
        Post signal to Telegram channel with animated banner

        OPT-051: Added retry logic, health checks, and fallback handling

        SECURITY: Only posts to authorized channel (TELEGRAM_CHANNEL_ID)

        Returns:
            Message ID if successful, None otherwise
        """

        if not self.enabled or not self.bot or not self.channel_id:
            error_msg = f"⚠️ SIGNAL PASSED BUT NOT POSTED TO TELEGRAM - enabled={self.enabled}, bot={'initialized' if self.bot else 'None'}, channel_id={self.channel_id}"
            logger.warning(error_msg)

            # OPT-051: Store failed signal for fallback
            token_data = signal_data.get('token_data', {})
            mint = token_data.get('token_address', 'UNKNOWN')
            self.failed_signals.append({
                'mint': mint,
                'reason': 'telegram_not_initialized',
                'timestamp': datetime.utcnow(),
                'signal_data': signal_data
            })
            logger.error(f"🚨 FAILED TO POST SIGNAL: {mint} - telegram_not_initialized")

            return None

        # SECURITY: Verify we're posting to authorized channel only
        if not self.channel_id:
            logger.error("🚫 No authorized channel configured - refusing to post")
            return None

        # Extract token info for logging
        token_data = signal_data.get('token_data', {})
        symbol = token_data.get('token_symbol', 'UNKNOWN')
        mint = token_data.get('token_address', 'UNKNOWN')
        conviction = signal_data.get('score', 0)

        # Log what data we received
        logger.info(f"📤 Preparing Telegram signal:")
        logger.info(f"   Symbol: {symbol}")
        logger.info(f"   Price: ${token_data.get('price_usd', 0):.8f}")
        logger.info(f"   MCap: ${token_data.get('market_cap', 0):,.0f}")
        logger.info(f"   Liquidity: ${token_data.get('liquidity', 0):,.0f}")
        logger.info(f"   Conviction: {conviction}")
        logger.info(f"   Target channel: {self.channel_id}")

        # OPT-051: Retry logic (3 attempts, 2s delay)
        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(1, max_retries + 1):
            try:
                compact_caption = self._format_signal_compact(signal_data)

                # If we have a banner, send as animation/video with compact caption
                if self.banner_file_id:
                    try:
                        logger.info(f"🎬 Sending animation banner for ${symbol}...")
                        result = await self.bot.send_animation(
                            chat_id=self.channel_id,
                            animation=self.banner_file_id,
                            caption=compact_caption,
                            parse_mode=ParseMode.HTML,
                            disable_notification=False
                        )
                    except TelegramError as e1:
                        logger.warning(f"⚠️ Animation failed ({e1}), trying send_video...")
                        try:
                            result = await self.bot.send_video(
                                chat_id=self.channel_id,
                                video=self.banner_file_id,
                                caption=compact_caption,
                                parse_mode=ParseMode.HTML,
                                supports_streaming=True,
                                disable_notification=False
                            )
                        except TelegramError as e2:
                            logger.warning(f"⚠️ Video also failed ({e2}), file_id may be expired. Sending text-only")
                            logger.warning(f"   Banner file_id: {self.banner_file_id[:30]}...")
                            logger.warning(f"   Re-upload banner with upload_banner() to get a fresh file_id")
                            result = await self.bot.send_message(
                                chat_id=self.channel_id,
                                text=compact_caption,
                                parse_mode=ParseMode.HTML,
                                disable_web_page_preview=False
                            )
                else:
                    # No banner - send compact text message
                    result = await self.bot.send_message(
                        chat_id=self.channel_id,
                        text=compact_caption,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=False
                    )

                # SUCCESS! Reset failure counter
                self.consecutive_failures = 0
                logger.info(f"📤 Posted Prometheus signal to Telegram: ${symbol} ({conviction})")
                return result.message_id

            except TelegramError as e:
                logger.error(f"❌ Telegram error (attempt {attempt}/{max_retries}): {e}")
                if attempt < max_retries:
                    logger.info(f"⏳ Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                else:
                    # Final attempt failed - log to fallback
                    self._handle_posting_failure(mint, symbol, conviction, str(e), signal_data)
                    return None

            except Exception as e:
                logger.error(f"❌ Unexpected error (attempt {attempt}/{max_retries}): {e}")
                import traceback
                logger.error(traceback.format_exc())
                if attempt < max_retries:
                    logger.info(f"⏳ Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                else:
                    # Final attempt failed - log to fallback
                    self._handle_posting_failure(mint, symbol, conviction, str(e), signal_data)
                    return None

        return None

    def _handle_posting_failure(self, mint: str, symbol: str, conviction: int, error: str, signal_data: Dict[str, Any]):
        """
        OPT-051: Handle posting failure - track for health check and fallback

        Args:
            mint: Token contract address
            symbol: Token symbol
            conviction: Conviction score
            error: Error message
            signal_data: Full signal data
        """
        self.consecutive_failures += 1
        self.failed_signals.append({
            'mint': mint,
            'symbol': symbol,
            'conviction': conviction,
            'reason': error,
            'timestamp': datetime.utcnow(),
            'signal_data': signal_data
        })

        logger.error(f"🚨 FAILED TO POST SIGNAL: {mint} ({symbol}) - {error}")
        logger.error(f"   Conviction: {conviction}")
        logger.error(f"   Consecutive failures: {self.consecutive_failures}")

        # OPT-051: Health check - alert if 3+ consecutive failures
        if self.consecutive_failures >= 3:
            logger.critical(f"""
🚨🚨🚨 TELEGRAM HEALTH CHECK FAILED 🚨🚨🚨
Consecutive posting failures: {self.consecutive_failures}
Recent failed signals: {len(self.failed_signals)}

⚠️  TELEGRAM POSTING IS DOWN - INVESTIGATE IMMEDIATELY
Check:
1. Bot token is valid (TELEGRAM_BOT_TOKEN)
2. Channel ID is correct (TELEGRAM_CHANNEL_ID={self.channel_id})
3. Bot has admin rights in channel
4. Network connectivity
5. Railway logs for errors

Failed signals logged to database with 'posting_failed' flag.
""")

        # Log failed signal count
        logger.warning(f"📊 Total failed signals this session: {len(self.failed_signals)}")
    
    async def post_test_message(self) -> bool:
        """
        Post a test message to verify bot is working

        SECURITY: Only posts to authorized channel
        """

        if not self.bot or not self.channel_id:
            logger.error("Bot not initialized")
            return False

        try:
            logger.info(f"📤 Posting test message to authorized channel: {self.channel_id}")

            test_message = f"""🔥 <b>PROMETHEUS - System Test</b>

✅ Telegram connection working
⏰ Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

The fire has been stolen. Watching for elite trader activity... 🔥"""
            
            if self.banner_file_id:
                # Send with animation banner (fallback to video)
                try:
                    await self.bot.send_animation(
                        chat_id=self.channel_id,
                        animation=self.banner_file_id,
                        caption=test_message,
                        parse_mode=ParseMode.HTML
                    )
                except TelegramError:
                    await self.bot.send_video(
                        chat_id=self.channel_id,
                        video=self.banner_file_id,
                        caption=test_message,
                        parse_mode=ParseMode.HTML,
                        supports_streaming=True
                    )
            else:
                await self.bot.send_message(
                    chat_id=self.channel_id,
                    text=test_message,
                    parse_mode=ParseMode.HTML
                )
            
            logger.info("✅ Test message posted successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to post test message: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def upload_banner(self, banner_path: str) -> Optional[str]:
        """
        Upload banner video/GIF and return file_id for future use

        Args:
            banner_path: Path to the banner video (MP4) or GIF file

        Returns:
            file_id if successful, None otherwise
        """
        if not self.bot or not self.channel_id:
            logger.error("Bot not initialized")
            return None

        try:
            with open(banner_path, 'rb') as f:
                result = await self.bot.send_video(
                    chat_id=self.channel_id,
                    video=f,
                    caption="🎨 Banner uploaded! Saving file_id...",
                    supports_streaming=True
                )

                file_id = result.video.file_id
                logger.info(f"✅ Banner uploaded successfully!")
                logger.info(f"📝 Set this environment variable:")
                logger.info(f'TELEGRAM_BANNER_FILE_ID={file_id}')

                # Delete the test message
                await self.bot.delete_message(
                    chat_id=self.channel_id,
                    message_id=result.message_id
                )

                return file_id

        except FileNotFoundError:
            logger.error(f"❌ Banner file not found: {banner_path}")
            return None
        except Exception as e:
            logger.error(f"❌ Failed to upload banner: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
