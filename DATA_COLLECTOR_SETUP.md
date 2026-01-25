# Historical Data Collector - Setup Guide
**Status:** ✅ **READY FOR RAILWAY DEPLOYMENT**
**Last Updated:** 2026-01-25

---

## ✅ What's Working

### **Automated Collector Integration**
- ✅ Integrated into `main.py:483-484` (starts on bot startup)
- ✅ Runs weekly in background (every 168 hours)
- ✅ Incremental updates (won't re-collect existing tokens)
- ✅ Configurable via environment variables

### **Code Components**
1. **`automated_collector.py`** - Background scheduler
2. **`run_collector_once.py`** - Manual one-time runner
3. **`tools/historical_data_collector.py`** - Core collection logic

---

## 🚀 How It Works

### **On Railway Deployment:**

```
Bot starts → Automated collector initializes → Schedules first run in 1 hour
                                             ↓
                          Waits for scheduled time (every 7 days)
                                             ↓
                    Collects 50 new tokens from DexScreener
                                             ↓
           Extracts whale wallets (if Moralis API key is set)
                                             ↓
        Saves to data/historical_training_data.json
                                             ↓
                  Updates database with successful whales
                                             ↓
                      Schedules next run (+7 days)
```

### **First Run Timeline:**
- **T+0h:** Bot deploys to Railway
- **T+1h:** First collector run starts (gives bot time to stabilize)
- **T+1h-2h:** Collects 50 tokens + whales
- **T+168h:** Second run (7 days later)
- **Every 7 days:** Incremental updates (+50 tokens each time)

---

## 📊 What Gets Collected

### **Token Data (from DexScreener - FREE!)**
For each token:
```json
{
  "token_address": "...",
  "symbol": "TOKEN",
  "name": "Token Name",
  "price_usd": 0.001,
  "market_cap": 5000000,
  "liquidity": 150000,
  "volume_24h": 500000,
  "buys_24h": 120,
  "sells_24h": 80,
  "buy_percentage_24h": 60.0,
  "outcome": "10x",
  "whale_wallets": ["wallet1...", "wallet2..."]
}
```

### **Whale Wallets (from Moralis - Optional)**
Successful whales (50%+ win rate):
```json
{
  "address": "whale_address...",
  "tokens_bought_count": 5,
  "wins": 3,
  "win_rate": 0.6,
  "tokens": [...]
}
```

---

## ⚙️ Configuration

### **Environment Variables (Railway)**

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTO_COLLECTOR_ENABLED` | `true` | Enable/disable automated collection |
| `AUTO_COLLECTOR_INTERVAL_HOURS` | `168` | Run every 7 days (168h) |
| `AUTO_COLLECTOR_COUNT` | `50` | Collect 50 new tokens per run |
| `AUTO_COLLECTOR_MIN_MCAP` | `1000000` | Min MCAP: $1M |
| `AUTO_COLLECTOR_MAX_MCAP` | `100000000` | Max MCAP: $100M |
| `MORALIS_API_KEY` | *(optional)* | For whale extraction |

### **Current Config (from config.py:33-37)**
```python
AUTO_COLLECTOR_ENABLED = True      # ✅ Enabled
AUTO_COLLECTOR_INTERVAL_HOURS = 168  # Every 7 days
AUTO_COLLECTOR_COUNT = 50           # 50 tokens per run
AUTO_COLLECTOR_MIN_MCAP = 1000000   # $1M minimum
AUTO_COLLECTOR_MAX_MCAP = 100000000 # $100M maximum
```

---

## 🔧 API Requirements

### **DexScreener (FREE - No API key needed)**
- ✅ Token discovery
- ✅ Market data (price, MCAP, volume, liquidity)
- ✅ Transaction data (buys/sells)
- ✅ Price changes
- **Rate limits:** 300 req/min (plenty for 50 tokens)

### **Moralis (Optional - Free tier: 40K CU/day)**
- 🔧 Whale wallet extraction
- 🔧 Top holders analysis
- 🔧 Early buyer detection
- **Cost:** ~10 CU per token = 500 CU for 50 tokens
- **Sign up:** https://admin.moralis.io

**Without Moralis:**
- ✅ Collector still works
- ✅ Token data collected
- ❌ No whale wallets extracted
- 💡 Can add Moralis later anytime!

---

## 📁 Output Files

### **`data/historical_training_data.json`**
```json
{
  "collected_at": "2026-01-25T18:16:00Z",
  "total_tokens": 150,
  "cu_used_estimate": 1500,
  "outcome_distribution": {
    "100x+": 5,
    "50x": 10,
    "10x": 30,
    "2x": 50,
    "small": 55
  },
  "tokens": [...]
}
```

### **`data/successful_whale_wallets.json`** (if Moralis enabled)
```json
{
  "collected_at": "2026-01-25T18:16:00Z",
  "total_whales": 25,
  "whales": [
    {
      "address": "whale123...",
      "tokens_bought_count": 8,
      "wins": 5,
      "win_rate": 0.625,
      "tokens": [...]
    }
  ]
}
```

---

## 🧪 Testing

### **Local Testing (Manual Run)**
```bash
# One-time collection (manual)
python3 run_collector_once.py

# Or direct script
python3 tools/historical_data_collector.py --count 20
```

### **Railway Logs (Monitor Progress)**
Look for these messages:
```
🤖 AUTOMATED HISTORICAL COLLECTOR
   Status: ENABLED
   Schedule: Every 168 hours (7 days)
   Tokens per run: 50

🔍 SCANNING DEXSCREENER FOR 50 PUMP.FUN GRADUATES
   ✅ TOKEN: $5,000,000 MCAP

🐋 EXTRACTING WHALE WALLETS
   [1/50] TOKEN...
   🐋 Total whales found: 12

✅ COLLECTION COMPLETE
   📊 Collected 50 tokens
   🐋 Identified 15 successful whales
   💰 Estimated Moralis CU used: 500
```

---

## 🚨 Troubleshooting

### **No tokens collected**
- ✅ Check Railway logs for API errors
- ✅ Verify network connectivity
- ✅ DexScreener API might be down (rare)

### **No whale data**
- ⚠️ Moralis API key not set (this is optional)
- ✅ Set `MORALIS_API_KEY` in Railway env vars
- ✅ Get free key at: https://admin.moralis.io

### **Collector not running**
- ✅ Check `AUTO_COLLECTOR_ENABLED=true` in Railway
- ✅ Look for startup logs: "AUTOMATED HISTORICAL COLLECTOR"
- ✅ First run is 1 hour after deployment (normal)

---

## 📈 Expected Results

### **After 1st Run (1 hour after deployment):**
- 50 tokens collected
- 10-20 successful whales identified (if Moralis enabled)
- `data/historical_training_data.json` created
- Ready for ML training!

### **After 4 Runs (1 month):**
- 200 tokens collected
- 40-60 successful whales
- Rich dataset for ML training
- High-confidence whale patterns

### **After 8 Runs (2 months):**
- 400+ tokens
- 80+ successful whales
- Production-ready ML model
- Automated whale-copy strategy

---

## 🎯 Next Steps After Collection

1. **ML Training:**
   ```bash
   python ralph/ml_pipeline.py --train
   ```

2. **Use Whale Data:**
   - Successful whales saved to database
   - Real-time matching in conviction scoring
   - +15 points when known whale buys

3. **Monitor Performance:**
   ```bash
   python ralph/win_rate_dashboard.py
   ```

---

## 🔐 Security Notes

- ✅ No sensitive data in collected files
- ✅ Wallet addresses are public on-chain data
- ✅ Safe to commit to repo
- ✅ All API calls are read-only

---

## 📊 Cost Estimate

### **Free Tier (No Moralis):**
- DexScreener: FREE (no limit)
- **Total cost: $0/month**

### **With Moralis Free Tier:**
- DexScreener: FREE
- Moralis: 40K CU/day (500 CU per week = plenty)
- **Total cost: $0/month**

### **Scaling Up:**
- 50 tokens/week = ~200 tokens/month
- 10 CU per token = 500 CU/week
- Well within 40K CU/day free tier!

---

## ✅ Status: READY FOR DEPLOYMENT

The collector is **fully integrated** and will start automatically when deployed to Railway!

**What happens next:**
1. Deploy bot to Railway
2. Wait 1 hour
3. Collector runs first collection
4. Check Railway logs for progress
5. Repeat weekly for continuous ML dataset growth

**Manual trigger (admin command):**
```
/collect_data
```
(Triggers immediate collection run)

---

**Questions? Check Railway logs or run diagnostics:**
```bash
python startup_diagnostics.py
```
