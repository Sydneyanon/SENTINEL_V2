# RAILWAY TELEGRAM FIX GUIDE

## The Problem

Bot is properly configured in Telegram channel but Railway shows "Chat not found" error.

**Root Cause:** Environment variables not properly set in Railway.

## Fix: Check Railway Environment Variables

### Step 1: Get Your Bot Token

1. Open Telegram and search for `@BotFather`
2. Send `/mybots`
3. Select your bot: `@prometheus_elitebot`
4. Click "API Token"
5. Copy the full token (looks like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Step 2: Get Your Channel ID

Your channel ID is: `-1003380850002`

### Step 3: Set Environment Variables in Railway

1. Go to Railway dashboard: https://railway.app/
2. Select your project: `SENTINEL_V2`
3. Click on your service
4. Go to **"Variables"** tab
5. Click **"+ New Variable"**

Add these TWO variables:

**Variable 1:**
- Name: `TELEGRAM_BOT_TOKEN`
- Value: `YOUR_FULL_BOT_TOKEN_HERE` (paste the token from step 1)

**Variable 2:**
- Name: `TELEGRAM_CHANNEL_ID`
- Value: `-1003380850002`

### Step 4: Redeploy

After adding both variables, Railway will automatically redeploy your service.

## Verify It Works

Once redeployed, check logs for:

```
✅ Telegram bot initialized: @prometheus_elitebot
```

If you see this, the bot is working!

## Test Message

You can also run this script to test:

```bash
python test_telegram_bot.py
```

This will:
1. Check if bot token is valid
2. Check if bot can see the channel
3. Send a test message

## Common Mistakes

### ❌ Wrong: Token has extra spaces
```
TELEGRAM_BOT_TOKEN = " 1234567890:ABC... "  # Has spaces!
```

### ✅ Correct: Clean token
```
TELEGRAM_BOT_TOKEN = 1234567890:ABC...
```

### ❌ Wrong: Channel ID missing minus sign
```
TELEGRAM_CHANNEL_ID = 1003380850002  # Missing "-"!
```

### ✅ Correct: Has minus sign
```
TELEGRAM_CHANNEL_ID = -1003380850002
```

## Current Status

- ✅ Bot exists: `@prometheus_elitebot`
- ✅ Bot in channel with admin permissions
- ✅ Bot has "Post Messages" permission
- ❌ Environment variables not set in Railway (NEEDS FIX)

## Expected Behavior After Fix

Once environment variables are set correctly:

1. Bot will initialize on startup
2. Logs will show: `✅ Telegram bot initialized: @prometheus_elitebot`
3. When a signal fires, you'll see a message like:

```
🔥 PROMETHEUS SIGNAL 🔥🔥🔥🔥

$SYMBOL
Conviction: 85/100

💰 Price: $0.00001234
💎 MCap: $123,456
💧 Liquidity: $45,678
👥 Holders: 89
📊 Bonding: 67.5%

👑 Elite Trader Activity:
👑 Top KOL (75% WR, $50k PnL) - 2m ago

🔗 DexScreener | Birdeye | Pump.fun

[token_address]

⚠️ DYOR - Not financial advice
🔥 The fire spreads.
```

## Still Not Working?

If you set the variables correctly and it still fails:

1. Check Railway logs for exact error message
2. Run `test_telegram_bot.py` locally with the same credentials
3. Verify bot hasn't been removed from channel
4. Try regenerating bot token in @BotFather
