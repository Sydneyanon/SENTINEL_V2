"""
PumpPortal Monitor - Real-time pump.fun bonding curve tracking
UPDATED: Added extensive error logging to diagnose connection issues
"""
import asyncio
import json
import logging
from typing import Callable, Dict, Optional
import websockets
import aiohttp

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
        self.connection_attempts = 0
        self.messages_received = 0
        
    async def start(self):
        """Start monitoring PumpPortal WebSocket"""
        self.running = True
        logger.info("🔌 Starting PumpPortal monitor...")
        
        while self.running:
            try:
                self.connection_attempts += 1
                logger.info(f"🔄 Connection attempt #{self.connection_attempts}")
                await self._connect_and_listen()
            except Exception as e:
                logger.error(f"❌ PumpPortal error: {e}")
                logger.error(f"   Error type: {type(e).__name__}")
                import traceback
                logger.error(traceback.format_exc())
                logger.info("🔄 Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
    
    async def _connect_and_listen(self):
        """Connect to WebSocket and listen for messages"""
        try:
            logger.info(f"📡 Connecting to {self.ws_url}...")
            
            async with websockets.connect(
                self.ws_url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            ) as ws:
                self.ws = ws
                logger.info("✅ Connected to PumpPortal WebSocket")
                
                # Subscribe to new token events and trades
                await self._subscribe()
                
                # Listen for messages
                logger.info("👂 Listening for messages...")
                message_count = 0
                
                async for message in ws:
                    try:
                        message_count += 1
                        self.messages_received += 1
                        
                        # Log first few messages for debugging
                        if message_count <= 3:
                            logger.info(f"📨 Message #{message_count} received: {message[:200]}...")
                        elif message_count % 100 == 0:
                            logger.info(f"📊 Received {message_count} messages so far (total: {self.messages_received})")
                        
                        await self._process_message(message)
                    except Exception as e:
                        logger.error(f"❌ Error processing message #{message_count}: {e}")
                        
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"⚠️ WebSocket connection closed: {e}")
            logger.warning(f"   Code: {e.code}, Reason: {e.reason}")
        except asyncio.TimeoutError:
            logger.error("❌ WebSocket connection timeout")
        except Exception as e:
            logger.error(f"❌ WebSocket connection error: {e}")
            logger.error(f"   Error type: {type(e).__name__}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    async def _subscribe(self):
        """Subscribe to PumpPortal events"""
        try:
            # Subscribe to new tokens
            subscribe_new = {
                "method": "subscribeNewToken"
            }
            logger.info("📤 Sending subscription: subscribeNewToken")
            await self.ws.send(json.dumps(subscribe_new))
            logger.info("✅ Sent subscribeNewToken")
            
            # Small delay to ensure subscription is processed
            await asyncio.sleep(0.5)
            
            # Subscribe to all token trades (for bonding curve tracking)
            subscribe_trades = {
                "method": "subscribeTokenTrade",
                "keys": ["*"]  # Monitor all tokens
            }
            logger.info("📤 Sending subscription: subscribeTokenTrade")
            await self.ws.send(json.dumps(subscribe_trades))
            logger.info("✅ Sent subscribeTokenTrade")
            
            logger.info("📡 Subscriptions sent - waiting for data...")
            
        except Exception as e:
            logger.error(f"❌ Failed to subscribe: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    async def _process_message(self, message: str):
        """Process incoming WebSocket message"""
        try:
            data = json.loads(message)
            
            # Get event type
            tx_type = data.get('txType')
            
            if tx_type == 'create':
                # New token created
                logger.debug(f"🆕 New token: {data.get('symbol', 'UNKNOWN')}")
                await self._handle_new_token(data)
            
            elif tx_type in ['buy', 'sell']:
                # Trade event - check bonding curve
                await self._handle_trade(data)
            
            elif tx_type == 'complete':
                # Token graduated (100% bonding curve)
                await self._handle_graduation(data)
            else:
                # Unknown message type - log for debugging
                if self.messages_received <= 5:
                    logger.info(f"📬 Unknown message type: {tx_type}")
                    logger.info(f"   Data keys: {list(data.keys())}")
                
        except json.JSONDecodeError:
            logger.debug(f"⚠️ Non-JSON message received: {message[:100]}")
        except Exception as e:
            logger.error(f"❌ Error processing message: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
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
                
                # Extract token data and enrich with holder count
                token_data = await self._extract_and_enrich_token_data(data)
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
            
            # Extract token data and enrich with holder count
            token_data = await self._extract_and_enrich_token_data(data)
            token_data['bonding_curve_pct'] = 100
            
            await self.on_signal_callback(token_data, 'POST_GRADUATION')
            
            # Remove from tracking (no longer on pump.fun)
            self.tracked_tokens.pop(token_address, None)
    
    async def _extract_and_enrich_token_data(self, data: Dict) -> Dict:
        """Extract token data from PumpPortal and enrich with holder count"""
        token_address = data.get('mint')
        
        # Base data from PumpPortal
        token_data = {
            'token_address': token_address,
            'token_name': data.get('name'),
            'token_symbol': data.get('symbol'),
            'description': data.get('description', ''),
            'bonding_curve_pct': data.get('bondingCurvePercentage', 0),
            
            # Market data
            'market_cap': data.get('marketCapSol', 0) * 150,
            'liquidity': data.get('vSolInBondingCurve', 0) * 150,
            'volume_24h': data.get('volume24h', 0),
            
            # Price data
            'price_usd': data.get('priceUsd', 0),
            'price_native': data.get('priceNative', 0),
            'price_change_5m': data.get('priceChange5mPercent', 0),
            'price_change_1h': data.get('priceChange1hPercent', 0),
            
            # Volume metrics
            'volume_5m': data.get('volume5m', 0),
            'volume_1h': data.get('volume1h', 0),
            
            # Transaction data
            'tx_signature': data.get('signature'),
            'trader_wallet': data.get('traderPublicKey'),
            
            # Metadata
            'image_uri': data.get('uri', ''),
            'created_timestamp': data.get('timestamp'),
            
            # Holder count (will be enriched)
            'holder_count': 0
        }
        
        # Enrich with holder count from DexScreener
        holder_count = await self._fetch_holder_count(token_address)
        token_data['holder_count'] = holder_count
        
        return token_data
    
    async def _fetch_holder_count(self, token_address: str) -> int:
        """Fetch holder count from DexScreener API"""
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        return 0
                    
                    data = await resp.json()
                    pairs = data.get('pairs', [])
                    
                    if not pairs:
                        return 0
                    
                    pair = pairs[0]
                    holder_count = pair.get('txns', {}).get('h24', {}).get('unique', 0)
                    
                    if holder_count == 0:
                        holder_count = pair.get('holderCount', 0)
                    
                    return holder_count
                    
        except:
            return 0
    
    async def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.ws:
            await self.ws.close()
            logger.info(f"🛑 PumpPortal monitor stopped (received {self.messages_received} total messages)")
    
    def cleanup_old_tokens(self, max_age_hours: int = 24):
        """Remove tokens from tracking if they've been tracked too long"""
        current_size = len(self.tracked_tokens)
        
        if current_size > 1000:
            tokens_to_remove = list(self.tracked_tokens.keys())[:500]
            for token in tokens_to_remove:
                self.tracked_tokens.pop(token, None)
            
            logger.info(f"🧹 Cleaned up {len(tokens_to_remove)} old tracked tokens")
