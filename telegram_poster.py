"""
Telegram Signal Poster for Prometheus
Posts conviction signals to Telegram channel
"""
import asyncio
from telegram import Bot
from telegram.error import TelegramError
from loguru import logger
import config

class TelegramPoster:
    """Posts signals to Telegram channel"""
    
    def __init__(self):
        """Initialize Telegram bot"""
        if not config.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN not set in environment variables")
        if not config.TELEGRAM_CHANNEL_ID:
            raise ValueError("TELEGRAM_CHANNEL_ID not set in environment variables")
            
        self.bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        self.channel_id = config.TELEGRAM_CHANNEL_ID
        logger.info(f"✅ Telegram bot initialized for channel: {self.channel_id}")
    
    async def post_signal(self, token_data, conviction_result):
        """
        Post a high-conviction signal to Telegram
        
        Args:
            token_data: Dict with token info
            conviction_result: Dict with scoring breakdown
        """
        try:
            # Format the signal message
            message = self._format_signal(token_data, conviction_result)
            
            # Post to channel
            await self.bot.send_message(
                chat_id=self.channel_id,
                text=message,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            
            logger.info(f"📤 Posted signal to Telegram: {token_data.get('token_name', 'Unknown')}")
            return True
            
        except TelegramError as e:
            logger.error(f"❌ Failed to post to Telegram: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error posting to Telegram: {e}")
            return False
    
    def _format_signal(self, token_data, conviction_result):
        """Format signal for Telegram post"""
        
        # Get basic info
        token_name = token_data.get('token_name', 'Unknown')
        token_symbol = token_data.get('token_symbol', 'UNK')
        token_address = token_data.get('token_address', 'Unknown')
        
        # Get prices
        price = token_data.get('price_usd', 0)
        bonding = token_data.get('bonding_curve_pct', 0)
        
        # Get scores
        total_score = conviction_result.get('score', 0)
        scores = conviction_result.get('scores', {})
        
        # Determine status
        is_graduated = bonding >= 100
        status = "POST-GRADUATION" if is_graduated else "PRE-GRADUATION"
        
        # Build message
        message = f"""🔥 *PROMETHEUS SIGNAL*

*${token_symbol}* - {token_name}
`{token_address[:8]}...{token_address[-6:]}`

💎 *CONVICTION: {total_score}/100*

📊 *Breakdown:*
"""
        
        # Add score breakdown
        if 'smart_wallets' in scores:
            message += f"• Elite Wallets: {scores['smart_wallets']}/40\n"
        
        if 'volume' in scores:
            message += f"• Volume: {scores['volume']}/10\n"
        
        if 'momentum' in scores:
            message += f"• Momentum: {scores['momentum']}/10\n"
        
        if 'unique_buyers' in scores:
            count = token_data.get('unique_buyers', 0)
            message += f"• Unique Buyers: {count} ({scores['unique_buyers']}/15)\n"
        elif 'holders' in scores:
            count = token_data.get('holder_count', 0)
            message += f"• Holders: {count} ({scores['holders']}/15)\n"
        
        # Add entry info
        message += f"""
📍 *Entry:* {bonding:.1f}% bonding curve
💰 *Price:* ${price:.8f}

🎯 *Status:* {status}
⚡ The fire spreads. 🔥
"""
        
        return message
    
    async def post_update(self, token_address, update_text):
        """Post an update about a signal"""
        try:
            await self.bot.send_message(
                chat_id=self.channel_id,
                text=update_text,
                parse_mode='Markdown'
            )
            return True
        except Exception as e:
            logger.error(f"❌ Failed to post update: {e}")
            return False
    
    async def test_connection(self):
        """Test Telegram connection"""
        try:
            me = await self.bot.get_me()
            logger.info(f"✅ Telegram bot connected: @{me.username}")
            
            # Try to get chat info
            chat = await self.bot.get_chat(self.channel_id)
            logger.info(f"✅ Target channel: {chat.title if hasattr(chat, 'title') else 'Channel'}")
            
            return True
        except TelegramError as e:
            logger.error(f"❌ Telegram connection test failed: {e}")
            return False
