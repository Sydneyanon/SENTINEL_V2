# Built-in Telegram Monitor Setup Guide

## Overview

SENTINEL now has a **built-in Telegram monitor** that runs directly in the bot (no separate binary needed).

**Advantages:**
- ✅ Everything in one process
- ✅ Easier to configure (just edit config.py)
- ✅ Auto-detects Solana CAs in messages
- ✅ Helper script to list your groups
- ✅ No webhook setup needed

**You still need to:**
- Join Telegram groups manually
- Get API credentials from Telegram
- Run helper script once to find group IDs

---

## Step 1: Get Telegram API Credentials

1. Go to https://my.telegram.org
2. Log in with your phone number
3. Click **"API development tools"**
4. Create an app:
   - **App title:** "SENTINEL Monitor"
   - **Short name:** "sentinel"
   - **Platform:** Other
5. Copy your **api_id** and **api_hash**

---

## Step 2: Set Environment Variables

Add to your environment (Railway/server):

```bash
export TELEGRAM_API_ID="12345678"
export TELEGRAM_API_HASH="abcdef1234567890abcdef1234567890"
export TELEGRAM_PHONE="+15551234567"  # Optional: for first-time auth
```

**On Railway:**
1. Go to your project settings
2. Click "Variables"
3. Add:
   - `TELEGRAM_API_ID` = your api_id
   - `TELEGRAM_API_HASH` = your api_hash
   - `TELEGRAM_PHONE` = your phone (optional)

---

## Step 3: Join Telegram Groups

**Manually join 5-10 Solana alpha groups:**

Search Telegram for:
- "Solana calls"
- "Pump.fun alpha"
- "Solana gems"
- "Memecoin calls"

**Popular types:**
- Free alpha groups
- Public call channels
- Premium groups (if you have access)

**You must be a member** of each group to monitor it.

---

## Step 4: Auto-Generate Group List

Run the helper script to list all your groups:

```bash
python telegram_monitor.py
```

**What it does:**
1. Connects to your Telegram account
2. Lists all groups you're in
3. Shows their IDs
4. Generates config template

**First time:** You'll be asked for:
- Phone number
- Verification code (sent via Telegram)
- 2FA password (if enabled)

**Output looks like:**
```
🔍 Fetching your Telegram groups...

  1. Bullish's Bangers
     ID: 1234567890

  2. Solana Alpha Calls
     ID: 9876543210

  3. Pump.fun Gems
     ID: 5555555555

✅ Found 3 groups/channels

==================================================================
TELEGRAM_GROUPS CONFIG (add to config.py)
==================================================================

# Telegram Groups to Monitor
TELEGRAM_GROUPS = {
    1234567890: 'bullish_bangers',  # Bullish's Bangers
    9876543210: 'alpha_calls',      # Solana Alpha Calls
    5555555555: 'pump_gems',        # Pump.fun Gems
}
```

---

## Step 5: Update config.py

Copy the `TELEGRAM_GROUPS` config from the script output and add it to `config.py`:

```python
# config.py

# Enable built-in monitor
ENABLE_BUILTIN_TELEGRAM_MONITOR = True

# Telegram Groups to Monitor
TELEGRAM_GROUPS = {
    1234567890: 'bullish_bangers',  # Bullish's Bangers
    9876543210: 'alpha_calls',      # Solana Alpha Calls
    5555555555: 'pump_gems',        # Pump.fun Gems
}
```

**Edit to keep only groups you want to monitor** (remove noisy ones).

---

## Step 6: Install Dependencies

```bash
pip install telethon
```

Or if using requirements.txt:
```bash
pip install -r requirements.txt
```

---

## Step 7: Start SENTINEL

```bash
python main.py
```

**You'll see:**
```
📱 Initializing built-in Telegram monitor...
✅ Telegram connected: @your_username
🔍 Monitoring 3 group(s)
✅ Telegram monitor started (3 groups)
```

**Monitor is now running!**

---

## How It Works

### When a CA is Mentioned in a Group

```
1. Someone posts in "Bullish's Bangers":
   "New gem! GDfnLz8VKz..."

2. Monitor detects Solana CA
   └─ Regex finds: GDfnLz8VKz...

3. Adds to telegram_calls_cache
   └─ Same structure as webhook version

4. If KOL buys same token later:
   └─ SENTINEL applies Telegram bonus (+5-15 pts)
```

---

## Monitoring Logs

Look for these in SENTINEL logs:

```
✅ Call detected:
🔥 TELEGRAM CALL detected: GDfnLz8V... (group: bullish_bangers)
   📊 Total mentions: 1 from 1 group(s)

✅ Multi-group convergence:
🔥 TELEGRAM CALL detected: GDfnLz8V... (group: alpha_calls)
   📊 Total mentions: 3 from 3 group(s)

✅ Bonus applied:
🔥 TELEGRAM CALL BONUS: +15 pts
   3 mention(s) from 3 group(s) (4m ago)
```

---

## Configuration Options

### Enable/Disable

```python
# config.py
ENABLE_BUILTIN_TELEGRAM_MONITOR = True   # Built-in monitor
ENABLE_TELEGRAM_SCRAPER = True           # Webhook mode (external scraper)
```

**You can use both** or just one:
- **Both enabled:** Built-in + external scraper (double coverage)
- **Built-in only:** No external scraper needed
- **External only:** Use solana-token-scraper binary instead

---

### Add/Remove Groups

**To add a group:**
1. Join it on Telegram
2. Run `python telegram_monitor.py` again
3. Copy new group ID to config.py
4. Restart SENTINEL

**To remove a group:**
1. Delete the line from `TELEGRAM_GROUPS`
2. Restart SENTINEL

---

## Troubleshooting

### "TELEGRAM_API_ID and TELEGRAM_API_HASH must be set"

**Fix:**
- Set environment variables (see Step 2)
- Check they're actually set: `echo $TELEGRAM_API_ID`
- On Railway: verify in project variables

### "Failed to initialize Telegram monitor"

**Possible causes:**
1. **Wrong credentials:** Double-check api_id and api_hash
2. **First-time auth needed:** Set `TELEGRAM_PHONE` and run locally first
3. **Session file issue:** Delete `sentinel_session.session` and restart

### "No groups detected" when running helper script

**Possible causes:**
1. You haven't joined any groups yet
2. Groups are channels (not groups) - still works!
3. Telegram API connection issue - check credentials

### Monitor not detecting calls

**Check:**
1. Are you actually a member of the groups?
2. Are groups posting Solana CAs? (test with a known call)
3. Is `ENABLE_BUILTIN_TELEGRAM_MONITOR = True`?
4. Check logs for errors

### "Flood wait" error

Telegram rate limiting. Wait a few minutes and try again.

---

## Comparison: Built-in vs External Scraper

| Feature | Built-in Monitor | External Scraper (Option 1) |
|---------|------------------|----------------------------|
| **Setup** | pip install telethon | Download binary |
| **Running** | Part of SENTINEL | Separate service |
| **Config** | config.py | filters.csv |
| **Maintenance** | One process | Two processes |
| **Crash risk** | Affects SENTINEL | Isolated |
| **Discord** | No | Yes |
| **Flexibility** | Full control | Limited |

**Recommendation:**
- **Built-in** if you want everything in one place
- **External** if you want isolation or need Discord support

---

## Security Notes

1. **Session file:** `sentinel_session.session` contains auth token - keep secure
2. **Read-only:** Monitor only reads messages, never posts
3. **Telegram TOS:** Using user account for automation is technically against TOS (use at own risk)
4. **Use secondary account:** Consider using a separate Telegram account for monitoring

---

## Advanced: Group Quality Weighting (Future)

Track which groups give best calls:

```python
# config.py (future enhancement)
TELEGRAM_GROUP_WEIGHTS = {
    1234567890: 1.5,  # Bullish's Bangers (75% hit rate)
    9876543210: 1.2,  # Alpha Calls (60% hit rate)
    5555555555: 0.5,  # Noisy group (25% hit rate)
}
```

Apply multiplier to scoring:
```python
base_score = 10  # Medium intensity
group_multiplier = TELEGRAM_GROUP_WEIGHTS.get(group_id, 1.0)
final_score = int(base_score * group_multiplier)
```

---

## Summary

**Setup steps:**
1. Get Telegram API credentials → 2 min
2. Set environment variables → 1 min
3. Join Telegram groups → 5 min
4. Run helper script → 1 min
5. Update config.py → 1 min
6. Restart SENTINEL → Done!

**Total time:** ~10 minutes (one-time setup)

**Result:** SENTINEL now gets +5-15 pts bonus when Telegram groups call tokens that KOLs buy! 🔥

---

**Questions?** Check the logs or re-run `python telegram_monitor.py` to verify your groups.
