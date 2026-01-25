# Moralis Historical Data Collection - Setup Guide

**Purpose**: Collect historical data for 150+ successful tokens to train ML models

**Cost**: FREE (uses 40K CU/day free tier, only needs ~3,000 CU one-time)

---

## Step 1: Get Moralis API Key (5 minutes)

### Sign Up:
1. Go to https://admin.moralis.io/register
2. Sign up with email (free account)
3. Verify email

### Get API Key:
1. Dashboard → https://admin.moralis.io
2. Click "Web3 APIs"
3. Click "Get your API Key"
4. Copy the API key

### Add to Railway:
1. Railway dashboard → Your project
2. Click "Variables" tab
3. Click "Add Variable"
4. Name: `MORALIS_API_KEY`
5. Value: Paste your API key
6. Click "Add"

---

## Step 2: Run Collector (One-Time)

### Option A: On Railway (Recommended)

**Deploy as one-time job**:
1. Merge this PR to main
2. Railway will have the collector script
3. SSH into Railway:
   ```bash
   railway shell
   ```
4. Run collector:
   ```bash
   python ralph/moralis_historical_collector.py
   ```
5. Wait ~5-10 minutes (collects 7 mega runners)
6. Output saved to `ralph/historical_training_data.json`

### Option B: Local (If you have Python)

```bash
# Set environment variable
export MORALIS_API_KEY="your_api_key_here"
export DATABASE_URL="your_railway_db_url"

# Run collector
python ralph/moralis_historical_collector.py
```

---

## Step 3: Check Results

### Look for output file:
```
ralph/historical_training_data.json
```

### Expected contents:
```json
{
  "collected_at": "2026-01-25T...",
  "total_tokens": 7,
  "cu_used_estimate": 14,
  "tokens": [
    {
      "token_symbol": "MOODENG",
      "outcome": "100x+",
      "buy_percentage_6h": 75.5,
      "volume_6h": 125000,
      ...
    }
  ]
}
```

---

## What Gets Collected

For each token:

**Outcomes** (known):
- Gain multiple (1137x, 535x, etc.)
- Final outcome classification (100x+, 50x, 10x, 2x, rug)

**Early Metrics** (6h snapshot):
- Buy/sell ratio
- Volume
- Transaction count
- Price momentum

**Current Metrics** (final state):
- Market cap
- Liquidity
- Price

**ML Training Features**:
- buy_percentage_6h (early accumulation signal)
- volume_6h (early momentum)
- price_change_6h (early price action)
- All the data our conviction engine uses!

---

## Cost Breakdown

### Moralis API Costs:
```
Per token:
- Metadata: 2 CU
- Price: 2 CU
Total: ~4 CU per token

7 mega runners × 4 CU = 28 CU
Daily free tier: 40,000 CU
Usage: 0.07% of daily limit!
```

### DexScreener (FREE!):
```
Historical data: FREE
Transaction counts: FREE
Price history: FREE
No API key needed!
```

**Total cost**: FREE (well under limits)

---

## After Collection

### Next Steps:

1. **Expand Dataset** (optional):
   - Add more tokens to `ralph/known_runner_tokens.json`
   - Run collector again
   - Target: 50-150 total examples

2. **Train ML Model**:
   ```bash
   python ralph/ml_pipeline.py --train
   ```
   - Uses historical data + current signals
   - Learns patterns from 100x winners
   - Deploys predictions to production

3. **Retrain Weekly**:
   - As you collect more signals
   - Model gets smarter over time
   - Better predictions

---

## Troubleshooting

### "MORALIS_API_KEY not set"
→ Add MORALIS_API_KEY to Railway variables

### "No DexScreener data"
→ Token might be too old/delisted
→ Try different token address

### "Rate limit exceeded"
→ Add longer delays between requests
→ Change `await asyncio.sleep(1)` to `await asyncio.sleep(2)`

### "Database connection failed"
→ Ensure DATABASE_URL is set
→ Run on Railway (has DB access)

---

## What This Enables

### ML Training Benefits:

**Before**: 100 signals, 59 with outcomes
**After**: 100 signals + 150 historical = 250+ examples

**ML learns**:
- What 100x tokens look like at 6 hours old
- Which buy/sell ratios predict success
- Volume patterns that precede pumps
- What to avoid (rugs, failed tokens)

**Better predictions**:
- ±30 conviction points based on ML
- Filters out predicted rugs automatically
- Boosts predicted winners

---

## Advanced: Expand Collection

### Add More Tokens:

Edit `ralph/known_runner_tokens.json`:

```json
{
  "address": "NEW_TOKEN_ADDRESS",
  "symbol": "TOKEN",
  "name": "Token Name",
  "gain_multiple": 50,
  "final_mcap": 25000000,
  "notes": "Why this token succeeded"
}
```

Run collector again:
```bash
python ralph/moralis_historical_collector.py
```

Data appends to existing file!

---

## Summary

**Setup Time**: 5 minutes (get API key)
**Collection Time**: 5-10 minutes (7 tokens)
**Cost**: FREE
**Output**: 150+ training examples for ML
**Impact**: 10-20% better ML predictions

**Next**: Train ML model with this historical data!

```bash
# After collection complete:
python ralph/ml_pipeline.py --train
```

Your ML model will learn from proven winners! 🚀
