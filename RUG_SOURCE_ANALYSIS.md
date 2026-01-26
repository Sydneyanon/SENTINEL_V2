# 🚨 Rug Source Analysis - Identify Where Rugs Are Coming From

## Problem Statement

You're experiencing a high number of rugs and need to identify the source:
- Are rugs coming from **KOL wallet buys**?
- Are rugs coming from **Telegram group calls**?
- Are rugs coming from **whale tracking** or other sources?

This feature adds **source tracking** and **comprehensive analytics** to answer these questions.

---

## 🔍 What We Implemented

### 1. Signal Source Tracking (Database Enhancement)

**New Column**: `signal_source` in `signals` table
- Tracks where each signal originated from
- Values: `'kol_buy'`, `'telegram_call'`, `'whale_buy'`, `'unknown'`
- Automatically populated when signals are created

**Files Modified**:
- `database.py`: Added `signal_source` column migration
- `database.py`: Updated `insert_signal()` to store source
- `active_token_tracker.py`: Pass `state.source` when inserting signals

### 2. Rug Analysis Tool

**New Script**: `analyze_rug_sources.py`
- Comprehensive analytics broken down by signal source
- Identifies which sources are producing rugs
- Provides actionable recommendations

---

## 📊 How to Use the Analysis Tool

### Basic Usage

Run the analysis for the last 7 days (default):
```bash
python analyze_rug_sources.py
```

### Custom Time Period

Analyze the last 30 days:
```bash
python analyze_rug_sources.py --days 30
```

Analyze the last 24 hours:
```bash
python analyze_rug_sources.py --days 1
```

---

## 📈 What the Report Shows

### Section 1: Signal Breakdown by Source
Shows total signals, posted count, and average conviction by source.

**Example Output**:
```
Source               | Total    | Posted   | Has Outcome  | Avg Conviction
---------------------------------------------------------------------------------------
kol_buy              | 45       | 32       | 28           | 62.3
telegram_call        | 23       | 18       | 15           | 55.1
unknown              | 5        | 3        | 2            | 48.0
```

**What to look for**:
- Are most signals coming from one source?
- Which source has higher conviction scores?

### Section 2: Outcome Breakdown by Source
Shows how many 2x, 5x, rugs, etc. from each source.

**Example Output**:
```
KOL_BUY:
  rug            :  12 signals (avg ROI:   -80.0%)
  loss           :   5 signals (avg ROI:   -30.0%)
  2x             :   8 signals (avg ROI:   120.0%)
  5x             :   3 signals (avg ROI:   400.0%)

TELEGRAM_CALL:
  rug            :   9 signals (avg ROI:   -85.0%)
  2x             :   4 signals (avg ROI:   115.0%)
  10x            :   2 signals (avg ROI:   850.0%)
```

**What to look for**:
- Which source produces more rugs in absolute numbers?
- Which source has better winning outcomes?

### Section 3: Rug Rate Analysis by Source 🔥 MOST IMPORTANT

Shows rug percentage and win percentage for each source.

**Example Output**:
```
Source               | Total   | Rugs   | Wins   | Losses  | Rug Rate   | Win Rate
---------------------------------------------------------------------------------------
telegram_call        | 15      | 9      | 4      | 2       | 60.0%      | 26.7%     🚨
kol_buy              | 28      | 12     | 11     | 5       | 42.9%      | 39.3%     ⚠️
whale_buy            | 8       | 1      | 6      | 1       | 12.5%      | 75.0%

OVERALL: 22 rugs out of 51 signals (43.1% rug rate)
🚨 WORST SOURCE: telegram_call (60.0% rug rate, 9 rugs)
✅ BEST SOURCE: whale_buy (12.5% rug rate, 1 rug)
```

**What to look for**:
- **Rug Rate > 50%** 🚨 = CRITICAL - This source is producing mostly rugs
- **Rug Rate 30-50%** ⚠️ = WARNING - Needs improvement
- **Rug Rate < 20% + Win Rate > 40%** ✅ = EXCELLENT - This source is performing well

### Section 4: Recent Rugs (Last 20)
Lists the most recent rugs with their source and details.

**Example Output**:
```
Date         | Source          | Symbol     | Conv  | Max ROI  | Address
---------------------------------------------------------------------------------------
2026-01-26   | telegram_call   | SCAM       | 58    | -95.0%   | GDfn8x...
2026-01-25   | kol_buy         | FAKE       | 65    | -80.0%   | 7Htn2p...
2026-01-25   | telegram_call   | RUG        | 52    | -100.0%  | 4Bmq9k...
```

**What to look for**:
- Are recent rugs clustered around one source?
- Do rugs have high conviction scores (indicating scoring issues)?

### Section 5: Correlation Analysis
Shows tokens that had BOTH telegram calls AND KOL activity.

**Example Output**:
```
Symbol     | Source          | Outcome    | TG Groups  | TG Calls   | Conviction
---------------------------------------------------------------------------------------
TOKEN1     | kol_buy         | 5x         | 3          | 5          | 72
TOKEN2     | telegram_call   | rug        | 4          | 8          | 68
TOKEN3     | kol_buy         | 2x         | 2          | 3          | 61
```

**What to look for**:
- Do tokens with both KOL + TG calls perform better?
- Are rugs associated with specific patterns (e.g., many TG calls but no KOL follow-through)?

### Section 6: Actionable Insights 💡
Automated recommendations based on the data.

**Example Recommendations**:
```
🚨 CRITICAL: 'telegram_call' source has 60.0% rug rate!
   Recommendation: Consider disabling or reducing weight for this source
   Or add stricter rug detection filters for telegram_call signals

✅ EXCELLENT: 'kol_buy' source has only 12.5% rug rate with 75.0% win rate
   Recommendation: Consider increasing weight or conviction bonus for this source
```

---

## 🛠️ What to Do Based on Results

### If Telegram Calls Have High Rug Rate

**Option 1: Stricter Filters**
Edit `scoring/conviction_engine.py` to increase rug detection for telegram-sourced signals:
```python
if state.source == 'telegram_call':
    # Apply stricter rug checks
    if holder_concentration_penalty > -20:  # More strict
        logger.info("⚠️  TG call: High holder concentration - skipping")
        return None
```

**Option 2: Reduce Telegram Call Bonus**
Edit `scoring/conviction_engine.py` (Phase 3.7):
```python
# Reduce telegram scoring
if mention_count >= 6 or group_count >= 3:
    social_confirmation_score = 10  # Was 15
elif mention_count >= 3:
    social_confirmation_score = 5   # Was 10
```

**Option 3: Disable Low-Quality Groups**
Edit `config.py` to remove groups with poor track record from `TELEGRAM_GROUPS` list.

**Option 4: Require KOL Confirmation**
Only post telegram signals if a KOL also bought:
```python
if state.source == 'telegram_call' and state.kol_buy_count == 0:
    logger.info("⏳ TG call waiting for KOL confirmation")
    return None  # Skip posting until KOL buys
```

### If KOL Buys Have High Rug Rate

**Option 1: Review KOL List**
Some KOLs may be performing poorly. Check individual KOL performance:
```sql
SELECT
    wallet_name,
    COUNT(*) as total_signals,
    SUM(CASE WHEN outcome = 'rug' THEN 1 ELSE 0 END) as rugs,
    ROUND(100.0 * SUM(CASE WHEN outcome = 'rug' THEN 1 ELSE 0 END) / COUNT(*), 2) as rug_rate
FROM smart_wallet_activity swa
JOIN signals s ON swa.token_address = s.token_address
WHERE s.outcome IS NOT NULL
GROUP BY wallet_name
ORDER BY rug_rate DESC;
```

**Option 2: Increase Conviction Threshold**
Edit `config.py`:
```python
MIN_CONVICTION_SCORE = 60  # Increase from 50
```

**Option 3: Strengthen Rug Detection**
The rug detector may need tuning. Check `rug_detector.py` and `rugcheck_api.py`.

### If Both Sources Have High Rug Rates

**Likely Causes**:
1. **Market Conditions** - Bear market = more rugs everywhere
2. **Rug Detection Too Lenient** - Need stricter filters
3. **Missing Signals** - Outcome tracking may be incomplete

**Actions**:
1. Verify outcome tracking is working: `SELECT COUNT(*) FROM signals WHERE outcome IS NOT NULL;`
2. Review recent rugs manually to identify common patterns
3. Consider pausing new signals until rug detection is improved

---

## 📊 Tracking Outcomes

For the analysis to work, outcomes must be tracked. There are two ways:

### 1. Automatic Outcome Tracking (Future Enhancement)
Not yet implemented, but would involve:
- Background job monitoring token prices
- Auto-marking as rug if liquidity pulled
- Auto-marking milestones (2x, 5x, etc.)

### 2. Manual Outcome Tracking (Current Method)
Use the existing `add_manual_outcome.py` script:

```bash
# Mark a token as rug
python add_manual_outcome.py <token_address> <symbol> rug 0

# Mark a successful 10x
python add_manual_outcome.py <token_address> <symbol> 10x 900

# Mark a 2x
python add_manual_outcome.py <token_address> <symbol> 2x 100
```

**Batch Update Example**:
```bash
# Review your signals
SELECT token_address, token_symbol FROM signals WHERE signal_posted = TRUE AND outcome IS NULL;

# Then manually track outcomes for each
python add_manual_outcome.py GDfn8x... SCAM rug 0
python add_manual_outcome.py 7Htn2p... MOON 5x 400
```

---

## 🔄 Continuous Monitoring

### Daily Workflow

1. **Morning**: Check if signals posted overnight
   ```bash
   python check_signal_flow.py
   ```

2. **Afternoon**: Update outcomes for yesterday's signals
   ```bash
   # Check each posted signal and mark outcome
   python add_manual_outcome.py <address> <symbol> <outcome> <roi>
   ```

3. **Weekly**: Run rug source analysis
   ```bash
   python analyze_rug_sources.py --days 7
   ```

4. **Monthly**: Deep analysis and strategy adjustment
   ```bash
   python analyze_rug_sources.py --days 30
   # Review recommendations and adjust config/scoring
   ```

---

## 🎯 Success Metrics

### Healthy Signal Distribution
- **Rug Rate**: < 30% overall
- **Win Rate**: > 40% (2x or better)
- **Loss Rate**: < 30% (small losses, stop-loss working)

### Source Performance Targets
- **Best Source**: < 20% rug rate, > 50% win rate
- **Good Source**: < 30% rug rate, > 40% win rate
- **Warning Source**: 30-50% rug rate - needs improvement
- **Critical Source**: > 50% rug rate - disable or fix immediately

---

## 🔧 Files Modified

1. **database.py**
   - Added `signal_source` column to signals table
   - Updated `insert_signal()` to accept and store source

2. **active_token_tracker.py**
   - Modified to pass `state.source` when inserting signals
   - Source is already tracked in `TokenState` dataclass

3. **analyze_rug_sources.py** (NEW)
   - Comprehensive rug analysis tool
   - 6 analysis sections with actionable insights

4. **RUG_SOURCE_ANALYSIS.md** (NEW)
   - This documentation file

---

## 📞 Example Session

```bash
# Step 1: Run the analysis
$ python analyze_rug_sources.py --days 7

# Output shows:
# telegram_call: 65% rug rate (13 rugs out of 20 signals) 🚨
# kol_buy: 28% rug rate (7 rugs out of 25 signals) ⚠️

# Step 2: Take action - Reduce telegram call weight
$ nano scoring/conviction_engine.py
# Reduce telegram_call scoring from 15 to 10 max

# Step 3: Review problematic Telegram groups
$ nano config.py
# Remove or disable low-performing groups

# Step 4: Deploy changes
$ git add .
$ git commit -m "Reduce telegram call weight based on rug analysis"
$ git push

# Step 5: Monitor for improvement
# Wait 3-7 days, then re-run analysis
$ python analyze_rug_sources.py --days 7
# Check if telegram_call rug rate improved
```

---

## ✅ Summary

**What You Can Now Do**:
- ✅ Track where every signal comes from (kol_buy vs telegram_call)
- ✅ Analyze rug rates by source
- ✅ Identify problem sources with data
- ✅ Get automated recommendations
- ✅ Make data-driven decisions to reduce rugs

**Next Steps**:
1. Deploy this update to Railway
2. Let it run for 7 days to collect source data
3. Manually track outcomes for signals
4. Run `python analyze_rug_sources.py` after 7 days
5. Adjust strategy based on results

**Future Enhancements**:
- Auto outcome tracking via price monitoring
- Real-time source performance dashboard
- Per-group rug rate tracking
- Auto-disable sources above rug threshold
- ML model to predict rugs by source patterns

---

**Status**: ✅ Ready for deployment
**Breaking Changes**: None (backwards compatible)
**Database Migration**: Automatic on startup
