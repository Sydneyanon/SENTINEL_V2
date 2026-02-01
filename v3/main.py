"""
SENTINEL V3 - Main Entry Point
FastAPI app with Helius webhook handler.
"""
import asyncio
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from loguru import logger

from config import HELIUS_API_KEY, LOG_LEVEL, ADMIN_USER_ID, SKIP_TOKENS
import database as db
from scoring import calculate_score, format_breakdown
from tracker import TokenTracker
from fetchers import fetch_token_data
from tg_poster import TelegramPoster
from admin import AdminBot
from pumpportal_ws import PumpPortalWS
from rugcheck import get_rugcheck, cleanup_rugcheck
from discovery import get_discovery
from active_tracker import ActiveTokenTracker


# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    level=LOG_LEVEL,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>"
)

# Global instances
telegram_poster = TelegramPoster()
token_tracker = TokenTracker(telegram_poster)
admin_bot = AdminBot()
pumpportal = None  # Initialized in lifespan
smart_money_discovery = None  # Initialized in lifespan
active_tracker = None  # V2-style continuous tracking


async def on_kol_buy(token_address: str, wallet_address: str, symbol: str,
                     unique_buyers: int, bonding_pct: float, volume_sol: float):
    """Callback when PumpPortal detects a KOL buy."""
    global active_tracker

    wallet = await db.get_wallet(wallet_address)
    if not wallet:
        return

    logger.info(f"PumpPortal: {wallet['name'] or wallet_address[:8]} bought ${symbol}")

    # Start V2-style tracking (continuous reanalysis)
    await start_tracking_token(token_address, wallet, symbol)


async def on_trade_event(token_address: str, tx_type: str, trader: str,
                         sol_amount: float, bonding_pct: float):
    """Callback when PumpPortal detects any trade on a tracked token."""
    global active_tracker

    if active_tracker:
        active_tracker.update_from_websocket(
            token_address=token_address,
            tx_type=tx_type,
            trader=trader,
            sol_amount=sol_amount,
            bonding_pct=bonding_pct
        )


async def on_signal_threshold_crossed(token_address: str, symbol: str, name: str,
                                       wallet_address: str, wallet_tier: str,
                                       wallet_name: str, score: int, breakdown: dict,
                                       state):
    """Callback when active tracker detects signal threshold crossed."""
    global active_tracker

    # Check if we already signaled this token
    existing = await db.get_signal_by_token(token_address)
    if existing and existing.get('posted_at'):
        logger.debug(f"Already signaled {token_address[:8]}")
        return

    # RugCheck - block high risk tokens
    rugcheck = get_rugcheck()
    rug_result = await rugcheck.check(token_address)
    if not rug_result.get('safe', True):
        logger.info(f"Skip ${symbol}: RugCheck - {rug_result.get('reason', 'High risk')}")
        return

    logger.info(f"SIGNAL ${symbol}! Score: {score}/100 | Buys: {state.buys} | Unique: {len(state.unique_buyers)}")

    # Fetch latest token data for signal
    data = await fetch_token_data(token_address)
    if not data:
        data = {'price': 0, 'mcap': state.mcap, 'liquidity': state.liquidity,
                'holders': state.holders, 'volume_1h': 0}

    # Create signal in database
    signal_id = await db.create_signal(
        token_address=token_address,
        symbol=symbol,
        name=name,
        wallet_address=wallet_address,
        wallet_tier=wallet_tier,
        entry_price=data.get('price', 0),
        entry_mcap=data.get('mcap', state.mcap),
        entry_liquidity=data.get('liquidity', state.liquidity),
        entry_holders=data.get('holders', state.holders),
        entry_volume_1h=data.get('volume_1h', 0),
        score=score,
        score_breakdown=breakdown
    )

    # Mark as signaled in active tracker
    if active_tracker:
        active_tracker.mark_signaled(token_address)

    # Get the full signal and post to Telegram
    signal = await db.get_signal(signal_id)
    message_id = await telegram_poster.post_signal(signal, breakdown)

    if message_id:
        await db.mark_signal_posted(signal_id, message_id)
        logger.info(f"Posted ${symbol} to Telegram (msg_id: {message_id})")
    else:
        logger.warning(f"Failed to post ${symbol} to Telegram, removing signal")
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute('DELETE FROM signals WHERE id = $1', signal_id)


async def start_tracking_token(token_address: str, wallet: dict, symbol: str = None):
    """Start V2-style continuous tracking for a token."""
    global active_tracker, pumpportal

    if not active_tracker:
        logger.warning("ActiveTracker not initialized")
        return

    # Skip if token already in SKIP_TOKENS
    if token_address in SKIP_TOKENS:
        return

    # Check if already signaled
    existing = await db.get_signal_by_token(token_address)
    if existing and existing.get('posted_at'):
        logger.debug(f"Already signaled {token_address[:8]}")
        return

    # Fetch token data
    data = await fetch_token_data(token_address)
    if not data:
        logger.debug(f"No data for {token_address[:8]}")
        return

    symbol = data.get('symbol', symbol or 'UNKNOWN')
    name = data.get('name', 'Unknown')
    graduated = data.get('graduated', True)

    # Get WebSocket stats if available
    ws_buys = 0
    ws_sells = 0
    if pumpportal:
        ws_stats = pumpportal.get_token_stats(token_address)
        if ws_stats:
            ws_buys = ws_stats.get('buys', 0)
            ws_sells = ws_stats.get('sells', 0)

    # Start tracking
    is_new = active_tracker.start_tracking(
        token_address=token_address,
        symbol=symbol,
        name=name,
        wallet_address=wallet['address'],
        wallet_tier=wallet['tier'],
        wallet_name=wallet.get('name') or wallet['address'][:8],
        graduated=graduated,
        initial_data={
            'liquidity': data.get('liquidity', 0),
            'mcap': data.get('mcap', 0),
            'holders': data.get('holders', 0),
            'bonding_pct': data.get('bonding_pct', 0),
        }
    )

    if is_new:
        # Initialize with WebSocket data
        state = active_tracker.get_token_state(token_address)
        if state:
            state.buys = ws_buys
            state.sells = ws_sells
            # Add triggering wallet as first unique buyer
            state.unique_buyers.add(wallet['address'])
            # Add any existing buyers from WebSocket
            if pumpportal:
                existing_buyers = pumpportal.token_buyers.get(token_address, set())
                state.unique_buyers.update(existing_buyers)

        # Register for WebSocket trade events
        if pumpportal:
            pumpportal.add_token_tracking(token_address)

        logger.info(f"Tracking ${symbol} (graduated={graduated}, liq=${data.get('liquidity', 0):,.0f})")


async def on_smart_money_added(wallet_addresses: list):
    """Callback when new smart money wallets are added to tracking."""
    global pumpportal
    if pumpportal:
        await pumpportal.update_wallets(wallet_addresses)


async def on_discovery_complete(result: dict):
    """Callback when smart money discovery completes - send Telegram notification."""
    if not result.get('success') or result.get('added_to_tracking', 0) == 0:
        return

    new_wallets = result.get('new_wallets', [])
    if not new_wallets:
        return

    # Build notification message
    lines = ["<b>🔍 Weekly Discovery Complete</b>\n"]
    lines.append(f"New wallets found: {result['discovered']}")
    lines.append(f"Auto-added to tracking: {result['added_to_tracking']}\n")

    lines.append("<b>New Smart Money:</b>")
    for w in new_wallets[:5]:  # Top 5
        lines.append(
            f"• <code>{w['address'][:8]}...</code> "
            f"({w['win_rate']:.0f}% WR, {w['total_trades']} trades)"
        )

    lines.append("\n<i>View full list: /smartmoney list</i>")

    # Send to admin via Telegram
    try:
        if admin_bot.app and admin_bot.running and ADMIN_USER_ID:
            await admin_bot.app.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text="\n".join(lines),
                parse_mode="HTML"
            )
            logger.info(f"Sent discovery notification to admin")
    except Exception as e:
        # Fall back to logging if Telegram fails
        logger.warning(f"Failed to send discovery notification: {e}")
        logger.info(f"Discovery complete: {result['message']}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown."""
    global pumpportal, smart_money_discovery, active_tracker

    # Startup
    logger.info("=" * 50)
    logger.info("SENTINEL V3 Starting...")
    logger.info("=" * 50)

    await db.init_db()
    await token_tracker.start()

    # Initialize V2-style active tracker (continuous reanalysis)
    active_tracker = ActiveTokenTracker(
        on_signal=on_signal_threshold_crossed,
        max_age_minutes=60,
        reanalysis_interval=30
    )
    await active_tracker.start()

    # Delay to avoid Telegram bot conflicts during Railway redeployments
    # Old container may still be running for a few seconds
    logger.info("Waiting for previous instance to shut down...")
    await asyncio.sleep(10)
    await admin_bot.start()

    # Get tracked wallets and start PumpPortal WebSocket
    wallets = await db.get_all_wallets()
    wallet_addresses = [w['address'] for w in wallets]

    pumpportal = PumpPortalWS(on_kol_buy=on_kol_buy, on_trade=on_trade_event)
    await pumpportal.start(tracked_wallets=wallet_addresses)

    # Start smart money discovery scheduler
    smart_money_discovery = get_discovery()
    smart_money_discovery.on_wallets_added = on_smart_money_added
    smart_money_discovery.on_discovery_complete = on_discovery_complete
    await smart_money_discovery.start()

    logger.info(f"Tracking {len(wallets)} wallets")

    stats = await db.get_stats()
    logger.info(f"Total signals: {stats['total_signals']} | Win rate: {stats['win_rate']:.1f}%")

    sm_stats = await db.get_smart_money_stats()
    if sm_stats['total_discovered'] > 0:
        logger.info(f"Smart Money: {sm_stats['total_discovered']} discovered, {sm_stats['tracking']} tracking")

    logger.info("Ready! (Helius webhooks + PumpPortal WebSocket + Smart Money Discovery)")

    yield

    # Shutdown
    logger.info("Shutting down...")
    if smart_money_discovery:
        await smart_money_discovery.stop()
    if active_tracker:
        await active_tracker.stop()
    if pumpportal:
        await pumpportal.stop()
    await token_tracker.stop()
    await admin_bot.stop()
    await cleanup_rugcheck()


app = FastAPI(title="SENTINEL V3", lifespan=lifespan)


@app.get("/")
async def health():
    """Health check."""
    stats = await db.get_stats()
    return {
        "status": "ok",
        "version": "3.0",
        "signals": stats['total_signals'],
        "win_rate": f"{stats['win_rate']:.1f}%"
    }


@app.post("/webhook/wallet")
async def handle_wallet_webhook(request: Request):
    """
    Handle Helius webhook for tracked wallet transactions.
    This is called when any tracked wallet makes a transaction.
    """
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")

    # Helius sends an array of transactions
    transactions = data if isinstance(data, list) else [data]

    for tx in transactions:
        try:
            await process_wallet_transaction(tx)
        except Exception as e:
            logger.error(f"Error processing transaction: {e}")

    return {"status": "ok", "processed": len(transactions)}


async def process_wallet_transaction(tx: dict):
    """Process a single wallet transaction from Helius webhook."""

    # Extract wallet address (fee payer is usually the signer)
    fee_payer = tx.get('feePayer')
    if not fee_payer:
        return

    # Check if this wallet is tracked
    wallet = await db.get_wallet(fee_payer)
    if not wallet:
        return

    # Look for token transfers (pump.fun buys)
    token_transfers = tx.get('tokenTransfers', [])
    if not token_transfers:
        return

    # Debug: log all token transfers
    wallet_name = wallet.get('name') or fee_payer[:8]
    logger.debug(f"Tx from {wallet_name}: {len(token_transfers)} token transfers")

    # Find the token being bought (received by wallet)
    # Skip stablecoins and major tokens
    for transfer in token_transfers:
        if transfer.get('toUserAccount') == fee_payer:
            token_address = transfer.get('mint')
            if not token_address:
                continue

            # Skip known stablecoins/major tokens
            if token_address in SKIP_TOKENS:
                logger.debug(f"Skip stablecoin/major token: {token_address[:8]}")
                continue

            # Found a potential meme token buy - start V2-style tracking
            await start_tracking_token(token_address, wallet)
            return  # Process first non-stablecoin token only


async def process_potential_signal(token_address: str, wallet: dict):
    """Process a potential signal from a wallet buy."""
    global pumpportal

    # Check if we already have a recent signal for this token
    existing = await db.get_signal_by_token(token_address)
    if existing and existing.get('posted_at'):
        logger.debug(f"Already signaled {token_address[:8]}")
        return

    # Fetch token data from DexScreener/PumpPortal
    data = await fetch_token_data(token_address)
    if not data:
        logger.debug(f"No data for {token_address[:8]}")
        return

    symbol = data.get('symbol', 'UNKNOWN')
    name = data.get('name', 'Unknown')
    graduated = data.get('graduated', True)

    logger.info(f"Wallet {wallet['name'] or wallet['address'][:8]} bought ${symbol}")

    # Get real-time buy/sell data from WebSocket (much better than REST API zeros)
    buys = data.get('buys_1h', 0)
    sells = data.get('sells_1h', 0)

    if pumpportal and not graduated:
        ws_stats = pumpportal.get_token_stats(token_address)
        if ws_stats:
            buys = ws_stats.get('buys', buys)
            sells = ws_stats.get('sells', sells)
            logger.debug(f"WebSocket data for ${symbol}: {buys} buys, {sells} sells")

    # Calculate score
    score, breakdown, should_signal, skip_reason = calculate_score(
        wallet_tier=wallet['tier'],
        volume_1h=data.get('volume_1h', 0),
        liquidity=data.get('liquidity', 0),
        price_change_1h=data.get('price_change_1h', 0),
        holders=data.get('holders', 0),
        mcap=data.get('mcap', 0),
        buys_1h=buys,
        sells_1h=sells,
        graduated=graduated
    )

    if not should_signal:
        logger.info(f"Skip ${symbol}: {skip_reason}")
        return

    # RugCheck - block high risk tokens
    rugcheck = get_rugcheck()
    rug_result = await rugcheck.check(token_address)
    if not rug_result.get('safe', True):
        logger.info(f"Skip ${symbol}: RugCheck - {rug_result.get('reason', 'High risk')}")
        return

    logger.info(f"Signal ${symbol}! Score: {score}/100 | Risk: {rug_result.get('risk_level', '?')}")
    logger.debug(f"\n{format_breakdown(breakdown)}")

    # Create signal in database
    signal_id = await db.create_signal(
        token_address=token_address,
        symbol=symbol,
        name=name,
        wallet_address=wallet['address'],
        wallet_tier=wallet['tier'],
        entry_price=data.get('price', 0),
        entry_mcap=data.get('mcap', 0),
        entry_liquidity=data.get('liquidity', 0),
        entry_holders=data.get('holders', 0),
        entry_volume_1h=data.get('volume_1h', 0),
        score=score,
        score_breakdown=breakdown
    )

    # Get the full signal
    signal = await db.get_signal(signal_id)

    # Post to Telegram
    message_id = await telegram_poster.post_signal(signal, breakdown)

    if message_id:
        await db.mark_signal_posted(signal_id, message_id)
        logger.info(f"Posted ${symbol} to Telegram (msg_id: {message_id})")
    else:
        # Failed to post - delete the orphaned signal
        logger.warning(f"Failed to post ${symbol} to Telegram, removing signal")
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute('DELETE FROM signals WHERE id = $1', signal_id)


@app.post("/webhook/test")
async def test_webhook(request: Request):
    """Test endpoint to simulate a signal."""
    try:
        data = await request.json()
        token_address = data.get('token_address')

        if not token_address:
            raise HTTPException(400, "token_address required")

        # Get a wallet to use as source
        wallets = await db.get_all_wallets()
        if not wallets:
            raise HTTPException(400, "No wallets configured")

        wallet = wallets[0]
        await process_potential_signal(token_address, wallet)

        return {"status": "ok", "token": token_address}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
