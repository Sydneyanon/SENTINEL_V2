# OPT-013: LunarCrush Social Sentiment Integration

## Objective
Test if adding LunarCrush social sentiment data improves signal quality and ROI.

## Hypothesis
Tokens that are trending on X/Twitter (via LunarCrush) with bullish sentiment will have better performance than non-trending tokens.

## Implementation

### Current Setup
LunarCrush integration is **already implemented** in `scoring/conviction_engine.py` and enabled via `config.ENABLE_LUNARCRUSH = True`.

### Scoring Logic
```python
# Bonus points (0-20):
- Trending rank <=20: +10 pts
- Trending rank <=50: +7 pts
- Trending rank <=100: +3 pts
- Sentiment >= 4.0: +5 pts
- Sentiment >= 3.5: +3 pts
- Social volume growth >= 100%: +5 pts
- Social volume growth >= 50%: +3 pts
```

### Test Variables
Ralph will test different configurations:

**A. Scoring Thresholds:**
1. Current: Trending top 20 = +10, top 50 = +7, top 100 = +3
2. Stricter: Top 10 = +15, top 30 = +10, ignore below
3. Looser: Top 50 = +10, top 150 = +5

**B. Sentiment Thresholds:**
1. Current: >= 4.0 = +5, >= 3.5 = +3
2. Stricter: >= 4.5 = +10, >= 4.0 = +5
3. Remove sentiment entirely (trending only)

**C. Enable/Disable:**
- Test with ENABLE_LUNARCRUSH = True vs False
- Measure impact on signal count and quality

## Acceptance Criteria

### Success Metrics
1. **Signal Quality Improvement**
   - Signals with LunarCrush bonus perform 15%+ better than baseline
   - Fewer rugs in trending tokens (< 10% rug rate)

2. **ROI Improvement**
   - Average ROI across all signals improves by 20%+
   - Tokens with "Trending Top 20" tag average 3x+ within 24h

3. **False Positive Reduction**
   - Tokens WITHOUT social buzz but high conviction score underperform
   - LunarCrush helps filter out low-quality signals

### Failure Metrics
1. No statistically significant improvement in ROI
2. Trending tokens underperform non-trending tokens
3. API costs/rate limits become problematic

## Test Plan

### Phase 1: Baseline (7 days)
- Run bot with `ENABLE_LUNARCRUSH = False`
- Collect performance data on all signals
- Calculate average ROI, rug rate, hit rate

### Phase 2: LunarCrush Enabled (7 days)
- Enable `ENABLE_LUNARCRUSH = True`
- Track which signals get LunarCrush bonus
- Compare performance of:
  - Signals WITH LunarCrush bonus
  - Signals WITHOUT LunarCrush bonus
  - Baseline signals from Phase 1

### Phase 3: Threshold Optimization (7 days)
- Test stricter trending thresholds
- Test different sentiment weights
- Find optimal configuration

### Phase 4: Exit Signal Testing (7 days)
- Implement exit signals when:
  - Sentiment drops below 3.0
  - Social volume drops >30% in 1 hour
  - Trending rank drops out of top 100
- Measure if early exits improve overall ROI

## Metrics to Track

### Signal-Level Metrics
```sql
-- Track LunarCrush data for each signal
CREATE TABLE lunarcrush_signal_data (
    signal_id INT,
    token_address TEXT,
    galaxy_score REAL,
    trending_rank INT,
    sentiment REAL,
    social_volume INT,
    social_volume_24h_change REAL,
    lunarcrush_bonus INT,  -- Points added
    created_at TIMESTAMP
);
```

### Performance Comparison
```python
# Compare groups:
1. Baseline (no LunarCrush)
2. LunarCrush bonus 0 (token not trending)
3. LunarCrush bonus 1-5 (weak trend)
4. LunarCrush bonus 6-10 (moderate trend)
5. LunarCrush bonus 11+ (strong trend)

# For each group, measure:
- Average max ROI (24h)
- Rug rate
- Hit rate (>2x)
- Average time to 2x
```

## Implementation Steps

### 1. Database Schema Update
```python
# Add to database.py
await conn.execute('''
    ALTER TABLE signals
    ADD COLUMN IF NOT EXISTS lunarcrush_bonus INT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS trending_rank INT,
    ADD COLUMN IF NOT EXISTS sentiment REAL,
    ADD COLUMN IF NOT EXISTS galaxy_score REAL
''')
```

### 2. Save LunarCrush Data
Update `publishers/telegram.py` to save social data:
```python
if result.get('social_data'):
    await db.update_signal_social_data(
        signal_id=signal_id,
        lunarcrush_bonus=result['breakdown']['social_sentiment'],
        trending_rank=result['social_data'].get('trending_rank'),
        sentiment=result['social_data'].get('sentiment'),
        galaxy_score=result['social_data'].get('galaxy_score')
    )
```

### 3. Ralph Analysis Script
```python
# ralph/analyze_lunarcrush.py
async def analyze_lunarcrush_impact():
    # Query all signals from last 7 days
    signals = await db.fetch_signals(days=7)

    # Group by LunarCrush bonus level
    groups = {
        'baseline': [],
        'no_bonus': [],
        'weak_trend': [],
        'moderate_trend': [],
        'strong_trend': []
    }

    for signal in signals:
        bonus = signal['lunarcrush_bonus']
        if signal['baseline_period']:
            groups['baseline'].append(signal)
        elif bonus == 0:
            groups['no_bonus'].append(signal)
        elif bonus <= 5:
            groups['weak_trend'].append(signal)
        elif bonus <= 10:
            groups['moderate_trend'].append(signal)
        else:
            groups['strong_trend'].append(signal)

    # Calculate metrics for each group
    for group_name, group_signals in groups.items():
        avg_roi = calculate_avg_roi(group_signals)
        rug_rate = calculate_rug_rate(group_signals)
        hit_rate = calculate_hit_rate(group_signals, threshold=2.0)

        print(f"{group_name}:")
        print(f"  Signals: {len(group_signals)}")
        print(f"  Avg ROI: {avg_roi:.2f}x")
        print(f"  Rug Rate: {rug_rate:.1f}%")
        print(f"  Hit Rate (2x): {hit_rate:.1f}%")
```

## Expected Outcomes

### Best Case
- Trending tokens average 5x+ ROI
- Rug rate drops from 15% to <5%
- Signal confidence improves dramatically
- Clear correlation: trending rank ↔ performance

### Worst Case
- No correlation between trending and performance
- Social data is lagging indicator (not predictive)
- API costs outweigh benefits
- Decision: Disable LunarCrush, revert changes

### Most Likely
- Moderate improvement (20-30% better ROI)
- Trending helps validate high-conviction signals
- Non-trending tokens with KOL buys still valuable
- Optimal: Use as tiebreaker, not primary signal

## Rollback Plan

If LunarCrush underperforms:
1. Set `ENABLE_LUNARCRUSH = False` in config.py
2. Remove social_sentiment from conviction scoring
3. Keep lunarcrush_fetcher.py for future experiments
4. Document findings in ralph/progress.txt

## API Costs

LunarCrush Free Tier:
- 1000 requests/day
- 30k requests/month

Expected Usage:
- ~50 signals/day × 1 request each = 50 requests/day
- Well under free tier limit

Caching:
- 30-minute cache on social metrics
- Reduces API calls for repeated checks

## Next Steps After Testing

If successful:
1. **Exit Signals:** Use sentiment cooling as exit trigger
2. **Narrative Detection:** Auto-detect hot narratives from trending topics
3. **Influencer Tracking:** Track which X accounts are pumping tokens
4. **Sentiment Alerts:** Alert when sentiment spikes on existing holdings

## Notes

LunarCrush data includes:
- Galaxy Score (proprietary metric)
- Alt Rank (overall ranking)
- Sentiment (1-5 scale)
- Social volume (mentions/posts)
- Social contributors (unique posters)
- Social dominance (% of crypto chatter)
- Price correlation (social → price)

Useful for:
- Validating KOL buys with social proof
- Detecting FOMO waves early
- Identifying when hype is dying (exit signal)
- Cross-referencing narratives
