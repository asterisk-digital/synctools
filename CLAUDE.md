# CLAUDE.md

synctools is a Python library for syncing data, primarily providing BigQuery helpers (`bqtools`) and dict/env utilities (`utils`). It is imported as a dependency by other projects.

## Quality gates

Major changes must not break tests, linting, or formatting. Verify with:

```bash
uv run tox          # tests
uv run ruff check . # linting
uv run ruff format . --check # formatting
```
