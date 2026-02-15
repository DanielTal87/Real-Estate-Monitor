# Testing Guide - Real Estate Monitor

## Quick Start

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_processor.py -v

# Run tests matching a pattern
pytest tests/ -k "deal_score" -v
```

## Test Execution Time

- **Full Suite**: ~90 seconds
- **No browser required** - all tests use mocks
- **102 tests passing** (91% pass rate)

## What's Tested

### ✅ Core Logic
- Deal score calculation (0-100 points)
- Listing processing and deduplication
- Price change tracking
- Neighborhood statistics

### ✅ Data Parsing
- Hebrew text extraction (rooms, size, floor)
- Phone number normalization
- Feature detection (elevator, parking, balcony, mamad)
- Location parsing

### ✅ Scrapers (Mocked)
- Yad2 HTML parsing
- Search URL construction
- Error handling
- Data extraction

## GitHub Actions

Tests run automatically on:
- Every push to `main`, `master`, `develop`
- Every pull request

**Requirements:**
- Python 3.9, 3.10, 3.11
- Coverage threshold: 70%

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures (mocks, test data)
├── unit/
│   ├── test_processor.py    # Business logic tests
│   └── test_parsers.py      # Data parsing tests
└── mocked_scrapers/
    └── test_yad2_parser.py  # Scraper tests (no browser)
```

## Key Features

1. **No Browser Required**: All scraper tests use mocked `DrissionPage`
2. **Fast Execution**: In-memory SQLite database
3. **Parametrized Tests**: Comprehensive coverage with minimal code
4. **CI/CD Ready**: Runs in GitHub Actions without headless browser

## Coverage Report

```bash
# Generate HTML coverage report
pytest tests/ --cov=app --cov-report=html

# Open in browser
open htmlcov/index.html
```

## Common Commands

```bash
# Run only unit tests
pytest tests/unit/ -v

# Run only scraper tests
pytest tests/mocked_scrapers/ -v

# Run with verbose output
pytest tests/ -vv

# Stop on first failure
pytest tests/ -x

# Show local variables on failure
pytest tests/ -l

# Run last failed tests
pytest tests/ --lf

# Run tests in parallel (requires pytest-xdist)
pytest tests/ -n auto
```

## Writing Tests

See [`tests/README.md`](tests/README.md) for detailed examples and best practices.

## Troubleshooting

### "Unable to import pytest"
```bash
pip install pytest pytest-cov pytest-mock
```

### "Module not found: app"
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/app"
```

### Tests fail with database errors
Tests use in-memory SQLite. Ensure fixtures are properly configured in `conftest.py`.

## CI/CD Integration

The `.github/workflows/python-app.yml` workflow:
- Runs on multiple Python versions
- Generates coverage reports
- Uploads artifacts
- Fails if coverage < 70%

## Next Steps

- [ ] Fix remaining 10 failing tests (filter criteria issues)
- [ ] Add tests for Facebook and Madlan scrapers
- [ ] Increase coverage to 80%+
- [ ] Add integration tests with real database
