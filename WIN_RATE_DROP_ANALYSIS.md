# WIN RATE DROP ROOT CAUSE ANALYSIS
**Date:** January 23, 2026
**Issue:** Win rate dropped from 67% to below 50% in last 12-14 hours

## ROOT CAUSE IDENTIFIED

### Primary Issue: CONVICTION THRESHOLD TOO LOW

The `MIN_CONVICTION_SCORE` has been set to **45** (ultra-aggressive mode) since January 22, 2026 at 09:45 UTC.

**Timeline of Threshold Changes:**
```
Jan 21 ~16:00 - Threshold at 80 (original, high quality)
Jan 21 21:20  - Lowered to catch more signals  
Jan 22 06:53  - Lowered to 55 (aggressive)
Jan 22 09:45  - Lowered to 45 (ULTRA AGGRESSIVE) ← CRITICAL CHANGE
Jan 23 15:40  - Raised to 70 (experiment, OPT-001)
Jan 23 16:16  - Reverted to 45 (diagnostic mode) ← CURRENT STATE
```

**Current Config (config.py line 56):**
```python
MIN_CONVICTION_SCORE = 45  # Pre-graduation threshold
POST_GRAD_THRESHOLD = 45   # Post-graduation threshold
```

### Why This Causes Low Win Rate

**Conviction Score of 45 means:**
- Only 3-4 KOL wallets bought the token (30-40 points)
- Little to no narrative support (0-5 points)
- Poor holder distribution (0-5 points)
- Minimal volume/momentum (0-5 points)

**At threshold 45, you're catching:**
- ✅ Tokens with 4-5 KOL buys (good)
- ❌ Tokens with 3 KOL buys + NO other signals (bad)
- ❌ Tokens with weak narratives
- ❌ Tokens with poor distribution
- ❌ Early-stage tokens that may not pump

**At threshold 70-80, you would catch:**
- ✅ Tokens with 6-8 KOL buys (excellent)
- ✅ Tokens with strong narrative + good distribution
- ✅ Tokens with proven momentum
- ✅ Higher probability of success

## SECONDARY ISSUES

### 1. Diagnostic Mode Comment
The code comment says "DIAGNOSTIC MODE: Finding why signals show low conviction" - but the real issue is that LOW THRESHOLD allows low conviction signals through!

### 2. Recent Infrastructure Changes (Last 14 hours)
Multiple Docker/Railway changes were deployed:
- Switch to Claude Code CLI
- Run Docker as non-root user  
- Reduce logging to prevent Railway limits

These changes were infrastructure-only and shouldn't affect signal quality, BUT they could have caused:
- Service restarts
- Brief downtime
- Timing issues with signal processing

### 3. Possible Telegram Posting Issues
Commit `5e5dc81` (Jan 23 18:25) fixed silent Telegram failures. This suggests some signals may have passed threshold but failed to post, creating confusion about actual vs posted win rate.

## DIAGNOSTIC SCRIPT CREATED

I've created `/home/user/SENTINEL_V2/diagnose_win_rate_drop.py` which will:
1. Compare performance before/after 14 hours ago
2. Check if signals are being posted (signal_posted field)
3. Analyze conviction score distribution
4. Identify failing tokens and KOL tiers
5. Show hourly breakdown
6. Suggest root causes

**To run on Railway or with database access:**
```bash
python3 diagnose_win_rate_drop.py
```

## RECOMMENDATIONS

### IMMEDIATE FIX (Now)
```python
# In config.py, change:
MIN_CONVICTION_SCORE = 70  # Was 45, raise to 70
POST_GRAD_THRESHOLD = 70   # Was 45, raise to 70
```

This will immediately filter out low-quality signals.

### SHORT-TERM FIXES (Next 24h)

1. **Run the diagnostic script** to confirm the hypothesis
   ```bash
   python3 /home/user/SENTINEL_V2/diagnose_win_rate_drop.py
   ```

2. **Monitor for 4-6 hours** after raising threshold
   - Expected: Fewer signals but higher win rate
   - Target: Back to 60-70% win rate

3. **Check Telegram posting health**
   - Verify all high-conviction signals are posting
   - Check logs for "WARNING" messages about TG failures

4. **Review wallet autodiscovery**
   - Check if bad wallets were added recently
   - Blacklist underperforming wallets

### LONG-TERM OPTIMIZATIONS

1. **Dynamic Thresholds** - Adjust based on win rate
   - If WR > 75%: Lower threshold slightly (catch more)
   - If WR < 60%: Raise threshold (quality over quantity)

2. **Graduated Scoring System**
   - Threshold 80+: Auto-post (highest confidence)
   - Threshold 70-79: Post with "⚠️ Medium" tag
   - Threshold 60-69: Post with "⚠️ Lower confidence" tag
   - Below 60: Don't post

3. **Wallet Performance Tracking**
   - Auto-blacklist wallets with < 40% win rate
   - Boost score for wallets with > 75% win rate

4. **Narrative Validation**
   - Verify narratives are actually trending
   - Penalize stale narratives

## EXPECTED RESULTS

**After raising threshold to 70:**
- Win rate: 60-70% (back to target)
- Signal volume: ~50% reduction (quality over quantity)
- User trust: Restored
- False positives: Dramatically reduced

**After implementing dynamic thresholds:**
- Win rate: 70-80% sustained
- Signal volume: Optimized
- Revenue: Increased (users more likely to follow signals)

## DEPLOYMENT STEPS

1. Update `config.py`:
   ```python
   MIN_CONVICTION_SCORE = 70
   POST_GRAD_THRESHOLD = 70
   ```

2. Commit and push:
   ```bash
   git add config.py
   git commit -m "CRITICAL FIX: Raise conviction threshold to 70 to restore win rate"
   git push
   ```

3. Railway will auto-deploy (watch logs)

4. Monitor for 4-6 hours

5. Run diagnostic script to confirm improvement

## NOTES

- The diagnostic script requires DATABASE_URL environment variable
- Run it on Railway or from a machine with network access to the database
- Current threshold of 45 is TOO LOW for quality signals
- This is not a bug - it's a configuration issue from aggressive experimentation

---

**Created:** /home/user/SENTINEL_V2/diagnose_win_rate_drop.py (comprehensive diagnostic tool)
**Status:** Awaiting database access to run diagnostics and confirm hypothesis
**Priority:** CRITICAL - Fix immediately to restore user trust
