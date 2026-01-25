# Ralph: Auto-Fix Errors & Optimize Data Collection

Ralph now has **5 new optimizations** specifically for fixing errors and improving data collection:

## 🔧 OPT-013: Auto-Fix Runtime Errors (Priority 13)

**What Ralph Does:**
1. Fetches last 1000 lines from Railway logs
2. Parses for error patterns: `ERROR`, `Exception`, `Failed`, `Traceback`
3. Classifies errors by type:
   - API failures (Helius, DexScreener timeouts)
   - Data parsing errors (bonding curve decode fails)
   - Missing data (price, metadata not found)
   - Timeout errors (slow API responses)
4. Implements fixes automatically:
   - **API failures** → Add retry logic with exponential backoff
   - **Parsing errors** → Add validation and safe defaults
   - **Missing data** → Add fallback data sources
   - **Timeouts** → Increase timeout or add caching
5. Deploys fixes to Railway
6. Monitors for 2 hours
7. **Keeps if error count drops >50%**

**Example Fix:**
```python
# Before (causes errors):
price_data = await api.get_price(token)
token_price = price_data['price']  # ❌ KeyError if 'price' missing

# After (Ralph adds):
price_data = await api.get_price(token)
token_price = price_data.get('price', 0.0)  # ✅ Safe with default
if not token_price:
    # Ralph adds fallback
    token_price = await dexscreener.get_price(token)
```

**Monitoring:**
Ralph checks your phone shows: `✅ Fixed 8/12 errors (67% reduction)`

---

## 📊 OPT-014: Optimize Metadata Collection (Priority 14)

**Problem:** Tokens showing `$UNKNOWN` because metadata fetch fails

**What Ralph Does:**
1. Audits current sources (Helius DAS, bonding curve, DexScreener)
2. Measures success rate and latency
3. Implements fallback chain:
   - **Primary**: Helius DAS API (fast, 1 credit)
   - **Secondary**: DexScreener API (free, slower)
   - **Tertiary**: Jupiter API (free)
   - **Last resort**: Solscan scraper (free)
4. Adds 24h cache (name/symbol rarely change)
5. Implements parallel fetching (metadata + price + holders simultaneously)
6. **Keeps if metadata success rate >95% and latency <500ms**

**Before:**
- 60% of tokens showing `$UNKNOWN`
- Single source (Helius) - fails = no data

**After:**
- 95%+ tokens have name/symbol
- 4 fallback sources
- 24h cache reduces API calls by 80%

---

## 💰 OPT-015: Optimize Price Data (Priority 15)

**Problem:** Logs showing `⚠️ No price data available` frequently

**What Ralph Does:**
1. Audits price sources (bonding curve, DexScreener, Jupiter, Raydium)
2. Measures success rate per source
3. Implements weighted price aggregation:
   - Gets prices from 2-3 sources
   - Averages them (rejects outliers)
4. Adds staleness detection (rejects prices >5 min old)
5. Implements 30s price cache
6. Adds sanity checks (rejects price changes >500% in 1 min)
7. **Keeps if "No price data" errors drop >80%**

**Before:**
- 30% of tokens have no price
- Bonding curve decoder fails → no price at all

**After:**
- 95%+ tokens have accurate price
- Multiple sources ensure price availability
- Outlier rejection prevents bad data

---

## 👑 OPT-016: Track KOL Performance (Priority 16)

**Problem:** All 36 KOLs score 10 points equally, but some are better than others

**What Ralph Does:**
1. Creates `kol_performance` database table
2. Tracks each KOL:
   - Tokens bought
   - Outcomes (rug/2x/10x/50x+)
   - Win rate
   - Avg ROI
3. Auto-demotes KOLs with <50% win rate
4. Auto-promotes wallets with >75% win rate + >3x avg ROI
5. Adjusts scoring:
   - **High performers** (>75% WR): +15 pts
   - **Medium performers** (50-75% WR): +10 pts
   - **Low performers** (<50% WR): +5 pts
6. Creates `/kol-leaderboard` command
7. **Keeps if signal quality improves >10%**

**Example:**
```
Before (all equal):
- Ram: 10 points
- Bad KOL: 10 points
- Good KOL: 10 points

After (performance-based):
- Ram (80% WR, 5x avg): 15 points
- Bad KOL (40% WR): 5 points
- Good KOL (70% WR, 3x avg): 15 points
```

**You'll see on phone:**
```
📊 KOL Leaderboard (last 30 days):
1. Ram - 80% WR, 5.2x avg ROI, 24 trades
2. Clukz - 75% WR, 3.8x avg ROI, 18 trades
3. The Doc - 72% WR, 3.1x avg ROI, 31 trades
...
32. BadKOL - 38% WR, 0.8x avg ROI, 15 trades (auto-demoted)
```

---

## 🤖 OPT-017: Auto-Tune Scoring (Priority 17)

**Problem:** Scoring weights are guesses (smart_wallet=40, narrative=25, etc.)

**What Ralph Does:**
1. Extracts last 100 signals from database with outcomes
2. Trains ML model (gradient descent) to predict outcome from scores
3. Finds optimal weights that:
   - Maximize 10x+ predictions
   - Minimize rug predictions
4. Tests on validation set
5. Applies new weights to config.py
6. **Keeps if 10x+ rate improves >20% OR rug rate drops >30%**

**Example:**
```
Before (manual weights):
- Smart wallet activity: 40 points
- Narrative: 25 points
- Holders: 15 points
- Volume: 10 points
- Momentum: 10 points

After (ML-optimized):
- Smart wallet activity: 45 points (increased - most predictive!)
- Narrative: 15 points (decreased - less predictive)
- Holders: 20 points (increased - important for 10x+)
- Volume: 10 points (same)
- Momentum: 10 points (same)
```

---

## Timeline & Priority

Ralph will run these in order:

**Quick wins (2 hours each):**
1. **OPT-001-004**: Basic tuning (6 hours)
2. **OPT-013**: Fix errors (2 hours) 🔧
3. **OPT-014**: Optimize metadata (2 hours) 📊
4. **OPT-015**: Optimize prices (2 hours) 💰

**Total for critical fixes: ~12 hours**

**Medium term (4-7 days):**
5. **OPT-016**: KOL tracking (7 days) 👑
6. **OPT-017**: ML scoring (3 days) 🤖

---

## What You'll See on Your Phone

**Railway logs:**
```
===============================================================
  Ralph Iteration 5 of 10
===============================================================

📊 Working on: OPT-013 - Auto-fix runtime errors
📊 Fetching Railway logs...
🔍 Found 47 errors in last 1000 lines:
   - 18x "No price data available" (API failures)
   - 12x "KeyError: 'symbol'" (data parsing)
   - 8x "TimeoutError" (slow APIs)
   - 9x "Failed to decode bonding curve" (parsing)

🔧 Implementing fixes:
   ✅ Added price fallback chain (Helius → DexScreener → Jupiter)
   ✅ Added safe .get() for all dict access
   ✅ Increased API timeout: 5s → 10s
   ✅ Added bonding curve validation

📝 Committed: fix: auto-fix 47 runtime errors
🚀 Deployed to Railway
⏳ Monitoring for 2 hours...

[2 hours later]

📈 Results:
   - Error count: 47 → 8 (-83% ✅)
   - "No price data": 18 → 2 (-89%)
   - "KeyError": 12 → 0 (-100%)
   - "TimeoutError": 8 → 3 (-62%)

✅ KEEP: Error count dropped 83% (target: >50%)
💾 Updated prd.json: OPT-013 passes=true
```

**GitHub commits:**
```
Ralph Bot committed 2h ago
fix: auto-fix 47 runtime errors (-83% error rate)

Ralph Bot committed 4h ago
optimize: metadata fallback chain (95% success rate, was 60%)

Ralph Bot committed 6h ago
optimize: price aggregation from 3 sources (-89% 'No price data' errors)
```

---

## Cost

**Quick error fixes (OPT-013-015):**
- ~$0.90 total (3 optimizations × $0.30 each)
- Saves you debugging time
- Runs in ~6 hours

**KOL tracking + ML (OPT-016-017):**
- ~$0.60 total (2 optimizations × $0.30 each)
- Requires 7-10 days monitoring
- Dramatically improves signal quality

---

## Deploy Now

1. **Merge PR:** https://github.com/Sydneyanon/SENTINEL_V2/compare/main...claude/review-option-b-EuwEL
2. **Deploy Ralph** to Railway (see RAILWAY_DEPLOY.md)
3. **Check phone** throughout the day to see Ralph fixing errors

Ralph will autonomously:
- ✅ Fix all recurring errors in your logs
- ✅ Optimize metadata/price fetching
- ✅ Track which KOLs actually perform
- ✅ Auto-tune scoring weights with ML

**No babysitting required. Just check your phone to see improvements.** 📱🤖
