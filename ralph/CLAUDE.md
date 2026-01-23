# Ralph - Prometheus Bot Debugging Agent

You are an autonomous debugging agent for the Prometheus Solana memecoin signals bot.

## URGENT: Current Issues to Debug

The user reports these critical issues:

1. **Telegram Calls Not Being Stored**: User sees CAs being called in Telegram groups, but they're not being collected in `telegram_calls_cache`
2. **KOL Names Missing**: KOL wallet names not displaying properly in signals
3. **Overall Flow Broken**: Framework exists but data isn't flowing through correctly

## Your Task

**Debug the entire flow systematically:**

1. **Check Telegram Monitor Status**
   - Is telegram_monitor connected and running?
   - Are messages being processed?
   - Are CAs being extracted from messages?
   - Is `telegram_calls_cache` being populated?

2. **Check KOL Name Flow**
   - Are KOL names being fetched from gmgn.ai?
   - Are they being stored in smart_wallet_tracker?
   - Are they being passed to conviction_data?
   - Are they making it to Telegram messages?

3. **Trace Full Data Flow**
   - KOL buy detected (webhook) → active_tracker
   - Token tracked → PumpPortal data collection
   - Conviction scoring → uses all components
   - Signal sent → Telegram with all data

## Investigation Steps

### 1. Check Telegram Monitor

```bash
# Check if monitor is initialized
grep -r "Telegram monitor" *.py

# Check cache population
grep -r "telegram_calls_cache\[" *.py

# Look for connection logs
# In Railway logs should see: "✅ Telegram connected" or errors
```

**Files to check:**
- `telegram_monitor.py` - Main monitor code
- `main.py` - Where cache is imported/used
- `scoring/conviction_engine.py` - Where cache is read for scoring
- `config.py` - TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_GROUPS

**Common issues:**
- TELEGRAM_API_ID/TELEGRAM_API_HASH not set in Railway env vars
- Monitor crashes on startup
- Groups not configured correctly
- Message handler not registered

### 2. Check KOL Name Storage

```bash
# Find where names are fetched
grep -r "gmgn.ai\|wallet_name\|kol_name" *.py

# Check smart_wallet_tracker
# Should have tracked_wallets dict with name/tier/win_rate
```

**Files to check:**
- `trackers/smart_wallets.py` - Wallet tracking
- `wallet_enrichment.py` - Name/tier fetching
- `active_token_tracker.py` - Signal generation
- `publishers/telegram.py` - Display formatting

**Common issues:**
- Names fetched but not stored in dict
- Names stored but not passed to signal_data
- Names in signal_data but not rendered in message

### 3. Trace Conviction Scoring

Check each component returns data:

```python
# In conviction_engine.py analyze_token():
# Should see logs like:
#   👑 Smart Wallets: 40 points
#   👥 Unique Buyers (15): +8 points
#   📡 Checking Telegram calls for XXXXX...
#   🐦 Twitter: +10 points
```

**Expected flow:**
```
analyze_token(token_address, token_data)
  ↓
base_scores['smart_wallet'] = 40  ← from smart_wallet_tracker
base_scores['narrative'] = 0       ← disabled (ENABLE_NARRATIVES=False)
base_scores['volume'] = 0          ← needs high thresholds
base_scores['momentum'] = 10       ← if price moved +20%
  ↓
unique_buyers_score = 5            ← from active_tracker.unique_buyers
  ↓
telegram_calls_score = 0           ← CHECK IF CACHE HAS DATA
twitter_score = 0                  ← conditional (40%+ bonding)
  ↓
TOTAL = 55 (should pass 45 threshold)
```

## Debugging Code Changes

Make targeted fixes:

### Fix 1: Add Telegram Monitor Diagnostics

If monitor isn't connecting:

```python
# In telegram_monitor.py initialize():
logger.info(f"🔧 TELEGRAM MONITOR DIAGNOSTIC:")
logger.info(f"   API_ID: {bool(self.api_id)}")
logger.info(f"   API_HASH: {bool(self.api_hash)}")
logger.info(f"   Groups configured: {len(monitored_groups)}")

# After connection:
logger.info(f"✅ Connected! Monitoring {len(self.monitored_groups)} groups")
for group_id, name in list(self.monitored_groups.items())[:3]:
    logger.info(f"   - {name} ({group_id})")
```

### Fix 2: Add Cache Population Logging

If CAs not being stored:

```python
# In telegram_monitor.py on_new_message():
if token_address:
    logger.info(f"🔥 TELEGRAM CALL: {token_address[:8]}... from {group_name}")
    logger.info(f"   Cache size before: {len(self.telegram_calls_cache)}")

    # ... add to cache ...

    logger.info(f"   Cache size after: {len(self.telegram_calls_cache)}")
    logger.info(f"   Total mentions for this token: {len(self.telegram_calls_cache[token_address]['mentions'])}")
```

### Fix 3: Verify Cache in Conviction Scoring

If cache populated but not used:

```python
# In conviction_engine.py PHASE 3.7:
logger.info(f"   📡 Telegram calls check:")
logger.info(f"      Cache has {len(telegram_calls_cache)} tokens")
logger.info(f"      Looking for: {token_address[:8]}...")

if token_address in telegram_calls_cache:
    logger.info(f"      ✅ FOUND! {len(telegram_calls_cache[token_address]['mentions'])} mentions")
else:
    logger.info(f"      ❌ NOT FOUND in cache")
```

### Fix 4: KOL Name Passthrough

If names not showing:

```python
# In active_token_tracker.py _send_signal():
logger.info(f"🚀 SENDING SIGNAL:")
logger.info(f"   smart_wallet_data: {conviction_data.get('smart_wallet_data')}")
logger.info(f"   Wallets: {conviction_data['smart_wallet_data'].get('wallets', [])}")

# Ensure wallets array has name/tier/win_rate for each
```

## Commit Strategy

Make small, focused commits:

```bash
git add <specific_files>
git commit -m "debug: Add Telegram monitor connection diagnostics"
git push

# Wait 2 minutes for deployment
# Check Railway logs for new diagnostic output
# Identify next issue
```

## Important

- **Make ONE focused change at a time**
- **Always add logging to verify**
- **Check Railway logs after each deploy**
- **Document what you found and fixed**
- **Don't assume - verify with logs**

## Output Format

After each investigation cycle, report:

```
## Investigation: [Component Name]

### What I Checked
- [File/function checked]
- [What I looked for]

### What I Found
- [Issue discovered]
- [Root cause]

### Fix Applied
- [Code change made]
- [File modified]

### Verification Needed
- [What to check in Railway logs]
- [Expected log output]

### Next Step
- [Next component to investigate]
```

## Railway Log Keywords

Look for these in logs to verify functionality:

**Telegram Monitor:**
- "✅ Telegram connected"
- "📡 Monitoring N group(s)"
- "🔥 TELEGRAM CALL detected"
- "📊 Total mentions: N"

**Conviction Scoring:**
- "🔍 Analyzing $SYMBOL"
- "👑 Smart Wallets: N points"
- "👥 Unique Buyers (N): +N points"
- "📡 Checking Telegram calls"
- "🎯 FINAL CONVICTION: N/100"

**Signal Sending:**
- "🚀 SENDING SIGNAL: $SYMBOL"
- "📤 Posted Prometheus signal"

If ANY of these are missing, that's where the issue is!
