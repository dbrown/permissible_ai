#!/bin/bash
# Test runner script for Permissible

echo "🧪 Running Permissible Test Suite"
echo "=================================="
echo ""

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "❌ pytest not found. Installing test dependencies..."
    pip install -r requirements-test.txt
fi

# Run tests with different options based on argument
case "$1" in
    "coverage")
        echo "📊 Running tests with coverage report..."
        pytest --cov=app --cov-report=html --cov-report=term
        echo ""
        echo "✅ Coverage report generated in htmlcov/index.html"
        ;;
    "fast")
        echo "⚡ Running fast tests only..."
        pytest -m "not slow"
        ;;
    "verbose")
        echo "📝 Running tests with verbose output..."
        pytest -vv
        ;;
    "specific")
        if [ -z "$2" ]; then
            echo "❌ Please specify a test file or pattern"
            echo "Usage: ./run_tests.sh specific tests/test_api_key_model.py"
            exit 1
        fi
        echo "🎯 Running specific tests: $2"
        pytest "$2"
        ;;
    *)
        echo "🧪 Running all tests..."
        pytest
        ;;
esac

exit_code=$?

echo ""
if [ $exit_code -eq 0 ]; then
    echo "✅ All tests passed!"
else
    echo "❌ Some tests failed. Exit code: $exit_code"
fi

exit $exit_code
