# Advanced Optimization Implementation Guide

This guide provides specific implementation details for OPT-006 through OPT-010 (Grok's advanced ideas).

## OPT-006: On-Chain Data Pipeline

**Goal:** Real-time Solana transaction streaming for early signal detection

**Implementation:**

### 1. Helius Geyser Websocket Streamer

```python
# streaming/helius_geyser.py
import asyncio
import websockets
import json
from database import Database

class HeliusGeyserStream:
    """
    Real-time Solana transaction streaming via Helius Geyser
    Focuses on Pump.fun token launches and smart wallet activity
    """

    def __init__(self, helius_api_key: str, db: Database):
        self.ws_url = f"wss://atlas-mainnet.helius-rpc.com/?api-key={helius_api_key}"
        self.db = db

    async def stream_pumpfun_launches(self):
        """Stream new Pump.fun token launches"""
        subscription = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "transactionSubscribe",
            "params": [
                {
                    "accountInclude": ["6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"],  # Pump.fun program
                    "failed": False
                },
                {
                    "commitment": "confirmed",
                    "encoding": "jsonParsed",
                    "transactionDetails": "full"
                }
            ]
        }

        async with websockets.connect(self.ws_url) as ws:
            await ws.send(json.dumps(subscription))

            async for message in ws:
                data = json.loads(message)
                await self.process_transaction(data)

    async def process_transaction(self, tx_data: dict):
        """Extract wallet behavior and store to DB"""
        # Extract: wallet, token, amount, timestamp
        # Cluster: early_buyer, quick_flipper, holder
        # Store in on_chain_activity table
        pass
```

### 2. Database Schema

```sql
-- Add to database.py create_tables()
CREATE TABLE IF NOT EXISTS on_chain_activity (
    id SERIAL PRIMARY KEY,
    wallet_address TEXT NOT NULL,
    token_address TEXT NOT NULL,
    transaction_type TEXT NOT NULL,  -- 'buy', 'sell'
    amount_sol REAL,
    timestamp TIMESTAMP NOT NULL,
    cluster_label TEXT,  -- 'early_buyer', 'quick_flipper', 'holder'
    detected_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_onchain_wallet ON on_chain_activity(wallet_address);
CREATE INDEX idx_onchain_token ON on_chain_activity(token_address);
```

### 3. Wallet Clustering

```python
# ml/wallet_clustering.py
from sklearn.cluster import DBSCAN
import numpy as np

def cluster_wallets_by_behavior(wallet_txs: list) -> dict:
    """
    Cluster wallets by trading patterns:
    - early_buyer: buys within 5min of launch
    - quick_flipper: avg hold time <30min
    - holder: avg hold time >24h
    """
    features = []
    for wallet in wallet_txs:
        features.append([
            wallet['avg_entry_time'],  # Seconds after launch
            wallet['avg_hold_time'],   # Hold duration
            wallet['trade_frequency']  # Trades per day
        ])

    X = np.array(features)
    clustering = DBSCAN(eps=0.3, min_samples=5).fit(X)

    # Label clusters
    labels = {
        0: 'early_buyer',
        1: 'quick_flipper',
        2: 'holder',
        -1: 'noise'
    }

    return {wallet['address']: labels.get(clustering.labels_[i], 'unknown')
            for i, wallet in enumerate(wallet_txs)}
```

---

## OPT-007: RSS Narrative Detection

**Goal:** Discover emerging crypto narratives from news without X API

**Implementation:**

### 1. RSS Feed Ingestion

```python
# narrative/rss_fetcher.py
import feedparser
from datetime import datetime

RSS_FEEDS = {
    'coindesk': 'https://www.coindesk.com/arc/outboundfeeds/rss/',
    'cointelegraph': 'https://cointelegraph.com/rss',
    'decrypt': 'https://decrypt.co/feed'
}

class RSSNarrativeFetcher:
    def fetch_articles(self, hours=24):
        """Fetch recent articles from crypto news RSS feeds"""
        articles = []

        for source, url in RSS_FEEDS.items():
            feed = feedparser.parse(url)
            for entry in feed.entries:
                pub_date = datetime(*entry.published_parsed[:6])
                if (datetime.now() - pub_date).total_seconds() < hours * 3600:
                    articles.append({
                        'title': entry.title,
                        'description': entry.description,
                        'source': source,
                        'published': pub_date,
                        'link': entry.link
                    })

        return articles
```

### 2. BERTopic Clustering

```python
# narrative/bertopic_detector.py
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer

class BERTopicNarrativeDetector:
    def __init__(self):
        self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        self.topic_model = BERTopic(embedding_model=self.embedding_model)

    def detect_narratives(self, articles: list):
        """
        Cluster articles into narrative topics
        Returns: emerging narratives (new clusters with >5 mentions)
        """
        docs = [f"{a['title']} {a['description']}" for a in articles]

        topics, probs = self.topic_model.fit_transform(docs)

        # Extract topic keywords
        topic_info = self.topic_model.get_topic_info()

        # Filter: emerging = new topics with >5 articles
        emerging = []
        for topic_id, row in topic_info.iterrows():
            if row['Count'] >= 5 and topic_id != -1:  # -1 = outliers
                keywords = [word for word, _ in self.topic_model.get_topic(topic_id)[:5]]
                emerging.append({
                    'name': '_'.join(keywords[:2]),  # e.g., 'ai_agent'
                    'keywords': keywords,
                    'count': row['Count'],
                    'weight': min(row['Count'] / 10, 2.0)  # Boost weight
                })

        return emerging
```

### 3. Auto-Update Narratives

```python
# Update config.py HOT_NARRATIVES automatically
def update_narratives_config(emerging: list):
    """Add discovered narratives to config.py"""
    for narrative in emerging:
        # Add to config.HOT_NARRATIVES if not exists
        # Set active=True, boost=narrative['weight']*10
        pass
```

---

## OPT-008: ML Wallet Discovery

**Goal:** Auto-find high-alpha wallets using ML classification

**Implementation:**

### 1. Feature Extraction from Dune/Helius

```python
# ml/wallet_discovery.py
import requests
import pandas as pd

def extract_wallet_features(wallet_address: str) -> dict:
    """
    Query Dune/Helius for wallet metrics
    Features: win_rate, avg_roi, hold_time, entry_timing, frequency
    """
    # Simplified - use Dune API or Helius getTransactions
    query_url = f"https://api.dune.com/api/v1/query/..."

    response = requests.get(query_url)
    data = response.json()

    # Calculate features
    trades = data['result']['rows']
    wins = [t for t in trades if t['roi'] > 0]

    return {
        'wallet_address': wallet_address,
        'win_rate': len(wins) / len(trades) if trades else 0,
        'avg_roi': sum(t['roi'] for t in trades) / len(trades) if trades else 0,
        'avg_hold_time': sum(t['hold_minutes'] for t in trades) / len(trades) if trades else 0,
        'avg_entry_time': sum(t['seconds_after_launch'] for t in trades) / len(trades) if trades else 0,
        'trade_frequency': len(trades) / 30  # Trades per day (assuming 30-day window)
    }
```

### 2. Train Smart Wallet Classifier

```python
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

class SmartWalletClassifier:
    def __init__(self):
        self.model = LogisticRegression()
        self.scaler = StandardScaler()

    def train(self, labeled_wallets: pd.DataFrame):
        """
        Train on known smart wallets (from curated_wallets.py)
        Label: 1 = smart (win_rate>70% & avg_roi>50%), 0 = not smart
        """
        X = labeled_wallets[['win_rate', 'avg_roi', 'avg_hold_time',
                              'avg_entry_time', 'trade_frequency']]
        y = labeled_wallets['is_smart']

        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)

    def predict_smart_wallets(self, unlabeled: pd.DataFrame) -> list:
        """Predict which unlabeled wallets are 'smart'"""
        X = unlabeled[['win_rate', 'avg_roi', 'avg_hold_time',
                       'avg_entry_time', 'trade_frequency']]
        X_scaled = self.scaler.transform(X)

        probs = self.model.predict_proba(X_scaled)[:, 1]  # Probability of 'smart'

        # Return top 20 by probability
        top_indices = probs.argsort()[-20:][::-1]
        return unlabeled.iloc[top_indices].to_dict('records')
```

---

## OPT-009: Backtesting Framework

**Goal:** Validate optimizations on historical data before live deploy

**Implementation:**

```python
# backtesting/engine.py
from database import Database
from scoring.conviction_engine import ConvictionEngine

class BacktestingEngine:
    """
    Replay historical signals with different configs
    Measure: ROI, win_rate, Sharpe ratio, max drawdown
    """

    def __init__(self, db: Database):
        self.db = db

    async def backtest_config(self, config_overrides: dict, days=30):
        """
        Test a config on last N days of signals

        Args:
            config_overrides: {'MIN_CONVICTION_SCORE': 70, ...}
            days: Lookback period

        Returns:
            {
                'signals_posted': int,
                'avg_roi': float,
                'win_rate': float,
                'sharpe_ratio': float,
                'max_drawdown': float
            }
        """
        # Get historical token data from database
        historical_tokens = await self.db.get_tokens_last_n_days(days)

        # Apply config overrides
        import config
        for key, value in config_overrides.items():
            setattr(config, key, value)

        # Re-score each token with new config
        conviction_engine = ConvictionEngine(...)
        results = []

        for token in historical_tokens:
            score = await conviction_engine.analyze_token(token['address'], token['data'])

            # Simulate: would we have signaled?
            if score['passed']:
                # Get actual outcome from performance table
                outcome = await self.db.get_token_outcome(token['address'])
                results.append({
                    'signaled': True,
                    'roi': outcome['max_roi'],
                    'rugged': outcome['rugged']
                })

        # Calculate metrics
        winning_signals = [r for r in results if r['roi'] > 2.0]

        return {
            'signals_posted': len(results),
            'avg_roi': sum(r['roi'] for r in results) / len(results) if results else 0,
            'win_rate': len(winning_signals) / len(results) if results else 0,
            'sharpe_ratio': self._calculate_sharpe(results),
            'max_drawdown': self._calculate_max_drawdown(results)
        }

    def _calculate_sharpe(self, results: list) -> float:
        """Sharpe ratio: (avg_return - risk_free_rate) / std_dev"""
        import numpy as np
        returns = [r['roi'] - 1.0 for r in results]  # Convert ROI to returns
        return (np.mean(returns) - 0.0) / np.std(returns) if returns else 0

    def _calculate_max_drawdown(self, results: list) -> float:
        """Max drawdown from peak equity"""
        import numpy as np
        equity = np.cumsum([r['roi'] - 1.0 for r in results])
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak
        return abs(np.min(drawdown)) if len(drawdown) > 0 else 0
```

---

## OPT-010: Dynamic Risk Management

**Goal:** ML-powered adaptive TP/SL based on volatility

**Implementation:**

```python
# ml/dynamic_exits.py
from sklearn.ensemble import RandomForestClassifier
import numpy as np

class DynamicExitModel:
    """
    Predict optimal exit timing based on:
    - Current volatility (rolling std dev)
    - Volume spike (vs 24h avg)
    - Holder growth rate
    """

    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100)

    def train(self, historical_signals: pd.DataFrame):
        """
        Train on historical signals with actual exits
        Features: volatility, volume_spike, holder_growth
        Target: 1 = should exit (realized >2x), 0 = hold
        """
        X = historical_signals[['volatility', 'volume_spike', 'holder_growth']]
        y = historical_signals['should_exit']  # Labeled from actual outcomes

        self.model.fit(X, y)

    def predict_exit(self, current_price_data: dict) -> dict:
        """
        Predict exit signal and adaptive stop loss

        Returns:
            {
                'exit_signal': bool,
                'trailing_stop_pct': float,  # Adaptive based on volatility
                'confidence': float
            }
        """
        # Calculate features
        volatility = np.std(current_price_data['prices'][-20:])  # Rolling 20-period
        volume_spike = current_price_data['volume'] / current_price_data['avg_volume_24h']
        holder_growth = (current_price_data['holders_now'] - current_price_data['holders_1h_ago']) / current_price_data['holders_1h_ago']

        X = np.array([[volatility, volume_spike, holder_growth]])

        exit_prob = self.model.predict_proba(X)[0, 1]

        # Adaptive trailing stop: tighter in high volatility
        trailing_stop_pct = 0.15 if volatility > 0.1 else 0.25  # 15% vs 25%

        return {
            'exit_signal': exit_prob > 0.7,
            'trailing_stop_pct': trailing_stop_pct,
            'confidence': exit_prob
        }
```

---

## Integration into Conviction Engine

Add ML exit signals to scoring/conviction_engine.py:

```python
# In analyze_token()
if self.dynamic_exit_model:
    exit_prediction = self.dynamic_exit_model.predict_exit(price_data)

    if exit_prediction['exit_signal']:
        logger.info(f"   🚨 ML Exit Signal: {exit_prediction['confidence']:.2%} confidence")
        # Trigger Telegram alert or auto-exit
```

---

## Ralph Integration

Ralph will autonomously:
1. Implement each optimization (OPT-006 to OPT-010)
2. Deploy to Railway
3. Monitor for specified duration
4. Backtest before committing (using OPT-009 framework)
5. Keep changes if metrics improve

**Run Ralph:**
```bash
cd ralph
export DATABASE_URL="postgresql://..."
./ralph.sh --tool claude 15  # Run 15 iterations for all 10 optimizations
```

Ralph will execute these in priority order, learning and improving autonomously! 🤖
