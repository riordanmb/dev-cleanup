# dev-cleanup

A CLI tool for cleaning up dependencies (node_modules, venv, etc.) from stale git repositories, with an option to completely nuke projects and their GitHub repos.

## Features

- **Interactive prompts** - Age filters and directory selection prompts when run without flags
- **Age-based filtering** - Find projects older/younger than X months
- **Flexible directory scanning** - Clean `node_modules`, `venv`, `.venv`, `env`, and more
- **Interactive selection** - Checkbox UI for selecting what to clean
- **Safe deletion** - Uses macOS `trash` command (recoverable from Trash)
- **Configuration wizard** - `--setup` to save your preferences
- **Dry-run by default** - See what would be deleted before committing
- **Nuke mode** - Delete entire projects (with optional GitHub integration)

## Requirements

- Python 3.12+
- macOS (uses `trash` command)
- Optional: `gh` CLI for GitHub deletion

## Installation

### Quick Install (Recommended)

```bash
# Install trash first
brew install trash

# Install pipx if you don't have it
brew install pipx
pipx ensurepath

# Install dev-cleanup globally
pipx install .
```

The `dev-cleanup` command will now be available globally in your terminal.

### Development Install

If you want to develop or modify the tool:

```bash
pip install -e .
```

### Uninstall

```bash
pipx uninstall dev-cleanup
```

## Usage

### Main Command - Clean Dependencies

```bash
# Interactive mode - prompts for age filters and directories
dev-cleanup

# Show projects older than 3 months
dev-cleanup --older-than 3

# Show projects younger than 1 month (recently active)
dev-cleanup --younger-than 1

# Range: projects between 1-6 months old
dev-cleanup --older-than 1 --younger-than 6

# Custom root directories
dev-cleanup --roots ~/Work ~/Code

# Actually delete (after selection)
dev-cleanup --execute
```

### Configuration Wizard

Set your default preferences:

```bash
dev-cleanup --setup
```

This will prompt you to configure:
- Default root directories to scan
- Default age threshold
- Default cleanable directories

### Nuke Mode - Delete Entire Projects

⚠️ **WARNING**: This mode deletes entire project directories, not just dependencies!

```bash
# Dry run - see what would be deleted
dev-cleanup nuke

# Projects older than 12 months
dev-cleanup nuke --older-than 12

# Delete locally and from GitHub (requires gh CLI)
dev-cleanup nuke --github --execute

# With age filters and custom roots
dev-cleanup nuke --older-than 6 --roots ~/OldProjects --execute
```

## How it Works

### Main Command

1. Scans configured root directories for git repositories
2. Prompts for age filters (if not provided via flags)
3. Prompts for which directories to clean (if not provided via config)
4. Checks last commit date for each repo
5. Finds repos matching filters with cleanable directories
6. Displays an interactive table with sizes
7. Allows checkbox selection of projects to clean
8. In execute mode, moves selected directories to Trash

### Nuke Command

1. Scans for ALL stale git repositories (regardless of cleanable dirs)
2. Optionally checks for GitHub remotes (`--github` flag)
3. Displays projects with last commit dates
4. Interactive selection of projects to DELETE ENTIRELY
5. Multiple confirmation prompts for safety
6. Trashes local directories
7. If `--github`: Deletes repositories from GitHub using `gh repo delete`

## Configuration

Default config is stored in `~/.dev-cleanup/config.json`:

```json
{
  "roots": ["~/Projects", "~/2025-Projects"],
  "older_than_months": 6,
  "cleanable_dirs": [
    "node_modules",
    "venv",
    ".venv",
    "env",
    "target",
    ".next",
    "dist",
    "build",
    "__pycache__"
  ]
}
```

CLI arguments override config values. Use `dev-cleanup --setup` to configure interactively.

## Examples

### Clean Dependencies

```bash
# Interactive mode with prompts
dev-cleanup

# Projects not touched in 3+ months
dev-cleanup --older-than 3 --execute

# Recent projects (< 1 month old)
dev-cleanup --younger-than 1

# Specific age range
dev-cleanup --older-than 2 --younger-than 6 --execute
```

### Configuration

```bash
# Run setup wizard
dev-cleanup --setup

# After setup, just run with no args to use your saved preferences
dev-cleanup
```

### Nuke Entire Projects

```bash
# Dry run to see what would be deleted
dev-cleanup nuke --older-than 12

# Delete very old projects locally
dev-cleanup nuke --older-than 24 --execute

# Nuclear option - delete locally AND from GitHub
dev-cleanup nuke --older-than 12 --github --execute
```

## Safety Features

### Main Command
- Dry-run by default (requires `--execute`)
- Uses `trash` command (recoverable from Trash)
- Only deletes dependency directories, not entire projects
- Shows size and directory types before deletion

### Nuke Command
- Dry-run by default (requires `--execute`)
- Multiple confirmation prompts
- Separate confirmation for GitHub deletion
- Clear warnings about destructiveness
- Shows full project paths before deletion
- Uses `trash` for local (recoverable)
- Separate tallies for local and GitHub deletions

## GitHub Integration

To use the `--github` flag with `nuke`, install the GitHub CLI:

```bash
brew install gh
gh auth login
```

This allows dev-cleanup to delete repositories from GitHub after removing them locally.

## License

MIT
