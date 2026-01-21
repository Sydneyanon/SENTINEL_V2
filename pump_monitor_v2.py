"""
PumpPortal Monitor V2 - Real-time pump.fun bonding curve tracking
UPDATED: Now tracks unique buyers for FREE pre-graduation distribution scoring
         + Detects KOL trades from PumpPortal and logs with names
"""
import asyncio
import json
from typing import Callable, Dict, Optional
from datetime import datetime
import websockets
import aiohttp
from loguru import logger
from data.curated_wallets import get_wallet_info

class PumpMonitorV2:
    """Monitors pump.fun tokens via PumpPortal WebSocket"""
    
    def __init__(self, on_signal_callback: Callable, active_tracker=None):
        self.ws_url = 'wss://pumpportal.fun/api/data'
        self.on_signal_callback = on_signal_callback
        self.active_tracker = active_tracker
        self.ws = None
        self.tracked_tokens = {}
        
        # NEW: Track unique buyers per token (FREE distribution metric)
        self.unique_buyers = {}  # {token_address: set(buyer_wallets)}
        self.buyer_tracking_start = {}  # {token_address: datetime}
        
        self.running = False
        self.connection_attempts = 0
        self.messages_received = 0
        logger.info("🎬 PumpMonitorV2 initialized with unique buyer tracking")
        
    async def start(self):
        """Start monitoring"""
        logger.info("🚨 START METHOD CALLED!")
        
        self.running = True
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
        
        # Subscribe to migrations (graduations to Raydium)
        logger.info("📤 Subscribing to migrations (graduations)...")
        await self.ws.send(json.dumps({"method": "subscribeMigration"}))
        logger.info("✅ Subscribed to migrations")
        
        logger.info("📡 Subscriptions complete - monitoring token creations and graduations")
    
    async def _process_message(self, message: str):
        """Process message"""
        try:
            data = json.loads(message)
            tx_type = data.get('txType')
            
            # Log ALL message types we receive (not just create)
            if self.messages_received <= 20:
                logger.info(f"📬 Message type: {tx_type}, keys: {list(data.keys())[:10]}")
            
            if tx_type == 'create':
                await self._handle_new_token(data)
            elif tx_type in ['buy', 'sell']:
                await self._handle_trade(data)
            elif tx_type == 'complete':
                await self._handle_graduation(data)
            else:
                # Log unknown types
                if self.messages_received <= 10:
                    logger.info(f"🤷 Unknown tx_type: {tx_type}")
        except:
            pass
    
    async def _handle_new_token(self, data: Dict):
        """Handle new token"""
        token_address = data.get('mint')
        symbol = data.get('symbol', 'UNKNOWN')
        if token_address:
            # Only log if we're tracking this token (KOL bought it)
            if self.active_tracker and self.active_tracker.is_tracked(token_address):
                logger.info(f"🆕 New token (TRACKED): ${symbol}")
            else:
                logger.debug(f"🆕 New token: ${symbol}")
            
            # Subscribe to this specific token's trades to track bonding curve + unique buyers
            try:
                await self.ws.send(json.dumps({
                    "method": "subscribeTokenTrade",
                    "keys": [token_address]
                }))
                logger.debug(f"   📡 Subscribed to trades for {token_address[:8]}")
                
                # Initialize buyer tracking for this token
                self.unique_buyers[token_address] = set()
                self.buyer_tracking_start[token_address] = datetime.now()
                
            except Exception as e:
                logger.debug(f"   ⚠️ Failed to subscribe to token trades: {e}")
            
            # Analyze the newly created token
            token_data = await self._extract_token_data(data)
            await self.on_signal_callback(token_data, 'NEW_TOKEN')
    
    async def _handle_trade(self, data: Dict):
        """
        Handle trade - NOW TRACKS UNIQUE BUYERS FOR FREE DISTRIBUTION METRIC
        
        NEW BEHAVIOR:
        - Track unique buyer wallets per token (0 credits!)
        - Check if token is actively tracked by KOLs
        - If yes, trigger immediate re-analysis via ActiveTokenTracker
        """
        token_address = data.get('mint')
        bonding_pct = data.get('bondingCurvePercentage', 0)
        tx_type = data.get('txType')  # 'buy' or 'sell'
        trader_wallet = data.get('traderPublicKey')
        
        if not token_address:
            return
        
        # NEW: Track unique buyers (only buys, not sells)
        if tx_type == 'buy' and trader_wallet:
            # Track locally in PumpPortal
            if token_address not in self.unique_buyers:
                self.unique_buyers[token_address] = set()
                self.buyer_tracking_start[token_address] = datetime.now()
            self.unique_buyers[token_address].add(trader_wallet)

            # CRITICAL: Sync to active_tracker for conviction scoring
            if self.active_tracker:
                if token_address not in self.active_tracker.unique_buyers:
                    self.active_tracker.unique_buyers[token_address] = set()
                self.active_tracker.unique_buyers[token_address].add(trader_wallet)

            # NEW: Check if this trader is a KOL from our list
            kol_info = get_wallet_info(trader_wallet)
            if kol_info:
                buyer_count = len(self.unique_buyers[token_address])
                tier_emoji = "🏆" if kol_info['tier'] == 'elite' else "👑" if kol_info['tier'] == 'top_kol' else "✅"
                symbol = data.get('symbol', token_address[:8])
                logger.info(f"{tier_emoji} {kol_info['name']} ({kol_info['tier']}) bought ${symbol} on PumpPortal ({buyer_count} unique buyers)")

            # Log milestone buyer counts
            buyer_count = len(self.unique_buyers[token_address])
            if buyer_count in [10, 25, 50, 75, 100]:
                logger.info(f"👥 {data.get('symbol', token_address[:8])} hit {buyer_count} unique buyers")
        
        # Check if this is a tracked token (KOL bought it)
        if self.active_tracker and self.active_tracker.is_tracked(token_address):
            # This is a tracked token! Update it in real-time
            await self.active_tracker.update_token_trade(token_address, data)
            return  # ActiveTracker handles everything from here
        
        # Pre-graduation range monitoring (40-60%)
        if 40 <= bonding_pct <= 60:
            if token_address not in self.tracked_tokens:
                logger.info(f"⚡ Token in range: {data.get('symbol')} at {bonding_pct:.1f}%")
                
                # Extract token data with unique buyer count
                token_data = await self._extract_token_data(data)
                
                await self.on_signal_callback(token_data, 'PRE_GRADUATION')
                self.tracked_tokens[token_address] = bonding_pct
    
    async def _handle_graduation(self, data: Dict):
        """Handle graduation"""
        token_address = data.get('mint')
        symbol = data.get('symbol', 'UNKNOWN')
        
        if token_address:
            buyer_count = len(self.unique_buyers.get(token_address, set()))
            logger.info(f"🎓 Graduation: ${symbol} ({buyer_count} unique buyers tracked)")
            
            # Check if this is a tracked token
            if self.active_tracker and self.active_tracker.is_tracked(token_address):
                # Update tracked token with graduation info
                data['bondingCurvePercentage'] = 100
                await self.active_tracker.update_token_trade(token_address, data)
            else:
                # Not tracked by KOLs, still report graduation
                token_data = await self._extract_token_data(data)
                token_data['bonding_curve_pct'] = 100
                await self.on_signal_callback(token_data, 'POST_GRADUATION')
            
            self.tracked_tokens.pop(token_address, None)
    
    async def _extract_token_data(self, data: Dict) -> Dict:
        """Extract token data with unique buyer count"""
        token_address = data.get('mint')
        bonding_pct = data.get('bondingCurvePercentage', 0)
        
        token_data = {
            'token_address': token_address,
            'token_name': data.get('name'),
            'token_symbol': data.get('symbol'),
            'description': data.get('description', ''),
            'bonding_curve_pct': bonding_pct,
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
            'holder_count': 0,
            'unique_buyers': 0  # Will be set below
        }
        
        # NEW: Add unique buyer count (FREE!)
        token_data['unique_buyers'] = len(self.unique_buyers.get(token_address, set()))
        
        # For post-graduation tokens, enrich with fresh DEX data
        if bonding_pct >= 100:
            dex_data = await self._get_dex_data(token_address)
            if dex_data:
                # Update with fresh Raydium volume data
                token_data['volume_5m'] = dex_data.get('volume_5m', token_data['volume_5m'])
                token_data['volume_1h'] = dex_data.get('volume_1h', token_data['volume_1h'])
                token_data['volume_24h'] = dex_data.get('volume_24h', token_data['volume_24h'])
                token_data['liquidity'] = dex_data.get('liquidity', token_data['liquidity'])
                token_data['holder_count'] = dex_data.get('holder_count', 0)
                logger.debug(f"   📊 Enriched with fresh DEX data")
        # else: Pre-graduation uses unique_buyers instead of holder_count (already set above)
        
        return token_data
    
    async def _get_dex_data(self, token_address: str) -> dict:
        """
        Get fresh volume and holder data from DexScreener for post-graduation tokens
        Returns dict with volume_5m, volume_1h, volume_24h, liquidity, holder_count
        """
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        logger.debug(f"⚠️ DexScreener returned {resp.status}")
                        return None
                    
                    data = await resp.json()
                    pairs = data.get('pairs', [])
                    
                    if not pairs:
                        return None
                    
                    # Get data from first (most liquid) pair
                    pair = pairs[0]
                    
                    # Extract volume data
                    volume_obj = pair.get('volume', {})
                    txns = pair.get('txns', {})
                    
                    dex_data = {
                        'volume_5m': volume_obj.get('m5', 0),
                        'volume_1h': volume_obj.get('h1', 0),
                        'volume_24h': volume_obj.get('h24', 0),
                        'liquidity': pair.get('liquidity', {}).get('usd', 0),
                        'holder_count': txns.get('h24', {}).get('unique', 0) or pair.get('holderCount', 0)
                    }
                    
                    logger.debug(f"   📊 DEX data: vol_1h=${dex_data['volume_1h']:.0f}, holders={dex_data['holder_count']}")
                    return dex_data
                    
        except Exception as e:
            logger.debug(f"⚠️ Error fetching DEX data: {e}")
            return None
    
    def get_unique_buyers(self, token_address: str) -> int:
        """
        Get count of unique buyers for a token
        
        Args:
            token_address: Token mint address
            
        Returns:
            Number of unique buyers tracked
        """
        return len(self.unique_buyers.get(token_address, set()))
    
    def get_buyer_tracking_duration(self, token_address: str) -> float:
        """
        Get how long we've been tracking buyers for a token (in minutes)
        
        Args:
            token_address: Token mint address
            
        Returns:
            Duration in minutes
        """
        if token_address not in self.buyer_tracking_start:
            return 0.0
        
        start_time = self.buyer_tracking_start[token_address]
        elapsed_seconds = (datetime.now() - start_time).total_seconds()
        return elapsed_seconds / 60
    
    async def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.ws:
            await self.ws.close()
        logger.info(f"🛑 Stopped (received {self.messages_received} messages)")
    
    def cleanup_old_tokens(self):
        """Cleanup old tracked tokens and buyer data"""
        if len(self.tracked_tokens) > 1000:
            tokens_to_remove = list(self.tracked_tokens.keys())[:500]
            for token in tokens_to_remove:
                self.tracked_tokens.pop(token, None)
                # NEW: Also cleanup buyer tracking data
                self.unique_buyers.pop(token, None)
                self.buyer_tracking_start.pop(token, None)
            
            logger.info(f"🧹 Cleaned up {len(tokens_to_remove)} old tokens")
