"""
SENTINEL V3 - Active Token Tracker
Hybrid approach: KOL/Smart wallet triggers tracking, then V2-style continuous analysis.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Set, Optional, Callable
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class TokenState:
    """State for a token being actively tracked."""
    token_address: str
    symbol: str
    name: str
    wallet_address: str  # First wallet that triggered tracking
    wallet_tier: str
    wallet_name: str

    # Tracking timestamps
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_analyzed: Optional[datetime] = None

    # Token data (updated on each analysis)
    graduated: bool = False
    liquidity: float = 0
    mcap: float = 0
    holders: int = 0
    bonding_pct: float = 0

    # Accumulated data from WebSocket
    buys: int = 0
    sells: int = 0
    volume_sol: float = 0
    unique_buyers: Set[str] = field(default_factory=set)

    # Scoring
    last_score: int = 0
    signal_sent: bool = False
    skip_reason: Optional[str] = None

    # Multi-KOL tracking
    kol_buy_count: int = 1
    kol_addresses: Set[str] = field(default_factory=set)


class ActiveTokenTracker:
    """
    Tracks tokens that KOL/smart wallets buy.
    Re-analyzes continuously until signal threshold is crossed or max age reached.
    """

    def __init__(
        self,
        on_signal: Optional[Callable] = None,
        max_age_minutes: int = 60,
        reanalysis_interval: int = 30
    ):
        self.tracked_tokens: Dict[str, TokenState] = {}
        self.on_signal = on_signal  # Callback when signal threshold crossed
        self.max_age_minutes = max_age_minutes
        self.reanalysis_interval = reanalysis_interval

        self._running = False
        self._task = None

        logger.info(f"ActiveTokenTracker initialized (reanalysis every {reanalysis_interval}s)")

    async def start(self):
        """Start the background reanalysis task."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._reanalysis_loop())
        logger.info("ActiveTokenTracker started")

    async def stop(self):
        """Stop the background task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("ActiveTokenTracker stopped")

    def start_tracking(
        self,
        token_address: str,
        symbol: str,
        name: str,
        wallet_address: str,
        wallet_tier: str,
        wallet_name: str,
        graduated: bool = False,
        initial_data: Optional[Dict] = None
    ) -> bool:
        """
        Start tracking a token (triggered by KOL/smart wallet buy).

        Returns:
            True if new tracking started, False if already tracking
        """
        if token_address in self.tracked_tokens:
            # Already tracking - increment KOL count
            state = self.tracked_tokens[token_address]
            if wallet_address not in state.kol_addresses:
                state.kol_buy_count += 1
                state.kol_addresses.add(wallet_address)
                logger.info(f"Another KOL bought ${state.symbol} (total: {state.kol_buy_count})")
            return False

        # Create new tracking state
        state = TokenState(
            token_address=token_address,
            symbol=symbol,
            name=name,
            wallet_address=wallet_address,
            wallet_tier=wallet_tier,
            wallet_name=wallet_name,
            graduated=graduated
        )
        state.kol_addresses.add(wallet_address)

        # Apply initial data if provided
        if initial_data:
            state.liquidity = initial_data.get('liquidity', 0)
            state.mcap = initial_data.get('mcap', 0)
            state.holders = initial_data.get('holders', 0)
            state.bonding_pct = initial_data.get('bonding_pct', 0)

        self.tracked_tokens[token_address] = state
        logger.info(f"Started tracking ${symbol} ({token_address[:8]}) - triggered by {wallet_name}")

        return True

    def update_from_websocket(
        self,
        token_address: str,
        tx_type: str,  # 'buy' or 'sell'
        trader: str,
        sol_amount: float = 0,
        bonding_pct: float = 0
    ):
        """
        Update token state from WebSocket trade event.
        Called by PumpPortal WebSocket handler.
        """
        if token_address not in self.tracked_tokens:
            return

        state = self.tracked_tokens[token_address]

        if tx_type == 'buy':
            state.buys += 1
            state.volume_sol += sol_amount
            state.unique_buyers.add(trader)
            if bonding_pct > state.bonding_pct:
                state.bonding_pct = bonding_pct
        elif tx_type == 'sell':
            state.sells += 1

    def get_token_state(self, token_address: str) -> Optional[TokenState]:
        """Get current state for a token."""
        return self.tracked_tokens.get(token_address)

    def mark_signaled(self, token_address: str):
        """Mark a token as having been signaled."""
        if token_address in self.tracked_tokens:
            self.tracked_tokens[token_address].signal_sent = True

    def get_pending_tokens(self) -> list:
        """Get tokens that haven't been signaled yet."""
        return [
            state for state in self.tracked_tokens.values()
            if not state.signal_sent
        ]

    def get_stats(self) -> Dict:
        """Get tracker statistics."""
        pending = len([s for s in self.tracked_tokens.values() if not s.signal_sent])
        signaled = len([s for s in self.tracked_tokens.values() if s.signal_sent])

        return {
            'total_tracked': len(self.tracked_tokens),
            'pending': pending,
            'signaled': signaled
        }

    async def _reanalysis_loop(self):
        """Background task that re-analyzes pending tokens."""
        while self._running:
            try:
                await asyncio.sleep(self.reanalysis_interval)

                # Get pending tokens
                pending = self.get_pending_tokens()
                if not pending:
                    continue

                logger.debug(f"Reanalyzing {len(pending)} pending tokens...")

                for state in pending:
                    try:
                        await self._reanalyze_token(state)
                    except Exception as e:
                        logger.error(f"Error reanalyzing ${state.symbol}: {e}")

                # Cleanup old tokens
                self._cleanup_old_tokens()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Reanalysis loop error: {e}")
                await asyncio.sleep(5)

    async def _reanalyze_token(self, state: TokenState):
        """Re-analyze a single token and check if it should signal."""
        # Cooldown: don't reanalyze too frequently
        now = datetime.utcnow()
        if state.last_analyzed:
            seconds_since = (now - state.last_analyzed).total_seconds()
            if seconds_since < 10:
                return

        state.last_analyzed = now

        # Calculate score with accumulated data
        from scoring import calculate_score_v2

        score, breakdown, should_signal, skip_reason = calculate_score_v2(
            wallet_tier=state.wallet_tier,
            liquidity=state.liquidity,
            mcap=state.mcap,
            holders=state.holders,
            graduated=state.graduated,
            buys=state.buys,
            sells=state.sells,
            unique_buyers=len(state.unique_buyers),
            kol_count=state.kol_buy_count,
            bonding_pct=state.bonding_pct,
            tracking_seconds=(now - state.first_seen).total_seconds()
        )

        state.last_score = score
        state.skip_reason = skip_reason

        # Log score changes
        if score != state.last_score or should_signal:
            logger.debug(f"${state.symbol}: score={score}, buys={state.buys}, unique={len(state.unique_buyers)}")

        # Check if should signal
        if should_signal and not state.signal_sent:
            logger.info(f"Signal threshold crossed for ${state.symbol}! Score: {score}")

            if self.on_signal:
                await self.on_signal(
                    token_address=state.token_address,
                    symbol=state.symbol,
                    name=state.name,
                    wallet_address=state.wallet_address,
                    wallet_tier=state.wallet_tier,
                    wallet_name=state.wallet_name,
                    score=score,
                    breakdown=breakdown,
                    state=state
                )

    def _cleanup_old_tokens(self):
        """Remove tokens that are too old."""
        cutoff = datetime.utcnow() - timedelta(minutes=self.max_age_minutes)

        to_remove = [
            addr for addr, state in self.tracked_tokens.items()
            if state.first_seen < cutoff and state.signal_sent
        ]

        # Also remove very old unsignaled tokens (2x max age)
        very_old_cutoff = datetime.utcnow() - timedelta(minutes=self.max_age_minutes * 2)
        to_remove.extend([
            addr for addr, state in self.tracked_tokens.items()
            if state.first_seen < very_old_cutoff and not state.signal_sent
            and addr not in to_remove
        ])

        for addr in to_remove:
            symbol = self.tracked_tokens[addr].symbol
            logger.debug(f"Removing ${symbol} from tracking (aged out)")
            del self.tracked_tokens[addr]
