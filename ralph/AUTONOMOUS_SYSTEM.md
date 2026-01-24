# Ralph Autonomous System

Complete autonomous optimization and learning system for Prometheus bot.

## 🤖 What It Does

Ralph now operates **100% autonomously**:

1. **Makes optimizations** - Changes code to improve win rate
2. **Deploys changes** - Pushes to Railway automatically
3. **Monitors results** - Checks metrics every 4 hours
4. **Makes decisions** - Auto-KEEP or auto-REVERT based on data
5. **Learns continuously** - Retrains ML models weekly on new data
6. **Notifies you** - Keeps you informed of all decisions

## 📊 Components

### 1. deployment_tracker.py
**Tracks all of Ralph's deployments**

```python
# When Ralph makes a change
tracker.track_deployment(
    optimization_id="OPT-041",
    monitor_duration_hours=6,
    acceptance_criteria={"credits_reduced": ">40%"},
    baseline_metrics={"credits_per_signal": 50}
)
```

Stores:
- What changed
- When to check results
- What defines success
- Baseline to compare against

### 2. auto_monitor.py
**Runs every 4 hours to check completed monitoring windows**

```bash
# Run manually
python ralph/auto_monitor.py

# Or via cron (every 4 hours)
0 */4 * * * cd /app && python ralph/auto_monitor.py
```

For each completed monitoring window:
1. Collects current metrics from database
2. Compares to baseline
3. Evaluates acceptance criteria
4. Makes KEEP or REVERT decision
5. Records decision with reason

### 3. ml_pipeline.py
**ML training and prediction system**

```bash
# Train on collected data
python ralph/ml_pipeline.py --train

# Retrain on fresh data (runs weekly)
python ralph/ml_pipeline.py --retrain

# Test predictions
python ralph/ml_pipeline.py --test
```

**Features extracted:**
- KOL count and involvement
- Holder concentration (top 10%, top 3%)
- Volume/liquidity ratios
- Security scores (RugCheck)
- Price momentum
- Token age

**Predicts:**
- Outcome class: Rug, 2x, 10x, 50x, 100x+
- Win probability (0-1)
- Adds conviction bonus: -30 to +20 points

### 4. integrate_ml.py
**Adds ML predictions to conviction engine**

```python
from ralph.integrate_ml import get_ml_predictor

predictor = get_ml_predictor()
ml_result = predictor.predict_for_signal(token_data, kol_count=3)

# ml_result = {
#     'prediction_class': 2,       # 10x
#     'class_name': '10x',
#     'confidence': 0.78,          # 78% confident
#     'ml_bonus': +10,             # Add 10 conviction points
#     'ml_enabled': True
# }
```

## 🚀 Setup Instructions

### 1. Install ML Dependencies

```bash
pip install xgboost scikit-learn
```

Add to `requirements.txt`:
```
xgboost==2.0.3
scikit-learn==1.4.0
```

### 2. Setup Cron on Railway

Add to Railway environment or use a scheduler service:

```bash
# Every 4 hours: Check monitoring windows
0 */4 * * * cd /app && python ralph/auto_monitor.py >> /app/logs/monitor.log 2>&1

# Every Sunday at midnight: Retrain ML models
0 0 * * 0 cd /app && python ralph/ml_pipeline.py --retrain >> /app/logs/ml_retrain.log 2>&1
```

**Alternative: Use Railway's built-in cron** (if available)

Or deploy a separate "scheduler" service that runs these commands.

### 3. Integrate ML into Conviction Engine

Edit `scoring/conviction_engine.py`:

```python
from ralph.integrate_ml import get_ml_predictor

class ConvictionEngine:
    def __init__(self, ...):
        # ... existing code ...

        # Add ML predictor
        self.ml_predictor = get_ml_predictor()

    async def analyze_token(self, token_address: str, token_data: Dict, ...):
        # ... existing scoring code ...

        # Add ML prediction
        ml_result = self.ml_predictor.predict_for_signal(
            token_data,
            kol_count=len(smart_wallets)
        )

        if ml_result['ml_enabled']:
            logger.info(f"   🤖 ML Prediction: {ml_result['class_name']} "
                       f"({ml_result['confidence']*100:.0f}% confident)")
            logger.info(f"      Conviction bonus: {ml_result['ml_bonus']:+d} points")

            # Add to score
            final_score += ml_result['ml_bonus']
```

### 4. First ML Training

After Ralph collects 1000 tokens:

```bash
# Train initial model
python ralph/ml_pipeline.py --train

# Test it works
python ralph/ml_pipeline.py --test
```

### 5. Enable Auto-Monitoring

Ralph will automatically track deployments when he makes changes.

The auto-monitor will check every 4 hours and make decisions.

You'll see in logs:
```
🎯 DECISION: KEEP
📝 Reason:
✅ Credits reduced 42.3% (target: >40%)
✅ Win rate improved 8.2% (target: >5%)
```

## 📈 Workflow Example

### Day 1: Ralph Makes Optimization
```
1. Ralph: "Implementing OPT-041 - Reduce Helius calls"
2. Ralph: Increases cache TTL from 60min → 120min
3. Ralph: git commit && git push
4. deployment_tracker: Records deployment, monitor for 6 hours
```

### Day 1, 6 hours later: Auto-Monitor Checks
```
1. auto_monitor: "OPT-041 monitoring window complete"
2. auto_monitor: Collects last 6 hours of metrics
3. auto_monitor: Baseline credits/signal = 50, Current = 29
4. auto_monitor: Credits reduced 42% > 40% target ✅
5. auto_monitor: DECISION = KEEP
6. deployment_tracker: Records decision
7. Ralph PRD: Updates OPT-041 to passes=true
```

### Week 1: ML Retraining
```
1. auto_monitor (Sunday): "Time to retrain ML models"
2. ml_pipeline: Scrapes 500 new graduated tokens
3. ml_pipeline: Retrains on 1500 total tokens (1000 + 500 new)
4. ml_pipeline: Evaluates: Accuracy improved 73% → 76%
5. ml_pipeline: Saves updated model
6. Next signals: Use new model with better predictions
```

## 🎯 Benefits

### For You
- ✅ **No manual intervention** - Ralph optimizes autonomously
- ✅ **Data-driven decisions** - Metrics determine KEEP/REVERT
- ✅ **Continuous learning** - ML improves every week
- ✅ **Full transparency** - All decisions logged with reasons
- ✅ **Faster iteration** - Check every 4 hours vs manually

### For The Bot
- ✅ **Better signals** - ML predicts winners before posting
- ✅ **Adaptive** - Learns from new market patterns
- ✅ **Optimized costs** - Auto-reduces Helius usage
- ✅ **Higher win rate** - Continuous optimization toward 75%

## 🔧 Monitoring

### Check Deployment Status
```bash
python -c "
from ralph.deployment_tracker import DeploymentTracker
tracker = DeploymentTracker()
active = tracker.get_active_deployments()
print(f'{len(active)} deployments being monitored')
for d in active:
    print(f'  {d[\"optimization_id\"]} - check at {d[\"check_at\"]}')
"
```

### Check Recent Decisions
```bash
python -c "
from ralph.deployment_tracker import DeploymentTracker
tracker = DeploymentTracker()
history = tracker.get_deployment_history(limit=5)
for d in history:
    print(f'{d[\"optimization_id\"]}: {d[\"status\"]} - {d.get(\"decision_reason\", \"monitoring\")}')
"
```

### Force Check Now
```bash
# Don't wait for cron - check immediately
python ralph/auto_monitor.py
```

## 📝 Logs

All autonomous actions are logged:

- `ralph/deployments.json` - All tracked deployments
- `ralph/models/` - Trained ML models + metadata
- `ralph/external_data.json` - Collected token data
- Railway logs - Auto-monitor decisions

## 🚨 Manual Override

If you need to override Ralph's decision:

```python
from ralph.deployment_tracker import DeploymentTracker

tracker = DeploymentTracker()

# Force a different decision
tracker.record_decision(
    optimization_id="OPT-041",
    decision="revert",  # or "keep"
    reason="Manual override - observed issue X",
    final_metrics={}
)
```

## 🎓 Future Enhancements

- [ ] Telegram notifications for all decisions
- [ ] Web dashboard to view all deployments
- [ ] A/B testing framework (test 2 configs simultaneously)
- [ ] Auto-rollback on critical failures
- [ ] Predictive scheduling (deploy during low-traffic hours)
- [ ] Meta-learning (Ralph learns how to optimize better)

---

**Result:** Ralph is now a fully autonomous agent that optimizes, monitors, learns, and improves the bot 24/7 without human intervention! 🤖🚀
