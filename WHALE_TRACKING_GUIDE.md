# Whale Tracking & Daily Collection System

## Overview

This system collects successful tokens daily, extracts whale wallets, and uses them to boost conviction scores in real-time.

## 🐋 How Whale Tracking Works

### 1. **Data Collection**
- **Daily**: Collects top 50-100 tokens from DexScreener
- **Metrics**: Price, volume, market cap, buy/sell ratios
- **Whales**: Top holders with $50K+ positions (via Helius RPC)

### 2. **Whale Identification**
```python
# For each successful token (10x+):
- Get top 20 token holders (Helius getTokenLargestAccounts)
- Filter for positions worth $50K+ USD
- Track which tokens they bought
- Calculate win rate: (wins / total_tokens_bought)
- Save whales with 50%+ win rate to database
```

### 3. **Real-Time Conviction Boost**
When your bot tracks a new token:
```python
# Check if any successful whale bought it
whale_wallets_from_db = get_successful_whales()  # From database
if token_buyer in whale_wallets_from_db:
    conviction_score += WHALE_BONUS_POINTS  # e.g., +15 points
    signal_confidence += 20%  # Higher confidence
```

## 📊 Database Integration

### Whale Tables (Already Exist in database.py)

**`whale_wallets` table:**
- `address`: Wallet address
- `tokens_bought_count`: How many tokens they bought
- `wins`: How many were successful (10x+)
- `win_rate`: wins / tokens_bought_count
- `is_early_whale`: Bought in early (before 50% bonding curve)

**`whale_token_purchases` table:**
- `whale_address`: Wallet address
- `token_address`: Token they bought
- `token_symbol`: Symbol
- `usd_value`: Position size
- `balance`: Token amount

### ML Training Data Flow

```
Daily Collection
    ↓
Extract Whales (Helius)
    ↓
Calculate Win Rates
    ↓
Save to Database (successful whales only)
    ↓
Save to JSON (all tokens for ML training)
    ↓
Bot queries DB in real-time
    ↓
Whale buy detected → Conviction boost
```

## 🚀 Running the System

### Option 1: Daily Automated Collection (Recommended)

```bash
# Run daily via cron
0 0 * * * cd /path/to/SENTINEL_V2 && python tools/daily_token_collector.py

# Or add to automated_collector.py for Railway
```

**Benefits:**
- Continuous dataset growth (50 tokens/day = 18,250/year)
- Diverse market conditions captured
- Whale database stays updated
- No manual intervention needed

### Option 2: One-Time Collection

```bash
# Collect 150 tokens once
python run_collector_once.py

# Good for: Initial dataset, backfilling
```

### Environment Variables

```bash
# Required for whale extraction
HELIUS_API_KEY=your_helius_key_here

# Optional for Moralis data
MORALIS_API_KEY=your_moralis_key_here

# Database (Railway auto-provides)
DATABASE_URL=postgresql://...

# Daily collection config
DAILY_COLLECTOR_COUNT=50  # Tokens per day
```

## 📈 Daily Collection Strategy

### Why Daily Collection is Better

**One-Time Collection (150 tokens):**
- ❌ Single snapshot in time
- ❌ Same market conditions
- ❌ Limited diversity
- ❌ Becomes stale quickly

**Daily Collection (50 tokens/day):**
- ✅ Continuous updates
- ✅ Multiple market conditions (bull, bear, crab)
- ✅ Fresh data always available
- ✅ Larger dataset over time (18K+ tokens/year)
- ✅ Whales tracked across different periods
- ✅ **CRITICAL**: Collects tokens that ALREADY RAN (known outcomes)

### What Gets Collected Daily

**Key Insight: We collect YESTERDAY'S winners, not today's trending tokens**

This gives us labeled training data:
```
Token XYZ at 10:00 AM → Had these signals → By 10:00 PM → 50x gain ✅
```

**Collection filters:**
```json
{
  "required_criteria": {
    "price_change_24h": ">100%",  // Already 2x+ (it RAN yesterday)
    "volume_24h": ">$100K",        // Real activity
    "market_cap": ">$500K",        // Not too small
    "chain": "solana",             // Solana only
    "outcome_known": true          // We know if it was 2x, 10x, 50x, etc.
  },
  "per_token_data": {
    "outcome": "KNOWN (2x, 10x, 50x, 100x+)",  // ← CRITICAL
    "early_whales": "Wallets that bought BEFORE pump",
    "conditions_before_pump": "Volume, buys, ratios at early stage",
    "final_result": "Peak MCAP, total gain, duration"
  }
}
```

**Example Daily Collection:**
```
Date: 2026-01-25
Tokens: 50 that gained 100%+ in last 24h

Token 1: PEPE2
  - Started: $200K MCAP (yesterday 10am)
  - Ended: $5M MCAP (today 10am)
  - Outcome: 25x ✅
  - Early whales: [0x7xKXtg..., 0x8BnEgH...]
  - Early signals: 300 buys/hr, 75% buy ratio, 2 whales bought

Token 2: SCAM
  - Started: $150K MCAP
  - Peaked: $800K MCAP (+5x)
  - Ended: $50K MCAP (-67% from peak)
  - Outcome: RUG ❌
  - No early whale activity detected
```

This is PERFECT for ML training because:
- We have the complete story (start → signals → outcome)
- We know which whales picked winners vs losers
- We can correlate early signals with final results

## 🎯 Conviction Scoring with Whales

### Current Scoring Weights (config.py)

```python
SMART_WALLET_WEIGHTS = {
    'per_kol': 10,           # 10 points per KOL wallet
    'max_score': 40,         # Cap at 4 KOLs
    'multi_kol_bonus': 15,   # Extra if 2+ KOLs buy
}
```

### Proposed: Add Whale Weights

```python
WHALE_WEIGHTS = {
    'high_win_rate': 15,     # Whale with 75%+ win rate
    'medium_win_rate': 10,   # Whale with 50-74% win rate
    'early_whale': 5,        # Additional if whale bought early
    'multiple_whales': 10,   # Bonus if 2+ whales buy
}
```

### Example Conviction Calculation

```python
# Token XYZ scenario:
base_score = 40  # From other factors

# Whale detection:
whale_1 = "7xKXtg..."  # 80% win rate (10/12 tokens)
whale_2 = "8BnEgH..."  # 65% win rate (13/20 tokens)

# Scoring:
whale_1_score = 15  # High win rate (75%+)
whale_2_score = 10  # Medium win rate (50-74%)
multi_whale_bonus = 10  # 2+ whales

total_whale_boost = 15 + 10 + 10 = 35 points

# Final conviction:
final_score = 40 + 35 = 75 points → SIGNAL! 🚀
```

## 🔧 Implementation Steps

### Step 1: Test Whale Extraction

```bash
# Make sure HELIUS_API_KEY is set
export HELIUS_API_KEY="your_key_here"

# Run collector to test whale extraction
python run_collector_once.py

# Check results
cat data/successful_whale_wallets.json | jq '.whales[] | {address, win_rate, wins}'
```

### Step 2: Add Whale Scoring to Bot

Edit `conviction_engine.py`:

```python
async def calculate_conviction(self, token_address: str, token_data: dict) -> int:
    score = 0

    # ... existing scoring logic ...

    # NEW: Whale wallet boost
    whale_score = await self.check_whale_buyers(token_address)
    score += whale_score

    return score

async def check_whale_buyers(self, token_address: str) -> int:
    """Check if any successful whales bought this token"""
    score = 0

    # Get recent buyers (from PumpPortal or Helius)
    recent_buyers = await self.get_recent_buyers(token_address)

    # Get successful whales from database
    whales_from_db = await self.db.get_successful_whales()

    whale_buyers = []
    for buyer in recent_buyers:
        if buyer in whales_from_db:
            whale_data = whales_from_db[buyer]
            whale_buyers.append(whale_data)

            # Score based on win rate
            if whale_data['win_rate'] >= 0.75:
                score += 15  # High win rate
            elif whale_data['win_rate'] >= 0.50:
                score += 10  # Medium win rate

    # Bonus for multiple whales
    if len(whale_buyers) >= 2:
        score += 10

    return score
```

### Step 3: Set Up Daily Collection

**Option A: Cron (Linux/Mac)**
```bash
# Edit crontab
crontab -e

# Add line (runs daily at midnight UTC):
0 0 * * * cd /home/user/SENTINEL_V2 && python tools/daily_token_collector.py >> logs/daily_collection.log 2>&1
```

**Option B: Railway Scheduler**
```bash
# Add to Procfile or Railway cron
collector: python tools/daily_token_collector.py
```

**Option C: Integrate with automated_collector.py**
Replace or supplement the weekly collector with daily collection.

## 📊 Monitoring & Analytics

### Check Collection Progress

```bash
# View total tokens collected
cat data/historical_training_data.json | jq '.total_tokens'

# View successful whales
cat data/successful_whale_wallets.json | jq '.total_whales'

# Top whales by win rate
cat data/successful_whale_wallets.json | jq '.whales | sort_by(.win_rate) | reverse | .[0:10]'
```

### Database Queries

```sql
-- Get top whales
SELECT address, win_rate, wins, tokens_bought_count
FROM whale_wallets
ORDER BY win_rate DESC, wins DESC
LIMIT 20;

-- Check if whale bought a token
SELECT w.address, w.win_rate, wtp.token_symbol
FROM whale_wallets w
JOIN whale_token_purchases wtp ON w.address = wtp.whale_address
WHERE wtp.token_address = 'ED5nyyWEzpPPiWimP8vYm7sD7TD3LAt3Q3gRTWHzPJBY';
```

## 🎓 Machine Learning Integration

### Current Data Structure

```json
{
  "tokens": [
    {
      "token_address": "...",
      "symbol": "MOODENG",
      "price_usd": 0.245,
      "market_cap": 64000000,
      "volume_24h": 5200000,
      "buys_24h": 1843,
      "sells_24h": 892,
      "buy_percentage_24h": 67.4,
      "outcome": "100x+",
      "whale_wallets": ["7xKXtg...", "8BnEgH..."],
      "whale_count": 2
    }
  ]
}
```

### ML Training Features

**Input Features (X):**
- `price_usd`, `market_cap`, `liquidity`
- `volume_24h`, `volume_6h`
- `buys_24h`, `sells_24h`, `buy_percentage`
- `whale_count` ← NEW!
- `has_high_win_rate_whale` ← NEW! (boolean)

**Target (y):**
- `outcome`: ["small", "2x", "10x", "50x", "100x+"]

**Benefits:**
- Whale presence becomes a predictive feature
- ML learns: "tokens with 2+ whales have X% success rate"
- Can predict probability of success based on whale activity

## 🚨 Important Notes

1. **Helius API Key Required**: Whale extraction needs Helius RPC (you already have this)
2. **Rate Limiting**: Daily collector sleeps 1.5s between whale extractions
3. **Database Required**: Whales are saved to DB for real-time matching
4. **Storage**: 50 tokens/day = ~5KB/day = ~1.8MB/year (negligible)

## 🎯 Expected Results

### After 30 Days of Daily Collection:
- **Tokens collected**: 1,500+
- **Whales identified**: 50-150 (with 50%+ win rate)
- **Database growth**: ~50KB
- **ML dataset**: Ready for training

### Conviction Score Improvements:
- **Before whales**: Avg 58 conviction, 32% win rate
- **After whales**: Avg 68 conviction, 45%+ win rate (projected)
- **Whale signals**: Higher confidence, better timing

## 🔗 Files Modified/Created

- ✅ `tools/historical_data_collector.py` - Updated with Helius whale extraction
- ✅ `tools/daily_token_collector.py` - NEW: Daily collection script
- ✅ `database.py` - Already has whale_wallets tables
- ⏳ `conviction_engine.py` - TODO: Add whale scoring
- ⏳ `automated_collector.py` - TODO: Integrate daily collection

---

**Ready to deploy!** 🚀

The system is now set up to:
1. ✅ Extract whale wallets using Helius
2. ✅ Save whales to database
3. ✅ Collect tokens daily
4. ⏳ Boost conviction when whales buy (next step)
