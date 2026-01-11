"""Main CLI for dev-cleanup."""

from pathlib import Path

import typer
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from dev_cleanup.config import DEFAULT_CONFIG, load_config
from dev_cleanup.models import format_size
from dev_cleanup.scanner import scan_for_stale_projects
from dev_cleanup.utils.display import display_deletion_summary, display_scan_results
from dev_cleanup.utils.filesystem import trash_directory

app = typer.Typer(
    name="dev-cleanup",
    help="Find and clean up dependencies from stale git repositories",
    add_completion=False,
)
console = Console()


def get_project_size(project) -> int:
    """Get total size handling both StaleProject objects and dicts.

    InquirerPy may serialize StaleProject objects to dicts, losing computed properties.
    """
    if hasattr(project, 'total_size_bytes'):
        return project.total_size_bytes
    # For dict, compute from cleanable_dirs
    return sum(
        d['size_bytes'] if isinstance(d, dict) else d.size_bytes
        for d in project['cleanable_dirs']
    )


@app.command()
def main(
    older_than: int | None = typer.Option(
        None,
        "--older-than",
        "-o",
        help="Show projects with last commit older than X months (default: 6)",
    ),
    younger_than: int | None = typer.Option(
        None,
        "--younger-than",
        "-y",
        help="Show projects with last commit younger than X months",
    ),
    roots: list[str] | None = typer.Option(
        None,
        "--roots",
        "-r",
        help="Root directories to scan (can specify multiple)",
    ),
    execute: bool = typer.Option(
        False,
        "--execute",
        "-e",
        help="Actually delete selected directories (default: dry run)",
    ),
) -> None:
    """Find stale git repositories and clean up their dependency directories.

    By default runs in dry-run mode. Use --execute to actually delete.

    Examples:

        dev-cleanup                               # Dry run with defaults (>6 months)

        dev-cleanup --older-than 3                # Projects older than 3 months

        dev-cleanup --younger-than 1              # Projects younger than 1 month

        dev-cleanup --older-than 1 --younger-than 6  # Projects 1-6 months old

        dev-cleanup --roots ~/Work ~/Code         # Custom directories

        dev-cleanup --execute                     # Actually delete after selection
    """
    # Load config and apply CLI overrides
    config = load_config()

    # Apply defaults only if NO age filters are specified
    if older_than is None and younger_than is None:
        # Use default older_than
        older_than_months = config.get("older_than_months", DEFAULT_CONFIG["older_than_months"])
        younger_than_months = None
    else:
        # Use whatever the user specified
        older_than_months = older_than
        younger_than_months = younger_than

    root_paths = [
        Path(r).expanduser()
        for r in (roots or config.get("roots", DEFAULT_CONFIG["roots"]))
    ]

    # Generate filter description for header
    from dev_cleanup.utils.display import get_filter_description
    filter_desc = get_filter_description(older_than_months, younger_than_months)

    # Header
    mode_text = "[red]EXECUTE MODE[/]" if execute else "[yellow]DRY RUN[/]"
    console.print(
        Panel.fit(
            f"[bold cyan]dev-cleanup[/]\n\n"
            f"Mode: {mode_text}\n"
            f"Filter: {filter_desc}\n"
            f"Scanning: {', '.join(str(r) for r in root_paths)}",
            border_style="cyan",
        )
    )

    # Scan for stale projects
    console.print("\n[bold]Scanning for stale projects...[/]")

    with console.status("[bold green]Scanning repositories..."):
        results = scan_for_stale_projects(
            roots=root_paths,
            older_than_months=older_than_months,
            younger_than_months=younger_than_months,
            console=console,
        )

    if not results.stale_projects:
        console.print("\n[green]No stale projects with cleanable directories found![/]")
        raise typer.Exit(0)

    # Display results
    console.print(f"\nScanned {results.total_repos_scanned} repositories")
    display_scan_results(console, results)

    # Interactive selection using InquirerPy checkboxes
    choices = [
        Choice(
            value=project,
            name=f"{project.name} - {format_size(project.total_size_bytes)} "
            f"({', '.join(d.dir_type for d in project.cleanable_dirs)})",
        )
        for project in results.stale_projects
    ]

    console.print("\n")
    selected = inquirer.checkbox(
        message="Select projects to clean (space to toggle, enter to confirm):",
        choices=choices,
        instruction="(Use arrow keys to navigate, space to select, enter to confirm)",
    ).execute()

    if not selected:
        console.print("\n[yellow]No projects selected. Exiting.[/]")
        raise typer.Exit(0)

    # Show summary
    display_deletion_summary(console, selected, execute=False)

    total_to_delete = sum(get_project_size(p) for p in selected)
    console.print(f"\n[bold]Total to reclaim:[/] {format_size(total_to_delete)}")

    if not execute:
        console.print("\n[yellow]This was a dry run. Use --execute to actually delete.[/]")
        raise typer.Exit(0)

    # Confirm before executing
    if not Confirm.ask("\n[bold red]Proceed with deletion?[/]"):
        console.print("[yellow]Cancelled.[/]")
        raise typer.Exit(0)

    # Execute deletion
    console.print("\n[bold]Cleaning up...[/]")

    success_count = 0
    fail_count = 0

    for project in selected:
        # Handle both StaleProject objects and dicts (InquirerPy may serialize to dict)
        cleanable_dirs = project.cleanable_dirs if hasattr(project, 'cleanable_dirs') else project["cleanable_dirs"]
        for cleanable_dir in cleanable_dirs:
            # cleanable_dir might be CleanableDirectory object or dict
            if isinstance(cleanable_dir, dict):
                dir_path = cleanable_dir["path"]
            else:
                dir_path = cleanable_dir.path
            
            with console.status(f"Trashing {dir_path.name}..."):
                if trash_directory(dir_path, execute=True):
                    console.print(f"  [green]✓[/] {dir_path}")
                    success_count += 1
                else:
                    console.print(f"  [red]✗[/] {dir_path}")
                    fail_count += 1

    # Final summary
    console.print("\n[bold green]Done![/]")
    console.print(f"  Deleted: {success_count} directories")
    if fail_count:
        console.print(f"  [red]Failed: {fail_count} directories[/]")
    console.print(f"  Space reclaimed: {format_size(total_to_delete)}")


if __name__ == "__main__":
    app()
