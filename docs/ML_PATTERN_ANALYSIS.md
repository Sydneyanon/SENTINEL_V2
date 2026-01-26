# ML Pattern Analysis - Predicting Biggest Gains

## Overview

This document explains how SENTINEL's ML system analyzes patterns to predict which tokens will achieve the biggest gains (10x, 50x, 100x+).

## Current ML Architecture

### Model: XGBoost Multi-Class Classifier

**Output Classes (5):**
- Class 0: Rug/Fail (< 2x)
- Class 1: Small win (2x - 10x)
- Class 2: Medium win (10x - 50x)
- Class 3: Big win (50x - 100x)
- Class 4: Mega win (100x+)

**Training Method:**
- 80/20 train/test split with stratification
- Features: 45+ engineered signals
- Validation: Classification report, accuracy, feature importance
- Retraining: Automatic when 50+ new tokens collected

### Feature Categories (45+ Features)

#### 1. **KOL & Smart Money Signals**
- `kol_count`: Number of tracked KOLs buying
- `new_wallet_count`: New wallets detected
- Early whale entry timing
- KOL tier distribution (S, A, B, C tiers)

#### 2. **Holder Distribution**
- `holder_count`: Total unique holders
- `top_10_concentration`: % held by top 10 wallets
- `top_3_concentration`: % held by top 3 wallets
- `decentralization_score`: Distribution quality (0-100)

#### 3. **Volume & Liquidity Dynamics**
- `volume_24h`, `volume_6h`, `volume_1h`: Multi-timeframe volume
- `liquidity_usd`: Pool depth
- `volume_to_liquidity`: Velocity ratio
- `liquidity_base`, `liquidity_quote`: Pool reserves
- `reserve_ratio`: Balance between token/SOL

#### 4. **Buy Pressure & Momentum**
- `buys_24h`, `sells_24h`: Transaction counts
- `buy_pressure_1h`, `buy_pressure_6h`: Recent buying intensity
- `price_change_24h`, `price_change_6h`, `price_change_1h`: Multi-timeframe momentum
- Buy/sell ratio patterns

#### 5. **Security & Risk Metrics**
- `rugcheck_score`: Onchain security analysis
- `is_rugged`: Historical rug detection
- `is_honeypot`: Contract exploit check
- `risk_level`: Composite risk score
- Bundle detection (coordinated buys)

#### 6. **Social & Narrative Signals**
- `has_website`, `has_twitter`, `has_telegram`: Platform presence
- `social_count`: Total social platforms
- Narrative matching (AI, meme, utility, etc.)
- Telegram call frequency & intensity

#### 7. **Timing & Market Context**
- `created_at`: Token age
- Time to bonding curve graduation
- Market conditions at signal time
- Bonding velocity (speed to $1M MCAP)

#### 8. **Conviction Engine Output**
- `conviction_score`: Our multi-factor score (0-145+)
- `signal_source`: Origin (KOL_buy, telegram_call, whale_buy)
- Individual component scores

## Pattern Analysis: What Predicts Big Gains?

### Hypotheses to Test

Based on 21 initial tokens (14 small, 3 x10, 2 x50, 2 x100+), we're testing:

#### **Pattern 1: Early KOL + Low Holder Concentration**
```
IF kol_count >= 2
AND top_10_concentration < 30%
AND created_at < 2 hours ago
THEN higher probability of 10x+
```

**Logic:** Multiple KOLs buying early + distributed holders = organic growth potential

#### **Pattern 2: High Volume Velocity + Strong Buy Pressure**
```
IF volume_to_liquidity > 5.0
AND buy_pressure_6h > 65%
AND price_change_6h > 100%
THEN higher probability of 50x+
```

**Logic:** Massive buying volume relative to pool size = "they're dumping on liquidity"

#### **Pattern 3: Social Verification + Narrative Match**
```
IF social_count >= 3
AND has_telegram == true
AND narrative_match (AI, meme, or trending)
AND rugcheck_score > 60
THEN higher probability of 10x+
```

**Logic:** Legit social presence + trending narrative = sustained community growth

#### **Pattern 4: Whale Accumulation + Low MCAP**
```
IF whale_count >= 3
AND market_cap < $500K
AND top_3_concentration BETWEEN 15% AND 35%
AND early_whale_entry == true
THEN higher probability of 100x+
```

**Logic:** Smart money accumulating at low MCAP = they see something big

#### **Pattern 5: Multi-Call Convergence**
```
IF telegram_calls >= 3
AND different_telegram_groups >= 2
AND conviction_score > 70
AND bonding_velocity > 0.8
THEN higher probability of 50x+
```

**Logic:** Multiple independent groups calling = decentralized discovery of alpha

### Feature Importance Analysis

Once we have 200+ tokens, XGBoost will reveal **actual** feature importance:

```python
# Example output (hypothetical)
Feature Importance (Top 10):
1. conviction_score        0.18  (18% importance)
2. buy_pressure_6h         0.14
3. kol_count               0.12
4. top_10_concentration    0.11
5. volume_to_liquidity     0.09
6. social_count            0.08
7. rugcheck_score          0.07
8. whale_count             0.06
9. telegram_calls          0.05
10. price_change_6h        0.04
```

This tells us which signals **actually matter** for predicting outcomes.

### Correlation Analysis

We'll identify feature correlations:

```python
# Positive correlations with 100x outcomes:
- kol_count + social_count (0.72) → Legitimacy signal
- whale_count + early_entry (0.81) → Smart money signal
- buy_pressure_6h + volume_velocity (0.65) → Momentum signal

# Negative correlations with 100x outcomes:
- top_3_concentration + is_rugged (0.89) → Rug risk
- bundle_detected + low_social_count (0.76) → Scam pattern
- high_sell_pressure_1h + no_telegram (0.68) → Dead launch
```

## How Pattern Analysis Works

### 1. **Data Collection Phase** (Current: 21 tokens → Target: 1000+ tokens)

```
Daily Collection (Midnight UTC):
├─ DexScreener: 50 tokens/day that did 2x+ yesterday
├─ Production Signals: 10-20 tokens/day from our own signals
└─ Historical Scraping: 150 tokens/week from pump.fun graduates

Timeline to 200 tokens: ~2-3 days
Timeline to 1000 tokens: ~15-20 days
Timeline to 5000 tokens: ~80-100 days
```

### 2. **Feature Engineering Phase**

For each token, we extract 45+ features at **signal time** (not outcome time):

```python
# Example: Token detected at $50K MCAP
{
  "token_address": "ABC123...",
  "signal_time_mcap": 50000,      # When we detected it
  "signal_time_price": 0.00005,
  "outcome_mcap": 5000000,        # 24h later (100x)
  "outcome_price": 0.005,

  # Features at SIGNAL time (what we knew BEFORE it pumped):
  "kol_count": 3,                 # 3 KOLs bought early
  "whale_count": 5,               # 5 whales accumulated
  "top_10_concentration": 22%,    # Good distribution
  "buy_pressure_6h": 73%,         # Strong buying
  "volume_to_liquidity": 8.2,     # High velocity
  "social_count": 4,              # Twitter + Telegram + Website + Discord
  "conviction_score": 82,         # Our score
  "rugcheck_score": 71,           # Passed security

  # LABEL (what we're predicting):
  "outcome": "100x+"              # This is what we want to predict!
}
```

### 3. **Pattern Discovery Phase**

XGBoost trains by finding **decision tree patterns**:

```
Example Decision Tree (Simplified):

                    [Root: All Tokens]
                            |
              Is conviction_score > 70?
             /                          \
          YES                            NO
           |                              |
    Is kol_count >= 2?             Is buy_pressure > 80%?
      /           \                  /              \
    YES           NO               YES              NO
     |             |                |                |
  10x+ (80%)   2x+ (60%)        10x+ (50%)      Rug (70%)

Pattern learned:
- High conviction + KOLs → 80% chance of 10x+
- High conviction + No KOLs → 60% chance of 2x+
- Low conviction + High buy pressure → 50% chance of 10x+ (momentum play)
- Low conviction + Low buy pressure → 70% chance of rug
```

### 4. **Prediction Phase** (Real-time)

When a new token is detected:

```python
# New token detected
token = {
  "kol_count": 4,
  "conviction_score": 88,
  "buy_pressure_6h": 71%,
  "whale_count": 6,
  # ... 40+ other features
}

# ML model predicts
prediction = model.predict(token)
# Output: Class 4 (100x+) with 73% confidence

# Conviction engine uses this
ml_bonus = calculate_ml_bonus(prediction, confidence)
# Output: +18 points to conviction score

final_conviction = base_score + ml_bonus
# Output: 88 + 18 = 106 (MEGA signal!)
```

### 5. **Continuous Learning Phase**

```
Daily Cycle:
1. Collect 50 tokens from yesterday (known outcomes)
2. Extract features at signal time
3. Append to training dataset
4. Retrain model if 50+ new tokens
5. Deploy new model
6. Use improved model for today's predictions
7. Track performance
8. Repeat

Result: Model gets smarter every day
```

## Expected Performance Improvements

### Current State (21 tokens, not enough data):
- Model accuracy: Unknown (insufficient data)
- Feature importance: Unknown
- Pattern detection: Minimal

### After 200 tokens (Week 1):
- Model accuracy: ~60-65% (baseline)
- Feature importance: Top 10 features identified
- Pattern detection: Basic patterns emerge
- Conviction boost: +5-10% win rate

### After 1000 tokens (Week 3-4):
- Model accuracy: ~70-75%
- Feature importance: Refined, actionable insights
- Pattern detection: Complex multi-feature patterns
- Conviction boost: +10-15% win rate

### After 5000 tokens (Month 3-4):
- Model accuracy: ~78-82%
- Feature importance: Highly optimized
- Pattern detection: Sophisticated edge cases
- Conviction boost: +15-20% win rate

## Key Insights We'll Discover

With enough data, we'll definitively answer:

### 1. **What makes a 100x token?**
```
Example: We might find that 100x tokens have:
- 80% have kol_count >= 3
- 75% have social_count >= 4
- 90% have top_10_concentration < 25%
- 85% have conviction_score > 75
- 70% have whale_count >= 4
- 95% have rugcheck_score > 60
```

### 2. **What are the red flags for rugs?**
```
Example: Rugs typically have:
- 90% have top_3_concentration > 40%
- 80% have social_count <= 1
- 75% have bundle_detected == true
- 85% have kol_count == 0
- 70% have conviction_score < 30
```

### 3. **Which signals are noise vs alpha?**
```
Example: Signal value ranking:
1. KOL buying (18% importance) → ALPHA
2. Whale accumulation (14%) → ALPHA
3. Buy pressure (12%) → ALPHA
4. Token name length (0.2%) → NOISE
5. Time of day created (0.1%) → NOISE
```

### 4. **What's the optimal entry timing?**
```
Example: We might find:
- Tokens called at <$100K MCAP → 10x average return
- Tokens called at $100K-$500K → 5x average return
- Tokens called at >$1M MCAP → 2x average return

→ Optimize conviction threshold to catch tokens earlier
```

## Integration with Conviction Engine

The ML predictions enhance our conviction scoring:

```python
# Conviction Scoring with ML
base_conviction = calculate_base_conviction(token)  # 0-125 pts
ml_prediction = ml_model.predict(token)             # Class 0-4
ml_confidence = ml_model.predict_proba(token)       # 0-1

# ML Bonus Calculation
if ml_prediction == 4 (100x+):
    if ml_confidence > 0.7:
        ml_bonus = +20 pts
    elif ml_confidence > 0.5:
        ml_bonus = +15 pts
    else:
        ml_bonus = +10 pts

elif ml_prediction == 3 (50x):
    ml_bonus = +10 to +15 pts (confidence-weighted)

elif ml_prediction == 2 (10x):
    ml_bonus = +5 to +10 pts

elif ml_prediction == 1 (2x):
    ml_bonus = 0 pts (neutral)

elif ml_prediction == 0 (rug):
    ml_bonus = -30 pts (WARNING)

final_conviction = base_conviction + ml_bonus
```

**Result:** ML acts as a **pattern-recognition multiplier** on top of our rule-based conviction engine.

## Monitoring & Validation

We track ML performance continuously:

```python
# Daily ML Performance Report
{
  "date": "2026-02-01",
  "predictions_made": 47,
  "outcomes_known": 35,
  "accuracy": 0.74,
  "precision_by_class": {
    "rug": 0.82,
    "2x": 0.71,
    "10x": 0.68,
    "50x": 0.65,
    "100x+": 0.59
  },
  "feature_drift": {
    "kol_count": "stable",
    "buy_pressure": "increasing",
    "social_count": "stable"
  },
  "recommended_actions": [
    "Retrain: 50+ new tokens available",
    "Adjust: Lower 100x+ confidence threshold"
  ]
}
```

## Future Enhancements

### Phase 1: Advanced Feature Engineering (Month 2-3)
- Sentiment analysis on Telegram/Twitter
- Transaction graph analysis (wallet relationships)
- Historical pattern matching (similar tokens)
- Macro market conditions (SOL price, overall volume)

### Phase 2: Ensemble Models (Month 3-4)
- XGBoost + Random Forest + Neural Network
- Vote averaging for higher confidence
- Specialized models per outcome class

### Phase 3: Reinforcement Learning (Month 6+)
- Model learns from posting performance
- Adjusts conviction thresholds based on outcomes
- Optimizes for ROI, not just accuracy

## Conclusion

**Pattern analysis works by:**

1. **Collecting massive datasets** (1000s of tokens with outcomes)
2. **Engineering predictive features** (45+ signals at detection time)
3. **Training ML models** (XGBoost finds patterns humans can't see)
4. **Making predictions** (New tokens → Model → Outcome probability)
5. **Continuous learning** (Daily retraining with new data)
6. **Integration** (ML predictions boost conviction scores)
7. **Validation** (Track accuracy, precision, drift)

**The more data we collect, the smarter the system gets.**

With 5000+ tokens over 3-4 months, we'll have a **world-class pattern recognition system** that can identify 100x tokens with high confidence before they pump.

---

**Current Status:**
- ✅ ML infrastructure built
- ✅ 45+ features engineered
- ✅ XGBoost pipeline ready
- ✅ Automated retraining configured
- ⏳ Collecting data (21/200 minimum)
- ⏳ Pattern discovery pending (need 200+ tokens)

**Timeline:**
- Week 1: Reach 200 tokens → Train first production model
- Week 3-4: Reach 1000 tokens → Robust pattern detection
- Month 3-4: Reach 5000 tokens → Production-grade predictions
