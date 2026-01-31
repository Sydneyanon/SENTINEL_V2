"""
SENTINEL V3 - Main Entry Point
FastAPI app with Helius webhook handler.
"""
import asyncio
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from loguru import logger

from config import HELIUS_API_KEY, LOG_LEVEL
import database as db
from scoring import calculate_score, format_breakdown
from tracker import TokenTracker, fetch_token_data
from telegram import TelegramPoster
from admin import AdminBot


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown."""
    # Startup
    logger.info("=" * 50)
    logger.info("SENTINEL V3 Starting...")
    logger.info("=" * 50)

    await db.init_db()
    await token_tracker.start()
    await admin_bot.start()

    wallets = await db.get_all_wallets()
    logger.info(f"Tracking {len(wallets)} wallets")

    stats = await db.get_stats()
    logger.info(f"Total signals: {stats['total_signals']} | Win rate: {stats['win_rate']:.1f}%")

    logger.info("Ready to receive webhooks")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await token_tracker.stop()
    await admin_bot.stop()


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

    # Find the token being bought (received by wallet)
    for transfer in token_transfers:
        if transfer.get('toUserAccount') == fee_payer:
            token_address = transfer.get('mint')
            if token_address:
                await process_potential_signal(token_address, wallet)
                break


async def process_potential_signal(token_address: str, wallet: dict):
    """Process a potential signal from a wallet buy."""

    # Check if we already have a recent signal for this token
    existing = await db.get_signal_by_token(token_address)
    if existing and existing.get('posted_at'):
        logger.debug(f"Already signaled {token_address[:8]}")
        return

    # Fetch token data from DexScreener
    data = await fetch_token_data(token_address)
    if not data:
        logger.debug(f"No DexScreener data for {token_address[:8]}")
        return

    symbol = data.get('symbol', 'UNKNOWN')
    name = data.get('name', 'Unknown')

    logger.info(f"Wallet {wallet['name'] or wallet['address'][:8]} bought ${symbol}")

    # Calculate score
    score, breakdown, should_signal, skip_reason = calculate_score(
        wallet_tier=wallet['tier'],
        volume_1h=data.get('volume_1h', 0),
        liquidity=data.get('liquidity', 0),
        price_change_1h=data.get('price_change_1h', 0),
        holders=data.get('holders', 0),
        mcap=data.get('mcap', 0)
    )

    if not should_signal:
        logger.info(f"Skip ${symbol}: {skip_reason}")
        return

    logger.info(f"Signal ${symbol}! Score: {score}/100")
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
    uvicorn.run(app, host="0.0.0.0", port=8080)
