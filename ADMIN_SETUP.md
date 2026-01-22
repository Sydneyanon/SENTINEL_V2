# Admin Bot Setup Guide

## Getting Your Telegram User ID

Your Telegram User ID is a unique number that identifies your account. You need this to enable admin commands.

### Method 1: Using @userinfobot (Easiest)

1. Open Telegram
2. Search for **@userinfobot**
3. Start a chat with the bot
4. The bot will immediately reply with your user ID
5. Copy the number (e.g., `123456789`)

### Method 2: Using @raw_data_bot

1. Open Telegram
2. Search for **@raw_data_bot**
3. Start a chat with the bot
4. Send any message
5. Look for `"id": 123456789` in the response
6. Copy that number

## Setting Up Admin Commands

### 1. Add Your User ID to Environment Variables

**Railway:**
1. Go to your Railway project
2. Click on **Variables**
3. Add a new variable:
   - Name: `ADMIN_TELEGRAM_USER_ID`
   - Value: Your user ID (just the number, no quotes)
4. Click **Deploy** to apply changes

**Local (.env.local):**
```bash
ADMIN_TELEGRAM_USER_ID=123456789
```

### 2. Redeploy

After adding the environment variable, the admin bot will start automatically on next deployment.

## Available Admin Commands

Send these commands to your Telegram bot (in a private message):

### Performance & Stats
- `/stats` - Overall system statistics
- `/performance` - Recent signal performance (last 48h)

### Monitoring
- `/active` - Currently tracked tokens (top 10)
- `/health` - System health check
- `/cache` - Telegram calls cache status

### Help
- `/help` - Show all available commands

## Security Features

✅ **Admin commands are locked** - Only your Telegram user ID can use /stats, /health, etc.

✅ **Unauthorized users are blocked** - Other users get no response (silent block)

✅ **Channel locked** - Bot only posts signals to YOUR configured channel (TELEGRAM_CHANNEL_ID)

✅ **Cannot be hijacked** - Even if someone adds your bot to their channel, it won't post there

### How Channel Security Works

The bot is hardcoded to only post to `TELEGRAM_CHANNEL_ID` from your environment variables. Even if someone:
- Gets your bot username and adds it to their channel
- Tries to trigger commands
- Has the bot token

The bot will ONLY post signals to YOUR channel. It verifies the channel ID before every post.

## Testing Admin Commands

1. Make sure `ADMIN_TELEGRAM_USER_ID` is set
2. Deploy your bot
3. Find your bot on Telegram (search for your bot username)
4. Send `/help` to see all commands
5. Try `/stats` to see system statistics

## Troubleshooting

**Bot doesn't respond to commands:**
1. Check Railway logs for these messages:
   - `✅ Admin bot initialized`
   - `✅ Admin bot polling started`
   - `Authorized user ID: YOUR_ID`

2. Verify `ADMIN_TELEGRAM_USER_ID` is set:
   - Go to Railway → Variables
   - Make sure it's your numeric ID (e.g., `123456789`)
   - NOT your @username

3. Test your user ID:
   - Message @userinfobot to confirm your ID
   - Make sure it matches what's in Railway

4. Check bot chat:
   - Make sure you're in a PRIVATE MESSAGE with the bot (not a group/channel)
   - Try `/start` first to wake up the bot
   - Then try `/help`

**"Admin bot disabled" in logs:**
- `ADMIN_TELEGRAM_USER_ID` is not set or is 0
- Add the variable and redeploy

**Commands work but show errors:**
- Check Railway logs for specific error messages
- Database connection might be down
- Performance tracker might not be initialized

**Someone else tries to use the bot:**
- They get no response (silent block)
- Only your user ID can see commands
- Bot won't reveal itself to unauthorized users

## Example Usage

```
You: /stats

Bot:
📊 PROMETHEUS STATISTICS

Tracking:
• Active tokens: 5
• Total tracked: 47
• Signals sent: 12

Signals (24h):
• Last 24h: 3
• All time: 12

Performance:
• Win rate: 75.0%
• Avg gain: 45.2%
• Best gain: 500.0%

Telegram Cache:
• Tokens called: 2

⏰ Updated: 2026-01-22 19:30 UTC
```
