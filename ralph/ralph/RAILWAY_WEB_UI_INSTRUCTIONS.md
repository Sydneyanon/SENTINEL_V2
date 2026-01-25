# How to Check Railway Code (Web UI Only)

Since you're working through Railway web UI and Claude, here's how to run the diagnostic:

## Option 1: Via Railway Web UI (Easiest)

### Step 1: Merge This PR First
1. Go to: https://github.com/Sydneyanon/SENTINEL_V2/pulls
2. Find the PR for `claude/check-sessions-clarity-6CaJr`
3. Click "Merge pull request"
4. Railway will auto-deploy in ~2 minutes

### Step 2: Run Diagnostic via Railway Dashboard
1. Go to Railway Dashboard: https://railway.app
2. Select your SENTINEL_V2 project
3. Click on the `prometheusbot-production` service (or whatever the main bot service is called)
4. Click "Settings" tab
5. Scroll down to "Deploy Triggers"
6. Click "New Deployment" to trigger a fresh deploy

### Step 3: Run the Script
**Option A - Via Railway CLI (if available in web terminal)**:
1. In Railway dashboard, click on your service
2. Look for a "Terminal" or "Shell" option in the UI
3. If available, run:
   ```bash
   python diagnostic_code_check.py
   ```

**Option B - Add as One-Time Job**:
1. In Railway dashboard, click "+ New"
2. Select "Empty Service"
3. Add name: "diagnostic-check"
4. In Settings → Start Command, enter:
   ```bash
   python diagnostic_code_check.py
   ```
5. Click "Deploy"
6. Check logs for output

**Option C - View in Logs (Simplest)**:
1. Add this line to your `main.py` at the very top (after imports):
   ```python
   # TEMPORARY DIAGNOSTIC - REMOVE AFTER CHECKING
   import subprocess
   print("🔍 RUNNING DIAGNOSTIC...")
   subprocess.run(["python", "diagnostic_code_check.py"])
   ```
2. Commit and push to main
3. Railway redeploys
4. Check Railway logs - diagnostic output will appear at startup
5. **IMPORTANT**: Remove this code after checking!

## Option 2: Manual File Check (If Above Doesn't Work)

### Via GitHub Web UI:
1. Go to deployed branch on Railway (probably `main`)
2. Navigate to: https://github.com/Sydneyanon/SENTINEL_V2/blob/main/scoring/conviction_engine.py
3. Look for:
   - Line count (bottom right shows total lines)
   - Search in file (press `/` then type "buy sell")
   - Check if more than 745 lines

### Via Railway Logs:
The diagnostic output will show in logs if Option C above is used.

## What You're Looking For

The diagnostic will output something like:

```
🔍 RAILWAY CODE DIAGNOSTIC
========================================

📋 GIT STATUS:
On branch main
Your branch is up to date with 'origin/main'

📁 FILE INFORMATION:
✅ scoring/conviction_engine.py: 745 lines   ← Should match git

🔍 SEARCHING FOR 'BUY/SELL RATIO' CODE:
Found 3 lines mentioning buy/sell:
  Line 158: # NEW: Track unique buyers (only buys, not sells)
  Line 342: if wallet in self.our_kol_wallets:

❌ NO 'Buy/Sell Ratio' logging found     ← KEY CHECK
❌ NO '/113' found (should be /85 in git) ← KEY CHECK
```

**If you see**:
- ✅ "NO 'Buy/Sell Ratio' logging found" → Railway matches git (GOOD)
- ❌ "FOUND 'Buy/Sell Ratio' logging!" → Railway has extra code (PROBLEM)

## Alternative: Check Specific Files via Railway UI

Some Railway plans allow file browsing:

1. Go to Railway dashboard
2. Click your service
3. Look for "Files" or "File Browser" tab
4. Navigate to `/app/scoring/conviction_engine.py`
5. Check line count and search for "Buy/Sell"

## If All Else Fails: Use Logs

Your Railway logs already show the output! Look for lines like:
```
💹 Buy/Sell Ratio: -5 points        ← This is the proof
⚡ Volume/Liquidity Velocity: 0 point
💰 BASE SCORE: 5/113                 ← /113 instead of /85
```

This tells us Railway HAS extra code that's not in git.

## What to Do After Running Diagnostic

**Scenario 1**: Diagnostic shows "NO Buy/Sell Ratio found"
- Good news: Railway matches git
- The logs you saw might be from an old deployment
- Force a fresh deploy to be sure

**Scenario 2**: Diagnostic shows "FOUND Buy/Sell Ratio"
- Railway has code not in git
- Decision time: Keep it or remove it?
- If keep: Need to download and commit to git
- If remove: Redeploy from main

**Scenario 3**: Can't run diagnostic
- Share your Railway deployment settings
- Check which git branch/commit Railway is deploying
- Look for "Build Logs" in Railway to see what was deployed

## Quick Summary

**Easiest path**:
1. Merge this PR
2. Wait for Railway to deploy
3. Add the 3-line code snippet to `main.py`
4. Push to trigger redeploy
5. Check Railway logs for diagnostic output
6. Remove the 3 lines after

**Output will tell us**:
- Exact code running on Railway
- Whether it matches git
- Where the mystery code is
