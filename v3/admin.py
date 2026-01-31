"""
SENTINEL V3 - Admin Bot
Essential commands only. Clean and focused.
"""
import asyncio
from telegram import Update, Bot, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode
from loguru import logger

from config import TELEGRAM_BOT_TOKEN, ADMIN_USER_ID, WEBHOOK_URL
import database as db
import helius


class AdminBot:
    """Admin bot for monitoring and management."""

    def __init__(self):
        self.app = None
        self.running = False

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

        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)

        # Register commands with Telegram menu
        await self.app.bot.set_my_commands([
            BotCommand("stats", "Overall statistics"),
            BotCommand("wallets", "Wallet performance"),
            BotCommand("active", "Currently tracking"),
            BotCommand("history", "Daily win rates"),
            BotCommand("addwallet", "Add a wallet"),
            BotCommand("rmwallet", "Remove a wallet"),
            BotCommand("syncwebhook", "Sync wallets with Helius"),
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

<b>Management:</b>
/addwallet &lt;address&gt; [name] - Add wallet
/rmwallet &lt;address&gt; - Remove wallet
/syncwebhook - Sync wallets with Helius
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

        webhook_url = f"{WEBHOOK_URL}/webhook/wallet"

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
