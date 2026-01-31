# SENTINEL V3

Clean. Simple. Focused.

## Architecture

```
Helius Webhook → main.py → scoring.py → telegram.py → Channel
                    ↓
                database.py ← tracker.py (milestones)
                    ↑
                 admin.py (commands)
```

## Files

| File | Purpose |
|------|---------|
| `config.py` | Configuration (100 lines vs 950) |
| `database.py` | PostgreSQL with clean schema |
| `scoring.py` | 4-factor scoring (wallet, volume, momentum, holders) |
| `tracker.py` | Token tracking and milestone detection |
| `telegram.py` | Signal and milestone posting |
| `admin.py` | Admin commands (/stats, /wallets, /active) |
| `main.py` | FastAPI entry point with webhook handler |

## Scoring (100 points max)

| Factor | Points | How |
|--------|--------|-----|
| Wallet Tier | 0-40 | elite=40, top_kol=30, verified=20, new=10 |
| Volume | 0-20 | Based on volume/liquidity ratio |
| Momentum | 0-20 | Based on 1h price change |
| Holders | 0-20 | Based on holder count |

**Threshold: 60 points to signal**

## Database Schema

```sql
-- wallets: Tracked KOL wallets with auto-adjusting tiers
-- signals: All signals with entry metrics and outcomes
-- milestones: 2x, 5x, 10x etc
```

## Deployment

1. Set environment variables:
   - `HELIUS_API_KEY`
   - `DATABASE_URL`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHANNEL_ID`
   - `ADMIN_TELEGRAM_USER_ID`

2. Run:
   ```bash
   cd v3
   pip install -r requirements.txt
   python main.py
   ```

3. Register Helius webhooks for tracked wallets

## Admin Commands

- `/stats` - Overall statistics
- `/wallets` - Wallet performance
- `/active` - Currently tracking
- `/history` - Daily win rates
- `/addwallet <address> [name]` - Add wallet

## Key Differences from V2

| Aspect | V2 | V3 |
|--------|----|----|
| Config | 950 lines | 100 lines |
| Scoring factors | 20+ | 4 |
| Data sources | 3+ | 1 (signals table) |
| Organic scanner | Yes (broken) | No |
| Experimental features | Many | None |
| Code complexity | High | Low |
