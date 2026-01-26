# Pull Request: Implement Grok Recommendations - Enhanced Scoring, Timing Rules & Monitoring

## 🎯 Overview

Implements all Grok recommendations to improve signal quality and reduce rug calls:
- **Phase 1:** Enhanced scoring system with graduated volume/momentum/velocity
- **Phase 2:** Timing/exit rules with early triggers, MCAP caps, and post-call monitoring

## 📊 Expected Impact

**Call Volume & Quality:**
- Target: 5-10 calls/day (from too many low-quality)
- Timing: 10-15K MCAP sweet spot (mid-cycle pumps)
- Rug reduction: "most" → ~30% (Grok estimate)

**Examples:**
- ✅ Catch SHRIMP-like mid-cycle pumps (early trigger at 30% bonding)
- 🚫 Avoid late entries at tops (MCAP cap at $25K)
- 🚨 Protect users with exit alerts (-15% in 5min)

---

## 🔧 Phase 1: Enhanced Scoring System

### 1. Threshold Adjustments
- **Pre-grad:** 35 → **45** (catch mid-cycle, not just early)
- **Post-grad:** 40 → **75** (much stricter, avoid tops)

### 2. Volume/Momentum/Velocity Enhancements
**More graduated scoring (less binary):**

**Volume:**
- Spiking (2x+): 10 pts
- Growing (1.25x+): 7 pts ⬆️ (was 5)
- Steady (1x+): 3 pts ✨ NEW

**Momentum:**
- Very strong (50%+): 10 pts
- Strong (30%+): 7 pts ⬆️ (was 5, threshold raised from 20%)
- Moderate (10%+): 3 pts ✨ NEW

**Velocity:**
- 30+: 10 pts ⬆️ (was 8)
- 20+: 8 pts ⬆️ (was 6)
- 10+: 5 pts ⬆️ (was 4)
- 5+: 3 pts ⬆️ (was 2)
- 2+: 1 pt ✨ NEW

### 3. Enabled Narratives
- \`ENABLE_NARRATIVES = True\` (was False)
- Adds 0-25 points for hot narratives (AI Agent, DeSci, RWA, etc.)
- Helps catch early trend plays

### 4. Stricter Rug Penalties
- **RugCheck extra penalty:** -10 if score >3/10
- **Dev sell detection:** Enabled (-20 if >20% sell)
- **Concentration improvement bonus:** +5 if top 10 decreases

### 5. Removed Twitter/LunarCrush
- Cleaned up unused weight dictionaries
- Already disabled, now fully removed from config

---

## ⚡ Phase 2: Timing & Exit Rules

### 1. Early Trigger System
**Catch mid-cycle pumps at 30% bonding**

### 2. MCAP Cap System
**Prevent late entries at tops**

### 3. Post-Call Monitoring
**Automatic price monitoring with exit alerts**

### 4. "Why No Signal" Logging
**Detailed breakdown for ML training**

---

## 📁 Files Changed

### New Files
- \`post_call_monitor.py\` - AsyncIO-based price monitoring system
- \`docs/GROK_RECOMMENDATIONS_20260126.md\` - Phase 1 documentation
- \`docs/TIMING_EXIT_RULES_20260126.md\` - Phase 2 documentation

### Modified Files
- \`config.py\` - All threshold, weight, and feature config updates
- \`scoring/conviction_engine.py\` - Enhanced scoring logic + timing rules

---

## 📋 Commits Included

1. \`c04eb6e\` - feat: Implement Grok recommendations - enhanced scoring & stricter thresholds
2. \`9c3fa47\` - feat: Add timing/exit rules and data monitoring (Grok Phase 2)

**Branch:** \`claude/check-sessions-clarity-6CaJr\`
**Base:** \`main\`
