# Whale Tracking Implementation Plan

**Date**: 2026-01-25
**Status**: Planned (pending Moralis historical data collection)
**Priority**: Medium (after ML training)

---

## Concept

Track non-KOL whale wallets (>$50K positions) that accumulate tokens alongside KOL buys.

**Why**: Smart money (whales) often buy before KOLs call it publicly. Cross-validates KOL signals.

---

## Conviction Scoring Addition

**New Component**: Whale Accumulation (0-15 points)

```python
# In conviction_engine.py
async def _score_whale_activity(self, token_address: str) -> int:
    """
    Score based on whale accumulation (0-15 points)

    Whales = wallets with >$50K position in token
    Excludes tracked KOLs (already counted separately)
    """
    # Get token holders from Moralis
    holders = await moralis.get_token_holders(
        token_address,
        min_value_usd=50000  # $50K minimum
    )

    # Filter out our tracked KOLs
    whale_count = 0
    for holder in holders:
        if holder.address not in smart_wallet_tracker.tracked_wallets:
            whale_count += 1

    # Score based on whale count
    if whale_count >= 10:
        return 15  # Heavy whale accumulation
    elif whale_count >= 5:
        return 10  # Good whale interest
    elif whale_count >= 3:
        return 5   # Some whale activity
    else:
        return 0   # No significant whale activity
```

---

## Integration into Scoring

**Current BASE SCORE**: 123 points
**New BASE SCORE**: 138 points

```
Smart Wallet Activity (KOLs): 0-40 points
Narrative Detection: 0-25 points
Buy/Sell Ratio: 0-20 points
Whale Activity: 0-15 points  ← NEW
Volume Velocity: 0-10 points
Price Momentum: 0-10 points
Volume/Liquidity Velocity: 0-8 points
MCAP Penalty: -20 to 0 points
```

---

## Data Collection (Moralis)

### **Historical Analysis** (One-time):

```python
# For each known runner, find who bought early
for runner in known_successful_tokens:
    # Get holders at 1-hour mark
    early_holders = moralis.get_token_holders_at_time(
        token=runner,
        timestamp=launch + 1h,
        min_value=50000  # $50K minimum
    )

    # Identify whales (non-KOL)
    whales = [h for h in early_holders if h.address not in tracked_kols]

    # Save for ML training
    historical_data[runner]['whale_count_1h'] = len(whales)
    historical_data[runner]['whale_addresses'] = [w.address for w in whales]
```

---

## ML Training Feature

**Add to training dataset**:
```python
features = {
    'kol_count': 3,           # Existing
    'whale_count': 7,         # NEW
    'buy_percentage': 82.5,   # Existing
    'volume_velocity': 15.2,  # Existing
    # ... other features
}

# ML learns: "Tokens with 5+ whales + 3+ KOLs → 85% success rate"
```

---

## Cost Analysis (Moralis)

### **Historical Collection** (one-time):
```
Get holders for 150 tokens (at 1h mark each):
- 150 tokens × 3 CU = 450 CU
Total: ~450 CU (one-time)
```

### **Real-Time Usage** (per signal):
```
Option A: Check every token
- ~100 tokens/day × 3 CU = 300 CU/day
- Sustainable (40K/day free tier)

Option B: Check only high-conviction tokens (better)
- Only check if base score >40
- ~20 tokens/day × 3 CU = 60 CU/day
- Very light usage
```

**Recommendation**: Option B (check only promising tokens)

---

## Implementation Plan

### **Phase 1**: Historical Analysis (Week 1)
1. Collect holder data for 150 known runners
2. Identify whale patterns at 1h, 6h marks
3. Analyze correlation with outcomes
4. Add to ML training dataset

### **Phase 2**: ML Training (Week 2)
1. Train model with whale_count as feature
2. See if whales predict success
3. Determine optimal thresholds

### **Phase 3**: Real-Time Integration (Week 3+)
1. Add whale tracking to conviction engine
2. Only check tokens with base score >40
3. Add 0-15 points based on whale count
4. Monitor impact on signal quality

---

## Alternative: Whale Copying Strategy

**More Advanced Use**:

Instead of just counting whales, **copy their moves**:

```python
# Weekly: Identify whales who consistently win
successful_whales = analyze_whale_win_rates()

# Real-time: See what they're buying NOW
for whale in successful_whales:
    current_holdings = moralis.get_wallet_tokens(whale)
    recent_buys = [t for t in current_holdings if t.acquired_within_24h]

    # Start tracking these tokens (whale-triggered signals)
    for token in recent_buys:
        if not already_tracking(token):
            start_tracking(token, source='whale_copy')
            conviction += 10  # Whale copy bonus
```

**Benefit**: Find tokens BEFORE KOLs call them!

---

## Expected Impact

### **Conviction Score**:
- Tokens with 10+ whales: +15 points (could push borderline signals over threshold)
- Tokens with 0 whales: +0 points (no impact)

### **Signal Quality**:
- Cross-validates KOL buys
- Filters out fake KOL pumps (no whales = suspicious)
- Identifies true smart money plays

### **Discovery**:
- Whale copying finds tokens early
- Beat KOLs to the punch
- Lower entry prices

---

## Integration with Current System

**Fits naturally into existing flow**:

```python
# In conviction_engine.py analyze_token()

# ... existing checks ...

# After base score calculated:
if base_score >= 40:  # Only check promising tokens
    whale_score = await self._score_whale_activity(token_address)
    base_scores['whale_activity'] = whale_score
    logger.info(f"   🐋 Whale Activity: {whale_score}/15 points")
else:
    logger.info(f"   🐋 Whale Activity: SKIPPED (base score too low)")
```

---

## Next Steps

**After Moralis historical collection**:
1. Analyze whale patterns in successful vs failed tokens
2. Determine if whales are predictive
3. If yes (>70% correlation) → implement real-time tracking
4. If no (<50% correlation) → skip this feature

**Data decides!**

---

## Bottom Line

**Whale tracking = Smart addition, but not critical**

**Priority**:
1. Train ML model first (existing data ready)
2. Collect Moralis historical data
3. See if whales predict success
4. Then decide whether to implement

**Don't build it until data proves it's valuable!**
