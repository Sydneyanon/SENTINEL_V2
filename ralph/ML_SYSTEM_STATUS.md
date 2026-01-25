# ML System Status & Startup Guide

**Status**: ✅ Code Ready | ❌ Not Trained | ⏳ Needs Data
**Last Updated**: 2026-01-25

---

## Current State

### What Exists
✅ **PostgreSQL Database** - Tables created, schema ready
✅ **ML Pipeline Code** - XGBoost training pipeline (`ralph/ml_pipeline.py`)
✅ **ML Integration** - Conviction score integration (`ralph/integrate_ml.py`)
✅ **Database Schema** - Full tracking for signals, outcomes, KOL activity

### What's Missing
❌ **Trained ML Models** - `ralph/models/` directory doesn't exist
❌ **Training Data** - `ralph/external_data.json` has 0 tokens
❌ **Outcome Labels** - Need to track which signals succeeded/failed

---

## System Architecture

### Data Flow
```
Token Detected → Conviction Scoring → Signal Posted → Database
                                          ↓
                                    Track Outcome (7 days)
                                          ↓
                                    ML Training Data
                                          ↓
                                    Train XGBoost Model
                                          ↓
                                  ML Predictions → Conviction Boost
```

### Database Tables

**1. `signals`** - All posted signals
- Conviction score, entry price, liquidity, volume
- Outcome tracking (rug, 2x, 10x, 50x, 100x+)
- Narrative tags, KOL wallets, holder patterns
- Currently: **UNKNOWN COUNT** (need to check)

**2. `smart_wallet_activity`** - KOL transactions
- Tracks which KOLs bought which tokens
- Win rate and PnL tracking per wallet
- Currently: **UNKNOWN COUNT**

**3. `kol_buys`** - KOL buy events
- Amount, transaction signature
- Currently: **UNKNOWN COUNT**

**4. `performance`** - Milestone tracking
- 2x, 5x, 10x, 50x, 100x achievements
- Time to milestone

---

## How to Start ML System

### Step 1: Check Database (5 minutes)

**Run on Railway**:
```bash
python ralph/check_database.py
```

This will:
- Count total signals in database
- Show conviction score distribution
- Check how many have outcomes labeled
- Export all signal data to `ralph/signals_export.json`

**What you'll learn**:
- Do we have enough data to train? (need 50+ signals)
- How many outcomes are labeled?
- What's the signal quality distribution?

---

### Step 2: Label Outcomes (if needed)

If database has signals but no outcomes:

**Option A: Automated Tracker** (Recommended)
Create `outcome_tracker.py` to run daily:
```python
# Check each signal's current price vs entry price
# After 7 days, label outcome:
# - rug: -50% or worse
# - 2x: 100-300%
# - 10x: 300-900%
# - 50x: 900-4900%
# - 100x+: 5000%+

# Update database:
await db.update_signal_outcome(
    token_address,
    outcome="10x",
    outcome_price=current_price,
    max_price_reached=max_price,
    max_roi=max_roi
)
```

**Option B: Manual Labeling**
Export signals, check Birdeye/DexScreener, label manually.

---

### Step 3: Train Model (30 minutes)

Once you have 50+ signals with outcomes:

```bash
cd ralph
python ml_pipeline.py --train
```

**What this does**:
1. Loads signals from `signals_export.json`
2. Extracts features (KOL count, holder concentration, volume/liquidity, etc.)
3. Trains XGBoost classifier (5 classes: rug, 2x, 10x, 50x, 100x+)
4. Saves model to `ralph/models/xgboost_model.pkl`
5. Shows accuracy and feature importance

**Expected Output**:
```
✅ Model trained!
   Accuracy: 73.5%

📊 Top 10 Most Important Features:
   kol_count: 0.2341
   volume_to_liquidity: 0.1823
   top_10_concentration: 0.1456
   ...
```

---

### Step 4: Enable ML Predictions (1 hour)

**Edit `scoring/conviction_engine.py`**:

```python
# At top of file
from ralph.integrate_ml import get_ml_predictor

# In __init__
self.ml_predictor = get_ml_predictor()  # Loads model once

# In analyze_token(), after calculating mid_total:
ml_result = self.ml_predictor.predict_for_signal(
    token_data,
    kol_count=len(smart_wallet_activity)
)

if ml_result['ml_enabled']:
    logger.info(f"   🤖 ML Prediction: {ml_result['class_name']}")
    logger.info(f"   🎯 ML Confidence: {ml_result['confidence']*100:.1f}%")
    logger.info(f"   ⚡ ML Bonus: {ml_result['ml_bonus']:+d} points")

    # Add ML bonus to final score
    ml_bonus = ml_result['ml_bonus']
else:
    ml_bonus = 0

final_score = mid_total + holder_score + ml_bonus
```

**ML Bonus Logic**:
- Predicted 100x+ → +20 points (if high confidence)
- Predicted 50x → +15 points
- Predicted 10x → +10 points
- Predicted 2x → +5 points
- Predicted rug → **-30 points** (filter out!)

---

## Alternative: Use Runner Data to Train

**Current issue**: `ralph/runner_data.json` only has post-success data, not early signals.

**Solution**: Fetch historical data from DexScreener for these 4 runners:
1. Find their Raydium pool creation time
2. Get volume/liquidity data from first 24 hours
3. Estimate early holder distribution
4. Create synthetic "early signal" data
5. Train model on that

**Caveat**: Less accurate than real signal data, but better than nothing.

---

## Can Claude Do This?

**Yes** - I can execute the entire ML pipeline:

✅ Check database (run `check_database.py` on Railway)
✅ Create outcome tracker if needed
✅ Train ML model (`ml_pipeline.py --train`)
✅ Integrate ML predictions into conviction engine
✅ Test and verify predictions

**Blockers**:
- Need Railway access to run Python scripts on production
- OR need DATABASE_URL to connect from local environment
- OR export signal data manually and provide to me

---

## Recommended Next Steps

### Immediate (Do Now)
1. **Run `ralph/check_database.py` on Railway**
   - See how many signals exist
   - Export data for analysis
   - Determine if we need outcome tracker

### Short Term (This Week)
2. **If <50 signals**: Keep bot running, collect more data
3. **If 50+ signals**: Implement outcome tracker, label outcomes
4. **If 50+ with outcomes**: Train ML model immediately

### Medium Term (Next Week)
5. **Deploy ML predictions** to production
6. **Monitor ML accuracy** vs actual outcomes
7. **Retrain weekly** as more data accumulates

---

## Questions?

**Q: How many signals do we need?**
A: Minimum 50, ideally 100+. More data = better model.

**Q: How often to retrain?**
A: Weekly at first (as data accumulates), then monthly once stable.

**Q: Will ML improve signal quality?**
A: Yes, if trained on good data. Expected 10-20% boost in conviction accuracy.

**Q: What if model predicts wrong?**
A: Models aren't perfect. ML bonus is capped at ±30 points, so it won't override strong fundamentals.

**Q: Can we start without outcomes?**
A: No, need labeled data (which tokens succeeded/failed) to train supervised ML.

---

## Bottom Line

**ML System Status**: ✅ Code complete, ⏳ awaiting training data

**Next Action**: Run `ralph/check_database.py` to see if we have enough signals to start training.

**ETA to ML Live**:
- If data exists: 1-2 hours
- If need to collect: 1-2 weeks
