"""
Active Token Tracker - Real-time monitoring of KOL-bought tokens
Tracks tokens that smart wallets buy and re-analyzes them in real-time
"""
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from loguru import logger
import asyncio


@dataclass
class TokenState:
    """State of an actively tracked token"""
    token_address: str
    token_data: Dict
    conviction_score: int
    signal_sent: bool
    first_tracked_at: datetime
    last_updated: datetime
    kol_buy_count: int
    last_holder_check: datetime
    last_holder_count: int
    source: str = 'kol_buy'  # 'kol_buy' or 'telegram_call'


class ActiveTokenTracker:
    """
    Tracks tokens that KOLs bought and monitors them in real-time
    Re-analyzes on every trade, holder change, or new KOL buy
    """
    
    def __init__(self, conviction_engine, telegram_publisher, db=None, helius_fetcher=None):
        self.conviction_engine = conviction_engine
        self.telegram_publisher = telegram_publisher
        self.db = db
        self.helius_fetcher = helius_fetcher

        # Active tokens being tracked
        self.tracked_tokens: Dict[str, TokenState] = {}

        # Unique buyer tracking (for conviction scoring)
        self.unique_buyers: Dict[str, Set[str]] = {}  # {token_address: set(buyer_wallets)}

        # Metrics
        self.tokens_tracked_total = 0
        self.signals_sent_total = 0
        self.reanalyses_total = 0

        logger.info("🎯 ActiveTokenTracker initialized")
    
    async def start_tracking(self, token_address: str, initial_data: Optional[Dict] = None, source: str = 'kol_buy') -> bool:
        """
        Start tracking a token (triggered by KOL buy or Telegram call)

        Args:
            token_address: Token mint address
            initial_data: Initial token data (optional, will fetch if not provided)
            source: Trigger source ('kol_buy' or 'telegram_call')

        Returns:
            True if tracking started, False if already tracking
        """
        try:
            # Check if already tracking
            if token_address in self.tracked_tokens:
                logger.debug(f"⏭️  Already tracking {token_address[:8]}...")
                # Increment KOL buy count (another KOL bought)
                self.tracked_tokens[token_address].kol_buy_count += 1
                logger.info(f"👑 Another KOL bought {token_address[:8]} (total: {self.tracked_tokens[token_address].kol_buy_count})")
                # Re-analyze with new KOL buy
                await self._reanalyze_token(token_address)
                return False
            
            logger.info(f"🎯 START TRACKING: {token_address[:8]}...")
            
            # Fetch initial token data from Helius
            if self.helius_fetcher:
                logger.info(f"   📡 Fetching data from Helius...")
                try:
                    helius_data = await self.helius_fetcher.get_token_data(token_address)
                    
                    if helius_data:
                        logger.info(f"   ✅ Helius returned data!")
                        logger.info(f"      Symbol: {helius_data.get('token_symbol')}")
                        logger.info(f"      Name: {helius_data.get('token_name')}")
                        
                        # Enrich with DexScreener price data if available
                        initial_data = await self.helius_fetcher.enrich_token_data(helius_data)
                        logger.info(f"   ✅ Got complete data: ${initial_data.get('token_symbol', 'UNKNOWN')}")
                    else:
                        logger.warning(f"   ⚠️ Helius returned None - trying metadata only...")
                        # Try to get just metadata (name/symbol) without bonding curve
                        metadata = await self._fetch_metadata_only(token_address)
                        if metadata:
                            initial_data = self._create_minimal_data(token_address)
                            initial_data.update(metadata)
                            logger.info(f"   ✅ Got metadata: ${metadata.get('token_symbol', 'UNKNOWN')}")
                        else:
                            logger.warning(f"   ⚠️ No metadata available - using minimal fallback")
                            initial_data = self._create_minimal_data(token_address)
                except Exception as e:
                    logger.error(f"   ❌ Helius fetch error: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    # Try metadata only as last resort
                    metadata = await self._fetch_metadata_only(token_address)
                    if metadata:
                        initial_data = self._create_minimal_data(token_address)
                        initial_data.update(metadata)
                    else:
                        initial_data = self._create_minimal_data(token_address)
            else:
                logger.warning(f"   ⚠️ No Helius fetcher initialized - using minimal fallback")
                initial_data = self._create_minimal_data(token_address)
            
            # Create initial state
            now = datetime.utcnow()
            state = TokenState(
                token_address=token_address,
                token_data=initial_data,
                conviction_score=0,
                signal_sent=False,
                first_tracked_at=now,
                last_updated=now,
                kol_buy_count=1 if source == 'kol_buy' else 0,  # Only count as KOL buy if from KOL
                last_holder_check=now,
                last_holder_count=initial_data.get('holder_count', 0),
                source=source
            )
            
            self.tracked_tokens[token_address] = state
            self.tokens_tracked_total += 1
            
            # Do initial analysis
            await self._reanalyze_token(token_address)
            
            logger.info(f"✅ Now tracking {self.get_active_count()} tokens")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error starting tracking for {token_address[:8]}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _create_minimal_data(self, token_address: str) -> Dict:
        """Create minimal token data structure as fallback"""
        return {
            'token_address': token_address,
            'token_name': 'Unknown',
            'token_symbol': 'UNKNOWN',
            'bonding_curve_pct': 0,
            'price_usd': 0,
            'liquidity': 0,
            'volume_24h': 0,
            'volume_1h': 0,
            'volume_5m': 0,
            'market_cap': 0,
            'holder_count': 0,
            'description': '',
            'price_change_5m': 0,
            'price_change_1h': 0,
        }
    
    async def _fetch_metadata_only(self, token_address: str) -> Optional[Dict]:
        """
        Fetch JUST metadata (name/symbol) from Helius
        Used as fallback when full bonding curve decode fails
        """
        try:
            import aiohttp
            import config
            
            url = f"https://api.helius.xyz/v0/token-metadata?api-key={config.HELIUS_API_KEY}"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json={"mintAccounts": [token_address]},
                    timeout=aiohttp.ClientTimeout(total=3)
                ) as resp:
                    if resp.status != 200:
                        return None
                    
                    data = await resp.json()
                    
                    if not data or len(data) == 0:
                        return None
                    
                    asset = data[0]
                    metadata = asset.get('offChainMetadata', {}).get('metadata', {})
                    on_chain = asset.get('onChainMetadata', {}).get('data', {})
                    
                    name = metadata.get('name', on_chain.get('name', 'Unknown'))
                    symbol = metadata.get('symbol', on_chain.get('symbol', 'UNKNOWN'))
                    
                    # Clean up
                    name = name.replace('\x00', '').strip()
                    symbol = symbol.replace('\x00', '').strip()
                    
                    return {
                        'token_name': name,
                        'token_symbol': symbol
                    }
                    
        except Exception as e:
            logger.debug(f"   ⚠️ Metadata fetch error: {e}")
            return None
    
    async def update_token_trade(self, token_address: str, trade_data: Dict) -> None:
        """
        Update token from PumpPortal trade event (REAL-TIME)
        Triggers immediate re-analysis
        
        Args:
            token_address: Token mint address
            trade_data: Trade data from PumpPortal
        """
        if token_address not in self.tracked_tokens:
            return
        
        try:
            state = self.tracked_tokens[token_address]
            
            # Calculate price from reserves (PumpPortal doesn't always provide priceUsd)
            market_cap_sol = trade_data.get('marketCapSol', 0)
            v_sol_reserves = trade_data.get('vSolInBondingCurve', 0)
            
            # Constants
            TOTAL_SUPPLY = 1_000_000_000  # 1 billion tokens
            SOL_PRICE_USD = 150  # TODO: Fetch live SOL price
            
            # Calculate price from market cap
            price_sol = market_cap_sol / TOTAL_SUPPLY if market_cap_sol > 0 else 0
            price_usd = price_sol * SOL_PRICE_USD
            
            # Calculate liquidity (SOL in bonding curve)
            liquidity_usd = v_sol_reserves * SOL_PRICE_USD
            
            # Calculate market cap in USD
            market_cap_usd = market_cap_sol * SOL_PRICE_USD
            
            # Calculate bonding curve %
            bonding_pct = (v_sol_reserves / 85) * 100 if v_sol_reserves > 0 else 0
            bonding_pct = min(bonding_pct, 100)  # Cap at 100%
            
            # Log calculation
            if v_sol_reserves > 0:
                logger.info(f"   💰 Calculated from PumpPortal: price=${price_usd:.8f}, mcap=${market_cap_usd:.0f}, bonding={bonding_pct:.1f}%")
            
            # Update token data with latest trade info
            state.token_data.update({
                'token_name': trade_data.get('name', state.token_data.get('token_name', 'Unknown')),
                'token_symbol': trade_data.get('symbol', state.token_data.get('token_symbol', 'UNKNOWN')),
                'bonding_curve_pct': bonding_pct,
                'volume_5m': trade_data.get('volume5m', state.token_data.get('volume_5m', 0)),
                'volume_1h': trade_data.get('volume1h', state.token_data.get('volume_1h', 0)),
                'price_usd': price_usd,
                'price_change_5m': trade_data.get('priceChange5mPercent', state.token_data.get('price_change_5m', 0)),
                'liquidity': liquidity_usd,
                'market_cap': market_cap_usd,
            })
            
            state.last_updated = datetime.utcnow()
            
            # Log data quality for debugging
            symbol = state.token_data.get('token_symbol', 'UNKNOWN')
            price = state.token_data.get('price_usd', 0)
            mcap = state.token_data.get('market_cap', 0)
            liq = state.token_data.get('liquidity', 0)
            
            logger.info(f"   📊 Updated {symbol}: price=${price:.8f}, mcap=${mcap:.0f}, liq=${liq:.0f}")
            
            # Re-analyze with updated data
            await self._reanalyze_token(token_address)
            
        except Exception as e:
            logger.error(f"❌ Error updating token trade: {e}")
    
    async def update_holder_count(self, token_address: str, holder_count: int) -> None:
        """
        Update holder count for a tracked token
        Triggers re-analysis if holder count changed
        
        Args:
            token_address: Token mint address
            holder_count: New holder count
        """
        if token_address not in self.tracked_tokens:
            return
        
        try:
            state = self.tracked_tokens[token_address]
            
            # Check if holder count changed significantly
            if holder_count != state.last_holder_count:
                logger.debug(f"👥 Holder update: {token_address[:8]} {state.last_holder_count} → {holder_count}")
                
                state.token_data['holder_count'] = holder_count
                state.last_holder_count = holder_count
                state.last_holder_check = datetime.utcnow()
                
                # Re-analyze with new holder count
                await self._reanalyze_token(token_address)
            
        except Exception as e:
            logger.error(f"❌ Error updating holder count: {e}")
    
    async def smart_poll_token(self, token_address: str) -> None:
        """
        Poll token for updates (WITH CREDIT OPTIMIZATION)

        Polling strategy:
        - Fixed 30-second interval
        - Uses Helius bonding curve + DexScreener
        - SKIPS tokens below conviction threshold (saves credits!)

        Args:
            token_address: Token mint address
        """
        if token_address not in self.tracked_tokens:
            return

        if not self.helius_fetcher:
            return

        try:
            import config

            state = self.tracked_tokens[token_address]

            # CREDIT OPTIMIZATION: Skip polling low-conviction tokens
            if config.DISABLE_POLLING_BELOW_THRESHOLD:
                if state.conviction_score < 50 and not state.signal_sent:
                    logger.debug(f"⏭️  Skipping poll for {state.token_data.get('token_symbol', 'UNKNOWN')} (conviction={state.conviction_score} < 50)")
                    return

            # Simple fixed interval (30s)
            poll_interval = 30

            # Check if it's time to poll
            now = datetime.utcnow()
            time_since_last_poll = (now - state.last_updated).total_seconds()

            if time_since_last_poll < poll_interval:
                return  # Not time yet

            # Fetch fresh data
            symbol = state.token_data.get('token_symbol', 'UNKNOWN')
            logger.debug(f"🔄 Polling {symbol} (interval: {poll_interval}s, conviction={state.conviction_score})")

            # get_token_data uses Helius + bonding curve decoder
            token_data = await self.helius_fetcher.get_token_data(token_address)

            if token_data:
                # Update token data
                state.token_data.update(token_data)
                state.last_updated = now

                price = token_data.get('price_usd', 0)
                holders = token_data.get('holder_count', 0)
                logger.debug(f"   ✅ Updated: price=${price:.8f}, holders={holders}")

                # Re-analyze with fresh data
                await self._reanalyze_token(token_address)

        except Exception as e:
            logger.error(f"❌ Error polling token: {e}")
    
    async def _reanalyze_token(self, token_address: str) -> None:
        """
        Re-analyze a tracked token and send signal if threshold crossed
        
        Args:
            token_address: Token mint address
        """
        if token_address not in self.tracked_tokens:
            return
        
        try:
            state = self.tracked_tokens[token_address]
            self.reanalyses_total += 1
            
            # Get fresh conviction score
            conviction_data = await self.conviction_engine.analyze_token(
                token_address,
                state.token_data
            )
            
            new_score = conviction_data.get('score', 0)
            old_score = state.conviction_score
            
            # Update score
            state.conviction_score = new_score
            
            # Log score changes
            if new_score != old_score:
                symbol = state.token_data.get('token_symbol', 'UNKNOWN')
                logger.info(f"📈 {symbol}: {old_score} → {new_score} conviction")
                
                # Log data summary when score changes
                logger.debug(f"   Data: symbol={state.token_data.get('token_symbol')}, "
                           f"price=${state.token_data.get('price_usd', 0):.8f}, "
                           f"mcap=${state.token_data.get('market_cap', 0):.0f}, "
                           f"liq=${state.token_data.get('liquidity', 0):.0f}")
            
            # Check if we should send signal
            from config import MIN_CONVICTION_SCORE
            
            # Strict validation - don't send signal if token data is incomplete
            symbol = state.token_data.get('token_symbol', 'UNKNOWN')
            name = state.token_data.get('token_name', 'Unknown')
            price = state.token_data.get('price_usd', 0)
            mcap = state.token_data.get('market_cap', 0)
            liq = state.token_data.get('liquidity', 0)
            
            has_real_data = (
                symbol not in ['UNKNOWN', '', None] and
                name not in ['Unknown', '', None] and
                price > 0 and
                mcap > 0 and
                liq > 0
            )
            
            if new_score >= MIN_CONVICTION_SCORE and not state.signal_sent:
                if has_real_data:
                    logger.info(f"✅ {symbol} ready to signal: score={new_score}, price=${price:.8f}, mcap=${mcap:.0f}")
                    await self._send_signal(token_address, conviction_data)
                else:
                    # Log exactly what's missing
                    missing = []
                    if symbol in ['UNKNOWN', '', None]:
                        missing.append(f"symbol={symbol}")
                    if name in ['Unknown', '', None]:
                        missing.append(f"name={name}")
                    if price <= 0:
                        missing.append(f"price=${price}")
                    if mcap <= 0:
                        missing.append(f"mcap=${mcap}")
                    if liq <= 0:
                        missing.append(f"liq=${liq}")
                    
                    logger.warning(f"⏳ {symbol}: Score {new_score} but missing data: {', '.join(missing)}")
            
        except Exception as e:
            logger.error(f"❌ Error re-analyzing token: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def _send_signal(self, token_address: str, conviction_data: Dict) -> None:
        """
        Send signal to Telegram
        
        Args:
            token_address: Token mint address
            conviction_data: Conviction analysis data
        """
        try:
            state = self.tracked_tokens[token_address]
            symbol = state.token_data.get('token_symbol', 'UNKNOWN')
            score = conviction_data.get('score', 0)
            
            logger.info(f"🚀 SENDING SIGNAL: ${symbol} ({score}/100)")
            
            # Add signal metadata
            conviction_data['signal_type'] = 'KOL_TRIGGERED'
            conviction_data['bonding_curve_pct'] = state.token_data.get('bonding_curve_pct', 0)
            conviction_data['kol_buy_count'] = state.kol_buy_count
            
            # Save to database
            if self.db:
                await self.db.insert_signal({
                    'token_address': token_address,
                    'token_name': state.token_data.get('token_name'),
                    'token_symbol': symbol,
                    'signal_type': 'KOL_TRIGGERED',
                    'bonding_curve_pct': state.token_data.get('bonding_curve_pct', 0),
                    'conviction_score': score,
                    'entry_price': state.token_data.get('price_usd', 0),
                    'liquidity': state.token_data.get('liquidity', 0),
                    'volume_24h': state.token_data.get('volume_24h', 0),
                    'market_cap': state.token_data.get('market_cap', 0),
                })
            
            # Post to Telegram
            message_id = await self.telegram_publisher.post_signal(conviction_data)
            
            # Mark as sent
            if message_id:
                state.signal_sent = True
                self.signals_sent_total += 1
                
                if self.db:
                    await self.db.mark_signal_posted(token_address, message_id)
                
                logger.info(f"✅ Signal sent for ${symbol}")
            
        except Exception as e:
            logger.error(f"❌ Error sending signal: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def track_buyers_from_webhook(self, token_address: str, webhook_transactions: List[Dict]) -> int:
        """
        Track unique buyers from Helius webhook transactions

        Args:
            token_address: Token mint address
            webhook_transactions: List of Helius enhanced transactions

        Returns:
            Count of unique buyers for this token
        """
        try:
            # Initialize set if needed
            if token_address not in self.unique_buyers:
                self.unique_buyers[token_address] = set()

            # Extract buyer addresses from token transfers
            for transaction in webhook_transactions:
                token_transfers = transaction.get('tokenTransfers', [])

                for transfer in token_transfers:
                    # Check if this transfer is for our token
                    if transfer.get('mint') == token_address:
                        # Get the receiver (buyer)
                        buyer = transfer.get('toUserAccount', '')
                        if buyer:
                            self.unique_buyers[token_address].add(buyer)

            buyer_count = len(self.unique_buyers[token_address])
            logger.debug(f"👥 {token_address[:8]}: {buyer_count} unique buyers")
            return buyer_count

        except Exception as e:
            logger.error(f"❌ Error tracking buyers from webhook: {e}")
            return 0

    def is_tracked(self, token_address: str) -> bool:
        """Check if token is being tracked"""
        return token_address in self.tracked_tokens
    
    def get_active_tokens(self) -> List[str]:
        """Get list of actively tracked token addresses"""
        return list(self.tracked_tokens.keys())
    
    def get_active_count(self) -> int:
        """Get count of actively tracked tokens"""
        return len(self.tracked_tokens)
    
    def get_state(self, token_address: str) -> Optional[TokenState]:
        """Get state of a tracked token"""
        return self.tracked_tokens.get(token_address)

    def get_token_trades(self, token_address: str) -> List[Dict]:
        """
        Get trades for a token (returns empty list - trade tracking is done by PumpPortal).
        This stub exists for compatibility with ConvictionEngine's bundle detection.
        """
        return []
    
    def cleanup_old_tokens(self, max_age_hours: int = 24):
        """
        Remove tokens that are too old or have been signaled
        CREDIT OPTIMIZATION: Remove low-conviction tokens quickly!

        Args:
            max_age_hours: Maximum age in hours before removal
        """
        import config

        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        low_conviction_cutoff = datetime.utcnow() - timedelta(minutes=30)  # Remove low-conviction after 30 min

        tokens_to_remove = []

        for token_address, state in self.tracked_tokens.items():
            # Remove if:
            # 1. Signal already sent AND been tracking for > 1 hour
            # 2. Been tracking for > max_age_hours with no signal
            # 3. CREDIT OPTIMIZATION: Low conviction (< 30) for > 30 minutes

            if state.signal_sent and (datetime.utcnow() - state.first_tracked_at).total_seconds() > 3600:
                tokens_to_remove.append(token_address)
            elif state.first_tracked_at < cutoff:
                tokens_to_remove.append(token_address)
            elif config.DISABLE_POLLING_BELOW_THRESHOLD and state.conviction_score < 30 and state.first_tracked_at < low_conviction_cutoff:
                # Remove low-conviction tokens after 30 minutes to save credits
                tokens_to_remove.append(token_address)

        for token_address in tokens_to_remove:
            symbol = self.tracked_tokens[token_address].token_data.get('token_symbol', 'UNKNOWN')
            score = self.tracked_tokens[token_address].conviction_score
            logger.debug(f"🧹 Removing {symbol} from tracking (conviction={score})")
            del self.tracked_tokens[token_address]

            # Also remove unique buyer data
            if token_address in self.unique_buyers:
                del self.unique_buyers[token_address]

        if tokens_to_remove:
            logger.info(f"🧹 Cleaned up {len(tokens_to_remove)} tokens, {self.get_active_count()} remain")
    
    def get_stats(self) -> Dict:
        """Get tracker statistics"""
        return {
            'active_tokens': self.get_active_count(),
            'tokens_tracked_total': self.tokens_tracked_total,
            'signals_sent': self.signals_sent_total,
            'reanalyses_total': self.reanalyses_total,
        }
