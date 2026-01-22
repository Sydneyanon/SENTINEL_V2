"""
Admin Telegram Bot - Handle admin commands for monitoring and control
"""
import asyncio
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

            # Block all other users (unauthorized access attempts)
            self.app.add_handler(MessageHandler(~admin_filter, self._handle_unauthorized))

            logger.info(f"✅ Admin bot initialized")
            logger.info(f"   Commands registered: /start /help /stats /active /performance /health /cache")
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

<b>Monitoring:</b>
/active - Currently tracked tokens
/health - System health check
/cache - Telegram calls cache status

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
                stats_text += f"• Tokens called: {cache_size}\n"

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
        """Show recent signal performance"""
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
            response += f"Signals (48h): {len(signals)}\n\n"

            # Show last 8 signals
            for signal in signals[:8]:
                symbol = signal.get('token_symbol', 'UNKNOWN')
                score = signal.get('conviction_score', 0)
                entry = signal.get('entry_price', 0)
                timestamp = signal.get('created_at', '')

                # Parse timestamp
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    age = datetime.utcnow().replace(tzinfo=dt.tzinfo) - dt
                    age_str = f"{age.total_seconds() / 3600:.1f}h ago"
                except:
                    age_str = "unknown"

                response += f"<b>${symbol}</b> ({score}/100)\n"
                response += f"   Entry: ${entry:.8f}\n"
                response += f"   {age_str}\n\n"

            if len(signals) > 8:
                response += f"<i>...and {len(signals) - 8} more</i>"

            await self._send_response(update, context, response)

        except Exception as e:
            logger.error(f"❌ Error in /performance: {e}")
            await update.message.reply_text(f"❌ Error getting performance: {str(e)}")

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
