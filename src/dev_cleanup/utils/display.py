"""Display utilities for dev-cleanup using Rich."""

from rich.console import Console
from rich.table import Table

from dev_cleanup.models import ScanResult, StaleProject, format_size


def get_filter_description(older: int | None, younger: int | None) -> str:
    """Generate a human-readable filter description.

    Args:
        older: Older than X months filter
        younger: Younger than X months filter

    Returns:
        Description string for the filter
    """
    if older and younger:
        return f"{older}-{younger} months old"
    elif older:
        return f">{older} months old"
    elif younger:
        return f"<{younger} months old"
    return "all projects"


def display_scan_results(console: Console, results: ScanResult) -> None:
    """Display scan results in a rich table.

    Args:
        console: Rich console instance
        results: ScanResult to display
    """
    filter_desc = get_filter_description(results.older_than_months, results.younger_than_months)
    table = Table(title=f"Stale Projects ({filter_desc})")

    table.add_column("#", style="dim", width=4)
    table.add_column("Project", style="cyan")
    table.add_column("Last Commit", style="yellow")
    table.add_column("Days Stale", justify="right")
    table.add_column("Cleanable Dirs", style="magenta")
    table.add_column("Total Size", justify="right", style="green")

    for idx, project in enumerate(results.stale_projects, 1):
        dirs_str = ", ".join(d.dir_type for d in project.cleanable_dirs)
        table.add_row(
            str(idx),
            project.name,
            project.last_commit_date.strftime("%Y-%m-%d"),
            str(project.days_stale),
            dirs_str,
            format_size(project.total_size_bytes),
        )

    console.print(table)

    # Summary
    total_size = sum(p.total_size_bytes for p in results.stale_projects)
    console.print(f"\n[bold]Total reclaimable space:[/] {format_size(total_size)}")


def display_deletion_summary(
    console: Console, selected_projects: list[StaleProject | dict], execute: bool
) -> None:
    """Display what will be/was deleted.

    Args:
        console: Rich console instance
        selected_projects: List of projects to clean (StaleProject objects or dicts)
        execute: Whether this is actual deletion or dry run
    """
    mode = "Deleted" if execute else "Would delete"

    console.print(f"\n[bold]{mode}:[/]")
    for project in selected_projects:
        # Handle both StaleProject objects and dicts (InquirerPy may serialize to dict)
        cleanable_dirs = project.cleanable_dirs if isinstance(project, StaleProject) else project["cleanable_dirs"]
        for d in cleanable_dirs:
            # d might be CleanableDirectory object or dict
            if isinstance(d, dict):
                console.print(f"  - {d['path']} ({format_size(d['size_bytes'])})")
            else:
                console.print(f"  - {d.path} ({format_size(d.size_bytes)})")
