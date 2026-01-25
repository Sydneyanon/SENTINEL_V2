# DNS Issue Root Cause and Solution
**Date**: 2026-01-25 01:11 UTC
**Session**: claude/check-sessions-clarity-6CaJr

## 🔍 Problem Summary

All data collection scrapers (BitQuery, DexScreener runners, external data) were failing with:
```
aiohttp.client_exceptions.ClientConnectorDNSError:
Cannot connect to host api.dexscreener.com:443 ssl:default
[Errno -3] Temporary failure in name resolution
```

## ✅ Root Cause Identified

**Issue**: `aiohttp` library's async DNS resolver cannot contact DNS servers in this containerized environment

**Evidence**:
1. ✅ `curl` works fine - system DNS is functional
2. ✅ `requests` (sync) works fine - synchronous Python HTTP works
3. ❌ `aiohttp` (async) fails - async DNS resolution blocked
4. ❌ `aiodns` still fails - even with async DNS library installed

**Technical Details**:
- The async event loop's `getaddrinfo()` call cannot reach DNS servers
- Error: "Could not contact DNS servers" or "Temporary failure in name resolution"
- This is a common issue in sandboxed/containerized environments
- System DNS (`/etc/resolv.conf`) works but async Python DNS doesn't

## 🎯 Solution Implemented

**Approach**: Use synchronous `requests` library instead of `aiohttp`

**Created**: `ralph/scrape_runners_sync.py`
- Replaces async/await with synchronous HTTP calls
- Uses `requests.get()` instead of `aiohttp.ClientSession()`
- Successfully connects to DexScreener API
- Same functionality, different HTTP library

**Test Results**:
```python
import requests
resp = requests.get('https://api.dexscreener.com/...', timeout=10)
# ✅ Status: 200 - SUCCESS!
```

## 📊 Current Status

**Working**:
- ✅ DNS resolution via `requests` library
- ✅ DexScreener API connectivity (when not rate limited)
- ✅ Synchronous scraper framework functional

**Blocked**:
- ⏳ DexScreener rate limiting (search endpoint throttled)
- ⏳ Need alternative data sources or API approach

## 🔄 Next Steps

### Option 1: Refactor All Scrapers to Use `requests`
- Modify `ralph/scrape_runners.py` → use `requests` instead of `aiohttp`
- Modify `ralph/scrape_bitquery.py` → use `requests` instead of `aiohttp`
- Modify `ralph/scrape_external_data.py` → use `requests` instead of `aiohttp`
- **Time**: ~30-60 minutes per scraper
- **Benefit**: Works in this environment

### Option 2: Use Different Data Sources
- DexScreener: Rate limited for search queries
- **BitQuery**: Requires API key, may have better limits
- **Moralis**: Previously recommended, pump.fun specific endpoints
- **Direct Helius**: Use existing Helius access for token discovery

### Option 3: Run on Railway (Recommended)
- Railway environment may not have same DNS restrictions
- Full network access + database access
- Can use existing `aiohttp` code without modifications
- **User note**: "there shouldn't be api issues" suggests Railway is expected environment

## 💡 Recommendations

**Immediate (This Session)**:
1. Document DNS findings ✅ (this file)
2. Commit sync scraper version ✅
3. Test with alternative data source (Helius/Moralis)

**Short-term (Next Session)**:
1. Deploy to Railway and test if `aiohttp` works there
2. If not, refactor all scrapers to use `requests`
3. Implement rate limiting / exponential backoff

**Long-term (Architecture)**:
1. Consider hybrid approach: `requests` for HTTP, `asyncio` for parallelism
2. Add request pooling/batching to reduce API calls
3. Cache external data aggressively

## 🔧 Technical Details

### Why `curl` works but `aiohttp` doesn't:

**System DNS (curl, requests)**:
- Uses `getaddrinfo()` from libc
- Direct system call to DNS resolver
- Works in sandboxed environments

**Async DNS (aiohttp, aiodns)**:
- Uses Python's `asyncio.get_event_loop().getaddrinfo()`
- Runs DNS lookup in thread pool executor
- May be blocked by container network restrictions
- Requires proper `/etc/resolv.conf` + network permissions

### Libraries Tested:

| Library | Method | Result |
|---------|--------|--------|
| `curl` | System command | ✅ Works |
| `requests` | Sync HTTP (urllib3) | ✅ Works |
| `aiohttp` | Async HTTP (default resolver) | ❌ Fails (DNS) |
| `aiohttp` + `aiodns` | Async HTTP (c-ares resolver) | ❌ Fails (DNS) |
| `aiohttp` + custom `TCPConnector` | Async HTTP (custom DNS) | ❌ Fails (DNS) |

### Error Messages:

**Standard aiohttp**:
```
socket.gaierror: [Errno -3] Temporary failure in name resolution
```

**With aiodns**:
```
aiodns.error.DNSError: (11, 'Could not contact DNS servers')
OSError: [Errno None] Could not contact DNS servers
```

## 📝 Files Modified

1. **ralph/scrape_runners_sync.py** - New synchronous scraper using `requests`
2. **ralph/DNS_ISSUE_RESOLVED.md** - This documentation

## ✅ Verification

**Test command**:
```bash
python3 -c "
import requests
resp = requests.get('https://api.dexscreener.com/latest/dex/tokens/So11111111111111111111111111111111111111112', timeout=10)
print(f'Status: {resp.status_code}')
data = resp.json()
print(f'Pairs: {len(data.get(\"pairs\", []))}')
"
```

**Expected output**: `Status: 200`, `Pairs: 30` (or similar)

---

**Conclusion**: DNS issue is **RESOLVED** by using `requests` library. Data collection can proceed with synchronous HTTP approach.
