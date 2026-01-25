# Runner Token Analysis
**Date**: 2026-01-25
**Tokens Analyzed**: 4 major Solana runners
**Data Source**: ralph/runner_data.json (DexScreener discovery)

---

## Executive Summary

Analyzed 4 confirmed "runner" tokens that achieved 100x-1000x gains:
- **MOODENG**: 1,137x gain ($68.2M MCAP)
- **GOAT**: 535x gain ($32M MCAP)
- **ACT**: 367x gain ($22M MCAP)
- **ZEREBRO**: 200x gain ($12M MCAP)

**Key Finding**: Current data only has post-success metrics. We need **early signal data** (when tokens first appeared) to train ML models.

---

## Token Profiles

### 1. MOODENG (Moo Deng) - The Mega Runner
**Performance**: 1,137x gain
**Current MCAP**: $68.2M
**Address**: `ED5nyyWEzpPPiWimP8vYm7sD7TD3LAt3Q3gRTWHzPJBY`

**Current Metrics**:
- Price: $0.06889
- Liquidity: $3.6M
- Volume 24h: $127,936
- Volume/Liquidity Ratio: **3.5%** (LOW - mature token)
- Created: Sept 10, 2024

**Pattern**: Established token with deep liquidity but low volume ratio (distribution phase).

---

### 2. GOAT (Goatseus Maximus) - AI Narrative
**Performance**: 535x gain
**Current MCAP**: $32M
**Address**: `CzLSujWBLFsSjncfkh59rUFqvafWcY5tzedWJSuypump`

**Current Metrics**:
- Price: $0.03207
- Liquidity: $2.2M
- Volume 24h: $70,896
- Volume/Liquidity Ratio: **3.2%** (LOW)
- Created: Oct 10, 2024

**Pattern**: Another mature token in distribution. AI-themed (likely had strong narrative during pump).

---

### 3. ACT (Act I: The AI Prophecy) - AI Trend
**Performance**: 367x gain
**Current MCAP**: $22M
**Address**: `GJAFwWjJ3vnTsrQVabjBVK2TYB1YtRCQXRDfDgUnpump`

**Current Metrics**:
- Price: $0.02319
- Liquidity: $2.2M
- Volume 24h: $82,369
- Volume/Liquidity Ratio: **3.7%** (LOW)
- Created: Oct 19, 2024

**Pattern**: AI narrative token (note "AI Prophecy" in name). Similar distribution metrics to GOAT.

---

### 4. ZEREBRO (zerebro) - Recent Runner
**Performance**: 200x gain
**Current MCAP**: $12M
**Address**: `8x5VqbHA8D7NkD52uNuS5nnt3PwA8pLD34ymskeSo2Wn`

**Current Metrics**:
- Price: $0.01197
- Liquidity: $1.7M
- Volume 24h: $290,272
- Volume/Liquidity Ratio: **17.4%** (HIGHEST - still active?)
- Created: Oct 28, 2024

**Pattern**: Newest runner with notably higher volume ratio. Possibly still has momentum.

---

## Common Patterns (Current State)

### Volume/Liquidity Ratios
| Token | V/L Ratio | Status |
|-------|-----------|--------|
| MOODENG | 3.5% | Mature/distributed |
| GOAT | 3.2% | Mature/distributed |
| ACT | 3.7% | Mature/distributed |
| ZEREBRO | 17.4% | ⚡ Still active |

**Insight**: Mature runners settle at 3-4% volume/liquidity. ZEREBRO's 17% suggests it may still be pumping.

### Liquidity vs Market Cap
| Token | MCAP | Liquidity | MCAP/Liquidity |
|-------|------|-----------|----------------|
| MOODENG | $68M | $3.6M | 19x |
| GOAT | $32M | $2.2M | 14.5x |
| ACT | $22M | $2.2M | 10x |
| ZEREBRO | $12M | $1.7M | 7x |

**Insight**: Successful runners maintain 10-20x MCAP/Liquidity ratio. Lower ratio = healthier (less risk of rug).

### Narrative Analysis
- **AI Theme**: 3/4 tokens (GOAT, ACT, ZEREBRO) have AI-related names/narratives
- **Meme**: MOODENG is pure meme (hippo character)
- **Timing**: All launched Oct-Nov 2024 (AI narrative peak on Solana)

---

## Critical Data Gap

### What We Have
✅ Post-success metrics (current state)
✅ Final MCAs and gain multiples
✅ Current liquidity/volume

### What We Need (Missing!)
❌ **Early signal data** - metrics when first detected
❌ Holder concentration at launch
❌ Smart wallet activity (KOLs who bought early)
❌ Initial volume velocity
❌ Price momentum in first 1-6 hours
❌ Social signals (Twitter/Telegram mentions)

**Problem**: The runner_data.json has `"early_signal": {}` - empty for all tokens!

This means we **CANNOT** train ML models yet because we don't know:
- What these tokens looked like when they were $60K MCAP
- Which scoring components would have caught them early
- Whether our current thresholds would pass/fail them

---

## What Our Current System Would Do

### Current Scoring Weights (config.py)
```
BASE SCORE (0-85):
- Smart Wallet Activity: 0-15 points
- Narrative Detection: 0-20 points
- Volume Velocity: 0-20 points
- Price Momentum: 0-30 points

MID SCORE (0-100):
- Unique Buyers (FREE): +15 if >30 buyers

EXPENSIVE (10 credits):
- Holder Concentration: 0-40 points

THRESHOLD: 75 conviction score
```

### Would We Have Caught These?

**Unknown** - because we don't have early data. But we can infer:

1. **AI tokens (GOAT, ACT, ZEREBRO)**:
   - Likely scored high on Narrative Detection (+20 if "AI" present)
   - If KOLs bought early → Smart Wallet Activity (+15)
   - **Estimated base score**: 35-55/85
   - Would need strong volume/price momentum to hit 75

2. **MOODENG** (meme):
   - No AI narrative → 0 narrative points
   - Would need exceptional volume/momentum or KOL activity
   - **Higher risk of being missed** without strong fundamentals

---

## Recommendations

### Immediate: Collect Early Signal Data

**Option 1: Historical Backfill** (Best)
Use DexScreener API to fetch historical data for these 4 tokens:
```bash
GET https://api.dexscreener.com/latest/dex/tokens/{address}
```

Look for:
- Initial liquidity pools (when they started)
- Volume patterns in first 24 hours
- Price changes hour-by-hour

**Option 2: Prospective Collection** (Easier)
Start collecting data NOW for new tokens:
1. When bot detects a token, save full snapshot to database
2. Track outcome over 7 days
3. After 100+ tokens, train ML model

**Option 3: Use Database Signals** (Fastest)
Check production database - it should already have signal data!
```sql
SELECT * FROM signals WHERE signal_posted = TRUE
```

Each signal has:
- `conviction_score` (what we predicted)
- `entry_price`, `liquidity`, `volume_24h`
- Can track outcomes to see if we were right

### ML System Status

**✅ Code exists**:
- `database.py` - PostgreSQL schema with outcome tracking
- `ralph/ml_pipeline.py` - XGBoost training pipeline
- `ralph/integrate_ml.py` - Conviction score integration

**❌ Not initialized**:
- No trained models (`ralph/models/` doesn't exist)
- No training data (`external_data.json` has 0 tokens)
- Database likely has data but needs analysis

**🔧 To Start ML**:

**Step 1**: Export existing signal data from database
```bash
# Check if database has data
railway run --service prometheusbot-production \
  psql $DATABASE_URL -c "SELECT COUNT(*) FROM signals WHERE signal_posted = TRUE;"

# Export to CSV for analysis
railway run --service prometheusbot-production \
  psql $DATABASE_URL -c "COPY signals TO STDOUT CSV HEADER" > signals_export.csv
```

**Step 2**: Collect outcomes for existing signals
- Track which tokens 2x, 10x, or rugged
- Need 50-100 signals with known outcomes to train

**Step 3**: Train initial model
```bash
cd ralph
python ml_pipeline.py --train
```

**Step 4**: Enable ML predictions in conviction engine
```python
# In scoring/conviction_engine.py
from ralph.integrate_ml import get_ml_predictor

ml_result = get_ml_predictor().predict_for_signal(token_data, kol_count)
final_score += ml_result['ml_bonus']  # Add ML boost
```

---

## Next Tasks Priority

### 1. **Check Production Database** (5 minutes)
See if we already have 50+ signals with data we can analyze.

### 2. **Analyze Existing Signals** (1 hour)
If database has signals, export and analyze:
- How many signals sent?
- What was their conviction score distribution?
- Can we manually tag outcomes (rug/2x/10x)?

### 3. **Decide Training Strategy** (15 minutes)
- If database has <50 signals → collect more data first
- If database has 50+ signals → start training

### 4. **Train First Model** (30 minutes)
Once we have 50+ tokens with outcomes, train XGBoost model.

### 5. **Deploy ML Predictions** (1 hour)
Integrate ML bonus into conviction scoring.

---

## Can Claude Do This?

**Yes**, I can do all of this:

✅ **Query database** - I can run psql commands via Railway CLI
✅ **Export and analyze signal data** - Read CSV, analyze patterns
✅ **Train ML model** - Run `python ml_pipeline.py --train`
✅ **Integrate into code** - Modify conviction_engine.py to use ML
✅ **Test predictions** - Verify ML bonuses make sense

**Cannot do (requires human)**:
❌ Manually label outcomes (which tokens rugged vs succeeded)
❌ Set DATABASE_URL if not already configured in Railway

---

## Bottom Line

**Runner Analysis**: Limited by lack of early signal data. Current data only shows post-success state (not useful for ML).

**ML System**: Fully coded and ready, but needs training data.

**Immediate Path Forward**:
1. **Check database** - see if we already have 50+ signals
2. **If yes** → export, label outcomes, train model (I can do this)
3. **If no** → need to collect 50-100 more signals first

**Your decision**: Should I proceed to check the database and attempt to train the ML model?
