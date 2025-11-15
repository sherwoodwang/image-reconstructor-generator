# Guidelines for Claude Code

## Development Environment

This project uses a virtual environment for dependency management.

**Ensure virtual environment is activated:**

```bash
source venv/bin/activate
```

VSCode should automatically use the virtual environment configured in `.vscode/settings.json`.

## Dependencies

Dependencies are managed via `pyproject.toml`. To install or update dependencies:

```bash
pip install -e .
```

## Testing

**Run tests before committing or after major changes:**

```bash
python3 -m unittest discover -s tests -v
```

All tests must pass before committing.

**Note:** Make sure the virtual environment is activated when running tests.

## Type Checking

This project uses pyright for static type checking.

**Installation:**

Pyright should be installed in the virtual environment:

```bash
source venv/bin/activate
pip install pyright
```

**Run pyright type checking frequently during development:**

```bash
source venv/bin/activate
pyright image_rebuilder.py
```

- Run pyright after any non-trivial changes to catch type errors early
- All code must pass type checking with 0 errors before committing
- Type checking helps catch potential bugs and improves code quality
- Always run pyright from within the activated virtual environment
