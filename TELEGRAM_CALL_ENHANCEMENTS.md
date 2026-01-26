# 📱 Telegram Call Tracking Enhancements

## Overview
Enhanced the Telegram group call tracking system with three major improvements:
1. **Multi-Call Bonus Scoring** - Rewards repeated mentions and multi-group confirmation
2. **Persistent Call Tracking** - Database storage for historical analysis
3. **Group Correlation Matrix** - Tracks which groups call together

---

## 🎯 Feature 1: Multi-Call Bonus Scoring

### Implementation
Location: `scoring/conviction_engine.py` (lines ~388-425)

### Scoring Logic
- **High Frequency Bonus**: +10 pts when same CA is mentioned 3+ times within 30 minutes
- **Multi-Group Bonus**: +15 pts when called by 3+ different groups within 30 minutes
- **Combined Cap**: Maximum +20 pts total to prevent over-scoring

### Example Scenarios

#### Scenario A: Rapid Fire Calls
- Token called 5 times in 15 minutes from 2 groups
- **Result**: +10 pts (high frequency bonus)

#### Scenario B: Cross-Group Confirmation
- Token called by 4 different groups within 20 minutes
- **Result**: +15 pts (multi-group bonus)

#### Scenario C: Maximum Bonus
- Token called 6 times from 5 groups within 10 minutes
- **Result**: +20 pts (both bonuses, capped)

### Integration
- Queries persistent database for call statistics
- Works alongside existing telegram call scoring (5-15 pts)
- Total telegram score can now reach up to 35 pts (15 base + 20 bonus)

---

## 💾 Feature 2: Persistent Call Tracking

### Database Schema

#### `telegram_calls` Table
```sql
CREATE TABLE telegram_calls (
    id SERIAL PRIMARY KEY,
    token_address TEXT NOT NULL,
    group_name TEXT NOT NULL,
    message_text TEXT,
    timestamp TIMESTAMP NOT NULL,
    detected_at TIMESTAMP DEFAULT NOW()
)
```

#### Indexes
- `idx_telegram_calls_token` - Fast token lookups
- `idx_telegram_calls_timestamp` - Time-based queries
- `idx_telegram_calls_group` - Group-specific analysis

### New Database Methods

#### Insert Call
```python
await db.insert_telegram_call(
    token_address="GDfn...",
    group_name="bullish_bangers",
    message_text="🚀 Next 100x",
    timestamp=datetime.utcnow()
)
```

#### Get Call Stats (for multi-call bonus)
```python
stats = await db.get_telegram_call_stats(
    token_address="GDfn...",
    minutes=30
)
# Returns: {call_count, group_count, first_call_time, latest_call_time}
```

#### Get Group History
```python
calls = await db.get_group_call_history(
    group_name="bullish_bangers",
    days=7
)
```

### Benefits
- **Historical Analysis**: Query past calls beyond 4-hour in-memory cache
- **Pattern Detection**: Identify group accuracy over time
- **ML Training**: Use call data for prediction models
- **Auditing**: Track which groups called which tokens when

---

## 🔗 Feature 3: Group Correlation Matrix

### Database Schema

#### `group_correlations` Table
```sql
CREATE TABLE group_correlations (
    id SERIAL PRIMARY KEY,
    group_a TEXT NOT NULL,
    group_b TEXT NOT NULL,
    token_address TEXT NOT NULL,
    time_diff_seconds INTEGER NOT NULL,
    correlation_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(group_a, group_b, token_address, correlation_date)
)
```

### How It Works

#### Automatic Tracking
When a telegram call webhook is received:
1. Check if other groups already called this token
2. Calculate time difference between calls
3. If within 30 minutes → store correlation
4. Track all group pairs that call together

#### Example Flow
```
10:00 AM - Group "alpha_calls" calls TOKEN_X
10:05 AM - Group "beta_signals" calls TOKEN_X
→ Correlation stored: (alpha_calls, beta_signals, TOKEN_X, 300s)

10:10 AM - Group "gamma_gems" calls TOKEN_X
→ Correlations stored:
   - (alpha_calls, gamma_gems, TOKEN_X, 600s)
   - (beta_signals, gamma_gems, TOKEN_X, 300s)
```

### Correlation Analysis Methods

#### Get Correlation Score
```python
score = await db.get_group_correlation_score(
    group_a="alpha_calls",
    group_b="beta_signals",
    days=30
)
# Returns:
# {
#   correlation_count: 15,
#   avg_time_diff: 240,  # seconds
#   unique_tokens: 12,
#   correlation_strength: 85  # 0-100 scale
# }
```

#### Get Top Correlated Pairs
```python
pairs = await db.get_top_group_pairs(days=30, limit=10)
# Returns top 10 group pairs that call together most often
```

### Use Cases

#### 1. Detect Coordinated vs Organic Calls
- **Coordinated**: Same groups always call within 1-2 minutes
- **Organic**: Random time spreads, different group combinations

#### 2. Group Quality Assessment
- Groups that correlate with high-accuracy groups → higher trust
- Groups that correlate with low-accuracy groups → lower trust

#### 3. Future Enhancement Ideas
- Weight group calls based on correlation strength
- Detect shill groups (always call together, low accuracy)
- Auto-tier groups based on correlation with successful outcomes

---

## 📊 Performance Impact

### Database Load
- **Inserts**: 1 call insert + N correlation inserts per webhook (N = existing groups)
- **Queries**: 1 stats query per token analysis (cached for scoring)
- **Indexes**: Optimized for fast lookups

### Memory Impact
- In-memory cache still used for real-time detection
- Database provides persistent layer without increasing RAM

### Cost Impact
- Database operations are async (non-blocking)
- Minimal latency added to webhook processing
- PostgreSQL indexes ensure fast queries

---

## 🚀 Deployment Notes

### Database Migration
Tables and indexes are created automatically on startup via `create_tables()` method.

No manual migration needed - just deploy and run!

### Backwards Compatibility
- Existing telegram call tracking continues to work
- In-memory cache still used for 4-hour window
- New features are additive (won't break existing scoring)

### Configuration
No new environment variables required. Feature is enabled when:
- `ENABLE_TELEGRAM_SCRAPER = True` (existing config)
- Database connection is available

---

## 🧪 Testing Recommendations

### 1. Manual Testing
Trigger telegram calls via webhook:
```bash
curl "http://localhost:8000/webhook/telegram-call?token=TEST_CA_123&group=test_group_1"
curl "http://localhost:8000/webhook/telegram-call?token=TEST_CA_123&group=test_group_2"
curl "http://localhost:8000/webhook/telegram-call?token=TEST_CA_123&group=test_group_3"
```

### 2. Verify Database Storage
```sql
SELECT * FROM telegram_calls WHERE token_address = 'TEST_CA_123';
SELECT * FROM group_correlations WHERE token_address = 'TEST_CA_123';
```

### 3. Check Multi-Call Bonus
Watch logs during token analysis:
```
📊 Multi-call analysis: 3 calls from 3 groups (30m)
🔥 HIGH FREQUENCY BONUS: +10 pts (3 calls)
🔥 MULTI-GROUP BONUS: +15 pts (3 groups)
⚖️  Multi-call bonus capped at +20 pts
```

### 4. Query Correlation Stats
```python
# In Python console or admin endpoint
stats = await db.get_group_correlation_score("test_group_1", "test_group_2", days=1)
print(stats)
```

---

## 📈 Future Enhancements

### Potential Additions (Not Implemented Yet)

1. **Group Tier System** (like KOL tiers)
   - Elite Groups: Based on historical accuracy
   - Top Groups: Consistent performers
   - Standard Groups: New or unproven

2. **Call Outcome Tracking**
   - Link calls to signal outcomes (2x, 5x, rug, etc.)
   - Calculate group-specific win rates
   - Auto-adjust scoring based on performance

3. **Coordinated Call Detection**
   - Flag suspicious patterns (always same groups, always same timing)
   - Detect pump-and-dump coordination
   - Apply penalties to suspected shill groups

4. **Cross-Signal Correlation**
   - When TG call + KOL buy happen together → extra bonus
   - Track which groups tend to call before/after KOL activity
   - Identify "alpha leak" patterns

---

## 📝 Files Modified

### 1. `database.py`
- Added `telegram_calls` table schema
- Added `group_correlations` table schema
- Added 8 new methods for call tracking and correlation analysis

### 2. `scoring/conviction_engine.py`
- Added `database` parameter to `__init__`
- Added Phase 3.7.5: Multi-Call Bonus section
- Queries database for call stats during scoring

### 3. `main.py`
- Passed `database` to ConvictionEngine initialization
- Added persistent call storage in telegram webhook
- Added automatic group correlation tracking

---

## ✅ Summary

### What Changed
✅ Telegram calls now stored persistently in database
✅ Multi-call bonus rewards repeated mentions (up to +20 pts)
✅ Group correlation matrix tracks which groups call together
✅ 8 new database methods for analysis
✅ No configuration changes required
✅ Backwards compatible with existing system

### Impact
- **Better Signal Quality**: Rewards coordinated community buzz
- **Historical Insights**: Query past call patterns
- **Future ML Training**: Rich dataset for pattern analysis
- **Group Intelligence**: Understand group relationships and accuracy

### Next Steps
1. Deploy to Railway
2. Monitor logs for multi-call bonuses
3. Query correlation data after 7 days
4. Consider implementing Group Tier System based on outcomes

---

**Status**: ✅ Ready for deployment
**Breaking Changes**: None
**Database Migration**: Automatic on startup
