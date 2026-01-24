# Telegram Scraper Integration - Implementation Summary

## Overview

Implemented **solana-token-scraper** integration with **Grok's enhanced variable scoring** system to detect alpha group calls and boost conviction scores.

## What Was Implemented

### 1. Webhook Endpoint (`main.py`)

**GET `/webhook/telegram-call`**

Receives contract addresses from solana-token-scraper when detected in Telegram groups.

**Features:**
- **Multiple mention tracking** - Stacks mentions from different groups
- **Group quality tracking** - Tracks which groups called the token
- **Auto-cleanup** - Removes calls older than 4 hours
- **Optional call-triggered tracking** - Can start tracking based on calls alone (disabled by default)

**URL Format:**
```
GET https://your-sentinel.railway.app/webhook/telegram-call?token={CA}&group={group_name}
```

**Example:**
```bash
# Single call
GET /webhook/telegram-call?token=GDfnLz8VKz...&group=bullish_bangers

# System tracks:
# - 1 mention from 1 group
# - Timestamp for age tracking
# - Group name for quality weighting
```

---

### 2. Variable Social Confirmation Scoring (`conviction_engine.py`)

**Phase 3.7: SOCIAL CONFIRMATION (TELEGRAM CALLS)**

Added **after** Twitter scoring, **before** holder concentration check.

**Gating Logic:**
- Only checks if `mid_total >= 60` (promising tokens only)
- Only applies to tokens **already tracked by KOLs** (social confirmation)
- Saves resources by not checking every random token

**Variable Scoring (0-15 points):**

| Intensity | Criteria | Points |
|-----------|----------|--------|
| **High** | 6+ mentions OR 3+ groups | +15 pts |
| **Medium** | 3-5 mentions OR growing buzz (2+ very recent) | +10 pts |
| **Low** | 1-2 mentions | +5 pts |

**Age Decay:**
- Calls >2 hours old: **50% reduction** (e.g., 10 pts → 5 pts)
- Prevents scoring stale calls that already faded

**Stacking Cap:**
- Total social score (Twitter + Telegram) capped at **25 pts max**
- Prevents over-scoring noisy hype
- Example: Twitter +15, Telegram +15 = 25 (not 30)

**Time Windows:**
- **Recent mentions**: Last 10 minutes
- **Very recent**: Last 5 minutes (for intensity check)

---

### 3. Configuration (`config.py`)

**Feature Flags:**
```python
ENABLE_TELEGRAM_SCRAPER = True  # Enable Telegram call tracking (FREE)
TELEGRAM_CALL_TRIGGER_ENABLED = False  # Start tracking on calls alone (disabled)
```

**Weights:**
```python
TELEGRAM_CONFIRMATION_WEIGHTS = {
    'high_intensity': 15,   # 6+ mentions OR 3+ groups
    'medium_intensity': 10, # 3-5 mentions OR growing buzz
    'low_intensity': 5,     # 1-2 mentions
    'age_decay': 0.5,       # 50% reduction if call >2 hours old
    'max_social_total': 25  # Cap total social (Twitter + Telegram)
}
```

**Optional: Call-Triggered Tracking Settings:**
```python
TELEGRAM_CALL_TRIGGER_SETTINGS = {
    'min_groups': 2,              # Require 2+ groups
    'time_window_seconds': 300,   # Within 5 minutes
    'base_score': 15,             # Lower initial score (riskier)
    'signal_threshold': 85        # Higher threshold (vs 80 for KOL)
}
```

---

### 4. Active Tracker Updates (`active_token_tracker.py`)

**Added Source Tracking:**
- `TokenState` now tracks `source` ('kol_buy' or 'telegram_call')
- `start_tracking()` accepts optional `source` parameter
- Supports future call-triggered tracking (when enabled)

---

## How It Works

### Standard Flow (KOL-Triggered + Telegram Confirmation)

```
1. Alpha groups call token on Telegram
   ├─ 12:00 PM: "Bullish Bangers" calls $TOKEN
   ├─ 12:02 PM: "Alpha Calls" calls $TOKEN
   └─ 12:04 PM: "Solana Gems" calls $TOKEN

2. Scraper sends webhook calls to SENTINEL
   └─ 3 mentions tracked in telegram_calls_cache

3. KOL buys the same token (12:06 PM)
   └─ SENTINEL starts tracking (KOL buy trigger)

4. Conviction scoring runs:
   ├─ Base score (KOL + volume + buyers): 68 pts
   ├─ Twitter check (bonding 65%, score 68): +10 pts → 78 pts
   ├─ Telegram check (mid_total 78 >= 60):
   │   ├─ Found 3 mentions from 3 groups (6 min ago)
   │   ├─ High intensity: +15 pts
   │   └─ Social cap check: 10 + 15 = 25 (OK, no cap)
   └─ Final: 93 pts → SIGNAL! 🚀

Without Telegram: Would have scored 78, MISSED THRESHOLD (80)
```

---

### Optional: Call-Triggered Tracking (Disabled by Default)

If `TELEGRAM_CALL_TRIGGER_ENABLED = True`:

```
1. Alpha groups call token
   ├─ 2+ groups mention within 5 minutes
   └─ SENTINEL starts tracking (call-triggered)

2. Lower initial score (15 pts base vs 40 for KOL)
   └─ Higher signal threshold (85 vs 80)

3. Auto-kill if no KOL buy confirmation within 5 min
   └─ Prevents false positives from low-quality calls

4. If KOL confirms: Upgrade to KOL-triggered
   └─ Full scoring applied
```

**Why Disabled by Default:**
- More rug exposure (calls without KOL confirmation)
- Higher noise ratio
- Best to use Telegram as **confirmation** (current setup) vs **trigger**

---

## Grok's Strategic Insights (Implemented)

### 1. ✅ Variable Scoring (Not Flat +10)

**Implemented:** 5-15 pts based on intensity
- Flat +10 too low for multi-group convergence
- High intensity (3+ groups) = strong signal → deserves +15
- Low intensity (1 group) = weak signal → only +5

### 2. ✅ Stacking with Cap

**Implemented:** Cap at 25 pts total social
- Allows Twitter + Telegram to stack
- Prevents over-scoring (max 25, not unlimited)
- Similar to LunarCrush sentiment stacking

### 3. ✅ Convergence Reward

**Implemented:** Social confirmation component
- Only applies to KOL-tracked tokens (convergence)
- Rewards alignment between on-chain (KOL buys) and off-chain (calls)
- High-confidence signal when both agree

### 4. ✅ Group Quality Tracking (Future-Ready)

**Implemented:** Group name tracking in cache
- Currently treats all groups equally
- Ready for future weighting (e.g., "Bullish Bangers" = 1.5x multiplier)
- Can backtest group quality and apply weights

### 5. ⚠️ Call-Triggered Tracking (Optional, Disabled)

**Implemented but disabled:**
- Code ready to enable
- Requires `TELEGRAM_CALL_TRIGGER_ENABLED = True`
- Recommended to keep disabled until backtest validates it

---

## Expected Impact

### Conservative Estimates (Grok's Analysis)

**Daily Usage:**
- 15-30 alpha calls per day across groups
- 5-10 calls align with KOL buys (quality convergence)
- 3-5 bonus signals per day (tokens at 75-79 → 80+)

**Hit Rate:**
- 30-50% of multi-group calls are legit
- Single-group calls: 10-20% legit (mostly noise)
- 2+ groups + KOL = 60-80% hit rate

**Accuracy Improvement:**
- **+20-30%** more signals when social aligns with on-chain
- Catches tokens with community momentum + smart money
- Similar to Maestro's call scraping strategy

**Signal Quality:**
- Higher quality signals (multi-source validation)
- Fewer missed gems (borderline tokens get boosted)
- Better timing (calls often precede KOL buys by 2-10 min)

---

## Cost

**Total:** $0/month (100% FREE)

- Telegram scraper: Free (open-source)
- Telegram API: Free (unlimited)
- No additional hosting (webhook only)
- No API credits (FREE component)

---

## Setup Instructions

### 1. Download solana-token-scraper

```bash
cd /opt
wget https://github.com/thelezend/solana-token-scraper/releases/latest/download/token-scraper-linux-x86_64
chmod +x token-scraper-linux-x86_64
```

### 2. Configure `settings.json`

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

Get credentials: https://my.telegram.org

### 3. Configure `filters.csv`

```csv
NAME,DISCORD_CHANNEL_ID,DISCORD_USER_ID,TELEGRAM_CHANNEL_ID,TOKEN_ENDPOINT_URL,MARKET_CAP
bullish-bangers,,,1234567890,https://your-sentinel.railway.app/webhook/telegram-call?group=bullish_bangers,
alpha-calls,,,9876543210,https://your-sentinel.railway.app/webhook/telegram-call?group=alpha_calls,
```

**Important:**
- Remove `-100` prefix from Telegram channel IDs
- Add `?group={group_name}` to URL for group tracking
- You must be a member of each group to monitor it

### 4. Run the Scraper

```bash
cd /opt
./token-scraper-linux-x86_64
```

First time: Enter phone number to authenticate Telegram

### 5. Run as Service (Production)

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
WorkingDirectory=/opt
ExecStart=/opt/token-scraper-linux-x86_64
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

---

## Monitoring

### Check Telegram Calls in SENTINEL Logs

```bash
# Look for Telegram call detections
grep "TELEGRAM CALL" prometheus.log

# Example output:
🔥 TELEGRAM CALL detected: GDfnLz8V... (group: bullish_bangers)
   📊 Total mentions: 3 from 2 group(s)
```

### Check Bonus Applications

```bash
# Look for bonus scoring
grep "TELEGRAM CALL BONUS" prometheus.log

# Example output:
🔥 TELEGRAM CALL BONUS: +15 pts
   3 mention(s) from 3 group(s) (4m ago)
```

### Check Social Cap Applications

```bash
# Look for cap enforcement
grep "Social cap applied" prometheus.log

# Example output:
⚖️ Social cap applied: reduced Telegram by 5 pts (max 25 total)
```

---

## Telegram Groups to Monitor

### Free Alpha Groups (Recommended to Start)

- Search Telegram for:
  - "Solana calls"
  - "Pump.fun alpha"
  - "Solana gems"
  - "Memecoin calls"

### Premium Groups (If You're In Them)

- Paid alpha groups (e.g., "Bullish's Bangers")
- Private KOL call channels
- Insider groups

**Finding Channel IDs:**
1. Open Telegram Web
2. Navigate to channel
3. Check URL: `https://web.telegram.org/k/#-1001234567890`
4. ID is `1234567890` (remove `-100` prefix)

---

## Configuration Options

### Enable Call-Triggered Tracking (Advanced)

```python
# config.py
TELEGRAM_CALL_TRIGGER_ENABLED = True  # ⚠️ Higher risk!
```

**Pros:**
- Catches tokens before KOL buys (earlier entry)
- More signals (20-30% increase)

**Cons:**
- More false positives (rug risk)
- Higher signal threshold (85 vs 80)
- Requires strong multi-group filter (2+ groups)

**Recommended:** Leave disabled until you backtest group quality

---

### Adjust Social Cap

```python
# config.py
TELEGRAM_CONFIRMATION_WEIGHTS = {
    ...
    'max_social_total': 30  # Increase cap to 30 (from 25)
}
```

**When to increase:**
- You're finding Telegram + Twitter alignment is very accurate
- Want to reward multi-source validation more heavily

---

## Troubleshooting

### "No Telegram calls detected"

**Possible causes:**
1. Scraper not running → Check: `systemctl status telegram-scraper`
2. Wrong channel IDs → Verify IDs in `filters.csv`
3. Not a member of groups → Join the groups first
4. Wrong webhook URL → Check SENTINEL URL in `filters.csv`

### "Telegram bonus not applied"

**Possible causes:**
1. `ENABLE_TELEGRAM_SCRAPER = False` → Check `config.py`
2. Mid score too low (<60) → System gates behind mid_total >= 60
3. Call too old (>4 hours) → Cache auto-cleaned
4. Token not tracked by KOL → Only applies to KOL-tracked tokens

### "Social cap always applied"

**Expected behavior:**
- If Twitter + Telegram both give max points (15 + 15 = 30)
- Cap reduces to 25 (excess removed from Telegram)
- This prevents over-scoring noisy hype

---

## Future Enhancements

### 1. Group Quality Weighting

Track historical accuracy per group:

```python
GROUP_QUALITY_WEIGHTS = {
    'bullish_bangers': 1.5,      # 75% hit rate → 1.5x multiplier
    'alpha_calls': 1.2,          # 60% hit rate → 1.2x
    'random_shills': 0.5         # 25% hit rate → 0.5x penalty
}
```

Apply multiplier to Telegram score:
```python
base_score = 10  # Medium intensity
group = "bullish_bangers"
multiplier = GROUP_QUALITY_WEIGHTS.get(group, 1.0)
final_score = int(base_score * multiplier)  # 10 * 1.5 = 15
```

### 2. Multi-Call Blacklist

Auto-ignore wallets that spam calls:

```python
if call_count_last_hour > 20:  # Wallet spamming
    blacklist_group(group)
    logger.warning(f"🚫 Blacklisted {group} (spam detected)")
```

### 3. ML-Based Call Quality Scoring

Train model on historical data:
- Features: Group, time of day, mention count, call age
- Target: Did KOL buy within 1 hour? Did it pump 2x+?
- Output: Quality score (0-100) for each call

---

## Summary

✅ **Implemented:**
- Webhook endpoint for Telegram scraper integration
- Variable scoring (5-15 pts) based on mention intensity
- Age decay for stale calls
- Stacking cap (max 25 pts total social)
- Group quality tracking (ready for weighting)
- Optional call-triggered tracking (disabled by default)

✅ **Benefits:**
- 100% FREE (no API costs)
- Catches multi-group convergence = high-confidence signals
- Rewards social + on-chain alignment
- +20-30% more signals when calls align with KOL buys

✅ **Next Steps:**
1. Download and configure solana-token-scraper
2. Join 5-10 alpha groups on Telegram
3. Add group IDs to `filters.csv`
4. Run scraper and monitor logs
5. Watch for "TELEGRAM CALL BONUS" in conviction scoring

**Ready to deploy!** This adds real alpha group intelligence to SENTINEL for FREE.
