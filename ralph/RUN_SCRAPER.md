# Run External Data Scraper on Railway

## Quick Run (Railway CLI)

```bash
railway run python ralph/scrape_external_data.py
```

## Or via Railway Dashboard

1. Go to Railway dashboard
2. Open your main Prometheus service (not ralph-optimizer)
3. Click "Settings" → "Deploy"
4. Add a one-time command:
   ```
   python ralph/scrape_external_data.py
   ```

## What It Does

- Fetches 500 graduated pump.fun tokens
- Filters for tokens with $100k+ market cap
- Checks which KOLs bought them (2-3 Helius credits per token)
- Discovers 200-300 new potential KOL wallets
- Saves results to `ralph/external_data.json`

**Cost:** ~2,500 Helius credits (0.025% of 8.9M budget)
**Time:** ~10-15 minutes

## After It Completes

Run the pattern analyzer:
```bash
python ralph/analyze_patterns.py
```

This will discover:
- Optimal KOL count thresholds
- Holder distribution patterns
- Security score patterns
- Volume/liquidity sweet spots
- Best launch timing windows
