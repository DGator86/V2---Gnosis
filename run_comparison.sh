#!/bin/bash
# Run comparative backtest to evaluate agent configurations

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                                                               ║"
echo "║         🔬 COMPARATIVE BACKTEST - SANDBOX MODE 🔬             ║"
echo "║                                                               ║"
echo "║  This compares 6 different agent configurations:             ║"
echo "║  1. Baseline (3 agents, 2-of-3)                               ║"
echo "║  2. Conservative (3 agents, require all)                      ║"
echo "║  3. Wyckoff Enhanced (4 agents)                               ║"
echo "║  4. Markov Enhanced (4 agents)                                ║"
echo "║  5. Full 5-Agent (3-of-5 voting)                              ║"
echo "║  6. Full 5-Agent Strict (4-of-5 voting)                       ║"
echo "║                                                               ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Default args
SYMBOL=${1:-SPY}
DATE=${2:-2025-11-03}

echo "📊 Running comparison for: $SYMBOL on $DATE"
echo ""

# Activate venv if exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run comparison
python -m gnosis.backtest.comparative_backtest "$SYMBOL" "$DATE"

echo ""
echo "✅ Comparison complete!"
echo ""
echo "📈 Next steps:"
echo "   1. Review results above"
echo "   2. Check JSON file for details"
echo "   3. If Wyckoff/Markov outperform, integrate them"
echo "   4. If baseline is best, keep as-is"
