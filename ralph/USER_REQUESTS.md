# User-Requested Features for 75% Win Rate

These features were specifically requested by the user to improve win rate and user experience.

## High Priority UX/Features

### 1. Display KOL Names (OPT-027)
**Problem:** Telegram posts show "KOL" instead of actual names like "Ansem" or "Machi Big Brother"
**Solution:**
- Fix `publishers/telegram.py` line 163-166 (fallback to 'KOL')
- Ensure wallet names from `data/curated_wallets.py` are passed through signal_data
- Add tier badges: 🔥 Elite, 👑 God tier
- Show top 3 KOLs by tier if multiple bought

**Files to modify:**
- `publishers/telegram.py` - Fix name display logic
- `trackers/smart_wallets.py` - Ensure names are included in wallet data
- Test with real signal to verify names appear

---

### 2. Fix Telegram Channel Scraper (OPT-028)
**Problem:** telegram_monitor.py has calling issues - missing signals or connection drops
**Solution:**
- Debug `telegram_monitor.py` for auth/connection issues
- Add reconnection logic with exponential backoff
- Add health check: alert if no messages in 10min
- Log all calls to database with timestamp + channel
- Monitor for 6h to ensure reliability

**Files to modify:**
- `telegram_monitor.py` - Add reconnection + health checks
- `database.py` - Add telegram_calls table if missing

---

### 3. Auto-Discover High Win-Rate Channels (OPT-029)
**Problem:** Missing alpha from undiscovered Telegram channels
**Solution:**
- Scrape Solana Telegram directories for memecoin channels
- Monitor each channel for 7 days, track token calls
- Calculate win_rate per channel (track price 6h/24h after call)
- Auto-add channels with >55% win rate and >20 calls tracked
- Weight high-performing channel signals higher

**Implementation:**
- Create `channel_discovery.py` - Telegram directory scraper
- Add channel performance tracking to database
- Modify `telegram_monitor.py` to weight channels by performance

---

### 4. Auto-Discover New KOLs (OPT-030)
**Problem:** Missing signals from emerging KOLs not in curated list
**Solution:**
- Track wallets mentioned in high-performing TG channels
- Monitor DexScreener top traders (whale wallets)
- Calculate 30-day performance: win_rate, avg_ROI, trade_frequency
- Auto-promote: win_rate >65% + avg_ROI >4x + >15 trades
- Start at 'promising' tier (low points), upgrade if they maintain performance

**Implementation:**
- Create `kol_discovery.py` - Wallet discovery engine
- Add `promising` tier to curated_wallets.py
- Auto-update curated_wallets.py with new discoveries
- Track performance in database

---

### 5. Real-Time Automated Narratives (OPT-031)
**Problem:** Narratives are static - miss trending narratives, boost dead ones
**Solution:**
- Scan token names/descriptions every 15min for keywords
- Track keyword frequency: 'AI', 'cat', 'dog', 'pepe', 'degen', etc.
- Auto-create narrative if keyword appears in >5 tokens in 1h
- Calculate narrative win_rate dynamically (last 24h)
- Boost trending narratives (+15 pts), suppress dead ones (-10 pts)

**Implementation:**
- Create `narrative_scanner.py` - Real-time keyword tracker
- Modify `trackers/narrative_detector.py` - Add dynamic scoring
- Track narrative performance in database
- Auto-update active narratives list

---

### 6. Exit Strategy System (OPT-032)
**Problem:** Bot tells traders when to enter but not when to exit
**Solution:**
- Track posted signals: price, volume, holder count, liquidity
- Define exit signals: volume drops >70%, holders drop >30%, price 5x+
- Calculate exit timing: hit 5x in 2h → suggest 50% exit at 3x
- Build exit score: 0-100 based on sustainability indicators
- Backtest: would exit strategy improve realized gains?

**Implementation:**
- Create `exit_strategy.py` - Exit signal calculator
- Add exit_score to active token tracking
- Calculate optimal exit points per token
- Track in database for performance analysis

---

### 7. Telegram Exit Alerts (OPT-033)
**Problem:** Traders hold too long, miss profit-taking opportunities
**Solution:**
- Monitor all posted signals continuously
- Post exit alert when:
  - Hit 3x → "Take 50% profits"
  - Hit 5x → "Take 70% profits"
  - Red flags → "EXIT NOW" (volume -80%, holders -40%, liquidity -50%)
- Format: "🚨 EXIT SIGNAL: [TOKEN] hit 5x - Suggest taking 70% profits. Volume: -15%, Holders: +5%"
- Track if exit alerts improve realized ROI vs holding

**Implementation:**
- Modify `active_token_tracker.py` - Add exit monitoring
- Create exit alert formatter in `publishers/telegram.py`
- Post to same channel as entry signals
- Add exit_signal_posted flag to database

---

## Why These Features Drive 75% Win Rate

**Cut Losses:**
- Exit alerts prevent holding rugs to zero
- Real-time narratives avoid dead trends
- Better KOL names → more trust → better execution

**Amplify Winners:**
- Auto-discover new alpha sources (channels + KOLs)
- Exit strategy helps realize gains (sell at 5x not 2x)
- Fix TG scraper → never miss a call

**Compound Effect:**
- Each feature adds 3-5% win rate improvement
- Combined: 50% → 75%+ win rate achievable

---

## Ralph's Execution Plan

1. **OPT-027** (2h) - Fix KOL names → better UX
2. **OPT-028** (3h) - Fix TG scraper → no missed signals
3. **OPT-033** (4h) - Exit alerts → realize gains better
4. **OPT-031** (6h) - Real-time narratives → avoid dead trends
5. **OPT-032** (6h) - Exit strategy system → data-driven exits
6. **OPT-029** (7d) - Channel discovery → new alpha sources
7. **OPT-030** (14d) - KOL discovery → expand coverage

**Total time:** ~3-4 weeks for full deployment
**Expected win rate progression:**
- Week 1: 50% → 60% (UX fixes + exit alerts)
- Week 2: 60% → 68% (narratives + exit strategy)
- Week 3-4: 68% → 75%+ (discovery systems mature)

---

## Files Created/Modified

**New files to create:**
- `channel_discovery.py` - Telegram channel scraper
- `kol_discovery.py` - Wallet discovery engine
- `narrative_scanner.py` - Real-time narrative detector
- `exit_strategy.py` - Exit signal calculator

**Files to modify:**
- `publishers/telegram.py` - KOL names + exit alerts
- `telegram_monitor.py` - Reliability fixes
- `trackers/narrative_detector.py` - Dynamic scoring
- `active_token_tracker.py` - Exit monitoring
- `data/curated_wallets.py` - Auto-add discoveries
- `database.py` - New tables for tracking

**Database changes:**
- `telegram_calls` table - Track channel calls
- `channel_performance` table - Win rate per channel
- `discovered_kols` table - Track new wallet performance
- `exit_signals` table - Track exit alert performance
