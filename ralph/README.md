# Ralph - Autonomous Optimization for Prometheus Bot

Ralph is an autonomous AI agent loop that continuously optimizes the Prometheus memecoin signals bot.

Based on the [Ralph pattern by Geoffrey Huntley](https://ghuntley.com/ralph/).

## What Ralph Does

Ralph runs optimization experiments autonomously:

1. **Deploy** a config change to Railway
2. **Monitor** performance metrics for 2-4 hours
3. **Analyze** what worked and what didn't
4. **Keep or Revert** based on data
5. **Repeat** indefinitely

## Current Optimizations

See `prd.json` for the full list. Examples:

- **OPT-001**: Tune conviction score threshold (65 → 70 → 75 → 80)
- **OPT-002**: Reduce Helius API credit usage
- **OPT-003**: Auto-discover high-performing wallets from DB
- **OPT-004**: Optimize bundle detection penalties
- **OPT-005**: Build ML prediction layer for signals

## Setup

### Prerequisites

- Claude Code installed: `npm install -g @anthropic-ai/claude-code`
- Railway CLI installed: `npm install -g @railway/cli`
- Railway project linked: `railway link`
- DATABASE_URL environment variable set (for metrics collection)

### Quick Start

```bash
# From project root
cd ralph

# Run Ralph (max 10 iterations, ~20-40 hours total)
./ralph.sh --tool claude 10
```

Ralph will:
1. Pick highest priority optimization with `passes: false`
2. Collect baseline metrics
3. Make changes
4. Deploy to Railway
5. Monitor for required duration
6. Analyze results
7. Keep or revert
8. Update `prd.json` and `progress.txt`
9. Move to next optimization

## Monitoring Duration

Each optimization specifies monitoring time in acceptance criteria:
- **2 hours**: Quick experiments (threshold changes)
- **4 hours**: Complex changes (new features, ML models)

Ralph automatically waits the required duration before analyzing.

## Metrics Tracked

**Signal Quality:**
- `signals_posted`: Total signals sent
- `avg_conviction`: Average conviction score
- `avg_roi`: Average ROI (when implemented)

**Credit Efficiency:**
- `estimated_helius_credits`: Total API credits used
- `credits_per_signal`: Efficiency metric

**Smart Wallet Activity:**
- `total_kol_buys`: KOL purchases detected
- `unique_kols`: Number of unique KOL wallets active

## Manual Metrics Collection

```bash
# Collect current metrics (2 hours)
python collect_metrics.py --duration 120

# Save as baseline for OPT-001
python collect_metrics.py --duration 120 --save-baseline OPT-001

# Compare to baseline
python collect_metrics.py --duration 120 --compare OPT-001
```

## Files

| File | Purpose |
|------|---------|
| `ralph.sh` | The autonomous loop (spawns Claude Code) |
| `CLAUDE.md` | Prompt template for optimization agent |
| `prd.json` | Optimization tasks with pass/fail status |
| `collect_metrics.py` | Performance metrics collection |
| `progress.txt` | Append-only learnings log |

## Stopping Ralph

- **Ctrl+C** to stop mid-loop
- Ralph auto-stops when all optimizations have `passes: true`
- Or when max iterations reached

## Safety

- Each iteration commits changes
- Failed experiments are reverted via `git reset`
- Railway auto-deploys from main (feature branches safe)
- Database is read-only for metrics (no data loss risk)

## Customizing

Edit `prd.json` to add/remove optimizations:

```json
{
  "id": "OPT-XXX",
  "title": "Your optimization",
  "description": "What it does",
  "acceptanceCriteria": [
    "Specific measurable goals",
    "Monitor for X hours",
    "Commit if metric improves >Y%"
  ],
  "priority": 1,
  "passes": false
}
```

## Example Session

```bash
$ ./ralph.sh --tool claude 5

===============================================================
  Ralph Iteration 1 of 5 (claude)
===============================================================

📊 Working on: OPT-001 - Optimize conviction score threshold
📊 Collecting baseline metrics...
✅ Baseline: 12 signals, 73.5 avg conviction, ~120 credits

🔧 Testing conviction threshold: 70 (current: 65)
📝 Updated config.py: MIN_CONVICTION_SCORE = 70
🚀 Deployed to Railway
⏳ Monitoring for 2 hours...

📈 Results: 8 signals, 78.2 avg conviction, ~80 credits
✅ KEEP: Conviction +6.4%, Credits -33%
💾 Committed changes

===============================================================
  Ralph Iteration 2 of 5 (claude)
===============================================================
...
```

## Troubleshooting

**"No DATABASE_URL set":**
```bash
export DATABASE_URL="postgresql://user:pass@host:port/db"
```

**"Railway deploy failed":**
- Check Railway dashboard for errors
- Ensure PR was merged to main
- Wait 2-3 minutes for deployment

**"Metrics look wrong":**
- Check monitoring duration (might be too short)
- Verify database has recent data
- Check Railway logs for bot errors

## Next Steps

After Ralph completes optimizations:

1. Review `progress.txt` for learnings
2. Check `prd.json` for which optimizations worked
3. Add new optimization experiments
4. Run Ralph again!

---

**Ralph makes your bot smarter while you sleep.** 🤖💤
