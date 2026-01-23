# Quick Start: Get Ralph Running

Ralph is ready to go! Here are your options:

## Option 1: Run Locally (Quick Start)

If you have an Anthropic API key, run Ralph locally:

```bash
# Set your API key (get one from https://console.anthropic.com/)
export ANTHROPIC_API_KEY="sk-ant-api03-..."

# Set your database URL (same as the main bot)
export DATABASE_URL="postgresql://..."

# Optional: Enable debug logging (default: off to reduce log spam)
export RALPH_DEBUG="true"

# Run Ralph (10 iterations = ~20-40 hours total)
cd /home/user/SENTINEL_V2/ralph
./ralph.sh --tool api 10
```

Ralph will run in your terminal. Use `screen` or `tmux` if you want to detach:

```bash
# Start a screen session
screen -S ralph

# Inside screen, run Ralph
cd /home/user/SENTINEL_V2/ralph
export ANTHROPIC_API_KEY="sk-ant-api03-..."
export DATABASE_URL="postgresql://..."
export RALPH_DEBUG="false"  # Reduce log spam (Railway has 500 lines/sec limit)
./ralph.sh --tool api 10

# Detach: Press Ctrl+A then D
# Reattach later: screen -r ralph
```

## Option 2: Deploy to Railway (Recommended for 24/7)

For continuous autonomous optimization while you sleep:

### 1. Install Railway CLI

```bash
npm install -g @railway/cli
```

### 2. Link to Railway Project

```bash
cd /home/user/SENTINEL_V2
railway link
```

### 3. Create Ralph Service

```bash
# Create the service
railway service create ralph-optimizer

# Set environment variables via Railway dashboard:
# - ANTHROPIC_API_KEY: Your API key from console.anthropic.com
# - DATABASE_URL: Same as main bot (copy from main service)
# - GIT_AUTHOR_NAME: "Ralph Bot"
# - GIT_AUTHOR_EMAIL: "ralph@prometheus.bot"
# - GITHUB_TOKEN: Your GitHub token for pushing commits
# - RALPH_DEBUG: "false" (keep logs minimal, Railway has 500 lines/sec limit)
```

### 4. Deploy

```bash
cd ralph
railway up --service ralph-optimizer
```

### 5. Monitor

```bash
# Watch logs
railway logs --service ralph-optimizer --follow

# Check progress
git log --oneline --author="Ralph" --all
cat ralph/progress.txt
```

## What Ralph Does

1. Picks highest priority optimization from `prd.json`
2. Collects baseline metrics (2-4 hours)
3. Makes code changes
4. Deploys to Railway
5. Monitors performance (2-4 hours)
6. Analyzes results
7. Keeps changes if better, reverts if worse
8. Updates `prd.json` and `progress.txt`
9. Repeats with next optimization

## Current Optimizations

Ralph will work through these in priority order:

- **OPT-001**: Optimize conviction score threshold (2h)
- **OPT-002**: Reduce Helius API credit waste (2h)
- **OPT-003**: Auto-discover high-performing wallets (4h)
- **OPT-004**: Tune bundle detection penalties (2h)
- **OPT-005**: Build ML prediction layer (4h)
- **OPT-013**: Auto-fix runtime errors from Railway logs (2h)
- **OPT-014**: Optimize metadata collection (2h)
- **OPT-015**: Optimize price data fetching (2h)
- **OPT-016**: Track KOL performance (7d)
- **OPT-017**: Auto-tune scoring weights with ML (3d)
- ...and more (see `prd.json`)

## Stopping Ralph

**Gracefully (wait for current iteration):**
```bash
# If running locally: Ctrl+C
# If on Railway: Stop the service from dashboard
```

## Troubleshooting

**"No ANTHROPIC_API_KEY set"**
- Get an API key from https://console.anthropic.com/
- Set it: `export ANTHROPIC_API_KEY="sk-ant-..."`

**"No DATABASE_URL set"**
- Copy from your main bot's Railway service environment variables
- Set it: `export DATABASE_URL="postgresql://..."`

**Railway CLI not found**
- Install: `npm install -g @railway/cli`
- Login: `railway login`

## Next Steps

1. Choose Option 1 (local) or Option 2 (Railway)
2. Run Ralph
3. Go to bed! 😴
4. Wake up to optimized signals 🚀

Ralph will commit all changes to git and document learnings in `progress.txt`.

---

**All dependencies are installed. Ralph is ready to optimize!** 🤖
