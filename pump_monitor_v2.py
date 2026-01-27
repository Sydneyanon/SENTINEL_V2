"""
PumpPortal Monitor V2 - Real-time pump.fun bonding curve tracking
UPDATED: Now tracks unique buyers for FREE pre-graduation distribution scoring
         + Detects KOL trades from PumpPortal and logs with names
         + Organic scanner: auto-discovers tokens with strong on-chain activity
"""
import asyncio
import json
from typing import Callable, Dict, Optional
from datetime import datetime, timedelta
import websockets
import aiohttp
from loguru import logger
from data.curated_wallets import get_wallet_info
import config

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

        # NEW: Pre-bonding milestone tracking (journey from 0% -> 100%)
        self.bonding_milestones = {}  # {token_address: {milestone_pct: {'timestamp': datetime, 'sol_raised': float, 'buyer_count': int, 'trades_since_last': int}}}
        self.milestone_percentages = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]  # Track every 10%
        self.trade_counts = {}  # {token_address: total_trade_count}
        self.sol_raised = {}  # {token_address: cumulative_sol}

        # NEW: Velocity spike detection (FOMO acceleration)
        # Track buyer count in 60-second windows to detect >2x spikes after 50% bonding
        self.buyer_history = {}  # {token_address: [(timestamp, buyer_count), ...]}
        self.velocity_spikes = {}  # {token_address: {'detected': bool, 'spike_at_pct': int}}

        # ORGANIC SCANNER: Track candidate tokens for automatic discovery
        self.organic_candidates = {}  # {token_address: {'first_seen': datetime, 'buys': int, 'sells': int, 'same_block_buys': {}, 'symbol': str}}
        self.organic_promoted = set()  # Tokens already sent to tracker (avoid duplicates)
        self.organic_rejected = set()  # Tokens rejected (too old, failed filters)
        self.last_organic_eval = datetime.now()  # Rate-limit evaluations

        # Track buy/sell per token for ratio calculation
        self.trade_stats = {}  # {token_address: {'buys': int, 'sells': int, 'blocks': {block_slot: count}}}

        # ROLLING SOL VOLUME: Track SOL amounts per trade for phase-aware volume scoring
        # Pre-grad tokens have no DexScreener data, so we calculate volume momentum
        # from PumpPortal WebSocket trade events (each trade has solAmount)
        self.sol_volume_history = {}  # {token_address: [(datetime, sol_amount), ...]}

        self.running = False
        self.connection_attempts = 0
        self.messages_received = 0
        logger.info("🎬 PumpMonitorV2 initialized with unique buyer tracking + bonding milestones + organic scanner")
        
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
        
        # Track buy/sell stats per token (for organic scanner ratio)
        if token_address not in self.trade_stats:
            self.trade_stats[token_address] = {'buys': 0, 'sells': 0, 'blocks': {}}
        if tx_type == 'buy':
            self.trade_stats[token_address]['buys'] += 1
            # Track same-block buys for bundle detection
            block_slot = data.get('slot', 0)
            if block_slot:
                self.trade_stats[token_address]['blocks'][block_slot] = \
                    self.trade_stats[token_address]['blocks'].get(block_slot, 0) + 1
        elif tx_type == 'sell':
            self.trade_stats[token_address]['sells'] += 1

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
                # Apply fallback for None/empty names
                kol_name = kol_info.get('name')
                if not kol_name or kol_name is None or kol_name == 'None':
                    kol_name = f"KOL_{trader_wallet[:6]}"

                buyer_count = len(self.unique_buyers[token_address])
                tier_emoji = "🏆" if kol_info['tier'] == 'elite' else "👑" if kol_info['tier'] == 'top_kol' else "✅"
                symbol = data.get('symbol', token_address[:8])
                logger.info(f"{tier_emoji} {kol_name} ({kol_info['tier']}) bought ${symbol} on PumpPortal ({buyer_count} unique buyers)")

            # Log milestone buyer counts
            buyer_count = len(self.unique_buyers[token_address])
            if buyer_count in [10, 25, 50, 75, 100]:
                logger.info(f"👥 {data.get('symbol', token_address[:8])} hit {buyer_count} unique buyers")

            # NEW: Velocity spike detection (>2x buyer count in 60s after 50% bonding)
            if bonding_pct >= 50:  # Only check after 50% bonding
                now = datetime.now()

                # Initialize buyer history if needed
                if token_address not in self.buyer_history:
                    self.buyer_history[token_address] = []
                    self.velocity_spikes[token_address] = {'detected': False, 'spike_at_pct': 0}

                # Add current buyer count snapshot
                self.buyer_history[token_address].append((now, buyer_count))

                # Clean old history (keep last 2 minutes for analysis)
                self.buyer_history[token_address] = [
                    (ts, count) for ts, count in self.buyer_history[token_address]
                    if (now - ts).total_seconds() <= 120
                ]

                # Check for velocity spike (>2x in last 60s)
                if not self.velocity_spikes[token_address]['detected']:
                    history = self.buyer_history[token_address]
                    if len(history) >= 2:
                        # Get buyer counts from 60s ago and now
                        sixty_sec_ago = now - timedelta(seconds=60)
                        buyers_60s_ago = None
                        buyers_now = buyer_count

                        # Find buyer count closest to 60s ago
                        for ts, count in history:
                            if (now - ts).total_seconds() >= 60:
                                buyers_60s_ago = count

                        # Detect spike: >2x increase in 60s
                        if buyers_60s_ago and buyers_now > buyers_60s_ago * 2:
                            self.velocity_spikes[token_address]['detected'] = True
                            self.velocity_spikes[token_address]['spike_at_pct'] = int(bonding_pct)
                            increase_pct = ((buyers_now - buyers_60s_ago) / buyers_60s_ago * 100)
                            symbol = data.get('symbol', token_address[:8])
                            logger.info(f"🚀 VELOCITY SPIKE: ${symbol} buyers: {buyers_60s_ago} → {buyers_now} (+{increase_pct:.0f}%) in 60s at {bonding_pct:.0f}% bonding!")

        # NEW: Track bonding curve milestones (SOL raised, velocity, trade counts)
        if token_address not in self.bonding_milestones:
            self.bonding_milestones[token_address] = {}
            self.trade_counts[token_address] = 0
            self.sol_raised[token_address] = 0.0

        # Increment trade count
        self.trade_counts[token_address] += 1

        # Track SOL raised (approximate from trade data if available)
        sol_amount = data.get('solAmount', 0)
        if sol_amount:
            self.sol_raised[token_address] += float(sol_amount)

            # Track SOL volume with timestamps for rolling window analysis
            if token_address not in self.sol_volume_history:
                self.sol_volume_history[token_address] = []
            self.sol_volume_history[token_address].append((datetime.now(), float(sol_amount)))

        # Check if we hit a bonding milestone
        current_bonding_pct = int(bonding_pct)
        for milestone in self.milestone_percentages:
            if milestone not in self.bonding_milestones[token_address]:
                if current_bonding_pct >= milestone:
                    # We just crossed this milestone!
                    buyer_count = len(self.unique_buyers.get(token_address, set()))

                    # Calculate trades since last milestone
                    last_milestone = milestone - 10
                    trades_since_last = self.trade_counts[token_address]
                    if last_milestone > 0 and last_milestone in self.bonding_milestones[token_address]:
                        trades_since_last = self.trade_counts[token_address] - self.bonding_milestones[token_address][last_milestone].get('total_trades', 0)

                    # Calculate time since last milestone (velocity)
                    time_since_last = None
                    if last_milestone > 0 and last_milestone in self.bonding_milestones[token_address]:
                        time_since_last = (datetime.now() - self.bonding_milestones[token_address][last_milestone]['timestamp']).total_seconds()

                    # Record milestone
                    self.bonding_milestones[token_address][milestone] = {
                        'timestamp': datetime.now(),
                        'sol_raised': self.sol_raised[token_address],
                        'buyer_count': buyer_count,
                        'total_trades': self.trade_counts[token_address],
                        'trades_since_last': trades_since_last,
                        'time_since_last_seconds': time_since_last
                    }

                    symbol = data.get('symbol', token_address[:8])

                    # Calculate velocity
                    if time_since_last:
                        velocity = 10 / (time_since_last / 60)  # 10% per X minutes
                        logger.info(f"📊 ${symbol} hit {milestone}% bonding | {buyer_count} buyers | {trades_since_last} trades in {time_since_last/60:.1f}min | Velocity: {velocity:.2f}%/min")
                    else:
                        logger.info(f"📊 ${symbol} hit {milestone}% bonding | {buyer_count} buyers | SOL raised: {self.sol_raised[token_address]:.2f}")

        # Check if this is a tracked token (KOL bought it)
        if self.active_tracker and self.active_tracker.is_tracked(token_address):
            # This is a tracked token! Update it in real-time
            await self.active_tracker.update_token_trade(token_address, data)
            return  # ActiveTracker handles everything from here
        
        # ORGANIC SCANNER: Evaluate tokens for automatic discovery
        # Replaces old pre-graduation range monitoring (40-60%)
        if config.ORGANIC_SCANNER.get('enabled', False) and not config.STRICT_KOL_ONLY_MODE:
            await self._evaluate_organic_candidate(token_address, data, bonding_pct)
    
    async def _evaluate_organic_candidate(self, token_address: str, data: Dict, bonding_pct: float):
        """
        Organic Scanner: Evaluate if a token meets organic activity thresholds.
        If criteria met, route to active_tracker for full conviction scoring.

        Criteria (from config.ORGANIC_SCANNER):
        - min_unique_buyers: 60+ unique buyers (OR velocity bypass)
        - min_buy_ratio: 70%+ buys vs sells
        - max_bundle_ratio: <20% same-block buys (anti-bundle)
        - min_bonding_pct: past 40% bonding (avoid very early sniped rugs)
        - max_bonding_pct: below 85% bonding (not too late)
        - velocity_bypass: If buyer velocity >2.5x in 5min, bypass buyer count
        """
        # Skip if already tracked, promoted, or rejected
        if token_address in self.organic_promoted:
            return
        if token_address in self.organic_rejected:
            return
        if self.active_tracker and self.active_tracker.is_tracked(token_address):
            return

        scanner_cfg = config.ORGANIC_SCANNER

        # Check bonding range
        min_bonding = scanner_cfg.get('min_bonding_pct', 25)
        max_bonding = scanner_cfg.get('max_bonding_pct', 90)
        if bonding_pct < min_bonding or bonding_pct > max_bonding:
            return

        # Check unique buyer count (with velocity bypass)
        buyer_count = len(self.unique_buyers.get(token_address, set()))
        min_buyers = scanner_cfg.get('min_unique_buyers', 38)
        velocity_bypassed = False

        if buyer_count < min_buyers:
            # Velocity bypass: if buyer acceleration is >2x in last 5 min, bypass count
            velocity_multiplier = scanner_cfg.get('velocity_bypass_multiplier', 2.0)
            history = self.buyer_history.get(token_address, [])
            if len(history) >= 2:
                now = datetime.now()
                cutoff = now - timedelta(seconds=300)  # 5 min window
                buyers_at_cutoff = 0
                buyers_now = buyer_count
                for ts, count in history:
                    if ts <= cutoff:
                        buyers_at_cutoff = count
                if buyers_at_cutoff > 0 and buyers_now >= buyers_at_cutoff * velocity_multiplier:
                    velocity_bypassed = True
                    symbol = data.get('symbol', token_address[:8])
                    logger.info(f"⚡ Organic scanner: ${symbol} velocity bypass! {buyers_at_cutoff}→{buyers_now} buyers ({buyers_now/buyers_at_cutoff:.1f}x in 5m)")

            if not velocity_bypassed:
                return

        # Check buy/sell ratio
        stats = self.trade_stats.get(token_address, {'buys': 0, 'sells': 0, 'blocks': {}})
        total_trades = stats['buys'] + stats['sells']
        if total_trades < 20:
            return  # Not enough data
        buy_ratio = stats['buys'] / total_trades
        min_buy_ratio = scanner_cfg.get('min_buy_ratio', 0.65)
        if buy_ratio < min_buy_ratio:
            return

        # Check bundle ratio (same-block buys as % of total buys)
        if stats['buys'] > 0 and stats['blocks']:
            max_same_block = max(stats['blocks'].values()) if stats['blocks'] else 0
            bundle_ratio = max_same_block / stats['buys']
            max_bundle = scanner_cfg.get('max_bundle_ratio', 0.20)
            if bundle_ratio > max_bundle:
                symbol = data.get('symbol', token_address[:8])
                logger.info(f"🚫 Organic scanner REJECTED ${symbol}: bundle ratio {bundle_ratio:.0%} > {max_bundle:.0%}")
                self.organic_rejected.add(token_address)
                return

        # Rate limit evaluations
        now = datetime.now()
        cooldown = scanner_cfg.get('cooldown_seconds', 60)
        if (now - self.last_organic_eval).total_seconds() < cooldown:
            return
        self.last_organic_eval = now

        # Check candidate limit
        max_candidates = scanner_cfg.get('max_tracked_candidates', 100)
        if len(self.organic_promoted) >= max_candidates:
            return

        # ALL CRITERIA MET - Promote to active tracking!
        symbol = data.get('symbol', token_address[:8])
        self.organic_promoted.add(token_address)

        logger.info("=" * 60)
        bypass_tag = " [VELOCITY BYPASS]" if velocity_bypassed else ""
        logger.info(f"🔬 ORGANIC SCANNER: ${symbol} QUALIFIED!{bypass_tag}")
        logger.info(f"   👥 Buyers: {buyer_count} | 💹 Buy ratio: {buy_ratio:.0%} | ⚡ Bonding: {bonding_pct:.0f}%")
        logger.info(f"   📊 Trades: {total_trades} ({stats['buys']} buys / {stats['sells']} sells)")
        logger.info(f"   🎯 Routing to ActiveTokenTracker for conviction scoring...")
        logger.info("=" * 60)

        # Route to active tracker
        if self.active_tracker:
            try:
                await self.active_tracker.start_tracking(token_address, source='organic_scanner')
                logger.info(f"   ✅ ${symbol} now being tracked (organic discovery)")
            except Exception as e:
                logger.error(f"   ❌ Failed to start tracking ${symbol}: {e}")
        else:
            # Fallback: send via callback
            token_data = await self._extract_token_data(data)
            token_data['source'] = 'organic_scanner'
            await self.on_signal_callback(token_data, 'ORGANIC_DISCOVERY')

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

        # NEW: Add bonding milestone data (velocity tracking)
        if token_address in self.bonding_milestones:
            token_data['bonding_milestones'] = self.bonding_milestones[token_address]

            # Calculate overall bonding velocity (0% -> current%)
            start_time = self.buyer_tracking_start.get(token_address)
            if start_time and bonding_pct > 0:
                elapsed_seconds = (datetime.now() - start_time).total_seconds()
                bonding_velocity = bonding_pct / (elapsed_seconds / 60) if elapsed_seconds > 0 else 0  # %/minute
                token_data['bonding_velocity'] = bonding_velocity
            else:
                token_data['bonding_velocity'] = 0
        
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

    def get_velocity_spike(self, token_address: str) -> Optional[Dict]:
        """
        Get velocity spike data for a token (FOMO acceleration detection)

        Args:
            token_address: Token mint address

        Returns:
            Dict with spike info or None if no spike detected
        """
        spike_data = self.velocity_spikes.get(token_address)
        if spike_data and spike_data['detected']:
            return {
                'detected': True,
                'spike_at_pct': spike_data['spike_at_pct'],
                'bonus_points': 10 if spike_data['spike_at_pct'] >= 60 else 5  # Higher bonus if late-stage spike
            }
        return None
    
    def get_rolling_sol_volume(self, token_address: str, window_seconds: int = 300) -> dict:
        """
        Get rolling SOL volume for a token in current and previous windows.
        Used for pre-graduation volume momentum scoring (DexScreener has no pre-grad data).

        Args:
            token_address: Token mint address
            window_seconds: Size of each rolling window (default 300s = 5 min)

        Returns:
            dict with 'current_window' (SOL in last 5m), 'previous_window' (SOL in 5-10m ago),
            'velocity_ratio' (current/previous), 'total_trades' (trade count in current window)
        """
        history = self.sol_volume_history.get(token_address, [])
        if not history:
            return {'current_window': 0, 'previous_window': 0, 'velocity_ratio': 0, 'total_trades': 0}

        now = datetime.now()
        current_cutoff = now - timedelta(seconds=window_seconds)
        previous_cutoff = now - timedelta(seconds=window_seconds * 2)

        current_window = 0.0
        previous_window = 0.0
        current_trades = 0

        for ts, sol_amt in history:
            if ts > current_cutoff:
                current_window += sol_amt
                current_trades += 1
            elif ts > previous_cutoff:
                previous_window += sol_amt

        # Calculate velocity ratio (current / previous)
        # If no previous window data, use 0 (new token, not enough history)
        velocity_ratio = current_window / previous_window if previous_window > 0 else 0

        return {
            'current_window': current_window,
            'previous_window': previous_window,
            'velocity_ratio': velocity_ratio,
            'total_trades': current_trades
        }

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
                # Also cleanup buyer tracking data
                self.unique_buyers.pop(token, None)
                self.buyer_tracking_start.pop(token, None)
                self.trade_stats.pop(token, None)

            logger.info(f"🧹 Cleaned up {len(tokens_to_remove)} old tokens")

        # Cleanup SOL volume history (trim entries older than 15 min per token)
        vol_tokens_to_clean = []
        for token, history in self.sol_volume_history.items():
            if history:
                cutoff = datetime.now() - timedelta(minutes=15)
                trimmed = [(ts, amt) for ts, amt in history if ts > cutoff]
                if trimmed:
                    self.sol_volume_history[token] = trimmed
                else:
                    vol_tokens_to_clean.append(token)
        for token in vol_tokens_to_clean:
            self.sol_volume_history.pop(token, None)
        if len(self.sol_volume_history) > 2000:
            keys_to_remove = list(self.sol_volume_history.keys())[:1000]
            for k in keys_to_remove:
                self.sol_volume_history.pop(k, None)

        # Cleanup organic scanner data (keep sets bounded)
        if len(self.organic_promoted) > 500:
            self.organic_promoted = set(list(self.organic_promoted)[-200:])
        if len(self.organic_rejected) > 2000:
            self.organic_rejected = set(list(self.organic_rejected)[-500:])
        if len(self.trade_stats) > 2000:
            # Remove oldest entries
            keys_to_remove = list(self.trade_stats.keys())[:1000]
            for k in keys_to_remove:
                self.trade_stats.pop(k, None)
