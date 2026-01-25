# OPT-041: Helius API Credit Usage Audit
**Date**: 2026-01-25 01:00 UTC
**Priority**: 0 (HIGH - Cost optimization)
**Goal**: Identify redundant Helius calls and reduce credits by 40%+

## Executive Summary

**Current Status:**
- OPT-055: Smart gating saves 80-85% of holder check credits ✅ DEPLOYED
- OPT-002: 120min holder cache saves ~50% credits ✅ DEPLOYED
- **OPT-041 Target**: Additional 40% reduction on remaining calls

**Credit Costs:**
- Holder check (`getTokenLargestAccounts` + `getTokenSupply`): **10 credits**
- Token metadata (`get_token_data`): **~1-2 credits**
- RPC calls (`getAccountInfo` for bonding curve): **<1 credit**

## All Helius API Calls (Inventory)

### 1. Holder Concentration Checks (10 credits each)

**File:** `helius_fetcher.py:494-550` (`get_token_holders`)
**Frequency:** Once per token when gating passes
**Current Caching:** 120 minutes (OPT-002)
**Cost:** 10 credits per call

**Call Sites:**
1. `rug_detector.py:200` - Called from `detect_rug_signals()`
2. `scoring/conviction_engine.py:460` - Holder concentration scoring

**Smart Gating (OPT-055):**
- Skips check if emergency flags present (80-85% savings)
- Skips if insufficient KOL signals
- Only checks high-conviction candidates

**Current Optimization Level:** ⭐⭐⭐⭐ (4/5)

---

### 2. Token Metadata Fetches (1-2 credits each)

**File:** `helius_fetcher.py:383-435` (`get_token_metadata_batch`)
**Frequency:** On token discovery
**Current Caching:** 60 minutes (OPT-041 mentions this)
**Cost:** 1-2 credits per token

**Call Sites:**
1. `active_token_tracker.py:240` - Direct Helius metadata API call
2. `active_token_tracker.py:349` - Fallback if PumpPortal name missing
3. `active_token_tracker.py:481` - Full token data fetch during scoring

**Redundancy Detected:** ⚠️ **YES - Multiple calls for same token**

**Issue:**
- Line 240: Direct metadata fetch
- Line 349: Helius fallback during polling
- Line 481: Full token data during conviction scoring
- **Same token may be fetched 2-3 times in rapid succession**

**Current Optimization Level:** ⭐⭐ (2/5)

---

### 3. Token Data Enrichment (1-2 credits)

**File:** `helius_fetcher.py:109-145` (`get_token_data`)
**Frequency:** Every tracked token during polling
**Current Caching:** None (calls DexScreener after Helius)
**Cost:** 1-2 Helius credits + DexScreener call

**Call Sites:**
1. `active_token_tracker.py:111` - Parallel fetch with PumpPortal
2. `active_token_tracker.py:135` - Enrichment with DexScreener
3. `active_token_tracker.py:349` - Fallback during polling

**Redundancy Detected:** ⚠️ **YES - Called multiple times per poll cycle**

**Current Optimization Level:** ⭐⭐ (2/5)

---

### 4. Bonding Curve Decoding (RPC calls, <1 credit)

**File:** `helius_fetcher.py:157-230` (`get_bonding_curve_data`)
**Frequency:** Every poll (every 5-30 seconds for tracked tokens)
**Current Caching:** 5 seconds (OPT-035)
**Cost:** <1 credit per RPC call

**Optimization:** OPT-035 added 5-second cache with ~80% hit rate ✅

**Current Optimization Level:** ⭐⭐⭐⭐ (4/5)

---

## Redundancy Analysis

### Critical Finding 1: Triple Metadata Fetching

**Problem:** Same token metadata fetched up to 3 times:

1. **Initial Discovery** (`active_token_tracker.py:240`):
   ```python
   url = f"https://api.helius.xyz/v0/token-metadata?api-key={config.HELIUS_API_KEY}"
   # Direct call - NO CACHING
   ```

2. **Name Fallback** (`active_token_tracker.py:349`):
   ```python
   helius_data = await self.helius_fetcher.get_token_data(token_address)
   # Called if PumpPortal name is empty
   ```

3. **Conviction Scoring** (`active_token_tracker.py:481`):
   ```python
   token_data = await self.helius_fetcher.get_token_data(token_address)
   # Full data fetch for scoring
   ```

**Cost Impact:** 2-6 credits wasted per token (3x redundant calls × 1-2 credits)

**Solution:**
- Add in-memory cache for token metadata (24h TTL)
- Deduplicate: Store first fetch result, reuse for all subsequent calls
- Expected savings: 66% of metadata credits

---

### Critical Finding 2: No Cross-Function Cache

**Problem:** `helius_fetcher.py` has separate cache dicts:
- `holder_cache` (120min TTL) - used by holder checks
- `bonding_curve_cache` (5s TTL) - used by bonding curve checks
- **NO cache for token metadata** - fresh call every time

**Cost Impact:** Every `get_token_data()` call hits Helius API

**Solution:**
- Add `metadata_cache` dict with 1-hour TTL
- Cache structure: `{token_address: {'data': {...}, 'timestamp': datetime}}`
- Expected savings: 90% of metadata credits

---

### Critical Finding 3: Parallel Fetching Without Deduplication

**Problem:** `active_token_tracker.py:116` uses `asyncio.gather()`:
```python
tasks = [fetch_pumpportal(), fetch_helius()]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

If multiple tokens trigger simultaneously, each spawns parallel Helius calls.
**NO request batching or deduplication.**

**Cost Impact:** N tokens = N Helius calls (could be batched)

**Helius Batch API Available:** `POST /v0/token-metadata` accepts array of addresses
- Can fetch 100 tokens in 1 call vs 100 calls
- Saves 99% of credits for batch scenarios

**Solution:**
- Implement request queue: collect token addresses over 1-second window
- Batch into single Helius call if >1 token pending
- Expected savings: 50-70% for multi-token scenarios

---

## Optimization Recommendations (OPT-041)

### 1. Add Metadata Cache (HIGH PRIORITY)

**Location:** `helius_fetcher.py`

```python
# Add to __init__:
self.metadata_cache = {}  # {token_address: {'data': {...}, 'timestamp': datetime}}
self.metadata_cache_ttl_minutes = 60  # 1 hour

# Modify get_token_metadata_batch() to check cache first:
def _check_metadata_cache(self, token_address):
    if token_address in self.metadata_cache:
        cached = self.metadata_cache[token_address]
        age = (datetime.utcnow() - cached['timestamp']).total_seconds() / 60
        if age < self.metadata_cache_ttl_minutes:
            return cached['data']  # Cache hit!
    return None
```

**Expected Impact:** 90% reduction in metadata API calls (most tokens checked multiple times)

---

### 2. Eliminate Redundant Direct Calls (HIGH PRIORITY)

**Location:** `active_token_tracker.py:240`

**Current:** Direct Helius API call (bypasses caching)
```python
url = f"https://api.helius.xyz/v0/token-metadata?api-key={config.HELIUS_API_KEY}"
async with session.post(url, json={"mintAccounts": [mint_address]}) as response:
```

**Problem:** This call doesn't use `helius_fetcher` instance - no cache benefit!

**Solution:** Replace with cached fetcher call:
```python
# Instead of direct call, use the cached fetcher:
metadata = await self.helius_fetcher.get_token_metadata_batch([mint_address])
# This will use the new metadata_cache
```

**Expected Impact:** Eliminate 1-2 redundant calls per token

---

### 3. Implement Request Batching (MEDIUM PRIORITY)

**Location:** `helius_fetcher.py` - new module

**Concept:** Request queue + batch flush
```python
class HeliusBatchQueue:
    def __init__(self, flush_interval=1.0):  # 1 second batching window
        self.pending_tokens = []
        self.flush_interval = flush_interval

    async def queue_metadata_request(self, token_address):
        self.pending_tokens.append(token_address)
        # If queue reaches 10 or 1s elapsed, flush batch
        if len(self.pending_tokens) >= 10:
            return await self._flush_batch()

    async def _flush_batch(self):
        # Single batch API call for all pending tokens
        result = await self.helius_fetcher.get_token_metadata_batch(self.pending_tokens)
        self.pending_tokens.clear()
        return result
```

**Expected Impact:** 50-70% reduction when multiple tokens arrive simultaneously

---

### 4. Increase Metadata Cache TTL (LOW RISK)

**Current:** No metadata cache (every call is fresh)
**Proposed:** 60 minutes → 2 hours (align with holder cache)

**Rationale:**
- Token name/symbol rarely change
- Price/liquidity are fetched separately (don't need fresh metadata)
- 2-hour staleness is acceptable for metadata

**Expected Impact:** Higher cache hit rate (fewer misses from expiration)

---

## Expected Total Savings (OPT-041)

**Before OPT-041:**
- Holder checks: 10 credits × gating (80-85% already saved by OPT-055)
- Metadata calls: 1-2 credits × 3 redundant calls per token = 3-6 credits wasted
- Tokens per day: ~50-100 tracked
- **Metadata waste alone:** 150-600 credits/day

**After OPT-041:**
- Metadata cache: 90% hit rate → 15-60 credits/day (vs 150-600)
- Eliminate direct calls: 50-100 fewer calls/day
- Batching (when applicable): 50-70% savings on bursts

**Total Expected Reduction:** 40-60% of remaining credits (OPT-055 already saved 80-85%)

**Monetary Impact:**
- Current usage: 1.1M / 10M credits (11%)
- After OPT-041: Target <0.7M credits (7%)
- Extends credit runway significantly

---

## Implementation Priority

1. ✅ **Add metadata_cache to helius_fetcher.py** (15 min)
2. ✅ **Replace direct API call in active_token_tracker.py:240** (5 min)
3. ✅ **Increase metadata cache TTL to 2 hours** (2 min)
4. ⏳ **Implement batch queue** (optional - 30 min, for multi-token scenarios)

**Total Implementation Time:** 20-50 minutes

---

## Testing Plan

1. **Deploy changes** to Railway
2. **Monitor credit usage** for 6 hours using `credit_tracker.py`
3. **Compare before/after**:
   - Credits per signal
   - Cache hit rates
   - Total Helius credits used
4. **Keep if:** Credits per signal drops >40% with no quality degradation
5. **Metrics to track:**
   - `credits_saved` in logs
   - Cache hit rate for metadata
   - Total API calls per hour

---

## Conclusion

**OPT-041 is READY for implementation.**

**Quick wins:**
- Metadata caching (15 min implementation, 90% savings)
- Eliminate redundant direct call (5 min, immediate savings)

**Total Expected Impact:**
- 40-60% reduction in remaining Helius credits
- Extends credit budget significantly
- No quality loss (metadata rarely changes)

**Next Step:** Implement changes and deploy to Railway for monitoring.
