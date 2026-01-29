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
        self.pending_media_type = None  # Tracks what type of media is expected next (banner, 2x, 10x, etc.)

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
            self.app.add_handler(CommandHandler("setmultiplier", self._cmd_setmultiplier, filters=admin_filter))
            self.app.add_handler(CommandHandler("testmultiplier", self._cmd_testmultiplier, filters=admin_filter))
            self.app.add_handler(CommandHandler("setbanner", self._cmd_setbanner, filters=admin_filter))

            # Wallet management commands
            self.app.add_handler(CommandHandler("wallets", self._cmd_wallets, filters=admin_filter))
            self.app.add_handler(CommandHandler("addwallet", self._cmd_addwallet, filters=admin_filter))
            self.app.add_handler(CommandHandler("removewallet", self._cmd_removewallet, filters=admin_filter))
            self.app.add_handler(CommandHandler("renamewallet", self._cmd_renamewallet, filters=admin_filter))
            self.app.add_handler(CommandHandler("syncwebhook", self._cmd_syncwebhook, filters=admin_filter))
            self.app.add_handler(CommandHandler("listwebhooks", self._cmd_listwebhooks, filters=admin_filter))
            self.app.add_handler(CommandHandler("clearwebhooks", self._cmd_clearwebhooks, filters=admin_filter))
            self.app.add_handler(CommandHandler("clearwebhooksdb", self._cmd_clearwebhooks_db, filters=admin_filter))
            self.app.add_handler(CommandHandler("countwallets", self._cmd_countwallets, filters=admin_filter))

            # Handle media uploads from admin (for banner file_id capture)
            self.app.add_handler(MessageHandler(
                admin_filter & (filters.VIDEO | filters.ANIMATION | filters.Document.VIDEO),
                self._handle_media_upload
            ))

            # Block all other users (unauthorized access attempts)
            self.app.add_handler(MessageHandler(~admin_filter, self._handle_unauthorized))

            logger.info(f"✅ Admin bot initialized")
            logger.info(f"   Commands registered: /help /stats /active /performance /winrate /health /cache /missed /whales /config /dataset /collect /ml /pause /resume /testbanner /wallets /addwallet /removewallet /renamewallet")
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

<b>Wallet Management:</b>
/wallets - View all tracked wallets
/addwallet &lt;name&gt; &lt;address&gt; - Add wallet to tracking
/removewallet &lt;address&gt; - Remove wallet from tracking
/renamewallet &lt;address&gt; &lt;name&gt; - Rename a wallet
/syncwebhook - Sync all wallets to Helius webhook
/listwebhooks - Show all registered Helius webhooks
/clearwebhooks - Delete all wallet webhooks (fresh start)
/countwallets - Debug wallet counts (DB vs Helius)

<b>Data &amp; ML:</b>
/dataset - ML training dataset stats
/collect - Run daily token collection now
/ml - Retrain ML model with latest data

<b>Control:</b>
/pause - Pause signal posting
/resume - Resume signal posting
/testbanner - Test signal banner in channel
/setbanner - Set new signal banner (send video)

<b>Multiplier Animations:</b>
/setmultiplier &lt;tier&gt; - Set animation (2x/10x/100x/1000x)
/testmultiplier &lt;tier&gt; - Test multiplier animation

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

            # Primary: Load from database (persists across Railway deploys)
            db_count = 0
            if self.database:
                try:
                    db_count = await self.database.get_training_token_count()
                except Exception:
                    pass

            # Fallback: Load from file
            file_data = {}
            try:
                with open(data_file, 'r') as f:
                    file_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                pass

            file_count = file_data.get('total_tokens', 0)

            # Use whichever source has more data
            if db_count == 0 and file_count == 0:
                await self._send_response(update, context,
                    "ℹ️ <b>No dataset yet.</b>\n\n"
                    "Run /collect to start building training data.")
                return

            # Prefer DB count if higher (file may be stale after Railway deploy)
            data = file_data

            # Use DB count if it's higher than file (file resets on Railway deploy)
            total = max(db_count, file_data.get('total_tokens', 0))
            data_source = "DB" if db_count >= file_count else "file"

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
            response += f"<b>Tokens:</b> {total} ({data_source})\n"
            if db_count != file_count:
                response += f"<b>DB/File:</b> {db_count}/{file_count}\n"
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

    async def _cmd_setbanner(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set the signal banner: /setbanner (then send video)"""
        self.pending_media_type = 'banner'
        await self._send_response(update, context,
            "🎬 <b>Banner Setup Mode</b>\n\n"
            "Send me the video/animation you want to use as the signal banner.\n\n"
            "Supported: MP4 videos, GIFs, animations")

    async def _cmd_setmultiplier(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set multiplier animations: /setmultiplier <tier>"""
        args = context.args
        valid_tiers = ['2x', '10x', '100x', '1000x']

        if not args or args[0].lower() not in valid_tiers:
            # Show current config
            current = {
                '2x': getattr(config, 'MILESTONE_BANNER_2X', None),
                '10x': getattr(config, 'MILESTONE_BANNER_10X', None),
                '100x': getattr(config, 'MILESTONE_BANNER_100X', None),
                '1000x': getattr(config, 'MILESTONE_BANNER_1000X', None),
            }

            response = "🎯 <b>Multiplier Animations</b>\n\n"
            for tier, val in current.items():
                status = "✅" if val else "❌"
                response += f"{status} <b>{tier}</b>: {'Set' if val else 'Not set'}\n"

            response += "\n<b>Usage:</b>\n"
            response += "<code>/setmultiplier 2x</code> - then send video\n"
            response += "<code>/setmultiplier 10x</code> - then send video\n"
            response += "<code>/setmultiplier 100x</code> - then send video\n"
            response += "<code>/setmultiplier 1000x</code> - then send video"

            await self._send_response(update, context, response)
            return

        tier = args[0].lower()
        self.pending_media_type = f'multiplier_{tier}'

        tier_names = {
            '2x': '🔥 LET IT BURN (2-5x)',
            '10x': '☄️ HELL FIRE (10-50x)',
            '100x': '🌋 SCORCHED EARTH (100-500x)',
            '1000x': '💀 INFERNO (1000x+)'
        }

        await self._send_response(update, context,
            f"🎯 <b>{tier_names.get(tier, tier)} Animation Setup</b>\n\n"
            f"Send me the video/animation for the <b>{tier}</b> milestone alerts.\n\n"
            f"Supported: MP4 videos, GIFs, animations")

    async def _cmd_testmultiplier(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Test multiplier animations: /testmultiplier <tier>"""
        args = context.args
        valid_tiers = ['2x', '10x', '100x', '1000x']

        if not args or args[0].lower() not in valid_tiers:
            # Show usage
            await self._send_response(update, context,
                "🎯 <b>Test Multiplier Animations</b>\n\n"
                "<b>Usage:</b>\n"
                "<code>/testmultiplier 2x</code>\n"
                "<code>/testmultiplier 10x</code>\n"
                "<code>/testmultiplier 100x</code>\n"
                "<code>/testmultiplier 1000x</code>\n\n"
                "This will post the animation to the channel for testing.")
            return

        tier = args[0].lower()

        # Get the file_id for this tier
        tier_config = {
            '2x': (getattr(config, 'MILESTONE_BANNER_2X', None), '🔥 LET IT BURN', '2-5x'),
            '10x': (getattr(config, 'MILESTONE_BANNER_10X', None), '☄️ HELL FIRE', '10-50x'),
            '100x': (getattr(config, 'MILESTONE_BANNER_100X', None), '🌋 SCORCHED EARTH', '100-500x'),
            '1000x': (getattr(config, 'MILESTONE_BANNER_1000X', None), '💀 INFERNO', '1000x+'),
        }

        file_id, title, range_text = tier_config.get(tier, (None, tier, tier))

        if not file_id:
            await self._send_response(update, context,
                f"❌ No animation set for <b>{tier}</b> tier.\n\n"
                f"Set it with: <code>/setmultiplier {tier}</code>")
            return

        try:
            # Create test message
            test_caption = (
                f"<b>{title}</b>\n\n"
                f"🧪 <b>TEST ALERT</b> 🧪\n\n"
                f"This is what the <b>{tier}</b> milestone alert will look like.\n"
                f"Range: {range_text}\n\n"
                f"<i>Test by admin</i>"
            )

            # Try to send to channel
            channel_id = config.TELEGRAM_CHANNEL_ID
            if channel_id:
                await context.bot.send_animation(
                    chat_id=channel_id,
                    animation=file_id,
                    caption=test_caption,
                    parse_mode='HTML'
                )
                await self._send_response(update, context,
                    f"✅ <b>{tier}</b> animation posted to channel!")
            else:
                # No channel, send to admin
                await update.message.reply_animation(
                    animation=file_id,
                    caption=test_caption,
                    parse_mode='HTML'
                )
                await self._send_response(update, context,
                    f"✅ <b>{tier}</b> animation sent!\n"
                    f"<i>(No channel configured, sent to DM)</i>")

        except Exception as e:
            logger.error(f"Error testing multiplier animation: {e}")
            await self._send_response(update, context,
                f"❌ Error sending animation: {str(e)[:100]}\n\n"
                f"The file_id may be invalid. Try setting it again with:\n"
                f"<code>/setmultiplier {tier}</code>")

    async def _handle_media_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Capture file_id when admin sends a video/animation"""
        try:
            msg = update.message
            file_id = None
            media_type = None

            if msg.animation:
                file_id = msg.animation.file_id
                media_type = "animation"
            elif msg.video:
                file_id = msg.video.file_id
                media_type = "video"
            elif msg.document and msg.document.mime_type and msg.document.mime_type.startswith('video/'):
                file_id = msg.document.file_id
                media_type = "document (video)"

            if not file_id:
                return

            logger.info(f"🎬 Admin uploaded {media_type}, file_id: {file_id}")

            # Determine what type of media this is for
            pending = self.pending_media_type
            self.pending_media_type = None  # Reset state

            if pending == 'banner' or pending is None:
                # Default: signal banner
                config.TELEGRAM_BANNER_FILE_ID = file_id
                env_var = 'TELEGRAM_BANNER_FILE_ID'
                description = "Signal Banner"

            elif pending.startswith('multiplier_'):
                tier = pending.replace('multiplier_', '')
                tier_map = {
                    '2x': ('MILESTONE_BANNER_2X', '2x (LET IT BURN)'),
                    '10x': ('MILESTONE_BANNER_10X', '10x (HELL FIRE)'),
                    '100x': ('MILESTONE_BANNER_100X', '100x (SCORCHED EARTH)'),
                    '1000x': ('MILESTONE_BANNER_1000X', '1000x (INFERNO)'),
                }
                env_var, description = tier_map.get(tier, ('UNKNOWN', tier))

                # Set in config memory
                if tier == '2x':
                    config.MILESTONE_BANNER_2X = file_id
                elif tier == '10x':
                    config.MILESTONE_BANNER_10X = file_id
                elif tier == '100x':
                    config.MILESTONE_BANNER_100X = file_id
                elif tier == '1000x':
                    config.MILESTONE_BANNER_1000X = file_id
            else:
                env_var = 'TELEGRAM_BANNER_FILE_ID'
                description = "Banner (default)"

            await msg.reply_text(
                f"🎬 <b>{description} Captured!</b>\n\n"
                f"Type: <code>{media_type}</code>\n"
                f"File ID:\n<code>{file_id}</code>\n\n"
                f"✅ <b>Applied in memory</b>\n\n"
                f"For persistence across restarts, set env var:\n"
                f"<code>{env_var}={file_id}</code>",
                parse_mode=ParseMode.HTML
            )

        except Exception as e:
            logger.error(f"❌ Error handling media upload: {e}")

    # ================================================================
    # WALLET MANAGEMENT COMMANDS
    # ================================================================

    async def _cmd_wallets(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show all tracked wallets"""
        try:
            if not self.database:
                await self._send_response(update, context, "❌ Database not available")
                return

            wallets = await self.database.get_tracked_wallets(active_only=True)

            if not wallets:
                await self._send_response(update, context,
                    "👛 <b>TRACKED WALLETS</b>\n\n"
                    "No wallets tracked yet.\n\n"
                    "Add wallets with:\n"
                    "<code>/addwallet Name Address</code>")
                return

            response = f"👛 <b>TRACKED WALLETS ({len(wallets)})</b>\n\n"

            for i, w in enumerate(wallets[:30], 1):  # Limit to 30 to avoid message length issues
                name = w.get('wallet_name', 'Unknown')
                addr = w.get('wallet_address', '')
                addr_short = f"{addr[:6]}...{addr[-4:]}" if len(addr) > 12 else addr
                tier = w.get('tier', 'unknown')
                win_rate = w.get('win_rate')
                pnl = w.get('pnl')
                source = w.get('source', 'manual')

                # Status indicator
                status = "🟢" if tier in ['elite', 'top_kol'] else "⚪"

                response += f"{status} <b>{name}</b>\n"
                response += f"   <code>{addr_short}</code>\n"

                # Stats line
                stats = []
                if win_rate is not None:
                    stats.append(f"WR: {win_rate*100:.0f}%")
                if pnl is not None:
                    pnl_str = f"+${pnl:,.0f}" if pnl >= 0 else f"-${abs(pnl):,.0f}"
                    stats.append(f"PnL: {pnl_str}")
                if stats:
                    response += f"   {' | '.join(stats)}\n"

                response += "\n"

            if len(wallets) > 30:
                response += f"<i>...and {len(wallets) - 30} more</i>\n\n"

            response += "<b>Commands:</b>\n"
            response += "<code>/addwallet Name Address</code>\n"
            response += "<code>/removewallet Address</code>\n"
            response += "<code>/renamewallet Address NewName</code>"

            await self._send_response(update, context, response)

        except Exception as e:
            logger.error(f"❌ Error in /wallets: {e}")
            await self._send_response(update, context, f"❌ Error: {str(e)}")

    async def _cmd_addwallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add a wallet to tracking: /addwallet <name> <address>"""
        try:
            if not self.database:
                await self._send_response(update, context, "❌ Database not available")
                return

            args = context.args
            if len(args) < 2:
                await self._send_response(update, context,
                    "❌ <b>Usage:</b> <code>/addwallet Name Address</code>\n\n"
                    "Example:\n"
                    "<code>/addwallet Ansem 9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM</code>")
                return

            name = args[0]
            address = args[1]

            # Validate address format (basic check)
            if len(address) < 32 or len(address) > 50:
                await self._send_response(update, context,
                    "❌ Invalid Solana address format.\n"
                    "Address should be 32-44 characters.")
                return

            # Check if already exists
            existing = await self.database.get_tracked_wallet(address)

            # Add to database
            success = await self.database.add_tracked_wallet(
                address=address,
                name=name,
                tier='unknown',
                source='manual'
            )

            if success:
                action = "updated" if existing else "added"
                response = f"✅ <b>Wallet {action}!</b>\n\n"
                response += f"<b>Name:</b> {name}\n"
                response += f"<b>Address:</b>\n<code>{address}</code>\n\n"

                # Try to register with Helius webhook
                try:
                    from helius_fetcher import HeliusDataFetcher
                    helius = HeliusDataFetcher()

                    # Get all wallet addresses
                    all_addresses = await self.database.get_tracked_wallet_addresses()

                    if all_addresses:
                        # Get Railway public domain from environment (auto-set by Railway)
                        railway_domain = os.getenv('RAILWAY_PUBLIC_DOMAIN', '')
                        if railway_domain:
                            base_url = f"https://{railway_domain}" if not railway_domain.startswith('http') else railway_domain
                            webhook_url = f"{base_url}/webhook/smart-wallet"
                            webhook_id = await helius.ensure_wallet_webhook(webhook_url, all_addresses)

                            if webhook_id:
                                response += f"📡 <b>Helius webhook updated</b>\n"
                                response += f"   Monitoring {len(all_addresses)} wallets\n"
                            else:
                                response += f"⚠️ Helius webhook update failed\n"
                        else:
                            response += f"⚠️ RAILWAY_PUBLIC_DOMAIN not set - webhook not registered!\n"
                except Exception as e:
                    logger.error(f"Helius webhook error: {e}")
                    response += f"⚠️ Helius webhook: {str(e)[:50]}\n"

                response += f"\n🔔 Wallet now tracked!"
            else:
                response = f"❌ Failed to add wallet. Check logs."

            await self._send_response(update, context, response)

        except Exception as e:
            logger.error(f"❌ Error in /addwallet: {e}")
            await self._send_response(update, context, f"❌ Error: {str(e)}")

    async def _cmd_removewallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Remove a wallet from tracking: /removewallet <address>"""
        try:
            if not self.database:
                await self._send_response(update, context, "❌ Database not available")
                return

            args = context.args
            if len(args) < 1:
                await self._send_response(update, context,
                    "❌ <b>Usage:</b> <code>/removewallet Address</code>\n\n"
                    "Example:\n"
                    "<code>/removewallet 9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM</code>")
                return

            address = args[0]

            # Check if exists
            existing = await self.database.get_tracked_wallet(address)
            if not existing:
                await self._send_response(update, context,
                    f"❌ Wallet not found:\n<code>{address}</code>")
                return

            wallet_name = existing.get('wallet_name', 'Unknown')

            # Remove from database (soft delete)
            success = await self.database.remove_tracked_wallet(address)

            if success:
                response = f"✅ <b>Wallet removed!</b>\n\n"
                response += f"<b>Name:</b> {wallet_name}\n"
                response += f"<b>Address:</b>\n<code>{address}</code>\n\n"

                # Update Helius webhook
                try:
                    from helius_fetcher import HeliusDataFetcher
                    helius = HeliusDataFetcher()

                    all_addresses = await self.database.get_tracked_wallet_addresses()

                    # Get Railway public domain from environment (auto-set by Railway)
                    railway_domain = os.getenv('RAILWAY_PUBLIC_DOMAIN', '')
                    if railway_domain and all_addresses:
                        base_url = f"https://{railway_domain}" if not railway_domain.startswith('http') else railway_domain
                        webhook_url = f"{base_url}/webhook/smart-wallet"
                        webhook_id = await helius.ensure_wallet_webhook(webhook_url, all_addresses)

                        if webhook_id:
                            response += f"📡 <b>Helius webhook updated</b>\n"
                            response += f"   Now monitoring {len(all_addresses)} wallets"
                except Exception as e:
                    logger.error(f"Helius webhook error: {e}")

                response += f"\n\n🔕 Wallet no longer tracked."
            else:
                response = f"❌ Failed to remove wallet. Check logs."

            await self._send_response(update, context, response)

        except Exception as e:
            logger.error(f"❌ Error in /removewallet: {e}")
            await self._send_response(update, context, f"❌ Error: {str(e)}")

    async def _cmd_renamewallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Rename a tracked wallet: /renamewallet <address> <newname>"""
        try:
            if not self.database:
                await self._send_response(update, context, "❌ Database not available")
                return

            args = context.args
            if len(args) < 2:
                await self._send_response(update, context,
                    "❌ <b>Usage:</b> <code>/renamewallet Address NewName</code>\n\n"
                    "Example:\n"
                    "<code>/renamewallet 9WzDXwBb... Ansem_Main</code>")
                return

            address = args[0]
            new_name = ' '.join(args[1:])  # Allow spaces in name

            # Check if exists
            existing = await self.database.get_tracked_wallet(address)
            if not existing:
                await self._send_response(update, context,
                    f"❌ Wallet not found:\n<code>{address}</code>")
                return

            old_name = existing.get('wallet_name', 'Unknown')

            # Rename
            success = await self.database.rename_wallet(address, new_name)

            if success:
                addr_short = f"{address[:6]}...{address[-4:]}"
                response = f"✅ <b>Wallet renamed!</b>\n\n"
                response += f"<b>Old name:</b> {old_name}\n"
                response += f"<b>New name:</b> {new_name}\n"
                response += f"<b>Address:</b> <code>{addr_short}</code>"
            else:
                response = f"❌ Failed to rename wallet. Check logs."

            await self._send_response(update, context, response)

        except Exception as e:
            logger.error(f"❌ Error in /renamewallet: {e}")
            await self._send_response(update, context, f"❌ Error: {str(e)}")

    async def _cmd_listwebhooks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all registered Helius webhooks: /listwebhooks"""
        try:
            await self._send_response(update, context, "🔍 Fetching Helius webhooks...")

            from helius_fetcher import HeliusDataFetcher
            helius = HeliusDataFetcher()
            webhooks = await helius.get_webhooks()

            if not webhooks:
                await self._send_response(update, context,
                    "📡 <b>No webhooks registered</b>\n\n"
                    "Use /addwallet to add wallets and register webhooks.")
                return

            response = f"📡 <b>HELIUS WEBHOOKS ({len(webhooks)})</b>\n\n"

            for idx, wh in enumerate(webhooks, 1):
                webhook_id = wh.get('webhookID', 'unknown')
                webhook_url = wh.get('webhookURL', 'unknown')
                addresses = wh.get('accountAddresses', [])
                webhook_type = wh.get('webhookType', 'unknown')

                # Determine webhook purpose
                pump_program = 'pump'
                is_pump = any(pump_program in addr.lower() for addr in addresses[:5])

                if is_pump:
                    purpose = "🎰 Pump.fun Program"
                else:
                    purpose = f"👛 Wallet Monitor ({len(addresses)} wallets)"

                response += f"<b>{idx}. {purpose}</b>\n"
                response += f"   ID: <code>{webhook_id[:20]}...</code>\n"
                response += f"   Type: {webhook_type}\n"
                response += f"   URL: ...{webhook_url[-30:]}\n"

                # Show sample addresses for wallet webhooks
                if not is_pump and addresses:
                    response += f"   Sample: {addresses[0][:8]}...\n"

                response += "\n"

            response += "<b>Commands:</b>\n"
            response += "/clearwebhooks - Delete all wallet webhooks\n"
            response += "/syncwebhook - Re-sync wallets to webhook"

            await self._send_response(update, context, response)

        except Exception as e:
            logger.error(f"❌ Error in /listwebhooks: {e}")
            await self._send_response(update, context, f"❌ Error: {str(e)}")

    async def _cmd_clearwebhooks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Delete all wallet webhooks (fresh start): /clearwebhooks"""
        try:
            await self._send_response(update, context,
                "🗑️ <b>Clearing wallet webhooks...</b>\n\n"
                "This will delete all wallet monitoring webhooks.\n"
                "Pump.fun program webhook will be preserved.")

            from helius_fetcher import HeliusDataFetcher
            import config

            helius = HeliusDataFetcher()
            webhooks = await helius.get_webhooks()

            if not webhooks:
                await self._send_response(update, context, "✅ No webhooks to delete.")
                return

            pump_program = config.HELIUS_PUMP_WEBHOOK.get('program_id', '')
            deleted = 0
            preserved = 0

            for wh in webhooks:
                webhook_id = wh.get('webhookID')
                addresses = wh.get('accountAddresses', [])

                # Skip pump.fun program webhook
                if pump_program in addresses:
                    preserved += 1
                    logger.info(f"   Preserving pump.fun webhook: {webhook_id[:20]}...")
                    continue

                # Delete wallet webhook
                success = await helius.delete_webhook(webhook_id)
                if success:
                    deleted += 1
                    logger.info(f"   Deleted webhook: {webhook_id[:20]}...")

            # Also clear database wallets if requested
            clear_db = context.args and 'db' in [a.lower() for a in context.args]
            db_cleared = 0
            db_error = None
            db_before = 0
            db_after = 0

            if clear_db:
                if self.database:
                    try:
                        # Check count BEFORE clear
                        before_wallets = await self.database.get_tracked_wallet_addresses()
                        db_before = len(before_wallets)
                        logger.info(f"📊 Before clear: {db_before} active wallets")

                        # Use batch clear for reliability
                        db_cleared = await self.database.clear_all_tracked_wallets()
                        if db_cleared == -1:
                            db_error = "Database error during clear"
                            db_cleared = 0
                        else:
                            logger.info(f"✅ Cleared {db_cleared} wallets from database")

                        # Check count AFTER clear to verify
                        after_wallets = await self.database.get_tracked_wallet_addresses()
                        db_after = len(after_wallets)
                        logger.info(f"📊 After clear: {db_after} active wallets")

                        if db_after > 0 and db_cleared > 0:
                            db_error = f"Clear reported {db_cleared} but {db_after} still active!"
                    except Exception as e:
                        db_error = str(e)
                        logger.error(f"Error clearing DB wallets: {e}")
                else:
                    db_error = "Database not available"
                    logger.error("Cannot clear DB wallets: self.database is None")

            response = f"✅ <b>Webhooks Cleared!</b>\n\n"
            response += f"<b>Deleted:</b> {deleted} wallet webhook(s)\n"
            response += f"<b>Preserved:</b> {preserved} (pump.fun program)\n"

            if clear_db:
                if db_error:
                    response += f"<b>DB Clear:</b> ❌ {db_error}\n"
                    response += f"<b>Debug:</b> Before={db_before}, After={db_after}\n"
                else:
                    response += f"<b>DB Cleared:</b> {db_cleared} wallet(s) deactivated\n"
                    response += f"<b>Verified:</b> {db_before} → {db_after} active\n"

            response += f"\n<b>Next steps:</b>\n"
            response += f"1. Add wallets: <code>/addwallet Name Address</code>\n"
            response += f"2. Get addresses from KOL scan or GMGN\n"
            response += f"\n<i>Tip: Add 'db' to also clear database:</i>\n"
            response += f"<code>/clearwebhooks db</code>"

            await self._send_response(update, context, response)

        except Exception as e:
            logger.error(f"❌ Error in /clearwebhooks: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await self._send_response(update, context, f"❌ Error: {str(e)}")

    async def _cmd_clearwebhooks_db(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Clear webhooks AND database wallets: /clearwebhooksdb"""
        try:
            await self._send_response(update, context,
                "🗑️ <b>Clearing webhooks + database...</b>")

            from helius_fetcher import HeliusDataFetcher
            import config

            helius = HeliusDataFetcher()
            webhooks = await helius.get_webhooks()

            pump_program = config.HELIUS_PUMP_WEBHOOK.get('program_id', '')
            deleted = 0

            for wh in (webhooks or []):
                webhook_id = wh.get('webhookID')
                addresses = wh.get('accountAddresses', [])
                if pump_program not in addresses and webhook_id:
                    if await helius.delete_webhook(webhook_id):
                        deleted += 1

            # Clear database wallets
            db_before = 0
            db_after = 0
            db_cleared = 0
            db_error = None

            if self.database:
                try:
                    before_wallets = await self.database.get_tracked_wallet_addresses()
                    db_before = len(before_wallets)
                    logger.info(f"📊 Before clear: {db_before} active wallets")

                    db_cleared = await self.database.clear_all_tracked_wallets()
                    if db_cleared == -1:
                        db_error = "Database error"
                        db_cleared = 0

                    after_wallets = await self.database.get_tracked_wallet_addresses()
                    db_after = len(after_wallets)
                    logger.info(f"📊 After clear: {db_after} active wallets")

                    if db_after > 0 and db_cleared > 0:
                        db_error = f"Still {db_after} active after clear!"
                except Exception as e:
                    db_error = str(e)
                    logger.error(f"DB clear error: {e}")
            else:
                db_error = "Database not connected"

            response = f"✅ <b>Full Clear Complete!</b>\n\n"
            response += f"<b>Helius:</b> {deleted} webhook(s) deleted\n"
            if db_error:
                response += f"<b>Database:</b> ❌ {db_error}\n"
                response += f"<b>Debug:</b> {db_before} → {db_after}\n"
            else:
                response += f"<b>Database:</b> {db_cleared} wallets cleared\n"
                response += f"<b>Verified:</b> {db_before} → {db_after}\n"

            await self._send_response(update, context, response)

        except Exception as e:
            logger.error(f"❌ Error in /clearwebhooksdb: {e}")
            await self._send_response(update, context, f"❌ Error: {str(e)}")

    async def _cmd_countwallets(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Debug command to check wallet counts: /countwallets"""
        try:
            import config

            response = "📊 <b>Wallet Count Debug</b>\n\n"

            # Config wallets
            config_wallets = getattr(config, 'SMART_WALLETS', [])
            response += f"<b>Config:</b> {len(config_wallets)} wallets\n"

            # Database wallets
            if self.database:
                try:
                    # Active wallets
                    active = await self.database.get_tracked_wallet_addresses()
                    response += f"<b>DB Active:</b> {len(active)} wallets\n"

                    # Total wallets (including inactive)
                    all_wallets = await self.database.get_tracked_wallets(active_only=False)
                    inactive = len(all_wallets) - len(active)
                    response += f"<b>DB Inactive:</b> {inactive} wallets\n"
                    response += f"<b>DB Total:</b> {len(all_wallets)} wallets\n"
                except Exception as e:
                    response += f"<b>DB Error:</b> {str(e)}\n"
            else:
                response += f"<b>DB:</b> Not connected\n"

            # Helius webhooks
            try:
                from helius_fetcher import HeliusDataFetcher
                helius = HeliusDataFetcher()
                webhooks = await helius.get_webhooks()

                pump_program = config.HELIUS_PUMP_WEBHOOK.get('program_id', '')
                wallet_webhook_count = 0
                wallet_addresses_total = 0

                for wh in webhooks:
                    addresses = wh.get('accountAddresses', [])
                    if pump_program not in addresses:
                        wallet_webhook_count += 1
                        wallet_addresses_total += len(addresses)

                response += f"\n<b>Helius Webhooks:</b> {len(webhooks)} total\n"
                response += f"   Wallet webhooks: {wallet_webhook_count}\n"
                response += f"   Addresses in webhooks: {wallet_addresses_total}\n"
            except Exception as e:
                response += f"\n<b>Helius Error:</b> {str(e)}\n"

            await self._send_response(update, context, response)

        except Exception as e:
            logger.error(f"❌ Error in /countwallets: {e}")
            await self._send_response(update, context, f"❌ Error: {str(e)}")

    async def _cmd_syncwebhook(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Register Helius webhook with all tracked wallets (force recreate)"""
        try:
            await self._send_response(update, context, "🔄 Syncing Helius webhook...")

            # Get wallets from config
            import config
            config_wallets = getattr(config, 'SMART_WALLETS', [])

            # Get wallets from database
            db_wallets = []
            if self.database:
                try:
                    db_wallets = await self.database.get_tracked_wallet_addresses()
                except Exception as e:
                    logger.warning(f"Could not get DB wallets: {e}")

            # Combine unique wallets
            all_wallets = list(set(config_wallets + db_wallets))

            if not all_wallets:
                await self._send_response(update, context,
                    "❌ No wallets found in config or database.\n"
                    "Add wallets with /addwallet first.")
                return

            # Get Railway URL
            railway_domain = os.getenv('RAILWAY_PUBLIC_DOMAIN', '')
            if not railway_domain:
                await self._send_response(update, context,
                    "❌ RAILWAY_PUBLIC_DOMAIN not set.\n"
                    "Cannot register webhook without public URL.")
                return

            base_url = f"https://{railway_domain}" if not railway_domain.startswith('http') else railway_domain
            webhook_url = f"{base_url}/webhook/smart-wallet"

            from helius_fetcher import HeliusDataFetcher
            helius = HeliusDataFetcher()

            # Delete existing wallet webhooks first (force fresh start)
            pump_program = config.HELIUS_PUMP_WEBHOOK.get('program_id', '')
            existing = await helius.get_webhooks()
            deleted = 0
            for wh in (existing or []):
                addresses = wh.get('accountAddresses', [])
                webhook_id = wh.get('webhookID')
                if webhook_id and pump_program not in addresses:
                    await helius.delete_webhook(webhook_id)
                    deleted += 1
                    logger.info(f"   Deleted old wallet webhook: {webhook_id[:20]}...")

            # Create fresh webhook with all wallets
            result = await helius.register_wallet_webhook(webhook_url, all_wallets)

            if result and result.get('webhook_id'):
                webhook_id = result['webhook_id']
                response = f"✅ <b>Helius Webhook Synced!</b>\n\n"
                if deleted > 0:
                    response += f"🗑️ Deleted {deleted} old webhook(s)\n"
                response += f"📡 Webhook ID: <code>{webhook_id[:20]}...</code>\n"
                response += f"🔗 URL: <code>{webhook_url}</code>\n"
                response += f"👛 Monitoring: {len(all_wallets)} wallets\n"
                response += f"   • {len(config_wallets)} from config\n"
                response += f"   • {len(db_wallets)} from database\n\n"
                response += f"✅ KOL buys will now trigger tracking!"
            else:
                response = f"❌ Failed to register webhook.\n"
                response += f"Check HELIUS_API_KEY is valid."

            await self._send_response(update, context, response)

        except Exception as e:
            logger.error(f"❌ Error in /syncwebhook: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await self._send_response(update, context, f"❌ Error: {str(e)}")
