"""
Active Token Tracker - Real-time monitoring of KOL-bought tokens
Tracks tokens that smart wallets buy and re-analyzes them in real-time
"""
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from loguru import logger
import asyncio
import aiohttp


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


class ActiveTokenTracker:
    """
    Tracks tokens that KOLs bought and monitors them in real-time
    Re-analyzes on every trade, holder change, or new KOL buy
    """
    
    def __init__(self, conviction_engine, telegram_publisher, db=None):
        self.conviction_engine = conviction_engine
        self.telegram_publisher = telegram_publisher
        self.db = db
        
        # Active tokens being tracked
        self.tracked_tokens: Dict[str, TokenState] = {}
        
        # Metrics
        self.tokens_tracked_total = 0
        self.signals_sent_total = 0
        self.reanalyses_total = 0
        
        logger.info("🎯 ActiveTokenTracker initialized")
    
    async def start_tracking(self, token_address: str, initial_data: Optional[Dict] = None) -> bool:
        """
        Start tracking a token (triggered by KOL buy)
        
        Args:
            token_address: Token mint address
            initial_data: Initial token data (optional, will fetch if not provided)
            
        Returns:
            True if tracking started, False if already tracking
        """
        try:
            # Check if already tracking
            if token_address in self.tracked_tokens:
                logger.debug(f"⏭️  Already tracking {token_address[:8]}...")
                # Still do initial analysis in case it's a NEW KOL buy
                await self._reanalyze_token(token_address)
                return False
            
            logger.info(f"🎯 START TRACKING: {token_address[:8]}...")
            
            # Get initial token data if not provided
            if not initial_data:
                initial_data = await self._fetch_token_data(token_address)
            
            if not initial_data:
                logger.warning(f"⚠️ Could not fetch data for {token_address[:8]}")
                return False
            
            # Create initial state
            now = datetime.utcnow()
            state = TokenState(
                token_address=token_address,
                token_data=initial_data,
                conviction_score=0,
                signal_sent=False,
                first_tracked_at=now,
                last_updated=now,
                kol_buy_count=1,  # Started because of KOL buy
                last_holder_check=now,
                last_holder_count=initial_data.get('holder_count', 0)
            )
            
            self.tracked_tokens[token_address] = state
            self.tokens_tracked_total += 1
            
            # Do initial analysis
            await self._reanalyze_token(token_address)
            
            logger.info(f"✅ Now tracking {self.get_active_count()} tokens")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error starting tracking for {token_address[:8]}: {e}")
            return False
    
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
            
            # Update token data with latest trade info
            state.token_data.update({
                'bonding_curve_pct': trade_data.get('bondingCurvePercentage', state.token_data.get('bonding_curve_pct', 0)),
                'volume_5m': trade_data.get('volume5m', state.token_data.get('volume_5m', 0)),
                'volume_1h': trade_data.get('volume1h', state.token_data.get('volume_1h', 0)),
                'price_usd': trade_data.get('priceUsd', state.token_data.get('price_usd', 0)),
                'price_change_5m': trade_data.get('priceChange5mPercent', state.token_data.get('price_change_5m', 0)),
                'liquidity': trade_data.get('vSolInBondingCurve', 0) * 150,
                'market_cap': trade_data.get('marketCapSol', 0) * 150,
            })
            
            state.last_updated = datetime.utcnow()
            
            logger.debug(f"📊 Trade update: {token_address[:8]} at {state.token_data.get('bonding_curve_pct', 0):.1f}%")
            
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
            
            # Check if we should send signal
            from config import MIN_CONVICTION_SCORE
            
            if new_score >= MIN_CONVICTION_SCORE and not state.signal_sent:
                await self._send_signal(token_address, conviction_data)
            
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
    
    async def _fetch_token_data(self, token_address: str) -> Optional[Dict]:
        """
        Fetch initial token data from DexScreener
        
        Args:
            token_address: Token mint address
            
        Returns:
            Token data dict or None
        """
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        return None
                    
                    data = await resp.json()
                    pairs = data.get('pairs', [])
                    
                    if not pairs:
                        return None
                    
                    pair = pairs[0]
                    
                    return {
                        'token_address': token_address,
                        'token_name': pair.get('baseToken', {}).get('name', ''),
                        'token_symbol': pair.get('baseToken', {}).get('symbol', ''),
                        'bonding_curve_pct': 0,  # Unknown initially
                        'price_usd': float(pair.get('priceUsd', 0)),
                        'liquidity': pair.get('liquidity', {}).get('usd', 0),
                        'volume_24h': pair.get('volume', {}).get('h24', 0),
                        'volume_1h': pair.get('volume', {}).get('h1', 0),
                        'volume_5m': pair.get('volume', {}).get('m5', 0),
                        'market_cap': pair.get('marketCap', 0),
                        'holder_count': 0,  # Will fetch separately
                        'description': '',
                    }
                    
        except Exception as e:
            logger.error(f"❌ Error fetching token data: {e}")
            return None
    
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
    
    def cleanup_old_tokens(self, max_age_hours: int = 24):
        """
        Remove tokens that are too old or have been signaled
        
        Args:
            max_age_hours: Maximum age in hours before removal
        """
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        tokens_to_remove = []
        
        for token_address, state in self.tracked_tokens.items():
            # Remove if:
            # 1. Signal already sent AND been tracking for > 1 hour
            # 2. Been tracking for > max_age_hours with no signal
            
            if state.signal_sent and (datetime.utcnow() - state.first_tracked_at).total_seconds() > 3600:
                tokens_to_remove.append(token_address)
            elif state.first_tracked_at < cutoff:
                tokens_to_remove.append(token_address)
        
        for token_address in tokens_to_remove:
            symbol = self.tracked_tokens[token_address].token_data.get('token_symbol', 'UNKNOWN')
            logger.debug(f"🧹 Removing {symbol} from tracking")
            del self.tracked_tokens[token_address]
        
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
