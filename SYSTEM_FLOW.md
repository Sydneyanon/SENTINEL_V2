# SENTINEL System Flow & Configuration

## Overview
SENTINEL tracks tokens bought by elite KOL wallets, monitors them in real-time, and sends Telegram signals when conviction thresholds are met.

---

## Complete Token Flow

### Stage 1: KOL Buy Detection
```
1. KOL wallet buys token
   └─ Helius webhook triggers
      └─ Start tracking token in ActiveTokenTracker
         ├─ Initial conviction score: 0
         └─ Begin aggressive polling
```

### Stage 2: Real-Time Monitoring & Scoring

**Polling Strategy:**
```
First 2 minutes: Poll every 5 seconds (fast)
After 2 minutes:  Poll every 15 seconds (normal)
If stuck:         Poll every 30 seconds (slow)
Max age:          Stop polling after 30 minutes
```

**Each Poll Cycle:**
```
1. Fetch token data (Birdseye API)
   ├─ Price, market cap, liquidity
   ├─ Bonding curve progress
   └─ Holder count

2. Calculate Conviction Score (0-100+)

   BASE SCORING (0-65 points):
   ├─ Smart Wallet Activity (0-40 pts)
   │  └─ 10 pts per KOL that bought
   │
   ├─ Volume Velocity (0-10 pts)
   │  ├─ Spiking (2x expected): +10 pts
   │  └─ Growing (1.25x expected): +5 pts
   │
   ├─ Price Momentum (0-10 pts)
   │  ├─ Very strong (+50% in 5min): +10 pts
   │  └─ Strong (+20% in 5min): +5 pts
   │
   └─ Unique Buyers (0-15 pts)
      ├─ 100+ buyers: +15 pts
      ├─ 70-99 buyers: +12 pts
      ├─ 40-69 buyers: +8 pts
      └─ 20-39 buyers: +5 pts

   RUG DETECTION (penalties):
   ├─ Bundle Detection (0 to -40 pts)
   │  ├─ 4-10 same-block txs: -10 pts
   │  ├─ 11-20 same-block txs: -25 pts
   │  └─ 21+ same-block txs: -40 pts
   │
   └─ Holder Concentration (0 to -40 pts)
      ├─ Top 10 hold >80%: -999 pts (HARD DROP)
      ├─ Top 10 hold >70%: -35 pts
      ├─ Top 10 hold >50%: -20 pts
      └─ Top 10 hold >40%: -10 pts

   SOCIAL INTELLIGENCE (if enabled):
   └─ Twitter Buzz (0-15 pts) - CONDITIONAL
      └─ Only checks if:
         ├─ Bonding ≥ 60%
         ├─ Conviction ≥ 70
         ├─ Not cached (24h)
         └─ Rate limit OK (5 calls/week)

      Scoring:
      ├─ High buzz (5+ mentions, 10+ avg engagement): +15 pts
      ├─ Medium buzz (3+ mentions): +10 pts
      ├─ Low buzz (1+ mentions): +5 pts
      └─ Viral tweet (100+ likes): +12 pts

3. Apply Early Kill Switch (if enabled)
   └─ If bonding ≥ 50% AND < 5 new buyers in 2 minutes:
      └─ STOP TRACKING (token is dead)

4. Check Signal Thresholds

   PRE-GRADUATION (token still on bonding curve):
   └─ If conviction ≥ 80:
      └─ SEND TELEGRAM SIGNAL! 🚀

   POST-GRADUATION (token graduated to Raydium):
   └─ If conviction ≥ 75:
      └─ SEND TELEGRAM SIGNAL! 🚀
```

### Stage 3: Exit Rules

**Remove token from tracking if:**
```
1. Signal sent + tracked > 1 hour
   └─ Job done, stop wasting resources

2. Tracked > 24 hours with no signal
   └─ Token failed, give up

3. Conviction < 30 for > 30 minutes
   └─ Low conviction, not worth tracking

4. Early kill switch triggered
   └─ No new buyers, token is dead
```

---

## Key Thresholds Summary

| Stage | Threshold | Purpose |
|-------|-----------|---------|
| **Twitter Check** | 60% bonding + 70 conviction | When to check Twitter API |
| **Pre-Grad Signal** | 80 conviction | Send Telegram alert (on bonding curve) |
| **Post-Grad Signal** | 75 conviction | Send Telegram alert (graduated) |
| **Early Kill** | 50% bonding + <5 buyers/2min | Stop tracking dead token |
| **Cleanup** | <30 conviction for 30min | Remove low-conviction token |

---

## Twitter Integration Details

### API Limits (Free Tier)
- **100 tweet READS per month** (NOT 100 calls)
- With `max_results=5`: 100 ÷ 5 = **20 API calls/month**
- That's **~5 calls per week**
- **24-hour cache** per token

### When Twitter Checks
```
Token at 62% bonding, 72 conviction:
├─ Bonding check: 62% ≥ 60% ✅
├─ Conviction check: 72 ≥ 70 ✅
├─ Cache check: Not checked in 24h ✅
├─ Rate limit: 3/5 calls used ✅
└─ TWITTER CHECK! 🐦
   ├─ Search: "$TOKEN (crypto OR token OR solana)"
   ├─ Fetch: 5 recent tweets
   ├─ Analyze: mentions, engagement, viral tweets
   └─ Score: +0 to +15 points
```

### Rate Limiting
- **Weekly limit:** 5 calls
- **Resets:** Every 7 days
- **Logging:** "📊 Twitter API calls this week: 3/5"
- **If limit hit:** Skip Twitter, score token without it

---

## Configuration Values

### Conviction Thresholds
```python
MIN_CONVICTION_SCORE = 80       # Pre-graduation signal threshold
POST_GRAD_THRESHOLD = 75        # Post-graduation signal threshold
```

### Polling Settings
```python
POLLING_INTERVALS = {
    'initial': 5,               # First 2 min: every 5 seconds
    'initial_duration': 120,    # 2 minutes fast polling
    'normal': 15,               # Normal: every 15 seconds
    'slow': 30,                 # If stuck: every 30 seconds
    'stuck_threshold': 3,       # Consider stuck after 3 polls
    'max_age': 1800            # Stop after 30 minutes
}
```

### Early Kill Switch
```python
EARLY_KILL_SWITCH = {
    'enabled': True,
    'min_new_buyers': 5,        # Need 5+ new buyers
    'check_window_seconds': 120, # Check every 2 minutes
    'trigger_at_bonding_pct': 50 # Only apply at 50%+ bonding
}
```

### Twitter Settings
```python
ENABLE_TWITTER = True           # Twitter integration enabled
ENABLE_LUNARCRUSH = False       # LunarCrush disabled
ENABLE_NARRATIVES = False       # Narratives disabled

# Twitter check thresholds (in conviction_engine.py):
bonding_pct >= 60 and mid_total >= 70
```

### Scoring Weights
```python
WEIGHTS = {
    'smart_wallet_kol': 10,      # Per KOL buy
    'volume_spike': 10,          # Strong volume
    'volume_increasing': 5,      # Steady volume
    'momentum_strong': 10,       # +50% in 5min
    'momentum_moderate': 5,      # +20% in 5min
}

UNIQUE_BUYER_WEIGHTS = {
    'exceptional': 15,           # 100+ buyers
    'high': 12,                  # 70-99 buyers
    'medium': 8,                 # 40-69 buyers
    'low': 5,                    # 20-39 buyers
}

TWITTER_WEIGHTS = {
    'high_buzz': 15,             # 5+ mentions, 10+ engagement
    'medium_buzz': 10,           # 3+ mentions
    'low_buzz': 5,               # 1+ mentions
    'viral_tweet': 12            # 100+ likes
}

RUG_DETECTION = {
    'bundles': {
        'minor': -10,            # 4-10 same-block txs
        'medium': -25,           # 11-20 same-block txs
        'massive': -40           # 21+ same-block txs
    },
    'holder_concentration': {
        'extreme': -999,         # Top 10 > 80%
        'severe': -35,           # Top 10 > 70%
        'high': -20,             # Top 10 > 50%
        'medium': -10            # Top 10 > 40%
    }
}
```

---

## Example Token Journey

### Token: $AIDOG (AI agent narrative)

**Minute 0: KOL Buy**
```
KOL wallet buys $AIDOG
├─ Start tracking
├─ Initial score: 10 pts (1 KOL buy)
└─ Begin 5-second polling
```

**Minute 1: Building Momentum**
```
Poll #12:
├─ 30% bonding
├─ 25 unique buyers
├─ Strong momentum (+30% in 5min)
├─ Score: 10 (KOL) + 5 (buyers) + 5 (momentum) = 20 pts
└─ Too low, continue tracking
```

**Minute 5: Growing**
```
Poll #60:
├─ 55% bonding
├─ 65 unique buyers
├─ Volume spiking
├─ Score: 10 (KOL) + 8 (buyers) + 10 (volume) = 28 pts
└─ Still too low, continue tracking
```

**Minute 8: Approaching Threshold**
```
Poll #96:
├─ 62% bonding
├─ 85 unique buyers
├─ 2nd KOL buys!
├─ Score: 20 (2 KOLs) + 12 (buyers) + 10 (volume) + 10 (momentum) = 52 pts
└─ Still below 80, continue tracking
```

**Minute 10: Strong Signal**
```
Poll #120:
├─ 68% bonding
├─ 110 unique buyers
├─ Score: 20 (KOLs) + 15 (buyers) + 10 (volume) + 10 (momentum) = 55 pts
├─ Bundle check: Clean ✅
├─ Holder check: Well distributed ✅
└─ Mid-score: 55 pts (not enough for signal yet)
```

**Minute 12: Twitter Check Triggered**
```
Poll #144:
├─ 72% bonding
├─ 120 unique buyers
├─ Score so far: 20 + 15 + 10 + 10 = 55 pts
├─ Bonding: 72% ≥ 60% ✅
├─ Conviction: 55 ≥ 70 ❌
└─ SKIP TWITTER (conviction too low)
```

**Minute 15: 3rd KOL Buys**
```
Poll #180:
├─ 75% bonding
├─ 130 unique buyers
├─ 3rd KOL bought!
├─ Score: 30 (3 KOLs) + 15 (buyers) + 10 (volume) + 10 (momentum) = 65 pts
├─ Multi-KOL bonus: +15 pts (3 KOLs within 5 min)
├─ Total: 80 pts
└─ Still checking if 80 after penalties...

Rug checks:
├─ Bundle: -10 pts (minor bundling detected)
├─ Holder concentration: -5 pts (top 10 hold 42%)
└─ Final score: 80 - 10 - 5 = 65 pts

Still not 80, continue...
```

**Minute 18: Twitter Boost**
```
Poll #216:
├─ 78% bonding
├─ 145 unique buyers
├─ Score: 30 (KOLs) + 15 (buyers) + 10 (volume) + 10 (momentum) = 65 pts
├─ After penalties: 65 - 10 - 5 = 50 pts
├─ Bonding: 78% ≥ 60% ✅
├─ Conviction: 50 ≥ 70 ❌
└─ SKIP TWITTER (still too low)
```

**Minute 20: 4th KOL Buys!**
```
Poll #240:
├─ 80% bonding
├─ 155 unique buyers
├─ 4th KOL bought!
├─ Score: 40 (4 KOLs, max) + 15 (buyers) + 10 (volume) + 10 (momentum) = 75 pts
├─ After penalties: 75 - 10 - 5 = 60 pts
├─ Still not 80... wait, let's check Twitter now!

Twitter check:
├─ Bonding: 80% ≥ 60% ✅
├─ Conviction: 60 ≥ 70 ❌
└─ SKIP (still 10 pts short)
```

**Minute 22: Better Distribution**
```
Poll #264:
├─ 85% bonding
├─ 180 unique buyers (improved!)
├─ Score: 40 (KOLs) + 15 (buyers) + 10 (volume) + 10 (momentum) = 75 pts
├─ Holder concentration improved: top 10 now hold 38%
├─ After penalties: 75 - 10 - 0 = 65 pts (concentration penalty removed!)
└─ Still 15 points short of 80...

Wait! Fresh buyers are coming in fast...
```

**Minute 24: Volume Surge**
```
Poll #288:
├─ 88% bonding
├─ 200 unique buyers!
├─ Volume 3x spiking!
├─ Momentum +60% in 5min!
├─ Score: 40 (KOLs) + 15 (buyers) + 10 (volume) + 10 (momentum) = 75 pts
├─ After penalties: 75 - 10 = 65 pts
├─ Twitter check eligible!

Twitter check (call 4/5 this week):
├─ Search "$AIDOG (crypto OR token OR solana)"
├─ Found 7 tweets
├─ Total engagement: 145 (likes + RTs + replies)
├─ Avg engagement: 20.7 per tweet
├─ Top tweet: 89 likes
├─ Assessment: MEDIUM BUZZ
└─ Score: +10 pts

FINAL SCORE: 65 + 10 = 75 pts

Still 5 points short! But getting close...
```

**Minute 26: BREAKTHROUGH**
```
Poll #312:
├─ 92% bonding (very close to graduation!)
├─ 210 unique buyers
├─ Someone just tweeted with 120 likes! (viral)
├─ Base score: 40 + 15 + 10 + 10 = 75 pts
├─ After penalties: 75 - 10 = 65 pts
├─ Twitter cached (use previous result): +10 pts
├─ TOTAL: 75 pts

Wait... let me recalculate. Bundle penalty reduced due to good distribution!

Recheck rug detection:
├─ Bundle: -5 pts (improved, less coordinated now)
├─ Holder: 0 pts (well distributed)
└─ After penalties: 75 - 5 = 70 pts

With Twitter: 70 + 10 = 80 pts! 🎯

✅ CONVICTION THRESHOLD MET: 80 ≥ 80

🚀 SEND TELEGRAM SIGNAL!

Signal content:
├─ Token: $AIDOG
├─ Conviction: 80/100
├─ Bonding: 92%
├─ KOLs: 4 wallets bought
├─ Buyers: 210 unique
├─ Twitter: Medium buzz (7 mentions)
├─ Status: About to graduate!
└─ CA: [contract address]
```

**Minute 28: Token Graduates**
```
├─ Token hits 100% bonding
├─ Graduates to Raydium
├─ Continue tracking for 1 hour post-signal
└─ Then remove from active tracking
```

---

## Performance Metrics

### Credit Usage (Helius API)
- **Webhooks:** ~20K/day (20 KOL wallets × 1K txs)
- **Polling:** Minimal (only high-conviction tokens)
- **Holder checks:** Gated (only when score ≥ 60)
- **Total:** ~25K credits/day (750K/month)
- **Well under free tier:** 1M/month limit

### Twitter Usage (Free Tier)
- **Limit:** 100 tweet reads/month = 20 calls/month
- **Expected:** 5 calls/week = 20 calls/month
- **Right at limit!** Need to monitor closely

### Signal Quality
- **Pre-optimization:** 5-10 signals/day, 30% accuracy
- **Post-optimization:** 2-3 signals/day, 70%+ accuracy
- **Twitter boost:** Adds 10-20% more high-quality signals

---

## Cost Breakdown

| Service | Cost | Purpose |
|---------|------|---------|
| Helius Developer | $49/mo | RPC + webhooks (1M credits) |
| Twitter Free | $0/mo | Buzz detection (100 reads) |
| Railway | $5-10/mo | Hosting |
| **Total** | **$54-59/mo** | Complete system |

Optional upgrades:
- Twitter Basic: +$100/mo (10K reads)
- LunarCrush: +$24/mo (cross-platform sentiment)
- Helius Pro: +$200/mo (10M credits)

---

## Questions for Grok

1. **Threshold optimization:** Are 60% bonding + 70 conviction the right thresholds for Twitter checks given 5 calls/week limit?

2. **Twitter value:** With only 5 calls/week (100 reads/month), is Twitter worth it vs upgrading to Basic tier ($100/mo) for 1,000 calls/month?

3. **Signal threshold:** Is 80 conviction pre-grad too high/low? Should we lower to 75 to catch more tokens?

4. **Polling intervals:** Current polling (5s → 15s → 30s) optimal or should we adjust?

5. **Early kill switch:** 50% bonding with <5 buyers/2min - too aggressive or too lenient?

6. **Missing signals:** What else should we check? Any blind spots in the scoring system?

7. **Alternative social intel:** Better free alternatives to Twitter for buzz detection?

8. **Rug detection:** Are bundle penalties (-10/-25/-40) and concentration penalties appropriately weighted?
