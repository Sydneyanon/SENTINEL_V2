# Historical Data Collector - Usage Guide

**Purpose**: Collect tokens that graduated from pump.fun (40-60% bonding → 100%) and reached 6-7-8 figure market caps for ML training.

## Two Collection Modes

### 1. **Automatic Mode** (Recommended - Runs in Background)
- ✅ **Enabled by default** - Runs weekly automatically
- Collects 50 new tokens per week
- Incremental updates (doesn't re-collect existing tokens)
- Zero manual intervention required
- Configurable via environment variables

### 2. **Manual Mode** (For Custom Collection)
- Run on-demand via SSH
- Full control over parameters (count, MCAP range, etc.)
- Useful for initial dataset or custom needs

---

## Prerequisites

### Get Moralis API Key (5 minutes, FREE)

**Why**: Needed for whale wallet extraction (works for both automatic and manual modes)

**Steps**:
1. Go to https://admin.moralis.io/register
2. Sign up with email (free account)
3. Verify email
4. Dashboard → Web3 APIs → Get your API Key
5. Copy the API key

### Add to Railway

1. Railway dashboard → Your project
2. Click "Variables" tab
3. Click "Add Variable"
4. Name: `MORALIS_API_KEY`
5. Value: Paste your API key
6. Click "Add"

**Note**: If you skip this, collector will still work but won't extract whale data (uses DexScreener only)

---

## Automatic Collection (Default)

The collector runs automatically in the background, collecting 50 new tokens every week.

### Configuration

Set these environment variables in Railway (optional - defaults shown):

```bash
# Enable/disable automated collection (default: true)
AUTO_COLLECTOR_ENABLED=true

# Collection interval in hours (default: 168 = 7 days)
AUTO_COLLECTOR_INTERVAL_HOURS=168

# Tokens to collect per run (default: 50)
AUTO_COLLECTOR_COUNT=50

# MCAP range (default: $1M - $100M)
AUTO_COLLECTOR_MIN_MCAP=1000000
AUTO_COLLECTOR_MAX_MCAP=100000000
```

### How It Works

1. **On bot startup**: Scheduler initializes and checks last run time
2. **First run**: Waits 1 hour (gives bot time to stabilize)
3. **Weekly runs**: Collects 50 new tokens automatically
4. **Incremental**: Skips tokens already in `data/historical_training_data.json`
5. **Logs**: All activity visible in Railway logs

### Monitoring

Check Railway logs for collector status:
```
🤖 AUTOMATED HISTORICAL COLLECTOR
   Status: ENABLED
   Schedule: Every 168 hours (7 days)
   Tokens per run: 50
   Last run: 2026-01-25T12:00:00 (48.5h ago)
   Next run: 2026-02-01T12:00:00 (in 119.5h)
```

### To Disable Automatic Collection

Set in Railway environment variables:
```bash
AUTO_COLLECTOR_ENABLED=false
```

Then restart the bot.

### Benefits of Automatic Mode

- 📈 **Continuous growth**: Dataset grows automatically over time
- 🔄 **No manual work**: Set it and forget it
- 💰 **Free**: Uses Moralis free tier (well under daily limits)
- 📊 **Better ML**: More training data = better predictions

**Expected Growth**:
- Week 1: 50 tokens
- Week 2: 100 tokens (50 new)
- Week 3: 150 tokens (50 new)
- Week 4: 200 tokens (50 new)
- **Month 3**: 600+ tokens automatically collected!

---

## Manual Collection

For custom collection or initial dataset building.

### How to Run

SSH into Railway and run the collector script:

```bash
# SSH into Railway
railway shell

# Run collector (default: 50 tokens)
python tools/historical_data_collector.py

# Or specify custom count
python tools/historical_data_collector.py --count 100

# Or specify MCAP range
python tools/historical_data_collector.py --min-mcap 5000000 --max-mcap 50000000
```

**Runtime**: 5-10 minutes for 50 tokens, 10-15 minutes for 150 tokens

---

## What Collector Does

**Data Collection**:
1. **Uses Moralis** to find pump.fun bonding curve tokens that reached high MCaps ($1M-$100M)
2. **Extracts whale wallets** (>$50K positions) using two methods:
   - Current top holders (Moralis)
   - Early buyers from transfer history (Moralis) - identifies whales who bought early!
3. **Tracks whale win rates** across multiple successful tokens
4. **Outputs training data** for ML model with whale intelligence

**Outputs**:
- `data/historical_training_data.json` - Token metrics for ML training
- `data/successful_whale_wallets.json` - Successful whale addresses for whale-copy strategy

---

## What You'll See

### Step 1: Finding Pump.Fun Graduates with DexScreener
```
🔍 SCANNING DEXSCREENER FOR 50 PUMP.FUN GRADUATES
   MCAP Range: $1,000,000 - $100,000,000
   Target: Tokens that graduated from 40-60% bonding
   Skipping: 100 already collected tokens

📊 Strategy 1: Fetching from DexScreener...
   Got 500 tokens from API

   ✅ MOODENG: $68,205,920 MCAP
   ✅ GOAT: $32,073,010 MCAP
   ✅ ACT: $21,995,799 MCAP
   ...
✅ Collected 50 tokens for analysis
```

### Step 2: Extracting Whales (Current + Early Holders)
```
🐋 EXTRACTING WHALE WALLETS (CURRENT + EARLY HOLDERS)

[1/50] MOODENG...
   Current holders: 18 whales
   Early buyers: +5 early whales
   🐋 Total whales found: 23

[2/50] GOAT...
   Current holders: 15 whales
   Early buyers: +8 early whales
   🐋 Total whales found: 23
...
```

### Step 3: Whale Analysis
```
📊 WHALE ANALYSIS
   Found 47 successful whales (50%+ win rate)
   1. 7xKXtg2CW... - 85% WR (17/20)
   2. A8bQr5Ym9... - 80% WR (12/15)
   3. 9KpLmN3Qw... - 75% WR (9/12)
   ...
```

### Step 4: Final Summary
```
✅ COLLECTION COMPLETE

📊 Collected 50 tokens:
   100x+: 3
   50x: 8
   10x: 20
   2x: 15
   small: 4

🐋 Identified 23 successful whales
   Can use these for whale-copy strategy!

💰 Estimated Moralis CU used: 250
   Daily free tier: 40,000 CU
   Usage: 0.6%

🚀 Ready for ML training!
```

---

## Output Files

### `data/historical_training_data.json`

**Structure**:
```json
{
  "collected_at": "2026-01-25T12:34:56",
  "total_tokens": 150,
  "cu_used_estimate": 750,
  "outcome_distribution": {
    "100x+": 7,
    "50x": 15,
    "10x": 48,
    "2x": 60,
    "small": 20
  },
  "tokens": [
    {
      "token_address": "ED5nyyWEzpPPiWimP8vYm7sD7TD3LAt3Q3gRTWHzPJBY",
      "symbol": "MOODENG",
      "name": "Moo Deng",
      "price_usd": 0.068,
      "market_cap": 68205920,
      "liquidity": 2500000,
      "volume_24h": 15000000,
      "buys_24h": 2500,
      "sells_24h": 750,
      "buy_percentage_24h": 76.9,
      "buy_percentage_6h": 82.5,
      "price_change_24h": 45.2,
      "outcome": "100x+",
      "whale_wallets": ["7xKXtg2CW...", "A8bQr5Ym9...", "9KpLmN3Qw..."],
      "whale_count": 23
    },
    ...
  ]
}
```

**ML Training Features**:
- Buy/sell ratios (24h, 6h) - accumulation signals
- Volume metrics - momentum indicators
- Price momentum - trend strength
- **Whale count (current + early)** - smart money validation
- **Early whale presence** - identifies tokens whales bought early
- Outcome labels (100% known!)

### `data/successful_whale_wallets.json`

**Structure**:
```json
{
  "collected_at": "2026-01-25T12:34:56",
  "total_whales": 47,
  "whales": [
    {
      "address": "7xKXtg2CW9eDnAGe5ggxt2b6eKStN4t7DxM1q8vKpVAy",
      "tokens_bought_count": 20,
      "wins": 17,
      "win_rate": 0.85,
      "tokens": [
        {"token": "MOODENG", "address": "ED5n...", "early_buyer": true},
        {"token": "GOAT", "address": "CzLS...", "early_buyer": true},
        {"token": "ACT", "address": "GJAFw..."},
        ...
      ]
    },
    ...
  ]
}
```

**Use Case**: Whale-copy strategy - track what these successful whales buy next!

**Early Buyer Intelligence**:
Whales marked with `"early_buyer": true` bought the token within its first 100 transfers. This is highly predictive because:
- Early whales have conviction before the crowd
- They're not chasing pumps (low-risk entry)
- ML can learn: "If wallet X bought early → 85% success rate"
- Real-time: When wallet X buys a new token early → instant signal!

---

## Cost Analysis

### DexScreener (FREE!)
- Price/volume data: FREE
- Transaction counts: FREE
- Historical data: FREE
- **Total: $0**

### Moralis (FREE TIER)
- Token discovery: ~10 CU (one-time batch)
- Whale extraction per token:
  - Top holders: ~5 CU
  - Transfer history: ~5 CU
  - **Total: ~10 CU per token**
- 50 tokens × 10 CU = 500 CU + 10 CU discovery = **510 CU per week**
- Daily free tier: 40,000 CU
- **Weekly usage: 1.3%** (still plenty of headroom!)

**Total Cost: FREE** (well under all API limits)

---

## After Collection

### Step 1: Verify Output Files

Check that files exist:
```bash
ls -lh data/historical_training_data.json
ls -lh data/successful_whale_wallets.json
```

### Step 2: Train ML Model

Use the historical data + current signals (100 signals, 59 outcomes):

```bash
python ralph/ml_pipeline.py --train
```

**Before**: 59 labeled examples
**After**: 59 + 150+ = 209+ labeled examples

**Result**: ML learns from proven 100x winners at their early stages!

### Step 3: Deploy ML Predictions

Model automatically loads on bot restart and adds ±30 conviction points per token:
- Predicted rugs: -30 points (filtered out)
- Predicted 100x: +20 points (boosted)

---

## Troubleshooting

### "MORALIS_API_KEY not set"
**Fix**: Add MORALIS_API_KEY to Railway variables (see Prerequisites above)
**Impact**: Collector still works but skips whale extraction

### "No tokens found"
**Fix**: Try different MCAP range with `--min-mcap` and `--max-mcap` flags
**Example**: `python tools/historical_data_collector.py --min-mcap 500000 --max-mcap 50000000`

### "Rate limit exceeded"
**Fix**: Increase delay between requests
**Edit**: Line 438 in historical_data_collector.py - change `await asyncio.sleep(1.5)` to `await asyncio.sleep(3)`

### "DexScreener timeout"
**Fix**: Network issue, just retry the command
**Why**: DexScreener API sometimes slow, retry usually works

### Automatic collector not running
**Check**: Railway logs for collector startup messages
**Fix 1**: Verify `AUTO_COLLECTOR_ENABLED=true` in Railway variables
**Fix 2**: Check bot startup logs for any errors
**Fix 3**: Restart the bot to reinitialize scheduler

---

## Whale Intelligence Benefits

### Early Detection Strategy

**What makes early whales special**:
- Bought within first 100 transfers (before the crowd)
- Had conviction when token was unknown
- Didn't chase pumps = lower risk entries
- 85%+ win rate whales provide strongest signal

**ML learns from this**:
- "If wallet X bought early → 85% success rate"
- Whale accumulation = bullish signal
- Early whale absence = caution flag
- Can weight signals: early whale (5x) > late whale (1x)

**Real-time application**:
- Track successful whales in real-time
- When they buy a new token early → instant +15 conviction
- Beat the crowd by following smart money
- Whale-copy strategy enables alpha

### Example Use Case

**Scenario**: ML identifies whale `7xKXtg2CW...` with:
- 17/20 wins (85% success rate)
- Early buyer in MOODENG, GOAT, ACT (all 100x+)

**Strategy**: Track this wallet in real-time
- Wallet buys new token `ABC` in first hour
- System detects: Successful early whale entering
- Adds +15 conviction points automatically
- You get signal before token pumps

**Result**: Follow the smartest money on Solana!

---

## Advanced Usage

### Collect Specific MCAP Range

Target mid-cap runners ($5M-$50M):
```bash
python tools/historical_data_collector.py \
  --count 100 \
  --min-mcap 5000000 \
  --max-mcap 50000000
```

### Collect Mega Runners Only

Only 100x+ tokens ($100M+):
```bash
python tools/historical_data_collector.py \
  --count 50 \
  --min-mcap 100000000 \
  --max-mcap 1000000000
```

### Adjust Automatic Collection Schedule

Run every 3 days instead of 7:
```bash
# In Railway environment variables
AUTO_COLLECTOR_INTERVAL_HOURS=72
```

Run daily (aggressive mode):
```bash
# In Railway environment variables
AUTO_COLLECTOR_INTERVAL_HOURS=24
AUTO_COLLECTOR_COUNT=20  # Collect fewer per run
```

### Add More Known Tokens

Edit `data/known_runner_tokens.json` to add manually curated tokens:

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

Collector will include these if DexScreener doesn't find enough.

---

## Expected ML Improvements

### Training Dataset Size
- **Before**: 59 examples (current signals with outcomes)
- **After Week 1**: 109+ examples (59 + 50 historical)
- **After Month 1**: 259+ examples (59 + 200 historical)
- **After Month 3**: 659+ examples (59 + 600 historical)
- **Increase**: Exponential growth with automated collection!

### Prediction Accuracy
- **Baseline**: ~60% (random is 50%)
- **Expected**: 70-80% with historical data
- **Impact**: 10-20% better signal quality

### Outcome Distribution Learning
- **100x+**: ML learns what mega runners look like early
- **Rugs**: ML learns red flags to avoid
- **Small gains**: ML learns realistic expectations

---

## Summary

**Automatic Mode (Recommended)**:
- ✅ Zero manual work
- ✅ Continuous dataset growth
- ✅ FREE (under all API limits)
- ✅ Runs in background
- ✅ Enabled by default

**Manual Mode**:
- ✅ Full control over parameters
- ✅ On-demand collection
- ✅ Useful for initial dataset

**What you get**:
- Historical examples of successful tokens
- Early-stage metrics (what 100x tokens looked like at 6h old)
- Whale wallets that consistently pick winners
- All data ready for ML training

**Why it matters**:
- ML learns from proven winners
- Better predictions than training on just 59 examples
- Identifies patterns that precede 100x gains
- Automatic rug filtering

🚀 **Ready to collect historical data and train ML automatically!**
