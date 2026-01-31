"""
SENTINEL V3 - Admin Bot
Essential commands only. Clean and focused.
"""
import asyncio
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode
from loguru import logger
from datetime import datetime

from config import TELEGRAM_BOT_TOKEN, ADMIN_USER_ID
import database as db


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

        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)

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
/wallets - Tracked wallet performance
/active - Currently tracking
/history - Daily win rates

<b>Management:</b>
/addwallet &lt;address&gt; [name] - Add wallet
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

            emoji = "" if mult >= 1 else ""
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

            bar = "" * int(wr / 10) + "" * (10 - int(wr / 10))
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
                f"Added wallet: {name or address[:8]}\n"
                f"Tier: new\n\n"
                f"Run /syncwebhook to register with Helius."
            )
        else:
            await update.message.reply_text("Wallet already exists.")
