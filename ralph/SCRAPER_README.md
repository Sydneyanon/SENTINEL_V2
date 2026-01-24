# External Data Scraper for Ralph

This scraper solves a critical problem: **We can't learn from our own signals if we're not posting any!**

## The Problem

- Conviction threshold = 75
- Current tokens scoring 25-35
- **ZERO signals posted** = ZERO data to analyze
- Can't learn what patterns actually work

## The Solution

Scrape external data from the ENTIRE Solana/pump.fun ecosystem:

1. **DexScreener API (FREE)** - Find all tokens that went 200%+, 500%+, 10x+
2. **Check KOL involvement** - Which of our tracked KOLs bought them?
3. **Discover NEW KOLs** - Which wallets bought 2+ winners?
4. **Learn patterns** - What actually predicts success?

## How to Run

### From Railway (Recommended)

```bash
# SSH into Railway or run as one-off command
python ralph/scrape_external_data.py
```

### From Local/Codespaces

```bash
# Make sure you have the required env vars
export HELIUS_API_KEY="your_key_here"

# Run the scraper
python ralph/scrape_external_data.py
```

## Output

Creates `ralph/external_data.json` with:

```json
{
  "scraped_at": "2026-01-24T...",
  "token_count": 45,
  "discovered_kols_count": 12,
  "tokens": [
    {
      "address": "...",
      "symbol": "CATCOIN",
      "price_change_24h": 850.5,
      "our_kol_count": 2,
      "our_kols_involved": ["wallet1...", "wallet2..."],
      "new_wallet_count": 15,
      "new_wallets": ["unknown_wallet1...", ...],
      "outcome": "10x"
    }
  ],
  "discovered_kols": {
    "GDfn...": {
      "winner_count": 5,
      "avg_gain": 450.2,
      "max_gain": 1200.0,
      "tokens": ["CATCOIN", "DOGGO", ...]
    }
  }
}
```

## What Ralph Can Learn

### 1. Validate Current KOLs
- "Which of our KOLs actually bought winners?"
- "Should we demote/remove underperformers?"

### 2. Discover New KOLs
- "Wallet XYZ bought 5 tokens that went 10x+"
- "Add them to curated_wallets.py!"

### 3. Find Patterns
- "Tokens with 3+ KOLs have 78% win rate"
- "AI narrative + 2 elite KOLs = 65% 10x rate"
- "Cat narrative has 42% win rate (avoid)"

### 4. Update Scoring
Based on real data:
- Increase weight for proven patterns
- Decrease weight for underperforming criteria
- Add new KOLs that consistently win

## Credit Usage

- **DexScreener**: FREE (no API key needed)
- **Helius** (checking KOL involvement): ~1-2 credits per token
- **Total for 100 tokens**: ~200 credits (one-time cost)

**ROI**: Massive! Learn from 100+ real outcomes for <1% of your credit budget.

## Next Steps After Running

1. Ralph analyzes `external_data.json`
2. Identifies winning patterns
3. Updates conviction_engine.py weights
4. Adds discovered KOLs to curated_wallets.py
5. Tests new scoring on next batch of signals

## Why This Works

Instead of waiting days for OUR signals (getting none at 75 threshold), we:
- Analyze the ENTIRE ecosystem immediately
- Learn from 100+ successful tokens
- Discover what ACTUALLY works
- Apply learnings to fix our conviction scoring

**Result**: Tomorrow Ralph can optimize based on REAL DATA, not guesses.
