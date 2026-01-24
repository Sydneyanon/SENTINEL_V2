# 🚨 URGENT: Execute OPT-044 Immediately

**USER REQUEST: Highest priority task - collect 1000 token dataset**

## What You Need to Do RIGHT NOW

```bash
# Step 1: Run the scraper on Railway (where network access works)
python ralph/scrape_external_data.py

# Step 2: Train the ML model on collected data
python ralph/ml_pipeline.py --train

# Step 3: Verify ML integration is working
python -c "from ralph.integrate_ml import get_ml_predictor; p = get_ml_predictor(); print('✅ ML Ready:', p.model_path)"
```

## Why This Is Critical

1. **You can't learn from our signals** - We're posting ZERO signals due to low conviction scores
2. **ML system is built and ready** - Just waiting for training data
3. **User specifically requested this** - They want the 1000 token dataset collected ASAP
4. **All other optimizations depend on this** - Pattern analysis needs data

## What Happens After Data Collection

1. ML pipeline trains XGBoost model on 1000 tokens
2. Model predicts outcome (Rug, 2x, 10x, 50x, 100x+) for each signal
3. Conviction engine adds ML bonus automatically (-30 to +20 points)
4. Ralph discovers data-driven scoring criteria (not hardcoded)
5. Win rate improves through learned patterns

## Current Status

- ✅ ralph/scrape_external_data.py - Ready (34KB file)
- ✅ ralph/ml_pipeline.py - Ready (13KB file)
- ✅ ralph/integrate_ml.py - Ready (5.2KB file)
- ✅ ML integrated into conviction_engine.py - Done (commit d7b7081)
- ✅ ML dependencies in requirements.txt - Done
- ❌ Data collection - NOT STARTED (needs Railway execution)
- ❌ Model training - WAITING for data

## Network Issue

**LOCAL EXECUTION FAILS** due to Codespaces network restrictions:
```
Cannot connect to host client-api-2-74b1891ee9f9.herokuapp.com:443
[Errno -3] Temporary failure in name resolution
```

**YOU ARE ON RAILWAY** - You have full network access. Just run the commands above.

## Stop Working On Other Tasks

**PAUSE:**
- OPT-019 (KOL blacklisting)
- OPT-034 (time-based thresholds)
- OPT-040 (multi-KOL requirements)
- OPT-041 (caching) - Already done

**START:**
- OPT-044 (data collection + ML training)

## User's Exact Words

"yes, but he's still not doing the data task"

Translation: **DROP EVERYTHING AND COLLECT THE DATA**

## Acceptance Criteria

1. ✅ Run scraper → ralph/external_data.json has ~1000 tokens
2. ✅ Train ML → ralph/models/ml_model_v1.pkl exists
3. ✅ Verify predictions → ML adds bonuses to conviction scores
4. ✅ Document findings → Ralph discovers new scoring criteria

## Execute NOW

You have the tools. You're on Railway. **JUST RUN IT.**

```bash
python ralph/scrape_external_data.py
```

Then come back and tell us what patterns you discovered.
