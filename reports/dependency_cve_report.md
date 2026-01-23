Dependency CVE Report
=====================

Date: 2026-01-24

Scope and method:

- Tools: `pip-audit` (v2.10.0) and `safety` (v3.7.0)
- Target: the virtual environment for this workspace (scanned site-packages)
- Commands run:

```python
d:/git/kasi_jobs/.venv/Scripts/python.exe -m pip install pip-audit safety
d:/git/kasi_jobs/.venv/Scripts/python.exe -m pip_audit --format=json > reports/pip_audit.json
d:/git/kasi_jobs/.venv/Scripts/python.exe -m safety check --json > reports/safety.json
```

Findings (summary):

- Packages scanned (safety): 161
- Vulnerabilities found: 0

Raw outputs:

- Pip-audit JSON: [reports/pip_audit.json](reports/pip_audit.json)
- Safety JSON: [reports/safety.json](reports/safety.json)

Notes and caveats:

- The scan targeted the active virtual environment's installed packages. If you want the audit to exactly match declared project dependencies, export a lock or requirements file and re-run the tools against that list (for example using `pip-audit -r requirements.txt` or `safety check -r requirements.txt`).
- `safety check` is deprecated; consider using `safety scan` in CI automation.
- If you prefer, I can run the audit against a generated `requirements.txt` (from `pyproject.toml` or Poetry) to ensure results match your declared dependencies.
