# Twitter Integration Strategy

## Overview

SENTINEL now uses Twitter API (free tier) to boost conviction scores for high-potential tokens.

**Goal:** Use limited API calls (~3/day) to detect Twitter buzz on tokens that are already showing strong signals.

---

## API Limits

**Free Tier:** ~100 calls/month = **3 calls per day**

**Strategy:** Ultra-selective checking with aggressive caching

---

## When Twitter Gets Checked

Twitter is only checked when **ALL** conditions are met:

1. ✅ **Bonding Curve:** Token is at **60%+ bonding** (close to graduation)
2. ✅ **Conviction Score:** Token already has **70+ conviction** (promising)
3. ✅ **Not Cached:** Token hasn't been checked in last 6 hours
4. ✅ **Rate Limit:** Haven't hit daily limit (3 calls/day)

### Example Flow

```
KOL buys token → Start tracking

Token at 40% bonding, 50 conviction
└─ Twitter: SKIP (bonding too low)

Token at 65% bonding, 60 conviction
└─ Twitter: SKIP (conviction too low)

Token at 70% bonding, 75 conviction
└─ Twitter: ✅ CHECK! (both thresholds met)
   ├─ Found 8 mentions, 120 engagement
   └─ +10 points → Final score: 85/100 → SIGNAL! 🚀
```

---

## Scoring Breakdown

Twitter adds **0-15 points** based on engagement:

| Engagement Level | Points | Criteria |
|-----------------|--------|----------|
| **High Buzz** | +15 | 5+ mentions, 10+ avg engagement |
| **Medium Buzz** | +10 | 3+ mentions |
| **Low Buzz** | +5 | 1+ mentions |
| **Viral Tweet** | +12 | Single tweet with 100+ likes |
| **No Buzz** | 0 | No mentions found |

---

## What Twitter Checks

For each token symbol (e.g., $BONK), searches Twitter for:

```
Query: "$BONK (crypto OR token OR solana) -is:retweet"
```

**Metrics tracked:**
- Mention count (recent tweets mentioning token)
- Total engagement (likes + retweets + replies)
- Average engagement per tweet
- Top tweet likes (viral detection)

**Cache:** Results cached for **6 hours** per token

---

## Expected Usage

### Daily Usage (Conservative)

```
KOLs buy ~10-20 tokens per day
└─ ~5-10 reach 60%+ bonding
   └─ ~1-3 have 70+ conviction at that point
      └─ Twitter checks: 1-3 per day ✅
```

**Monthly:** 30-90 calls (well under 100 limit)

---

## Smart Rate Limiting

**Built-in protection:**

1. **Daily limit:** 3 calls per day (hardcoded)
2. **Resets:** Automatically resets every 24 hours
3. **Cache:** 6-hour cache prevents duplicate checks
4. **Logging:** Shows API usage: `"📊 Twitter API calls today: 2/3"`

If limit hit:
```
🚨 Twitter API daily limit reached (3/3)
└─ Skips Twitter check
└─ Token still scored without Twitter boost
└─ Resets tomorrow
```

---

## Configuration

### Environment Variable (Required)

```bash
export TWITTER_BEARER_TOKEN="your_bearer_token_here"
```

Get token at: https://developer.twitter.com/

### Config Flags

```python
# config.py
ENABLE_TWITTER = True        # Enable Twitter checks
ENABLE_LUNARCRUSH = False    # Disabled (using Twitter only)
ENABLE_NARRATIVES = False    # Disabled (using Twitter only)
```

### Thresholds (in code)

```python
# scoring/conviction_engine.py
if config.ENABLE_TWITTER and bonding_pct >= 60 and mid_total >= 70:
    # Check Twitter
```

**Adjust these thresholds if needed:**
- Lower `bonding_pct` to check earlier (more API calls)
- Raise `mid_total` to be more selective (fewer API calls)

---

## Monitoring

### Check Rate Limit Status

```python
from twitter_fetcher import get_twitter_fetcher

twitter = get_twitter_fetcher()
status = twitter.get_rate_limit_status()

print(f"Calls today: {status['daily_calls']}/{status['daily_limit']}")
print(f"Remaining: {status['remaining']}")
print(f"Resets at: {status['reset_at']}")
```

### Logs

Look for these in logs:

```
✅ Positive signal:
🐦 Checking Twitter (bonding: 75%, score: 72)...
🐦 Twitter: +10 points
🔥 BUZZ: 8 mentions, 120 engagement

❌ No buzz:
🐦 Checking Twitter (bonding: 68%, score: 71)...
🐦 Twitter: No buzz detected

⏭️ Skipped (thresholds not met):
(no log - silently skipped)

🚨 Rate limit hit:
🚨 Twitter API daily limit reached (3/3)
```

---

## Cost

**Total:** $0/month (100% FREE)

No need for:
- ❌ LunarCrush ($24/mo)
- ❌ Twitter Basic tier ($100/mo)
- ❌ Additional APIs

---

## Impact

### Conservative Estimate

- **Usage:** 1-3 tokens checked per day
- **Boost:** +5-15 points per token checked
- **Value:** Detects early Twitter buzz before token graduates

### Best Case

Token at 70% bonding with 72 conviction:
- Base: 72 pts
- Twitter finds buzz: +10 pts
- **Final: 82 pts → SIGNAL!** (threshold: 80)

Without Twitter: Would have missed this signal.

---

## Troubleshooting

### "Twitter API daily limit reached"
- Normal - resets in 24 hours
- Token still scored without Twitter boost
- Adjust thresholds if you want to save calls

### "No Twitter mentions"
- Normal for new/small tokens
- Only adds points if mentions found
- Not a penalty - just 0 points

### "Twitter API error 401"
- Check `TWITTER_BEARER_TOKEN` is set correctly
- Verify token at https://developer.twitter.com/

### Want more/fewer checks?

Adjust thresholds in `scoring/conviction_engine.py`:

```python
# More checks (4-5 per day):
if config.ENABLE_TWITTER and bonding_pct >= 50 and mid_total >= 60:

# Fewer checks (1-2 per day):
if config.ENABLE_TWITTER and bonding_pct >= 70 and mid_total >= 75:

# Current (2-3 per day):
if config.ENABLE_TWITTER and bonding_pct >= 60 and mid_total >= 70:
```

---

## Future Enhancements

When ready to scale:

1. **Twitter Basic ($100/mo):** 10,000 calls/month
   - Check more tokens (lower thresholds)
   - Check earlier (50% bonding)

2. **LunarCrush ($24/mo):** Cross-platform sentiment
   - Add back for +20 pts
   - 2,000 calls/day limit

3. **Ralph Agent:** Autonomous narrative discovery
   - Monitor Twitter 24/7 for trending topics
   - Auto-update narratives

For now, stick with **free tier + smart gating** = maximum value per API call.
