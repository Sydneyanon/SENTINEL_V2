# Deploying Ralph to Railway

Ralph is an autonomous AI optimization loop that continuously improves the Prometheus bot. This guide shows how to run Ralph as a separate Railway service.

## Prerequisites

1. **Railway account** with CLI installed
2. **Anthropic API key** for Claude Code
3. **GitHub access token** for pushing optimizations
4. **Database access** (same Railway PostgreSQL as main bot)

## Setup Steps

### 1. Create New Railway Service

```bash
# In project root
railway link

# Create new service for Ralph
railway service create ralph-optimizer
```

### 2. Set Environment Variables

Go to Railway dashboard → ralph-optimizer service → Variables:

```bash
# Required: Anthropic API key for Claude Code
ANTHROPIC_API_KEY=sk-ant-api03-...

# Required: Database connection (same as main bot)
DATABASE_URL=postgresql://...

# Required: GitHub credentials for pushing optimizations
GITHUB_TOKEN=ghp_...
GIT_AUTHOR_NAME="Ralph Bot"
GIT_AUTHOR_EMAIL="ralph@prometheus.bot"

# Optional: Railway API token for deployments
RAILWAY_TOKEN=...

# Optional: Control Ralph behavior
RALPH_MAX_ITERATIONS=10
RALPH_TOOL=claude  # or 'amp'
```

### 3. Deploy Ralph

**Option A: Deploy from Railway Dashboard**

1. Go to Railway dashboard
2. Select `ralph-optimizer` service
3. Settings → Build → Dockerfile Path: `ralph/Dockerfile`
4. Settings → Deploy → Start Command: `bash /app/ralph/ralph.sh --tool claude 10`
5. Click "Deploy"

**Option B: Deploy via Railway CLI**

```bash
# From project root
cd ralph

# Deploy with Dockerfile
railway up --dockerfile Dockerfile --service ralph-optimizer
```

### 4. Monitor Ralph

**View Logs:**
```bash
railway logs --service ralph-optimizer
```

**Check Progress:**
Ralph logs all learnings to `ralph/progress.txt` (committed to git after each iteration).

```bash
# View progress file
cat ralph/progress.txt

# Or check via git
git log --oneline --author="Ralph" --all
```

## How Ralph Works

1. **Picks Optimization** - Selects highest priority task from `prd.json` with `passes: false`
2. **Collects Baseline** - Runs `collect_metrics.py` to get current performance
3. **Makes Changes** - Claude Code modifies code based on optimization goals
4. **Deploys to Main Bot** - Pushes to main branch (Railway auto-deploys main bot)
5. **Monitors** - Waits 2-4 hours for metrics (defined in acceptance criteria)
6. **Analyzes Results** - Compares new metrics to baseline
7. **Decides** - Keeps changes if better, reverts if worse
8. **Logs Learnings** - Appends insights to `progress.txt`
9. **Repeats** - Moves to next optimization

## Ralph's Decision Logic

**KEEP changes if:**
- Signal quality improves >10%
- Credit usage decreases >20%
- No regressions in other metrics

**REVERT changes if:**
- Signal quality drops >5%
- Credit usage increases
- Bot errors/crashes

## Optimization List

Ralph will run these in priority order (see `prd.json`):

1. **OPT-001**: Tune conviction threshold (quick - 2h)
2. **OPT-002**: Reduce Helius credit waste (quick - 2h)
3. **OPT-003**: Auto-discover high-performing wallets (medium - 4h)
4. **OPT-004**: Tune bundle detection penalties (quick - 2h)
5. **OPT-005**: Build ML prediction layer (complex - 4h)
6. **OPT-006**: On-chain data pipeline (complex - 4h)
7. **OPT-007**: RSS narrative detection (complex - 24h)
8. **OPT-008**: ML wallet discovery (complex - 7d)
9. **OPT-009**: Backtesting framework (medium - 4h)
10. **OPT-010**: Dynamic risk management (complex - 7d)
11. **OPT-011**: Telegram group tracking (complex - 7d)
12. **OPT-012**: ML learning engine (very complex - 14d)

## Cost Estimate

**Railway:**
- Ralph service: ~$5-10/month (runs intermittently)
- Shares database with main bot (no extra cost)

**Anthropic API:**
- ~100k tokens per optimization (~$0.30 with Claude Sonnet)
- 12 optimizations = ~$3.60 total
- Quick optimizations (OPT-001 to OPT-004): ~$1.20

**Total for initial run:** ~$8-15 one-time + ongoing Railway hosting

## Stopping Ralph

**Graceful stop:**
```bash
# Stop after current iteration completes
railway run bash -c "touch /app/ralph/STOP"
```

**Force stop:**
```bash
railway service stop ralph-optimizer
```

**Pause indefinitely:**
```bash
# Scale to 0 replicas
railway service scale --replicas 0 ralph-optimizer
```

## Troubleshooting

### Ralph keeps reverting changes
- Check if monitoring duration is too short (increase in `prd.json`)
- Verify baseline metrics were collected correctly
- Look for bot errors in main service logs

### "No DATABASE_URL" error
- Set DATABASE_URL env var in Railway (same as main bot)
- Verify database is accessible from Ralph service

### "ANTHROPIC_API_KEY not set"
- Set ANTHROPIC_API_KEY in Ralph service variables
- Verify API key is valid and has credits

### Ralph crashed mid-iteration
- Railway will auto-restart (up to 3 retries)
- Ralph will resume from last committed state
- Check logs: `railway logs --service ralph-optimizer`

### Changes deployed but bot not working
- Ralph automatically reverts on errors
- Check main bot logs for issues
- Manually revert: `git reset --hard HEAD~1 && git push -f`

## Safety Features

- ✅ All changes committed to git (easy rollback)
- ✅ Failed experiments auto-reverted
- ✅ Main bot unaffected by Ralph crashes
- ✅ Database read-only access (no data loss)
- ✅ Railway auto-restarts on failures

## Success Criteria

Ralph is working correctly if:
1. ✅ Logs show optimization iterations
2. ✅ `progress.txt` file gets updated with learnings
3. ✅ Git commits appear from "Ralph Bot"
4. ✅ Main bot metrics improve over time
5. ✅ No increase in errors/crashes

## Next Steps After Deployment

1. **Monitor first iteration** - Watch logs to ensure Ralph completes OPT-001
2. **Review progress.txt** - Read Ralph's learnings after each iteration
3. **Check main bot metrics** - Verify signals improve after optimizations
4. **Add custom optimizations** - Edit `prd.json` with your ideas
5. **Run indefinitely** - Let Ralph continuously optimize!

---

**Ralph makes your bot smarter while you sleep.** 🤖💤
