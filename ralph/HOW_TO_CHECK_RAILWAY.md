# How to Get Code from Railway

## Quick Commands (Copy & Paste)

### 1. Connect to Railway (if not already)
```bash
# Link to your project
railway link
# Select: Sydneyanon/SENTINEL_V2
```

### 2. Get the Actual Production Code
```bash
# Download the conviction engine file
railway run --service prometheusbot-production cat /app/scoring/conviction_engine.py > railway_conviction.py

# Check how many lines it has
wc -l railway_conviction.py
# Git version has 745 lines - does Railway match?

# Search for the mystery code
grep -n "Buy/Sell Ratio" railway_conviction.py
grep -n "Buy.*Sell" railway_conviction.py
grep -n "/113" railway_conviction.py
```

### 3. Compare to Git Version
```bash
# See ALL differences
diff scoring/conviction_engine.py railway_conviction.py | head -100

# Or use a side-by-side view
diff -y scoring/conviction_engine.py railway_conviction.py | less
```

### 4. Check Railway's Git Status
```bash
# See what branch Railway is on
railway run --service prometheusbot-production bash -c "cd /app && git status"

# See recent commits on Railway
railway run --service prometheusbot-production bash -c "cd /app && git log --oneline -10"

# Check which branch
railway run --service prometheusbot-production bash -c "cd /app && git branch -v"

# Check for uncommitted changes
railway run --service prometheusbot-production bash -c "cd /app && git diff HEAD"
```

### 5. Get Other Key Files (Optional)
```bash
# Get config.py
railway run --service prometheusbot-production cat /app/config.py > railway_config.py

# Get main.py
railway run --service prometheusbot-production cat /app/main.py > railway_main.py

# Compare config
diff config.py railway_config.py | head -50
```

## What You're Looking For

### If Railway has Extra Code:
You'll see something like this in the diff:
```diff
+ def _score_buy_sell_ratio(self, token_data: Dict) -> int:
+     """Score based on buy/sell transaction ratio"""
+     buys = token_data.get('txns_24h_buys', 0)
+     sells = token_data.get('txns_24h_sells', 0)
+
+     if sells == 0:
+         return 0
+
+     ratio = buys / sells
+
+     if ratio < 0.8:  # More sells than buys (distribution)
+         return -5
+     elif ratio > 1.5:  # More buys than sells (accumulation)
+         return 10
+     else:
+         return 0
+
+ # In analyze_token():
+ buy_sell_score = self._score_buy_sell_ratio(token_data)
+ logger.info(f"   💹 Buy/Sell Ratio: {buy_sell_score} points")
```

### If Railway is on Different Branch:
The `git status` command will show:
```
On branch some-old-branch
Your branch is up to date with 'origin/some-old-branch'.
```

### If Railway has Local Modifications:
The `git diff HEAD` will show uncommitted changes.

## Alternative: Download Entire App Directory

If you want everything:
```bash
# Create a tarball of the entire /app directory
railway run --service prometheusbot-production tar -czf /tmp/app-backup.tar.gz /app

# Download it (this might not work directly, so use individual files instead)
railway run --service prometheusbot-production cat /tmp/app-backup.tar.gz > app-backup.tar.gz

# Extract
tar -xzf app-backup.tar.gz
```

## Troubleshooting

### If Railway CLI Not Installed:
```bash
# Install Railway CLI
npm install -g @railway/cli

# Or with brew on Mac
brew install railway
```

### If "Service Not Found":
```bash
# List all services
railway status

# Common service names:
# - prometheusbot-production
# - prometheus-bot
# - main
# - web

# Try each one:
railway run --service <service-name> echo "Connected!"
```

### If Permission Denied:
```bash
# Login to Railway
railway login

# Then link again
railway link
```

## Quick Analysis Script

Save this as `check_railway.sh`:
```bash
#!/bin/bash

echo "=== Downloading Railway Code ==="
railway run --service prometheusbot-production cat /app/scoring/conviction_engine.py > railway_conviction.py

echo ""
echo "=== Line Count Comparison ==="
echo "Git:     $(wc -l < scoring/conviction_engine.py) lines"
echo "Railway: $(wc -l < railway_conviction.py) lines"

echo ""
echo "=== Searching for Mystery Code ==="
echo "Buy/Sell Ratio mentions:"
grep -c "Buy.*Sell" railway_conviction.py || echo "0"

echo ""
echo "=== Railway Git Status ==="
railway run --service prometheusbot-production bash -c "cd /app && git status" | head -5

echo ""
echo "=== Recent Commits on Railway ==="
railway run --service prometheusbot-production bash -c "cd /app && git log --oneline -5"

echo ""
echo "=== Checking for Uncommitted Changes ==="
railway run --service prometheusbot-production bash -c "cd /app && git diff HEAD --stat" || echo "No uncommitted changes"

echo ""
echo "Done! Check railway_conviction.py for the actual code."
```

Then run:
```bash
chmod +x check_railway.sh
./check_railway.sh
```

## What to Do With Results

### Scenario 1: Different Branch
**If Railway shows**: `On branch old-experimental-branch`

**Fix**:
```bash
# Deploy main branch to Railway
git checkout main
git push origin main
# Railway will auto-deploy from main
```

### Scenario 2: Uncommitted Changes
**If git diff shows changes**

**Fix Option A** (Keep Railway code):
```bash
# Commit Railway's code to git
cp railway_conviction.py scoring/conviction_engine.py
git add scoring/conviction_engine.py
git commit -m "sync: Import code from Railway production"
git push
```

**Fix Option B** (Discard Railway changes):
```bash
# Force Railway to use git version
# Just push to main, Railway will redeploy
git push origin main
```

### Scenario 3: Extra Code in Railway
**If Railway has buy/sell ratio code**

**Decision time**:
1. Review the code - is it good?
2. If yes → commit to git
3. If no → redeploy from git (loses the code)

## Next Steps After Download

1. **Review the differences**:
   ```bash
   diff scoring/conviction_engine.py railway_conviction.py > differences.txt
   cat differences.txt
   ```

2. **Decide what to keep**:
   - If Railway code is better → commit it to git
   - If git code is correct → redeploy to Railway

3. **Sync them**:
   ```bash
   # Either this (Railway → git):
   cp railway_conviction.py scoring/conviction_engine.py
   git add scoring/conviction_engine.py
   git commit -m "sync: Railway production code"
   git push

   # Or this (git → Railway):
   git push origin main  # triggers redeploy
   ```

## Summary

**Run these 3 commands**:
```bash
# 1. Get the code
railway run --service prometheusbot-production cat /app/scoring/conviction_engine.py > railway_conviction.py

# 2. Compare
diff scoring/conviction_engine.py railway_conviction.py | head -100

# 3. Check Railway's git status
railway run --service prometheusbot-production bash -c "cd /app && git status && git log --oneline -5"
```

That will show you:
- What code is actually running
- How different it is from git
- Which branch Railway is on
- If there are uncommitted changes

Then we can decide how to fix it.
