# dev-cleanup

A CLI tool for cleaning up dependencies (node_modules, venv, etc.) from stale git repositories.

## Features

- Scans for git repositories that haven't been committed to in N months
- Finds cleanable directories: `node_modules`, `venv`, `.venv`, `env`
- Interactive checkbox selection
- Safe deletion using macOS `trash` command (recoverable)
- Dry-run by default

## Requirements

- Python 3.12+
- macOS (uses `trash` command)

## Installation

### Quick Install (Recommended)

```bash
# Install trash first
brew install trash

# Install pipx if you don't have it
brew install pipx
pipx ensurepath

# Install dev-cleanup globally
cd /Users/michaelriordan2/2025-Projects/dev-cleanup
pipx install .
```

The `dev-cleanup` command will now be available globally in your terminal.

### Development Install

If you want to develop or modify the tool:

```bash
cd /Users/michaelriordan2/2025-Projects/dev-cleanup
pip install -e .
```

### Uninstall

```bash
pipx uninstall dev-cleanup
```

## Usage

```bash
# Dry run with defaults (6 months, ~/Projects + ~/2025-Projects)
dev-cleanup

# Custom threshold
dev-cleanup --months 3

# Custom root directories
dev-cleanup --roots ~/Work ~/Code

# Actually delete (after selection)
dev-cleanup --execute
```

## How it works

1. Scans configured root directories for git repositories
2. Checks last commit date for each repo
3. Finds repos older than threshold with cleanable directories
4. Displays an interactive table with sizes
5. Allows checkbox selection of projects to clean
6. In execute mode, moves selected directories to Trash

## Configuration

Default config is stored in `~/.dev-cleanup/config.json`:

```json
{
  "roots": ["~/Projects", "~/2025-Projects"],
  "months_threshold": 6,
  "cleanable_dirs": ["node_modules", "venv", ".venv", "env"]
}
```

CLI arguments override config values.
