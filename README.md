# synctools

A set of tools useful for syncing data.

## Setup

Add to your project's `pyproject.toml` dependencies:

```
"synctools @ git+https://github.com/asterisk-digital/synctools.git@main"
```

The library can be used as follows:

```(python)
import synctools

synctools.utils.complete_dicts(...)
```

## Development

### Setup

```(bash)
uv sync --group dev
```

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
uv run ruff format . --check
```
