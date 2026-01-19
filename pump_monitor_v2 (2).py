"""
PumpPortal Monitor V2 - Real-time pump.fun bonding curve tracking
Brand new file to force reload
"""
import asyncio
import json
from typing import Callable, Dict
import websockets
import aiohttp
from loguru import logger

class PumpMonitorV2:
    """Monitors pump.fun tokens via PumpPortal WebSocket"""
    
    def __init__(self, on_signal_callback: Callable):
        self.ws_url = 'wss://pumpportal.fun/api/data'
        self.on_signal_callback = on_signal_callback
        self.ws = None
        self.tracked_tokens = {}
        self.running = False
        self.connection_attempts = 0
        self.messages_received = 0
        logger.info("🎬 PumpMonitorV2 __init__ called")
        
    async def start(self):
        """Start monitoring"""
        logger.info("🚨🚨🚨 START METHOD CALLED! 🚨🚨🚨")
        logger.info(f"Running flag BEFORE: {self.running}")
        
        self.running = True
        logger.info(f"Running flag AFTER: {self.running}")
        logger.info("🔌 Starting PumpPortal monitor...")
        
        while self.running:
            try:
                self.connection_attempts += 1
                logger.info(f"🔄 Connection attempt #{self.connection_attempts}")
                await self._connect_and_listen()
            except Exception as e:
                logger.error(f"❌ Error: {e}")
                import traceback
                logger.error(traceback.format_exc())
                await asyncio.sleep(5)
    
    async def _connect_and_listen(self):
        """Connect to WebSocket"""
        logger.info(f"📡 Connecting to {self.ws_url}...")
        
        async with websockets.connect(
            self.ws_url,
            ping_interval=20,
            ping_timeout=10
        ) as ws:
            self.ws = ws
            logger.info("✅ Connected to PumpPortal WebSocket")
            
            await self._subscribe()
            
            logger.info("👂 Listening for messages...")
            async for message in ws:
                self.messages_received += 1
                if self.messages_received <= 3:
                    logger.info(f"📨 Message #{self.messages_received}: {message[:100]}...")
                await self._process_message(message)
    
    async def _subscribe(self):
        """Subscribe to events"""
        logger.info("📤 Subscribing to new tokens...")
        await self.ws.send(json.dumps({"method": "subscribeNewToken"}))
        logger.info("✅ Subscribed to new tokens")
        
        await asyncio.sleep(0.5)
        
        logger.info("📤 Subscribing to token trades...")
        await self.ws.send(json.dumps({"method": "subscribeTokenTrade", "keys": ["*"]}))
        logger.info("✅ Subscribed to token trades")
    
    async def _process_message(self, message: str):
        """Process message"""
        try:
            data = json.loads(message)
            tx_type = data.get('txType')
            
            if tx_type == 'create':
                await self._handle_new_token(data)
            elif tx_type in ['buy', 'sell']:
                await self._handle_trade(data)
            elif tx_type == 'complete':
                await self._handle_graduation(data)
        except:
            pass
    
    async def _handle_new_token(self, data: Dict):
        """Handle new token"""
        token_address = data.get('mint')
        symbol = data.get('symbol', 'UNKNOWN')
        if token_address:
            logger.info(f"🆕 New token: ${symbol}")
    
    async def _handle_trade(self, data: Dict):
        """Handle trade"""
        token_address = data.get('mint')
        bonding_pct = data.get('bondingCurvePercentage', 0)
        
        if not token_address:
            return
        
        if 40 <= bonding_pct <= 60:
            if token_address not in self.tracked_tokens:
                logger.info(f"⚡ Token in range: {data.get('symbol')} at {bonding_pct:.1f}%")
                token_data = await self._extract_token_data(data)
                await self.on_signal_callback(token_data, 'PRE_GRADUATION')
                self.tracked_tokens[token_address] = bonding_pct
    
    async def _handle_graduation(self, data: Dict):
        """Handle graduation"""
        token_address = data.get('mint')
        symbol = data.get('symbol', 'UNKNOWN')
        
        if token_address:
            logger.info(f"🎓 Graduation: ${symbol}")
            token_data = await self._extract_token_data(data)
            token_data['bonding_curve_pct'] = 100
            await self.on_signal_callback(token_data, 'POST_GRADUATION')
            self.tracked_tokens.pop(token_address, None)
    
    async def _extract_token_data(self, data: Dict) -> Dict:
        """Extract token data"""
        token_address = data.get('mint')
        
        token_data = {
            'token_address': token_address,
            'token_name': data.get('name'),
            'token_symbol': data.get('symbol'),
            'description': data.get('description', ''),
            'bonding_curve_pct': data.get('bondingCurvePercentage', 0),
            'market_cap': data.get('marketCapSol', 0) * 150,
            'liquidity': data.get('vSolInBondingCurve', 0) * 150,
            'volume_24h': data.get('volume24h', 0),
            'price_usd': data.get('priceUsd', 0),
            'price_native': data.get('priceNative', 0),
            'price_change_5m': data.get('priceChange5mPercent', 0),
            'price_change_1h': data.get('priceChange1hPercent', 0),
            'volume_5m': data.get('volume5m', 0),
            'volume_1h': data.get('volume1h', 0),
            'tx_signature': data.get('signature'),
            'trader_wallet': data.get('traderPublicKey'),
            'image_uri': data.get('uri', ''),
            'created_timestamp': data.get('timestamp'),
            'holder_count': 0
        }
        
        return token_data
    
    async def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.ws:
            await self.ws.close()
        logger.info(f"🛑 Stopped (received {self.messages_received} messages)")
    
    def cleanup_old_tokens(self):
        """Cleanup"""
        if len(self.tracked_tokens) > 1000:
            tokens_to_remove = list(self.tracked_tokens.keys())[:500]
            for token in tokens_to_remove:
                self.tracked_tokens.pop(token, None)
