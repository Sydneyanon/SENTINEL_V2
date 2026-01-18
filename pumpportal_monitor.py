"""
PumpPortal Monitor - Real-time pump.fun bonding curve tracking
Replaces Helius graduation webhooks with WebSocket monitoring
"""
import asyncio
import json
import logging
from typing import Callable, Dict, Optional
import websockets

logger = logging.getLogger(__name__)

class PumpPortalMonitor:
    """
    Monitors pump.fun tokens via PumpPortal WebSocket
    
    Catches:
    - Tokens at 40-60% bonding curve (pre-graduation, ultra-early)
    - Tokens at 100% graduation (just graduated to Raydium)
    """
    
    def __init__(self, on_signal_callback: Callable):
        """
        Args:
            on_signal_callback: Async function to call when a signal is detected
                                 Signature: async def callback(token_data: Dict, signal_type: str)
        """
        self.ws_url = 'wss://pumpportal.fun/api/data'
        self.on_signal_callback = on_signal_callback
        self.ws = None
        self.tracked_tokens = {}  # {token_address: bonding_pct} to avoid duplicates
        self.running = False
        
    async def start(self):
        """Start monitoring PumpPortal WebSocket"""
        self.running = True
        logger.info("🔌 Starting PumpPortal monitor...")
        
        while self.running:
            try:
                await self._connect_and_listen()
            except Exception as e:
                logger.error(f"❌ PumpPortal error: {e}")
                logger.info("🔄 Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
    
    async def _connect_and_listen(self):
        """Connect to WebSocket and listen for messages"""
        async with websockets.connect(
            self.ws_url,
            ping_interval=20,
            ping_timeout=10
        ) as ws:
            self.ws = ws
            logger.info("✅ Connected to PumpPortal WebSocket")
            
            # Subscribe to new token events and trades
            await self._subscribe()
            
            # Listen for messages
            async for message in ws:
                try:
                    await self._process_message(message)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
    
    async def _subscribe(self):
        """Subscribe to PumpPortal events"""
        # Subscribe to new tokens
        subscribe_new = {
            "method": "subscribeNewToken"
        }
        await self.ws.send(json.dumps(subscribe_new))
        logger.info("📡 Subscribed to new token events")
        
        # Subscribe to all token trades (for bonding curve tracking)
        subscribe_trades = {
            "method": "subscribeTokenTrade",
            "keys": ["*"]  # Monitor all tokens
        }
        await self.ws.send(json.dumps(subscribe_trades))
        logger.info("📡 Subscribed to token trade events")
    
    async def _process_message(self, message: str):
        """Process incoming WebSocket message"""
        try:
            data = json.loads(message)
            
            # Get event type
            tx_type = data.get('txType')
            
            if tx_type == 'create':
                # New token created
                await self._handle_new_token(data)
            
            elif tx_type in ['buy', 'sell']:
                # Trade event - check bonding curve
                await self._handle_trade(data)
            
            elif tx_type == 'complete':
                # Token graduated (100% bonding curve)
                await self._handle_graduation(data)
                
        except json.JSONDecodeError:
            logger.debug(f"Non-JSON message received: {message[:100]}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    async def _handle_new_token(self, data: Dict):
        """Handle new token creation"""
        token_address = data.get('mint')
        symbol = data.get('symbol', 'UNKNOWN')
        
        if token_address:
            logger.info(f"🆕 New token: ${symbol} ({token_address[:8]}...)")
    
    async def _handle_trade(self, data: Dict):
        """Handle trade event and check if we should signal"""
        token_address = data.get('mint')
        bonding_pct = data.get('bondingCurvePercentage', 0)
        
        if not token_address:
            return
        
        # Check if this token is in our target range (40-60%)
        if 40 <= bonding_pct <= 60:
            # Have we already signaled this token?
            if token_address not in self.tracked_tokens:
                logger.info(f"⚡ Token in range: {data.get('symbol')} at {bonding_pct:.1f}%")
                
                # Extract token data and signal
                token_data = self._extract_token_data(data)
                await self.on_signal_callback(token_data, 'PRE_GRADUATION')
                
                # Mark as tracked
                self.tracked_tokens[token_address] = bonding_pct
            
            # Update tracking
            else:
                self.tracked_tokens[token_address] = bonding_pct
    
    async def _handle_graduation(self, data: Dict):
        """Handle token graduation (100% bonding curve)"""
        token_address = data.get('mint')
        symbol = data.get('symbol', 'UNKNOWN')
        
        if token_address:
            logger.info(f"🎓 Graduation: ${symbol} ({token_address[:8]}...)")
            
            # Extract token data and signal
            token_data = self._extract_token_data(data)
            token_data['bonding_curve_pct'] = 100
            
            await self.on_signal_callback(token_data, 'POST_GRADUATION')
            
            # Remove from tracking (no longer on pump.fun)
            self.tracked_tokens.pop(token_address, None)
    
    def _extract_token_data(self, data: Dict) -> Dict:
        """Extract relevant token data from PumpPortal message"""
        return {
            'token_address': data.get('mint'),
            'token_name': data.get('name'),
            'token_symbol': data.get('symbol'),
            'description': data.get('description', ''),
            'bonding_curve_pct': data.get('bondingCurvePercentage', 0),
            
            # Market data
            'market_cap': data.get('marketCapSol', 0) * 150,  # Rough SOL to USD conversion
            'liquidity': data.get('vSolInBondingCurve', 0) * 150,  # SOL in bonding curve
            'volume_24h': data.get('volume24h', 0),
            
            # Price data
            'price_usd': data.get('priceUsd', 0),
            'price_native': data.get('priceNative', 0),
            'price_change_5m': data.get('priceChange5mPercent', 0),
            'price_change_1h': data.get('priceChange1hPercent', 0),
            
            # Transaction data
            'tx_signature': data.get('signature'),
            'trader_wallet': data.get('traderPublicKey'),
            
            # Metadata
            'image_uri': data.get('uri', ''),
            'created_timestamp': data.get('timestamp'),
        }
    
    async def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.ws:
            await self.ws.close()
            logger.info("PumpPortal monitor stopped")
    
    def cleanup_old_tokens(self, max_age_hours: int = 24):
        """Remove tokens from tracking if they've been tracked too long"""
        # This prevents memory leaks from tokens that never graduate
        current_size = len(self.tracked_tokens)
        
        # Simple approach: if we're tracking more than 1000 tokens, clear half
        if current_size > 1000:
            tokens_to_remove = list(self.tracked_tokens.keys())[:500]
            for token in tokens_to_remove:
                self.tracked_tokens.pop(token, None)
            
            logger.info(f"🧹 Cleaned up {len(tokens_to_remove)} old tracked tokens")
