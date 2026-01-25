# Daily Data Collection Schedule

## ⏰ Collection Timing

### Automatic Collection: **MIDNIGHT UTC (00:00 UTC)** Daily

**Why midnight UTC?**
- Collects the COMPLETE 24-hour data from yesterday
- Gets "yesterday's winners" with KNOWN outcomes (2x, 10x, 50x, etc.)
- Provides labeled training data for ML models
- Consistent daily snapshots at the same time

### Timezone Reference

| Your Timezone | Collection Time |
|--------------|----------------|
| **UTC** | 00:00 (Midnight) |
| **EST (New York)** | 19:00 (7 PM previous day) |
| **PST (Los Angeles)** | 16:00 (4 PM previous day) |
| **GMT (London)** | 00:00 (Midnight) |
| **CET (Paris)** | 01:00 (1 AM) |
| **JST (Tokyo)** | 09:00 (9 AM) |
| **AEST (Sydney)** | 11:00 (11 AM) |

## 📊 What Gets Collected

### Yesterday's Winners Strategy

```
Timeline Example:
─────────────────────────────────────────────────────
Jan 24, 10:00 AM → Token launches at $200K MCAP
Jan 24, 02:00 PM → Whales buy, volume spikes
Jan 24, 08:00 PM → Hits $5M MCAP (25x gain!)
─────────────────────────────────────────────────────
Jan 25, 00:00 UTC → Our collector runs ✅
                  → Captures the complete story:
                     - Start MCAP: $200K
                     - Peak MCAP: $5M
                     - Outcome: 25x
                     - Early whales: 2 addresses
                     - Buy signals: 400 buys/hr
```

**Key Benefits:**
- ✅ **Known outcomes** - We know if it went 2x, 10x, 50x, or rugged
- ✅ **Complete data** - Full 24-hour cycle captured
- ✅ **Early signals** - Can identify what happened BEFORE the pump
- ✅ **Whale tracking** - Extract wallets that bought early
- ✅ **ML training** - Perfect labeled data for supervised learning

## 🔧 Configuration

### Environment Variables

```bash
# Enable/disable daily collection
DAILY_COLLECTOR_ENABLED=true

# Number of tokens to collect per day
DAILY_COLLECTOR_COUNT=50

# Optional: Helius for enhanced whale tracking
HELIUS_API_KEY=your_key_here

# Optional: Moralis for additional data
MORALIS_API_KEY=your_key_here
```

### Current Settings (config.py)
```python
DAILY_COLLECTOR_ENABLED = True      # ✅ Enabled
DAILY_COLLECTOR_COUNT = 50          # 50 tokens per day
```

## 📈 Collection Filters

### Required Criteria (Yesterday's Winners)
```json
{
  "price_change_24h": ">100%",     // Minimum 2x gain (it already ran!)
  "volume_24h": ">$100,000",        // Real trading activity
  "market_cap": ">$500,000",        // Not too small
  "chain": "solana",                // Solana only
  "outcome": "KNOWN"                // We know the final result ✅
}
```

### What We Extract

For each token:
```json
{
  "token_address": "...",
  "symbol": "MOONDOGE",
  "outcome": "50x",                    // ← KNOWN OUTCOME
  "early_signals": {
    "mcap_at_start": 200000,
    "volume_first_hour": 150000,
    "buys_first_hour": 400,
    "buy_ratio": 78,
    "whale_count": 2
  },
  "final_result": {
    "peak_mcap": 10000000,
    "gain_multiple": 50,
    "duration_hours": 18
  },
  "whale_wallets": ["0x7xKXtg...", "0x8BnEgH..."]
}
```

## 📊 Expected Growth

### Daily Accumulation
```
Day 1:   50 tokens  (50 total)
Day 7:   50 tokens  (350 total)
Day 30:  50 tokens  (1,500 total)
Day 365: 50 tokens  (18,250 total)
```

### Whale Database Growth
```
Week 1:  15 successful whales identified
Month 1: 50-75 whales tracked
Month 3: 150-200 whales tracked
Year 1:  500+ whales (filtered for 50%+ win rate)
```

## 🤖 Automated System

### How It Works

```
Bot starts on Railway
    ↓
Daily collector initializes at startup
    ↓
Calculates next midnight UTC
    ↓
[WAITS UNTIL MIDNIGHT]
    ↓
00:00 UTC → Collection starts
    ↓
Fetches yesterday's top 50 tokens from DexScreener
    ↓
Filters for 2x+ gainers (known outcomes)
    ↓
Extracts whale wallets (if Helius enabled)
    ↓
Saves to data/historical_training_data.json
    ↓
Updates database with successful whales
    ↓
Schedules next run (tomorrow midnight)
    ↓
[REPEAT DAILY]
```

## 🔍 Monitoring

### Check Collection Status

```bash
# View total tokens collected
cat data/historical_training_data.json | jq '.total_tokens'

# View last collection date
cat data/historical_training_data.json | jq '.last_daily_collection'

# View successful whales
cat data/successful_whale_wallets.json | jq '.total_whales'

# Check logs
tail -f logs/bot.log | grep "DAILY COLLECTION"
```

### Railway Logs

Look for these messages:
```
📅 AUTOMATED DAILY TOKEN COLLECTOR
   Status: ENABLED
   Schedule: Daily at 00:00 UTC (midnight)
   Next run: 2026-01-26 00:00:00 (in 4.2h)

📅 DAILY COLLECTION: STARTING MIDNIGHT RUN
   Date: 2026-01-26
   Goal: Collect yesterday's top performers

✅ Collected 50 tokens that ALREADY RAN
   Top gainer: MOONDOGE (+5000%)
   Median gain: +250%

✅ Daily collection complete
   Next run: 2026-01-27 00:00:00 UTC
```

## 🎯 Manual Collection

### Run Collection Now (Any Time)

```bash
# Manual run (doesn't affect schedule)
python3 tools/daily_token_collector.py
```

This will:
- Collect tokens immediately
- Save to same output files
- NOT change the midnight schedule

### When to Use Manual Collection

1. **Initial dataset** - Get data immediately after deployment
2. **Backfill** - Missed a day due to downtime
3. **Testing** - Verify system is working
4. **Custom analysis** - Want data at specific time

## 📁 Output Files

### Main Training Dataset
**Location:** `data/historical_training_data.json`

```json
{
  "collected_at": "2026-01-25T00:00:00Z",
  "total_tokens": 1500,
  "last_daily_collection": "2026-01-25",
  "tokens_collected_today": 50,
  "outcome_distribution": {
    "100x+": 15,
    "50x": 35,
    "10x": 150,
    "2x": 300,
    "small": 1000
  },
  "tokens": [...]
}
```

### Whale Database
**Location:** `data/successful_whale_wallets.json`

```json
{
  "collected_at": "2026-01-25T00:00:00Z",
  "total_whales": 75,
  "whales": [
    {
      "address": "7xKXtg...",
      "win_rate": 0.75,
      "wins": 9,
      "tokens_bought_count": 12
    }
  ]
}
```

## 🚀 Integration with Bot

### Real-Time Whale Matching

When bot detects a new token:
```python
# Check if any successful whale bought it
whale_buyers = check_whale_buyers(token_address)

if whale_buyers:
    # Whale with 75%+ win rate bought
    conviction_score += 15
    logger.info(f"🐋 Known whale detected: {whale_address}")
```

### ML Training Pipeline

```python
# Load historical data
with open('data/historical_training_data.json') as f:
    training_data = json.load(f)

# Features: Early signals
X = extract_features(training_data['tokens'])
# volume_early, buys_early, whale_count, buy_ratio, etc.

# Labels: Outcomes
y = extract_outcomes(training_data['tokens'])
# "2x", "10x", "50x", "100x+"

# Train model
model.fit(X, y)
```

## ⚠️ Important Notes

### API Requirements
- **Moralis**: PRIMARY data source (free tier: 40K CU/day) - Get at https://admin.moralis.io
- **Helius**: Optional (for enhanced whale tracking and transaction history)
- **DexScreener**: Fallback only (if Moralis not configured)

### Rate Limits
- Moralis: 40K CU/day (500-1000 CU per day = well within free tier limit)
- Helius: 100 req/sec on free tier
- DexScreener: 300 req/min (fallback only)

### Storage
- 50 tokens/day ≈ 5KB/day
- 18,250 tokens/year ≈ 1.8MB/year
- Negligible storage cost

## 🎓 Why This Approach Works

### Problem with "Trending Now" Collection
```
❌ Collect token while it's trending
   → Don't know outcome yet
   → Can't use for supervised ML
   → No labeled training data
```

### Solution: "Yesterday's Winners" Collection
```
✅ Collect token after it already ran
   → Know complete outcome (2x, 10x, 50x)
   → Perfect for supervised ML
   → Labeled training data ✅
   → Can identify early signals
   → Can track successful whales
```

### Example Comparison

**Trending Now (Bad):**
```json
{
  "collected": "2026-01-25 10:00 AM",
  "symbol": "NEWCOIN",
  "status": "Trending right now",
  "outcome": "???" ← Unknown!
}
```

**Yesterday's Winners (Good):**
```json
{
  "collected": "2026-01-25 00:00 UTC",
  "symbol": "MOONDOGE",
  "started": "2026-01-24 10:00 AM",
  "ended": "2026-01-25 00:00 AM",
  "outcome": "50x" ← Known! ✅
}
```

## 📖 Summary

### Key Points
1. ⏰ **Runs at midnight UTC daily**
2. 📊 **Collects yesterday's top performers**
3. ✅ **Known outcomes** (2x, 10x, 50x, etc.)
4. 🐋 **Tracks successful whale wallets**
5. 🤖 **Fully automated** (no manual intervention)
6. 📈 **Continuous growth** (50 tokens/day = 18K/year)
7. 💰 **Zero cost** (free APIs)

### Status
- ✅ Code implemented
- ✅ Integrated into main.py
- ✅ Auto-starts with bot
- ✅ Runs at midnight UTC daily
- ✅ Ready for Railway deployment

---

**Next Run:** Check logs for "📅 AUTOMATED DAILY TOKEN COLLECTOR" message with next scheduled time!
