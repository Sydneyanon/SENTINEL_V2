"""
Active Token Tracker - Real-time monitoring of KOL-bought tokens
Tracks tokens that smart wallets buy and re-analyzes them in real-time
"""
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from loguru import logger
import asyncio
from pumpportal_api import PumpPortalAPI
import config


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
    last_analyzed: datetime = None  # Prevent spam re-analysis


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
        # Initialize PumpPortalAPI with Helius key for metadata fallback
        self.pumpportal_api = PumpPortalAPI(helius_api_key=config.HELIUS_API_KEY)

        # Active tokens being tracked
        self.tracked_tokens: Dict[str, TokenState] = {}

        # Unique buyer tracking (for conviction scoring)
        self.unique_buyers: Dict[str, Set[str]] = {}  # {token_address: set(buyer_wallets)}

        # Pause control (toggled via /pause and /resume admin commands)
        self.signal_posting_paused = False

        # Metrics
        self.tokens_tracked_total = 0
        self.signals_sent_total = 0
        self.reanalyses_total = 0
        self.signals_blocked_data_quality = 0  # OPT-036: Track blocked signals
        self.signals_blocked_emergency_stop = 0  # OPT-023: Track emergency stops

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

            # OPT-035: PARALLEL METADATA FETCHING (saves 1000-1500ms)
            # Fetch from all sources simultaneously instead of sequentially
            import asyncio

            pumpportal_name = initial_data.get('token_name') if initial_data else None
            pumpportal_symbol = initial_data.get('token_symbol') if initial_data else None

            # Check if we need to fetch metadata
            need_metadata = (not pumpportal_name or pumpportal_name in ['Unknown', '']) or \
                           (not pumpportal_symbol or pumpportal_symbol in ['UNKNOWN', ''])

            if need_metadata and self.helius_fetcher:
                logger.info(f"   ⚡ PARALLEL FETCH: PumpPortal + Helius + DexScreener...")

                try:
                    # Launch all fetches in parallel
                    tasks = []

                    # Task 1: PumpPortal metadata
                    async def fetch_pumpportal():
                        try:
                            return await self.pumpportal_api.get_token_metadata(token_address)
                        except Exception as e:
                            logger.warning(f"      ⚠️ PumpPortal error: {e}")
                            return None

                    # Task 2: Helius data
                    async def fetch_helius():
                        try:
                            return await self.helius_fetcher.get_token_data(token_address)
                        except Exception as e:
                            logger.warning(f"      ⚠️ Helius error: {e}")
                            return None

                    tasks = [fetch_pumpportal(), fetch_helius()]

                    # Wait for all fetches simultaneously (PARALLEL!)
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    pump_metadata, helius_data = results

                    # Extract PumpPortal metadata
                    if pump_metadata and not isinstance(pump_metadata, Exception):
                        pumpportal_name = pump_metadata.get('token_name')
                        pumpportal_symbol = pump_metadata.get('token_symbol')
                        logger.info(f"      ✅ PumpPortal: ${pumpportal_symbol} / {pumpportal_name}")

                    # Process Helius data
                    if helius_data and not isinstance(helius_data, Exception):
                        logger.info(f"   ✅ Helius returned data!")
                        logger.info(f"      Symbol: {helius_data.get('token_symbol')}")
                        logger.info(f"      Name: {helius_data.get('token_name')}")

                        # Enrich with DexScreener price data if available
                        merged_data = await self.helius_fetcher.enrich_token_data(helius_data)

                        # Restore PumpPortal metadata if Helius returned Unknown/UNKNOWN
                        if pumpportal_name and pumpportal_name not in ['Unknown', '']:
                            if merged_data.get('token_name') in ['Unknown', '']:
                                merged_data['token_name'] = pumpportal_name
                                logger.info(f"      🔄 Using PumpPortal name: {pumpportal_name}")

                        if pumpportal_symbol and pumpportal_symbol not in ['UNKNOWN', '']:
                            if merged_data.get('token_symbol') in ['UNKNOWN', '']:
                                merged_data['token_symbol'] = pumpportal_symbol
                                logger.info(f"      🔄 Using PumpPortal symbol: {pumpportal_symbol}")

                        initial_data = merged_data
                        logger.info(f"   ✅ Got complete data: ${initial_data.get('token_symbol', 'UNKNOWN')}")
                    else:
                        # Fallback to metadata only
                        logger.warning(f"   ⚠️ Helius returned None - trying metadata only...")
                        metadata = await self._fetch_metadata_only(token_address)
                        if metadata:
                            initial_data = self._create_minimal_data(token_address)
                            initial_data.update(metadata)
                            logger.info(f"   ✅ Got metadata: ${metadata.get('token_symbol', 'UNKNOWN')}")
                        else:
                            logger.warning(f"   ⚠️ No metadata available - using minimal fallback")
                            initial_data = self._create_minimal_data(token_address)

                except Exception as e:
                    logger.error(f"   ❌ Parallel fetch error: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    # Try metadata only as last resort
                    metadata = await self._fetch_metadata_only(token_address)
                    if metadata:
                        initial_data = self._create_minimal_data(token_address)
                        initial_data.update(metadata)
                    else:
                        initial_data = self._create_minimal_data(token_address)
            elif not self.helius_fetcher:
                logger.warning(f"   ⚠️ No Helius fetcher initialized - using minimal fallback")
                initial_data = self._create_minimal_data(token_address)
            else:
                # Already have metadata from initial_data
                logger.info(f"   ✅ Using provided initial_data")
            
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
                source=source,
                last_analyzed=now  # Initialize cooldown timer
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

        OPT-041: Now uses cached helius_fetcher instead of direct API call
        Saves 1-2 Helius credits per call via 60-minute metadata cache
        """
        try:
            # OPT-041: Use helius_fetcher with caching instead of direct API call
            if not self.helius_fetcher:
                logger.debug("   ⚠️ No helius_fetcher available")
                return None

            metadata = await self.helius_fetcher.get_token_metadata_batch(token_address)

            if not metadata:
                return None

            # Extract name and symbol from metadata
            off_chain = metadata.get('offChainMetadata', {}).get('metadata', {})
            on_chain = metadata.get('onChainMetadata', {}).get('data', {})

            name = off_chain.get('name', on_chain.get('name', 'Unknown'))
            symbol = off_chain.get('symbol', on_chain.get('symbol', 'UNKNOWN'))

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
            
            # FIXED: Preserve good metadata - don't overwrite with Unknown/UNKNOWN
            existing_name = state.token_data.get('token_name', '')
            existing_symbol = state.token_data.get('token_symbol', '')
            new_name = trade_data.get('name', '')
            new_symbol = trade_data.get('symbol', '')

            # Debug: Log what PumpPortal is sending
            logger.info(f"      🔍 PumpPortal metadata: name='{new_name}', symbol='{new_symbol}'")

            # If PumpPortal WebSocket sent empty strings, try to fetch from API
            if (not new_name or new_name == '') and (not new_symbol or new_symbol == ''):
                # Only try if we haven't already fetched recently (cache for 5 min)
                last_fetch_time = getattr(state, 'last_metadata_fetch', None)
                now = datetime.utcnow()

                if not last_fetch_time or (now - last_fetch_time).total_seconds() > 300:
                    logger.info(f"      🔄 PumpPortal WebSocket has no metadata, trying REST API...")
                    try:
                        pump_metadata = await self.pumpportal_api.get_token_metadata(token_address)
                        if pump_metadata:
                            new_name = pump_metadata.get('token_name', '')
                            new_symbol = pump_metadata.get('token_symbol', '')
                            logger.info(f"      ✅ Fetched from PumpPortal API: ${new_symbol} / {new_name}")
                        else:
                            logger.debug(f"      ⚠️ PumpPortal API also has no metadata")
                    except Exception as e:
                        logger.debug(f"      ⚠️ PumpPortal API error: {e}")

                    # If PumpPortal API failed, try DexScreener as final fallback
                    if (not new_name or new_name == '') and self.helius_fetcher:
                        logger.info(f"      🔄 PumpPortal failed, trying DexScreener...")
                        try:
                            helius_data = await self.helius_fetcher.get_token_data(token_address)
                            if helius_data and helius_data.get('token_name') and helius_data.get('token_symbol'):
                                new_name = helius_data.get('token_name', '')
                                new_symbol = helius_data.get('token_symbol', '')
                                logger.info(f"      ✅ Fetched from DexScreener: ${new_symbol} / {new_name}")
                            else:
                                logger.debug(f"      ⚠️ DexScreener also has no metadata")
                        except Exception as e:
                            logger.debug(f"      ⚠️ DexScreener error: {e}")

                    state.last_metadata_fetch = now

            # Use new data if it's good, otherwise keep existing good data
            final_name = existing_name  # Start with what we have
            if new_name and new_name not in ['Unknown', '']:
                final_name = new_name  # New data is good, use it
                if existing_name and existing_name not in ['Unknown', ''] and existing_name != new_name:
                    logger.info(f"      🔄 Updating name: '{existing_name}' -> '{new_name}'")
            elif not existing_name or existing_name in ['Unknown', '']:
                final_name = 'Unknown'  # Neither has good data

            final_symbol = existing_symbol  # Start with what we have
            if new_symbol and new_symbol not in ['UNKNOWN', '']:
                final_symbol = new_symbol  # New data is good, use it
                if existing_symbol and existing_symbol not in ['UNKNOWN', ''] and existing_symbol != new_symbol:
                    logger.info(f"      🔄 Updating symbol: '{existing_symbol}' -> '{new_symbol}'")
            elif not existing_symbol or existing_symbol in ['UNKNOWN', '']:
                final_symbol = 'UNKNOWN'  # Neither has good data

            # Update token data with latest trade info
            state.token_data.update({
                'token_name': final_name,
                'token_symbol': final_symbol,
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

            # CREDIT OPTIMIZATION: Tiered polling for low-conviction tokens
            # FIX: Previously hard-skipped tokens < 40 conviction, causing missed runners
            # like $STARTUP (+695%) that started low but pumped before re-analysis
            bonding_pct = state.token_data.get('bonding_curve_pct', 0)
            is_pre_grad = bonding_pct < 100

            if config.DISABLE_POLLING_BELOW_THRESHOLD and not state.signal_sent:
                if state.conviction_score < 0 and not is_pre_grad:
                    # Only skip truly negative-score POST-GRAD tokens
                    logger.debug(f"⏭️  Skipping poll for {state.token_data.get('token_symbol', 'UNKNOWN')} (conviction={state.conviction_score} < 0, post-grad)")
                    return
                # Pre-grad tokens: NEVER skip - they move too fast

            # Tiered polling interval based on conviction
            if state.conviction_score >= 20 or is_pre_grad:
                poll_interval = 30  # Normal: 30s for decent scores or any pre-grad
            else:
                poll_interval = 90  # Slow: 90s for low-conviction post-grad (save credits)

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
                # FIXED: Preserve existing good metadata (don't overwrite with UNKNOWN)
                existing_name = state.token_data.get('token_name', '')
                existing_symbol = state.token_data.get('token_symbol', '')

                # Update token data
                state.token_data.update(token_data)

                # Restore good metadata if Helius returned Unknown/UNKNOWN
                new_name = token_data.get('token_name', '')
                new_symbol = token_data.get('token_symbol', '')

                if new_name in ['Unknown', ''] and existing_name and existing_name not in ['Unknown', '']:
                    state.token_data['token_name'] = existing_name
                    logger.debug(f"   📛 Preserved existing name: {existing_name}")

                if new_symbol in ['UNKNOWN', ''] and existing_symbol and existing_symbol not in ['UNKNOWN', '']:
                    state.token_data['token_symbol'] = existing_symbol
                    logger.debug(f"   🏷️  Preserved existing symbol: {existing_symbol}")

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

            # COOLDOWN: Prevent spam re-analysis (max once per 3 seconds)
            now = datetime.utcnow()
            if state.last_analyzed:
                seconds_since_last = (now - state.last_analyzed).total_seconds()
                if seconds_since_last < 3:
                    logger.debug(f"⏭️  Skipping re-analysis (cooldown: {seconds_since_last:.1f}s < 3s)")
                    return

            state.last_analyzed = now
            self.reanalyses_total += 1

            # Add unique_buyers count to token_data (for display in Telegram)
            unique_buyers_count = len(self.unique_buyers.get(token_address, set()))
            state.token_data['unique_buyers'] = unique_buyers_count

            # Get fresh conviction score
            conviction_data = await self.conviction_engine.analyze_token(
                token_address,
                state.token_data
            )
            
            new_score = conviction_data.get('score', 0)
            old_score = state.conviction_score

            # OPT-023: Check for emergency stop
            if conviction_data.get('emergency_stop', False):
                self.signals_blocked_emergency_stop += 1
                symbol = state.token_data.get('token_symbol', 'UNKNOWN')
                reasons = conviction_data.get('emergency_reasons', [])
                logger.warning(f"🚨 EMERGENCY STOP: ${symbol} blocked - {', '.join(reasons)}")
                logger.warning(f"   📊 Total emergency stops: {self.signals_blocked_emergency_stop}")
                # Don't send signal, exit early
                return

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
            from config import MIN_CONVICTION_SCORE, MAX_MARKET_CAP_FILTER
            
            # Strict validation - don't send signal if token data is incomplete
            # RELAXED: Allow UNKNOWN symbols (Helius often doesn't have metadata for new tokens)
            symbol = state.token_data.get('token_symbol', 'UNKNOWN')
            name = state.token_data.get('token_name', 'Unknown')
            price = state.token_data.get('price_usd', 0)
            mcap = state.token_data.get('market_cap', 0)
            liq = state.token_data.get('liquidity', 0)

            # OPT-036: Strict data quality checks
            # Block signals with missing critical data to prevent posting garbage
            bonding_pct = state.token_data.get('bonding_curve_pct', 0)
            is_pre_grad = bonding_pct < 100

            # Critical data requirements
            data_quality_checks = {
                'price': price > 0,
                'liquidity': liq >= 1000,  # Min $1k liquidity
                'mcap': mcap > 0,
                'mcap_not_too_high': mcap <= MAX_MARKET_CAP_FILTER,  # Not already mooned
            }

            # Holder count check (exempt pre-grad tokens since they're still building)
            if not is_pre_grad:
                holder_count = state.token_data.get('holder_count', 0)
                data_quality_checks['holders'] = holder_count > 0

            has_real_data = all(data_quality_checks.values())
            
            # DIAGNOSTIC: Log every threshold check
            logger.info(f"🔍 THRESHOLD CHECK for {symbol}:")
            logger.info(f"   new_score={new_score}, threshold={MIN_CONVICTION_SCORE}, signal_sent={state.signal_sent}")
            logger.info(f"   Passes: {new_score >= MIN_CONVICTION_SCORE and not state.signal_sent}")

            if new_score >= MIN_CONVICTION_SCORE and not state.signal_sent:
                logger.info(f"   ✅ PASSES threshold check!")
                if has_real_data:
                    logger.info(f"   ✅ Has real data - SENDING SIGNAL")
                    logger.info(f"   📊 conviction_data['score'] = {conviction_data.get('score')}")
                    logger.info(f"   📊 conviction_data['breakdown']['total'] = {conviction_data.get('breakdown', {}).get('total')}")
                    await self._send_signal(token_address, conviction_data)
                else:
                    # OPT-036: Log exactly what quality checks failed
                    failed_checks = []
                    if not data_quality_checks.get('price', True):
                        failed_checks.append(f"price={price} (must be > 0)")
                    if not data_quality_checks.get('liquidity', True):
                        failed_checks.append(f"liquidity=${liq:.0f} (must be >= $1k)")
                    if not data_quality_checks.get('mcap', True):
                        failed_checks.append(f"mcap=${mcap:.0f} (must be > 0)")
                    if not data_quality_checks.get('mcap_not_too_high', True):
                        failed_checks.append(f"mcap=${mcap:.0f} (exceeds max ${MAX_MARKET_CAP_FILTER:.0f} - already mooned)")
                    if not data_quality_checks.get('holders', True):
                        holder_count = state.token_data.get('holder_count', 0)
                        failed_checks.append(f"holders={holder_count} (post-grad must have holders)")

                    self.signals_blocked_data_quality += 1
                    logger.warning(f"🚫 BLOCKED: ${symbol} scored {new_score} but failed data quality checks: {', '.join(failed_checks)}")
                    logger.warning(f"   💡 This prevents posting low-quality signals that are likely rugs")
                    logger.warning(f"   📊 Total blocked (data quality): {self.signals_blocked_data_quality}")
            else:
                logger.info(f"   ⏭️  FAILS threshold check - not sending signal")
            
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
            # Check if signal posting is paused by admin
            if self.signal_posting_paused:
                symbol = self.tracked_tokens[token_address].token_data.get('token_symbol', 'UNKNOWN')
                score = conviction_data.get('score', 0)
                logger.info(f"⏸️  PAUSED: ${symbol} ({score}/100) would have been signaled - posting paused by admin")
                return

            state = self.tracked_tokens[token_address]
            symbol = state.token_data.get('token_symbol', 'UNKNOWN')
            score = conviction_data.get('score', 0)

            # Debug: Log what we're about to send
            logger.info(f"🚀 SENDING SIGNAL: ${symbol} ({score}/100)")
            logger.info(f"   🏷️  state.token_data symbol: {state.token_data.get('token_symbol')}")
            logger.info(f"   🏷️  conviction_data token_data symbol: {conviction_data.get('token_data', {}).get('token_symbol')}")
            
            # Add signal metadata
            conviction_data['signal_type'] = 'KOL_TRIGGERED'
            conviction_data['bonding_curve_pct'] = state.token_data.get('bonding_curve_pct', 0)
            conviction_data['kol_buy_count'] = state.kol_buy_count
            
            # Save to database
            if self.db:
                # Calculate buy percentage for database storage
                buys_24h = state.token_data.get('buys_24h', 0)
                sells_24h = state.token_data.get('sells_24h', 0)
                total_txs = buys_24h + sells_24h
                buy_percentage = (buys_24h / total_txs * 100) if total_txs > 0 else None

                await self.db.insert_signal({
                    'token_address': token_address,
                    'token_name': state.token_data.get('token_name'),
                    'token_symbol': symbol,
                    'signal_type': 'KOL_TRIGGERED',
                    'signal_source': state.source,  # Track whether from kol_buy or telegram_call
                    'bonding_curve_pct': state.token_data.get('bonding_curve_pct', 0),
                    'conviction_score': score,
                    'entry_price': state.token_data.get('price_usd', 0),
                    'liquidity': state.token_data.get('liquidity', 0),
                    'volume_24h': state.token_data.get('volume_24h', 0),
                    'market_cap': state.token_data.get('market_cap', 0),
                    'buys_24h': buys_24h,
                    'sells_24h': sells_24h,
                    'buy_percentage': buy_percentage,
                    'buy_sell_score': conviction_data['breakdown'].get('buy_sell_ratio', 0),
                })
            
            # Post to Telegram
            message_id = await self.telegram_publisher.post_signal(conviction_data)

            # Mark as sent
            if message_id:
                state.signal_sent = True
                self.signals_sent_total += 1

                if self.db:
                    await self.db.mark_signal_posted(token_address, message_id)

                    # OPT-000 PREREQUISITE: Save signal metadata for pattern analysis
                    try:
                        # Extract metadata from conviction_data
                        # Extract KOL wallet data from conviction scoring results
                        sw_data = conviction_data.get('smart_wallet_data', {})
                        sw_wallets = sw_data.get('wallets', [])
                        kol_wallets = [w.get('wallet', w.get('address', '')) for w in sw_wallets] if sw_wallets else []
                        kol_tiers = [w.get('tier', 'unknown') for w in sw_wallets] if sw_wallets else []

                        # Get narratives from conviction breakdown
                        breakdown = conviction_data.get('breakdown', {})
                        narrative_tags = []
                        if breakdown.get('narrative', 0) > 0:
                            # Extract primary narrative if available
                            primary = conviction_data.get('primary_narrative')
                            if primary:
                                narrative_tags.append(primary)

                        # Determine holder pattern from conviction data
                        holder_concentration = breakdown.get('holder_concentration', {})
                        holder_penalty = holder_concentration.get('penalty', 0)
                        if holder_penalty < -20:
                            holder_pattern = 'highly_concentrated'
                        elif holder_penalty < -10:
                            holder_pattern = 'concentrated'
                        elif holder_concentration.get('kol_bonus', 0) > 0:
                            holder_pattern = 'kol_heavy'
                        else:
                            holder_pattern = 'distributed'

                        # Update signal metadata
                        await self.db.update_signal_metadata(
                            token_address=token_address,
                            narrative_tags=narrative_tags,
                            kol_wallets=kol_wallets,
                            kol_tiers=kol_tiers,
                            holder_pattern=holder_pattern
                        )

                        logger.debug(
                            f"📊 Saved metadata: narratives={narrative_tags}, "
                            f"kols={len(kol_wallets)}, pattern={holder_pattern}"
                        )
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to save signal metadata: {e}")

                logger.info(f"✅ Signal sent for ${symbol}")
            else:
                # OPT-051: Log posting failure to database
                logger.error(f"❌ Signal passed but failed to post to Telegram: ${symbol} ({score}/100)")
                if self.db:
                    await self.db.mark_posting_failed(token_address, "telegram_posting_failed")
            
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
        low_conviction_cutoff = datetime.utcnow() - timedelta(hours=2)  # Extended: 30min → 2h (was evicting runners)

        tokens_to_remove = []

        for token_address, state in self.tracked_tokens.items():
            # Remove if:
            # 1. Signal already sent AND been tracking for > 1 hour
            # 2. Been tracking for > max_age_hours with no signal
            # 3. CREDIT OPTIMIZATION: Negative conviction for > 2 hours (truly dead tokens only)
            #    FIX: Was <30 after 30min - this evicted $STARTUP before it could pump

            if state.signal_sent and (datetime.utcnow() - state.first_tracked_at).total_seconds() > 3600:
                tokens_to_remove.append(token_address)
            elif state.first_tracked_at < cutoff:
                tokens_to_remove.append(token_address)
            elif config.DISABLE_POLLING_BELOW_THRESHOLD and state.conviction_score < 0 and state.first_tracked_at < low_conviction_cutoff:
                # Only remove truly negative-score tokens after 2 hours
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
        """Get tracker statistics including social coverage metrics"""
        # Get social coverage stats from PumpPortalAPI
        social_coverage = self.pumpportal_api.get_social_coverage_stats()

        return {
            'active_tokens': self.get_active_count(),
            'tokens_tracked_total': self.tokens_tracked_total,
            'signals_sent': self.signals_sent_total,
            'reanalyses_total': self.reanalyses_total,
            'social_coverage': social_coverage,
        }
