"""
SENTINEL V3 - Telegram Poster
Posts signals and milestone updates to Telegram channel.
"""
import asyncio
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError
from loguru import logger
from typing import Optional, Dict

from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHANNEL_ID,
    BANNER_SIGNAL,
    BANNER_2X,
    BANNER_10X,
    BANNER_100X
)
import database as db


class TelegramPoster:
    """Posts signals and updates to Telegram."""

    def __init__(self):
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN) if TELEGRAM_BOT_TOKEN else None
        self.channel_id = TELEGRAM_CHANNEL_ID

    async def post_signal(self, signal: Dict, breakdown: Dict) -> Optional[int]:
        """
        Post a new signal to Telegram.
        Returns message_id if successful.
        """
        if not self.bot or not self.channel_id:
            logger.warning("Telegram not configured")
            return None

        try:
            # Build message
            text = self._format_signal(signal, breakdown)

            # Post with banner if available
            if BANNER_SIGNAL:
                msg = await self.bot.send_animation(
                    chat_id=self.channel_id,
                    animation=BANNER_SIGNAL,
                    caption=text,
                    parse_mode=ParseMode.HTML
                )
            else:
                msg = await self.bot.send_message(
                    chat_id=self.channel_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )

            logger.info(f"Posted signal: {signal['symbol']} (msg_id: {msg.message_id})")
            return msg.message_id

        except TelegramError as e:
            logger.error(f"Telegram error posting signal: {e}")
            return None

    async def post_milestone(self, signal: Dict, multiplier: int, price: float) -> Optional[int]:
        """Post a milestone update."""
        if not self.bot or not self.channel_id:
            return None

        try:
            text = self._format_milestone(signal, multiplier, price)
            banner = self._get_milestone_banner(multiplier)

            if banner:
                msg = await self.bot.send_animation(
                    chat_id=self.channel_id,
                    animation=banner,
                    caption=text,
                    parse_mode=ParseMode.HTML
                )
            else:
                msg = await self.bot.send_message(
                    chat_id=self.channel_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )

            # Update milestone with message ID
            await db.update_milestone_message(signal['id'], multiplier, msg.message_id)

            logger.info(f"Posted milestone: {signal['symbol']} {multiplier}x")
            return msg.message_id

        except TelegramError as e:
            logger.error(f"Telegram error posting milestone: {e}")
            return None

    def _format_signal(self, signal: Dict, breakdown: Dict) -> str:
        """Format signal message."""
        symbol = signal.get('symbol', 'UNKNOWN')
        name = signal.get('name', 'Unknown Token')
        token_address = signal['token_address']
        wallet_tier = signal.get('wallet_tier', 'unknown')
        score = signal.get('score', 0)
        mcap = signal.get('entry_mcap', 0)
        liquidity = signal.get('entry_liquidity', 0)
        holders = signal.get('entry_holders', 0)

        # Links
        dex_link = f"https://dexscreener.com/solana/{token_address}"
        pump_link = f"https://pump.fun/{token_address}"

        # Score breakdown
        w = breakdown.get('wallet', {})
        v = breakdown.get('volume', {})
        m = breakdown.get('momentum', {})
        h = breakdown.get('holders', {})

        text = f"""
<b>NEW SIGNAL</b>

<b>${symbol}</b> - {name}

<b>Score:</b> {score}/100
├ Wallet ({wallet_tier}): {w.get('score', 0)}/40
├ Volume ({v.get('ratio', 0):.1f}x): {v.get('score', 0)}/20
├ Momentum ({m.get('price_change_1h', 0):+.1f}%): {m.get('score', 0)}/20
└ Holders ({h.get('count', 0)}): {h.get('score', 0)}/20

<b>Metrics:</b>
├ MCAP: ${mcap:,.0f}
├ Liquidity: ${liquidity:,.0f}
└ Holders: {holders}

<a href="{dex_link}">DexScreener</a> | <a href="{pump_link}">Pump.fun</a>

<code>{token_address}</code>
"""
        return text.strip()

    def _format_milestone(self, signal: Dict, multiplier: int, price: float) -> str:
        """Format milestone message."""
        symbol = signal.get('symbol', 'UNKNOWN')
        token_address = signal['token_address']
        entry_price = signal.get('entry_price', 0)

        # Determine tier name
        if multiplier >= 100:
            tier = "INFERNO"
        elif multiplier >= 10:
            tier = "SCORCHED EARTH"
        elif multiplier >= 5:
            tier = "HELL FIRE"
        else:
            tier = "LET IT BURN"

        dex_link = f"https://dexscreener.com/solana/{token_address}"

        text = f"""
<b>{tier}</b>

<b>${symbol}</b> hit <b>{multiplier}x</b>!

Entry: ${entry_price:.10f}
Now: ${price:.10f}

<a href="{dex_link}">DexScreener</a>

<code>{token_address}</code>
"""
        return text.strip()

    def _get_milestone_banner(self, multiplier: int) -> Optional[str]:
        """Get appropriate banner for milestone."""
        if multiplier >= 100:
            return BANNER_100X
        elif multiplier >= 10:
            return BANNER_10X
        elif multiplier >= 2:
            return BANNER_2X
        return None


async def send_admin_message(text: str) -> bool:
    """Send a message to the admin (used for alerts)."""
    from config import ADMIN_USER_ID

    if not TELEGRAM_BOT_TOKEN or not ADMIN_USER_ID:
        return False

    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(
            chat_id=ADMIN_USER_ID,
            text=text,
            parse_mode=ParseMode.HTML
        )
        return True
    except TelegramError as e:
        logger.error(f"Failed to send admin message: {e}")
        return False
