"""
SENTINEL V3 - Admin Bot
Essential commands only. Clean and focused.
"""
import asyncio
from telegram import Update, Bot, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.constants import ParseMode
from loguru import logger

from config import TELEGRAM_BOT_TOKEN, ADMIN_USER_ID, WEBHOOK_URL
import config
import database as db
import helius
from discovery import get_discovery


class AdminBot:
    """Admin bot for monitoring and management."""

    def __init__(self):
        self.app = None
        self.running = False
        self.pending_media_type = None  # Tracks what media is expected (banner, multiplier_2x, etc.)

    async def start(self):
        """Start the admin bot."""
        if not TELEGRAM_BOT_TOKEN or not ADMIN_USER_ID:
            logger.warning("Admin bot disabled (no token or admin ID)")
            return

        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Register commands
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("help", self._cmd_help))
        self.app.add_handler(CommandHandler("stats", self._cmd_stats))
        self.app.add_handler(CommandHandler("wallets", self._cmd_wallets))
        self.app.add_handler(CommandHandler("active", self._cmd_active))
        self.app.add_handler(CommandHandler("history", self._cmd_history))
        self.app.add_handler(CommandHandler("addwallet", self._cmd_add_wallet))
        self.app.add_handler(CommandHandler("rmwallet", self._cmd_rm_wallet))
        self.app.add_handler(CommandHandler("syncwebhook", self._cmd_sync_webhook))
        self.app.add_handler(CommandHandler("setbanner", self._cmd_setbanner))
        self.app.add_handler(CommandHandler("setmultiplier", self._cmd_setmultiplier))
        self.app.add_handler(CommandHandler("smartmoney", self._cmd_smartmoney))
        self.app.add_handler(CommandHandler("discover", self._cmd_discover))
        self.app.add_handler(CommandHandler("cleanup", self._cmd_cleanup))

        # Media upload handler
        self.app.add_handler(MessageHandler(
            filters.VIDEO | filters.ANIMATION | filters.Document.VIDEO,
            self._handle_media_upload
        ))

        await self.app.initialize()

        # Clear any existing connections before starting
        await self.app.bot.delete_webhook(drop_pending_updates=True)

        await self.app.start()

        # Retry polling with backoff in case of conflict
        for attempt in range(3):
            try:
                await self.app.updater.start_polling(drop_pending_updates=True)
                break
            except Exception as e:
                if "Conflict" in str(e) and attempt < 2:
                    wait = (attempt + 1) * 5
                    logger.warning(f"Bot conflict, retrying in {wait}s...")
                    await asyncio.sleep(wait)
                else:
                    raise

        # Register commands with Telegram menu
        await self.app.bot.set_my_commands([
            BotCommand("stats", "Overall statistics"),
            BotCommand("wallets", "Wallet performance"),
            BotCommand("active", "Currently tracking"),
            BotCommand("history", "Daily win rates"),
            BotCommand("smartmoney", "Smart money stats"),
            BotCommand("discover", "Run wallet discovery"),
            BotCommand("addwallet", "Add a wallet"),
            BotCommand("rmwallet", "Remove a wallet"),
            BotCommand("syncwebhook", "Sync wallets with Helius"),
            BotCommand("setbanner", "Set signal banner"),
            BotCommand("setmultiplier", "Set milestone banners"),
            BotCommand("help", "Show commands"),
        ])

        self.running = True
        logger.info(f"Admin bot started (admin: {ADMIN_USER_ID})")

    async def stop(self):
        """Stop the admin bot."""
        if self.app and self.running:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            self.running = False
            logger.info("Admin bot stopped")

    def _is_admin(self, update: Update) -> bool:
        """Check if user is admin."""
        return update.effective_user.id == ADMIN_USER_ID

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        if not self._is_admin(update):
            return

        await update.message.reply_text(
            "<b>SENTINEL V3</b>\n\n"
            "Clean. Simple. Focused.\n\n"
            "Use /help to see commands.",
            parse_mode=ParseMode.HTML
        )

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        if not self._is_admin(update):
            return

        text = """
<b>SENTINEL V3 Commands</b>

<b>Monitoring:</b>
/stats - Overall statistics
/wallets - Wallet performance
/active - Currently tracking
/history - Daily win rates

<b>Smart Money:</b>
/smartmoney - View discovered wallets
/discover - Run discovery now

<b>Management:</b>
/addwallet &lt;address&gt; [name] - Add wallet
/rmwallet &lt;address&gt; - Remove wallet
/syncwebhook - Sync wallets with Helius

<b>Banners:</b>
/setbanner - Set signal banner (send video)
/setmultiplier - Set milestone banners
"""
        await update.message.reply_text(text.strip(), parse_mode=ParseMode.HTML)

    async def _cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command."""
        if not self._is_admin(update):
            return

        stats = await db.get_stats()

        text = f"""
<b>SENTINEL V3 Stats</b>

<b>Signals:</b>
├ Total: {stats['total_signals']}
├ Last 24h: {stats['signals_24h']}
├ Wins: {stats['total_wins']}
├ Rugs: {stats['total_rugs']}
└ Win Rate: {stats['win_rate']:.1f}%

<b>Wallets:</b> {stats['total_wallets']}
"""

        if stats['best_performer']:
            bp = stats['best_performer']
            text += f"\n<b>Best:</b> ${bp['symbol']} ({bp['max_multiplier']:.1f}x)"

        await update.message.reply_text(text.strip(), parse_mode=ParseMode.HTML)

    async def _cmd_wallets(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /wallets command."""
        if not self._is_admin(update):
            return

        wallets = await db.get_all_wallets()

        if not wallets:
            await update.message.reply_text("No wallets tracked.")
            return

        lines = ["<b>Tracked Wallets</b>\n"]

        for w in wallets[:20]:  # Top 20
            name = w['name'] or w['address'][:8]
            signals = w['signals']
            wins = w['wins']
            wr = (wins / signals * 100) if signals > 0 else 0
            tier = w['tier']

            lines.append(f"<b>{name}</b> [{tier}]")
            lines.append(f"  {wins}/{signals} signals ({wr:.0f}% WR)")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

    async def _cmd_active(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /active command."""
        if not self._is_admin(update):
            return

        signals = await db.get_active_signals()

        if not signals:
            await update.message.reply_text("No active signals.")
            return

        lines = ["<b>Active Signals</b>\n"]

        for s in signals[:10]:
            symbol = s['symbol'] or 'UNKNOWN'
            mult = s['current_multiplier'] or 1.0
            max_mult = s['max_multiplier'] or 1.0

            emoji = "📈" if mult >= 1 else "📉"
            lines.append(f"{emoji} <b>${symbol}</b>: {mult:.2f}x (max: {max_mult:.2f}x)")

        lines.append(f"\nTotal: {len(signals)} active")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

    async def _cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /history command."""
        if not self._is_admin(update):
            return

        # Get days from args
        days = 7
        if context.args:
            try:
                days = int(context.args[0])
            except ValueError:
                pass

        daily = await db.get_daily_stats(days)

        if not daily:
            await update.message.reply_text("No history data.")
            return

        lines = [f"<b>Daily Win Rate ({days}d)</b>\n"]

        for d in daily:
            date = d['date'].strftime('%m/%d')
            signals = d['signals']
            wins = d['wins']
            wr = (wins / signals * 100) if signals > 0 else 0

            filled = int(wr / 10)
            bar = "█" * filled + "░" * (10 - filled)
            lines.append(f"{date}: {bar} {wr:.0f}% ({wins}/{signals})")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

    async def _cmd_add_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /addwallet command."""
        if not self._is_admin(update):
            return

        if not context.args:
            await update.message.reply_text(
                "Usage: /addwallet <address> [name]\n"
                "Example: /addwallet ABC123... TraderJoe"
            )
            return

        address = context.args[0]
        name = context.args[1] if len(context.args) > 1 else None

        # Validate address length
        if len(address) < 32:
            await update.message.reply_text("Invalid address (too short)")
            return

        success = await db.add_wallet(address, name, 'new')

        if success:
            await update.message.reply_text(
                f"✅ Added wallet: {name or address[:8]}\n"
                f"Tier: new\n\n"
                f"Run /syncwebhook to register with Helius."
            )
        else:
            await update.message.reply_text("Wallet already exists.")

    async def _cmd_rm_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /rmwallet command."""
        if not self._is_admin(update):
            return

        if not context.args:
            await update.message.reply_text(
                "Usage: /rmwallet <address>\n"
                "Example: /rmwallet ABC123..."
            )
            return

        address = context.args[0]

        # Check if wallet exists
        wallet = await db.get_wallet(address)
        if not wallet:
            await update.message.reply_text("Wallet not found.")
            return

        # Remove from database
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute('DELETE FROM wallets WHERE address = $1', address)

        name = wallet['name'] or address[:8]
        await update.message.reply_text(
            f"✅ Removed wallet: {name}\n\n"
            f"Run /syncwebhook to update Helius."
        )

    async def _cmd_sync_webhook(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /syncwebhook command."""
        if not self._is_admin(update):
            return

        await update.message.reply_text("Syncing wallets with Helius...")

        # Get all wallets
        wallets = await db.get_all_wallets()

        if not wallets:
            await update.message.reply_text("No wallets to sync.")
            return

        # Get webhook URL from config
        if not WEBHOOK_URL:
            await update.message.reply_text(
                "❌ WEBHOOK_URL not set in Railway env vars.\n\n"
                "Set it to your Railway app URL, e.g.:\n"
                "<code>https://xxx.railway.app</code>",
                parse_mode=ParseMode.HTML
            )
            return

        webhook_url = f"{WEBHOOK_URL.strip().rstrip('/')}/webhook/wallet"

        # Get wallet addresses
        addresses = [w['address'] for w in wallets]

        # Sync with Helius
        result = await helius.sync_wallets(addresses, webhook_url)

        if result['success']:
            await update.message.reply_text(
                f"✅ Webhook synced!\n\n"
                f"Wallets: {result['wallets_synced']}\n"
                f"Webhook ID: <code>{result['webhook_id']}</code>\n"
                f"URL: {webhook_url}",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                f"❌ Sync failed: {result['message']}"
            )

    async def _cmd_setbanner(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set signal banner: /setbanner then send video."""
        if not self._is_admin(update):
            return

        self.pending_media_type = 'banner'
        await update.message.reply_text(
            "🎬 <b>Banner Setup Mode</b>\n\n"
            "Send me the video/animation for signal alerts.\n\n"
            "Supported: MP4 videos, GIFs, animations",
            parse_mode=ParseMode.HTML
        )

    async def _cmd_setmultiplier(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set milestone banners: /setmultiplier <tier>"""
        if not self._is_admin(update):
            return

        valid_tiers = ['2x', '10x', '100x']

        if not context.args or context.args[0].lower() not in valid_tiers:
            # Show current status
            current = {
                '2x': getattr(config, 'MILESTONE_BANNER_2X', None),
                '10x': getattr(config, 'MILESTONE_BANNER_10X', None),
                '100x': getattr(config, 'MILESTONE_BANNER_100X', None),
            }

            lines = ["🎯 <b>Milestone Banners</b>\n"]
            for tier, val in current.items():
                status = "✅" if val else "❌"
                lines.append(f"{status} <b>{tier}</b>: {'Set' if val else 'Not set'}")

            lines.append("\n<b>Usage:</b>")
            lines.append("<code>/setmultiplier 2x</code> - then send video")
            lines.append("<code>/setmultiplier 10x</code> - then send video")
            lines.append("<code>/setmultiplier 100x</code> - then send video")

            await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
            return

        tier = context.args[0].lower()
        self.pending_media_type = f'multiplier_{tier}'

        tier_names = {
            '2x': '🔥 2x Milestone',
            '10x': '☄️ 10x Milestone',
            '100x': '🌋 100x Milestone',
        }

        await update.message.reply_text(
            f"🎯 <b>{tier_names.get(tier, tier)} Setup</b>\n\n"
            f"Send me the video/animation for <b>{tier}</b> alerts.\n\n"
            f"Supported: MP4 videos, GIFs, animations",
            parse_mode=ParseMode.HTML
        )

    async def _handle_media_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle uploaded media for banners."""
        if not self._is_admin(update):
            return

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
            media_type = "document"

        if not file_id:
            return

        logger.info(f"Admin uploaded {media_type}, file_id: {file_id}")

        pending = self.pending_media_type
        self.pending_media_type = None

        if pending == 'banner' or pending is None:
            config.BANNER_SIGNAL = file_id
            env_var = 'TELEGRAM_BANNER_FILE_ID'
            description = "Signal Banner"

        elif pending.startswith('multiplier_'):
            tier = pending.replace('multiplier_', '')
            tier_map = {
                '2x': ('MILESTONE_BANNER_2X', '2x Milestone'),
                '10x': ('MILESTONE_BANNER_10X', '10x Milestone'),
                '100x': ('MILESTONE_BANNER_100X', '100x Milestone'),
            }
            env_var, description = tier_map.get(tier, ('UNKNOWN', tier))

            if tier == '2x':
                config.MILESTONE_BANNER_2X = file_id
            elif tier == '10x':
                config.MILESTONE_BANNER_10X = file_id
            elif tier == '100x':
                config.MILESTONE_BANNER_100X = file_id
        else:
            env_var = 'TELEGRAM_BANNER_FILE_ID'
            description = "Banner"

        await msg.reply_text(
            f"🎬 <b>{description} Captured!</b>\n\n"
            f"Type: <code>{media_type}</code>\n"
            f"File ID:\n<code>{file_id}</code>\n\n"
            f"✅ <b>Applied in memory</b>\n\n"
            f"For persistence, set in Railway:\n"
            f"<code>{env_var}={file_id}</code>",
            parse_mode=ParseMode.HTML
        )

    async def _cmd_smartmoney(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /smartmoney command - view discovered wallets."""
        if not self._is_admin(update):
            return

        # Get smart money stats
        stats = await db.get_smart_money_stats()

        lines = ["<b>🔍 Smart Money Discovery</b>\n"]
        lines.append(f"<b>Discovered:</b> {stats['total_discovered']} wallets")
        lines.append(f"<b>Tracking:</b> {stats['tracking']} wallets\n")

        lines.append("<b>By Tier:</b>")
        lines.append(f"├ Elite: {stats['by_tier']['elite']}")
        lines.append(f"├ Smart Money: {stats['by_tier']['smart_money']}")
        lines.append(f"└ Verified: {stats['by_tier']['verified']}\n")

        if stats['signals'] > 0:
            lines.append("<b>Performance (tracked):</b>")
            lines.append(f"├ Signals: {stats['signals']}")
            lines.append(f"├ Wins: {stats['wins']}")
            lines.append(f"└ Win Rate: {stats['win_rate']:.1f}%")

        # Show top wallets if requested with 'list'
        if context.args and context.args[0].lower() == 'list':
            wallets = await db.get_smart_money_wallets()
            if wallets:
                lines.append("\n<b>Top Discovered:</b>")
                for w in wallets[:10]:
                    tracking = "✅" if w['is_tracking'] else "⏸"
                    lines.append(
                        f"{tracking} <code>{w['address'][:8]}...</code> "
                        f"WR:{w['win_rate']:.0f}% PNL:${w['pnl_30d']:,.0f}"
                    )

        lines.append("\n<i>Use /smartmoney list for wallet list</i>")
        lines.append("<i>Use /discover to run discovery now</i>")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

    async def _cmd_discover(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /discover command - manually trigger wallet discovery."""
        if not self._is_admin(update):
            return

        if not config.APIFY_API_TOKEN:
            await update.message.reply_text(
                "❌ <b>APIFY_API_TOKEN not set</b>\n\n"
                "Set it in Railway env vars to enable discovery.\n"
                "Get your token from: https://console.apify.com/account/integrations",
                parse_mode=ParseMode.HTML
            )
            return

        await update.message.reply_text(
            "🔍 <b>Starting Discovery...</b>\n\n"
            "This may take 1-2 minutes.\n"
            "Using GMGN Smart Degen scraper via Apify.",
            parse_mode=ParseMode.HTML
        )

        # Run discovery
        discovery = get_discovery()
        result = await discovery.run_discovery()

        if result['success']:
            # Show new wallets in the response
            new_wallets = result.get('new_wallets', [])
            wallet_lines = ""
            if new_wallets:
                wallet_lines = "\n<b>New wallets:</b>\n"
                for w in new_wallets[:5]:
                    wallet_lines += (
                        f"• <code>{w['address'][:8]}...</code> "
                        f"({w['win_rate']:.0f}% WR)\n"
                    )

            await update.message.reply_text(
                f"✅ <b>Discovery Complete!</b>\n\n"
                f"Discovered: {result['discovered']} wallets\n"
                f"Added to tracking: {result['added_to_tracking']}"
                f"{wallet_lines}\n"
                f"Use /smartmoney to view stats.",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                f"❌ <b>Discovery Failed</b>\n\n"
                f"{result['message']}",
                parse_mode=ParseMode.HTML
            )

    async def _cmd_cleanup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cleanup command - remove underperforming wallets."""
        if not self._is_admin(update):
            return

        await update.message.reply_text(
            "🧹 <b>Running Cleanup...</b>\n\n"
            "Removing wallets with <30% WR after 30 days.",
            parse_mode=ParseMode.HTML
        )

        removed = await db.cleanup_stale_smart_money(days_inactive=30, min_signals=3)

        if removed > 0:
            await update.message.reply_text(
                f"✅ <b>Cleanup Complete</b>\n\n"
                f"Removed {removed} underperforming wallets.\n\n"
                f"Run /syncwebhook to update Helius.",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                "✅ No stale wallets found.\n\n"
                "All tracked wallets are performing well!",
                parse_mode=ParseMode.HTML
            )
