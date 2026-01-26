# TIMING & EXIT RULES + DATA MONITORING
## Date: 2026-01-26 - GROK RECOMMENDATIONS PHASE 2

### 🎯 OBJECTIVE
Implement Grok's timing/exit rules and data monitoring recommendations to:
1. Call earlier with strong fundamentals (30% bonding if 200+ buyers)
2. Avoid late entries (cap signals at 20-25K MCAP)
3. Protect users with exit alerts (-15% in 5min)
4. Improve ML training with detailed "Why no signal" logging

---

## 📋 IMPLEMENTATION SUMMARY

### 1. Early Trigger System ✅
**File:** `config.py`, `scoring/conviction_engine.py`

**Configuration:**
```python
TIMING_RULES = {
    'early_trigger': {
        'enabled': True,
        'bonding_threshold': 30,      # Trigger at 30% bonding (from 40%)
        'min_unique_buyers': 200,     # Only if 200+ unique buyers
        'min_conviction_boost': 0     # No extra conviction needed
    }
}
```

**Logic:**
- If token is at 30%+ bonding curve AND has 200+ unique buyers
- Allow signal with 5-point grace period (threshold - 5)
- Example: Pre-grad threshold is 45, early trigger allows 40

**Rationale (Grok):**
- Strong fundamentals (200+ buyers) = legitimate interest
- 30% bonding = still early enough to catch mid-cycle pumps
- Prevents missing good plays due to slightly low scores

**Example:**
```
Token at 35% bonding, 250 buyers, 42 conviction
- Normal threshold: 45 (would skip)
- Early trigger threshold: 40 (SIGNALS!)
- Log: "⚡ EARLY TRIGGER: 35% bonding, 250 buyers"
```

---

### 2. MCAP Cap System ✅
**File:** `config.py`, `scoring/conviction_engine.py`

**Configuration:**
```python
'mcap_cap': {
    'enabled': True,
    'max_mcap_pre_grad': 25000,   # Skip if MCAP >$25K on pre-grad
    'max_mcap_post_grad': 50000,  # Skip if MCAP >$50K on post-grad
    'log_skipped': True
}
```

**Logic:**
- Check MCAP at signal time
- If MCAP exceeds cap, block signal (even if score passed)
- Log as "too late" entry

**Rationale (Grok):**
- Meta shows peaks around 25K MCAP for pump.fun
- Signaling above this = late entry, likely at top
- Protects users from FOMO buys at ATH

**Example:**
```
Token: 68 conviction, $28K MCAP
- Score passed threshold (45)
- But MCAP > $25K cap
- Result: SIGNAL BLOCKED
- Log: "🚫 MCAP CAP: $28,000 > $25,000 (too late, skipping signal)"
```

---

### 3. Post-Call Monitoring System ✅
**File:** `post_call_monitor.py` (NEW)

**Configuration:**
```python
'post_call_monitoring': {
    'enabled': True,
    'exit_alert_threshold': -15,  # Alert if -15% drop
    'monitoring_duration': 300,   # Monitor for 5 minutes
    'check_interval': 30,         # Check every 30 seconds
    'send_telegram_alert': True
}
```

**Features:**
- **Automatic monitoring** after signal sent
- **Price checks** every 30 seconds for 5 minutes
- **Exit alert** if price drops -15% or more
- **Telegram notification** to warn users

**Alert Format:**
```
🚨 EXIT ALERT 🚨

Token: $SHRIMP
Address: 7xKXt...gAsU

📉 Price dropped -18.5% in 2.3 minutes

💵 Signal price: $0.00012340
💵 Current price: $0.00010052

⚠️ Consider taking profits or exiting position

[View on DexScreener]
```

**Integration:**
```python
# After sending signal
monitor = get_post_call_monitor(dexscreener, telegram)
await monitor.start_monitoring(
    token_address=address,
    signal_price=price,
    token_symbol=symbol,
    signal_score=score
)
```

**Example Log:**
```
📊 Starting post-call monitoring: $SHRIMP @ $0.00012340
🔍 Monitoring $SHRIMP for 300s (exit alert at -15%)
📊 $SHRIMP check 1: +2.3% (30s elapsed)
📊 $SHRIMP check 2: -8.1% (60s elapsed)
🚨 EXIT ALERT: $SHRIMP
📉 Price dropped -18.5% in 135s
✅ Exit alert sent to Telegram
```

---

### 4. "Why No Signal" Logging System ✅
**File:** `config.py`, `scoring/conviction_engine.py`

**Configuration:**
```python
SIGNAL_LOGGING = {
    'log_why_no_signal': True,        # Enable detailed breakdown
    'log_score_components': True,     # Log all components
    'min_gap_to_log': 5,              # Only log if within 5 pts of threshold
    'save_to_database': True,         # Save to DB (future)
    'include_recommendations': True   # Include actionable recommendations
}
```

**Output Format:**
```
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
   ⚠️  WHY NO SIGNAL - Breakdown:
   📉 Gap to threshold: 7.0 points

   📊 Top opportunities for improvement:
      1. Smart Wallet: 0/40 pts (potential +40)
      2. Narrative: 0/25 pts (potential +25)
      3. Telegram Calls: 0/15 pts (potential +15)

   ⚠️  Penalties applied: RugCheck: -15, Bundle: -10

   💡 Recommendations:
      • Wait for KOL buys
      • No hot narrative match
      • Need more buyers (12 currently)

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
```

**Logged When:**
- Score is within 5 points of threshold (configurable)
- MCAP cap is triggered (always log late entries)
- User can analyze why tokens didn't signal

**Benefits:**
- **ML training:** Identify near-misses for model improvement
- **Strategy refinement:** See which components need work
- **Backtesting:** Understand historical missed signals
- **User transparency:** Clear reasons for no signal

**Components Analyzed:**
1. **Top opportunities** - which metrics could gain most points
2. **Penalties applied** - what's holding score down
3. **Recommendations** - actionable next steps (e.g., "Wait for KOL buys")

---

## 📊 COMPLETE FLOW EXAMPLE

### Example: Mid-Cycle Pump (SHRIMP-like)

**Token State:**
- Bonding: 35%
- Unique buyers: 220
- MCAP: $18,000
- Base score: 42
- Narrative: AI Agent (+20)

**Traditional Flow (would miss):**
```
Base: 42
Threshold: 45
Result: ❌ SKIP (missed by 3 points)
```

**With GROK Enhancements:**

**Step 1: Early Trigger Check**
```
✅ Bonding 35% >= 30% threshold
✅ Buyers 220 >= 200 minimum
✅ Score 42 >= 40 (early trigger threshold)
⚡ EARLY TRIGGER ACTIVATED!
```

**Step 2: MCAP Cap Check**
```
✅ MCAP $18K < $25K cap
✅ Not too late, proceed
```

**Step 3: Signal Sent**
```
✅ SIGNAL! (Score: 42, Early trigger applied)
📱 Posted to Telegram
📊 Starting post-call monitoring
```

**Step 4: Post-Call Monitoring**
```
🔍 Monitoring $SHRIMP for 5 minutes
📊 Check 1 (30s): +5.2%  ✅ Good
📊 Check 2 (60s): +12.8% ✅ Pumping
📊 Check 3 (90s): +8.1%  ✅ Still good
📊 Check 4 (120s): -2.3% ✅ Small dip
📊 Check 5 (150s): -18.5% 🚨 EXIT ALERT!
```

**Step 5: Exit Alert Sent**
```
🚨 EXIT ALERT: $SHRIMP
📉 Price dropped -18.5% in 2.5 minutes
📱 Telegram alert sent
✅ Users warned to exit
```

**Outcome:**
- ✅ Caught mid-cycle pump with early trigger
- ✅ Protected from late entry with MCAP cap
- ✅ Warned users of dump with exit alert
- ✅ Better win rate vs. traditional system

---

### Example: Late Entry Avoided

**Token State:**
- Bonding: 95%
- Unique buyers: 450
- MCAP: $32,000
- Score: 68

**Flow:**
```
✅ Score 68 >= 45 threshold
🚫 MCAP $32K > $25K cap
❌ SIGNAL BLOCKED (too late)

Log: "🚫 MCAP CAP: $32,000 > $25,000 (too late, skipping signal)"
```

**Outcome:**
- Avoided signaling at top
- Prevented late entry / bag holding

---

### Example: Near Miss with Logging

**Token State:**
- Bonding: 60%
- Unique buyers: 45
- MCAP: $15,000
- Score: 41

**Flow:**
```
❌ Score 41 < 45 threshold
📉 Gap: 4 points (within min_gap_to_log of 5)

⚠️  WHY NO SIGNAL - Breakdown:
📉 Gap to threshold: 4.0 points

📊 Top opportunities:
   1. Smart Wallet: 0/40 pts (potential +40)
   2. Unique Buyers: 8/15 pts (potential +7)
   3. Telegram Calls: 0/15 pts (potential +15)

⚠️  Penalties: RugCheck: -10

💡 Recommendations:
   • Wait for KOL buys
   • Need more buyers (45 currently, need 50 for +15)
   • No Telegram buzz yet
```

**Outcome:**
- Clear understanding why it didn't signal
- Actionable recommendations (wait for KOLs)
- Data saved for ML training

---

## 🎯 INTEGRATION POINTS

### Where to Integrate Post-Call Monitor

**Option 1: In `active_token_tracker.py` (after signal sent)**
```python
from post_call_monitor import get_post_call_monitor

# After posting signal to Telegram
if result['passed']:
    # Start monitoring
    monitor = get_post_call_monitor(
        dexscreener_fetcher=self.dexscreener,
        telegram_poster=self.telegram
    )
    await monitor.start_monitoring(
        token_address=token_address,
        signal_price=token_data['price'],
        token_symbol=token_data['token_symbol'],
        signal_score=result['score']
    )
```

**Option 2: In `main.py` (orchestrator)**
```python
# Initialize monitor at startup
monitor = get_post_call_monitor(dexscreener, telegram)

# After signal
if conviction_result['passed']:
    await monitor.start_monitoring(...)
```

**Option 3: In `conviction_engine.py` (automatic)**
```python
# At end of analyze_token()
if passed and config.TIMING_RULES['post_call_monitoring']['enabled']:
    # Return flag to start monitoring
    return {
        ...
        'start_monitoring': True,
        'signal_price': token_data['price']
    }
```

---

## 📊 EXPECTED IMPACT

### Call Volume & Quality
**Before:**
- **Early misses:** Good plays at 30-40% bonding
- **Late entries:** Signals at tops (25K+ MCAP)
- **No exit protection:** Users hold through dumps

**After:**
- **Catch mid-cycle:** Early trigger at 30% with 200+ buyers
- **Avoid tops:** MCAP cap blocks late entries
- **Exit alerts:** Users warned of -15% drops

### Data & ML Training
**Before:**
- No data on near-miss signals
- Unknown why tokens didn't signal
- Hard to backtest improvements

**After:**
- **Detailed logging** of all near-misses
- **Component breakdown** for analysis
- **Recommendations** for model tuning
- **Database ready** for backtesting

---

## 🔧 CONFIGURATION TUNING

### Adjust Early Trigger Sensitivity
```python
# More aggressive (catch more plays)
'bonding_threshold': 25,      # Lower bonding %
'min_unique_buyers': 150,     # Fewer buyers required

# More conservative (fewer signals)
'bonding_threshold': 40,      # Higher bonding %
'min_unique_buyers': 300,     # More buyers required
```

### Adjust MCAP Cap Levels
```python
# Based on meta analysis
'max_mcap_pre_grad': 20000,   # Stricter (earlier entry)
'max_mcap_post_grad': 100000, # More lenient (allow bigger plays)
```

### Adjust Exit Alert Threshold
```python
# More sensitive (earlier exits)
'exit_alert_threshold': -10,  # Alert at -10%

# Less sensitive (avoid false alarms)
'exit_alert_threshold': -20,  # Alert at -20%
```

### Adjust Logging Detail
```python
# Log everything
'min_gap_to_log': 20,         # Log if within 20 pts

# Only log very close misses
'min_gap_to_log': 2,          # Log if within 2 pts
```

---

## 🚀 DEPLOYMENT CHECKLIST

- [x] Add timing/exit rules to `config.py`
- [x] Update `conviction_engine.py` with early trigger logic
- [x] Update `conviction_engine.py` with MCAP cap check
- [x] Update `conviction_engine.py` with "Why no signal" logging
- [x] Create `post_call_monitor.py` module
- [ ] Integrate post-call monitor in main signal flow
- [ ] Add database logging for near-misses (optional)
- [ ] Test early trigger with mock data
- [ ] Test MCAP cap with high-MCAP tokens
- [ ] Test post-call monitoring with real signals
- [ ] Monitor for 1-2 days and tune thresholds

---

## 📝 NEXT STEPS (GROK PHASE 3)

### Backtesting & Validation
1. **Use Dune Analytics** - Export 100 recent grads
2. **Simulate scoring** - Run through conviction engine
3. **Validate thresholds** - Ensure 30% rug rate (not "most")
4. **Tune parameters** - Adjust based on backtest results

### Additional Enhancements
1. **Database integration** - Save near-misses for ML
2. **Exit strategy automation** - Auto-sell on -15%? (risky)
3. **Multi-timeframe monitoring** - Track 1h, 6h, 24h performance
4. **Win rate dashboard** - Visualize signal performance

---

## 📊 METRICS TO TRACK

### Signal Quality (Daily)
- Total signals sent
- Early triggers applied (%)
- MCAP caps triggered (%)
- Exit alerts sent (%)

### Performance (Weekly)
- Win rate (signals that pumped vs. dumped)
- Average gain at 5min, 1h, 6h, 24h
- Average loss on exit alerts
- Rug rate (confirmed rugs / total signals)

### Near-Misses (For ML)
- Tokens within 5 pts of threshold
- Most common missing components
- Correlation between near-miss score and actual performance

---

## 🎯 SUCCESS CRITERIA

**Phase 2 Goals:**
1. ✅ Catch mid-cycle pumps like SHRIMP (early trigger)
2. ✅ Avoid late entries at tops (MCAP cap)
3. ✅ Protect users from dumps (exit alerts)
4. ✅ Generate ML training data (logging)

**Target Metrics (After 1-2 Days):**
- Call volume: 5-10/day
- Win rate: 50%+ (up from current)
- Rug rate: <30% (down from "most")
- Exit alerts: 20-30% of signals (normal)

**Monitoring Period:**
- Deploy and monitor for 1-2 days
- Collect data on all new features
- Tune thresholds based on results
- Iterate to Phase 3 (backtesting)

---

## 🔧 TROUBLESHOOTING

### Early Trigger Not Activating
- Check: `TIMING_RULES['early_trigger']['enabled']`
- Check: Bonding % >= 30
- Check: Unique buyers >= 200
- Check: Score within 5 pts of threshold

### MCAP Cap Blocking Good Plays
- Increase: `max_mcap_pre_grad` to 30K or 35K
- Review: Historical data to find optimal cap
- Consider: Dynamic cap based on liquidity

### Exit Alerts Too Frequent
- Increase: `exit_alert_threshold` to -20%
- Increase: `monitoring_duration` to 10min
- Decrease: `check_interval` to 60s (fewer checks)

### Logging Too Verbose
- Increase: `min_gap_to_log` to 10 or 20
- Disable: `include_recommendations` if too chatty
- Filter: Only log pre-grad (skip post-grad)

---

**END OF DOCUMENT**
