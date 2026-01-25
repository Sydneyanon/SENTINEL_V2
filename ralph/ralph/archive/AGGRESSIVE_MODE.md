# RALPH AGGRESSIVE MODE - 75% Win Rate Target

## Overview

Ralph has been configured in **AGGRESSIVE MODE** with one singular goal:

**Achieve 75% win rate using ANY means necessary.**

## What Changed

### 1. New High-Priority Optimizations (27 total, up from 17)

**EMERGENCY TIER (Priority 0-1):**
- **OPT-000**: Kill all losing signal patterns immediately
  - Blacklist any KOL + narrative + holder pattern with <40% win rate
  - Prevents posting signals that consistently lose
  - Test time: 2 hours

- **OPT-019**: Auto-blacklist bad KOLs
  - Demote KOLs with <35% win rate or >60% rug rate
  - Move them to "watchlist" with 0 points
  - Test time: 24 hours

- **OPT-023**: Emergency stop for rug indicators
  - Block if: top 3 holders >80%, liquidity <$5k, no socials, token age <2min
  - Better to miss a winner than post a rug
  - Test time: 4 hours

**SPEED TIER (Priority 2-4):**
- **OPT-018**: Parallel A/B testing
  - Test 5 conviction thresholds (60, 65, 70, 75, 80) simultaneously
  - Find optimal in 1 hour instead of 10 hours
  - Deploy winner immediately

- **OPT-020**: Double down on proven winners
  - KOLs with >70% win rate get 2x points
  - KOLs with >80% win rate get 3x points
  - KOLs with <40% win rate get 0.5x points
  - Test time: 12 hours

- **OPT-021**: Narrative boost
  - 3x multiplier for narratives with 5+ wins in 48h
  - 0.5x penalty for narratives with 0 wins in 7 days
  - Test time: 6 hours

- **OPT-024**: Raise conviction floor to 75
  - Only post highest conviction signals
  - Target: >60% win rate with >3x avg ROI
  - Accept fewer signals if they win more
  - Test time: 3 hours

**ADVANCED TIER (Priority 5-7):**
- **OPT-022**: Timing optimization
  - Only post in top 3 time windows (by historical win rate)
  - Queue signals for optimal posting time
  - Test time: 24 hours

- **OPT-025**: XGBoost ML predictions
  - Only post signals with P(win) > 0.60
  - Add +20 conviction for P(win) > 0.75
  - Test time: 8 hours

- **OPT-026**: Copy best KOL exactly
  - Mirror the single highest-performing KOL
  - Instant signals (bypass conviction scoring)
  - Test time: 24 hours

### 2. Aggressive Decision Logic

**OLD (Conservative):**
- Keep if primary metric improved >10-15%
- Revert if any critical metric degraded >5%

**NEW (Aggressive):**
- Keep if win rate improved >5% (even if signal count drops)
- Keep if win rate >70% (regardless of other metrics)
- Keep if rug rate decreased >20%
- Revert ONLY if win rate dropped AND no improvement in rug/ROI

**Bias: Quality over Quantity**
- Favor win rate over signal count
- Accept posting 5 signals/day with 75% win rate instead of 20 signals/day with 50% win rate

### 3. Reduced Monitoring Times (For Speed)

**OLD:**
- Quick tests: 2 hours
- Complex tests: 4 hours

**NEW:**
- Quick tests: 1 hour minimum
- Risky tests: 2 hours minimum
- ML models: 4 hours minimum

**Rationale:** Iterate faster, test more variations

### 4. Comprehensive Logging

Ralph now tracks and logs:
- Win rate by KOL tier, narrative, time of day, holder pattern
- Per-wallet performance (win rate, avg ROI, rug rate)
- Detailed explanations of what worked and why
- Patterns discovered (e.g., "AI narrative wins 85% on Saturdays")
- Recommendations for next optimizations

**New Tool: `win_rate_dashboard.py`**
```bash
# See real-time performance
python ralph/win_rate_dashboard.py 24  # last 24 hours
```

Shows:
- Overall win rate, rug rate, avg ROI
- Performance by KOL tier
- Top performing narratives
- Top performing wallets
- Underperforming wallets (blacklist candidates)

### 5. Increased Iteration Count

**OLD:** 10 iterations
**NEW:** 30 iterations

Ralph will work through 27 optimizations comprehensively over ~60-90 hours.

## How Ralph Will Optimize

### Phase 1: Emergency Triage (First 8 hours)
1. **OPT-000**: Blacklist losing patterns (2h test)
2. **OPT-019**: Demote bad KOLs (24h test, but starts immediately)
3. **OPT-023**: Add rug red flag filters (4h test)

**Expected Result:** Win rate jumps from ~50% to ~60% by cutting dead weight

### Phase 2: Amplify Winners (Hours 8-24)
4. **OPT-020**: Double points for proven KOLs (12h test)
5. **OPT-021**: 3x narrative boost (6h test)
6. **OPT-024**: Raise conviction floor to 75 (3h test)

**Expected Result:** Win rate climbs from ~60% to ~68% by amplifying good signals

### Phase 3: Speed Testing (Hours 24-36)
7. **OPT-018**: Parallel A/B test 5 thresholds (1h test)
8. **OPT-001**: Deploy optimal threshold from OPT-018

**Expected Result:** Fine-tuned threshold, win rate ~70%

### Phase 4: Advanced Optimizations (Hours 36-90)
9. **OPT-025**: Add ML predictions (8h test)
10. **OPT-022**: Timing optimization (24h test)
11. **OPT-026**: Mirror best KOL (24h test)
12. Continue through remaining optimizations...

**Expected Result:** Win rate reaches 75%+ target

## Monitoring Ralph's Progress

### Check Win Rate Dashboard
```bash
cd /home/user/SENTINEL_V2
python ralph/win_rate_dashboard.py 24
```

### Check Ralph's Learnings
```bash
cat ralph/progress.txt
```

### Check Which Optimizations Passed
```bash
cat ralph/prd.json | grep -A3 '"id".*OPT' | grep -E 'id|passes'
```

### See Ralph's Commits
```bash
git log --author="Ralph" --oneline
```

### Railway Logs
Watch Ralph's decisions in real-time:
```
Ralph service → Logs
Look for: "RALPH'S RESPONSE" sections
```

## Expected Timeline

**Hour 0-8:** Emergency fixes (cut losing strategies)
**Hour 8-24:** Amplify winners (boost proven patterns)
**Hour 24-36:** Speed optimization (parallel testing)
**Hour 36-72:** Advanced optimizations (ML, timing, copying)
**Hour 72-90:** Remaining optimizations (wallet discovery, narratives, etc.)

**Target Achievement:** 75% win rate by hour 36-48

## What Makes This "Aggressive"

1. **Ruthless Cutting:** Immediately blacklist anything with <40% win rate
2. **Extreme Amplification:** 3x multipliers for winners
3. **Speed Over Safety:** 1-hour tests instead of 2-4 hours when safe
4. **Bias Toward Action:** When in doubt, keep changes
5. **Quality Over Quantity:** Accept fewer signals if they win more
6. **Comprehensive Testing:** 27 optimizations instead of 17
7. **No Sacred Cows:** Will cut even "elite" KOLs if they're losing

## Success Metrics

Ralph considers an optimization **successful** if ANY of these:
- Win rate improved >5%
- Win rate >70% (regardless of other metrics)
- Rug rate decreased >20%
- Avg ROI improved >25%

Ralph will **revert** only if ALL of these:
- Win rate dropped or stayed flat
- No improvement in rug rate or ROI
- Acceptance criteria failed

## How to Help Ralph

1. **Merge the PR:** Ralph needs these changes deployed
   https://github.com/Sydneyanon/SENTINEL_V2/compare/main...claude/get-ralph-running-3gc4s

2. **Let Railway rebuild:** Wait ~3 minutes for deployment

3. **Go to sleep:** Ralph works autonomously

4. **Check progress when you wake up:**
   ```bash
   python ralph/win_rate_dashboard.py 24
   cat ralph/progress.txt
   ```

## If Ralph Plateaus

If Ralph gets stuck at ~65-70% win rate:

1. **Check win_rate_dashboard.py:** See which KOLs/narratives are underperforming
2. **Manually blacklist:** Add bad wallets to a blacklist file
3. **Add custom optimizations:** Edit `ralph/prd.json` with new ideas
4. **Restart Ralph:** He'll pick up new optimizations automatically

## Final Note

Ralph is now configured to be **ruthless, fast, and data-driven**. He will:
- Cut losing strategies without hesitation
- Amplify winners aggressively
- Test variations rapidly
- Document everything comprehensively

**Goal: 75% win rate minimum**

Ralph is THE MAN for this job. Let him cook. 🔥

---

Created: 2026-01-23
Mode: AGGRESSIVE
Target: 75% win rate
Status: READY TO DEPLOY
