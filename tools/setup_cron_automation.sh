#!/bin/bash
"""
Setup Cron Automation for SENTINEL ML Pipeline

This script sets up automated daily collection and ML retraining:
1. Midnight UTC: Collect yesterday's top tokens from DexScreener
2. 1 AM UTC: Export production signals to ML dataset
3. 2 AM UTC: Retrain ML model if enough new data
4. Daily: Logs rotation and cleanup

Usage:
    bash tools/setup_cron_automation.sh
"""

# Get the absolute path to the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_PATH=$(which python3)
VENV_PYTHON="$PROJECT_DIR/venv/bin/python3"

# Use venv python if it exists, otherwise system python
if [ -f "$VENV_PYTHON" ]; then
    PYTHON_PATH="$VENV_PYTHON"
fi

echo "================================================================================"
echo "🤖 SETTING UP CRON AUTOMATION FOR SENTINEL ML PIPELINE"
echo "================================================================================"
echo "   Project directory: $PROJECT_DIR"
echo "   Python interpreter: $PYTHON_PATH"
echo ""

# Create cron configuration
CRON_FILE="$PROJECT_DIR/sentinel_cron.txt"

cat > "$CRON_FILE" << EOF
# SENTINEL ML Pipeline - Automated Data Collection & Retraining
# ============================================================================
# All times are UTC. Adjust CRON_TZ if you want different timezone.

SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
PYTHONPATH=$PROJECT_DIR
CRON_TZ=UTC

# ============================================================================
# DAILY DATA COLLECTION PIPELINE
# ============================================================================

# Step 1: Collect yesterday's top tokens from DexScreener (Midnight UTC)
# - Pulls 50-100 tokens that did 2x+ in last 24 hours
# - Saves to data/historical_training_data.json
# - Extracts early whale wallets
0 0 * * * cd $PROJECT_DIR && $PYTHON_PATH tools/daily_token_collector.py >> logs/daily_collection.log 2>&1

# Step 2: Export production signals to ML dataset (1 AM UTC)
# - Pulls completed signals from PostgreSQL (last 7 days)
# - Enriches with DexScreener metrics
# - Appends to training dataset
0 1 * * * cd $PROJECT_DIR && $PYTHON_PATH tools/export_signals_to_ml.py >> logs/signal_export.log 2>&1

# Step 3: Automated ML retraining (2 AM UTC)
# - Checks if enough new data (50+ tokens since last train)
# - Retrains XGBoost model if threshold met
# - Deploys new model automatically
0 2 * * * cd $PROJECT_DIR && $PYTHON_PATH tools/automated_ml_retrain.py >> logs/ml_retrain.log 2>&1

# ============================================================================
# WEEKLY HISTORICAL DATA COLLECTION
# ============================================================================

# Collect 150 pump.fun graduates (Sundays at 3 AM UTC)
# - Scrapes tokens that graduated from bonding curve
# - Extracts early whale wallets
# - Costs ~3K Moralis compute units
0 3 * * 0 cd $PROJECT_DIR && $PYTHON_PATH tools/historical_data_collector.py >> logs/historical_collection.log 2>&1

# ============================================================================
# MAINTENANCE
# ============================================================================

# Rotate logs weekly (Mondays at 4 AM UTC)
0 4 * * 1 cd $PROJECT_DIR && find logs/ -name "*.log" -mtime +30 -delete

# Backup training data daily (5 AM UTC)
0 5 * * * cd $PROJECT_DIR && cp data/historical_training_data.json data/backups/training_data_\$(date +\%Y\%m\%d).json 2>/dev/null

EOF

echo "✅ Created cron configuration: $CRON_FILE"
echo ""
echo "Cron schedule:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  00:00 UTC - Collect yesterday's top tokens (DexScreener)"
echo "  01:00 UTC - Export production signals to ML dataset"
echo "  02:00 UTC - Retrain ML model (if 50+ new tokens)"
echo "  03:00 UTC - Weekly historical collection (Sundays)"
echo "  04:00 UTC - Log rotation (Mondays)"
echo "  05:00 UTC - Backup training data"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Create logs directory
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/data/backups"

echo "✅ Created directories:"
echo "   - logs/ (for cron output)"
echo "   - data/backups/ (for training data backups)"
echo ""

# Install crontab
echo "📋 Installing crontab..."
crontab "$CRON_FILE"

if [ $? -eq 0 ]; then
    echo "✅ Crontab installed successfully!"
    echo ""
    echo "Verifying installation:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    crontab -l | grep -A 3 "SENTINEL"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
else
    echo "❌ Failed to install crontab"
    echo ""
    echo "Manual installation:"
    echo "  1. Run: crontab -e"
    echo "  2. Copy contents from: $CRON_FILE"
    exit 1
fi

echo ""
echo "================================================================================"
echo "✅ CRON AUTOMATION SETUP COMPLETE"
echo "================================================================================"
echo ""
echo "Next steps:"
echo "  1. Monitor logs in logs/ directory"
echo "  2. Check data collection: tail -f logs/daily_collection.log"
echo "  3. Check ML retraining: tail -f logs/ml_retrain.log"
echo "  4. View training data: cat data/historical_training_data.json | jq '.total_tokens'"
echo ""
echo "To remove cron automation:"
echo "  crontab -r"
echo ""
echo "To edit cron schedule:"
echo "  crontab -e"
echo ""
