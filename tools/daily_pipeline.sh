#!/bin/bash
#
# Daily ML Pipeline - Automated Data Collection + Model Retraining
#
# This script runs daily at midnight UTC:
# 1. Collects yesterday's top 50 tokens from DexScreener/Moralis
# 2. Extracts whale wallets and saves to database
# 3. Retrains ML model if enough new data (200+ tokens, 50+ new)
# 4. Deploys new model for next conviction scoring cycle
#
# Add to crontab:
# 0 0 * * * /home/user/SENTINEL_V2/tools/daily_pipeline.sh >> /home/user/SENTINEL_V2/logs/daily_pipeline.log 2>&1

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=========================================="
echo "🌅 DAILY ML PIPELINE"
echo "=========================================="
echo "Date: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo ""

# ================================================================
# STEP 1: DAILY TOKEN COLLECTION
# ================================================================
echo "=========================================="
echo "📊 STEP 1: COLLECTING YESTERDAY'S TOP TOKENS"
echo "=========================================="
echo ""

python3 tools/daily_token_collector.py

if [ $? -ne 0 ]; then
    echo "❌ Daily collection failed!"
    exit 1
fi

echo ""
echo "✅ Daily collection complete"
echo ""

# ================================================================
# STEP 2: ML MODEL RETRAINING (if needed)
# ================================================================
echo "=========================================="
echo "🎓 STEP 2: AUTOMATED ML RETRAINING"
echo "=========================================="
echo ""

python3 tools/automated_ml_retrain.py

if [ $? -ne 0 ]; then
    echo "⚠️  ML retraining encountered issues (non-fatal)"
fi

echo ""
echo "✅ ML retraining check complete"
echo ""

# ================================================================
# STEP 3: SUMMARY
# ================================================================
echo "=========================================="
echo "✅ DAILY PIPELINE COMPLETE"
echo "=========================================="
echo "Completed at: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo ""
echo "Next steps:"
echo "1. Data collected and saved to data/historical_training_data.json"
echo "2. Whales saved to database for real-time conviction boost"
echo "3. ML model retrained (if criteria met)"
echo "4. New model will be used in next signal analysis"
echo ""
echo "Check logs for details:"
echo "- Daily collection: See output above"
echo "- ML training: data/ml_training_metrics.json"
echo ""
