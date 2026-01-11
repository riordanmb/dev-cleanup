"""Data models for dev-cleanup."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class CleanableDirectory:
    """A directory that can be cleaned (node_modules, venv, etc.)."""

    path: Path
    dir_type: str  # "node_modules", "venv", ".venv", "env"
    size_bytes: int

    @property
    def size_human(self) -> str:
        """Return human-readable size."""
        return format_size(self.size_bytes)


@dataclass
class StaleProject:
    """A git repository that hasn't been committed to recently."""

    path: Path
    name: str
    last_commit_date: datetime
    last_commit_message: str
    cleanable_dirs: list[CleanableDirectory] = field(default_factory=list)

    @property
    def total_size_bytes(self) -> int:
        """Total size of all cleanable directories."""
        return sum(d.size_bytes for d in self.cleanable_dirs)

    @property
    def days_stale(self) -> int:
        """Number of days since last commit."""
        return (datetime.now() - self.last_commit_date).days


@dataclass
class ScanResult:
    """Result of scanning root directories."""

    stale_projects: list[StaleProject]
    total_repos_scanned: int
    older_than_months: int | None = None
    younger_than_months: int | None = None
    # Filter statistics
    filtered_too_recent: int = 0
    filtered_too_old: int = 0
    filtered_no_commits: int = 0
    filtered_no_cleanable: int = 0


def format_size(bytes_size: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} PB"
