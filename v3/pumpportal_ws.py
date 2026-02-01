"""
SENTINEL V3 - PumpPortal WebSocket
Real-time feed for pre-graduation tokens.
"""
import asyncio
import json
import websockets
from loguru import logger
from typing import Optional, Callable, Dict, Set
from datetime import datetime, timedelta


class PumpPortalWS:
    """
    PumpPortal WebSocket client for real-time pump.fun data.

    Provides:
    - New token creation events
    - Trade events (buys/sells)
    - Unique buyer tracking
    - Bonding curve progress
    """

    WS_URL = "wss://pumpportal.fun/api/data"

    def __init__(self, on_kol_buy: Optional[Callable] = None, on_trade: Optional[Callable] = None):
        self.ws = None
        self.running = False
        self._task = None
        self.on_kol_buy = on_kol_buy  # Callback when tracked wallet buys
        self.on_trade = on_trade  # Callback for ALL trades on tracked tokens

        # Track tokens we're watching
        self.watched_tokens: Dict[str, dict] = {}  # token_address -> data
        self.tracked_wallets: Set[str] = set()  # Wallet addresses to watch
        self.actively_tracking: Set[str] = set()  # Tokens being actively tracked

        # Buyer tracking per token
        self.token_buyers: Dict[str, Set[str]] = {}  # token -> set of buyer addresses

    async def start(self, tracked_wallets: list = None):
        """Start the WebSocket connection."""
        if self.running:
            return

        if tracked_wallets:
            self.tracked_wallets = set(tracked_wallets)

        self.running = True
        self._task = asyncio.create_task(self._connection_loop())
        logger.info(f"PumpPortal WS started (tracking {len(self.tracked_wallets)} wallets)")

    async def stop(self):
        """Stop the WebSocket connection."""
        self.running = False
        if self.ws:
            await self.ws.close()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("PumpPortal WS stopped")

    def add_wallet(self, address: str):
        """Add a wallet to track."""
        self.tracked_wallets.add(address)

    def remove_wallet(self, address: str):
        """Remove a wallet from tracking."""
        self.tracked_wallets.discard(address)

    def add_token_tracking(self, token_address: str):
        """Mark a token for active tracking (will receive trade events)."""
        self.actively_tracking.add(token_address)

    def remove_token_tracking(self, token_address: str):
        """Stop tracking a token."""
        self.actively_tracking.discard(token_address)

    async def update_wallets(self, addresses: list):
        """Update the tracked wallets list."""
        old_count = len(self.tracked_wallets)
        self.tracked_wallets = set(addresses)
        new_count = len(self.tracked_wallets)
        if new_count != old_count:
            logger.info(f"PumpPortal wallets updated: {old_count} -> {new_count}")

    async def _connection_loop(self):
        """Main connection loop with auto-reconnect."""
        while self.running:
            try:
                await self._connect_and_listen()
            except websockets.exceptions.ConnectionClosed:
                logger.warning("PumpPortal WS disconnected, reconnecting in 5s...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"PumpPortal WS error: {e}, reconnecting in 10s...")
                await asyncio.sleep(10)

    async def _connect_and_listen(self):
        """Connect and listen for messages."""
        async with websockets.connect(self.WS_URL) as ws:
            self.ws = ws
            logger.info("PumpPortal WS connected")

            # Subscribe to trade events
            await ws.send(json.dumps({
                "method": "subscribeTokenTrade",
                "keys": []  # Empty = all tokens
            }))

            # Subscribe to new token events
            await ws.send(json.dumps({
                "method": "subscribeNewToken"
            }))

            logger.info("Subscribed to PumpPortal feeds")

            async for message in ws:
                if not self.running:
                    break

                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    logger.error(f"Error handling message: {e}")

    async def _handle_message(self, data: dict):
        """Handle incoming WebSocket message."""

        # New token creation
        if data.get('txType') == 'create':
            await self._handle_new_token(data)

        # Trade event (buy/sell)
        elif data.get('txType') in ('buy', 'sell'):
            await self._handle_trade(data)

    async def _handle_new_token(self, data: dict):
        """Handle new token creation event."""
        token_address = data.get('mint')
        if not token_address:
            return

        symbol = data.get('symbol', 'UNKNOWN')
        name = data.get('name', 'Unknown')

        # Initialize tracking for this token
        self.token_buyers[token_address] = set()
        self.watched_tokens[token_address] = {
            'symbol': symbol,
            'name': name,
            'created_at': datetime.utcnow(),
            'buys': 0,
            'sells': 0,
            'volume_sol': 0,
            'bonding_pct': 0,
        }

        logger.debug(f"New token: ${symbol} ({token_address[:8]})")

    async def _handle_trade(self, data: dict):
        """Handle trade event (buy or sell)."""
        token_address = data.get('mint')
        trader = data.get('traderPublicKey')
        tx_type = data.get('txType')  # 'buy' or 'sell'
        sol_amount = float(data.get('solAmount', 0) or 0) / 1e9  # Convert lamports to SOL

        if not token_address or not trader:
            return

        # Initialize if we haven't seen this token
        if token_address not in self.token_buyers:
            self.token_buyers[token_address] = set()
            self.watched_tokens[token_address] = {
                'symbol': data.get('symbol', 'UNKNOWN'),
                'name': data.get('name', 'Unknown'),
                'created_at': datetime.utcnow(),
                'buys': 0,
                'sells': 0,
                'volume_sol': 0,
                'bonding_pct': 0,
            }

        # Track the trade
        token_data = self.watched_tokens[token_address]
        bonding_pct = token_data['bonding_pct']

        if tx_type == 'buy':
            token_data['buys'] += 1
            token_data['volume_sol'] += sol_amount
            self.token_buyers[token_address].add(trader)

            # Update bonding curve percentage if provided
            if 'vSolInBondingCurve' in data:
                v_sol = float(data.get('vSolInBondingCurve', 0) or 0) / 1e9
                # Bonding curve: starts at ~30 SOL, graduates at ~85 SOL
                bonding_pct = max(0, min(100, ((v_sol - 30) / 55) * 100))
                token_data['bonding_pct'] = bonding_pct

            # Check if this is a tracked wallet (KOL)
            if trader in self.tracked_wallets:
                symbol = token_data['symbol']
                unique_buyers = len(self.token_buyers[token_address])

                logger.info(f"KOL BUY: {trader[:8]} bought ${symbol} ({unique_buyers} buyers)")

                # Trigger callback
                if self.on_kol_buy:
                    await self.on_kol_buy(
                        token_address=token_address,
                        wallet_address=trader,
                        symbol=symbol,
                        unique_buyers=unique_buyers,
                        bonding_pct=bonding_pct,
                        volume_sol=token_data['volume_sol'],
                    )

        elif tx_type == 'sell':
            token_data['sells'] += 1

        # Send trade event to active tracker for actively tracked tokens
        if self.on_trade and token_address in self.actively_tracking:
            await self.on_trade(
                token_address=token_address,
                tx_type=tx_type,
                trader=trader,
                sol_amount=sol_amount,
                bonding_pct=bonding_pct
            )

    def get_token_stats(self, token_address: str) -> Optional[dict]:
        """Get current stats for a token."""
        if token_address not in self.watched_tokens:
            return None

        data = self.watched_tokens[token_address]
        return {
            **data,
            'unique_buyers': len(self.token_buyers.get(token_address, set())),
            'buy_sell_ratio': data['buys'] / max(1, data['sells']),
        }

    def cleanup_old_tokens(self, max_age_minutes: int = 30):
        """Remove tokens older than max_age_minutes."""
        cutoff = datetime.utcnow() - timedelta(minutes=max_age_minutes)

        to_remove = [
            addr for addr, data in self.watched_tokens.items()
            if data.get('created_at', datetime.utcnow()) < cutoff
        ]

        for addr in to_remove:
            del self.watched_tokens[addr]
            self.token_buyers.pop(addr, None)

        if to_remove:
            logger.debug(f"Cleaned up {len(to_remove)} old tokens")
