# Contributing

Use Python 3.11+ and keep vendor-specific logic inside `src/uas_thermal/sensors`.

Before opening a change:

```powershell
pip install -e ".[dev]"
pytest
python -m compileall src
```

Do not commit customer imagery, vendor SDK binaries, private license material, generated reports, or local environment files.
