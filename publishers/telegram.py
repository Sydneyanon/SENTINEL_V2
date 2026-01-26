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
        # Banner disabled temporarily - file_id was for thumbnail, not animation
        # To re-enable: upload actual GIF/animation and get new file_id
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
                logger.info("🎨 Animated banner enabled")
            else:
                logger.info("ℹ️ No banner configured - signals will be text-only")
            
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize Telegram: {e}")
            return False
    
    def _format_signal(self, signal_data: Dict[str, Any]) -> str:
        """Format signal data into Telegram message"""
        
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

        # Get buyer/holder count based on graduation status
        # Pre-grad: use unique_buyers (from PumpPortal trades - FREE data)
        # Post-grad: use holder_count (from Helius/DexScreener - 10 credits)
        is_post_grad = bonding >= 100
        unique_buyers_count = token_data.get('unique_buyers', 0)

        if is_post_grad:
            holders = token_data.get('holder_count', signal_data.get('holders', 0))
            display_label = "Holders"
        else:
            # For pre-grad, show unique buyers (not holder_count which is always 0)
            holders = unique_buyers_count
            display_label = "Buyers"  # More accurate for pre-grad

        # Calculate age if we have created_timestamp
        age_minutes = 0
        created_ts = token_data.get('created_timestamp')
        if created_ts:
            age_seconds = (datetime.utcnow().timestamp() - created_ts)
            age_minutes = age_seconds / 60
        
        # Get smart wallet activity
        wallet_data = signal_data.get('smart_wallet_data', {})
        wallets = wallet_data.get('wallets', [])
        elite_count = wallet_data.get('elite_count', 0)
        kol_count = wallet_data.get('top_kol_count', 0)
        
        # Get narrative data
        narrative_data = signal_data.get('narrative_data', {})
        narratives = narrative_data.get('narratives', [])
        
        # Fire emojis based on conviction
        fire_count = min(conviction // 20, 5)
        fire_emojis = "🔥" * fire_count
        
        # Build message with HTML formatting and PROMETHEUS branding
        message = f"""🔥 <b>PROMETHEUS SIGNAL</b> {fire_emojis}

<b>${symbol}</b>
<b>Conviction: {conviction}/100</b>

💰 Price: ${price:.8f}
💎 MCap: ${mcap:,.0f}
💧 Liquidity: ${liquidity:,.0f}
👥 {display_label}: {holders}
📊 Bonding: {bonding:.1f}%
"""
        
        if age_minutes > 0:
            message += f"⏱️ Age: {age_minutes:.0f}m\n"
        
        message += "\n"
        
        # Add conviction breakdown (COMPLETE)
        if breakdown:
            message += "<b>📊 Score Breakdown:</b>\n"
            if breakdown.get('smart_wallet', 0) != 0:
                message += f"👑 Elite Wallets: +{breakdown['smart_wallet']}\n"
            if breakdown.get('narrative', 0) != 0:
                message += f"📈 Narratives: +{breakdown['narrative']}\n"
            if breakdown.get('unique_buyers', 0) != 0:
                message += f"👥 Unique Buyers: +{breakdown['unique_buyers']}\n"
            if breakdown.get('volume', 0) != 0:
                message += f"📊 Volume: +{breakdown['volume']}\n"
            if breakdown.get('momentum', 0) != 0:
                message += f"🚀 Momentum: +{breakdown['momentum']}\n"
            if breakdown.get('twitter_buzz', 0) != 0:
                message += f"🐦 Twitter: +{breakdown['twitter_buzz']}\n"
            if breakdown.get('telegram_calls', 0) != 0:
                message += f"📱 Telegram: +{breakdown['telegram_calls']}\n"
            # Show penalties/bonuses
            if breakdown.get('bundle_penalty', 0) != 0:
                message += f"⚠️ Bundle Penalty: {breakdown['bundle_penalty']}\n"
            if breakdown.get('holder_penalty', 0) != 0:
                message += f"⚠️ Holder Penalty: {breakdown['holder_penalty']}\n"
            if breakdown.get('kol_bonus', 0) != 0:
                message += f"🏆 KOL Bonus: +{breakdown['kol_bonus']}\n"
            # Show total
            message += f"<b>═══════════════</b>\n"
            message += f"<b>TOTAL: {breakdown.get('total', conviction)}/100</b>\n"
            message += "\n"
        
        # Add smart wallet activity (OPT-027: Enhanced with KOL names and tier badges)
        if wallets or elite_count > 0 or kol_count > 0:
            message += "<b>👑 Elite Trader Activity:</b>\n"
            if elite_count > 0:
                message += f"🏆 {elite_count} Elite trader(s)\n"
            if kol_count > 0:
                message += f"👑 {kol_count} Top KOL(s)\n"

            # Show top 3 wallets with enhanced tier badges
            for wallet in wallets[:3]:
                name = wallet.get('name', 'Unknown')
                # Fallback for None or empty names
                if not name or name == 'None' or name is None:
                    name = 'KOL'
                tier = wallet.get('tier', '')
                win_rate = wallet.get('win_rate', 0)
                pnl_30d = wallet.get('pnl_30d', 0)
                mins_ago = wallet.get('minutes_ago', 0)

                # OPT-027: Enhanced tier badges with god/elite/whale distinction
                if tier == 'god':
                    tier_badge = "👑 GOD"
                    tier_emoji = "👑"
                elif tier == 'elite':
                    tier_badge = "🔥 ELITE"
                    tier_emoji = "🔥"
                elif tier == 'top_kol':
                    tier_badge = "⭐ TOP KOL"
                    tier_emoji = "⭐"
                elif tier == 'whale':
                    tier_badge = "🐋 WHALE"
                    tier_emoji = "🐋"
                else:
                    tier_badge = "📊"
                    tier_emoji = "📊"

                # Build wallet line with tier badge, win rate, and optional PnL
                if win_rate > 0 and pnl_30d > 0:
                    message += f"{tier_emoji} <b>{name}</b> [{tier_badge}] - {win_rate*100:.0f}% WR, ${pnl_30d/1000:.0f}k PnL - {mins_ago:.0f}m ago\n"
                elif win_rate > 0:
                    message += f"{tier_emoji} <b>{name}</b> [{tier_badge}] - {win_rate*100:.0f}% WR - {mins_ago:.0f}m ago\n"
                else:
                    message += f"{tier_emoji} <b>{name}</b> [{tier_badge}] - {mins_ago:.0f}m ago\n"
            message += "\n"
        
        # Add narrative info
        if narratives:
            message += "<b>📈 Narratives:</b>\n"
            for narrative in narratives[:2]:  # Show top 2
                name = narrative.get('name', '').upper()
                message += f"• {name}\n"
            message += "\n"

        # Add rug detection warnings (if any)
        rug_checks = signal_data.get('rug_checks', {})
        bundle_check = rug_checks.get('bundle', {})
        holder_check = rug_checks.get('holder_concentration', {})

        if bundle_check.get('severity') and bundle_check['severity'] != 'none':
            severity = bundle_check['severity'].upper()
            reason = bundle_check.get('reason', '')
            message += f"⚠️  <b>{severity} BUNDLE DETECTED</b>\n"
            if reason:
                message += f"   {reason}\n"
            message += "\n"

        if holder_check.get('penalty', 0) < 0:
            reason = holder_check.get('reason', '')
            message += f"⚠️  <b>HOLDER CONCENTRATION</b>\n"
            if reason:
                message += f"   {reason}\n"
            message += "\n"

        # Add links
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
        else:
            holders = token_data.get('unique_buyers', 0)
            holder_label = "buyers"

        fire_count = min(conviction // 20, 5)
        fire_emojis = "\U0001f525" * fire_count

        # Format mcap/liquidity as compact K/M
        def fmt_k(v):
            if v >= 1_000_000:
                return f"${v/1_000_000:.1f}M"
            elif v >= 1_000:
                return f"${v/1_000:.1f}K"
            return f"${v:.0f}"

        msg = f"\U0001f525 <b>PROMETHEUS SIGNAL</b> {fire_emojis}\n\n"
        msg += f"<b>${symbol}</b> | <b>Conviction: {conviction}/100</b>\n\n"
        msg += f"\U0001f4b0 ${price:.8f} | \U0001f48e MCap {fmt_k(mcap)}\n"
        msg += f"\U0001f4a7 Liq {fmt_k(liquidity)} | \U0001f465 {holders} {holder_label}\n"
        msg += f"\U0001f4ca {bonding:.1f}% bonded"

        age_minutes = 0
        created_ts = token_data.get('created_timestamp')
        if created_ts:
            age_minutes = (datetime.utcnow().timestamp() - created_ts) / 60
        if age_minutes > 0:
            msg += f" | \u23f1\ufe0f {age_minutes:.0f}m old"
        msg += "\n"

        # Compact breakdown - only non-zero scores on one line
        if breakdown:
            parts = []
            score_map = [
                ('smart_wallet', '\U0001f451 Elite'), ('narrative', '\U0001f4c8 Narr'),
                ('unique_buyers', '\U0001f465 Buy'), ('volume', '\U0001f4ca Vol'),
                ('momentum', '\U0001f680 Mom'), ('telegram_calls', '\U0001f4f1 TG'),
            ]
            for key, label in score_map:
                v = breakdown.get(key, 0)
                if v > 0:
                    parts.append(f"{label} +{v}")
            if parts:
                msg += f"\n<b>\U0001f4ca Scores:</b> {' | '.join(parts)}\n"

        # Compact wallets - top 2
        wallet_data = signal_data.get('smart_wallet_data', {})
        wallets = wallet_data.get('wallets', [])
        if wallets:
            msg += f"\n<b>\U0001f451 Elite Traders:</b>\n"
            for w in wallets[:2]:
                name = w.get('name', 'KOL')
                if not name or name == 'None':
                    name = 'KOL'
                tier = w.get('tier', '')
                tier_map = {'god': 'GOD', 'elite': 'ELITE', 'top_kol': 'TOP KOL', 'whale': 'WHALE'}
                tier_str = tier_map.get(tier, 'KOL')
                wr = w.get('win_rate', 0)
                line = f"<b>{name}</b> [{tier_str}]"
                if wr > 0:
                    line += f" {wr*100:.0f}% WR"
                msg += f"{line}\n"

        # Links
        msg += f'\n<a href="https://dexscreener.com/solana/{token_address}">DexS</a>'
        msg += f' | <a href="https://birdeye.so/token/{token_address}">Bird</a>'
        msg += f' | <a href="https://pump.fun/{token_address}">Pump</a>\n'
        msg += f"\n<code>{token_address}</code>\n"
        msg += f"\n\u26a0\ufe0f DYOR | \U0001f525 The fire spreads."

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
        logger.info(f"   Conviction: {conviction}/100")
        logger.info(f"   Target channel: {self.channel_id}")

        # OPT-051: Retry logic (3 attempts, 2s delay)
        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(1, max_retries + 1):
            try:
                message = self._format_signal(signal_data)

                # If we have a banner, send as single video message with compact caption
                if self.banner_file_id:
                    try:
                        compact_caption = self._format_signal_compact(signal_data)
                        result = await self.bot.send_video(
                            chat_id=self.channel_id,
                            video=self.banner_file_id,
                            caption=compact_caption,
                            parse_mode=ParseMode.HTML,
                            supports_streaming=True,
                            disable_notification=False
                        )
                    except TelegramError as e:
                        logger.warning(f"⚠️ Banner failed ({e}), sending text-only")
                        # Fallback to full text-only message
                        result = await self.bot.send_message(
                            chat_id=self.channel_id,
                            text=message,
                            parse_mode=ParseMode.HTML,
                            disable_web_page_preview=False
                        )
                else:
                    # No banner - send full text message
                    result = await self.bot.send_message(
                        chat_id=self.channel_id,
                        text=message,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=False
                    )

                # SUCCESS! Reset failure counter
                self.consecutive_failures = 0
                logger.info(f"📤 Posted Prometheus signal to Telegram: ${symbol} ({conviction}/100)")
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
        logger.error(f"   Conviction: {conviction}/100")
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
                # Send with banner if available
                await self.bot.send_animation(
                    chat_id=self.channel_id,
                    animation=self.banner_file_id,
                    caption=test_message,
                    parse_mode=ParseMode.HTML
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
        Upload banner GIF and return file_id for future use
        
        Args:
            banner_path: Path to the banner GIF file
            
        Returns:
            file_id if successful, None otherwise
        """
        if not self.bot or not self.channel_id:
            logger.error("Bot not initialized")
            return None
        
        try:
            with open(banner_path, 'rb') as gif:
                result = await self.bot.send_animation(
                    chat_id=self.channel_id,
                    animation=gif,
                    caption="🎨 Banner uploaded! Saving file_id..."
                )
                
                file_id = result.animation.file_id
                logger.info(f"✅ Banner uploaded successfully!")
                logger.info(f"📝 Add this to your config.py:")
                logger.info(f'TELEGRAM_BANNER_FILE_ID = "{file_id}"')
                
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
