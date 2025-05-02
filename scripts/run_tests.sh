#!/bin/bash
set -e

# Run pytest with coverage
echo "Running tests with coverage..."
pytest --cov=app --cov-report=term --cov-report=html:coverage_html tests/

# Show coverage report
echo ""
echo "Coverage report:"
coverage report

echo ""
echo "HTML coverage report generated in coverage_html/ directory"
echo "Open coverage_html/index.html in a browser to view detailed coverage report"
