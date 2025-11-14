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
python3 -m unittest tests.test_image_rebuilder -v
```

All tests must pass before committing.

**Note:** Make sure the virtual environment is activated when running tests.
