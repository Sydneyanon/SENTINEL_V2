"""
Telegram Publisher - Post signals to channel
"""
from typing import Dict, Any, Optional
from datetime import datetime
from loguru import logger
from telegram import Bot
from telegram.error import TelegramError
import config


class TelegramPublisher:
    """Publishes trading signals to Telegram channel"""
    
    def __init__(self):
        self.bot: Optional[Bot] = None
        self.channel_id = config.TELEGRAM_CHANNEL_ID
        self.enabled = config.ENABLE_TELEGRAM
        
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
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize Telegram: {e}")
            return False
    
    def _format_signal(self, signal_data: Dict[str, Any]) -> str:
        """Format signal data into Telegram message"""
        
        symbol = signal_data.get('symbol', 'UNKNOWN')
        token_address = signal_data.get('token_address', 'N/A')
        conviction = signal_data.get('conviction_score', 0)
        
        # Get conviction breakdown
        breakdown = signal_data.get('breakdown', {})
        reasons = signal_data.get('reasons', [])
        
        # Get metrics
        price = signal_data.get('price', 0)
        mcap = signal_data.get('market_cap', 0)
        liquidity = signal_data.get('liquidity', 0)
        holders = signal_data.get('holders', 0)
        age_minutes = signal_data.get('age_minutes', 0)
        
        # Get smart wallet activity
        wallet_data = signal_data.get('wallet_activity', {})
        wallets = wallet_data.get('wallets', [])
        
        # Get narrative data
        narrative_data = signal_data.get('narrative_data', {})
        narratives = narrative_data.get('narratives', [])
        
        # Fire emojis based on conviction
        fire_count = min(conviction // 20, 5)
        fire_emojis = "🔥" * fire_count
        
        # Build message
        message = f"""🎯 **NEW SIGNAL** {fire_emojis}

**${symbol}**
**Conviction: {conviction}/100**

💰 Price: ${price:.8f}
💎 MCap: ${mcap:,.0f}
💧 Liquidity: ${liquidity:,.0f}
👥 Holders: {holders}
⏱️ Age: {age_minutes:.0f}m

"""
        
        # Add conviction reasons
        if reasons:
            message += "**Why This Signal:**\n"
            for reason in reasons:
                message += f"{reason}\n"
            message += "\n"
        
        # Add smart wallet activity
        if wallets:
            message += "**👑 Smart Money Activity:**\n"
            for wallet in wallets[:3]:  # Show top 3
                name = wallet.get('name', 'Unknown')
                tier = wallet.get('tier', '')
                win_rate = wallet.get('win_rate', 0)
                mins_ago = wallet.get('minutes_ago', 0)
                
                tier_emoji = "🏆" if tier == 'elite' else "👑"
                message += f"{tier_emoji} {name} ({win_rate*100:.0f}% WR) - {mins_ago:.0f}m ago\n"
            message += "\n"
        
        # Add narrative info
        if narratives:
            message += "**📈 Narratives:**\n"
            for narrative in narratives[:2]:  # Show top 2
                name = narrative.get('name', '').upper()
                message += f"• {name}\n"
            message += "\n"
        
        # Add links
        message += f"""🔗 [DexScreener](https://dexscreener.com/solana/{token_address})
🔗 [Birdeye](https://birdeye.so/token/{token_address})
📋 `{token_address}`

⚠️ DYOR - Not financial advice"""
        
        return message
    
    async def post_signal(self, signal_data: Dict[str, Any]) -> bool:
        """Post signal to Telegram channel"""
        
        if not self.enabled or not self.bot or not self.channel_id:
            logger.debug("Telegram not enabled - skipping post")
            return False
        
        try:
            message = self._format_signal(signal_data)
            
            await self.bot.send_message(
                chat_id=self.channel_id,
                text=message,
                parse_mode='Markdown',
                disable_web_page_preview=False
            )
            
            symbol = signal_data.get('symbol', 'UNKNOWN')
            conviction = signal_data.get('conviction_score', 0)
            logger.info(f"📤 Posted signal to Telegram: ${symbol} ({conviction}/100)")
            return True
            
        except TelegramError as e:
            logger.error(f"❌ Telegram error: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error posting to Telegram: {e}")
            return False
    
    async def post_test_message(self) -> bool:
        """Post a test message to verify bot is working"""
        
        if not self.bot or not self.channel_id:
            logger.error("Bot not initialized")
            return False
        
        try:
            test_message = f"""🤖 **Bot Test Message**

✅ Telegram connection working
⏰ Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

This is a test message to verify the bot can post to the channel."""
            
            await self.bot.send_message(
                chat_id=self.channel_id,
                text=test_message,
                parse_mode='Markdown'
            )
            
            logger.info("✅ Test message posted successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to post test message: {e}")
            return False
