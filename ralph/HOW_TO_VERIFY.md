# How to Verify Database & OPT-041

**Tasks**:
1. Check database signal count for ML training
2. Verify OPT-041 credit optimization is working

---

## Option 1: Railway Web Interface (Easiest)

### Step 1: Access Railway Logs

1. Go to Railway dashboard
2. Click on `prometheusbot-production` service
3. Click "Logs" tab
4. Copy recent logs (last 100-200 lines)

### Step 2: Save Logs to File

Create file: `railway_logs.txt`
Paste the logs you copied

### Step 3: Run Verification Scripts

```bash
# Verify OPT-041 credit optimization
python ralph/verify_opt041.py railway_logs.txt

# Check database (needs to run ON Railway)
# See Option 2 below
```

---

## Option 2: Run Check on Railway (Most Accurate)

### Method A: Railway CLI (if installed)

```bash
# Link to project
railway link

# Run database check
railway run python ralph/check_database.py

# View recent logs
railway logs
```

### Method B: Deploy Diagnostic Script

1. **Edit main.py** - Add at startup:

```python
# At top of main.py, after imports
import ralph.check_database as db_check

# In main(), before bot starts:
logger.info("🔍 Running database diagnostic...")
try:
    import asyncio
    asyncio.create_task(db_check.main())
except Exception as e:
    logger.error(f"Diagnostic failed: {e}")
```

2. **Commit and push**:

```bash
git add main.py
git commit -m "temp: Add database diagnostic to startup"
git push origin claude/check-sessions-clarity-6CaJr
```

3. **Merge PR and check logs** - Database stats will appear in Railway logs

4. **Remove diagnostic code** after checking

---

## Option 3: Manual Log Analysis

### For Database Check:

**Look for in Railway logs**:
- `Signal posted` messages → Count them
- `New token detected` → Shows tokens being tracked
- Database connection messages
- Any SQL queries in logs

**What to count**:
- Total signals posted (search for "Signal posted" or "Sending signal")
- Signals per day
- Any outcome tracking messages

### For OPT-041 Check:

**Look for in Railway logs**:
- ✅ `Using cached metadata` or `Cache hit` → OPT-041 working!
- ✅ `metadata_cache` mentions → Cache is active
- ❌ `api.helius.xyz/v0/token-metadata` → Direct API calls (should be rare)
- 💳 Credit usage numbers → Should be decreasing over time

**Good signs**:
- See "cached" or "cache hit" messages frequently
- Few direct Helius API calls
- Credit usage lower than before

**Bad signs**:
- Many direct API calls to Helius
- No cache hit messages
- High credit usage

---

## Quick Manual Check (No Code Needed)

### Database Status:

1. Check Railway logs for last 24 hours
2. Search for: `signal` (should see "Signal posted" messages)
3. Count occurrences
4. If >50 signals → Ready for ML training!
5. If <50 signals → Need more time running

### OPT-041 Status:

1. Check Railway logs for last 1-2 hours
2. Search for: `cache` or `cached`
3. If you see "Using cached metadata" → OPT-041 is working!
4. Compare: Count "cache hit" vs "Fetching metadata"
5. Ratio >50% = OPT-041 working well

---

## What to Report Back

After checking, report:

### For Database:
- [ ] Total signals posted: ___
- [ ] Signals with outcomes: ___
- [ ] Ready for ML? Yes/No
- [ ] Sample log showing signal posts (paste 5-10 lines)

### For OPT-041:
- [ ] Cache hits seen: ___
- [ ] Direct API calls: ___
- [ ] Cache hit rate: ___%
- [ ] OPT-041 working? Yes/No/Unclear
- [ ] Sample log showing cache activity (paste 5-10 lines)

---

## Expected Outcomes

### If Database Has 50+ Signals:
- I can train ML model immediately
- Will export signals and train XGBoost
- ML predictions go live within 1-2 hours

### If Database Has <50 Signals:
- Need to keep bot running to collect more
- ETA: 1-2 weeks based on signal rate
- In meantime, work on other optimizations

### If OPT-041 Working:
- Estimated 40-60% credit savings
- Metadata calls are cached (60 min TTL)
- No further action needed

### If OPT-041 Not Working:
- Check code deployment (may need Railway redeploy)
- Verify helius_fetcher.py has metadata_cache
- Check logs for error messages

---

## Automated Check (If You Can Run Python)

If you can run Python locally with Railway access:

```bash
# Install Railway CLI
npm install -g @railway/cli

# Link project
railway link

# Run checks
railway run python ralph/check_database.py

# Copy logs to file
railway logs > railway_recent.txt

# Verify OPT-041
python ralph/verify_opt041.py railway_recent.txt
```

This will give you complete diagnostics automatically.
