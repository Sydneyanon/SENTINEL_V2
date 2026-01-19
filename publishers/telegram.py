"""
Telegram Publisher - Post signals to channel with animated banner
"""
from typing import Dict, Any, Optional
from datetime import datetime
from loguru import logger
from telegram import Bot
from telegram.error import TelegramError
from telegram.constants import ParseMode
import config


class TelegramPublisher:
    """Publishes trading signals to Telegram channel"""
    
    def __init__(self):
        self.bot: Optional[Bot] = None
        self.channel_id = config.TELEGRAM_CHANNEL_ID
        self.enabled = config.ENABLE_TELEGRAM
        # Use file_id from config, or fallback to this one
        self.banner_file_id = getattr(config, 'TELEGRAM_BANNER_FILE_ID', 
                                      "AAMCBQADGQEAARo2t2luZc3uCBRvzP8MzukkPSpP2vhVAALUHAAC6vxxV7_SZXW_LNdlAQAHbQADOAQ")
        
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
            
            if self.banner_file_id:
                logger.info("🎨 Animated banner enabled")
            else:
                logger.info("ℹ️ No banner configured - signals will be text-only")
            
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize Telegram: {e}")
            return False
    
    def _format_signal(self, signal_data: Dict[str, Any]) -> str:
        """Format signal data into Telegram message"""
        
        # Extract token data
        token_data = signal_data.get('token_data', {})
        
        symbol = token_data.get('token_symbol', signal_data.get('symbol', 'UNKNOWN'))
        token_address = token_data.get('token_address', signal_data.get('token_address', 'N/A'))
        conviction = signal_data.get('score', signal_data.get('conviction_score', 0))
        
        # Get conviction breakdown
        breakdown = signal_data.get('breakdown', {})
        
        # Get metrics
        price = token_data.get('price_usd', signal_data.get('price', 0))
        mcap = token_data.get('market_cap', signal_data.get('market_cap', 0))
        liquidity = token_data.get('liquidity', signal_data.get('liquidity', 0))
        holders = token_data.get('holder_count', signal_data.get('holders', 0))
        bonding = token_data.get('bonding_curve_pct', 0)
        
        # Calculate age if we have created_timestamp
        age_minutes = 0
        created_ts = token_data.get('created_timestamp')
        if created_ts:
            age_seconds = (datetime.utcnow().timestamp() - created_ts)
            age_minutes = age_seconds / 60
        
        # Get smart wallet activity
        wallet_data = signal_data.get('smart_wallet_data', {})
        wallets = wallet_data.get('wallets', [])
        elite_count = wallet_data.get('elite_count', 0)
        kol_count = wallet_data.get('top_kol_count', 0)
        
        # Get narrative data
        narrative_data = signal_data.get('narrative_data', {})
        narratives = narrative_data.get('narratives', [])
        
        # Fire emojis based on conviction
        fire_count = min(conviction // 20, 5)
        fire_emojis = "🔥" * fire_count
        
        # Build message with HTML formatting (better for animations)
        message = f"""🎯 <b>NEW SIGNAL</b> {fire_emojis}

<b>${symbol}</b>
<b>Conviction: {conviction}/100</b>

💰 Price: ${price:.8f}
💎 MCap: ${mcap:,.0f}
💧 Liquidity: ${liquidity:,.0f}
👥 Holders: {holders}
📊 Bonding: {bonding:.1f}%
"""
        
        if age_minutes > 0:
            message += f"⏱️ Age: {age_minutes:.0f}m\n"
        
        message += "\n"
        
        # Add conviction breakdown
        if breakdown:
            message += "<b>📊 Score Breakdown:</b>\n"
            if breakdown.get('smart_wallet', 0) > 0:
                message += f"👑 Smart Wallets: {breakdown['smart_wallet']}\n"
            if breakdown.get('narrative', 0) > 0:
                message += f"📈 Narratives: {breakdown['narrative']}\n"
            if breakdown.get('holders', 0) > 0:
                message += f"👥 Holders: {breakdown['holders']}\n"
            if breakdown.get('volume_velocity', 0) > 0:
                message += f"📊 Volume: {breakdown['volume_velocity']}\n"
            if breakdown.get('momentum', 0) > 0:
                message += f"🚀 Momentum: {breakdown['momentum']}\n"
            message += "\n"
        
        # Add smart wallet activity
        if wallets or elite_count > 0 or kol_count > 0:
            message += "<b>👑 Smart Money Activity:</b>\n"
            if elite_count > 0:
                message += f"🏆 {elite_count} Elite trader(s)\n"
            if kol_count > 0:
                message += f"👑 {kol_count} Top KOL(s)\n"
            
            for wallet in wallets[:3]:  # Show top 3
                name = wallet.get('name', 'Unknown')
                tier = wallet.get('tier', '')
                win_rate = wallet.get('win_rate', 0)
                mins_ago = wallet.get('minutes_ago', 0)
                
                tier_emoji = "🏆" if tier == 'elite' else "👑"
                if win_rate > 0:
                    message += f"{tier_emoji} {name} ({win_rate*100:.0f}% WR) - {mins_ago:.0f}m ago\n"
                else:
                    message += f"{tier_emoji} {name} - {mins_ago:.0f}m ago\n"
            message += "\n"
        
        # Add narrative info
        if narratives:
            message += "<b>📈 Narratives:</b>\n"
            for narrative in narratives[:2]:  # Show top 2
                name = narrative.get('name', '').upper()
                message += f"• {name}\n"
            message += "\n"
        
        # Add links
        message += f"""🔗 <a href="https://dexscreener.com/solana/{token_address}">DexScreener</a>
🔗 <a href="https://birdeye.so/token/{token_address}">Birdeye</a>
🔗 <a href="https://pump.fun/{token_address}">Pump.fun</a>

<code>{token_address}</code>

⚠️ DYOR - Not financial advice"""
        
        return message
    
    async def post_signal(self, signal_data: Dict[str, Any]) -> Optional[int]:
        """
        Post signal to Telegram channel with animated banner
        
        Returns:
            Message ID if successful, None otherwise
        """
        
        if not self.enabled or not self.bot or not self.channel_id:
            logger.debug("Telegram not enabled - skipping post")
            return None
        
        try:
            message = self._format_signal(signal_data)
            
            # If we have a banner, send as animation with caption
            if self.banner_file_id:
                result = await self.bot.send_animation(
                    chat_id=self.channel_id,
                    animation=self.banner_file_id,
                    caption=message,
                    parse_mode=ParseMode.HTML,
                    disable_notification=False
                )
            else:
                # Fallback to regular message if no banner
                result = await self.bot.send_message(
                    chat_id=self.channel_id,
                    text=message,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=False
                )
            
            # Extract symbol for logging
            token_data = signal_data.get('token_data', {})
            symbol = token_data.get('token_symbol', signal_data.get('symbol', 'UNKNOWN'))
            conviction = signal_data.get('score', signal_data.get('conviction_score', 0))
            
            logger.info(f"📤 Posted signal to Telegram: ${symbol} ({conviction}/100)")
            return result.message_id
            
        except TelegramError as e:
            logger.error(f"❌ Telegram error: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error posting to Telegram: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    async def post_test_message(self) -> bool:
        """Post a test message to verify bot is working"""
        
        if not self.bot or not self.channel_id:
            logger.error("Bot not initialized")
            return False
        
        try:
            test_message = f"""🤖 <b>Bot Test Message</b>

✅ Telegram connection working
⏰ Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

This is a test message to verify the bot can post to the channel."""
            
            if self.banner_file_id:
                # Send with banner if available
                await self.bot.send_animation(
                    chat_id=self.channel_id,
                    animation=self.banner_file_id,
                    caption=test_message,
                    parse_mode=ParseMode.HTML
                )
            else:
                await self.bot.send_message(
                    chat_id=self.channel_id,
                    text=test_message,
                    parse_mode=ParseMode.HTML
                )
            
            logger.info("✅ Test message posted successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to post test message: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def upload_banner(self, banner_path: str) -> Optional[str]:
        """
        Upload banner GIF and return file_id for future use
        
        Args:
            banner_path: Path to the banner GIF file
            
        Returns:
            file_id if successful, None otherwise
        """
        if not self.bot or not self.channel_id:
            logger.error("Bot not initialized")
            return None
        
        try:
            with open(banner_path, 'rb') as gif:
                result = await self.bot.send_animation(
                    chat_id=self.channel_id,
                    animation=gif,
                    caption="🎨 Banner uploaded! Saving file_id..."
                )
                
                file_id = result.animation.file_id
                logger.info(f"✅ Banner uploaded successfully!")
                logger.info(f"📝 Add this to your config.py:")
                logger.info(f'TELEGRAM_BANNER_FILE_ID = "{file_id}"')
                
                # Delete the test message
                await self.bot.delete_message(
                    chat_id=self.channel_id,
                    message_id=result.message_id
                )
                
                return file_id
                
        except FileNotFoundError:
            logger.error(f"❌ Banner file not found: {banner_path}")
            return None
        except Exception as e:
            logger.error(f"❌ Failed to upload banner: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
