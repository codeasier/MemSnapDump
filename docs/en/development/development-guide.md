[中文](../../zh/development/development-guide.md)

# Development Guide

## Local setup

```bash
python -m pip install -e .[dev]
```

## Quality checks

```bash
ruff check .
black --check .
pytest --cov=memsnapdump --cov-fail-under=85
```

Auto-fix formatting/lint issues:

```bash
ruff check . --fix
black .
```

## CI
GitHub workflow runs:
- `ruff check .`
- `black --check .`
- `pytest --cov=memsnapdump --cov-fail-under=85`

Across Python versions:
- 3.10
- 3.11
- 3.12

## Repository layout
```text
MemSnapDump/
├── src/memsnapdump/
│   ├── base/        # snapshot entity definitions
│   ├── simulate/    # replay and allocator simulation logic
│   ├── tools/       # CLI entrypoints and tools
│   └── util/        # logger, file, timer, sqlite helpers
├── tests/           # unit tests and fixture data
├── docs/            # user docs, reference docs, and project notes
├── pyproject.toml   # packaging and tool configuration
└── README.md        # English landing page
```

## Notes for contributors
- Prefer updating user-facing docs in both `docs/en` and `docs/zh`.
- Keep `README.md` and `README.zh.md` concise and navigational.
- Place deeper operational details under `docs/` rather than expanding the root README files.
