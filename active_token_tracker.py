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
    
    def __init__(self, conviction_engine, telegram_publisher, db=None, pumpportal_monitor=None):
        self.conviction_engine = conviction_engine
        self.telegram_publisher = telegram_publisher
        self.db = db
        self.pumpportal_monitor = pumpportal_monitor  # NEW: for subscribing to specific tokens
        
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
            initial_data: Initial token data (optional, will be populated by PumpPortal)
            
        Returns:
            True if tracking started, False if already tracking
        """
        try:
            # Check if already tracking
            if token_address in self.tracked_tokens:
                logger.debug(f"⏭️  Already tracking {token_address[:8]}...")
                # Still increment KOL buy count (another KOL bought)
                self.tracked_tokens[token_address].kol_buy_count += 1
                # Re-analyze with new KOL buy
                await self._reanalyze_token(token_address)
                return False
            
            logger.info(f"🎯 START TRACKING: {token_address[:8]}...")
            
            # Create minimal initial data if not provided
            # PumpPortal will populate this via trade updates
            if not initial_data:
                initial_data = {
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
                logger.info(f"   📊 Waiting for PumpPortal data...")
            
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
                last_holder_count=0
            )
            
            self.tracked_tokens[token_address] = state
            self.tokens_tracked_total += 1
            
            # Do initial analysis (will show KOL buy points at minimum)
            await self._reanalyze_token(token_address)
            
            logger.info(f"✅ Now tracking {self.get_active_count()} tokens")
            
            # Subscribe to this token's trades on PumpPortal
            await self._subscribe_to_token_trades(token_address)
            
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
                'token_name': trade_data.get('name', state.token_data.get('token_name', 'Unknown')),
                'token_symbol': trade_data.get('symbol', state.token_data.get('token_symbol', 'UNKNOWN')),
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
    
    async def _subscribe_to_token_trades(self, token_address: str) -> None:
        """
        Subscribe to trades for a specific token on PumpPortal
        
        Args:
            token_address: Token mint address
        """
        if not self.pumpportal_monitor or not self.pumpportal_monitor.ws:
            logger.debug(f"⚠️ PumpPortal not available for subscription")
            return
        
        try:
            import json
            await self.pumpportal_monitor.ws.send(json.dumps({
                "method": "subscribeTokenTrade",
                "keys": [token_address]
            }))
            logger.debug(f"📡 Subscribed to trades for {token_address[:8]}")
        except Exception as e:
            logger.debug(f"⚠️ Failed to subscribe to token trades: {e}")
    
    
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
