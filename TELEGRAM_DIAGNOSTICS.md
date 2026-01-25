# Telegram Issues - Diagnostic & Fix

## Issues Reported

1. **Telegram commands not working** - No responses from bot
2. **Telegram calls not logging** - Not seeing call detections in logs

---

## Diagnostics Required

### 1. Check Environment Variables

On Railway, verify these are set:

```bash
# Required for commands
TELEGRAM_BOT_TOKEN=your_bot_token
ADMIN_TELEGRAM_USER_ID=your_user_id  # Get from @userinfobot

# Required for call detection
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_GROUPS={"group_id": "group_name"}  # Must be valid JSON or Python dict
```

### 2. Check Railway Logs

Look for these specific messages:

**Admin Bot (Commands):**
```
✅ Admin bot initialized
✅ Admin bot polling started
```

**Telegram Monitor (Call Detection):**
```
✅ Telegram connected: @username
✅ Message handler registered - listening for calls!
📬 Telegram monitor active: X messages processed
```

**If Missing:**
```
⚠️ TELEGRAM_BOT_TOKEN not set - admin bot disabled
⚠️ ADMIN_TELEGRAM_USER_ID not set - admin bot disabled
⚠️ TELEGRAM_API_ID and TELEGRAM_API_HASH not set - Telegram monitoring disabled
```

---

## Common Causes

### Admin Bot Not Responding

**Cause 1: Bot token invalid or expired**
- Solution: Regenerate token via @BotFather
- Command: `/newbot` or `/token`

**Cause 2: Admin user ID not set or wrong**
- Solution: Get YOUR user ID from @userinfobot
- Set: `ADMIN_TELEGRAM_USER_ID=123456789`

**Cause 3: Bot crashed silently**
- Check logs for: `❌ Admin bot crashed:`
- Common errors:
  - Network timeout
  - Token revoked
  - Bot blocked by Telegram

**Cause 4: Polling not started**
- Bot initialized but never started polling
- Check for: `✅ Admin bot polling started`

### Call Detection Not Logging

**Cause 1: Telegram Monitor not initialized**
- Missing: `TELEGRAM_API_ID` or `TELEGRAM_API_HASH`
- Get from: https://my.telegram.org

**Cause 2: No groups configured**
- `TELEGRAM_GROUPS` is empty or invalid JSON
- Must be dict format: `{"chat_id": "group_name"}`

**Cause 3: Session expired**
- Telegram session (`sentinel_session.session`) became invalid
- Solution: Delete session file, re-authenticate

**Cause 4: Not in groups**
- Bot account not added to monitored groups
- Solution: Join groups with account linked to API_ID

---

## Quick Test Commands

### Test Admin Bot

```bash
# In Telegram, send to your bot:
/help
/health
/stats
```

**Expected**: Bot responds with formatted message

**If No Response**:
1. Check bot is running: `railway logs --tail 100`
2. Check user ID matches: Look for "Authorized user ID: X"
3. Test bot token: `curl https://api.telegram.org/bot<TOKEN>/getMe`

### Test Call Detection

**Method 1**: Post CA in monitored group
```
Check out this token: GDfnRi8...abc
```

**Expected in logs**:
```
🔥 TELEGRAM CALL detected: GDfn8... (group: bullish_bangers)
📊 Total mentions: 1 from 1 group(s)
```

**If No Detection**:
1. Check monitor active: `📬 Telegram monitor active: X messages`
2. Check session: `✅ Telegram connected: @username`
3. Check groups: `🔍 Monitoring X group(s)`

---

## Step-by-Step Fix

### Fix Admin Bot Commands

1. **Get your Telegram user ID**:
   - Message @userinfobot in Telegram
   - Copy your ID (e.g., `123456789`)

2. **Set environment variable**:
   ```bash
   # Railway dashboard → Variables
   ADMIN_TELEGRAM_USER_ID=123456789
   ```

3. **Restart bot**:
   - Railway auto-restarts on variable change
   - Check logs: `✅ Admin bot polling started`

4. **Test**:
   - Send `/help` to your bot
   - Should respond immediately

### Fix Call Detection

1. **Verify Telegram API credentials**:
   ```bash
   # Railway dashboard → Variables
   TELEGRAM_API_ID=1234567
   TELEGRAM_API_HASH=abc123...
   ```

2. **Check session**:
   - If monitor failing to connect, delete session:
   ```bash
   railway shell
   rm sentinel_session.session
   exit
   ```
   - Restart bot - it will re-authenticate

3. **Verify groups configured**:
   ```python
   # config.py
   TELEGRAM_GROUPS = {
       -1001234567890: "bullish_bangers",
       -1009876543210: "moon_shots"
   }
   ```

4. **Check logs**:
   ```
   ✅ Telegram connected: @yourhandle
   🔍 Monitoring 2 group(s):
      - bullish_bangers (-1001234567890)
      - moon_shots (-1009876543210)
   ✅ Message handler registered - listening for calls!
   ```

---

## Emergency Fix Script

If nothing works, try this:

```bash
# Railway shell
railway shell

# Check environment
env | grep TELEGRAM
env | grep ADMIN

# Test bot token
curl -s https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe

# Check if admin bot running
ps aux | grep python

# Check logs for errors
cat /var/log/*.log | grep -i "telegram\|admin"

# Force restart
railway restart
```

---

## Still Not Working?

### Get Detailed Diagnostics

Add this to `main.py` after admin bot initialization:

```python
if admin_bot_initialized:
    logger.info("="*80)
    logger.info("ADMIN BOT DIAGNOSTIC:")
    logger.info(f"   App created: {bool(admin_bot.app)}")
    logger.info(f"   Token set: {bool(config.TELEGRAM_BOT_TOKEN)}")
    logger.info(f"   Admin ID: {admin_bot.admin_user_id}")
    logger.info(f"   Handlers: {len(admin_bot.app.handlers) if admin_bot.app else 0}")
    logger.info("="*80)
```

### Check Telegram Monitor

Add this to telegram_monitor.py initialization:

```python
logger.info("="*80)
logger.info("TELEGRAM MONITOR DIAGNOSTIC:")
logger.info(f"   Client created: {bool(self.client)}")
logger.info(f"   Connected: {self.client.is_connected() if self.client else False}")
logger.info(f"   Groups to monitor: {list(self.monitored_groups.keys())}")
logger.info(f"   Message handler registered: {bool(self.client._event_builders)}")
logger.info("="*80)
```

---

## Preventative Monitoring

Add health checks to detect issues early:

### Admin Bot Health
```python
# Check every 5 minutes
async def check_admin_bot():
    if not admin_bot.app or not admin_bot.app.updater:
        logger.error("🚨 Admin bot updater dead - restarting...")
        await admin_bot.stop()
        await admin_bot.start()
```

### Telegram Monitor Health
```python
# Already implemented in telegram_monitor.py
# Health check runs every 10 minutes
# Alerts if no messages in 10+ minutes
```

---

## Summary

**Most Common Fix**:
1. Set `ADMIN_TELEGRAM_USER_ID` in Railway
2. Restart bot
3. Send `/help` - should work

**Call Detection Fix**:
1. Verify `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` set
2. Check `TELEGRAM_GROUPS` configured
3. Delete `sentinel_session.session` if needed
4. Restart and check logs

**Still Broken?**:
- Check Railway logs for crash errors
- Test bot token with curl
- Verify account not banned by Telegram
- Check firewall/network isn't blocking
