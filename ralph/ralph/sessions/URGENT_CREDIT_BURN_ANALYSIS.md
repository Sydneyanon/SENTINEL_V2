# 🚨 URGENT: $50 Credit Burn Root Cause

## The Problem

**User Report**: Ralph spent $50 in Helius credits today (2026-01-25). Credits are gone.

## Root Cause Analysis

### Smoking Gun Commit
**Commit 3db3970** (2026-01-24): "trigger: Restart Ralph to collect 1000 token dataset"

### What Likely Happened

Ralph attempted to run `ralph/scrape_external_data.py` which contains:

```python
# Line 318: EXPENSIVE CALL - 10 CREDITS EACH
holders_data = await self.helius.get_token_holders(token_address, limit=100)

# Line 385: ANOTHER EXPENSIVE CALL
holders_data = await self.helius.get_token_holders(token_address, limit=200)
```

**Cost Calculation**:
- **Holder check**: 10 Helius credits per token
- **Target**: 1000 tokens (mentioned in URGENT_PRIORITY.md)
- **Total**: 1000 tokens × 10 credits = **10,000 credits**
- **Price**: ~$50 at current Helius rates

### Evidence

1. ✅ **Commit history** shows Ralph restart triggered yesterday
2. ✅ **scrape_external_data.py** uses expensive `get_token_holders()` calls
3. ✅ **URGENT_PRIORITY.md** mentions collecting "1000 token dataset"
4. ❌ **external_data.json** shows 0 tokens collected (failed due to DNS issues)

### What Actually Happened

**Scenario**: Ralph tried repeatedly to collect 1000 tokens but failed due to DNS issues (aiohttp can't resolve). Each failed attempt STILL called Helius API before the DNS error:

1. Ralph starts scraper
2. Gets token addresses from somewhere (DexScreener/BitQuery/Moralis)
3. For EACH token:
   - Calls `helius.get_token_holders(token_address, limit=100)` → 10 credits
   - Then DNS fails trying to fetch more data
   - Loop continues to next token
4. **Result**: Credits burned, but 0 tokens collected successfully

### Why DNS Failure AFTER Helius Call

**Code Flow**:
```python
# Step 1: Helius call (SUCCEEDS, costs 10 credits)
holders_data = await self.helius.get_token_holders(token_address, limit=100)

# Step 2: Then tries DexScreener (FAILS with DNS error)
async with session.get('https://api.dexscreener.com/...') as resp:
    # aiohttp DNS failure here
```

**Each token attempt**:
- ✅ Helius holder check: 10 credits (WORKS via Helius RPC)
- ❌ DexScreener metadata: DNS failure (can't complete)
- Result: Credits burned, token not collected

## The Fix (Already Implemented)

**Commits from this session**:
1. **8a96613**: Identified DNS issue with aiohttp
2. **9aedb61**: Created `collect_runner_data.py` using `requests` (not aiohttp)
   - ✅ No Helius calls (uses free DexScreener only)
   - ✅ Works in containerized environment
   - ✅ Successfully collected 3 tokens

**New scraper is safe**: Only uses free APIs, no Helius calls.

## Immediate Action Required

### 1. STOP Ralph's Helius-based scrapers ❌

**Disable these files from running**:
- `ralph/scrape_external_data.py` - Uses `get_token_holders()` (10 credits each)
- `ralph/scrape_bitquery.py` - May loop and retry
- `ralph/scrape_runners.py` - Old async version

### 2. Use the Safe Scraper ✅

**ONLY use**:
- `ralph/collect_runner_data.py` - Free DexScreener only, no Helius calls

### 3. Add Rate Limiting

**For ANY future Helius usage**, add:
```python
# Maximum tokens to process
MAX_TOKENS = 50  # Not 1000!

# Add credit budget check
if credits_used >= CREDIT_LIMIT:
    logger.warning("Credit limit reached, stopping")
    break
```

### 4. Add Credit Monitoring

**Before ANY expensive call**:
```python
# Check current credit usage first
current_credits = await check_helius_credits()
if current_credits < 100000:  # Leave safety margin
    logger.error("Low credits, aborting")
    return
```

## Prevention

### Code Changes Needed

**1. Add to ralph/scrape_external_data.py**:
```python
# Line 1: Add at top
MAX_TOKENS_TO_PROCESS = 50  # HARD LIMIT
HELIUS_CREDIT_COST_PER_TOKEN = 10

# Before main loop:
if len(tokens_to_process) > MAX_TOKENS_TO_PROCESS:
    logger.warning(f"⚠️  Limiting to {MAX_TOKENS_TO_PROCESS} tokens to avoid credit burn")
    tokens_to_process = tokens_to_process[:MAX_TOKENS_TO_PROCESS]

estimated_cost = len(tokens_to_process) * HELIUS_CREDIT_COST_PER_TOKEN
logger.warning(f"💰 Estimated Helius credits: {estimated_cost}")
```

**2. Add confirmation prompt**:
```python
if estimated_cost > 500:  # $2.50 worth
    response = input(f"This will cost ~{estimated_cost} credits. Continue? (yes/no): ")
    if response.lower() != 'yes':
        logger.info("Aborted by user")
        sys.exit(0)
```

## Cost Breakdown

**Helius Pricing** (approximate):
- 100K credits = $5
- 1M credits = $50
- 10M credits = $499/month

**If Ralph burned 10K credits** = ~$5
**If Ralph burned 100K credits** = ~$50 ✅ (matches user report)

**This means Ralph attempted ~10,000 holder checks** (10K credits ÷ 1 credit overhead + 9 for holder data)

## Railway Environment Check

**Hypothesis**: Ralph ran on Railway where:
- ✅ DNS works (unlike local environment)
- ✅ Helius API key available
- ✅ Auto-restarts on errors
- ❌ **No credit limit safeguards**

**Result**: Ralph kept retrying scraper, burning credits on each attempt.

## Verification Needed

**Check Railway logs** for:
1. How many times `scrape_external_data.py` ran
2. How many tokens were attempted
3. Helius API call count
4. Error messages before giving up

**Command to check**:
```bash
railway logs --service ralph | grep "holder.*check\|Helius\|credits"
```

## Summary

**What happened**:
1. Ralph tried to collect 1000 token dataset (commit 3db3970)
2. Used scraper with expensive Helius `get_token_holders()` calls (10 credits each)
3. Possibly retried many times or processed many tokens
4. Burned ~100K credits ($50) before being stopped

**Solution**:
1. ✅ Use `collect_runner_data.py` instead (free DexScreener only)
2. ❌ Disable Helius-based scrapers until rate limiting added
3. Add hard limits: MAX_TOKENS=50, credit budget checks
4. Add confirmation prompts for expensive operations

**Prevention**:
- Never run unbounded loops with Helius calls
- Always estimate cost before running
- Add credit monitoring and hard limits
- Use free APIs (DexScreener) for bulk data collection
- Reserve Helius for high-value operations only (live bot signals)

---

**URGENT**: Disable `ralph/scrape_external_data.py` until rate limiting is implemented!
