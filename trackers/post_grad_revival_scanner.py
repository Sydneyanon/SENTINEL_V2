"""
Post-Graduation Revival Scanner

Monitors recently graduated tokens for "bottom reversal" patterns.
Many tokens graduate, dump 50-80%, consolidate, then do 5-10x.

Strategy:
1. Track all graduations from PumpPortal (already happening)
2. Keep watchlist of graduated tokens for 48h
3. Poll DexScreener every 60s for price/volume
4. Detect revival signals: volume spike + price uptick from local low
5. Trigger tracking when revival pattern detected

Revival Criteria:
- Graduated in last 48h
- Price dropped >40% from graduation price (can go to $10-20K MCAP)
- Volume spike: >$5K in last 5min OR >$20K in last 1h
- Price uptick: >15% from local low (last 1h)
- MCAP sweet spot: $10K - $200K
"""
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from loguru import logger
import config


@dataclass
class GraduatedToken:
    """State of a graduated token being watched for revival"""
    token_address: str
    symbol: str
    graduation_time: datetime
    graduation_price: float  # USD price at graduation
    graduation_mcap: float   # MCAP at graduation (~$69K typically)

    # Tracking state
    lowest_price_seen: float = 0.0
    lowest_mcap_seen: float = 0.0
    lowest_seen_at: datetime = None
    last_checked: datetime = None

    # Revival detection
    revival_triggered: bool = False
    revival_price: float = 0.0
    revival_mcap: float = 0.0


class PostGradRevivalScanner:
    """
    Monitors graduated tokens for bottom reversal patterns.

    The classic pattern: Graduate at $69K → dump to $15-30K → moon to $500K+
    We want to catch the reversal, not the graduation.
    """

    def __init__(self, active_tracker=None, on_revival_callback=None):
        self.active_tracker = active_tracker
        self.on_revival_callback = on_revival_callback

        # Watchlist of graduated tokens
        self.watchlist: Dict[str, GraduatedToken] = {}

        # Already triggered (don't re-trigger)
        self.triggered_tokens: Set[str] = set()

        # Config
        self.config = config.POST_GRAD_REVIVAL_SCANNER if hasattr(config, 'POST_GRAD_REVIVAL_SCANNER') else {
            'enabled': True,
            'watchlist_hours': 48,           # How long to watch after graduation
            'min_drop_pct': 40,              # Min % drop from graduation price to watch
            'min_recovery_pct': 15,          # Min % recovery from local low to trigger
            'min_volume_5m': 5000,           # Min 5m volume (USD) for revival signal
            'min_volume_1h': 20000,          # Min 1h volume (USD) for revival signal
            'min_mcap': 10000,               # Min MCAP to consider ($10K)
            'max_mcap': 200000,              # Max MCAP to consider ($200K)
            'poll_interval': 60,             # Seconds between DexScreener polls
            'max_watchlist_size': 100,       # Limit watchlist to prevent API spam
        }

        self.running = False
        self.stats = {
            'graduations_tracked': 0,
            'revivals_detected': 0,
            'tokens_expired': 0,
        }

        logger.info("🔄 PostGradRevivalScanner initialized")
        logger.info(f"   Watchlist duration: {self.config['watchlist_hours']}h")
        logger.info(f"   Min drop to watch: {self.config['min_drop_pct']}%")
        logger.info(f"   Min recovery to trigger: {self.config['min_recovery_pct']}%")
        logger.info(f"   MCAP range: ${self.config['min_mcap']:,} - ${self.config['max_mcap']:,}")
        if self.config.get('graduation_momentum_enabled', True):
            logger.info(f"   Graduation momentum: ENABLED (vol>${self.config.get('momentum_min_volume_1h', 50000):,})")

    async def add_graduation(self, token_address: str, symbol: str, graduation_price: float = None, graduation_mcap: float = None):
        """
        Handle a newly graduated token.
        1. Check if it has strong momentum → track immediately
        2. Otherwise → add to watchlist for revival monitoring
        """
        if not self.config.get('enabled', True):
            return

        if token_address in self.triggered_tokens:
            logger.debug(f"🔄 {symbol} already triggered, skipping")
            return

        if token_address in self.watchlist:
            logger.debug(f"🔄 {symbol} already in revival watchlist")
            return

        # Default graduation MCAP (~$69K for pump.fun)
        if not graduation_mcap:
            graduation_mcap = 69000
        if not graduation_price:
            graduation_price = graduation_mcap / 1_000_000_000  # Assume 1B supply

        self.stats['graduations_tracked'] += 1

        # CHECK GRADUATION MOMENTUM: Track hot tokens immediately
        if self.config.get('graduation_momentum_enabled', True):
            momentum_triggered = await self._check_graduation_momentum(
                token_address, symbol, graduation_mcap
            )
            if momentum_triggered:
                return  # Already triggered tracking, don't add to watchlist

        # No momentum → add to watchlist for revival monitoring
        # Limit watchlist size
        if len(self.watchlist) >= self.config['max_watchlist_size']:
            oldest = min(self.watchlist.values(), key=lambda x: x.graduation_time)
            del self.watchlist[oldest.token_address]
            logger.debug(f"🔄 Removed oldest from watchlist: {oldest.symbol}")

        token = GraduatedToken(
            token_address=token_address,
            symbol=symbol,
            graduation_time=datetime.utcnow(),
            graduation_price=graduation_price,
            graduation_mcap=graduation_mcap,
            lowest_price_seen=graduation_price,
            lowest_mcap_seen=graduation_mcap,
            lowest_seen_at=datetime.utcnow(),
        )

        self.watchlist[token_address] = token
        logger.info(f"🎓 Added to revival watchlist: ${symbol} (graduated at ${graduation_mcap:,.0f} MCAP)")
        logger.debug(f"   Watchlist size: {len(self.watchlist)}")

    async def _check_graduation_momentum(self, token_address: str, symbol: str, graduation_mcap: float) -> bool:
        """
        Check if a newly graduated token has strong momentum.
        If yes, track immediately instead of waiting for a dump.

        Returns True if momentum triggered tracking.
        """
        cfg = self.config
        try:
            # Fetch current data from DexScreener
            data = await self._fetch_dexscreener_batch([token_address])
            if not data or token_address not in data:
                return False

            pair = data[token_address]
            mcap = float(pair.get('marketCap', 0) or 0)
            volume_1h = float(pair.get('volume', {}).get('h1', 0) or 0)
            price_change_1h = float(pair.get('priceChange', {}).get('h1', 0) or 0)

            # Check momentum criteria
            min_volume = cfg.get('momentum_min_volume_1h', 50000)
            min_price_change = cfg.get('momentum_min_price_change', 5)
            max_mcap = cfg.get('momentum_max_mcap', 300000)

            has_volume = volume_1h >= min_volume
            has_momentum = price_change_1h >= min_price_change
            mcap_ok = mcap <= max_mcap

            if has_volume and has_momentum and mcap_ok:
                # HOT GRADUATION - track immediately!
                self.triggered_tokens.add(token_address)
                self.stats['momentum_triggers'] = self.stats.get('momentum_triggers', 0) + 1

                logger.info("=" * 60)
                logger.info(f"🔥 GRADUATION MOMENTUM: ${symbol}")
                logger.info(f"   💰 Volume 1h: ${volume_1h:,.0f} (min: ${min_volume:,})")
                logger.info(f"   📈 Price change: +{price_change_1h:.1f}% (min: {min_price_change}%)")
                logger.info(f"   💎 MCAP: ${mcap:,.0f}")
                logger.info(f"   🎯 Triggering immediate tracking...")
                logger.info("=" * 60)

                # Trigger tracking
                if self.active_tracker:
                    try:
                        await self.active_tracker.start_tracking(
                            token_address,
                            initial_data={
                                'token_symbol': symbol,
                                'token_name': symbol,
                                'market_cap': mcap,
                                'bonding_curve_pct': 100,
                            },
                            source='graduation_momentum'
                        )
                    except Exception as e:
                        logger.error(f"❌ Failed to start tracking: {e}")

                return True

        except Exception as e:
            logger.debug(f"Momentum check error for {symbol}: {e}")

        return False

    async def start(self):
        """Start the revival scanner background task"""
        if not self.config.get('enabled', True):
            logger.info("🔄 PostGradRevivalScanner disabled in config")
            return

        self.running = True
        logger.info("🔄 Starting PostGradRevivalScanner polling loop...")

        while self.running:
            try:
                await self._poll_watchlist()
                await asyncio.sleep(self.config['poll_interval'])
            except Exception as e:
                logger.error(f"❌ Revival scanner error: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                await asyncio.sleep(30)  # Back off on error

    async def stop(self):
        """Stop the scanner"""
        self.running = False
        logger.info("🔄 PostGradRevivalScanner stopped")

    async def _poll_watchlist(self):
        """Poll DexScreener for all watchlist tokens"""
        if not self.watchlist:
            return

        now = datetime.utcnow()
        expired = []
        to_check = []

        # Filter: remove expired, collect tokens to check
        for addr, token in self.watchlist.items():
            age_hours = (now - token.graduation_time).total_seconds() / 3600

            if age_hours > self.config['watchlist_hours']:
                expired.append(addr)
                continue

            # Only check if not recently checked (rate limiting)
            if token.last_checked:
                since_check = (now - token.last_checked).total_seconds()
                if since_check < self.config['poll_interval'] - 5:
                    continue

            to_check.append(token)

        # Remove expired
        for addr in expired:
            symbol = self.watchlist[addr].symbol
            del self.watchlist[addr]
            self.stats['tokens_expired'] += 1
            logger.debug(f"🔄 Expired from watchlist: ${symbol}")

        if not to_check:
            return

        # Batch fetch from DexScreener (max 30 per request)
        for i in range(0, len(to_check), 30):
            batch = to_check[i:i+30]
            addresses = [t.token_address for t in batch]

            try:
                data = await self._fetch_dexscreener_batch(addresses)
                if data:
                    await self._process_batch(batch, data)
            except Exception as e:
                logger.error(f"❌ DexScreener batch fetch error: {e}")

            await asyncio.sleep(1)  # Rate limit between batches

    async def _fetch_dexscreener_batch(self, addresses: List[str]) -> Dict:
        """Fetch token data from DexScreener"""
        if not addresses:
            return {}

        url = f"https://api.dexscreener.com/latest/dex/tokens/{','.join(addresses)}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {p['baseToken']['address']: p for p in data.get('pairs', [])
                                if p.get('chainId') == 'solana' and p.get('baseToken')}
        except Exception as e:
            logger.debug(f"DexScreener fetch error: {e}")

        return {}

    async def _process_batch(self, tokens: List[GraduatedToken], data: Dict):
        """Process a batch of token data and check for revival signals"""
        now = datetime.utcnow()

        for token in tokens:
            token.last_checked = now

            pair = data.get(token.token_address)
            if not pair:
                continue

            try:
                price_usd = float(pair.get('priceUsd', 0) or 0)
                mcap = float(pair.get('marketCap', 0) or 0)
                volume_5m = float(pair.get('volume', {}).get('m5', 0) or 0)
                volume_1h = float(pair.get('volume', {}).get('h1', 0) or 0)
                price_change_1h = float(pair.get('priceChange', {}).get('h1', 0) or 0)

                if price_usd <= 0 or mcap <= 0:
                    continue

                # Update lowest seen
                if mcap < token.lowest_mcap_seen or token.lowest_mcap_seen == 0:
                    token.lowest_mcap_seen = mcap
                    token.lowest_price_seen = price_usd
                    token.lowest_seen_at = now

                # Check revival criteria
                await self._check_revival(token, price_usd, mcap, volume_5m, volume_1h, price_change_1h)

            except Exception as e:
                logger.debug(f"Error processing {token.symbol}: {e}")

    async def _check_revival(self, token: GraduatedToken, price: float, mcap: float,
                            vol_5m: float, vol_1h: float, pct_change_1h: float):
        """Check if token shows revival signals"""

        cfg = self.config

        # Already triggered?
        if token.token_address in self.triggered_tokens:
            return

        # MCAP in range?
        if mcap < cfg['min_mcap'] or mcap > cfg['max_mcap']:
            return

        # Has it dropped enough from graduation?
        drop_from_grad = ((token.graduation_mcap - token.lowest_mcap_seen) / token.graduation_mcap) * 100
        if drop_from_grad < cfg['min_drop_pct']:
            return

        # Is it recovering from the low?
        if token.lowest_mcap_seen > 0:
            recovery_pct = ((mcap - token.lowest_mcap_seen) / token.lowest_mcap_seen) * 100
        else:
            recovery_pct = 0

        # Volume check (either 5m or 1h threshold)
        has_volume = vol_5m >= cfg['min_volume_5m'] or vol_1h >= cfg['min_volume_1h']

        # Recovery check
        has_recovery = recovery_pct >= cfg['min_recovery_pct'] or pct_change_1h >= cfg['min_recovery_pct']

        # REVIVAL DETECTED!
        if has_volume and has_recovery:
            await self._trigger_revival(token, price, mcap, vol_5m, vol_1h, recovery_pct, drop_from_grad)

    async def _trigger_revival(self, token: GraduatedToken, price: float, mcap: float,
                               vol_5m: float, vol_1h: float, recovery_pct: float, drop_pct: float):
        """Trigger tracking for a revival candidate"""

        self.triggered_tokens.add(token.token_address)
        self.stats['revivals_detected'] += 1

        token.revival_triggered = True
        token.revival_price = price
        token.revival_mcap = mcap

        logger.info("=" * 60)
        logger.info(f"🔄 REVIVAL DETECTED: ${token.symbol}")
        logger.info(f"   📉 Dropped {drop_pct:.0f}% from graduation (${token.graduation_mcap:,.0f} → ${token.lowest_mcap_seen:,.0f})")
        logger.info(f"   📈 Recovering {recovery_pct:.0f}% from low (now ${mcap:,.0f})")
        logger.info(f"   💰 Volume: ${vol_5m:,.0f} (5m) / ${vol_1h:,.0f} (1h)")
        logger.info(f"   🎯 Triggering tracking...")
        logger.info("=" * 60)

        # Trigger tracking via active tracker
        if self.active_tracker:
            try:
                await self.active_tracker.start_tracking(
                    token.token_address,
                    initial_data={
                        'token_symbol': token.symbol,
                        'token_name': token.symbol,  # Will be fetched
                        'price_usd': price,
                        'market_cap': mcap,
                        'bonding_curve_pct': 100,  # Post-graduation
                    },
                    source='revival_scanner'
                )
            except Exception as e:
                logger.error(f"❌ Failed to start tracking: {e}")

        # Callback for additional handling
        if self.on_revival_callback:
            try:
                await self.on_revival_callback({
                    'token_address': token.token_address,
                    'symbol': token.symbol,
                    'graduation_mcap': token.graduation_mcap,
                    'lowest_mcap': token.lowest_mcap_seen,
                    'current_mcap': mcap,
                    'drop_pct': drop_pct,
                    'recovery_pct': recovery_pct,
                    'volume_5m': vol_5m,
                    'volume_1h': vol_1h,
                })
            except Exception as e:
                logger.error(f"❌ Revival callback error: {e}")

        # Remove from watchlist (now being tracked)
        if token.token_address in self.watchlist:
            del self.watchlist[token.token_address]

    def get_stats(self) -> Dict:
        """Get scanner statistics"""
        return {
            **self.stats,
            'watchlist_size': len(self.watchlist),
            'triggered_count': len(self.triggered_tokens),
        }

    def get_watchlist_summary(self) -> List[Dict]:
        """Get summary of watchlist for debugging"""
        now = datetime.utcnow()
        summary = []

        for token in sorted(self.watchlist.values(), key=lambda x: x.graduation_time, reverse=True):
            age_hours = (now - token.graduation_time).total_seconds() / 3600
            drop_pct = ((token.graduation_mcap - token.lowest_mcap_seen) / token.graduation_mcap * 100) if token.graduation_mcap > 0 else 0

            summary.append({
                'symbol': token.symbol,
                'address': token.token_address[:8],
                'age_hours': round(age_hours, 1),
                'grad_mcap': token.graduation_mcap,
                'lowest_mcap': token.lowest_mcap_seen,
                'drop_pct': round(drop_pct, 1),
            })

        return summary[:20]  # Top 20
