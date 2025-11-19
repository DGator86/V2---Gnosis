#!/bin/bash
# Verification script for CI fix
# Run this locally to verify the fix works before pushing

set -e  # Exit on error

echo "🔍 Verifying CI Fix..."
echo ""

# Test 1: Check pyproject.toml doesn't contain greekcalc
echo "✓ Test 1: Checking pyproject.toml..."
if grep -q "greekcalc" pyproject.toml; then
    echo "❌ FAILED: greekcalc still present in pyproject.toml"
    exit 1
fi
echo "✅ PASSED: greekcalc not in pyproject.toml"
echo ""

# Test 2: Check requirements.txt has greekcalc commented out
echo "✓ Test 2: Checking requirements.txt..."
if grep "^greekcalc" requirements.txt; then
    echo "❌ FAILED: greekcalc is not commented out in requirements.txt"
    exit 1
fi
echo "✅ PASSED: greekcalc properly commented in requirements.txt"
echo ""

# Test 3: Test pip install works
echo "✓ Test 3: Testing pip install -e .[test]..."
python -m venv test_venv
source test_venv/bin/activate
pip install --upgrade pip > /dev/null 2>&1

if pip install -e ".[test]" > /dev/null 2>&1; then
    echo "✅ PASSED: pip install -e .[test] succeeded"
else
    echo "❌ FAILED: pip install -e .[test] failed"
    deactivate
    rm -rf test_venv
    exit 1
fi

# Test 4: Verify pytest is installed
echo "✓ Test 4: Verifying pytest installation..."
if command -v pytest > /dev/null 2>&1; then
    PYTEST_VERSION=$(pytest --version 2>&1 | head -n1)
    echo "✅ PASSED: $PYTEST_VERSION"
else
    echo "❌ FAILED: pytest not installed"
    deactivate
    rm -rf test_venv
    exit 1
fi

# Cleanup
deactivate
rm -rf test_venv

echo ""
echo "🎉 All tests passed! CI fix is working correctly."
echo ""
echo "Next steps:"
echo "1. Manually update .github/workflows/tests.yml (see WORKFLOW_FIX.md)"
echo "2. Push changes to your branch"
echo "3. CI should be green! ✅"
