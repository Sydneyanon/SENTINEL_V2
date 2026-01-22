# Telegram Scraper Integration Guide

## Overview

Integrate [solana-token-scraper](https://github.com/thelezend/solana-token-scraper) to detect tokens from Telegram/Discord alpha groups before or as KOLs buy them.

## How It Works

```
Alpha group posts token CA
└─ Scraper detects CA
   └─ Sends GET to SENTINEL webhook
      └─ SENTINEL adds +10 pts "Telegram call bonus"
         └─ When KOL buys same token → faster signal!
```

## Installation

### 1. Download Scraper

```bash
cd /opt
wget https://github.com/thelezend/solana-token-scraper/releases/latest/download/token-scraper-linux-x86_64
chmod +x token-scraper-linux-x86_64
```

### 2. Create Configuration

**settings.json:**
```json
{
    "telegram": {
        "api_id": "YOUR_TELEGRAM_API_ID",
        "api_hash": "YOUR_TELEGRAM_API_HASH"
    },
    "solana": {
        "rpc_url": "https://api.mainnet-beta.solana.com"
    }
}
```

Get Telegram credentials: https://my.telegram.org

**filters.csv:**
```csv
NAME,DISCORD_CHANNEL_ID,DISCORD_USER_ID,TELEGRAM_CHANNEL_ID,TOKEN_ENDPOINT_URL,MARKET_CAP
alpha-calls,,,1234567890,https://your-sentinel-url.railway.app/webhook/telegram-call,
premium-calls,,,9876543210,https://your-sentinel-url.railway.app/webhook/telegram-call,50000
```

**Replace:**
- `1234567890` with actual Telegram channel IDs
- `your-sentinel-url.railway.app` with your SENTINEL deployment URL

**Finding Telegram Channel IDs:**
1. Open Telegram Web
2. Navigate to channel
3. Check URL: `https://web.telegram.org/k/#-1001234567890`
4. ID is `1234567890` (remove `-100` prefix)

### 3. Run Scraper

```bash
cd /opt
./token-scraper-linux-x86_64
```

First time: Enter phone number to authenticate Telegram

### 4. Run as Service (Production)

```bash
sudo nano /etc/systemd/system/telegram-scraper.service
```

```ini
[Unit]
Description=Telegram Token Scraper
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/telegram-scraper
ExecStart=/opt/telegram-scraper/token-scraper-linux-x86_64
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-scraper
sudo systemctl start telegram-scraper
```

## SENTINEL Integration

### Add Webhook Endpoint

Add to `main.py`:

```python
from datetime import datetime, timedelta

# Hot tokens cache (tokens called in Telegram)
telegram_calls_cache = {}

@app.get("/webhook/telegram-call")
async def telegram_call_webhook(token: str):
    """
    Webhook for Telegram scraper
    Receives CA when detected in alpha groups
    """
    try:
        logger.info(f"🔥 TELEGRAM CALL detected: {token}")

        # Add to cache with timestamp
        telegram_calls_cache[token] = {
            'detected_at': datetime.utcnow(),
            'source': 'telegram_alpha'
        }

        # Cleanup old entries (>4 hours)
        cutoff = datetime.utcnow() - timedelta(hours=4)
        telegram_calls_cache = {
            k: v for k, v in telegram_calls_cache.items()
            if v['detected_at'] > cutoff
        }

        # Optional: Start light tracking
        # await active_tracker.start_tracking(token)

        return {"status": "received", "token": token}

    except Exception as e:
        logger.error(f"Error processing Telegram call: {e}")
        return {"status": "error", "message": str(e)}
```

### Add Scoring Bonus

Modify `scoring/conviction_engine.py`:

```python
async def calculate_conviction(self, token_data, ...):
    # ... existing scoring ...

    # After calculating mid_total, check for Telegram call
    token_address = token_data.get('token_address')

    # Import from main
    from main import telegram_calls_cache

    if token_address in telegram_calls_cache:
        call_data = telegram_calls_cache[token_address]
        call_age = datetime.utcnow() - call_data['detected_at']

        if call_age < timedelta(hours=2):  # Recent call (within 2h)
            telegram_bonus = 10
            mid_total += telegram_bonus
            logger.info(f"   🔥 TELEGRAM CALL BONUS: +{telegram_bonus} pts (called {call_age.seconds//60}m ago)")

    # ... continue with Twitter check, etc.
```

## Configuration

### Telegram Call Bonus Weight

Add to `config.py`:

```python
# Telegram Alpha Call Bonus (0-10 pts)
TELEGRAM_CALL_BONUS = 10  # Points added if token was called in alpha group
TELEGRAM_CALL_MAX_AGE_HOURS = 2  # Only count if called within 2 hours
```

## Expected Impact

### Conservative Estimate
- **Usage:** 5-10 tokens called per day in alpha groups
- **Hit rate:** 30-50% of calls are legit (others are rugs/fades)
- **Boost:** +10 pts when KOL buys within 2 hours of call
- **Value:** Pushes borderline tokens (70-75) over 80 threshold

### Example Flow

```
12:00 PM: Token called in Telegram alpha group
└─ Scraper detects CA → sends to SENTINEL
   └─ Added to telegram_calls_cache

12:05 PM: KOL buys same token
└─ SENTINEL starts tracking (KOL buy trigger)
   ├─ Base score: 70 pts (KOL + buyers + volume)
   ├─ Telegram bonus: +10 pts (called 5 min ago)
   └─ Total: 80 pts → SIGNAL! 🚀

Without Telegram: Would have scored 70, missed threshold
```

## Monitoring

### Check Scraper Logs

```bash
tail -f /opt/telegram-scraper/logs/latest.log
```

### Check SENTINEL Logs

```bash
# Look for Telegram call detections
grep "TELEGRAM CALL" prometheus.log

# Check bonus applications
grep "TELEGRAM CALL BONUS" prometheus.log
```

## Telegram Groups to Monitor

### Free Alpha Groups
- Pump.fun calls (public channels)
- Solana alpha groups
- Meme coin call channels

### Premium Groups (if you're in them)
- Paid alpha groups
- Private KOL call channels
- Insider groups

**Finding channels:**
1. Search Telegram for "Solana calls", "pump.fun", "solana alpha"
2. Join a few groups
3. Add their IDs to `filters.csv`

## Cost

**Total:** $0/month (100% FREE)

- Telegram scraper: Free, open-source
- Telegram API: Free (unlimited)
- No additional hosting (runs alongside SENTINEL)

## Security Notes

1. **Telegram TOS:** Using API for bots is allowed (unlike Discord)
2. **API credentials:** Keep `settings.json` private
3. **Session file:** `scraper.session` contains auth token (keep secure)

## Troubleshooting

### "Failed to authenticate Telegram"
- Check `api_id` and `api_hash` in `settings.json`
- Re-run and enter phone number + code

### "Channel ID not found"
- Remove `-100` prefix from Telegram channel ID
- Ensure you're a member of the channel

### "No tokens detected"
- Verify groups are posting CAs
- Check scraper logs for errors
- Test with known call channel

### "Webhook not receiving calls"
- Check SENTINEL URL is correct in `filters.csv`
- Ensure `/webhook/telegram-call` endpoint exists
- Check firewall/network settings

## Performance

### Expected Volume
- Free alpha groups: 10-20 calls/day
- Premium groups: 5-10 calls/day
- Total: 15-30 Telegram calls/day

### Memory Usage
- Scraper: ~50MB RAM
- Cache in SENTINEL: ~1KB per token
- Minimal overhead

### Network Usage
- Telegram API: <1MB/hour
- Webhook calls: <100KB/day
- Negligible bandwidth

## Scaling

If you join more alpha groups:

1. **Add to filters.csv:**
   ```csv
   group1,,,123456,https://sentinel/webhook/telegram-call,
   group2,,,789012,https://sentinel/webhook/telegram-call,
   ```

2. **Increase cache cleanup:**
   ```python
   # Keep last 6 hours instead of 4
   cutoff = datetime.utcnow() - timedelta(hours=6)
   ```

3. **Add filtering:**
   ```python
   # Only cache if market cap > $10k
   TELEGRAM_CALL_MIN_MCAP = 10000
   ```

## Alternative: Proactive Tracking

Instead of just caching, start tracking immediately:

```python
@app.get("/webhook/telegram-call")
async def telegram_call_webhook(token: str):
    logger.info(f"🔥 TELEGRAM CALL: {token}")

    # Start tracking immediately (aggressive)
    await active_tracker.start_tracking(token)

    # Still add to cache for bonus
    telegram_calls_cache[token] = {
        'detected_at': datetime.utcnow(),
        'source': 'telegram_alpha'
    }

    return {"status": "tracking", "token": token}
```

**Pros:** Catches tokens before KOL buys
**Cons:** More API usage, more false positives

## Future Enhancements

1. **Discord support:** Add Discord alpha groups
2. **Call quality scoring:** Track which groups have best hit rate
3. **Blacklist:** Auto-ignore known rug callers
4. **ML filtering:** Score calls based on historical accuracy

---

**Ready to deploy!** This adds real alpha group intelligence to SENTINEL for FREE.
