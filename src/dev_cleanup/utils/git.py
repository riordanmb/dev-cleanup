"""Git utilities for dev-cleanup."""

import subprocess
from datetime import datetime
from pathlib import Path


def is_git_repo(path: Path) -> bool:
    """Check if path is a git repository."""
    git_path = path / ".git"
    return git_path.is_dir() or git_path.is_file()


def get_last_commit_info(repo_path: Path) -> tuple[datetime, str] | None:
    """Get the last commit timestamp and message for a repo.

    Uses: git log -1 --format="%ct|%s" (unix timestamp | subject)

    Args:
        repo_path: Path to the git repository

    Returns:
        Tuple of (commit_datetime, commit_message) or None if no commits or error
    """
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ct|%s"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        output = result.stdout.strip()
        if not output:
            return None

        timestamp_str, message = output.split("|", 1)
        return datetime.fromtimestamp(int(timestamp_str)), message
    except (subprocess.CalledProcessError, ValueError, subprocess.TimeoutExpired):
        return None


def get_github_remote(repo_path: Path) -> str | None:
    """Get GitHub repository name (owner/repo) from remote URL.

    Args:
        repo_path: Path to the git repository

    Returns:
        Repository name as "owner/repo" or None if no GitHub remote
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        url = result.stdout.strip()

        # Parse GitHub URLs
        # https://github.com/owner/repo.git
        # git@github.com:owner/repo.git
        if "github.com" not in url:
            return None

        if url.startswith("https://github.com/"):
            path = url.replace("https://github.com/", "").replace(".git", "")
            return path
        elif url.startswith("git@github.com:"):
            path = url.replace("git@github.com:", "").replace(".git", "")
            return path

        return None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def find_git_repos(root: Path) -> list[Path]:
    """Find all git repositories under a root directory.

    Skips nested repos (doesn't recurse into .git directories or repos within repos).

    Args:
        root: Root directory to search

    Returns:
        List of paths to git repositories
    """
    repos = []

    if not root.exists() or not root.is_dir():
        return repos

    # Recursively walk the directory tree
    def scan_directory(path: Path) -> None:
        """Recursively scan for git repos."""
        try:
            # Check if this is a git repo first
            if is_git_repo(path):
                repos.append(path)
                # Don't recurse into git repos
                return

            # Not a git repo, scan subdirectories
            for item in path.iterdir():
                if item.is_dir():
                    if item.name.startswith("."):
                        # Hidden folders can still be repos; don't recurse into them.
                        if is_git_repo(item):
                            repos.append(item)
                        continue
                    scan_directory(item)
        except (PermissionError, OSError):
            # Skip directories we can't read
            pass

    scan_directory(root)
    return repos
