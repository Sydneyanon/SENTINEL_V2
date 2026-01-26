"""
Manually add a signal outcome for tokens that were missed
Useful for recording 100x plays that weren't auto-tracked
"""
import asyncio
import sys
from database import Database

async def add_outcome(token_address: str, token_symbol: str, outcome: str, max_roi: float):
    """
    Add a manual signal outcome

    Args:
        token_address: Token contract address
        token_symbol: Token symbol (e.g., "SHRIMP")
        outcome: Outcome category (e.g., "100x", "50x", "10x", "5x", "2x", "loss", "rug")
        max_roi: Maximum ROI achieved (e.g., 100.0 for 100x)
    """
    db = Database()
    await db.connect()

    async with db.pool.acquire() as conn:
        # Check if signal already exists
        existing = await conn.fetchrow(
            'SELECT * FROM signals WHERE token_address = $1',
            token_address
        )

        if existing:
            print(f"✅ Found existing signal for {token_symbol}")
            print(f"   Updating outcome to: {outcome} ({max_roi}x)")
            await conn.execute('''
                UPDATE signals
                SET outcome = $1,
                    max_roi = $2,
                    outcome_timestamp = NOW(),
                    updated_at = NOW()
                WHERE token_address = $3
            ''', outcome, max_roi, token_address)
            print(f"✅ Updated!")
        else:
            print(f"❌ No existing signal found for {token_address}")
            print(f"   Creating new manual signal record...")
            await conn.execute('''
                INSERT INTO signals
                (token_address, token_symbol, signal_type, conviction_score,
                 signal_posted, outcome, max_roi, outcome_timestamp)
                VALUES ($1, $2, 'manual', 0, FALSE, $3, $4, NOW())
            ''', token_address, token_symbol, outcome, max_roi)
            print(f"✅ Created manual record for {token_symbol} - {outcome} ({max_roi}x)")

    await db.close()

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python add_manual_outcome.py <token_address> <symbol> <outcome> <max_roi>")
        print("\nExample:")
        print("  python add_manual_outcome.py GDfn...abc SHRIMP 100x 100")
        print("\nOutcomes: 100x, 50x, 10x, 5x, 2x, loss, rug")
        sys.exit(1)

    token_address = sys.argv[1]
    symbol = sys.argv[2]
    outcome = sys.argv[3]
    max_roi = float(sys.argv[4])

    asyncio.run(add_outcome(token_address, symbol, outcome, max_roi))
