# Social Intelligence Integration

## Overview

SENTINEL now integrates **3 social intelligence layers** to boost conviction scoring:

1. **Narrative Detection** - Identifies trending themes (AI, DeSci, RWA, etc.)
2. **LunarCrush** - Aggregated social sentiment across Twitter, Reddit, etc.
3. **Twitter API** - Direct Twitter mentions and engagement (free tier)

## Conviction Score Impact

### Total Possible Points: **0-135+**

| Signal | Points | Description |
|--------|--------|-------------|
| Smart Wallet Activity | 0-40 | KOL buys and timing |
| **Narrative Detection** | **0-25** | Hot narrative matches |
| Unique Buyers | 0-15 | Distribution quality |
| Volume Velocity | 0-10 | Trading activity |
| Price Momentum | 0-10 | Price action |
| **LunarCrush Social** | **0-20** | Cross-platform sentiment |
| **Twitter Buzz** | **0-15** | Direct Twitter engagement |
| Bundle Penalty | -40 to 0 | Sniper detection |
| Holder Concentration | -40 to 0 | Whale concentration |

## 1. Narrative Detection (0-25 pts)

Identifies tokens matching trending narratives:

### 2026 Hot Narratives
- **AI Agents** (weight: 25) - ai, agent, autonomous, neural, gpt, bot, llm
- **DeSci** (weight: 22) - science, research, biotech, lab, molecule
- **RWA** (weight: 20) - real world assets, tokenized, treasury, bond
- **Privacy/ZK** (weight: 18) - privacy, zk, zero knowledge, anonymous
- **DeFi** (weight: 15) - defi, yield, stake, farm, swap
- **Mobile/Saga** (weight: 15) - mobile, saga, phone, seeker
- **GameFi** (weight: 12) - game, play, nft, metaverse, gaming
- **Meme** (weight: 10) - meme, pepe, doge, shiba, wojak

### Scoring Logic
- **Hot narrative match**: +20 pts
- **Fresh narrative** (<48h): +10 pts
- **Multiple narratives**: +5 pts
- **Max**: 35 pts (capped at 25 in config)

### Configuration
```python
# config.py
ENABLE_NARRATIVES = True

HOT_NARRATIVES = {
    'ai_agent': {
        'keywords': ['ai', 'agent', 'autonomous', ...],
        'weight': 25,
        'active': True
    },
    # ... more narratives
}
```

## 2. LunarCrush Integration (0-20 pts)

Aggregated social sentiment from Twitter, Reddit, news, etc.

### Scoring Breakdown
- **Trending in top 20**: +10 pts
- **Trending in top 50**: +7 pts
- **Trending in top 100**: +3 pts
- **Bullish sentiment** (≥4.0): +5 pts
- **Moderate sentiment** (≥3.5): +3 pts
- **Social volume spike** (+100%): +5 pts
- **Social volume growth** (+50%): +3 pts

### Metrics Tracked
- Galaxy Score (0-100 proprietary score)
- Alt Rank (overall ranking)
- Sentiment (1-5 scale)
- Social Volume & 24h change
- Tweet/Reddit/News volume
- Social dominance & correlation

### API Setup
1. Sign up: https://lunarcrush.com/
2. Get API key (pricing: $50-200/mo depending on tier)
3. Set env var: `LUNARCRUSH_API_KEY=your_key`

### Configuration
```python
# config.py
ENABLE_LUNARCRUSH = True

LUNARCRUSH_WEIGHTS = {
    'trending_top20': 10,
    'sentiment_high': 5,
    'volume_spike': 5
}
```

## 3. Twitter API Integration (0-15 pts)

Direct Twitter mentions and engagement analysis.

### Free Tier Optimization
- **Limit**: 1,500 tweets/month (~50/day)
- **Strategy**:
  - 2-hour caching per token
  - Only check tokens with score ≥60
  - Daily limit: 45 calls (safety buffer)

### Scoring Breakdown
- **High buzz** (5+ mentions, 10+ avg engagement): +15 pts
- **Medium buzz** (3+ mentions): +10 pts
- **Low buzz** (1+ mentions): +5 pts
- **Viral tweet** (100+ likes): +12 pts (minimum)

### Metrics Tracked
- Mention count (recent tweets mentioning token)
- Total engagement (likes + retweets + replies)
- Average engagement per tweet
- Top tweet likes (viral detection)
- Recent growth (mentions increasing)

### API Setup

#### Free Tier (Recommended)
1. Sign up: https://developer.twitter.com/
2. Create app → Get Bearer Token
3. **Limit**: 1,500 tweets/month
4. Set env var: `TWITTER_BEARER_TOKEN=your_bearer_token`

#### Basic Tier ($100/mo)
- **Limit**: 10,000 tweets/month
- Better for higher volume

### Configuration
```python
# config.py
ENABLE_TWITTER = True

TWITTER_WEIGHTS = {
    'high_buzz': 15,
    'medium_buzz': 10,
    'low_buzz': 5,
    'viral_tweet': 12
}
```

## Execution Flow

```
1. KOL buys token
   └→ Active Token Tracker starts monitoring

2. Token hits scoring threshold
   └→ Conviction Engine analyzes:
      ├→ Smart Wallet Activity (0-40 pts)
      ├→ Narrative Detection (0-25 pts) ← NEW
      ├→ Unique Buyers (0-15 pts)
      ├→ Volume & Momentum (0-20 pts)
      ├→ Bundle Detection (penalty)
      └→ If score ≥ 60:
         ├→ LunarCrush Social (0-20 pts) ← NEW
         └→ Twitter Buzz (0-15 pts) ← NEW

3. Final Score ≥ 80 (pre-grad) or ≥ 75 (post-grad)
   └→ Send Telegram Signal! 🚀
```

## Cost Analysis

| Service | Cost | Usage |
|---------|------|-------|
| Narrative Detection | **FREE** | Local keyword matching |
| LunarCrush | **$50-200/mo** | Unlimited API calls |
| Twitter Free Tier | **FREE** | 1,500 tweets/mo (~50/day) |
| Twitter Basic | **$100/mo** | 10,000 tweets/mo |
| **Total (Free Tier)** | **$50-200/mo** | LunarCrush only |

## Expected Impact

### Conservative Estimate
- **+5-15 pts** per token on average
- **+20% signal quality** (better narrative alignment)
- **+10% catch rate** (Twitter buzz early detection)

### Best Case
- Token matches hot narrative: **+25 pts**
- Trending on LunarCrush: **+20 pts**
- Twitter buzz detected: **+15 pts**
- **Total boost: +60 pts** 🚀

Example: Token with 70 base score → 130 final score (high conviction!)

## Environment Variables Required

```bash
# Required for LunarCrush (recommended)
LUNARCRUSH_API_KEY=your_lunarcrush_key

# Required for Twitter (optional but valuable)
TWITTER_BEARER_TOKEN=your_twitter_bearer_token
```

## Monitoring

Check logs for social intelligence signals:

```
🔍 Analyzing $TOKEN...
   👑 Smart Wallets: 30 points
   🎯 Narratives: 25 points (AI Agent)
   👥 Unique Buyers (45): 8 points
   📊 Volume: 10 points
   🚀 Momentum: 5 points
   💎 MID SCORE: 78/100
   🌙 LunarCrush: +15 points (Trending #32, Sentiment 4.2)
   🐦 Twitter: +10 points (6 mentions, 87 engagement)
   🎯 FINAL CONVICTION: 103/100
   ✅ SIGNAL!
```

## Rate Limit Status

Twitter API provides rate limit tracking:

```python
from twitter_fetcher import get_twitter_fetcher

twitter = get_twitter_fetcher()
status = twitter.get_rate_limit_status()

# {
#   'daily_calls': 23,
#   'daily_limit': 45,
#   'remaining': 22,
#   'reset_at': datetime(...)
# }
```

## Future Enhancements (Ralph)

Phase 2 will add autonomous narrative discovery:

- **Ralph Twitter Monitor**: Autonomous agent scanning Twitter 24/7
- **Auto-update narratives**: Discovers emerging trends before they're mainstream
- **Telegram group monitoring**: Track alpha in private groups
- **Reddit sentiment**: Expand beyond Twitter

For now, stick with manual narrative config + LunarCrush + Twitter free tier.

## Testing

Test the integration with a known token:

```python
from conviction_engine import ConvictionEngine
from twitter_fetcher import get_twitter_fetcher
from lunarcrush_fetcher import get_lunarcrush_fetcher

# Test Twitter
twitter = get_twitter_fetcher()
metrics = await twitter.get_token_twitter_metrics("BONK")
print(f"Twitter: {metrics}")

# Test LunarCrush
lunar = get_lunarcrush_fetcher()
metrics = await lunar.get_coin_social_metrics("BONK")
print(f"LunarCrush: {metrics}")
```

## Troubleshooting

### "Twitter API error 401"
- Check `TWITTER_BEARER_TOKEN` is set correctly
- Verify token on https://developer.twitter.com/

### "LunarCrush API error 403"
- Check `LUNARCRUSH_API_KEY` is set
- Verify subscription is active

### "No Twitter mentions"
- Normal for new/small tokens
- Only adds points if mentions found
- Check rate limit status

### "Daily limit reached"
- Twitter free tier exhausted (45 calls)
- Resets next day
- Consider upgrading to Basic ($100/mo)

## Questions?

See main README or check logs for detailed scoring breakdowns.
