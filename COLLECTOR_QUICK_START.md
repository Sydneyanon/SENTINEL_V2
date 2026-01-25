# Data Collector - Quick Start on Railway 🚀

## ✅ You're Ready!

The collector is **fully configured** and will run automatically on Railway. Here's what to expect:

---

## 🎯 Automatic Collection (Recommended)

**When:** 1 hour after deployment, then every 7 days
**What:** Collects 50 tokens + whales automatically
**Where:** Runs in background, no action needed

### Watch it work:
```bash
# In Railway logs, look for:
🤖 AUTOMATED HISTORICAL COLLECTOR
   Status: ENABLED
   Next run: <timestamp>

# When it runs:
🔍 SCANNING DEXSCREENER FOR 50 PUMP.FUN GRADUATES
   ✅ TOKEN: $5,000,000 MCAP
   ✅ TOKEN: $8,000,000 MCAP
   ...

🐋 EXTRACTING WHALE WALLETS
   [1/50] TOKEN... 🐋 Total whales found: 8
   [2/50] TOKEN... 🐋 Total whales found: 5
   ...

✅ COLLECTION COMPLETE
   📊 Collected 50 tokens
   🐋 Identified 15 successful whales
```

---

## 🧪 Manual Test Run (Optional)

Want to test it now? Run this in Railway shell:

```bash
# Quick test (10 tokens, ~2-3 minutes)
bash test_collector_railway.sh

# Or full collection (50 tokens, ~10-15 minutes)
python3 tools/historical_data_collector.py --count 50
```

### What you'll see:
1. **DexScreener scan** - Finding successful tokens
2. **Moralis extraction** - Finding whale wallets (if API key set)
3. **Results saved** - JSON files + database updated
4. **Summary** - Token count, whale count, outcomes

---

## 📊 Check Results

### View collected data:
```bash
# On Railway shell
cat data/historical_training_data.json | jq '.total_tokens, .outcome_distribution'

# Example output:
# 50
# {
#   "100x+": 2,
#   "50x": 5,
#   "10x": 12,
#   "2x": 18,
#   "small": 13
# }
```

### View whale data:
```bash
cat data/successful_whale_wallets.json | jq '.total_whales'
# Example: 15
```

---

## ⚙️ Configuration

Current settings (from `config.py`):

| Setting | Value | Meaning |
|---------|-------|---------|
| `AUTO_COLLECTOR_ENABLED` | `true` | ✅ Auto-collection ON |
| `AUTO_COLLECTOR_INTERVAL_HOURS` | `168` | Runs every 7 days |
| `AUTO_COLLECTOR_COUNT` | `50` | Collects 50 tokens per run |
| `AUTO_COLLECTOR_MIN_MCAP` | `1000000` | Min $1M MCAP |
| `AUTO_COLLECTOR_MAX_MCAP` | `100000000` | Max $100M MCAP |

**To change:** Update environment variables in Railway dashboard

---

## 🔑 API Keys

### ✅ Required:
- **None!** DexScreener is free (no key needed)

### 🎯 Optional (for whale extraction):
- **MORALIS_API_KEY** - You already have this! ✅
  - Free tier: 40K CU/day
  - Get at: https://admin.moralis.io
  - Used for: Finding successful whale wallets

**You're all set!** Collector will use Moralis automatically.

---

## 🚨 Troubleshooting

### "No tokens collected"
- ✅ Check Railway logs for errors
- ✅ Verify internet connectivity
- ✅ DexScreener API might be temporarily down

### "No whale data"
- ⚠️ Check `MORALIS_API_KEY` is set in Railway env vars
- ✅ Collector still works without it (just no whales)

### "Collector not running"
- ✅ Check Railway logs for: "AUTOMATED HISTORICAL COLLECTOR"
- ✅ Verify `AUTO_COLLECTOR_ENABLED=true`
- ✅ First run is T+1h (normal delay)

---

## 📈 What Happens Next

### After 1st collection (T+1h):
```
✅ 50 tokens collected
✅ 10-20 whales identified
✅ data/historical_training_data.json created
✅ Ready for ML training!
```

### After 1 month (4 collections):
```
✅ 200 tokens collected
✅ 40-60 whales identified
✅ Rich dataset for ML
```

### After 2 months (8 collections):
```
✅ 400+ tokens
✅ 80+ successful whales
✅ Production-ready ML model
✅ Automated whale-copy strategy
```

---

## 🎯 Using the Data

### 1. Train ML Model:
```bash
python ralph/ml_pipeline.py --train
```

### 2. Whale Copy Strategy:
- Whales automatically saved to database
- Real-time matching in conviction scoring
- +15 points when known whale buys

### 3. Performance Dashboard:
```bash
python ralph/win_rate_dashboard.py
```

---

## ✅ Summary

**What's working:**
- ✅ Collector integrated into main.py
- ✅ Auto-runs every 7 days
- ✅ Moralis API key configured (you fixed it!)
- ✅ Will collect 50 tokens + whales per run
- ✅ Incremental updates (no duplicates)

**What to do:**
1. Deploy to Railway (if not already)
2. Wait 1 hour for first collection
3. Check Railway logs for progress
4. Enjoy automated ML dataset growth!

**Manual test (optional):**
```bash
bash test_collector_railway.sh
```

---

**Status:** ✅ **READY TO ROCK!**

The collector will start working as soon as the bot deploys to Railway. No further action needed!
