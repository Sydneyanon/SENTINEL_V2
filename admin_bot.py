"""
Admin Telegram Bot - Handle admin commands for monitoring and control
"""
import asyncio
import aiohttp
import json
import os
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.constants import ParseMode
import config


class AdminBot:
    """Admin command handler for Telegram"""

    def __init__(self, active_tracker=None, database=None, performance_tracker=None, telegram_calls_cache=None):
        self.active_tracker = active_tracker
        self.database = database
        self.performance_tracker = performance_tracker
        self.telegram_calls_cache = telegram_calls_cache
        self.app: Optional[Application] = None
        self.admin_user_id = config.ADMIN_TELEGRAM_USER_ID
        self.admin_channel_id = config.ADMIN_CHANNEL_ID  # Optional: post to channel instead of DM

    async def initialize(self):
        """Initialize admin bot"""
        if not config.TELEGRAM_BOT_TOKEN:
            logger.warning("⚠️ TELEGRAM_BOT_TOKEN not set - admin bot disabled")
            return False

        if not self.admin_user_id:
            logger.warning("⚠️ ADMIN_TELEGRAM_USER_ID not set - admin bot disabled")
            logger.info("   Get your ID from @userinfobot and set ADMIN_TELEGRAM_USER_ID")
            return False

        try:
            logger.info(f"🔧 Creating admin bot application...")
            logger.info(f"   Bot token: {config.TELEGRAM_BOT_TOKEN[:20]}...")
            logger.info(f"   Admin user ID: {self.admin_user_id}")

            # Create application
            self.app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

            # Add security filter - only admin can use commands
            admin_filter = filters.User(user_id=self.admin_user_id)

            # Register command handlers (admin only)
            self.app.add_handler(CommandHandler("start", self._cmd_help, filters=admin_filter))
            self.app.add_handler(CommandHandler("help", self._cmd_help, filters=admin_filter))
            self.app.add_handler(CommandHandler("stats", self._cmd_stats, filters=admin_filter))
            self.app.add_handler(CommandHandler("active", self._cmd_active, filters=admin_filter))
            self.app.add_handler(CommandHandler("performance", self._cmd_performance, filters=admin_filter))
            self.app.add_handler(CommandHandler("health", self._cmd_health, filters=admin_filter))
            self.app.add_handler(CommandHandler("cache", self._cmd_cache, filters=admin_filter))
            self.app.add_handler(CommandHandler("missed", self._cmd_missed, filters=admin_filter))
            self.app.add_handler(CommandHandler("whales", self._cmd_whales, filters=admin_filter))
            self.app.add_handler(CommandHandler("config", self._cmd_config, filters=admin_filter))
            self.app.add_handler(CommandHandler("dataset", self._cmd_dataset, filters=admin_filter))
            self.app.add_handler(CommandHandler("collect", self._cmd_collect, filters=admin_filter))
            self.app.add_handler(CommandHandler("ml", self._cmd_ml_retrain, filters=admin_filter))
            self.app.add_handler(CommandHandler("pause", self._cmd_pause, filters=admin_filter))
            self.app.add_handler(CommandHandler("resume", self._cmd_resume, filters=admin_filter))
            self.app.add_handler(CommandHandler("winrate", self._cmd_winrate, filters=admin_filter))
            self.app.add_handler(CommandHandler("testbanner", self._cmd_testbanner, filters=admin_filter))

            # Block all other users (unauthorized access attempts)
            self.app.add_handler(MessageHandler(~admin_filter, self._handle_unauthorized))

            logger.info(f"✅ Admin bot initialized")
            logger.info(f"   Commands registered: /help /stats /active /performance /winrate /health /cache /missed /whales /config /dataset /collect /ml /pause /resume /testbanner")
            logger.info(f"   Security: Only user {self.admin_user_id} can use commands")
            if self.admin_channel_id:
                logger.info(f"   Response mode: Admin channel ({self.admin_channel_id})")
            else:
                logger.info(f"   Response mode: Direct message (DM)")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize admin bot: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    async def start(self):
        """Start polling for commands"""
        if not self.app:
            logger.warning("⚠️ Admin bot not initialized")
            return

        try:
            logger.info("🤖 Admin bot starting polling...")

            # Initialize and start
            await self.app.initialize()
            await self.app.start()

            # Start polling (this will run in background)
            await self.app.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query"]
            )

            logger.info("✅ Admin bot polling started - send /help for commands")
            logger.info(f"   Authorized user ID: {self.admin_user_id}")

            # Keep running
            while True:
                await asyncio.sleep(3600)  # Check every hour

        except Exception as e:
            logger.error(f"❌ Admin bot error: {e}")
            import traceback
            logger.error(traceback.format_exc())

    async def stop(self):
        """Stop the admin bot"""
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            logger.info("🛑 Admin bot stopped")

    async def _send_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Send response either to admin channel or DM"""
        try:
            if self.admin_channel_id:
                # Post to admin channel
                await context.bot.send_message(
                    chat_id=self.admin_channel_id,
                    text=text,
                    parse_mode=ParseMode.HTML
                )
            else:
                # Reply in DM
                await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"❌ Error sending response: {e}")
            # Fallback to DM if channel post fails
            await update.message.reply_text(text, parse_mode=ParseMode.HTML)

    async def _get_current_price(self, token_address: str) -> Optional[float]:
        """Fetch current price from DexScreener"""
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        pairs = data.get('pairs', [])
                        if pairs:
                            # Get first pair with price
                            for pair in pairs:
                                price = pair.get('priceUsd')
                                if price:
                                    return float(price)
        except:
            pass
        return None

    async def _handle_unauthorized(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle unauthorized access attempts"""
        user = update.effective_user
        logger.warning(f"🚫 Unauthorized access attempt from {user.username or user.id}")
        # Silently ignore - don't reveal bot exists to unauthorized users

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show available commands"""
        help_text = """
🤖 <b>PROMETHEUS ADMIN COMMANDS</b>

<b>Performance:</b>
/stats - Overall system statistics
/performance - Recent signal performance
/winrate - KOL vs On-Chain win rate comparison
/missed - Tracked tokens not signaled (potential missed runners)

<b>Monitoring:</b>
/active - Currently tracked tokens
/health - System health check
/cache - Telegram calls cache status
/whales - Discovered whale wallets
/config - Live scoring config values

<b>Data &amp; ML:</b>
/dataset - ML training dataset stats
/collect - Run daily token collection now
/ml - Retrain ML model with latest data

<b>Control:</b>
/pause - Pause signal posting
/resume - Resume signal posting
/testbanner - Test banner animation in channel

<b>Help:</b>
/help - Show this message
"""
        await self._send_response(update, context, help_text)

    async def _cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show system statistics"""
        try:
            stats_text = "📊 <b>PROMETHEUS STATISTICS</b>\n\n"

            # Active tracker stats
            if self.active_tracker:
                active_count = self.active_tracker.get_active_count()
                total_tracked = self.active_tracker.tokens_tracked_total
                signals_sent = self.active_tracker.signals_sent_total

                stats_text += f"<b>Tracking:</b>\n"
                stats_text += f"• Active tokens: {active_count}\n"
                stats_text += f"• Total tracked: {total_tracked}\n"
                stats_text += f"• Signals sent: {signals_sent}\n\n"

            # Database stats
            if self.database:
                try:
                    total_signals = await self.database.get_total_signal_count()
                    recent_signals = await self.database.get_signals_in_last_hours(24)

                    stats_text += f"<b>Signals (24h):</b>\n"
                    stats_text += f"• Last 24h: {len(recent_signals)}\n"
                    stats_text += f"• All time: {total_signals}\n\n"
                except:
                    pass

            # Performance tracker stats
            if self.performance_tracker:
                try:
                    metrics = await self.performance_tracker.get_summary_metrics()
                    if metrics:
                        stats_text += f"<b>Performance:</b>\n"
                        stats_text += f"• Win rate: {metrics.get('win_rate', 0):.1f}%\n"
                        stats_text += f"• Avg gain: {metrics.get('avg_gain', 0):.1f}%\n"
                        stats_text += f"• Best gain: {metrics.get('best_gain', 0):.1f}%\n\n"
                except:
                    pass

            # Telegram cache
            if self.telegram_calls_cache:
                cache_size = len(self.telegram_calls_cache)
                stats_text += f"<b>Telegram Cache:</b>\n"
                stats_text += f"• Tokens called: {cache_size}\n\n"

            # Recent signals list
            if self.database:
                try:
                    recent_signals = await self.database.get_signals_in_last_hours(24)
                    if recent_signals:
                        stats_text += f"<b>Recent Signals (Last 24h):</b>\n"
                        for signal in recent_signals[:5]:  # Show last 5
                            symbol = signal.get('token_symbol', 'UNKNOWN')
                            score = signal.get('conviction_score', 0)
                            entry = signal.get('entry_price', 0)
                            timestamp = signal.get('created_at', '')

                            # Parse age
                            try:
                                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                age = datetime.utcnow().replace(tzinfo=dt.tzinfo) - dt
                                age_str = f"{age.total_seconds() / 3600:.1f}h ago"
                            except:
                                age_str = "unknown"

                            stats_text += f"• <b>${symbol}</b> ({score}/100) - ${entry:.8f} - {age_str}\n"

                        if len(recent_signals) > 5:
                            stats_text += f"<i>...and {len(recent_signals) - 5} more (use /performance for full list)</i>\n"
                except Exception as e:
                    logger.error(f"Error fetching recent signals: {e}")

            stats_text += f"\n⏰ <i>Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</i>"

            await self._send_response(update, context, stats_text)

        except Exception as e:
            logger.error(f"❌ Error in /stats: {e}")
            await update.message.reply_text(f"❌ Error getting stats: {str(e)}")

    async def _cmd_active(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show currently tracked tokens"""
        try:
            if not self.active_tracker:
                await self._send_response(update, context, "❌ Active tracker not available")
                return

            active_tokens = []
            for addr, state in self.active_tracker.tracked_tokens.items():
                symbol = state.token_data.get('token_symbol', 'UNKNOWN')
                score = state.conviction_score
                price = state.token_data.get('price_usd', 0)
                mcap = state.token_data.get('market_cap', 0)
                bonding = state.token_data.get('bonding_curve_pct', 0)
                age_minutes = (datetime.utcnow() - state.first_tracked_at).total_seconds() / 60

                active_tokens.append({
                    'symbol': symbol,
                    'score': score,
                    'price': price,
                    'mcap': mcap,
                    'bonding': bonding,
                    'age': age_minutes,
                    'sent': state.signal_sent,
                    'address': addr
                })

            if not active_tokens:
                await self._send_response(update, context, "ℹ️ No tokens currently tracked")
                return

            # Sort by conviction score
            active_tokens.sort(key=lambda x: x['score'], reverse=True)

            response = f"🎯 <b>ACTIVE TOKENS ({len(active_tokens)})</b>\n\n"

            for token in active_tokens[:10]:  # Show top 10
                status = "📤" if token['sent'] else "⏳"
                response += f"{status} <b>${token['symbol']}</b>\n"
                response += f"   Score: {token['score']}/100\n"
                response += f"   Price: ${token['price']:.8f}\n"
                response += f"   MCap: ${token['mcap']:,.0f}\n"
                response += f"   Bonding: {token['bonding']:.1f}%\n"
                response += f"   Age: {token['age']:.0f}m\n"
                response += f"   <code>{token['address'][:16]}...</code>\n\n"

            if len(active_tokens) > 10:
                response += f"<i>...and {len(active_tokens) - 10} more</i>"

            await self._send_response(update, context, response)

        except Exception as e:
            logger.error(f"❌ Error in /active: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await update.message.reply_text(f"❌ Error getting active tokens: {str(e)}")

    async def _cmd_performance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show recent signal performance with gains"""
        try:
            if not self.database:
                await self._send_response(update, context, "❌ Database not available")
                return

            # Get recent signals
            signals = await self.database.get_signals_in_last_hours(48)

            if not signals:
                await self._send_response(update, context, "ℹ️ No signals in last 48 hours")
                return

            response = f"📈 <b>RECENT PERFORMANCE</b>\n\n"
            response += f"Signals (48h): {len(signals)}\n"

            # Limit display to last 20 signals to avoid Telegram message length limit
            MAX_DISPLAY = 20
            signals_to_show = signals[:MAX_DISPLAY]

            if len(signals) > MAX_DISPLAY:
                response += f"<i>Showing {MAX_DISPLAY} most recent (+ {len(signals) - MAX_DISPLAY} older)</i>\n\n"
            else:
                response += "\n"

            wins = 0
            flat = 0
            losses = 0

            # Show limited signals with gains
            for signal in signals_to_show:
                symbol = signal.get('token_symbol', 'UNKNOWN')
                score = signal.get('conviction_score', 0)
                entry = signal.get('entry_price', 0)
                token_address = signal.get('token_address', '')
                timestamp = signal.get('created_at', '')

                # Parse age
                try:
                    if isinstance(timestamp, str):
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    else:
                        dt = timestamp
                    age = datetime.utcnow().replace(tzinfo=dt.tzinfo if dt.tzinfo else None) - dt
                    age_str = f"{age.total_seconds() / 3600:.1f}h"
                except:
                    age_str = "?"

                # Get peak from max_price_reached (tracked every price check),
                # fall back to milestone table for older signals
                peak_price = signal.get('max_price_reached')
                if peak_price and entry and entry > 0:
                    peak_multiple = peak_price / entry
                else:
                    peak_multiple = await self.database.get_highest_milestone(token_address) if token_address else None

                # Fetch current price
                current_price = await self._get_current_price(token_address) if token_address else None

                if entry and entry > 0:
                    # Determine win/loss based on PEAK, not current
                    # WIN = hit at least 2.0x (a real pump)
                    if peak_multiple and peak_multiple >= 2.0:
                        emoji = "🟢"
                        wins += 1
                        peak_str = f"{peak_multiple:.1f}x"
                    elif peak_multiple and peak_multiple >= 1.1:
                        # Marginal gain (1.1x-1.99x) - NOT a win
                        emoji = "🟡"
                        flat += 1
                        peak_pct = (peak_multiple - 1) * 100
                        peak_str = f"+{peak_pct:.0f}%"
                    else:
                        # Never pumped or rugged
                        emoji = "🔴"
                        losses += 1
                        if peak_multiple and peak_multiple > 0:
                            peak_pct = (peak_multiple - 1) * 100
                            peak_str = f"{peak_pct:+.0f}%"
                        else:
                            peak_str = "no data"

                    # Show Entry → Peak → Current
                    peak_display = f"{peak_multiple:.1f}x" if peak_multiple else "?"
                    if current_price:
                        current_mult = current_price / entry
                        if current_mult >= 2.0:
                            current_str = f"{current_mult:.1f}x"
                        else:
                            current_pct = (current_mult - 1) * 100
                            current_str = f"{current_pct:+.0f}%"

                        response += f"{emoji} <b>${symbol}</b> Peak: {peak_str}\n"
                        response += f"   Entry: ${entry:.8f}\n"
                        response += f"   Peak: {peak_display} | Now: {current_str}\n"
                        response += f"   Score: {score}/100 | {age_str} ago\n\n"
                    else:
                        # Dead token
                        response += f"{emoji} <b>${symbol}</b> Peak: {peak_str}\n"
                        response += f"   Entry: ${entry:.8f}\n"
                        response += f"   Peak: {peak_display} | Now: DEAD\n"
                        response += f"   Score: {score}/100 | {age_str} ago\n\n"
                else:
                    # Can't calculate
                    response += f"⚫ <b>${symbol}</b> (no data)\n"
                    response += f"   Score: {score}/100 | {age_str} ago\n\n"
                    losses += 1

            # Add summary (based on displayed signals only)
            total = wins + flat + losses
            if total > 0:
                win_rate = (wins / total) * 100
                response += f"📊 <b>Win Rate: {win_rate:.0f}%</b> ({wins}W / {flat}F / {losses}L)\n"
                response += f"<i>W=2x+ | F=flat | L=loss — {total} signals shown</i>"

            await self._send_response(update, context, response)

        except Exception as e:
            logger.error(f"❌ Error in /performance: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await self._send_response(update, context, f"❌ Error getting performance: {str(e)}")

    async def _cmd_health(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show system health"""
        try:
            health = "🏥 <b>SYSTEM HEALTH</b>\n\n"

            # Active tracker
            if self.active_tracker:
                health += "✅ Active Tracker: Running\n"
                health += f"   • {self.active_tracker.get_active_count()} tokens tracked\n"
            else:
                health += "❌ Active Tracker: Not available\n"

            # Database
            if self.database:
                try:
                    # Test database connection
                    await self.database.get_total_signal_count()
                    health += "✅ Database: Connected\n"
                except Exception as e:
                    health += f"⚠️ Database: Error ({str(e)[:30]}...)\n"
            else:
                health += "❌ Database: Not available\n"

            # Performance tracker
            if self.performance_tracker:
                health += "✅ Performance Tracker: Running\n"
            else:
                health += "⚠️ Performance Tracker: Not available\n"

            # Telegram cache
            if self.telegram_calls_cache is not None:
                cache_size = len(self.telegram_calls_cache)
                health += f"✅ Telegram Cache: Active ({cache_size} tokens)\n"
            else:
                health += "⚠️ Telegram Cache: Not available\n"

            health += f"\n⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"

            await self._send_response(update, context, health)

        except Exception as e:
            logger.error(f"❌ Error in /health: {e}")
            await update.message.reply_text(f"❌ Error checking health: {str(e)}")

    async def _cmd_cache(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show Telegram calls cache status"""
        try:
            if self.telegram_calls_cache is None:
                await self._send_response(update, context, "❌ Telegram cache not available")
                return

            if not self.telegram_calls_cache:
                await self._send_response(update, context, "ℹ️ Telegram cache is empty - no calls detected yet")
                return

            response = f"📱 <b>TELEGRAM CALLS CACHE</b>\n\n"
            response += f"Total tokens called: {len(self.telegram_calls_cache)}\n\n"

            # Show recent calls (last 10)
            recent_calls = []
            for token_addr, call_data in self.telegram_calls_cache.items():
                mention_count = len(call_data.get('mentions', []))
                group_count = len(call_data.get('groups', set()))
                first_seen = call_data.get('first_seen', datetime.utcnow())

                # Calculate age
                age = datetime.utcnow() - first_seen
                age_minutes = age.total_seconds() / 60

                recent_calls.append({
                    'address': token_addr,
                    'mentions': mention_count,
                    'groups': group_count,
                    'age': age_minutes,
                    'first_seen': first_seen
                })

            # Sort by most recent first
            recent_calls.sort(key=lambda x: x['first_seen'], reverse=True)

            for call in recent_calls[:10]:
                response += f"<code>{call['address'][:16]}...</code>\n"
                response += f"   {call['mentions']} mention(s) from {call['groups']} group(s)\n"
                response += f"   {call['age']:.0f}m ago\n\n"

            if len(recent_calls) > 10:
                response += f"<i>...and {len(recent_calls) - 10} more</i>"

            await self._send_response(update, context, response)

        except Exception as e:
            logger.error(f"❌ Error in /cache: {e}")
            await update.message.reply_text(f"❌ Error getting cache: {str(e)}")

    async def _cmd_missed(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show tracked tokens that weren't signaled - potential missed runners"""
        try:
            if not self.active_tracker:
                await self._send_response(update, context, "❌ Active tracker not available")
                return

            missed = []
            for addr, state in self.active_tracker.tracked_tokens.items():
                if state.signal_sent:
                    continue  # Already signaled, not missed

                symbol = state.token_data.get('token_symbol', 'UNKNOWN')
                score = state.conviction_score
                entry_price = state.token_data.get('price_usd', 0)
                mcap = state.token_data.get('market_cap', 0)
                age_minutes = (datetime.utcnow() - state.first_tracked_at).total_seconds() / 60

                # Fetch current price to see if it ran
                current_price = await self._get_current_price(addr)
                if current_price and entry_price and entry_price > 0:
                    multiple = current_price / entry_price
                else:
                    multiple = 0

                missed.append({
                    'symbol': symbol,
                    'score': score,
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'multiple': multiple,
                    'mcap': mcap,
                    'age': age_minutes,
                    'address': addr,
                })

            if not missed:
                await self._send_response(update, context,
                    "ℹ️ No unsignaled tokens currently tracked.\n\n"
                    "All active tokens either already got signaled or none are being tracked.")
                return

            # Sort by price multiple (biggest runners first)
            missed.sort(key=lambda x: x['multiple'], reverse=True)

            response = f"👀 <b>UNSIGNALED TOKENS ({len(missed)})</b>\n\n"

            runners = [t for t in missed if t['multiple'] >= 2.0]
            if runners:
                response += f"🚨 <b>{len(runners)} potential missed runner(s):</b>\n\n"

            for token in missed[:15]:
                if token['multiple'] >= 5.0:
                    emoji = "🔥"
                elif token['multiple'] >= 2.0:
                    emoji = "🚨"
                elif token['multiple'] >= 1.5:
                    emoji = "⚠️"
                else:
                    emoji = "⏳"

                if token['multiple'] > 0:
                    mult_str = f"{token['multiple']:.1f}x" if token['multiple'] >= 2 else f"+{(token['multiple']-1)*100:.0f}%"
                else:
                    mult_str = "?"

                response += f"{emoji} <b>${token['symbol']}</b> — {mult_str} since tracking\n"
                response += f"   Score: {token['score']}/100 | MCap: ${token['mcap']:,.0f}\n"
                response += f"   Tracked: {token['age']:.0f}m ago\n"
                response += f"   <code>{token['address'][:16]}...</code>\n\n"

            if len(missed) > 15:
                response += f"<i>...and {len(missed) - 15} more</i>\n"

            response += f"\n⏰ <i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</i>"
            await self._send_response(update, context, response)

        except Exception as e:
            logger.error(f"❌ Error in /missed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _cmd_whales(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show discovered whale wallets"""
        try:
            whales = []

            # Try database first
            if self.database:
                try:
                    whales = await self.database.get_all_successful_whales(min_win_rate=0.0)
                except Exception as e:
                    logger.debug(f"Whale DB query failed: {e}")

            # Fallback to JSON file
            if not whales:
                whale_file = 'data/successful_whale_wallets.json'
                if os.path.exists(whale_file):
                    with open(whale_file, 'r') as f:
                        data = json.load(f)
                    whales = data.get('whales', [])

            if not whales:
                await self._send_response(update, context,
                    "ℹ️ <b>No whale wallets discovered yet.</b>\n\n"
                    "Whales are discovered during /collect runs.\n"
                    "Run daily collections to build up whale data.")
                return

            response = f"🐋 <b>WHALE WALLETS ({len(whales)})</b>\n\n"

            for whale in whales[:15]:
                addr = whale.get('wallet_address', whale.get('address', '?'))
                win_rate = whale.get('win_rate', 0)
                tokens = whale.get('tokens_bought_count', 0)
                wins = whale.get('wins', 0)
                early = whale.get('is_early_whale', False)

                # Win rate color
                if win_rate >= 0.7:
                    emoji = "🟢"
                elif win_rate >= 0.5:
                    emoji = "🟡"
                else:
                    emoji = "🔴"

                early_tag = " [EARLY]" if early else ""

                response += f"{emoji} <code>{addr[:16]}...</code>{early_tag}\n"
                response += f"   WR: {win_rate*100:.0f}% | Tokens: {tokens} | Wins: {wins}\n\n"

            if len(whales) > 15:
                response += f"<i>...and {len(whales) - 15} more</i>\n"

            response += f"\n⏰ <i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</i>"
            await self._send_response(update, context, response)

        except Exception as e:
            logger.error(f"❌ Error in /whales: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _cmd_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show live scoring configuration"""
        try:
            paused = self.active_tracker.signal_posting_paused if self.active_tracker else False
            paused_str = "⏸️ PAUSED" if paused else "▶️ Active"

            response = "⚙️ <b>LIVE CONFIGURATION</b>\n\n"

            response += f"<b>Signal Posting:</b> {paused_str}\n\n"

            response += "<b>Conviction Thresholds:</b>\n"
            response += f"  • Pre-grad signal: {config.MIN_CONVICTION_SCORE}/100\n"
            response += f"  • Post-grad signal: {config.POST_GRAD_THRESHOLD}/100\n"
            response += f"  • Distribution check: {config.DISTRIBUTION_CHECK_THRESHOLD}+\n\n"

            response += "<b>Safety Filters:</b>\n"
            response += f"  • Min holders: {config.MIN_HOLDERS}\n"
            response += f"  • Min unique buyers: {config.MIN_UNIQUE_BUYERS}\n"
            response += f"  • Min liquidity: ${config.MIN_LIQUIDITY:,}\n\n"

            response += "<b>Polling:</b>\n"
            response += f"  • Tiered polling: {'ON' if config.DISABLE_POLLING_BELOW_THRESHOLD else 'OFF'}\n"
            response += f"  • Pre-grad: always 30s\n"
            response += f"  • Post-grad (score ≥20): 30s\n"
            response += f"  • Post-grad (score 0-19): 90s\n"
            response += f"  • Post-grad (score <0): skipped\n\n"

            response += "<b>Rug Detection:</b>\n"
            rug = config.RUG_DETECTION
            response += f"  • Enabled: {'YES' if rug.get('enabled') else 'NO'}\n"
            bundle_penalties = rug.get('bundles', {}).get('penalties', {})
            response += f"  • Bundle penalty: {bundle_penalties.get('minor', 0)}/{bundle_penalties.get('medium', 0)}/{bundle_penalties.get('massive', 0)}\n\n"

            response += "<b>Discovery Mode:</b>\n"
            if not config.STRICT_KOL_ONLY_MODE:
                scanner = config.ORGANIC_SCANNER
                response += f"  • Mode: 🔬 ORGANIC SCANNER\n"
                response += f"  • Min buyers: {scanner.get('min_unique_buyers', 50)}\n"
                response += f"  • Min buy ratio: {scanner.get('min_buy_ratio', 0.65):.0%}\n"
                response += f"  • Bonding range: {scanner.get('min_bonding_pct', 30)}-{scanner.get('max_bonding_pct', 85)}%\n"
                response += f"  • KOL scoring: DISABLED\n\n"
            else:
                response += f"  • Mode: 👑 KOL-TRIGGERED\n"
                response += f"  • KOL scoring: ACTIVE (0-{config.SMART_WALLET_WEIGHTS.get('max_score', 40)} pts)\n\n"

            response += "<b>Features:</b>\n"
            response += f"  • Narratives: {'ON' if getattr(config, 'ENABLE_NARRATIVES', False) else 'OFF'} (max 10 pts)\n"
            response += f"  • Telegram posting: {'ON' if config.ENABLE_TELEGRAM else 'OFF'}\n"
            response += f"  • PumpPortal: {'OFF' if config.DISABLE_PUMPPORTAL else 'ON'}\n"

            response += f"\n⏰ <i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</i>"
            await self._send_response(update, context, response)

        except Exception as e:
            logger.error(f"❌ Error in /config: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _cmd_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Pause signal posting"""
        try:
            if not self.active_tracker:
                await self._send_response(update, context, "❌ Active tracker not available")
                return

            self.active_tracker.signal_posting_paused = True
            logger.info("⏸️ Signal posting PAUSED by admin")
            await self._send_response(update, context,
                "⏸️ <b>Signal posting PAUSED</b>\n\n"
                "Tokens are still being tracked and scored,\n"
                "but no signals will be posted to the channel.\n\n"
                "Use /resume to re-enable posting.")

        except Exception as e:
            logger.error(f"❌ Error in /pause: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Resume signal posting"""
        try:
            if not self.active_tracker:
                await self._send_response(update, context, "❌ Active tracker not available")
                return

            self.active_tracker.signal_posting_paused = False
            logger.info("▶️ Signal posting RESUMED by admin")
            await self._send_response(update, context,
                "▶️ <b>Signal posting RESUMED</b>\n\n"
                "Signals will now be posted to the channel when\n"
                "tokens meet conviction thresholds.")

        except Exception as e:
            logger.error(f"❌ Error in /resume: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _cmd_dataset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show ML training dataset statistics"""
        try:
            data_file = 'data/historical_training_data.json'
            whale_file = 'data/successful_whale_wallets.json'

            if not os.path.exists(data_file):
                await self._send_response(update, context,
                    "ℹ️ <b>No dataset yet.</b>\n\n"
                    "Run /collect to start building training data.")
                return

            with open(data_file, 'r') as f:
                data = json.load(f)

            total = data.get('total_tokens', 0)
            last_collection = data.get('last_daily_collection', data.get('last_backfill', 'never'))
            collected_today = data.get('tokens_collected_today', data.get('tokens_added_this_run', 0))
            outcome_dist = data.get('outcome_distribution', {})
            discovery_method = data.get('discovery_method', 'dexscreener')

            # ML readiness
            ml_threshold = 200
            progress_pct = min(100, (total / ml_threshold) * 100)
            tokens_needed = max(0, ml_threshold - total)
            bar_filled = int(progress_pct / 5)  # 20 char bar
            bar = "█" * bar_filled + "░" * (20 - bar_filled)

            source_label = "Helius + DexScreener" if 'helius' in discovery_method else "DexScreener"

            response = "📊 <b>ML TRAINING DATASET</b>\n\n"
            response += f"<b>Tokens:</b> {total}\n"
            response += f"<b>Source:</b> {source_label}\n"
            response += f"<b>Last collection:</b> {last_collection}\n"
            response += f"<b>Added last run:</b> {collected_today}\n\n"

            # Outcome breakdown
            if outcome_dist:
                response += "<b>Outcome Distribution:</b>\n"
                for outcome, count in sorted(outcome_dist.items(), key=lambda x: x[1], reverse=True):
                    response += f"  • {outcome}: {count}\n"
                response += "\n"

            # ML readiness bar
            response += f"<b>ML Training Ready:</b>\n"
            response += f"  [{bar}] {progress_pct:.0f}%\n"
            if tokens_needed > 0:
                response += f"  Need {tokens_needed} more tokens ({tokens_needed // 50} daily collections)\n"
            else:
                response += f"  ✅ Ready! Run /ml to train\n"

            # Whale stats
            if os.path.exists(whale_file):
                try:
                    with open(whale_file, 'r') as f:
                        whale_data = json.load(f)
                    whale_count = whale_data.get('total_whales', 0)
                    response += f"\n<b>Whale Wallets:</b> {whale_count} tracked"
                except Exception:
                    pass

            response += f"\n\n⏰ <i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</i>"

            await self._send_response(update, context, response)

        except Exception as e:
            logger.error(f"❌ Error in /dataset: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _cmd_collect(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manually trigger Helius backfill token collection"""
        try:
            await self._send_response(update, context,
                "📅 <b>Starting Helius backfill collection...</b>\n\n"
                "Discovering pump.fun tokens via Helius searchAssets,\n"
                "collecting 30+ ML features per token (DexScreener + Helius),\n"
                "and building ML training data.\n\n"
                "This may take a few minutes. Check Railway logs for progress.")

            # Run in background so the bot stays responsive
            asyncio.create_task(self._run_collect_background(update, context))

        except Exception as e:
            logger.error(f"❌ Error in /collect: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _run_collect_background(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Run Helius backfill collection in background and report result"""
        try:
            from tools.helius_backfill_collector import HeliusBackfillCollector

            collector = HeliusBackfillCollector(database=self.database)
            await collector.run()

            # Report results
            stats = collector.stats
            enriched = stats.get('enriched', 0)
            discovered = stats.get('discovered', 0)
            no_dex = stats.get('skipped_no_dex', 0)
            filtered = stats.get('skipped_filters', 0)
            existing = stats.get('skipped_existing', 0)
            credits = stats.get('credits_used_estimate', 0)

            # Get total dataset size (from DB first, then file fallback)
            total = 0
            try:
                if self.database:
                    total = await self.database.get_training_token_count()
                if total == 0:
                    import json
                    with open('data/historical_training_data.json', 'r') as f:
                        data = json.load(f)
                        total = data.get('total_tokens', 0)
            except Exception:
                pass

            await self._send_response(update, context,
                f"✅ <b>Helius backfill complete!</b>\n\n"
                f"<b>Discovered:</b> {discovered} tokens\n"
                f"<b>Added:</b> +{enriched} new tokens\n"
                f"<b>Skipped:</b> {existing} existing, {no_dex} no DEX pair, {filtered} filtered\n"
                f"<b>Dataset total:</b> {total} tokens\n"
                f"<b>Credits used:</b> ~{credits}\n\n"
                f"{'✅ Ready for ML training!' if total >= 200 else f'Need {200 - total} more tokens for ML training.'}")
        except Exception as e:
            logger.error(f"❌ Background collection failed: {e}")
            await self._send_response(update, context, f"❌ Collection failed: {str(e)}")

    async def _cmd_ml_retrain(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manually trigger ML model retraining"""
        try:
            await self._send_response(update, context,
                "🎓 <b>Starting ML retraining...</b>\n\n"
                "This retrains the signal prediction model using\n"
                "the latest collected token data.\n\n"
                "This may take a few minutes. Check Railway logs for progress.")

            asyncio.create_task(self._run_ml_background(update, context))

        except Exception as e:
            logger.error(f"❌ Error in /ml: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _run_ml_background(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Run ML retraining in background and report result"""
        try:
            from tools.automated_ml_retrain import AutomatedMLRetrainer
            retrainer = AutomatedMLRetrainer()
            result = await retrainer.run()

            if not result or result.get('action') == 'skipped':
                reason = result.get('reason', 'Unknown') if result else 'No result'
                total = result.get('total_tokens', 0) if result else 0
                required = result.get('required', 200) if result else 200
                await self._send_response(update, context,
                    f"⏭️ <b>ML training skipped</b>\n\n"
                    f"Reason: {reason}\n\n"
                    f"Dataset: {total}/{required} tokens\n"
                    f"Run /collect daily to build up training data.\n"
                    f"Use /dataset to check progress.")
            elif result.get('action') == 'failed':
                await self._send_response(update, context,
                    f"❌ <b>ML training failed</b>\n\n"
                    f"Reason: {result.get('reason', 'Unknown')}\n"
                    f"Check Railway logs for details.")
            else:
                await self._send_response(update, context,
                    f"✅ <b>ML model trained!</b>\n\n"
                    f"Features: {result.get('feature_count', '?')}\n"
                    f"Model deployed and active for scoring.")
        except Exception as e:
            logger.error(f"❌ ML retraining failed: {e}")
            await self._send_response(update, context, f"❌ ML retraining failed: {str(e)}")

    async def _cmd_winrate(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Compare win rates: KOL-based era vs On-Chain-first era"""
        try:
            if not self.database or not self.database.pool:
                await self._send_response(update, context, "❌ Database not available")
                return

            # On-chain-first scoring deployed ~2026-01-27 06:17 UTC (PR #131 merge)
            TRANSITION = datetime(2026, 1, 27, 6, 17, 0)

            async with self.database.pool.acquire() as conn:
                # --- ERA COMPARISON ---
                era_stats = await conn.fetch("""
                    SELECT
                        CASE WHEN created_at < $1 THEN 'KOL' ELSE 'ON-CHAIN' END as era,
                        COUNT(*) as total,
                        SUM(CASE WHEN outcome IN ('2x','5x','10x','50x','100x') THEN 1 ELSE 0 END) as wins,
                        SUM(CASE WHEN outcome = 'rug' THEN 1 ELSE 0 END) as rugs,
                        SUM(CASE WHEN outcome = 'loss' THEN 1 ELSE 0 END) as losses,
                        SUM(CASE WHEN outcome IS NULL THEN 1 ELSE 0 END) as pending,
                        ROUND(AVG(CASE WHEN max_roi IS NOT NULL THEN max_roi END)::numeric, 2) as avg_roi,
                        ROUND(MAX(CASE WHEN max_roi IS NOT NULL THEN max_roi END)::numeric, 1) as best_roi,
                        ROUND(AVG(conviction_score)::numeric, 0) as avg_score
                    FROM signals
                    WHERE signal_posted = TRUE
                    GROUP BY era
                    ORDER BY era
                """, TRANSITION)

                # --- BY SIGNAL SOURCE ---
                source_stats = await conn.fetch("""
                    SELECT
                        COALESCE(signal_source, 'unknown') as source,
                        COUNT(*) as total,
                        SUM(CASE WHEN outcome IN ('2x','5x','10x','50x','100x') THEN 1 ELSE 0 END) as wins,
                        SUM(CASE WHEN outcome = 'rug' THEN 1 ELSE 0 END) as rugs,
                        SUM(CASE WHEN outcome IS NULL THEN 1 ELSE 0 END) as pending,
                        ROUND(AVG(CASE WHEN max_roi IS NOT NULL THEN max_roi END)::numeric, 2) as avg_roi
                    FROM signals
                    WHERE signal_posted = TRUE
                    GROUP BY source
                    ORDER BY total DESC
                """)

                # --- DAILY TREND (last 7 days) ---
                daily = await conn.fetch("""
                    SELECT
                        DATE(created_at) as day,
                        COUNT(*) as total,
                        SUM(CASE WHEN outcome IN ('2x','5x','10x','50x','100x') THEN 1 ELSE 0 END) as wins,
                        SUM(CASE WHEN outcome = 'rug' THEN 1 ELSE 0 END) as rugs,
                        SUM(CASE WHEN outcome IS NULL THEN 1 ELSE 0 END) as pending
                    FROM signals
                    WHERE signal_posted = TRUE
                      AND created_at >= NOW() - INTERVAL '7 days'
                    GROUP BY day
                    ORDER BY day DESC
                """)

                # --- OUTCOME DISTRIBUTION (all time) ---
                outcomes = await conn.fetch("""
                    SELECT
                        COALESCE(outcome, 'pending') as outcome,
                        COUNT(*) as cnt
                    FROM signals
                    WHERE signal_posted = TRUE
                    GROUP BY outcome
                    ORDER BY cnt DESC
                """)

            # Build response
            r = "📊 <b>WIN RATE: KOL vs ON-CHAIN</b>\n\n"

            # Era comparison
            for row in era_stats:
                era = row['era']
                decided = row['total'] - row['pending']
                wr = (row['wins'] / decided * 100) if decided > 0 else 0
                rr = (row['rugs'] / decided * 100) if decided > 0 else 0
                emoji = "🟢" if wr >= 40 else "🟡" if wr >= 25 else "🔴"

                r += f"<b>{'👔 KOL ERA' if era == 'KOL' else '⛓ ON-CHAIN ERA'}</b>\n"
                r += f"{emoji} Win Rate: <b>{wr:.0f}%</b> ({row['wins']}W / {row['losses']}L / {row['rugs']}R)\n"
                r += f"   Signals: {row['total']} ({row['pending']} pending)\n"
                r += f"   Avg ROI: {row['avg_roi'] or 0}x | Best: {row['best_roi'] or 0}x\n"
                r += f"   Avg Score: {row['avg_score'] or 0}/100\n"
                if row['pending'] > 0 and decided == 0:
                    r += f"   ⏳ All signals still pending outcome\n"
                r += "\n"

            # Signal source breakdown
            r += "<b>📡 BY SOURCE</b>\n"
            for row in source_stats:
                decided = row['total'] - row['pending']
                wr = (row['wins'] / decided * 100) if decided > 0 else 0
                src = row['source'][:15]
                r += f"• {src}: {wr:.0f}% WR ({row['wins']}W/{row['rugs']}R of {decided}d) avg {row['avg_roi'] or 0}x\n"
            r += "\n"

            # Daily trend
            r += "<b>📅 DAILY TREND</b>\n"
            for row in daily:
                decided = row['total'] - row['pending']
                wr = (row['wins'] / decided * 100) if decided > 0 else 0
                day_str = row['day'].strftime('%m/%d')
                bar = "🟢" * row['wins'] + "🔴" * row['rugs']
                marker = " ⛓" if row['day'].strftime('%Y-%m-%d') >= '2026-01-27' else ""
                r += f"{day_str}: {wr:.0f}% ({row['total']}sig, {row['pending']}pend) {bar}{marker}\n"

            # Outcome distribution
            r += "\n<b>🎯 ALL-TIME OUTCOMES</b>\n"
            for row in outcomes:
                oc = row['outcome']
                cnt = row['cnt']
                emoji_map = {'100x': '💎', '50x': '🚀', '10x': '🔥', '5x': '✅', '2x': '🟢',
                             'loss': '🔴', 'rug': '💀', 'pending': '⏳'}
                em = emoji_map.get(oc, '•')
                r += f"{em} {oc}: {cnt}\n"

            r += f"\n<i>⛓ = on-chain era | Transition: Jan 27 06:17 UTC</i>"

            await self._send_response(update, context, r)

        except Exception as e:
            logger.error(f"❌ Error in /winrate: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await self._send_response(update, context, f"❌ Error: {str(e)}")

    async def _cmd_testbanner(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Test banner animation/video in channel"""
        try:
            from telegram.error import TelegramError

            file_id = config.TELEGRAM_BANNER_FILE_ID
            channel_id = config.TELEGRAM_CHANNEL_ID

            if not file_id:
                await self._send_response(update, context,
                    "❌ No banner configured.\n"
                    "Set <code>TELEGRAM_BANNER_FILE_ID</code> env var.")
                return

            if not channel_id:
                await self._send_response(update, context, "❌ TELEGRAM_CHANNEL_ID not set.")
                return

            await self._send_response(update, context,
                f"🎬 Testing banner...\n"
                f"File ID: <code>{file_id[:30]}...</code>\n"
                f"Channel: <code>{channel_id}</code>")

            # Step 1: Validate file_id
            try:
                file_info = await context.bot.get_file(file_id)
                size_kb = file_info.file_size / 1024 if file_info.file_size else 0
                await self._send_response(update, context,
                    f"✅ File ID valid ({size_kb:.0f} KB)\n"
                    f"Path: <code>{file_info.file_path}</code>")
            except TelegramError as e:
                await self._send_response(update, context,
                    f"❌ File ID INVALID: {e}\n\n"
                    f"You need to re-upload the banner MP4/GIF.\n"
                    f"Send the file to the bot, then set the new file_id.")
                return

            # Step 2: Try send_animation (for GIFs and short MP4s)
            sent_msg = None
            method_used = None
            try:
                sent_msg = await context.bot.send_animation(
                    chat_id=channel_id,
                    animation=file_id,
                    caption="🎬 Banner test (send_animation) — auto-deleting...",
                )
                method_used = "send_animation"
            except TelegramError as e1:
                await self._send_response(update, context,
                    f"⚠️ send_animation failed: {e1}\nTrying send_video...")

                # Step 3: Try send_video
                try:
                    sent_msg = await context.bot.send_video(
                        chat_id=channel_id,
                        video=file_id,
                        caption="🎬 Banner test (send_video) — auto-deleting...",
                    )
                    method_used = "send_video"
                except TelegramError as e2:
                    await self._send_response(update, context,
                        f"❌ send_video also failed: {e2}\n\n"
                        f"Both methods failed. The file may not be a valid animation/video.\n"
                        f"Try re-uploading as MP4 (H.264, under 50MB).")
                    return

            # Clean up test message
            if sent_msg:
                await asyncio.sleep(3)
                try:
                    await context.bot.delete_message(
                        chat_id=channel_id,
                        message_id=sent_msg.message_id
                    )
                except TelegramError:
                    pass

                await self._send_response(update, context,
                    f"✅ Banner works!\n"
                    f"Method: <code>{method_used}</code>\n"
                    f"Message sent and auto-deleted from channel.")

        except Exception as e:
            logger.error(f"❌ Error in /testbanner: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await self._send_response(update, context, f"❌ Error: {str(e)}")
