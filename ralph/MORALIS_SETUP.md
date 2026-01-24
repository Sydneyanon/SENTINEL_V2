# Moralis API Setup (1 Minute)

## Why Moralis?

Moralis has a **dedicated pump.fun graduated tokens endpoint** that provides:
- ✅ Exact graduation timestamps (when bonding curve completed)
- ✅ Historical data (10K+ graduated tokens from 2024-2026)
- ✅ Rich metadata: price, liquidity, MCAP, token info
- ✅ FREE tier: 2 calls/sec, 1M units/month (no credit card needed)
- ✅ Pagination support for bulk data collection

**This is PERFECT for Ralph's ML learning pipeline.**

## Quick Setup

### 1. Sign Up (30 seconds)

Go to: https://moralis.com

- Click "Start for Free"
- Sign up with email or Google
- **NO credit card required** for free tier

### 2. Get API Key (15 seconds)

After signup:
1. Go to dashboard: https://admin.moralis.io
2. Click "API Keys" in sidebar
3. Copy your **Solana API Key** (starts with "eyJ...")

### 3. Add to Railway (15 seconds)

In Railway dashboard:
1. Go to your **Ralph optimizer service** (not main bot)
2. Click "Variables" tab
3. Add new variable:
   - **Name**: `MORALIS_API_KEY`
   - **Value**: `<paste your API key>`
4. Click "Deploy" (Railway will restart Ralph with new env var)

**Important**: Add to Ralph's service, not the main Prometheus bot!

**Done! Ralph can now collect 1000 graduated tokens.**

## API Endpoint Details

**Endpoint**: `GET https://solana-gateway.moralis.io/token/mainnet/exchange/pumpfun/graduated`

**Headers**: `X-API-Key: <your_key>`

**Parameters**:
- `limit`: Number of tokens per page (max 100)
- `cursor`: Pagination cursor for next page

**Response Example**:
```json
{
  "tokens": [
    {
      "tokenAddress": "ABCD1234...",
      "name": "Example Token",
      "symbol": "EX",
      "logo": "https://...",
      "decimals": 9,
      "priceNative": "0.001 SOL",
      "priceUsd": "$0.15",
      "liquidity": "100 SOL",
      "fullyDilutedValuation": "$150000",
      "graduatedAt": "2026-01-24T15:30:00Z"
    }
  ],
  "cursor": "next_page_token"
}
```

## Rate Limits (Free Tier)

- **2 requests/second** (our scraper respects this with 0.6s delay)
- **1M compute units/month** (1 graduated tokens request = ~10 CUs)
- **~100K API calls/month** on free tier

**For 1000 tokens**: 10 API calls (100 tokens/page) = **100 compute units**

Plenty of headroom for daily analysis!

## Cost Comparison

| Source | Cost | Reliability | Data Quality |
|--------|------|-------------|--------------|
| pump.fun API | Free | ❌ Unreliable (DNS issues) | Good |
| DexScreener | Free | ⚠️ Generic (all DEXs) | Okay |
| **Moralis** | **Free** | **✅ Excellent** | **Perfect for pump.fun** |

**Winner**: Moralis - dedicated pump.fun endpoint with exact graduation data

## What Ralph Will Learn

With Moralis data, Ralph can discover:

1. **Time patterns**: "Tokens graduating 2-4 PM UTC perform 2x better"
2. **MCAP patterns**: "Tokens hitting $200k+ within 1h of grad = 80% win rate"
3. **Liquidity patterns**: "Graduated tokens with >150 SOL liquidity rarely rug"
4. **Volume patterns**: "High volume in first 30min post-grad = momentum indicator"
5. **KOL timing**: "KOLs buying within 5min of graduation = highest conviction"

All of this is possible because Moralis provides **exact graduation timestamps**.

## Support

- **Docs**: https://docs.moralis.io/web3-data-api/solana/reference
- **Discord**: https://moralis.io/discord (active community)
- **Free tier**: Sufficient for analysis (upgrade to Pro if scaling to 24/7 monitoring)

---

**TL;DR**: Sign up at moralis.com → Get API key → Add to Railway as `MORALIS_API_KEY` → Run scraper!
