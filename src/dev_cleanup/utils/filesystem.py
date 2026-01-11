"""Filesystem utilities for dev-cleanup."""

import subprocess
from pathlib import Path


def get_directory_size(path: Path) -> int:
    """Get total size of directory in bytes using du command for efficiency.

    Args:
        path: Directory path

    Returns:
        Size in bytes, or 0 if error
    """
    try:
        result = subprocess.run(
            ["du", "-sk", str(path)],  # -s = summarize, -k = KB
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        kb = int(result.stdout.split()[0])
        return kb * 1024
    except (subprocess.CalledProcessError, ValueError, subprocess.TimeoutExpired):
        return 0


def find_cleanable_directories(
    project_path: Path, cleanable_dirs: set[str]
) -> list[tuple[Path, str]]:
    """Find all cleanable directories in a project.

    Checks root level and one level deep (for monorepos).

    Args:
        project_path: Path to the project
        cleanable_dirs: Set of directory names to look for (e.g., {"node_modules", "venv"})

    Returns:
        List of (path, type) tuples where type is the directory name (e.g., "node_modules")
    """
    results = []

    # Check root level
    for name in cleanable_dirs:
        candidate = project_path / name
        if candidate.is_dir():
            results.append((candidate, name))

    # Check one level deep (for monorepos/workspaces)
    try:
        for subdir in project_path.iterdir():
            if subdir.is_dir() and not subdir.name.startswith("."):
                for name in cleanable_dirs:
                    candidate = subdir / name
                    if candidate.is_dir():
                        results.append((candidate, name))
    except PermissionError:
        # Skip if we can't read the directory
        pass

    return results


def trash_directory(path: Path, execute: bool = False) -> bool:
    """Move directory to trash using the trash command.

    Args:
        path: Directory to trash
        execute: If False, just return True (dry run)

    Returns:
        True if successful or dry run, False on error
    """
    if not execute:
        return True

    try:
        subprocess.run(
            ["trash", str(path)],
            check=True,
            capture_output=True,
            timeout=60,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False
