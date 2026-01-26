# Real-time Narrative Detection (RSS + BERTopic)
## Date: 2026-01-26 - No-Cost Alternative to Twitter/LunarCrush

### 🎯 OBJECTIVE
Implement real-time narrative detection using free RSS feeds + BERTopic machine learning, replacing expensive Twitter/LunarCrush APIs while providing better emerging trend detection.

---

## 📋 WHAT'S INCLUDED

### **New Components:**
1. **`trackers/realtime_narrative_detector.py`** - RSS fetcher + BERTopic clustering
2. **Enhanced `trackers/narrative_detector.py`** - Hybrid static + realtime detection
3. **Config options** - `ENABLE_REALTIME_NARRATIVES`, `NARRATIVE_UPDATE_INTERVAL`
4. **New dependencies** - feedparser, bertopic, sentence-transformers

---

## 🔧 HOW IT WORKS

### **Step 1: RSS Aggregation**
Every 15-30 minutes (configurable), fetch articles from 7+ crypto news sources:
- **CoinTelegraph** - General crypto news
- **CoinDesk** - Market trends
- **The Block** - Institutional crypto
- **CoinGecko** - Token-focused news
- **Decrypt** - Web3/DeFi news
- **Solana Blog** - Solana ecosystem updates
- **The Defiant** - DeFi trends

**Articles fetched:**
- Only last 24 hours (relevance filter)
- Title + summary extracted
- Deduplicated by URL
- Minimum 20 characters (skip empty)

### **Step 2: BERTopic Clustering**
Articles are clustered into emerging topics using:
- **SentenceTransformer** (all-MiniLM-L6-v2) - Fast embeddings
- **BERTopic** - Topic modeling with auto-reduction
- **Min topic size: 3** - Catch very early trends
- **Top 5 topics** - Focus on hottest narratives

**Output:**
```
Topic 0: ai_agents_solana (12 docs) - ai, agent, autonomous, solana, dex
Topic 1: zk_privacy_tech (8 docs) - zk, privacy, zero-knowledge, proof, stealth
Topic 2: rwa_tokenization (6 docs) - rwa, real, world, asset, treasury
Topic 3: desci_research (5 docs) - desci, science, research, biotech, data
Topic 4: mobile_saga_phone (4 docs) - mobile, saga, phone, seeker, solana
```

### **Step 3: Token Matching**
For each tracked token:
1. **Combine metadata** - `{name} {symbol} {description}`
2. **Embed token text** - Same SentenceTransformer model
3. **Calculate similarity** - Cosine similarity to each topic
4. **Award points** - Based on match strength

**Scoring:**
| Similarity | Points | Example |
|------------|--------|---------|
| 0.7+ | 25 pts | Token name: "AI Agent Doge" → Topic: "ai_agents_solana" |
| 0.5-0.7 | 20 pts | Strong semantic match |
| 0.4-0.5 | 15 pts | Medium match |
| 0.3-0.4 | 10 pts | Weak match |
| <0.3 | 0 pts | No match |

---

## 📊 ADVANTAGES OVER TWITTER/LUNARCRUSH

| Feature | Twitter/LunarCrush | RSS + BERTopic |
|---------|-------------------|----------------|
| **Cost** | $99-499/month | **$0** ✅ |
| **Update frequency** | Real-time | 15-30 min |
| **Emerging trends** | Lagging (needs volume) | **Leading** (news first) ✅ |
| **Narrative depth** | Keywords only | **Semantic clustering** ✅ |
| **Solana-specific** | Mixed chains | **Solana-focused sources** ✅ |
| **Resource usage** | API calls | **One-time CPU** (15 min) |
| **Reliability** | API rate limits | **No rate limits** ✅ |

**Key insight:** News articles about "AI agents on Solana" appear **hours before** Twitter buzz builds up. BERTopic catches these trends earlier than social APIs.

---

## 🚀 DEPLOYMENT ON RAILWAY

### **Resource Requirements:**
- **CPU:** Low (5-10s spike every 15 min for BERTopic)
- **RAM:** ~200-300MB (models loaded once)
- **Bandwidth:** Minimal (RSS feeds are tiny)
- **Storage:** <100MB (models cached)

### **Railway Setup:**
Railway auto-detects Python and installs dependencies from `requirements.txt`. No special config needed.

**Expected logs:**
```
📰 RealtimeNarrativeDetector initialized (update every 900s)
🔄 Loading SentenceTransformer (all-MiniLM-L6-v2)...
✅ Embedder loaded
🔄 Initializing BERTopic model...
✅ BERTopic model initialized
📰 Fetched 23 new articles from 7 sources
🔄 Running BERTopic on 23 articles...
✅ Detected 5 emerging narratives:
   📌 Topic 0: ai_agents_solana (12 docs) - ai, agent, autonomous, solana, dex
   📌 Topic 1: zk_privacy_tech (8 docs) - zk, privacy, zero-knowledge, proof
...
```

### **First Run:**
- Model downloads: ~2-3 minutes (one-time)
- First BERTopic fit: ~30-60 seconds
- Subsequent updates: ~10-20 seconds (incremental)

---

## 🎯 INTEGRATION WITH SCORING

### **Current Flow:**
```python
# In conviction_engine.py
narrative_result = self.narrative_detector.analyze_token(
    symbol=token_symbol,
    name=token_name,
    description=token_data.get('description', '')
)

base_scores['narrative'] = narrative_result['score']
```

### **Enhanced Flow (No Code Changes Needed!):**
The `narrative_detector.py` automatically uses realtime detection if enabled:

```python
# analyze_token() now returns:
{
    'has_narrative': True,
    'score': 25,  # Max of realtime (25) or static (20)
    'realtime_score': 25,  # From RSS + BERTopic
    'static_score': 20,    # From static HOT_NARRATIVES
    'realtime_reason': "Strong match to 'ai_agents_solana' narrative",
    'narratives': [...],   # Static matches
    'primary_narrative': 'ai_agent'  # Best static match
}
```

**The conviction engine uses the higher score automatically.**

---

## 📈 EXAMPLE: AI Agent Token

### **Token:**
- Name: "Autonomous AI Doge"
- Symbol: "AIDOGE"
- Description: "AI-powered trading agent on Solana"

### **RSS Articles (15 min ago):**
```
[CoinTelegraph] "Solana AI agents see surge in adoption..."
[The Block] "New autonomous trading protocols launch on Solana..."
[Decrypt] "AI-powered DeFi: The next wave of crypto innovation..."
```

### **BERTopic Result:**
```
Topic 0: ai_agents_solana (15 docs)
  Top words: ai, agent, autonomous, trading, solana, protocol
```

### **Token Scoring:**
```
Token text: "Autonomous AI Doge AIDOGE AI-powered trading agent on Solana"
Similarity to Topic 0: 0.82 (very high)

Result:
  Realtime score: 25 pts ✅ (strong match)
  Static score: 20 pts (matches 'ai_agent' in HOT_NARRATIVES)
  Final score: 25 pts (realtime wins)
  Reason: "Strong match to 'ai_agents_solana' narrative"
```

**Impact:** Token gets +25 pts instead of +20 pts (static), pushing it over threshold.

---

## 🔧 CONFIGURATION OPTIONS

### **Enable/Disable:**
```python
# config.py
ENABLE_NARRATIVES = True  # Overall narratives feature
ENABLE_REALTIME_NARRATIVES = True  # RSS + BERTopic
```

### **Update Frequency:**
```python
NARRATIVE_UPDATE_INTERVAL = 900  # 15 minutes (default)
# Options:
#   300 = 5 min (very aggressive, more CPU)
#   900 = 15 min (recommended)
#   1800 = 30 min (conservative)
#   3600 = 1 hour (slow but minimal resources)
```

### **RSS Sources:**
Edit `trackers/realtime_narrative_detector.py`:
```python
RSS_SOURCES = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    # Add more sources...
]
```

---

## 📊 MONITORING & LOGS

### **Startup Logs:**
```
✅ Narrative Detector initialized
   📊 Tracking 8 static narratives
   🔄 Enabling real-time RSS narrative detection
   ✅ Real-time narrative loop started
```

### **Update Logs (every 15 min):**
```
📰 Updating narratives from RSS feeds...
   📡 Fetching RSS: https://cointelegraph.com/rss
   📡 Fetching RSS: https://www.coindesk.com/arc/outboundfeeds/rss/
   ...
   📰 Fetched 23 new articles from 7 sources
   🔄 Running BERTopic on 23 articles...
   ✅ Detected 5 emerging narratives:
      📌 Topic 0: ai_agents_solana (12 docs) - ai, agent, autonomous
      📌 Topic 1: zk_privacy_tech (8 docs) - zk, privacy, proof
✅ Narrative update complete. Next update in 900s
```

### **Token Scoring Logs:**
```
🎯 Narrative boost: $AIDOGE +25 pts (Strong match to 'ai_agents_solana' narrative)
```

---

## 🐛 TROUBLESHOOTING

### **"Realtime narratives enabled but dependencies missing!"**
**Fix:** Install dependencies:
```bash
pip install feedparser bertopic sentence-transformers
```

### **"Too few articles (3), skipping update"**
**Cause:** RSS feeds not returning enough articles (network issue or slow news day)
**Fix:** Wait for next update (15 min). Add more RSS sources if persistent.

### **"BERTopic error: Not enough documents"**
**Cause:** <5 articles fetched (rare)
**Fix:** Reduce `min_topic_size` from 3 to 2 in `realtime_narrative_detector.py`:
```python
min_topic_size=2,  # Instead of 3
```

### **High CPU usage**
**Cause:** Update interval too aggressive (e.g., 5 min)
**Fix:** Increase `NARRATIVE_UPDATE_INTERVAL` to 900 (15 min) or 1800 (30 min)

### **Model download timeout**
**Cause:** Railway startup timeout (rare)
**Fix:** Models download in background, wait 2-3 min. If persistent, increase Railway timeout in settings.

---

## 📋 TESTING

### **Local Test:**
```bash
cd /home/user/SENTINEL_V2
python trackers/realtime_narrative_detector.py
```

**Expected output:**
```
📰 RealtimeNarrativeDetector initialized (update every 60s)
📰 Updating narratives from RSS feeds...
   📰 Fetched 23 new articles from 7 sources
   🔄 Running BERTopic on 23 articles...
   ✅ Detected 5 emerging narratives:
      📌 Topic 0: ai_agents_solana (12 docs) - ai, agent, autonomous
Test Result: 25 points - Strong match to 'ai_agents_solana' narrative
```

### **Integration Test:**
Add to your main bot startup:
```python
# In main.py or active_token_tracker.py
narrative_detector = NarrativeDetector()
await narrative_detector.start()

# Test with a token
result = narrative_detector.analyze_token(
    "AIDOGE",
    "AI Doge",
    "An AI agent on Solana"
)
print(f"Narrative score: {result['score']} pts")
print(f"Realtime: {result['realtime_score']}, Static: {result['static_score']}")
```

---

## 🎯 EXPECTED IMPACT

### **Before (Static Narratives):**
- Fixed keywords: "ai", "agent", "autonomous"
- Match: "AI Doge" → +20 pts (keyword match)
- **Problem:** Misses emerging trends (e.g., "ZK privacy" becomes hot but not in static list)

### **After (RSS + BERTopic):**
- Dynamic clustering: Detects "ai_agents_solana" from news
- Match: "AI Doge" → +25 pts (semantic similarity)
- **Advantage:** Catches emerging trends hours before Twitter buzz

### **Signal Quality:**
- **More signals:** Catch early narrative plays before they're "mainstream"
- **Better timing:** News articles → Token launches → Twitter buzz (hours delay)
- **No API cost:** Free RSS feeds vs. $99-499/month for Twitter/LunarCrush

### **Example:**
**Day 1:** CoinTelegraph publishes "Solana ZK rollups gain traction"
- RSS detector picks up "zk_privacy_tech" narrative
- Token "ZK Privacy Coin" launches 4 hours later
- **Result:** +25 pts (strong match) → signals early
- Twitter buzz builds 8 hours after launch (too late)

**Without realtime:** Token gets 0 pts (no "zk" in static narratives) → missed

---

## 📚 TECHNICAL DETAILS

### **Models Used:**
1. **SentenceTransformer (all-MiniLM-L6-v2)**
   - Size: ~90MB
   - Speed: ~1000 sentences/sec
   - Quality: High for English text

2. **BERTopic**
   - Algorithm: c-TF-IDF + HDBSCAN
   - Min cluster size: 3 documents
   - Auto-reduction: Yes

### **Memory Footprint:**
- Models: ~200MB (loaded once)
- Article cache: ~1MB (last 24h)
- Topic data: ~100KB

### **CPU Usage:**
- Model loading: 30-60s (startup only)
- BERTopic fit: 10-30s (every 15 min)
- Idle: <1% CPU

---

## 🚀 FUTURE ENHANCEMENTS

### **Phase 1 (Current):**
- ✅ RSS aggregation
- ✅ BERTopic clustering
- ✅ Token matching

### **Phase 2 (Optional):**
- Add more RSS sources (Messari, Bankless, etc.)
- Store narrative history in DB for backtesting
- Dashboard: Show top narratives + token matches

### **Phase 3 (Advanced):**
- Cross-reference narratives with Twitter trends (when budget allows)
- Multi-language support (non-English crypto news)
- Fine-tune embedding model on crypto corpus

---

## 📋 FILES MODIFIED

| File | Changes |
|------|---------|
| `requirements.txt` | Added feedparser, bertopic, sentence-transformers |
| `trackers/realtime_narrative_detector.py` | **NEW** - RSS + BERTopic module |
| `trackers/narrative_detector.py` | Enhanced with realtime support |
| `config.py` | Added `ENABLE_REALTIME_NARRATIVES`, `NARRATIVE_UPDATE_INTERVAL` |

---

## ✅ DEPLOYMENT CHECKLIST

- [x] Install dependencies (`pip install -r requirements.txt`)
- [x] Enable in config (`ENABLE_REALTIME_NARRATIVES = True`)
- [x] Set update interval (`NARRATIVE_UPDATE_INTERVAL = 900`)
- [ ] Deploy to Railway
- [ ] Monitor logs for "📰 Updating narratives"
- [ ] Test with AI/ZK tokens
- [ ] Validate narrative boosts in signals

---

**Real-time narratives: Catch trends before they're mainstream!** 🚀
