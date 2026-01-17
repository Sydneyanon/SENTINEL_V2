# 🎯 Sentinel Signals v2

**Clean, focused memecoin trading signals powered by smart wallet tracking and narrative detection.**

---

## 🏗️ Architecture

```
sentinel-v2/
├── main.py                      # FastAPI app with webhooks
├── config.py                    # Centralized configuration
├── database.py                  # Database models
│
├── data/
│   └── curated_wallets.py      # 20 elite + KOL wallets
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

## 📡 Helius Webhooks Setup

You need **2 webhooks** in your Helius dashboard:

### **Webhook 1: Token Graduations**

- **Type**: Enhanced Transactions
- **Address**: `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P` (Pump.fun program)
- **Transaction Type**: Any
- **Webhook URL**: `https://your-app.up.railway.app/webhook/graduation`

### **Webhook 2: Smart Wallets** 

- **Type**: Enhanced Transactions  
- **Addresses**: (All 20 addresses from `data/curated_wallets.py`)
```
9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM
H7vNP4r7cNnA2tLWYCEtZhyPBn3n7FfFo7MsEk3qYK5U
FjqQAQ8fmE3F5t7KJ9UxV5YcP8NmG3rZwTsN2D4vHk8L
3jK5r9mN8tF7hP2vQ6xL4bY8sW1nC5dR9mT7kH6jP3wX
2sR7tK9nM5gH3pL8vX6bF4yQ7wD1cT9mP5kN8jH4rY2W
8xT4wK2nP7gL5mV9bN3sH6yR1cF8dQ5pM2jK7tL9nW3X
5mN8tH3gP2vL7kR9bX4wF6yQ1sD3cK8pT5jM7nH9rY2W
7gL5mV9bN3sH6yR1cF8dQ5pM2jK7tL9nW3X4wK2nP8xT
CyaE1VxvBrahnPWkqm5VsdCvyS2QmNht2UFrKJHga54o
8Dg8J8xSeKqtBvL1nBe9waX348w5FSFjVnQaRLMpf7eV
Be24Gbf5KisDk1LcWWZsBn8dvB816By7YzYF5zWZnRR6
4BdKaxN8G6ka4GYtQQWk4G4dZRUTX2vQH9GcXdBREFUk
2fg5QD1eD7rzNNCsvnhmXFm5hqNgwTTG8p7kQ6f3rx6f
FAicXNV5FVqtfbpn4Zccs71XcfGeyxBSGbqLDyDJZjke
DYAn4XpAkN5mhiXkRB7dGq4Jadnx6XYgu8L5b3WGhbrt
GJA1HEbxGnqBhBifH9uQauzXSB53to5rhDrzmKxhSU65
G6fUXjMKPJzCY1rveAE6Qm7wy5U3vZgKDJmN1VPAdiZC
57rXqaQsvgyBKwebP2StfqQeCBjBS4jsrZFJN5aU2V9b
4mN7tK8gP3vL6kR8bX5wF7yQ2sD4cK9pT6jM8nH0rY3W
6gL4mV8bN2sH5yR0cF7dQ4pM1jK6tL8nW2X3wK1nP7xT
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
