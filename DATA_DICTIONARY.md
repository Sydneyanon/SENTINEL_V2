# 📊 Complete Data Dictionary - Maximum Information Extraction

## Overview

For each token that ran yesterday, we extract **50+ data points** across 10 categories.

**Goal:** More data = Better ML predictions

---

## 🎯 Data Categories (10 Total)

### 1. **Basic Token Info** (5 fields)
| Field | Type | Description | Example | ML Value |
|-------|------|-------------|---------|----------|
| `token_address` | string | Solana mint address | "ED5nyyWE..." | Identifier |
| `symbol` | string | Token ticker | "MOODENG" | Label |
| `name` | string | Full token name | "Moo Deng" | Metadata |
| `decimals` | int | Token decimals | 6 | Normalization |
| `total_supply` | float | Total token supply | 1000000000 | Supply analysis |

---

### 2. **Price Data** (12 fields)
| Field | Type | Description | Why It Matters |
|-------|------|-------------|----------------|
| `price_usd` | float | Current price USD | Final outcome |
| `price_24h_ago_estimate` | float | Price 24h ago | Starting point |
| `price_change_24h` | float | 24h change % | **PRIMARY OUTCOME** |
| `price_change_6h` | float | 6h change % | Momentum tracking |
| `price_change_1h` | float | 1h change % | Early momentum |
| `price_change_5m` | float | 5m change % | Ultra-early signal |
| `gain_multiple` | float | Total gain (10x, 50x) | **OUTCOME CATEGORY** |
| `outcome_category` | string | "2x", "10x", "50x", "100x+" | **ML TARGET VARIABLE** |
| `peak_price_estimate` | float | Estimated peak price | Max potential |
| `current_from_peak_pct` | float | % down from peak | Sustainability |
| `time_to_peak_hours` | float | Hours to reach peak | Pump speed |
| `price_volatility` | float | Price variance | Risk indicator |

**ML Usage:**
- `outcome_category` = Primary classification target
- `gain_multiple` = Regression target
- Price changes = Feature for momentum detection

---

### 3. **Volume Patterns** (10 fields)
| Field | Type | Description | Why It Matters |
|-------|------|-------------|----------------|
| `volume_24h` | float | 24h volume USD | Overall activity |
| `volume_6h` | float | 6h volume USD | Recent activity |
| `volume_1h` | float | 1h volume USD | Early activity |
| `volume_5m` | float | 5m volume USD | Ultra-early signal |
| `volume_mcap_ratio` | float | Volume / MCAP | **Velocity indicator** |
| `volume_growth_24h` | float | Volume growth % | Acceleration |
| `volume_growth_6h` | float | 6h growth % | Momentum |
| `volume_consistency` | float | StdDev of hourly vol | Organic vs pump |
| `volume_spike_detected` | bool | Sudden spike? | Manipulation flag |
| `avg_tx_size_usd` | float | Avg transaction $ | Whale activity |

**ML Usage:**
- `volume_mcap_ratio` = Key feature (>0.5 = strong)
- Volume growth = Momentum indicator
- Consistency = Quality score

---

### 4. **Transaction Patterns** (8 fields)
| Field | Type | Description | Why It Matters |
|-------|------|-------------|----------------|
| `buys_24h` | int | 24h buy count | Demand |
| `sells_24h` | int | 24h sell count | Supply |
| `buys_6h` | int | 6h buy count | Recent demand |
| `sells_6h` | int | 6h sell count | Recent supply |
| `buy_ratio_24h` | float | Buy % (0-100) | **Sentiment indicator** |
| `buy_ratio_6h` | float | 6h buy % | Recent sentiment |
| `unique_buyers_estimate` | int | Unique wallets | Distribution |
| `early_tx_count` | int | First 100 txs | Early activity |

**ML Usage:**
- `buy_ratio_24h` = Strong feature (>70% = bullish)
- Unique buyers = Organic growth
- Early tx count = Initial interest

---

### 5. **Liquidity Data** (6 fields)
| Field | Type | Description | Why It Matters |
|-------|------|-------------|----------------|
| `liquidity_usd` | float | Total liquidity USD | Exit ability |
| `liquidity_base` | float | Token side liquidity | Pool depth |
| `liquidity_quote` | float | SOL side liquidity | Real liquidity |
| `liquidity_mcap_ratio` | float | Liquidity / MCAP | **Rug risk** |
| `liquidity_adds_count` | int | LP add events | Growing LP |
| `liquidity_removes_count` | int | LP remove events | **RUG FLAG** |

**ML Usage:**
- `liquidity_mcap_ratio` = Critical (<0.05 = rug risk)
- LP removes = Immediate red flag
- Ratio stability = Quality metric

---

### 6. **Holder Distribution** (7 fields)
| Field | Type | Description | Why It Matters |
|-------|------|-------------|----------------|
| `holder_count_estimate` | int | Total holders | Distribution |
| `top_1_holder_pct` | float | Top holder % | Concentration |
| `top_5_holder_pct` | float | Top 5 holders % | Whale control |
| `top_10_holder_pct` | float | Top 10 holders % | **RUG INDICATOR** |
| `concentration_score` | float | 0-100 (high=bad) | Overall concentration |
| `distribution_quality` | string | excellent/good/poor | Human-readable |
| `distribution_score` | float | 0-100 (high=good) | **ML FEATURE** |

**ML Usage:**
- `top_10_holder_pct` = Critical feature (>70% = rug risk)
- `distribution_score` = Quality metric
- Concentration = Risk scoring

---

### 7. **Market Cap & Timing** (6 fields)
| Field | Type | Description | Why It Matters |
|-------|------|-------------|----------------|
| `market_cap` | float | Current MCAP USD | Size |
| `market_cap_24h_ago` | float | MCAP 24h ago | Starting point |
| `peak_market_cap` | float | Peak MCAP reached | Max size |
| `created_at` | int | Token creation time | Age |
| `time_alive_hours` | float | Hours since creation | Maturity |
| `graduation_time` | int | When graduated | Milestone |

**ML Usage:**
- MCAP growth = Outcome calculation
- Time alive = Age factor
- Creation → peak time = Speed metric

---

### 8. **Whale Activity** (8 fields)
| Field | Type | Description | Why It Matters |
|-------|------|-------------|----------------|
| `whale_wallets` | list | Whale addresses | **Who** bought |
| `whale_count` | int | Number of whales | Whale interest |
| `early_whale_count` | int | Whales who bought early | **PREDICTIVE** |
| `whale_avg_entry_mcap` | float | Avg MCAP when bought | Entry timing |
| `whale_total_position_usd` | float | Total $ from whales | Conviction |
| `whale_win_rate_avg` | float | Avg whale success % | Quality |
| `top_whale_address` | string | Best performing whale | Follow leader |
| `whale_detected_early` | bool | Whale in first hour? | **KEY SIGNAL** |

**ML Usage:**
- `early_whale_count` = **Most predictive feature**
- `whale_win_rate_avg` = Quality weighting
- Early detection = Real-time signal

---

### 9. **Rug Detection Indicators** (6 fields)
| Field | Type | Description | Why It Matters |
|-------|------|-------------|----------------|
| `rug_risk_score` | float | 0-100 (high=risky) | **Overall risk** |
| `bundle_detected` | bool | Coordinated buys? | Sniper bots |
| `bundle_size` | int | Txs in same block | Bot activity |
| `dev_sell_detected` | bool | Dev sold? | **RUG FLAG** |
| `lp_removed` | bool | LP pulled? | **INSTANT RUG** |
| `honeypot_risk` | bool | Can't sell? | Scam |

**ML Usage:**
- `rug_risk_score` = Filter bad tokens
- Bundle detection = Quality control
- LP removed = Immediate fail

---

### 10. **Social Signals** (Optional - 5 fields)
| Field | Type | Description | Why It Matters |
|-------|------|-------------|----------------|
| `twitter_mentions` | int | Twitter mentions | Hype |
| `telegram_mentions` | int | Telegram calls | Community |
| `social_sentiment` | float | 0-100 sentiment | Positive/negative |
| `influencer_mentions` | int | KOL mentions | Credibility |
| `social_spike` | bool | Sudden spike? | Pump signal |

**ML Usage:**
- Social confirmation = Secondary signal
- Influencer mentions = Credibility
- Sentiment = Market mood

---

## 📊 Total Data Points Collected

### Summary:
- **Basic Info**: 5 fields
- **Price Data**: 12 fields
- **Volume Patterns**: 10 fields
- **Transaction Patterns**: 8 fields
- **Liquidity Data**: 6 fields
- **Holder Distribution**: 7 fields
- **Market Cap & Timing**: 6 fields
- **Whale Activity**: 8 fields
- **Rug Detection**: 6 fields
- **Social Signals**: 5 fields (optional)

**TOTAL: 73 data points per token** 🎯

---

## 🤖 ML Feature Importance (Predicted)

### Tier 1: Most Predictive Features (Weight: 10/10)
```python
CRITICAL_FEATURES = [
    'early_whale_count',          # Whales who bought before pump
    'whale_win_rate_avg',          # Quality of whales
    'buy_ratio_24h',               # Sentiment
    'volume_mcap_ratio',           # Velocity
    'distribution_score',          # Holder quality
    'liquidity_mcap_ratio',        # Rug risk
]
```

### Tier 2: Strong Predictive Features (Weight: 7-9/10)
```python
STRONG_FEATURES = [
    'price_change_1h',             # Early momentum
    'volume_growth_6h',            # Acceleration
    'top_10_holder_pct',           # Concentration
    'unique_buyers_estimate',      # Organic growth
    'whale_avg_entry_mcap',        # Entry timing
    'rug_risk_score',              # Safety
]
```

### Tier 3: Supporting Features (Weight: 4-6/10)
```python
SUPPORTING_FEATURES = [
    'buys_6h', 'sells_6h',         # Recent activity
    'liquidity_usd',               # Pool size
    'time_alive_hours',            # Age
    'avg_tx_size_usd',             # Whale txs
    'bundle_detected',             # Bot activity
]
```

### Tier 4: Contextual Features (Weight: 1-3/10)
```python
CONTEXTUAL_FEATURES = [
    'symbol', 'name',              # Narrative hints
    'created_at',                  # Timing
    'dex_id',                      # DEX quality
    'social_mentions',             # Hype
]
```

---

## 🎯 Example: Complete Token Record

```json
{
  // BASIC INFO
  "token_address": "ED5nyyWEzpPPiWimP8vYm7sD7TD3LAt3Q3gRTWHzPJBY",
  "symbol": "MOODENG",
  "name": "Moo Deng",
  "decimals": 6,
  "total_supply": 1000000000,

  // PRICE DATA
  "price_usd": 0.0642,
  "price_24h_ago_estimate": 0.00057,
  "price_change_24h": 11163.15,  // 111x gain!
  "price_change_6h": 450.2,
  "price_change_1h": 85.3,
  "gain_multiple": 112.6,
  "outcome_category": "100x+",  // ← ML TARGET

  // VOLUME PATTERNS
  "volume_24h": 5200000,
  "volume_6h": 2100000,
  "volume_1h": 650000,
  "volume_mcap_ratio": 0.081,  // 8.1% velocity
  "volume_growth_24h": 850,
  "volume_consistency": 0.34,

  // TRANSACTIONS
  "buys_24h": 1843,
  "sells_24h": 892,
  "buy_ratio_24h": 67.4,  // 67% buys!
  "unique_buyers_estimate": 450,

  // LIQUIDITY
  "liquidity_usd": 850000,
  "liquidity_mcap_ratio": 0.0133,  // 1.3%
  "liquidity_adds_count": 12,
  "liquidity_removes_count": 0,  // No rug!

  // HOLDER DISTRIBUTION
  "holder_count_estimate": 520,
  "top_10_holder_pct": 35.2,  // Well distributed
  "distribution_score": 81,  // Good!
  "concentration_score": 35,

  // MARKET CAP
  "market_cap": 64000000,
  "market_cap_24h_ago": 570000,
  "peak_market_cap": 68000000,

  // WHALE ACTIVITY
  "whale_count": 3,
  "early_whale_count": 2,  // 2 whales bought early!
  "whale_avg_entry_mcap": 850000,  // Entered at $850K
  "whale_win_rate_avg": 0.73,  // 73% success rate
  "whale_wallets": [
    "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
    "8BnEgHoWFysVcuFFX7QztDmzuH8r5ZFvyP3sYwn1XTh6"
  ],

  // RUG DETECTION
  "rug_risk_score": 15,  // Low risk
  "bundle_detected": false,
  "dev_sell_detected": false,
  "lp_removed": false,

  // OUTCOME
  "analyzed_at": "2026-01-26T00:00:00Z",
  "data_quality_score": 95  // High quality data
}
```

---

## 🚀 How This Powers ML

### Training:
```python
# Load dataset
data = load_tokens("data/historical_training_data.json")

# Features (X)
X = data[[
    'early_whale_count',
    'whale_win_rate_avg',
    'buy_ratio_24h',
    'volume_mcap_ratio',
    'distribution_score',
    'liquidity_mcap_ratio',
    'price_change_1h',
    'unique_buyers_estimate',
    'top_10_holder_pct',
    'volume_growth_6h'
]]

# Target (y)
y = data['outcome_category']  # "2x", "10x", "50x", "100x+"

# Train
model.fit(X, y)
```

### Prediction (Real-time):
```python
# New token detected
new_token_features = extract_features(new_token_address)

# Predict
prediction = model.predict(new_token_features)
confidence = model.predict_proba(new_token_features)

# Result:
# "Predicted: 50x with 78% confidence"
# Reason: 2 early whales (75% WR), 72% buy ratio, 0.45 vol/mcap
```

---

## 📈 Data Quality Metrics

For each token, we also calculate:

```python
data_quality_score = (
    (fields_populated / total_fields * 40) +  # Completeness
    (whale_data_available * 30) +              # Whale data
    (social_data_available * 10) +             # Social data
    (no_errors_during_collection * 20)         # Clean collection
)
# Score: 0-100, higher = better
```

Only use tokens with `data_quality_score >= 70` for ML training.

---

## 🎯 Next Steps

1. ✅ Enhanced analyzer extracts all 73 fields
2. ⏳ Test on 10 tokens (verify data quality)
3. ⏳ Run daily collection (build dataset)
4. ⏳ After 30 days: 1,500 tokens × 73 fields = 109,500 data points
5. ⏳ Train ML model
6. ⏳ Deploy predictions to live bot

**More data = Smarter bot = Better signals** 🚀
