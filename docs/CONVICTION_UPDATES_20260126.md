# Conviction Scoring Updates - January 26, 2026

## Changes Made

### 1. Removed Twitter & LunarCrush Scoring ❌

**Reason:** No budget for API access

**Impact:**
- Lost 0-15 points (Twitter buzz)
- Lost 0-20 points (LunarCrush social sentiment)
- Total lost: 0-35 points

**Files changed:**
- `config.py`: Set `ENABLE_TWITTER = False`, `ENABLE_LUNARCRUSH = False`
- `scoring/conviction_engine.py`: Commented out Twitter/LunarCrush imports and scoring logic

### 2. Lowered Conviction Thresholds 📉

**Reason:** Compensate for removed scoring (35 pts lost)

**Changes:**
```python
# Before
MIN_CONVICTION_SCORE = 50
POST_GRAD_THRESHOLD = 50

# After
MIN_CONVICTION_SCORE = 35  # -30% reduction
POST_GRAD_THRESHOLD = 40   # -20% reduction
```

**Impact:**
- Maintains similar signal volume despite API removals
- Allows more data collection for ML training
- Goal: 50-100 tokens/day for training dataset

### 3. Updated Scoring Documentation 📝

**New max score:** ~110 points (down from ~145)

**Current breakdown:**
- Smart Wallet Activity: 0-40 pts
- Narrative Detection: 0-25 pts
- Buy/Sell Ratio: 0-20 pts
- Unique Buyers: 0-15 pts
- Volume Velocity: 0-10 pts
- Price Momentum: 0-10 pts
- Telegram Calls: 0-20 pts
- Bundle Penalty: -40 to 0 pts
- Holder Concentration: -40 to +30 pts
- RugCheck: -40 to 0 pts
- ML Prediction: -30 to +20 pts

**Total possible:** 0-130 points (with bonuses)

## Data Analysis Findings 🔬

See `docs/DATA_ANALYSIS_RECOMMENDATIONS.md` for full analysis.

### Key Insights from 21 Collected Tokens:

#### ❌ Pattern 1: High Buy Pressure ≠ Winners
```
Small winners:     57.5% avg buy pressure
Big winners (50x+): 52.6% avg buy pressure
```
**Finding:** Big winners have LOWER buy pressure than small wins!
**Implication:** Current buy/sell scoring may be inverted

#### ❌ Pattern 2: High Vol/Liq = Bad Signal
```
Small winners:     21.8x vol/liq ratio
Big winners:       0.04-0.08x vol/liq ratio
```
**Finding:** High volume/liquidity ratio indicates PnD, not sustainable growth
**Implication:** Need to penalize high vol/liq ratios

#### ✅ Pattern 3: Deep Liquidity Matters
```
Big winners: $2M-$7M liquidity pools
Small wins:  $50K-$120K liquidity pools
```
**Finding:** Sustainable winners have deep liquidity
**Implication:** Should score liquidity depth (currently missing)

#### ✅ Pattern 4: Early Entry Critical
```
Small winners:   $0.33M avg MCAP (when collected)
Big winners:     $50M-$500M avg MCAP (when collected)
```
**Finding:** We're catching big winners too late (after they 100x)
**Implication:** Need early MCAP bonus to catch tokens <$1M

#### ❌ Pattern 5: More Txns ≠ Better
```
Small winners:    7,715 avg buys/24h
Big winners:      286-658 avg buys/24h
```
**Finding:** High transaction count = retail FOMO (late entry)
**Implication:** Should penalize excessive transactions

## Recommended Future Improvements 🚀

### High Priority (Data-Driven)

1. **Invert Buy/Sell Ratio Scoring**
   - Current: 70%+ buy = max points
   - Recommended: 48-58% balanced = max points
   - Data shows: Extreme buy pressure = PnD behavior

2. **Add Volume/Liquidity Penalty**
   - Penalize vol/liq > 10x (shallow dumping)
   - Reward vol/liq < 0.5x (deep liquidity)

3. **Add Liquidity Depth Scoring**
   - $1M+ pool: +20 pts
   - $500K+ pool: +15 pts
   - $100K+ pool: +5 pts
   - <$100K pool: -10 pts (too risky)

4. **Add Early MCAP Bonus**
   - <$100K MCAP: +20 pts (very early)
   - <$500K MCAP: +15 pts (early)
   - <$1M MCAP: +10 pts (good entry)
   - >$5M MCAP: 0 pts (already ran)

5. **Add Transaction Count Penalty**
   - <500 buys/24h: +15 pts (whale accumulation)
   - 5000+ buys/24h: -10 pts (retail FOMO)

### Impact Estimate

**Current state:**
- Max score: ~110 pts
- Threshold: 35-40 pts
- Win rate: Unknown (insufficient data)

**After improvements:**
- Max score: ~155 pts (added new signals)
- Threshold: May need adjustment after testing
- Win rate: Expected +10-20% improvement

### Implementation Timeline

1. **Immediate** ✅ - Remove Twitter/LunarCrush, lower thresholds
2. **Week 1** - Collect 200+ tokens with new thresholds
3. **Week 2** - Analyze win rate, validate threshold adjustment
4. **Week 3** - Implement data-driven improvements (inverted buy pressure, liq scoring)
5. **Week 4** - Retrain ML with 1000+ tokens

## Testing Plan 📊

1. Deploy threshold changes to production
2. Monitor signal volume for 24-48 hours
3. Target: 5-10 signals/day minimum
4. If too many signals: Raise threshold to 40-45
5. If too few signals: Lower threshold to 30-35
6. Collect 200 tokens minimum for first ML model

## Expected Outcomes 🎯

### Short-term (Week 1)
- Signal volume increases to 5-10/day
- ML dataset grows to 200+ tokens
- First production ML model trained

### Medium-term (Weeks 2-4)
- 1000+ tokens collected
- Data-driven improvements implemented
- Win rate measurably improves

### Long-term (Months 2-3)
- 5000+ tokens in training set
- ML accuracy reaches 75-80%
- Win rate improvement of +15-20%

## Migration Notes ⚠️

**Breaking changes:** None
**Backward compatibility:** Full
**Rollback plan:** Revert thresholds to 50/50 if signal volume too high

**Monitoring:**
- Track daily signal count
- Track conviction score distribution
- Track outcome distribution (after 24h)
- Adjust thresholds as needed

---

**Summary:** Removed expensive APIs, lowered thresholds, identified critical scoring improvements from data analysis. The conviction engine is now budget-friendly and ready to collect data for ML training.
