# ✅ DEPLOYMENT CHECKLIST

Use this checklist to deploy Sentinel Signals v2 step by step.

---

## 📋 Pre-Deployment

- [ ] Create new GitHub repository
- [ ] Get Helius API key from https://helius.dev
- [ ] Get DexScreener API key (if needed)
- [ ] Create Telegram bot via @BotFather
- [ ] Create Telegram channel and add bot as admin
- [ ] Have Railway account ready

---

## 🗂️ Step 1: Setup Repository

```bash
# Create new repo on GitHub (private recommended)
# Then locally:

git clone <your-new-repo-url>
cd <your-repo-name>

# Copy all sentinel-v2 files into this directory
# (Download from Claude and copy into the repo)

git add .
git commit -m "Initial commit - Sentinel Signals v2"
git push origin main
```

**Files to copy:**
- [ ] `.gitignore`
- [ ] `requirements.txt`
- [ ] `config.py`
- [ ] `database.py`
- [ ] `main.py`
- [ ] `README.md`
- [ ] `data/curated_wallets.py`
- [ ] `data/__init__.py`
- [ ] `trackers/smart_wallets.py`
- [ ] `trackers/narrative_detector.py`
- [ ] `trackers/__init__.py`
- [ ] `scoring/conviction_engine.py`
- [ ] `scoring/__init__.py`
- [ ] `publishers/telegram.py`
- [ ] `publishers/__init__.py`

---

## 🚂 Step 2: Setup Railway

```bash
# Install Railway CLI (if not installed)
npm install -g @railway/cli

# Login
railway login

# Create new project
railway init

# Link to your repo
railway link
```

Or use Railway dashboard:
1. Go to https://railway.app
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose your repo

**Railway Configuration:**
- [ ] Connected to GitHub repo
- [ ] Auto-deploy on push enabled
- [ ] Database provisioned (PostgreSQL)

---

## 🔐 Step 3: Add Environment Variables

In Railway dashboard → Variables:

```bash
# Core APIs
HELIUS_API_KEY=your_helius_key_here
DEXSCREENER_API_KEY=your_dexscreener_key_here

# Telegram
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHANNEL_ID=@your_channel_or_-100123456789

# Scoring
MIN_CONVICTION_SCORE=75
MIN_LIQUIDITY=5000
MIN_HOLDERS=30
MAX_AGE_MINUTES=120

# Features
ENABLE_SMART_WALLETS=true
ENABLE_NARRATIVES=true
ENABLE_TELEGRAM=true

# Logging
LOG_LEVEL=INFO
```

**Note:** `DATABASE_URL` is provided automatically by Railway when you add PostgreSQL.

**Checklist:**
- [ ] All variables added
- [ ] No typos in variable names
- [ ] Telegram token is correct format
- [ ] Channel ID includes @ or -100

---

## 📡 Step 4: Setup Helius Webhooks

Go to https://helius.dev → Webhooks

### **Webhook 1: Graduations**

**Settings:**
- [ ] Type: Enhanced Transactions
- [ ] Address: `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`
- [ ] Transaction Type: Any
- [ ] Webhook URL: `https://YOUR-APP.up.railway.app/webhook/graduation`
- [ ] Click Create

### **Webhook 2: Smart Wallets**

**Settings:**
- [ ] Type: Enhanced Transactions
- [ ] Addresses: (paste all 20 from curated_wallets.py - one per line)
- [ ] Transaction Type: Any
- [ ] Webhook URL: `https://YOUR-APP.up.railway.app/webhook/smart-wallet`
- [ ] Click Create

**Get your Railway URL:**
```bash
railway domain
```
Or check Railway dashboard → Deployments → Domain

**Verify webhooks:**
- [ ] Both webhooks show "Active" in Helius dashboard
- [ ] URLs are correct (no typos)
- [ ] Delivery tests pass

---

## 🚀 Step 5: Deploy

```bash
# Make sure all files are committed
git status

# Push to trigger deploy
git push origin main
```

**Watch deployment:**
- [ ] Railway dashboard shows "Building..."
- [ ] Build completes successfully
- [ ] Deployment is live
- [ ] Health check passes

---

## ✅ Step 6: Verify Everything Works

### **Test 1: Health Check**

```bash
curl https://YOUR-APP.up.railway.app/
```

Expected: `{"status": "healthy", ...}`

- [ ] Health check returns 200 OK

### **Test 2: Status Endpoint**

```bash
curl https://YOUR-APP.up.railway.app/status
```

Expected: Full status with config, trackers, etc.

- [ ] Status shows correct configuration
- [ ] Smart wallets count = 20
- [ ] Narratives count = 5

### **Test 3: Check Railway Logs**

Look for these messages:
- [ ] `🚀 SENTINEL SIGNALS V2 STARTING`
- [ ] `✅ Telegram bot initialized: @your_bot_name`
- [ ] `✅ Smart Wallet Tracker initialized`
- [ ] `✅ Narrative Detector initialized`
- [ ] `✅ Conviction engine initialized`
- [ ] `✅ SENTINEL SIGNALS V2 READY`

### **Test 4: Telegram Test Message**

Check your Telegram channel:
- [ ] Received "Bot Test Message"
- [ ] Message formatting looks correct
- [ ] Bot is online

---

## 🎯 Step 7: Wait for First Signal

**What to expect:**
- First signal could take 30-60 minutes
- Bot only posts 75+ conviction scores
- Look for these in Railway logs:
  - `📥 Received graduation webhook`
  - `📥 Received smart wallet webhook`
  - `✅ HIGH CONVICTION: <symbol>`
  - `📤 Posted signal to Telegram`

**If no signals after 2 hours:**
- [ ] Check Helius webhooks are delivering
- [ ] Check Railway logs for errors
- [ ] Temporarily lower `MIN_CONVICTION_SCORE` to 60 to test
- [ ] Verify smart wallet webhook is receiving data

---

## 🐛 Troubleshooting

### No signals posting to Telegram?

1. Check Railway logs for `HIGH CONVICTION` messages
   - If yes → Telegram issue
   - If no → Scoring too strict

2. For Telegram issues:
   ```bash
   # Test bot manually
   curl -X POST https://api.telegram.org/bot<TOKEN>/sendMessage \
     -d chat_id=@your_channel \
     -d text="Test"
   ```
   - [ ] Bot can post manually
   - [ ] Bot is admin in channel
   - [ ] Channel ID is correct

3. For scoring issues:
   - [ ] Lower `MIN_CONVICTION_SCORE` temporarily
   - [ ] Check if webhooks are firing
   - [ ] Verify smart wallets are being tracked

### Webhooks not working?

1. Check Helius dashboard:
   - [ ] Webhooks show as "Active"
   - [ ] Recent delivery attempts visible
   - [ ] No error codes

2. Check Railway logs:
   - [ ] See `📥 Received` messages
   - [ ] No 404 or 500 errors
   - [ ] App is running

3. Test webhook URL manually:
   ```bash
   curl -X POST https://YOUR-APP.up.railway.app/webhook/graduation \
     -H "Content-Type: application/json" \
     -d '[]'
   ```
   Expected: `{"status": "success"}`

### Database errors?

- [ ] `DATABASE_URL` is set in Railway
- [ ] URL starts with `postgresql://` not `postgres://`
- [ ] Railway PostgreSQL service is running
- [ ] Check logs for connection errors

---

## 📊 Monitoring (First 24 Hours)

**Every few hours, check:**

1. **Railway Logs:**
   - [ ] No error messages
   - [ ] Webhooks being received
   - [ ] Signals being processed

2. **Helius Dashboard:**
   - [ ] Webhook delivery count increasing
   - [ ] No failed deliveries
   - [ ] API usage reasonable (~200-500/day)

3. **Telegram Channel:**
   - [ ] Signals posting
   - [ ] Formatting looks good
   - [ ] Information is accurate

4. **Database:**
   - [ ] Signals being saved
   - [ ] No duplicate entries
   - [ ] Data looks correct

---

## 🎉 Success Criteria

After 24 hours, you should have:

- [ ] 5-15 signals posted (depends on market)
- [ ] All signals have 75+ conviction
- [ ] Smart wallet activity showing in signals
- [ ] Narrative tags appearing
- [ ] No errors in logs
- [ ] Helius webhooks delivering successfully
- [ ] API usage under 1000 calls/day
- [ ] Database growing with signal data

---

## 📈 Next Steps

Once stable:

1. **Fine-tune scoring:**
   - Adjust weights in `config.py`
   - Monitor win rate of signals
   - Tweak thresholds based on results

2. **Update narratives:**
   - Add new trending narratives
   - Disable dead narratives
   - Adjust weights based on performance

3. **Monitor wallets:**
   - Track which wallets give best signals
   - Update wallet list monthly
   - Add new high-performers

4. **Plan Phase 2:**
   - Twitter KOL tracking
   - Telegram group monitoring
   - Exit signals
   - Performance dashboard

---

**🎊 CONGRATULATIONS! Your bot is live!**

For questions or issues, review the README.md or check Railway logs first.
