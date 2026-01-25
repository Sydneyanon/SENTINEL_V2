# Daily Pipeline Automation Setup

## Overview

The daily pipeline automatically:
1. **Collects** yesterday's top 50 tokens from DexScreener/Moralis (midnight UTC)
2. **Extracts** whale wallets and saves to database
3. **Retrains** ML model if enough new data (200+ tokens minimum, 50+ new)
4. **Deploys** new model for next conviction scoring cycle

## Files

- `tools/daily_token_collector.py` - Collects top tokens from yesterday
- `tools/automated_ml_retrain.py` - Smart ML retraining with validation
- `tools/daily_pipeline.sh` - Master script that runs both in sequence

## Railway Deployment

### Option 1: Railway Cron Job (Recommended)

Railway supports cron-like scheduling via their Cron service.

1. **Add Cron Service to `railway.toml`:**

```toml
[[services]]
name = "daily-pipeline"
type = "cron"
cronSchedule = "0 0 * * *"  # Midnight UTC daily
command = "/home/user/SENTINEL_V2/tools/daily_pipeline.sh"
```

2. **Deploy:**
```bash
railway up
```

Railway will automatically run the pipeline daily at midnight UTC.

### Option 2: Built-in Python Scheduler (Alternative)

If Railway cron is not available, use APScheduler:

1. **Install APScheduler:**
```bash
pip install apscheduler
```

2. **Add to `main.py` (already running 24/7):**

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from tools.daily_token_collector import DailyTokenCollector
from tools.automated_ml_retrain import AutomatedMLRetrainer

# In main() function:
scheduler = AsyncIOScheduler()

# Schedule daily collection at midnight UTC
scheduler.add_job(
    run_daily_pipeline,
    'cron',
    hour=0,
    minute=0,
    timezone='UTC'
)

scheduler.start()
logger.info("✅ Daily pipeline scheduled for midnight UTC")

async def run_daily_pipeline():
    logger.info("🌅 Starting daily pipeline...")

    # Step 1: Collect tokens
    collector = DailyTokenCollector()
    await collector.collect_daily()

    # Step 2: Retrain ML
    retrainer = AutomatedMLRetrainer()
    await retrainer.run()

    logger.info("✅ Daily pipeline complete")
```

3. **Add to requirements.txt:**
```
apscheduler==3.10.4
```

## Local Development / VPS

For local or VPS deployment, use cron:

### Add to Crontab

```bash
crontab -e
```

Add this line:
```
0 0 * * * /home/user/SENTINEL_V2/tools/daily_pipeline.sh >> /home/user/SENTINEL_V2/logs/daily_pipeline.log 2>&1
```

This runs the pipeline daily at midnight UTC and logs output.

### Create Log Directory

```bash
mkdir -p /home/user/SENTINEL_V2/logs
```

## Manual Execution

Test the pipeline manually:

```bash
# Run full pipeline
./tools/daily_pipeline.sh

# Or run individually:
python3 tools/daily_token_collector.py
python3 tools/automated_ml_retrain.py
```

## Configuration

### Adjust Collection Size

Edit `.env`:
```bash
DAILY_COLLECTOR_COUNT=50  # Default: 50 tokens/day
```

### Adjust ML Retraining Thresholds

Edit `tools/automated_ml_retrain.py`:
```python
self.min_tokens_for_retrain = 200  # Minimum total dataset size
self.min_new_tokens_for_retrain = 50  # Minimum new tokens to trigger retrain
```

## Monitoring

### Check Data Collection

```bash
cat data/historical_training_data.json | jq '.total_tokens'
```

### Check ML Training Metrics

```bash
cat data/ml_training_metrics.json | jq '.last_training'
```

### Check Logs (if using cron)

```bash
tail -f logs/daily_pipeline.log
```

## Expected Behavior

### Daily at Midnight UTC:
1. ✅ Collects 50 tokens that ran yesterday (100%+ gain)
2. ✅ Extracts whale wallets (early buyers who profited)
3. ✅ Saves whales to database → Used in real-time conviction boost
4. ✅ Checks if ML retraining needed:
   - **YES** if 200+ total tokens AND 50+ new tokens
   - **NO** if not enough data yet
5. ✅ If YES: Retrains XGBoost with new features
6. ✅ Deploys new model → Used in next signal analysis

### Growth Timeline:
- **Day 1-4:** Collecting data (0-200 tokens) → No retraining yet
- **Day 5:** First retrain (200+ tokens) → Model v1 deployed
- **Day 10:** Second retrain (450+ tokens) → Model v2 deployed
- **Day 20:** Third retrain (950+ tokens) → Model v3 deployed
- **Ongoing:** Retrain every ~5-10 days as data accumulates

## Troubleshooting

### Pipeline Not Running
- **Railway:** Check Railway dashboard → Logs → Cron service
- **Cron:** Run `crontab -l` to verify entry
- **Permissions:** Ensure scripts are executable (`chmod +x`)

### Collection Failing
- Check Moralis API key in `.env`
- Check Helius RPC URL in `.env`
- View logs: `python3 tools/daily_token_collector.py`

### ML Training Failing
- Ensure `data/historical_training_data.json` exists
- Check file has valid JSON
- Run manually: `python3 tools/automated_ml_retrain.py`

### Model Not Loading
- Check `ralph/models/` directory exists
- Verify `.joblib` file exists
- Restart main bot to reload model

## Benefits

✅ **Automated Data Collection:** No manual work, grows dataset organically

✅ **Smart ML Retraining:** Only retrains when enough new data (saves compute)

✅ **Continuous Improvement:** Model adapts to market shifts automatically

✅ **Whale Tracking:** Real-time conviction boost from successful wallets

✅ **Zero Maintenance:** Set and forget - runs 24/7 on Railway

## Next Steps

After setup:
1. Monitor first few runs to ensure working
2. Check `data/ml_training_metrics.json` for training history
3. Verify whales appear in database: `sqlite3 data/signals.db "SELECT COUNT(*) FROM whale_wallets;"`
4. Watch for ML bonus in signal logs: "ML: +15 pts (predicted 50x)"
