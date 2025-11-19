# GitHub Workflow Fix Instructions

## Issue
The CI workflow needs to be updated to use the test extras from `pyproject.toml` instead of `requirements.txt`.

## Manual Steps Required

Since the GitHub App doesn't have permission to modify workflow files, you need to manually update `.github/workflows/tests.yml`:

### Current Code (Lines 21-30)
```yaml
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Install package
        run: pip install -e .

      - name: Run pytest
        run: pytest
```

### Replace With
```yaml
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[test]"

      - name: Run pytest with coverage
        run: pytest -vv --cov=engines --cov=agents --cov=ml --cov-report=xml
```

## Why This Fix Works

1. **Uses pyproject.toml test extras**: The `pip install -e ".[test]"` command installs the package in editable mode with all test dependencies defined in `[project.optional-dependencies]` test section

2. **Simplifies workflow**: Merges two separate steps (install + test) into cleaner commands

3. **Adds coverage**: Includes coverage reporting which is useful for tracking test quality

4. **No greekcalc**: The test extras no longer include the problematic `greekcalc` package

## Files Already Fixed
- ✅ `requirements.txt` - greekcalc commented out
- ✅ `pyproject.toml` - greekcalc removed from test extras
- ⏳ `.github/workflows/tests.yml` - **Needs manual update** (this file)

## Verification
After making this change, the CI should pass. You can verify locally by running:
```bash
pip install -e ".[test]"
pytest -vv
```

Both commands should complete successfully without any greekcalc errors.
