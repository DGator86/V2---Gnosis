#!/bin/bash
# Setup Script for Real Data Integration
# =====================================
# 
# This script:
# 1. Installs all required dependencies
# 2. Validates API credentials
# 3. Tests data connectivity
# 4. Confirms system readiness

set -e  # Exit on error

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🚀 AGENTIC TRADING SYSTEM - REAL DATA INTEGRATION SETUP"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ ERROR: .env file not found!"
    echo "   Please create .env file with your API credentials"
    echo "   See .env.example for template"
    exit 1
fi

echo "✅ Found .env file with credentials"
echo ""

# Step 1: Install dependencies
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP 1: Installing Dependencies"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

pip install -r requirements.txt -q

echo "✅ All dependencies installed"
echo ""

# Step 2: Test data sources
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP 2: Testing Data Sources"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

python - << 'EOF'
from gnosis.ingest.adapters.unified_data_adapter import UnifiedDataAdapter

print("Testing data source connectivity...\n")
adapter = UnifiedDataAdapter()

if adapter.alpaca_available:
    print("✅ Alpaca Markets API: READY")
    print("   → Premium data source active")
    print("   → 1-minute bars available")
else:
    print("⚠️  Alpaca Markets API: UNAVAILABLE")
    print("   → Credentials invalid or API down")
    print("   → Will use Yahoo Finance fallback")

print()

if adapter.yfinance_available:
    print("✅ Yahoo Finance: READY")
    print("   → Free fallback source active")
    print("   → Hourly/daily bars available")
else:
    print("❌ Yahoo Finance: UNAVAILABLE")
    print("   → No data sources available!")
    exit(1)

print()
print("━" * 70)
print("✅ DATA INTEGRATION READY!")
print("━" * 70)
print()
print("Available Commands:")
print()
print("1. Fetch data for specific date:")
print("   python -m gnosis.ingest.adapters.unified_data_adapter SPY 2024-10-01 30 1h")
print()
print("2. Run full pipeline (fetch + features + backtest):")
print("   python run_full_pipeline.py SPY 2024-10-01 30")
print()
print("3. Quick test with existing data:")
print("   python run_full_pipeline.py SPY 2024-10-01 30 --skip-fetch")
print()
EOF

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ SETUP COMPLETE!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📖 Next Steps:"
echo ""
echo "1. Run full pipeline to test new agents:"
echo "   ./run_full_pipeline.py SPY 2024-10-01 30"
echo ""
echo "2. View documentation:"
echo "   - SANDBOX_TESTING_GUIDE.md   → Testing methodology"
echo "   - WYCKOFF_MARKOV_INTEGRATION.md → Integration guide"
echo "   - ARCHITECTURE_REPORT.md     → System deep dive"
echo ""
echo "3. If Alpaca credentials invalid, you can:"
echo "   - Generate new keys at: https://alpaca.markets"
echo "   - Update .env file with new credentials"
echo "   - System will auto-fallback to Yahoo Finance"
echo ""
