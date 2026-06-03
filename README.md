# synctools

A set of tools useful for syncing data.

## Installing

Add to your project's `pyproject.toml` dependencies:

```
"synctools @ git+https://github.com/asterisk-digital/synctools.git@main"
```

The library can be used as follows:

```(python)
import synctools

synctools.utils.complete_dicts(...)
```

## Development setup

```(bash)
uv sync
```

## Checks

These checks should always pass before pushing.

### Testing

```(bash)
uv run tox
```

### Linting

```(bash)
uv run ruff check .
```

### Formatting

```(bash)
uv run ruff format --check .
```
