# synctools

## Setup

To set up the python environmentm you need `uv`, then run:
```(bash)
uv venv venv && source venv/bin/activate && uv pip install ".[dev]"
op inject -i envtemplate.txt -o .env
```

## Running

The script depends on a set of envvars. To load these from `.env`, run
```(bash)
python3 -m synctools.main --envfile=.env
```

## Linting

```(bash)
ruff check .
```

## Formatting

```(bash)
ruff format .
```

## Testing

```(bash)
tox
```

## Deployment

```(bash)
./scripts/deploy.sh .env
```
