# 🚨 CRITICAL: Railway Running Different Code Than Git

## User Report

Railway logs show scoring that **DOESN'T EXIST** in any git branch:

**What Railway Shows**:
```
💹 Buy/Sell Ratio: -5 points
⚡ Volume/Liquidity Velocity: 0 point
💰 BASE SCORE: 5/113
💎 MID SCORE: 17/100
🔍 THRESHOLD CHECK for UNKNOWN:
    new_score=17, threshold=60, signal_sent=False
⏩ FAILS threshold check - not sending
```

**What Git Shows**:
```python
# scoring/conviction_engine.py (lines in current git)
logger.info(f"   📊 Volume: {volume_score} points")  # Line 126
logger.info(f"   💰 BASE SCORE: {base_total}/85")     # Line 134
logger.info(f"   💎 MID SCORE: {mid_total}/100")      # Line 181
logger.info(f"   🎯 FINAL CONVICTION: {final_score}/100")  # Line 535
```

## What's Different

### 1. "Buy/Sell Ratio" - DOESN'T EXIST
**Railway**: `💹 Buy/Sell Ratio: -5 points`
**Git**: NO CODE FOR THIS ANYWHERE

Searched all branches - **NOT FOUND**:
```bash
# Searched everywhere
for branch in $(git branch -a | grep remotes); do
  git show $branch:scoring/conviction_engine.py 2>/dev/null | grep -i "buy.*sell"
done
# Result: EMPTY - no branches have this code
```

### 2. "Volume/Liquidity Velocity" - WRONG NAME
**Railway**: `⚡ Volume/Liquidity Velocity: 0 point`
**Git**: `📊 Volume: {volume_score} points` (line 126)

Current code just says "Volume", not "Volume/Liquidity Velocity"

### 3. BASE SCORE - WRONG DENOMINATOR
**Railway**: `BASE SCORE: 5/113`
**Git**: `BASE SCORE: {base_total}/85` (line 134)

Railway shows "/113" but git shows "/85"

### 4. Missing "FINAL CONVICTION"
**Railway**: Shows BASE SCORE and MID SCORE, then goes to THRESHOLD CHECK
**Git**: Should show `🎯 FINAL CONVICTION: {final_score}/100` (line 535)

Railway is NOT showing final conviction score before threshold check.

### 5. Threshold Check Format Different
**Railway**:
```
🔍 THRESHOLD CHECK for UNKNOWN:
    new_score=17, threshold=60, signal_sent=False
```

**Git** (line 530-535):
```python
threshold = config.MIN_CONVICTION_SCORE if is_pre_grad else config.POST_GRAD_THRESHOLD
logger.info(f"   🎯 FINAL CONVICTION: {final_score}/100")
logger.info(f"   📊 Threshold: {threshold} ({'PRE-GRAD' if is_pre_grad else 'POST-GRAD'})")
```

Different logging format entirely.

## Verification

### Checked ALL Branches
```bash
# Current branch
grep "Buy/Sell Ratio" scoring/conviction_engine.py
# Result: NOT FOUND

# Main branch
git show origin/main:scoring/conviction_engine.py | grep "Buy/Sell"
# Result: NOT FOUND

# Ralph's branch
git show origin/ralph/optimize-v1:scoring/conviction_engine.py | grep "Buy/Sell"
# Result: NOT FOUND

# Every other branch
# Result: NOT FOUND in any branch
```

### What Git Actually Has

**Current code structure** (scoring/conviction_engine.py):
1. **Line 90**: PHASE 1: FREE BASE SCORE (0-60 points)
2. **Line 100-131**: Score components:
   - Smart Wallet Activity (line 100-105)
   - Narrative Detection (line 108-121)
   - Volume Velocity (line 123-126) ← Just "Volume", not "Volume/Liquidity Velocity"
   - Price Momentum (line 128-131)
3. **Line 134**: `BASE SCORE: {base_total}/85` ← Not /113
4. **Line 158-173**: Unique Buyers (FREE)
5. **Line 181**: `MID SCORE: {mid_total}/100`
6. **Line 423-505**: Holder Concentration (10 CREDITS)
7. **Line 515-527**: ML Prediction Bonus
8. **Line 530-535**: Final score calculation + FINAL CONVICTION log

**NO "Buy/Sell Ratio" scoring anywhere in this flow.**

## What This Means

### Railway Deployment is Out of Sync

**Possibilities**:

#### 1. Railway Deployed from Old Branch (Most Likely)
Railway might be running from an old branch that:
- Had experimental buy/sell ratio code
- Was never merged to main
- Is still deployed and running

**Check**:
```bash
# On Railway, check git status
railway run bash
git status
git log --oneline -10
git branch
```

#### 2. Railway Has Local Modifications
Someone (or Ralph?) modified code directly on Railway server:
- Edited files in /app directory
- Changes never committed to git
- Railway container has uncommitted changes

**Check**:
```bash
railway run git diff
railway run git status
```

#### 3. Wrong Service Deployed
Maybe looking at wrong Railway service:
- Could be a staging environment
- Could be old deployment still running
- Check which service is actually serving the bot

**Check**:
```bash
railway status
railway ps
```

## Immediate Actions Needed

### 1. Identify Railway Deployment Source
```bash
# Connect to Railway
railway link

# Check git status
railway run git status
railway run git log --oneline -5
railway run git branch -v

# Check for local changes
railway run git diff HEAD
```

### 2. Download Railway's Actual Code
```bash
# Get the actual file running on Railway
railway run cat scoring/conviction_engine.py > railway_conviction.py

# Compare to git
diff railway_conviction.py scoring/conviction_engine.py

# Search for the mystery code
grep -n "Buy/Sell Ratio" railway_conviction.py
grep -n "Volume/Liquidity Velocity" railway_conviction.py
```

### 3. Check Railway Environment Variables
```bash
# See which branch is configured
railway variables | grep BRANCH
railway variables | grep GIT

# Check deployment settings
railway status
```

### 4. Find When This Code Was Deployed
```bash
# Check Railway deployment history
railway logs --deployment | grep "deployed\|build"

# Check git history for this code (if it ever existed)
git log --all --grep="buy.*sell" --oneline
```

## The "Buy/Sell Ratio" Code Mystery

**If this code exists on Railway**, it likely looks like:

```python
# HYPOTHETICAL CODE (not in git)
def _score_buy_sell_ratio(self, token_data: Dict) -> int:
    """Score based on buy/sell ratio (accumulation vs distribution)"""
    buys = token_data.get('txns_24h_buys', 0)
    sells = token_data.get('txns_24h_sells', 0)

    if sells == 0:
        return 0

    ratio = buys / sells

    if ratio > 1.5:  # Strong accumulation
        return 10
    elif ratio > 1.2:  # Moderate accumulation
        return 5
    elif ratio < 0.8:  # Distribution (more sells than buys)
        return -5  # ← This matches "-5 points" in logs
    else:
        return 0

# Then in analyze_token():
buy_sell_score = self._score_buy_sell_ratio(token_data)
logger.info(f"   💹 Buy/Sell Ratio: {buy_sell_score} points")
```

**This would explain**:
- The "-5 points" (distribution penalty)
- Why it's always -5 (most tokens have more sells than buys)
- The emoji and label format

## Risk Assessment

### HIGH RISK: Production Code Divergence

**Problems**:
1. **Can't reproduce bugs** - git doesn't match production
2. **Can't audit changes** - no commit history for this code
3. **Can't rollback safely** - don't know what version is deployed
4. **Can't trust git** - source of truth is Railway, not git

**Consequences**:
- Future deployments might break unexpectedly
- Can't review what's actually running
- Can't track who made changes and when
- Can't ensure code quality/review process

## Resolution Steps

### Option A: Sync Railway → Git (Preserve Current Code)
1. Download Railway's actual code
2. Commit to new branch `railway-deployed-code`
3. Review changes
4. Merge to main if code is good
5. Redeploy from main to ensure sync

### Option B: Sync Git → Railway (Override Railway)
1. Force redeploy from main branch
2. Lose any Railway-only changes
3. This will remove "Buy/Sell Ratio" code
4. Use only code that's in git

### Option C: Investigate & Decide
1. Download Railway code
2. Compare to git thoroughly
3. Decide which changes to keep
4. Commit keepers to git
5. Redeploy to sync

## Recommended Action Plan

**Step 1: Download Railway Code (Urgent)**
```bash
railway run bash -c 'tar -czf /tmp/app-backup.tar.gz /app'
railway run cat /tmp/app-backup.tar.gz > app-backup.tar.gz
tar -xzf app-backup.tar.gz
```

**Step 2: Compare (High Priority)**
```bash
# Find all differences
diff -r app/ . > railway-vs-git.diff

# Focus on key files
diff app/scoring/conviction_engine.py scoring/conviction_engine.py
diff app/config.py config.py
```

**Step 3: Document Findings (High Priority)**
- What code exists on Railway but not git?
- When was it added?
- Who added it?
- Is it intentional or accidental?

**Step 4: Decide & Fix (High Priority)**
- If code is good: Commit to git
- If code is bad: Redeploy from git
- If unsure: Create staging environment to test

## Bottom Line

**CRITICAL ISSUE**: Railway is running code that doesn't exist in git repository.

**Evidence**:
- "Buy/Sell Ratio" logging: NOT IN ANY BRANCH
- Different score denominators: /113 vs /85
- Missing "FINAL CONVICTION" log
- Different threshold check format

**Next Steps**:
1. Connect to Railway and download actual code
2. Compare to git to find ALL differences
3. Decide whether to sync Railway→Git or Git→Railway
4. Establish process to prevent this in future

**Urgency**: HIGH - Can't safely deploy or rollback until sync is restored.
