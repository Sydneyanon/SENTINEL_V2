# Ralph Troubleshooting Guide

## "Invalid API key · Please run /login" Error

### Symptoms
```
===============================================================
  Ralph Iteration 1 of 30 (claude)
===============================================================
Invalid API key · Please run /login
Iteration 1 complete. Continuing...
```

This error repeats for every iteration (1-30).

### Root Cause

The Dockerfile was configured to use `--tool claude`, which requires the Claude Code CLI to be authenticated via `claude /login`. This is an **interactive process** that:

1. Opens a browser for OAuth authentication
2. Stores credentials in `~/.claude/` directory
3. Doesn't work in Railway's non-interactive container environment
4. Gets lost on container restarts (ephemeral storage)

### Solution

**✅ FIXED**: Changed Dockerfile to use `--tool api` instead.

The `--tool api` option uses the Anthropic Python SDK directly via `ralph_api.py`, which:
- Reads `ANTHROPIC_API_KEY` from environment variables (no interactive login needed)
- Works perfectly in Railway's non-interactive containers
- Is the recommended approach for production deployments

### Verification

After the fix, you should see:

```
===============================================================
  Ralph Iteration 1 of 30 (api)
===============================================================
[INFO] Ralph iteration starting...
[INFO] API key found (length: 108)
[INFO] Calling Claude API for optimization iteration...
[INFO] API call successful
```

### Environment Variables Required

For `--tool api` to work, set these in Railway dashboard:

```bash
ANTHROPIC_API_KEY=sk-ant-api03-...  # Get from https://console.anthropic.com/
DATABASE_URL=postgresql://...        # Copy from main bot service
GIT_AUTHOR_NAME=Ralph Bot
GIT_AUTHOR_EMAIL=ralph@prometheus.bot
GITHUB_TOKEN=ghp_...                # For pushing commits
RALPH_DEBUG=false                   # Reduce Railway log spam
```

### Tool Comparison

| Feature | `--tool api` (✅ Recommended) | `--tool claude` (❌ Doesn't work in Railway) |
|---------|---------------------------|-------------------------------------------|
| **Authentication** | Environment variable (`ANTHROPIC_API_KEY`) | Interactive OAuth (`claude /login`) |
| **Railway Compatible** | ✅ Yes | ❌ No (non-interactive) |
| **Persistent Auth** | ✅ Always (env var) | ❌ Lost on restart |
| **Setup Complexity** | ✅ Simple (set env var) | ❌ Complex (manual login) |
| **Code Execution** | ❌ Limited (API only) | ✅ Full (Bash, Git, Edit tools) |
| **Use Case** | ✅ Railway production | Local development only |

### Why Was Claude CLI Used Initially?

The Claude Code CLI provides more powerful tools (Bash, Git, Edit) that allow Ralph to:
- Make code changes directly
- Run git commands
- Execute tests and builds
- Push commits

However, the **authentication requirement** makes it unsuitable for Railway deployment.

### Future Enhancement

Consider implementing a **hybrid approach**:
1. Use `--tool api` to **decide what to do** (planning/analysis)
2. Use local scripts to **execute changes** (git, file edits, tests)
3. Maintain Railway compatibility while gaining execution power

This would combine the best of both worlds.

---

## Other Common Issues

### "ANTHROPIC_API_KEY not set"

**Symptom:**
```
[ERROR] ANTHROPIC_API_KEY not set
[INFO] Ralph iteration finished (exit code: 1)
```

**Solution:**
Set the environment variable in Railway dashboard or locally:
```bash
export ANTHROPIC_API_KEY="sk-ant-api03-..."
```

### "Railway Logs Limit Exceeded"

**Symptom:**
Container crashes with "Log rate limit exceeded (500 lines/second)"

**Solution:**
Set `RALPH_DEBUG=false` in Railway environment variables:
```bash
RALPH_DEBUG=false  # Only show summaries, not full API responses
```

### "Git author not configured"

**Symptom:**
```
Warning: GIT_AUTHOR_NAME or GIT_AUTHOR_EMAIL not set. Using defaults.
```

**Solution:**
Set git configuration in Railway:
```bash
GIT_AUTHOR_NAME=Ralph Bot
GIT_AUTHOR_EMAIL=ralph@prometheus.bot
```

### "Failed to push commits"

**Symptom:**
```
fatal: could not read Username for 'https://github.com': terminal prompts disabled
```

**Solution:**
Set GitHub token in Railway:
```bash
GITHUB_TOKEN=ghp_yourtokenhere
```

Generate a token at: https://github.com/settings/tokens
- Scope required: `repo` (full control of private repositories)

---

## Monitoring Ralph's Progress

### Check Logs
```bash
# Railway
railway logs --service ralph-optimizer --follow

# Local
tail -f ralph/progress.txt
```

### Check Commits
```bash
# See Ralph's commits
git log --oneline --author="Ralph" --all

# See what Ralph changed
git show <commit-hash>
```

### Check PRD Status
```bash
# View optimization progress
cat ralph/prd.json | jq '.userStories[] | select(.passes == false) | {id, title, priority}'
```

### Verify Ralph is Working

**Healthy output (API tool):**
```
[INFO] Ralph iteration starting...
[INFO] API key found (length: 108)
[INFO] Calling Claude API for optimization iteration...
[INFO] API call successful

Ralph's thinking about the next optimization...
(Response from Claude)
```

**Unhealthy output (Claude CLI without auth):**
```
Invalid API key · Please run /login
Invalid API key · Please run /login
Invalid API key · Please run /login
```

---

## Getting Help

1. Check `ralph/progress.txt` for Ralph's latest status
2. Check Railway logs for errors
3. Verify environment variables are set
4. Try running locally first: `./ralph.sh --tool api 1`
5. Report issues with full logs at: https://github.com/Sydneyanon/SENTINEL_V2/issues

---

**Last Updated**: 2026-01-23
**Issue Fixed**: Dockerfile now uses `--tool api` for Railway compatibility
