"""Scanner for finding stale git projects."""

from datetime import datetime
from pathlib import Path

from dateutil.relativedelta import relativedelta
from rich.console import Console

from dev_cleanup.models import CleanableDirectory, ScanResult, StaleProject
from dev_cleanup.utils.filesystem import find_cleanable_directories, get_directory_size
from dev_cleanup.utils.git import find_git_repos, get_last_commit_info


def scan_for_stale_projects(
    roots: list[Path],
    older_than_months: int | None = None,
    younger_than_months: int | None = None,
    cleanable_dirs: set[str] | None = None,
    console: Console | None = None,
) -> ScanResult:
    """Scan root directories for stale projects with cleanable directories.

    Args:
        roots: List of root directories to scan
        older_than_months: Only include projects older than X months
        younger_than_months: Only include projects younger than X months
        cleanable_dirs: Set of directory names to scan for (e.g., {"node_modules", "venv"})
        console: Optional Rich console for progress updates

    Returns:
        ScanResult with all stale projects found
    """
    # Use default cleanable dirs if not provided
    if cleanable_dirs is None:
        cleanable_dirs = {"node_modules", "venv", ".venv", "env"}
    # Calculate cutoff dates
    older_cutoff = None
    younger_cutoff = None

    if older_than_months is not None:
        older_cutoff = datetime.now() - relativedelta(months=older_than_months)
    if younger_than_months is not None:
        younger_cutoff = datetime.now() - relativedelta(months=younger_than_months)
    stale_projects = []
    total_repos = 0

    for root in roots:
        if not root.exists():
            if console:
                console.print(f"[yellow]Warning: Root {root} does not exist, skipping[/]")
            continue

        repos = find_git_repos(root)

        for repo_path in repos:
            total_repos += 1

            commit_info = get_last_commit_info(repo_path)
            if not commit_info:
                # No commits or error, skip
                continue

            last_commit_date, last_commit_message = commit_info

            # Check age filters
            if older_cutoff and last_commit_date >= older_cutoff:
                continue  # Too recent
            if younger_cutoff and last_commit_date < younger_cutoff:
                continue  # Too old

            # Find cleanable directories
            cleanable = find_cleanable_directories(repo_path, cleanable_dirs)
            if not cleanable:
                continue

            # Build cleanable directory objects with sizes
            cleanable_dirs = []
            for dir_path, dir_type in cleanable:
                size = get_directory_size(dir_path)
                cleanable_dirs.append(
                    CleanableDirectory(
                        path=dir_path,
                        dir_type=dir_type,
                        size_bytes=size,
                    )
                )

            stale_projects.append(
                StaleProject(
                    path=repo_path,
                    name=repo_path.name,
                    last_commit_date=last_commit_date,
                    last_commit_message=last_commit_message,
                    cleanable_dirs=cleanable_dirs,
                )
            )

    return ScanResult(
        stale_projects=stale_projects,
        total_repos_scanned=total_repos,
        older_than_months=older_than_months,
        younger_than_months=younger_than_months,
    )
