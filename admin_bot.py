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
        self.auto_ml_enabled = True  # Auto ML retraining enabled by default

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

            # NEW: Unified commands
            self.app.add_handler(CommandHandler("data", self._cmd_data, filters=admin_filter))
            self.app.add_handler(CommandHandler("ralph", self._cmd_ralph, filters=admin_filter))

            self.app.add_handler(CommandHandler("stats", self._cmd_stats, filters=admin_filter))
            self.app.add_handler(CommandHandler("active", self._cmd_active, filters=admin_filter))
            self.app.add_handler(CommandHandler("performance", self._cmd_performance, filters=admin_filter))
            self.app.add_handler(CommandHandler("toprunners", self._cmd_toprunners, filters=admin_filter))
            self.app.add_handler(CommandHandler("health", self._cmd_health, filters=admin_filter))
            self.app.add_handler(CommandHandler("cache", self._cmd_cache, filters=admin_filter))
            self.app.add_handler(CommandHandler("missed", self._cmd_missed, filters=admin_filter))
            self.app.add_handler(CommandHandler("whales", self._cmd_whales, filters=admin_filter))
            self.app.add_handler(CommandHandler("config", self._cmd_config, filters=admin_filter))
            self.app.add_handler(CommandHandler("dataset", self._cmd_dataset, filters=admin_filter))
            self.app.add_handler(CommandHandler("collect", self._cmd_collect, filters=admin_filter))
            self.app.add_handler(CommandHandler("ml", self._cmd_ml_retrain, filters=admin_filter))
            self.app.add_handler(CommandHandler("syncmldata", self._cmd_sync_ml_data, filters=admin_filter))
            self.app.add_handler(CommandHandler("automl", self._cmd_automl, filters=admin_filter))
            self.app.add_handler(CommandHandler("optimize", self._cmd_optimize, filters=admin_filter))
            self.app.add_handler(CommandHandler("pause", self._cmd_pause, filters=admin_filter))
            self.app.add_handler(CommandHandler("resume", self._cmd_resume, filters=admin_filter))
            self.app.add_handler(CommandHandler("winrate", self._cmd_winrate, filters=admin_filter))
            self.app.add_handler(CommandHandler("winratekol", self._cmd_winrate_kol, filters=admin_filter))
            self.app.add_handler(CommandHandler("kolstats", self._cmd_kolstats, filters=admin_filter))
            self.app.add_handler(CommandHandler("analyze", self._cmd_analyze, filters=admin_filter))
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

<b>🎯 CORE (Start Here):</b>
/data - All data stats in one place
/ralph - Full analysis + recommendations
/ml - Train ML model (auto-syncs data)

<b>Performance:</b>
/stats - Overall system statistics
/performance - Recent signal performance
/toprunners - All 2x+ winners
/kolstats - KOL performance breakdown

<b>Monitoring:</b>
/active - Currently tracked tokens
/health - System health check
/config - Live scoring config values

<b>Wallet Management:</b>
/wallets - View all tracked wallets
/addwallet &lt;name&gt; &lt;address&gt; - Add wallet
/removewallet &lt;address&gt; - Remove wallet
/syncwebhook - Sync wallets to Helius
/listwebhooks - Show all registered Helius webhooks
/clearwebhooks - Delete all wallet webhooks (fresh start)
/countwallets - Debug wallet counts (DB vs Helius)

<b>Data &amp; ML:</b>
/dataset - ML training dataset stats
/collect - Collect yesterday's missed winners
/syncmldata - Sync database signals to ML training
/ml - Retrain ML model with latest data
/automl - Toggle auto ML retraining (daily 2AM UTC)
/analyze - Deep performance analysis with recommendations
/optimize - Ralph finds optimal thresholds (backtests all signals)

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

    async def _cmd_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Unified data status command - all data stats in one place"""
        try:
            if not self.database or not self.database.pool:
                await self._send_response(update, context, "❌ Database not available")
                return

            from ralph.data_manager import DataManager
            dm = DataManager(self.database)
            status = await dm.get_status()

            if status.get('error'):
                await self._send_response(update, context, f"❌ {status['error']}")
                return

            # Build response
            r = "📊 <b>DATA STATUS</b>\n\n"

            # Signals
            r += "<b>📈 Signals:</b>\n"
            r += f"   Total posted: {status['total_signals']}\n"
            r += f"   With outcomes: {status['with_outcomes']}\n"
            r += f"   Pending outcomes: {status['pending_outcomes']}\n"
            r += f"   Last 24h: {status['recent_24h']}\n\n"

            # Diagnostic breakdown
            r += "<b>🔍 Data Quality:</b>\n"
            r += f"   Usable for ML: {status.get('usable_for_ml', status['with_outcomes'])}\n"
            missing_outcome = status.get('missing_outcome', 0)
            missing_price = status.get('missing_entry_price', 0)
            if missing_outcome > 0:
                r += f"   ⏳ Missing outcome: {missing_outcome}\n"
            if missing_price > 0:
                r += f"   ⚠️ Missing entry price: {missing_price}\n"
            r += "\n"

            # Outcomes breakdown
            if status['outcome_distribution']:
                r += "<b>📊 Outcomes:</b>\n"
                dist = status['outcome_distribution']
                wins = sum(dist.get(k, 0) for k in ['2x', '5x', '10x', '50x', '100x'])
                rugs = dist.get('rug', 0)
                losses = dist.get('loss', 0)
                r += f"   ✅ Wins: {wins} | ❌ Rugs: {rugs} | 📉 Loss: {losses}\n\n"

            # KOL & Wallets
            r += "<b>👑 KOL Data:</b>\n"
            r += f"   KOL-backed signals: {status['kol_signals']}\n"
            r += f"   Wallet activity records: {status['wallet_activity']}\n"
            r += f"   Tracked wallets: {status['tracked_wallets']}\n\n"

            # ML Status
            r += "<b>🤖 ML Status:</b>\n"
            r += f"   {status['ml_status']}\n"
            r += f"   Min required: {status['min_for_ml']} signals with outcomes\n\n"

            if status['ml_ready']:
                r += "💡 <i>Run /ml to train model</i>"
            else:
                r += "💡 <i>Keep collecting data, or run /ralph for analysis</i>"

            await self._send_response(update, context, r)

        except Exception as e:
            logger.error(f"❌ Error in /data: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await self._send_response(update, context, f"❌ Error: {str(e)}")

    async def _cmd_ralph(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Unified Ralph analysis - all analysis in one place"""
        try:
            if not self.database or not self.database.pool:
                await self._send_response(update, context, "❌ Database not available")
                return

            # Parse days argument
            days = 7
            if context.args:
                try:
                    days = int(context.args[0])
                    days = min(max(days, 1), 30)
                except ValueError:
                    pass

            await self._send_response(update, context,
                f"🤖 <b>Running Ralph Analysis...</b>\n"
                f"Analyzing last {days} days. This may take a moment.")

            # Run in background
            asyncio.create_task(self._run_ralph_background(update, context, days))

        except Exception as e:
            logger.error(f"❌ Error in /ralph: {e}")
            await self._send_response(update, context, f"❌ Error: {str(e)}")

    async def _run_ralph_background(self, update: Update, context: ContextTypes.DEFAULT_TYPE, days: int):
        """Run Ralph analysis in background"""
        try:
            from ralph.unified_analysis import RalphAnalysis

            analyzer = RalphAnalysis(self.database)
            results = await analyzer.full_analysis(days)

            if results.get('error') == 'insufficient_data':
                await self._send_response(update, context,
                    f"⚠️ <b>Insufficient data</b>\n\n"
                    f"Only {results.get('signal_count', 0)} signals.\n"
                    f"Need 10+ for analysis.")
                return

            if results.get('error'):
                await self._send_response(update, context,
                    f"❌ Analysis failed: {results['error']}")
                return

            # Build response
            r = "🤖 <b>RALPH ANALYSIS</b>\n\n"

            # Overall
            overall = results.get('overall', {})
            if overall:
                wr = overall.get('win_rate', 0)
                rr = overall.get('rug_rate', 0)
                emoji = "🟢" if wr >= 40 else "🟡" if wr >= 25 else "🔴"

                r += f"<b>📈 Overall ({days}d):</b>\n"
                r += f"{emoji} Win Rate: {wr:.0f}% ({overall.get('wins', 0)}W / {overall.get('rugs', 0)}R)\n"
                r += f"   Avg ROI: {overall.get('avg_roi', 1):.1f}x | Best: {overall.get('max_roi', 1):.0f}x\n\n"

            # Threshold recommendations
            thresh = results.get('threshold_analysis', {})
            if thresh.get('pre_grad', {}).get('thresholds'):
                r += "<b>🎯 Pre-grad Thresholds:</b>\n"
                pre = thresh['pre_grad']
                for t, data in sorted(pre['thresholds'].items()):
                    emoji = "🟢" if data['win_rate'] >= 50 else "🟡" if data['win_rate'] >= 35 else "🔴"
                    curr = " ←" if t == pre.get('current') else ""
                    opt = " 🎯" if t == pre.get('optimal') and t != pre.get('current') else ""
                    r += f"{emoji} {t}: {data['win_rate']:.0f}% ({data['signals']}){curr}{opt}\n"
                r += "\n"

            # KOL impact - show actual numbers
            kol = results.get('kol_analysis', {}).get('kol_vs_organic', {})
            if kol.get('kol') and kol.get('organic'):
                kol_wr = kol['kol'].get('win_rate', 0)
                kol_count = kol['kol'].get('total', 0)
                org_wr = kol['organic'].get('win_rate', 0)
                org_count = kol['organic'].get('total', 0)
                diff = kol_wr - org_wr

                r += "<b>👑 KOL vs ORGANIC:</b>\n"
                r += f"   KOL: {kol_wr:.0f}% WR ({kol_count} signals)\n"
                r += f"   Organic: {org_wr:.0f}% WR ({org_count} signals)\n"
                if diff > 5:
                    r += f"   ✅ KOL adds +{diff:.0f}%\n"
                elif diff < -5:
                    r += f"   ⚠️ KOL hurts by {diff:.0f}%\n"
                else:
                    r += f"   ➖ Similar performance\n"
                r += "\n"

            # Metrics breakdown (strong predictors + recommendations)
            metrics_data = results.get('metrics_breakdown', {})
            metrics = metrics_data.get('metrics', {})
            metrics_recs = metrics_data.get('recommendations', [])

            if metrics:
                r += "<b>🔬 METRICS BREAKDOWN:</b>\n"

                # Show strong predictors
                for key, data in metrics.items():
                    if data.get('is_predictive') and data.get('wins_avg') and data.get('rugs_avg'):
                        direction = "↑" if data.get('direction') == 'higher' else "↓"
                        name = data.get('name', key.replace('_', ' ').title())
                        r += f"✅ <b>{name}</b>\n"
                        r += f"   Wins: {data['wins_avg']:.1f} | Rugs: {data['rugs_avg']:.1f} ({direction})\n"

                        # Show best threshold if available
                        if data.get('best_threshold'):
                            best = data['best_threshold']
                            thresh_data = data.get('thresholds', {}).get(best, {})
                            op = "≥" if data.get('direction') == 'higher' else "≤"
                            r += f"   Best: {op}{best} → {thresh_data.get('win_rate', 0):.0f}% WR\n"

                        # Show recommendation if available
                        if data.get('recommendation'):
                            rec = data['recommendation']
                            r += f"   💡 {rec['from']} → {rec['to']} ({rec['impact']})\n"
                        r += "\n"

                # Summary
                summary = metrics_data.get('summary', {})
                if summary:
                    strong = len(summary.get('strong_predictors', []))
                    weak = len(summary.get('weak_predictors', []))
                    r += f"<i>{strong} strong, {weak} weak predictors</i>\n\n"

            # Metrics recommendations section
            if metrics_recs:
                r += "<b>📋 FILTER RECOMMENDATIONS:</b>\n"
                for rec in metrics_recs[:5]:
                    r += f"• {rec['name']}: {rec['from']} → {rec['to']} ({rec['impact']})\n"
                r += "\n"

            # Hidden patterns section
            hidden = results.get('hidden_patterns', {})
            if hidden:
                insights = hidden.get('insights', [])
                time_patterns = hidden.get('time_patterns', {})
                narrative = hidden.get('narrative_analysis', {})
                baseline_wr = time_patterns.get('baseline_wr', 27)

                r += "<b>⏰ HOURLY BREAKDOWN (UTC):</b>\n"

                # Full hourly breakdown
                hourly = time_patterns.get('hourly_breakdown', [])
                if hourly:
                    r += "<pre>"
                    r += "Hr │ WR  │n  ║Hr │ WR  │n\n"
                    r += "───┼─────┼───╬───┼─────┼───\n"
                    # Display hours in 2 columns (0-11 and 12-23)
                    for i in range(12):
                        h1, wr1, n1 = hourly[i] if i < len(hourly) else (i, None, 0)
                        h2, wr2, n2 = hourly[i+12] if i+12 < len(hourly) else (i+12, None, 0)

                        # Column 1
                        if wr1 is not None:
                            e1 = "🟢" if wr1 >= baseline_wr + 10 else "🔴" if wr1 <= baseline_wr - 10 else "🟡"
                            c1 = f"{h1:02d}│{e1}{wr1:3.0f}%│{n1:2d}"
                        else:
                            c1 = f"{h1:02d}│ --  │{n1:2d}"

                        # Column 2
                        if wr2 is not None:
                            e2 = "🟢" if wr2 >= baseline_wr + 10 else "🔴" if wr2 <= baseline_wr - 10 else "🟡"
                            c2 = f"{h2:02d}│{e2}{wr2:3.0f}%│{n2:2d}"
                        else:
                            c2 = f"{h2:02d}│ --  │{n2:2d}"

                        r += f"{c1}║{c2}\n"
                    r += "</pre>"
                    r += f"🟢>{baseline_wr+10:.0f}% 🟡avg 🔴<{baseline_wr-10:.0f}%\n\n"

                # Full daily breakdown
                daily = time_patterns.get('daily_breakdown', [])
                if daily:
                    r += "<b>📅 DAILY BREAKDOWN:</b>\n"
                    r += "<pre>"
                    for day_name, wr, count in daily:
                        if wr is not None:
                            e = "🟢" if wr >= baseline_wr + 10 else "🔴" if wr <= baseline_wr - 10 else "🟡"
                            r += f"{day_name}: {e}{wr:5.1f}% ({count:3d})\n"
                        else:
                            r += f"{day_name}:   --   ({count:3d})\n"
                    r += "</pre>\n"

                # Best/worst summary
                if time_patterns.get('best_hours'):
                    hours = time_patterns['best_hours'][:3]
                    r += f"✅ Best: {', '.join(f'{h}:00 ({wr:.0f}%)' for h, wr, _ in hours)}\n"
                if time_patterns.get('worst_hours'):
                    hours = time_patterns['worst_hours'][:3]
                    r += f"⚠️ Worst: {', '.join(f'{h}:00 ({wr:.0f}%)' for h, wr, _ in hours)}\n"

                # Winning narratives
                if narrative.get('winners'):
                    winners = narrative['winners'][:3]
                    r += f"📖 Hot: {', '.join(f'{t} ({wr:.0f}%)' for t, wr, _ in winners)}\n"

                # Key insights
                if insights:
                    for insight in insights[:2]:
                        r += f"💡 {insight}\n"

                r += "\n"

            # Recommendations
            recs = results.get('recommendations', [])
            if recs:
                r += "<b>💡 Recommendations:</b>\n"
                for rec in recs[:5]:
                    if rec['type'] == 'threshold':
                        r += f"• {rec['setting']}: {rec['current']} → {rec['recommended']}\n"
                    elif rec['type'] == 'kol':
                        r += f"• Remove: {rec['wallet']} ({rec['reason']})\n"
                r += "\n"

            # Health score
            health = results.get('health_score', {})
            if health:
                r += f"<b>📊 Health:</b> {health.get('score', 50)}/100 ({health.get('grade', 'N/A')})\n"

            r += "\n<i>Full analysis logged to Railway</i>"

            await self._send_response(update, context, r)

        except Exception as e:
            logger.error(f"❌ Ralph analysis failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await self._send_response(update, context, f"❌ Analysis failed: {str(e)}")

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

    async def _cmd_toprunners(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show all 2x+ winners from last 24 hours, sorted by peak ROI"""
        try:
            if not self.database:
                await self._send_response(update, context, "❌ Database not available")
                return

            # Get signals from last 24 hours
            signals = await self.database.get_signals_in_last_hours(24)

            if not signals:
                await self._send_response(update, context, "ℹ️ No signals in last 24 hours")
                return

            # Filter for 2x+ winners and collect their data
            winners = []
            for signal in signals:
                symbol = signal.get('token_symbol', 'UNKNOWN')
                entry = signal.get('entry_price', 0)
                token_address = signal.get('token_address', '')
                score = signal.get('conviction_score', 0)

                # Get peak from max_price_reached
                peak_price = signal.get('max_price_reached')
                if peak_price and entry and entry > 0:
                    peak_multiple = peak_price / entry
                else:
                    # Fall back to milestone table
                    peak_multiple = await self.database.get_highest_milestone(token_address) if token_address else None

                if peak_multiple and peak_multiple >= 2.0:
                    winners.append({
                        'symbol': symbol,
                        'multiple': peak_multiple,
                        'score': score,
                        'address': token_address
                    })

            if not winners:
                await self._send_response(update, context, f"ℹ️ No 2x+ winners in last 24h ({len(signals)} signals total)")
                return

            # Sort by multiple descending
            winners.sort(key=lambda x: x['multiple'], reverse=True)

            # Build response
            response = f"🏆 <b>TOP RUNNERS (24H)</b>\n"
            response += f"<i>{len(winners)} winners out of {len(signals)} signals</i>\n\n"

            for i, w in enumerate(winners, 1):
                if i == 1:
                    emoji = "🥇"
                elif i == 2:
                    emoji = "🥈"
                elif i == 3:
                    emoji = "🥉"
                elif w['multiple'] >= 5.0:
                    emoji = "🔥"
                else:
                    emoji = "✅"

                response += f"{emoji} <b>${w['symbol']}</b> → <b>{w['multiple']:.1f}x</b> (score {w['score']})\n"

            await self._send_response(update, context, response)

        except Exception as e:
            logger.error(f"❌ Error in /toprunners: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await self._send_response(update, context, f"❌ Error getting top runners: {str(e)}")

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
            ml_threshold = 75
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
        """Collect yesterday's winners we missed - the most valuable training data"""
        try:
            await self._send_response(update, context,
                "🎯 <b>Starting Missed Winners Collection...</b>\n\n"
                "Finding yesterday's top pump.fun gainers,\n"
                "checking which ones we DIDN'T signal,\n"
                "and learning from our blind spots.\n\n"
                "This is the most valuable ML training data!")

            # Run in background so the bot stays responsive
            asyncio.create_task(self._run_collect_background(update, context))

        except Exception as e:
            logger.error(f"❌ Error in /collect: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _run_collect_background(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Run missed winners collection in background and report result"""
        try:
            from tools.missed_winners_collector import MissedWinnersCollector

            collector = MissedWinnersCollector(database=self.database)
            result = await collector.run()

            if result.get('action') == 'failed':
                await self._send_response(update, context,
                    f"❌ <b>Collection failed</b>\n\n"
                    f"Reason: {result.get('reason', 'Unknown')}")
                return

            # Get stats
            missed = result.get('missed_winners', 0)
            signaled = result.get('already_signaled', 0)
            collected = result.get('collected', 0)
            checked = result.get('total_checked', 0)

            # Get total dataset size
            total = 0
            try:
                import json
                with open('data/historical_training_data.json', 'r') as f:
                    data = json.load(f)
                    total = data.get('total_tokens', 0)
            except Exception:
                pass

            # Build response
            if missed > 0:
                msg = f"🎯 <b>Missed Winners Found!</b>\n\n"
                msg += f"<b>Winners checked:</b> {checked}\n"
                msg += f"<b>We signaled:</b> {signaled} ✅\n"
                msg += f"<b>We MISSED:</b> {missed} ❌\n"
                msg += f"<b>New data added:</b> +{collected}\n\n"
                msg += f"<b>Dataset total:</b> {total} tokens\n\n"

                if signaled > 0 and checked > 0:
                    catch_rate = (signaled / checked) * 100
                    msg += f"📊 <b>Catch rate:</b> {catch_rate:.0f}%\n"
                    if catch_rate < 30:
                        msg += "⚠️ We're missing a lot of winners!\n"
                    elif catch_rate > 70:
                        msg += "✅ Good catch rate!\n"

                msg += f"\n{'✅ Ready for ML training!' if total >= 75 else f'Need {75 - total} more tokens.'}"
            else:
                msg = f"✅ <b>Collection complete</b>\n\n"
                msg += f"<b>Winners checked:</b> {checked}\n"
                msg += f"<b>We signaled:</b> {signaled}\n"
                msg += f"<b>Missed:</b> 0 (we caught them all!)\n\n"
                msg += f"<b>Dataset total:</b> {total} tokens"

            await self._send_response(update, context, msg)
        except Exception as e:
            logger.error(f"❌ Background collection failed: {e}")
            await self._send_response(update, context, f"❌ Collection failed: {str(e)}")

    async def _cmd_ml_retrain(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manually trigger ML model retraining (auto-syncs from database first)"""
        try:
            await self._send_response(update, context,
                "🎓 <b>Starting ML Training...</b>\n\n"
                "Step 1: Syncing data from database\n"
                "Step 2: Training ML model\n\n"
                "This may take a few minutes.")

            asyncio.create_task(self._run_ml_background(update, context))

        except Exception as e:
            logger.error(f"❌ Error in /ml: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _run_ml_background(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Run ML retraining in background - auto-syncs from database first"""
        try:
            # Step 1: Auto-sync from database
            logger.info("🔄 Auto-syncing data from database...")
            synced = await self._sync_db_to_training_file()
            logger.info(f"   Synced {synced} signals from database")

            # Step 2: Train ML model
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

    async def _sync_db_to_training_file(self) -> int:
        """Sync database signals to training file, merging with external data. Returns count synced."""
        try:
            import json
            import os

            if not self.database or not self.database.pool:
                return 0

            data_file = 'data/historical_training_data.json'

            # Load existing external data
            existing_tokens = []
            if os.path.exists(data_file):
                try:
                    with open(data_file, 'r') as f:
                        existing_data = json.load(f)
                        existing_tokens = existing_data.get('tokens', [])
                except:
                    pass

            # Get database signals
            from ralph.data_manager import DataManager
            dm = DataManager(self.database)
            data = await dm.get_training_data()

            if not data:
                return 0

            # Convert to training format
            db_tokens = []
            for s in data:
                token_data = {
                    'token_address': s.get('token_address', ''),
                    'symbol': s.get('token_symbol', ''),
                    'conviction_score': s.get('conviction_score', 0),
                    'entry_price': s.get('entry_price', 0),
                    'max_price_reached': s.get('max_price_reached', 0),
                    'max_roi': s.get('roi', 1),
                    'outcome': s.get('outcome', ''),
                    'bonding_curve_pct': s.get('bonding_curve_pct', 0),
                    'buy_percentage': s.get('buy_percentage', 0),
                    'unique_buyers': s.get('unique_buyers', 0),
                    'buys_24h': s.get('buys_24h', 0),
                    'sells_24h': s.get('sells_24h', 0),
                    'liquidity': s.get('liquidity', 0),
                    'volume_24h': s.get('volume_24h', 0),
                    'market_cap': s.get('market_cap', 0),
                    'kol_count': len(s.get('kol_wallets') or []),
                    'kol_wallets': s.get('kol_wallets'),
                    'source': 'database'
                }
                db_tokens.append(token_data)

            # Merge: DB takes priority, keep external tokens we don't have
            db_addresses = {t['token_address'] for t in db_tokens}
            external_only = [t for t in existing_tokens if t.get('token_address') not in db_addresses]
            combined = db_tokens + external_only

            # Write merged data
            os.makedirs('data', exist_ok=True)
            with open(data_file, 'w') as f:
                json.dump({
                    'tokens': combined,
                    'total_tokens': len(combined),
                    'db_signals': len(db_tokens),
                    'external_tokens': len(external_only),
                    'last_sync': datetime.utcnow().isoformat()
                }, f, indent=2, default=str)

            return len(db_tokens)

        except Exception as e:
            logger.error(f"Failed to sync DB to training file: {e}")
            return 0

    async def _cmd_sync_ml_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Sync database signals to ML training data file (legacy - /ml does this automatically)"""
        try:
            if not self.database or not self.database.pool:
                await self._send_response(update, context, "❌ Database not available")
                return

            await self._send_response(update, context,
                "🔄 <b>Syncing database signals to ML training data...</b>")

            # Get all signals from database
            signals = await self.database.get_all_signals_for_ml()

            if not signals:
                await self._send_response(update, context, "ℹ️ No signals found in database")
                return

            # Convert to ML training format
            training_tokens = []
            outcome_dist = {'rug': 0, '2x': 0, '10x': 0, '50x': 0, '100x': 0, 'loss': 0}

            for s in signals:
                if not s.get('entry_price') or s['entry_price'] <= 0:
                    continue

                # Calculate ROI and outcome
                peak = s.get('max_price_reached') or 0
                entry = s['entry_price']
                roi = peak / entry if peak > 0 else 0

                if roi >= 100:
                    outcome = '100x+'
                    outcome_dist['100x'] += 1
                elif roi >= 50:
                    outcome = '50x'
                    outcome_dist['50x'] += 1
                elif roi >= 10:
                    outcome = '10x'
                    outcome_dist['10x'] += 1
                elif roi >= 2:
                    outcome = '2x'
                    outcome_dist['2x'] += 1
                elif roi < 0.5:
                    outcome = 'rug'
                    outcome_dist['rug'] += 1
                else:
                    outcome = 'small'
                    outcome_dist['loss'] += 1

                token_data = {
                    'address': s.get('token_address', ''),
                    'symbol': s.get('token_symbol', ''),
                    'conviction_score': s.get('conviction_score', 0),
                    'entry_price': entry,
                    'max_price': peak,
                    'roi': roi,
                    'outcome': outcome,
                    'bonding_curve_pct': s.get('bonding_curve_pct', 0),
                    'buy_percentage': s.get('buy_percentage', 0),
                    'liquidity_usd': s.get('liquidity', 0),
                    'volume_24h': s.get('volume_24h', 0),
                    'market_cap': s.get('market_cap', 0),
                    'kol_count': len(s.get('kol_wallets') or []),
                    'has_kol': bool(s.get('kol_wallets')),
                    'created_at': str(s.get('created_at', ''))
                }
                training_tokens.append(token_data)

            # Load existing external data
            data_file = 'data/historical_training_data.json'
            try:
                import json
                with open(data_file, 'r') as f:
                    existing = json.load(f)
                external_tokens = existing.get('tokens', [])
            except:
                external_tokens = []

            # Merge (database signals take priority - more recent/accurate)
            existing_addresses = {t['address'] for t in training_tokens}
            for ext in external_tokens:
                if ext.get('address') not in existing_addresses:
                    training_tokens.append(ext)

            # Save merged data
            import json
            from datetime import datetime
            merged_data = {
                'total_tokens': len(training_tokens),
                'tokens': training_tokens,
                'outcome_distribution': outcome_dist,
                'last_sync': datetime.utcnow().isoformat(),
                'source': 'database + external',
                'db_signals': len(signals),
                'external_tokens': len(external_tokens)
            }

            with open(data_file, 'w') as f:
                json.dump(merged_data, f, indent=2, default=str)

            # Summary
            ready = "✅ Ready for ML training!" if len(training_tokens) >= 75 else f"Need {75 - len(training_tokens)} more tokens"

            await self._send_response(update, context,
                f"✅ <b>ML Data Synced!</b>\n\n"
                f"<b>Database signals:</b> {len(signals)}\n"
                f"<b>External tokens:</b> {len(external_tokens)}\n"
                f"<b>Total merged:</b> {len(training_tokens)}\n\n"
                f"<b>Outcomes:</b>\n"
                f"  🔴 Rug: {outcome_dist['rug']}\n"
                f"  🟡 Loss: {outcome_dist['loss']}\n"
                f"  🟢 2x: {outcome_dist['2x']}\n"
                f"  🟢 10x: {outcome_dist['10x']}\n"
                f"  🟢 50x: {outcome_dist['50x']}\n"
                f"  🔥 100x+: {outcome_dist['100x']}\n\n"
                f"{ready}\n\n"
                f"Run /ml to train the model.")

        except Exception as e:
            logger.error(f"❌ Error in /syncmldata: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await self._send_response(update, context, f"❌ Error: {str(e)}")

    async def _cmd_automl(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Toggle automatic ML retraining on/off"""
        try:
            args = context.args

            if not args:
                # Show current status
                status = "ON ✅" if self.auto_ml_enabled else "OFF ❌"
                await self._send_response(update, context,
                    f"🤖 <b>Auto ML Status:</b> {status}\n\n"
                    f"When enabled, ML automatically retrains daily at 2 AM UTC "
                    f"after collecting missed winners.\n\n"
                    f"Usage:\n"
                    f"  /automl on - Enable auto retraining\n"
                    f"  /automl off - Disable auto retraining")
                return

            cmd = args[0].lower()

            if cmd == 'on':
                self.auto_ml_enabled = True
                await self._send_response(update, context,
                    "✅ <b>Auto ML enabled!</b>\n\n"
                    "Daily pipeline will run at 2 AM UTC:\n"
                    "1. Collect missed winners from DexScreener\n"
                    "2. Sync database signals\n"
                    "3. Retrain ML model if enough data\n\n"
                    "Run /ml to train immediately.")
            elif cmd == 'off':
                self.auto_ml_enabled = False
                await self._send_response(update, context,
                    "❌ <b>Auto ML disabled.</b>\n\n"
                    "Use /ml to manually trigger training.\n"
                    "Use /automl on to re-enable.")
            else:
                await self._send_response(update, context,
                    "❓ Unknown option. Use: /automl on or /automl off")

        except Exception as e:
            logger.error(f"❌ Error in /automl: {e}")
            await self._send_response(update, context, f"❌ Error: {str(e)}")

    async def _cmd_optimize(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Run Ralph threshold optimizer to find optimal settings"""
        try:
            if not self.database or not self.database.pool:
                await self._send_response(update, context, "❌ Database not available")
                return

            # Parse days argument (default 7)
            days = 7
            if context.args:
                try:
                    days = int(context.args[0])
                    days = min(max(days, 1), 30)  # Clamp to 1-30 days
                except ValueError:
                    pass

            await self._send_response(update, context,
                f"🤖 <b>Running Ralph Threshold Optimizer...</b>\n\n"
                f"Analyzing last {days} days of signals.\n"
                f"This may take a moment.")

            # Run in background
            asyncio.create_task(self._run_optimize_background(update, context, days))

        except Exception as e:
            logger.error(f"❌ Error in /optimize: {e}")
            await self._send_response(update, context, f"❌ Error: {str(e)}")

    async def _run_optimize_background(self, update: Update, context: ContextTypes.DEFAULT_TYPE, days: int):
        """Run optimization in background and report results"""
        try:
            from ralph.optimizer import RalphOptimizer

            optimizer = RalphOptimizer(self.database)
            results = await optimizer.run_optimization(days)

            if results.get('error') == 'insufficient_data':
                await self._send_response(update, context,
                    f"⚠️ <b>Insufficient data</b>\n\n"
                    f"Only {results.get('signal_count', 0)} signals found.\n"
                    f"Need 20+ signals with outcomes for optimization.")
                return

            if results.get('error'):
                await self._send_response(update, context,
                    f"❌ Optimization failed: {results['error']}")
                return

            # Build response
            r = "🤖 <b>RALPH OPTIMIZATION RESULTS</b>\n\n"

            # Current settings
            curr = results.get('current_settings', {})
            r += f"<b>📊 Data analyzed:</b> {results.get('total_signals', 0)} signals\n"
            r += f"   Pre-grad: {results.get('pre_grad_count', 0)} | Post-grad: {results.get('post_grad_count', 0)}\n\n"

            # Pre-grad analysis
            pre = results.get('pre_grad_analysis', {})
            if pre.get('thresholds'):
                r += "<b>PRE-GRAD THRESHOLDS:</b>\n"
                for thresh, data in sorted(pre['thresholds'].items()):
                    emoji = "🟢" if data['win_rate'] >= 50 else "🟡" if data['win_rate'] >= 35 else "🔴"
                    curr_marker = " ←" if thresh == curr.get('min_conviction_score') else ""
                    opt_marker = " 🎯" if thresh == pre.get('optimal_threshold') and thresh != curr.get('min_conviction_score') else ""
                    r += f"{emoji} {thresh}: {data['win_rate']:.0f}% WR ({data['signals']}){curr_marker}{opt_marker}\n"
                r += "\n"

            # Post-grad analysis
            post = results.get('post_grad_analysis', {})
            if post.get('thresholds'):
                r += "<b>POST-GRAD THRESHOLDS:</b>\n"
                for thresh, data in sorted(post['thresholds'].items()):
                    emoji = "🟢" if data['win_rate'] >= 50 else "🟡" if data['win_rate'] >= 35 else "🔴"
                    curr_marker = " ←" if thresh == curr.get('post_grad_threshold') else ""
                    opt_marker = " 🎯" if thresh == post.get('optimal_threshold') and thresh != curr.get('post_grad_threshold') else ""
                    r += f"{emoji} {thresh}: {data['win_rate']:.0f}% WR ({data['signals']}){curr_marker}{opt_marker}\n"
                r += "\n"

            # KOL impact
            kol = results.get('kol_analysis', {})
            if 'kol_impact' in kol:
                impact = kol['kol_impact']
                if impact > 5:
                    r += f"<b>KOL Impact:</b> ✅ +{impact:.0f}% WR\n"
                elif impact < -5:
                    r += f"<b>KOL Impact:</b> ⚠️ {impact:.0f}% WR\n"
                else:
                    r += f"<b>KOL Impact:</b> ➖ {impact:+.0f}% WR\n"
                r += "\n"

            # Recommendations
            recs = results.get('recommendations', [])
            if recs:
                r += "<b>🎯 RECOMMENDATIONS:</b>\n"
                for rec in recs:
                    r += f"• {rec['setting']}: {rec['current']} → {rec['recommended']} ({rec['reason']})\n"
            else:
                r += "✅ <i>Current settings are optimal</i>\n"

            r += f"\n<i>Full analysis logged to Railway</i>"

            await self._send_response(update, context, r)

        except Exception as e:
            logger.error(f"❌ Optimization failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await self._send_response(update, context, f"❌ Optimization failed: {str(e)}")

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

    async def _cmd_winrate_kol(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Compare win rates: Pure Organic vs Organic + KOL backing"""
        try:
            if not self.database or not self.database.pool:
                await self._send_response(update, context, "❌ Database not available")
                return

            async with self.database.pool.acquire() as conn:
                # Get signals with KOL activity (JOIN with smart_wallet_activity)
                kol_backed_stats = await conn.fetchrow("""
                    SELECT
                        COUNT(DISTINCT s.token_address) as total,
                        SUM(CASE WHEN s.outcome IN ('2x','5x','10x','50x','100x') THEN 1 ELSE 0 END) as wins,
                        SUM(CASE WHEN s.outcome = 'rug' THEN 1 ELSE 0 END) as rugs,
                        SUM(CASE WHEN s.outcome = 'loss' THEN 1 ELSE 0 END) as losses,
                        SUM(CASE WHEN s.outcome IS NULL THEN 1 ELSE 0 END) as pending,
                        ROUND(AVG(CASE WHEN s.max_roi IS NOT NULL THEN s.max_roi END)::numeric, 2) as avg_roi,
                        ROUND(MAX(CASE WHEN s.max_roi IS NOT NULL THEN s.max_roi END)::numeric, 1) as best_roi,
                        ROUND(AVG(s.conviction_score)::numeric, 0) as avg_score
                    FROM signals s
                    WHERE s.signal_posted = TRUE
                      AND EXISTS (
                          SELECT 1 FROM smart_wallet_activity swa
                          WHERE swa.token_address = s.token_address
                      )
                """)

                # Get signals WITHOUT KOL activity (pure organic)
                organic_only_stats = await conn.fetchrow("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN outcome IN ('2x','5x','10x','50x','100x') THEN 1 ELSE 0 END) as wins,
                        SUM(CASE WHEN outcome = 'rug' THEN 1 ELSE 0 END) as rugs,
                        SUM(CASE WHEN outcome = 'loss' THEN 1 ELSE 0 END) as losses,
                        SUM(CASE WHEN outcome IS NULL THEN 1 ELSE 0 END) as pending,
                        ROUND(AVG(CASE WHEN max_roi IS NOT NULL THEN max_roi END)::numeric, 2) as avg_roi,
                        ROUND(MAX(CASE WHEN max_roi IS NOT NULL THEN max_roi END)::numeric, 1) as best_roi,
                        ROUND(AVG(conviction_score)::numeric, 0) as avg_score
                    FROM signals s
                    WHERE signal_posted = TRUE
                      AND NOT EXISTS (
                          SELECT 1 FROM smart_wallet_activity swa
                          WHERE swa.token_address = s.token_address
                      )
                """)

                # Get top KOLs by win rate
                top_kols = await conn.fetch("""
                    SELECT
                        swa.wallet_name,
                        COUNT(DISTINCT swa.token_address) as tokens,
                        SUM(CASE WHEN s.outcome IN ('2x','5x','10x','50x','100x') THEN 1 ELSE 0 END) as wins,
                        SUM(CASE WHEN s.outcome IN ('rug','loss') THEN 1 ELSE 0 END) as losses
                    FROM smart_wallet_activity swa
                    LEFT JOIN signals s ON s.token_address = swa.token_address AND s.signal_posted = TRUE
                    WHERE swa.transaction_type = 'buy'
                    GROUP BY swa.wallet_name
                    HAVING COUNT(DISTINCT swa.token_address) >= 2
                    ORDER BY
                        CASE WHEN SUM(CASE WHEN s.outcome IN ('2x','5x','10x','50x','100x') THEN 1 ELSE 0 END) +
                             SUM(CASE WHEN s.outcome IN ('rug','loss') THEN 1 ELSE 0 END) > 0
                        THEN SUM(CASE WHEN s.outcome IN ('2x','5x','10x','50x','100x') THEN 1 ELSE 0 END)::float /
                             (SUM(CASE WHEN s.outcome IN ('2x','5x','10x','50x','100x') THEN 1 ELSE 0 END) +
                              SUM(CASE WHEN s.outcome IN ('rug','loss') THEN 1 ELSE 0 END))
                        ELSE 0 END DESC
                    LIMIT 5
                """)

            # Build response
            r = "📊 <b>WIN RATE: ORGANIC vs ORGANIC+KOL</b>\n\n"

            # Pure Organic
            org = organic_only_stats
            if org and org['total'] > 0:
                decided = org['total'] - org['pending']
                wr = (org['wins'] / decided * 100) if decided > 0 else 0
                rr = (org['rugs'] / decided * 100) if decided > 0 else 0
                emoji = "🟢" if wr >= 40 else "🟡" if wr >= 25 else "🔴"

                r += f"<b>⛓ PURE ORGANIC</b> (no KOL)\n"
                r += f"{emoji} Win Rate: <b>{wr:.0f}%</b> ({org['wins']}W / {org['losses']}L / {org['rugs']}R)\n"
                r += f"   Signals: {org['total']} ({org['pending']} pending)\n"
                r += f"   Avg ROI: {org['avg_roi'] or 0}x | Best: {org['best_roi'] or 0}x\n"
                r += f"   Avg Score: {org['avg_score'] or 0}/100\n\n"
            else:
                r += "<b>⛓ PURE ORGANIC</b>\n   No data yet\n\n"

            # Organic + KOL
            kol = kol_backed_stats
            if kol and kol['total'] > 0:
                decided = kol['total'] - kol['pending']
                wr = (kol['wins'] / decided * 100) if decided > 0 else 0
                rr = (kol['rugs'] / decided * 100) if decided > 0 else 0
                emoji = "🟢" if wr >= 40 else "🟡" if wr >= 25 else "🔴"

                r += f"<b>👑 ORGANIC + KOL</b> (KOL backed)\n"
                r += f"{emoji} Win Rate: <b>{wr:.0f}%</b> ({kol['wins']}W / {kol['losses']}L / {kol['rugs']}R)\n"
                r += f"   Signals: {kol['total']} ({kol['pending']} pending)\n"
                r += f"   Avg ROI: {kol['avg_roi'] or 0}x | Best: {kol['best_roi'] or 0}x\n"
                r += f"   Avg Score: {kol['avg_score'] or 0}/100\n\n"
            else:
                r += "<b>👑 ORGANIC + KOL</b>\n   No data yet\n\n"

            # Top KOLs
            if top_kols:
                r += "<b>🏆 TOP KOLs (by win rate)</b>\n"
                for row in top_kols:
                    decided = row['wins'] + row['losses']
                    wr = (row['wins'] / decided * 100) if decided > 0 else 0
                    name = (row['wallet_name'] or 'Unknown')[:12]
                    r += f"• {name}: {wr:.0f}% ({row['wins']}W/{row['losses']}L, {row['tokens']} tokens)\n"

            r += f"\n<i>KOL backing = tracked wallet bought the token</i>"

            await self._send_response(update, context, r)

        except Exception as e:
            logger.error(f"❌ Error in /winratekol: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await self._send_response(update, context, f"❌ Error: {str(e)}")

    async def _cmd_kolstats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show ALL KOLs ranked by performance (best to worst)"""
        try:
            if not self.database or not self.database.pool:
                await self._send_response(update, context, "❌ Database not available")
                return

            await self._send_response(update, context, "📊 Analyzing KOL performance...")

            async with self.database.pool.acquire() as conn:
                # Get ALL KOLs with their performance stats
                all_kols = await conn.fetch("""
                    SELECT
                        swa.wallet_name,
                        swa.wallet_address,
                        COUNT(DISTINCT swa.token_address) as tokens,
                        SUM(CASE WHEN s.outcome IN ('2x','5x','10x','50x','100x') THEN 1 ELSE 0 END) as wins,
                        SUM(CASE WHEN s.outcome = 'rug' THEN 1 ELSE 0 END) as rugs,
                        SUM(CASE WHEN s.outcome = 'loss' THEN 1 ELSE 0 END) as losses,
                        SUM(CASE WHEN s.outcome IS NULL THEN 1 ELSE 0 END) as pending,
                        ROUND(AVG(CASE WHEN s.max_roi IS NOT NULL THEN s.max_roi END)::numeric, 2) as avg_roi
                    FROM smart_wallet_activity swa
                    LEFT JOIN signals s ON s.token_address = swa.token_address AND s.signal_posted = TRUE
                    WHERE swa.transaction_type = 'buy'
                    GROUP BY swa.wallet_name, swa.wallet_address
                    HAVING COUNT(DISTINCT swa.token_address) >= 1
                    ORDER BY
                        CASE WHEN SUM(CASE WHEN s.outcome IN ('2x','5x','10x','50x','100x') THEN 1 ELSE 0 END) +
                             SUM(CASE WHEN s.outcome IN ('rug','loss') THEN 1 ELSE 0 END) > 0
                        THEN SUM(CASE WHEN s.outcome IN ('2x','5x','10x','50x','100x') THEN 1 ELSE 0 END)::float /
                             (SUM(CASE WHEN s.outcome IN ('2x','5x','10x','50x','100x') THEN 1 ELSE 0 END) +
                              SUM(CASE WHEN s.outcome IN ('rug','loss') THEN 1 ELSE 0 END))
                        ELSE 0 END DESC
                """)

            if not all_kols:
                await self._send_response(update, context, "ℹ️ No KOL activity found in database")
                return

            # Build response
            r = "📊 <b>ALL KOL PERFORMANCE</b>\n"
            r += "<i>Ranked by win rate (best to worst)</i>\n\n"

            # Separate into tiers
            good_kols = []
            bad_kols = []
            no_data = []

            for row in all_kols:
                decided = row['wins'] + row['losses'] + row['rugs']
                if decided == 0:
                    no_data.append(row)
                else:
                    wr = (row['wins'] / decided * 100)
                    row_data = {**dict(row), 'wr': wr, 'decided': decided}
                    if wr >= 30:
                        good_kols.append(row_data)
                    else:
                        bad_kols.append(row_data)

            # Good performers
            if good_kols:
                r += "<b>✅ GOOD PERFORMERS (30%+ WR)</b>\n"
                for kol in good_kols[:10]:
                    name = (kol['wallet_name'] or 'Unknown')[:15]
                    emoji = "🟢" if kol['wr'] >= 50 else "🟡"
                    r += f"{emoji} {name}: {kol['wr']:.0f}% ({kol['wins']}W/{kol['losses']}L/{kol['rugs']}R)\n"
                r += "\n"

            # Bad performers (the ones dragging down WR)
            if bad_kols:
                r += "<b>❌ UNDERPERFORMERS (under 30% WR)</b>\n"
                # Sort by most damage (most losses/rugs)
                bad_kols.sort(key=lambda x: x['losses'] + x['rugs'], reverse=True)
                for kol in bad_kols[:10]:
                    name = (kol['wallet_name'] or 'Unknown')[:15]
                    addr = kol['wallet_address'][:8] if kol['wallet_address'] else ''
                    r += f"🔴 {name}: {kol['wr']:.0f}% ({kol['wins']}W/{kol['losses']}L/{kol['rugs']}R)\n"
                    r += f"   <code>{addr}...</code>\n"
                r += "\n"

            # Summary
            total_kols = len(good_kols) + len(bad_kols) + len(no_data)
            total_wins = sum(k.get('wins', 0) for k in good_kols + bad_kols)
            total_losses = sum(k.get('losses', 0) + k.get('rugs', 0) for k in good_kols + bad_kols)

            r += f"<b>📈 SUMMARY</b>\n"
            r += f"Total KOLs tracked: {total_kols}\n"
            r += f"Good performers: {len(good_kols)} | Bad: {len(bad_kols)} | No data: {len(no_data)}\n"
            if total_wins + total_losses > 0:
                overall_wr = total_wins / (total_wins + total_losses) * 100
                r += f"Overall KOL win rate: {overall_wr:.0f}%\n"

            if bad_kols:
                r += f"\n💡 <i>Consider removing underperformers with /removewallet</i>"

            await self._send_response(update, context, r)

        except Exception as e:
            logger.error(f"❌ Error in /kolstats: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await self._send_response(update, context, f"❌ Error: {str(e)}")

    async def _cmd_analyze(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Deep analysis of conviction scores, KOL impact, and recommendations"""
        try:
            if not self.database or not self.database.pool:
                await self._send_response(update, context, "❌ Database not available")
                return

            await self._send_response(update, context, "🔍 Running deep analysis (7 days)...")

            # Get all signals from last 7 days
            signals = await self.database.get_signals_in_last_hours(168)

            if not signals:
                await self._send_response(update, context, "ℹ️ No signals found in last 7 days")
                return

            # ===== CONVICTION SCORE ANALYSIS =====
            conviction_buckets = {
                "90-100": {"wins": 0, "total": 0, "rois": []},
                "80-89": {"wins": 0, "total": 0, "rois": []},
                "70-79": {"wins": 0, "total": 0, "rois": []},
                "60-69": {"wins": 0, "total": 0, "rois": []},
                "50-59": {"wins": 0, "total": 0, "rois": []},
                "0-49": {"wins": 0, "total": 0, "rois": []},
            }

            kol_data = {"wins": 0, "total": 0, "rois": []}
            non_kol_data = {"wins": 0, "total": 0, "rois": []}

            for s in signals:
                score = s.get('conviction_score') or 0
                entry = s.get('entry_price') or 0
                peak = s.get('max_price_reached') or 0
                kol_wallets = s.get('kol_wallets') or []

                roi = peak / entry if entry > 0 and peak > 0 else 0

                # Conviction bucket
                if score >= 90:
                    bucket = "90-100"
                elif score >= 80:
                    bucket = "80-89"
                elif score >= 70:
                    bucket = "70-79"
                elif score >= 60:
                    bucket = "60-69"
                elif score >= 50:
                    bucket = "50-59"
                else:
                    bucket = "0-49"

                conviction_buckets[bucket]["total"] += 1
                conviction_buckets[bucket]["rois"].append(roi)
                if roi >= 2.0:
                    conviction_buckets[bucket]["wins"] += 1

                # KOL tracking
                if kol_wallets and len(kol_wallets) > 0:
                    kol_data["total"] += 1
                    kol_data["rois"].append(roi)
                    if roi >= 2.0:
                        kol_data["wins"] += 1
                else:
                    non_kol_data["total"] += 1
                    non_kol_data["rois"].append(roi)
                    if roi >= 2.0:
                        non_kol_data["wins"] += 1

            # Build Part 1: Conviction Analysis
            msg1 = f"📊 <b>CONVICTION SCORE ANALYSIS</b>\n"
            msg1 += f"<i>{len(signals)} signals in 7 days</i>\n\n"
            msg1 += f"{'Score':<10} {'Sigs':<6} {'Wins':<6} {'WR':<8} {'Avg ROI':<8}\n"
            msg1 += "-" * 40 + "\n"

            for bucket, data in conviction_buckets.items():
                if data["total"] > 0:
                    wr = (data["wins"] / data["total"]) * 100
                    avg_roi = sum(data["rois"]) / len(data["rois"]) if data["rois"] else 0
                    emoji = "🟢" if wr >= 30 else "🟡" if wr >= 20 else "🔴"
                    msg1 += f"{emoji} {bucket:<8} {data['total']:<6} {data['wins']:<6} {wr:<7.0f}% {avg_roi:<.1f}x\n"

            await self._send_response(update, context, msg1)

            # Build Part 2: KOL Analysis
            msg2 = "📊 <b>KOL vs ORGANIC ANALYSIS</b>\n\n"

            if kol_data["total"] > 0:
                kol_wr = (kol_data["wins"] / kol_data["total"]) * 100
                kol_avg = sum(kol_data["rois"]) / len(kol_data["rois"]) if kol_data["rois"] else 0
                emoji = "🟢" if kol_wr >= 30 else "🟡" if kol_wr >= 20 else "🔴"
                msg2 += f"<b>👑 KOL-BACKED</b>\n"
                msg2 += f"{emoji} {kol_data['total']} signals | {kol_data['wins']} wins | {kol_wr:.0f}% WR | {kol_avg:.1f}x avg\n\n"

            if non_kol_data["total"] > 0:
                org_wr = (non_kol_data["wins"] / non_kol_data["total"]) * 100
                org_avg = sum(non_kol_data["rois"]) / len(non_kol_data["rois"]) if non_kol_data["rois"] else 0
                emoji = "🟢" if org_wr >= 30 else "🟡" if org_wr >= 20 else "🔴"
                msg2 += f"<b>⛓ PURE ORGANIC</b>\n"
                msg2 += f"{emoji} {non_kol_data['total']} signals | {non_kol_data['wins']} wins | {org_wr:.0f}% WR | {org_avg:.1f}x avg\n\n"

            if kol_data["total"] > 0 and non_kol_data["total"] > 0:
                kol_wr = (kol_data["wins"] / kol_data["total"]) * 100
                org_wr = (non_kol_data["wins"] / non_kol_data["total"]) * 100
                if org_wr > 0:
                    diff = ((kol_wr / org_wr) - 1) * 100
                    msg2 += f"💡 KOL signals are <b>{diff:+.0f}%</b> more likely to win\n"

            await self._send_response(update, context, msg2)

            # Build Part 3: Optimal Threshold
            msg3 = "📊 <b>OPTIMAL THRESHOLD ANALYSIS</b>\n\n"
            msg3 += f"{'Threshold':<12} {'Sigs':<6} {'Wins':<6} {'WR':<8}\n"
            msg3 += "-" * 35 + "\n"

            best_threshold = 60
            best_wr = 0
            for threshold in [50, 55, 60, 65, 70, 75, 80, 85, 90]:
                wins = 0
                total = 0
                for s in signals:
                    if (s.get('conviction_score') or 0) >= threshold:
                        entry = s.get('entry_price') or 0
                        peak = s.get('max_price_reached') or 0
                        if entry > 0 and peak > 0:
                            total += 1
                            if peak / entry >= 2.0:
                                wins += 1
                if total >= 5:
                    wr = (wins / total) * 100
                    emoji = "🟢" if wr >= 30 else "🟡" if wr >= 20 else "🔴"
                    msg3 += f"{emoji} {threshold}+          {total:<6} {wins:<6} {wr:<.0f}%\n"
                    if wr > best_wr:
                        best_wr = wr
                        best_threshold = threshold

            msg3 += f"\n💡 <b>RECOMMENDED: {best_threshold}+ conviction</b> ({best_wr:.0f}% WR)"

            await self._send_response(update, context, msg3)

            # Build Part 4: Worst performers
            rugs = []
            for s in signals:
                entry = s.get('entry_price') or 0
                peak = s.get('max_price_reached') or 0
                if entry > 0 and peak > 0:
                    roi = peak / entry
                    if roi < 1.2:
                        rugs.append({
                            'symbol': s.get('token_symbol', '???'),
                            'score': s.get('conviction_score', 0),
                            'roi': roi
                        })
            rugs.sort(key=lambda x: x['roi'])

            msg4 = "💀 <b>WORST PERFORMERS</b> (never hit 1.2x)\n\n"
            for r in rugs[:10]:
                msg4 += f"🔴 ${r['symbol']} → {r['roi']:.2f}x (score {r['score']})\n"

            if rugs:
                avg_rug_score = sum(r['score'] for r in rugs) / len(rugs)
                msg4 += f"\n📉 Avg score of rugs: <b>{avg_rug_score:.0f}</b>"

            await self._send_response(update, context, msg4)

            # Build Part 5: Actionable Recommendations
            msg5 = "🎯 <b>RECOMMENDED CHANGES</b>\n\n"

            # Current threshold (assume 60 if not set)
            current_threshold = getattr(config, 'MIN_CONVICTION_SCORE', 60)

            # Recommendation 1: Conviction threshold
            if best_threshold > current_threshold:
                msg5 += f"1️⃣ <b>RAISE CONVICTION THRESHOLD</b>\n"
                msg5 += f"   Current: {current_threshold} → Recommended: <b>{best_threshold}</b>\n"
                msg5 += f"   This would improve WR to {best_wr:.0f}%\n\n"
            elif best_threshold < current_threshold:
                msg5 += f"1️⃣ <b>LOWER CONVICTION THRESHOLD</b>\n"
                msg5 += f"   Current: {current_threshold} → Recommended: <b>{best_threshold}</b>\n"
                msg5 += f"   You're being too strict, missing winners\n\n"
            else:
                msg5 += f"1️⃣ <b>CONVICTION THRESHOLD OK</b>\n"
                msg5 += f"   Current {current_threshold} is optimal\n\n"

            # Recommendation 2: KOL requirement
            if kol_data["total"] > 0 and non_kol_data["total"] > 0:
                kol_wr = (kol_data["wins"] / kol_data["total"]) * 100 if kol_data["total"] > 0 else 0
                org_wr = (non_kol_data["wins"] / non_kol_data["total"]) * 100 if non_kol_data["total"] > 0 else 0

                if kol_wr > org_wr * 1.5:
                    msg5 += f"2️⃣ <b>REQUIRE KOL BACKING</b>\n"
                    msg5 += f"   KOL signals are {kol_wr/org_wr:.1f}x more likely to win\n"
                    msg5 += f"   Consider: Only signal if KOL-backed OR score 80+\n\n"
                elif kol_wr > org_wr:
                    msg5 += f"2️⃣ <b>BOOST KOL WEIGHT</b>\n"
                    msg5 += f"   KOL signals perform better but not dramatically\n"
                    msg5 += f"   Consider: Add +10 conviction for KOL backing\n\n"
                else:
                    msg5 += f"2️⃣ <b>KOL WEIGHT OK</b>\n"
                    msg5 += f"   KOLs not outperforming organic significantly\n\n"

            # Recommendation 3: Based on rug analysis
            if rugs:
                avg_rug_score = sum(r['score'] for r in rugs) / len(rugs)
                if avg_rug_score >= 60:
                    msg5 += f"3️⃣ <b>SCORING ISSUE DETECTED</b>\n"
                    msg5 += f"   Rugs have avg score of {avg_rug_score:.0f}\n"
                    msg5 += f"   High scores are not filtering rugs properly\n"
                    msg5 += f"   Review: buy/sell ratio, holder distribution\n\n"
                else:
                    msg5 += f"3️⃣ <b>SCORING WORKING</b>\n"
                    msg5 += f"   Rugs have low avg score ({avg_rug_score:.0f})\n"
                    msg5 += f"   Just need to enforce threshold strictly\n\n"

            # Summary action
            msg5 += "━━━━━━━━━━━━━━━━━━━━━\n"
            msg5 += f"<b>TL;DR:</b> Set MIN_CONVICTION_SCORE={best_threshold}"
            if kol_data["total"] > 0 and non_kol_data["total"] > 0:
                kol_wr = (kol_data["wins"] / kol_data["total"]) * 100
                org_wr = (non_kol_data["wins"] / non_kol_data["total"]) * 100
                if kol_wr > org_wr * 1.3:
                    msg5 += f"\nOR require KOL backing for scores under 75"

            await self._send_response(update, context, msg5)

        except Exception as e:
            logger.error(f"❌ Error in /analyze: {e}")
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

            # Check blacklist
            try:
                from data.kol_blacklist import is_blacklisted, get_blacklist_warning
                blacklist_info = is_blacklisted(address)
                if blacklist_info:
                    warning = get_blacklist_warning(address)
                    await self._send_response(update, context,
                        f"🚫 <b>CANNOT ADD - BLACKLISTED</b>\n\n{warning}\n\n"
                        "This wallet was removed for poor performance.\n"
                        "Review performance before re-adding.")
                    return
            except ImportError:
                pass  # Blacklist file not found, continue

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
