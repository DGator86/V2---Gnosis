# GitHub Actions CI Fix Required

## Problem

GitHub Actions CI is failing with `ModuleNotFoundError: No module named 'agents'`.

**Failed Run**: https://github.com/DGator86/V2---Gnosis/actions/runs/19406075225/job/55520891578#step:5:1

## Root Cause

The project has a `pyproject.toml` defining the package structure, but the CI workflow only runs:
```bash
pip install -r requirements.txt
```

This installs dependencies but **does NOT install the local package** (`agents`, `engines`, `execution` modules). In local development, Python can import from the current directory, but in CI, without package installation, imports fail.

## Solution

Add a package installation step to `.github/workflows/tests.yml`:

### Current Workflow (Failing)

```yaml
- name: Install dependencies
  run: |
    python -m pip install --upgrade pip
    pip install -r requirements.txt

- name: Run pytest
  run: pytest
```

### Fixed Workflow

```yaml
- name: Install dependencies
  run: |
    python -m pip install --upgrade pip
    pip install -r requirements.txt

- name: Install package          # ADD THIS STEP
  run: pip install -e .

- name: Run pytest
  run: pytest
```

## Why I Cannot Push This Fix

GitHub has a security feature that prevents GitHub Apps from modifying workflow files (`.github/workflows/*.yml`) without explicit `workflows` permission. This is to prevent automated tools from tampering with CI/CD pipelines.

**Error when attempting to push**:
```
! [remote rejected] main -> main (refusing to allow a GitHub App to create 
or update workflow `.github/workflows/tests.yml` without `workflows` permission)
```

## How to Apply the Fix

### **Option 1: Manual Edit (Recommended - Quickest)**

1. Go to: https://github.com/DGator86/V2---Gnosis/edit/main/.github/workflows/tests.yml
2. Add the three lines shown above (lines 26-28) between the "Install dependencies" and "Run pytest" steps
3. Commit directly to main with message: `fix(ci): Install package before running tests`
4. CI will automatically re-run and should pass

### **Option 2: Grant Workflows Permission to GitHub App**

If you want me to handle future workflow changes automatically:

1. Go to Repository Settings → Actions → General → Workflow permissions
2. Grant the GitHub App `workflows` write permission
3. Let me know, and I'll push the fix immediately

### **Option 3: Apply from This Branch**

I have the fix committed locally on the `main` branch (commit `1d198d3`). You can:

1. Pull the changes manually
2. Force push to remote main (if you have permissions)

## Verification

After applying the fix, the CI should:
1. ✅ Install dependencies from `requirements.txt`
2. ✅ Install the local package with `pip install -e .`
3. ✅ Run pytest successfully (all 117 tests should pass based on local results)

## Context

- **Phase 6**: Strategy Ranking Engine (37 tests) ✅
- **Phase 7**: Portfolio Manager v1.0 (16 tests) ✅  
- **Phase 8**: Execution Orchestration Layer v1.0 (58 tests) ✅
- **Total**: 111 new tests added in PR #12, all passing locally

The CI failure is purely an installation issue, not a code problem.

---

**Ready to proceed once workflow fix is applied!**
