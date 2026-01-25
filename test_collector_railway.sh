#!/bin/bash
# Test Historical Data Collector on Railway
# Run this via Railway shell: bash test_collector_railway.sh

echo "=============================================================================="
echo "HISTORICAL DATA COLLECTOR - MANUAL TEST RUN"
echo "=============================================================================="
echo ""
echo "This will collect 10 tokens as a test (takes ~2-3 minutes)"
echo ""

# Check Moralis API key
if [ -z "$MORALIS_API_KEY" ]; then
    echo "⚠️  WARNING: MORALIS_API_KEY not set - whale extraction disabled"
    echo "   Get free key at: https://admin.moralis.io"
else
    echo "✅ Moralis API Key detected: ${MORALIS_API_KEY:0:20}..."
fi

echo ""
echo "Starting collection..."
echo ""

# Run collector with small count for testing
python3 tools/historical_data_collector.py --count 10 --min-mcap 1000000 --max-mcap 50000000

echo ""
echo "=============================================================================="
echo "TEST COMPLETE"
echo "=============================================================================="
echo ""
echo "Check output:"
echo "  - data/historical_training_data.json (token data)"
echo "  - data/successful_whale_wallets.json (whales - if Moralis enabled)"
echo ""
echo "To collect full dataset (50 tokens):"
echo "  python3 tools/historical_data_collector.py --count 50"
echo ""
