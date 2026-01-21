# 🎯 Sentinel Signals v2

**Clean, focused memecoin trading signals powered by smart wallet tracking and narrative detection.**

---

## 🏗️ Architecture

```
sentinel-v2/
├── main.py                      # FastAPI app with webhooks
├── config.py                    # Centralized configuration
├── database.py                  # Database models
├── gmgn_wallet_fetcher.py      # GMGN metadata auto-fetcher
│
├── data/
│   └── curated_wallets.py      # 36 KOL wallets
│
├── trackers/ 
│   ├── smart_wallets.py        # Smart wallet webhook handler
│   └── narrative_detector.py   # Narrative analysis
│
├── scoring/
│   └── conviction_engine.py    # Conviction scoring
│
└── publishers/
    └── telegram.py             # Telegram signal posting
```

---

## 🎯 Conviction Scoring System

```
Base Score: 50 points

🏆 Smart Wallet Activity (Max +40):
  • Elite wallet buy: +15 each
  • Top KOL buy: +10 each

📈 Narrative Matching (Max +35):
  • Hot narrative: +20
  • Fresh narrative (<48h): +10
  • Multiple narratives: +5

⚡ Timing Bonus (Max +10):
  • Ultra early (<30m): +10
  • Early (30-60m): +5

Signal Threshold: 75/100
```

---

## 🚀 Quick Start

### 1. **Clone & Install**

```bash
git clone <your-repo-url>
cd sentinel-v2
pip install -r requirements.txt
```

### 2. **Set Environment Variables**

Create a `.env` file:

```bash
# Database (Railway provides this)
DATABASE_URL=postgresql://...

# API Keys
HELIUS_API_KEY=your_helius_api_key
DEXSCREENER_API_KEY=your_dexscreener_api_key

# GMGN Wallet Metadata (Optional - for live win_rate & PnL data)
# Get free account at https://apify.com
APIFY_API_TOKEN=your_apify_token

# LunarCrush Social Sentiment (Optional - for X/Twitter trending data)
# Get free API key at https://lunarcrush.com/developers/api
LUNARCRUSH_API_KEY=your_lunarcrush_key

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHANNEL_ID=@your_channel

# Scoring Configuration
MIN_CONVICTION_SCORE=75
MIN_LIQUIDITY=5000
MIN_HOLDERS=30
MAX_AGE_MINUTES=120

# Feature Flags
ENABLE_SMART_WALLETS=true
ENABLE_NARRATIVES=true
ENABLE_TELEGRAM=true

# Logging
LOG_LEVEL=INFO
```

### 3. **Run Locally**

```bash
python main.py
```

The app will start on `http://localhost:8000`

---

## 🤖 GMGN Wallet Metadata Auto-Fetching

The bot now automatically fetches live wallet stats (win_rate, pnl_30d, wallet name) from **GMGN.ai** via Apify when KOLs buy tokens.

### **How It Works:**

1. **Wallet buys in** → System checks if `fetch_metadata: True` in curated_wallets.py
2. **Auto-fetch from GMGN** → Pulls live win_rate, PnL, and wallet name via Apify REST API
3. **Cache for 6 hours** → Avoids excessive API calls, keeps data relatively fresh
4. **Display in Telegram** → Shows `🔥 WalletName (75% WR, $52k PnL) bought 5m ago`

### **Setup Apify (Free Tier):**

1. Sign up at https://apify.com (free tier available)
2. Get your API token from Account → Integrations
3. Add to Railway env: `APIFY_API_TOKEN=apify_api_xxxxx`

**Without Apify token:** Bot still works, but wallet metadata will be generic placeholders.

**Cost:** Apify free tier includes 100 actor runs/month - plenty for 36 wallets with 6-hour caching.

---

## 🌙 LunarCrush Social Sentiment

The bot integrates with **LunarCrush** to cross-reference social data with token signals.

### **How It Works:**

1. **Token signal generated** → Check if trending on X/Twitter via LunarCrush
2. **Social metrics** → Galaxy Score, sentiment, social volume, trending rank
3. **Bonus points** → Up to +20 points for trending tokens with bullish sentiment
4. **Exit signals** → Detect when social hype is cooling (future feature)

### **Scoring Breakdown:**

- **Trending in top 20:** +10 points
- **Bullish sentiment (>3.5/5):** +5 points
- **High social volume growth (>50%):** +5 points

### **Setup LunarCrush (Free Tier):**

1. Sign up at https://lunarcrush.com/developers/api
2. Get your free API key (1000 requests/day)
3. Add to Railway env: `LUNARCRUSH_API_KEY=your_key`

**Without LunarCrush:** Bot still works, social scoring disabled (0 points).

**Use Cases:**
- Cross-validate KOL buys with X/Twitter buzz
- Detect trending narratives in real-time
- Exit when sentiment cools (Ralph can test this)

---

## 📡 Helius Webhooks Setup

You need **2 webhooks** in your Helius dashboard:

### **Webhook 1: Token Graduations**

- **Type**: Enhanced Transactions
- **Address**: `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P` (Pump.fun program)
- **Transaction Type**: Any
- **Webhook URL**: `https://your-app.up.railway.app/webhook/graduation`

### **Webhook 2: Smart Wallets**

- **Type**: Enhanced Transactions
- **Addresses**: (All 36 addresses from `data/curated_wallets.py`)
```
3kebnKw7cPdSkLRfiMEALyZJGZ4wdiSRvmoN4rD1yPzV
57rXqaQsvgyBKwebP2StfqQeCBjBS4jsrZFJN5aU2V9b
FAicXNV5FVqtfbpn4Zccs71XcfGeyxBSGbqLDyDJZjke
Bi4rd5FH5bYEN8scZ7wevxNZyNmKHdaBcvewdPFxYdLt
G6fUXjMKPJzCY1rveAE6Qm7wy5U3vZgKDJmN1VPAdiZC
Be24Gbf5KisDk1LcWWZsBn8dvB816By7YzYF5zWZnRR6
GJA1HEbxGnqBhBifH9uQauzXSB53to5rhDrzmKxhSU65
F5jWYuiDLTiaLYa54D88YbpXgEsA6NKHzWy4SN4bMYjt
4vw54BmAogeRV3vPKWyFet5yf8DTLcREzdSzx4rw9Ud9
CA4keXLtGJWBcsWivjtMFBghQ8pFsGRWFxLrRCtirzu5
JAmx4Wsh7cWXRzQuVt3TCKAyDfRm9HA7ztJa4f7RM8h9
2net6etAtTe3Rbq2gKECmQwnzcKVXRaLcHy2Zy1iCiWz
gangJEP5geDHjPVRhDS5dTF5e6GtRvtNogMEEVs91RV
5sNnKuWKUtZkdC1eFNyqz3XHpNoCRQ1D1DfHcNHMV7gn
39q2g5tTQn9n7KnuapzwS2smSx3NGYqBoea11tBjsGEt
G3gZWqrYkNmYFKYCyfRCNtGuxdyuE2wiYKkZpiZn4WSS
215nhcAHjQQGgwpQSJQ7zR26etbjjtVdW74NLzwEgQjP
EeXvxkcGqMDZeTaVeawzxm9mbzZwqDUMmfG3bF7uzumH
4nvNc7dDEqKKLM4Sr9Kgk3t1of6f8G66kT64VoC95LYh
4fZFcK8ms3bFMpo1ACzEUz8bH741fQW4zhAMGd5yZMHu
6mWEJG9LoRdto8TwTdZxmnJpkXpTsEerizcGiCNZvzXd
zhYnXqK3MNSmwS3yxSvPmY5kUa1n2WUaCJgYUDrAHkL
9RrKUhRpbPDNxR7x88ZsCgdtqPHUfwYPjj4JdpV4FBj9
5B52w1ZW9tuwUduueP5J7HXz5AcGfruGoX6YoAudvyxG
BTf4A2exGK9BCVDNzy65b9dUzXgMqB4weVkvTMFQsadd
DYAn4XpAkN5mhiXkRB7dGq4Jadnx6XYgu8L5b3WGhbrt
sAdNbe1cKNMDqDsa4npB3TfL62T14uAo2MsUQfLvzLT
GNrmKZCxYyNiSUsjduwwPJzhed3LATjciiKVuSGrsHEC
DZAa55HwXgv5hStwaTEJGXZz1DhHejvpb7Yr762urXam
PMJA8UQDyWTFw2Smhyp9jGA6aTaP7jKHR7BPudrgyYN
BaLxyjXzATAnfm7cc5AFhWBpiwnsb71THcnofDLTWAPK
CxgPWvH2GoEDENELne2XKAR2z2Fr4shG2uaeyqZceGve
8oQoMhfBQnRspn7QtNAq2aPThRE4q94kLSTwaaFQvRgs
87rRdssFiTJKY4MGARa4G5vQ31hmR7MxSmhzeaJ5AAxJ
5B79fMkcFeRTiwm7ehsZsFiKsC7m7n1Bgv9yLxPp9q2X
AAMnoNo3TpezKcT7ah9puLFZ4D59muEhQHJJqpX16ccg
```
- **Transaction Type**: Any
- **Webhook URL**: `https://your-app.up.railway.app/webhook/smart-wallet`

---

## 🚂 Deploy to Railway

### 1. **Create New Railway Project**

```bash
# In your repo
railway init
railway link
```

### 2. **Add Environment Variables**

In Railway dashboard, add all variables from `.env` above.

### 3. **Deploy**

```bash
git add .
git commit -m "Initial v2 deployment"
git push
```

Railway will auto-deploy on push.

### 4. **Configure Webhooks**

Once deployed, get your Railway URL:
- Format: `https://sentinel-v2-production.up.railway.app`
- Add `/webhook/graduation` and `/webhook/smart-wallet` to Helius

---

## 📊 Monitoring

### **Check Status**

```bash
curl https://your-app.up.railway.app/status
```

### **Railway Logs**

Look for:
- `✅ SENTINEL SIGNALS V2 READY`
- `✅ Telegram bot initialized`
- `📥 Received graduation webhook`
- `📥 Received smart wallet webhook`
- `✅ HIGH CONVICTION: <symbol> - Score: XX/100`
- `📤 Posted signal to Telegram`

---

## 🎛️ Configuration

### **Update Narratives**

Edit `config.py` → `HOT_NARRATIVES`:

```python
HOT_NARRATIVES = {
    'ai': {
        'keywords': ['ai', 'agent', 'gpt'],
        'weight': 1.0,
        'active': True
    },
    # Add more...
}
```

### **Adjust Scoring Weights**

Edit `config.py` → `WEIGHTS`:

```python
WEIGHTS = {
    'smart_wallet_elite': 15,   # Change these values
    'smart_wallet_kol': 10,
    'narrative_hot': 20,
    # ...
}
```

### **Change Thresholds**

In Railway env variables:
- `MIN_CONVICTION_SCORE=75` → Lower for more signals
- `MIN_LIQUIDITY=5000` → Adjust as needed
- `MIN_HOLDERS=30` → Quality filter

---

## 🔧 Troubleshooting

### **No Signals Posting?**

1. Check Railway logs for `HIGH CONVICTION` messages
2. Lower `MIN_CONVICTION_SCORE` temporarily to test
3. Verify Telegram bot is admin in channel
4. Check `TELEGRAM_CHANNEL_ID` format (@channel or -100123456)

### **Webhooks Not Working?**

1. Check Helius dashboard for delivery errors
2. Verify webhook URLs are correct
3. Look for `📥 Received` messages in Railway logs
4. Test health endpoint: `curl https://your-app/`

### **Database Issues?**

1. Railway provides `DATABASE_URL` automatically
2. Check it starts with `postgresql://` not `postgres://`
3. Migrations run automatically on startup

---

## 📈 What's Next?

**Phase 2 Ideas:**
- Twitter/X KOL call tracking
- Telegram group monitoring  
- Bubble maps integration
- Exit strategy signals
- Performance tracking dashboard

---

## 📝 Notes

**This is v2 - a clean rebuild focused on:**
- Smart wallet activity (20 elite traders)
- Narrative detection (trending themes)
- Quality over quantity (75+ conviction only)
- Reliable Telegram posting
- Simple, maintainable code

**No more:**
- Overly complex scoring
- API spam from polling
- Conflicting logic
- Technical debt
- Feature bloat

---

Built with ❤️ for high-conviction memecoin signals
