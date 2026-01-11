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


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
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
    setup: bool = typer.Option(
        False,
        "--setup",
        help="Run configuration wizard to set defaults",
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
    # If a subcommand is invoked, don't run main
    if ctx.invoked_subcommand is not None:
        return

    # Load config and apply CLI overrides
    config = load_config()

    # Setup wizard
    if setup:
        console.print(Panel.fit(
            "[bold cyan]Configuration Wizard[/]\n\n"
            "Set your default preferences",
            border_style="cyan",
        ))

        # Prompt for default roots
        console.print("\n[bold cyan]Root Directories[/]")
        current_roots = config.get("roots", DEFAULT_CONFIG["roots"])
        roots_input = inquirer.text(
            message="Root directories to scan (comma-separated):",
            default=", ".join(current_roots),
        ).execute()
        new_roots = [r.strip() for r in roots_input.split(",")]

        # Prompt for default older_than
        console.print("\n[bold cyan]Default Age Filter[/]")
        new_older_than = int(inquirer.number(
            message="Default older than (months):",
            default=int(config.get("older_than_months") or DEFAULT_CONFIG["older_than_months"]),
            min_allowed=0,
        ).execute())

        # Prompt for default cleanable dirs
        console.print("\n[bold cyan]Default Cleanable Directories[/]")
        COMMON_DIRS = [
            "node_modules",
            "venv",
            ".venv",
            "env",
            "target",
            ".next",
            "dist",
            "build",
            "__pycache__",
            ".pytest_cache",
            ".tox",
        ]
        current_dirs = config.get("cleanable_dirs", DEFAULT_CONFIG["cleanable_dirs"])
        new_cleanable_dirs = inquirer.checkbox(
            message="Select default directories to clean:",
            choices=COMMON_DIRS,
            default=[d for d in COMMON_DIRS if d in current_dirs],
        ).execute()

        # Save config (ensure older_than is int)
        new_config = {
            "roots": new_roots,
            "older_than_months": int(new_older_than),
            "cleanable_dirs": new_cleanable_dirs,
        }
        from dev_cleanup.config import save_config
        save_config(new_config)

        console.print("\n[green]Configuration saved successfully![/]")
        raise typer.Exit(0)

    # Interactive prompts if no age filters specified
    if older_than is None and younger_than is None:
        console.print("\n[bold cyan]Age Filters[/]")
        older_than_months = int(inquirer.number(
            message="Show projects older than how many months?",
            default=int(config.get("older_than_months") or DEFAULT_CONFIG["older_than_months"]),
            min_allowed=0,
        ).execute())

        younger_prompt = int(inquirer.number(
            message="Show projects younger than how many months? (0 for no limit)",
            default=0,
            min_allowed=0,
        ).execute())
        younger_than_months = younger_prompt if younger_prompt > 0 else None
    else:
        # Use whatever the user specified
        older_than_months = older_than
        younger_than_months = younger_than

    # Interactive prompt for cleanable directories
    console.print("\n[bold cyan]Cleanable Directories[/]")
    COMMON_DIRS = [
        "node_modules",
        "venv",
        ".venv",
        "env",
        "target",
        ".next",
        "dist",
        "build",
        "__pycache__",
        ".pytest_cache",
        ".tox",
    ]
    default_dirs = config.get("cleanable_dirs", DEFAULT_CONFIG["cleanable_dirs"])

    selected_dirs = inquirer.checkbox(
        message="Select directories to clean:",
        choices=COMMON_DIRS,
        default=[d for d in COMMON_DIRS if d in default_dirs],
    ).execute()

    if not selected_dirs:
        console.print("[red]No directories selected. Exiting.[/]")
        raise typer.Exit(1)

    cleanable_dirs = set(selected_dirs)

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
            cleanable_dirs=cleanable_dirs,
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


@app.command()
def nuke(
    older_than: int | None = typer.Option(
        None,
        "--older-than",
        "-o",
        help="Show projects older than X months",
    ),
    younger_than: int | None = typer.Option(
        None,
        "--younger-than",
        "-y",
        help="Show projects younger than X months",
    ),
    roots: list[str] | None = typer.Option(
        None,
        "--roots",
        "-r",
        help="Root directories to scan (can specify multiple)",
    ),
    github: bool = typer.Option(
        False,
        "--github",
        "-g",
        help="Also delete repositories from GitHub (requires gh CLI)",
    ),
    execute: bool = typer.Option(
        False,
        "--execute",
        "-e",
        help="Actually delete projects (default: dry run)",
    ),
) -> None:
    """Delete entire stale projects (DESTRUCTIVE).

    WARNING: This command deletes entire project directories, not just dependencies.

    Examples:

        dev-cleanup nuke                     # Dry run showing deletable projects

        dev-cleanup nuke --older-than 12     # Projects older than 1 year

        dev-cleanup nuke --github --execute  # Delete locally and from GitHub
    """
    config = load_config()

    # Interactive prompts for age filters
    if older_than is None and younger_than is None:
        console.print("\n[bold cyan]Age Filters[/]")
        older_than_months = int(inquirer.number(
            message="Show projects older than how many months?",
            default=int(config.get("older_than_months") or DEFAULT_CONFIG["older_than_months"]),
            min_allowed=0,
        ).execute())

        younger_prompt = int(inquirer.number(
            message="Show projects younger than how many months? (0 for no limit)",
            default=0,
            min_allowed=0,
        ).execute())
        younger_than_months = younger_prompt if younger_prompt > 0 else None
    else:
        older_than_months = older_than
        younger_than_months = younger_than

    root_paths = [
        Path(r).expanduser()
        for r in (roots or config.get("roots", DEFAULT_CONFIG["roots"]))
    ]

    from dev_cleanup.utils.display import get_filter_description
    filter_desc = get_filter_description(older_than_months, younger_than_months)

    # Header with warning
    mode_text = "[red]EXECUTE MODE - DESTRUCTIVE[/]" if execute else "[yellow]DRY RUN[/]"
    console.print(
        Panel.fit(
            f"[bold red]⚠️  NUKE MODE  ⚠️[/]\n\n"
            f"Mode: {mode_text}\n"
            f"Filter: {filter_desc}\n"
            f"Scanning: {', '.join(str(r) for r in root_paths)}\n"
            f"GitHub deletion: {'[red]ENABLED[/]' if github else '[dim]disabled[/]'}",
            border_style="red",
        )
    )

    # Scan for ALL stale projects (not filtered by cleanable dirs)
    console.print("\n[bold]Scanning for stale projects...[/]")

    # Import git utilities
    from dev_cleanup.utils.git import find_git_repos, get_last_commit_info, get_github_remote
    from dateutil.relativedelta import relativedelta
    from datetime import datetime

    older_cutoff = None
    younger_cutoff = None

    if older_than_months is not None:
        older_cutoff = datetime.now() - relativedelta(months=older_than_months)
    if younger_than_months is not None:
        younger_cutoff = datetime.now() - relativedelta(months=younger_than_months)

    stale_projects = []
    total_repos = 0

    with console.status("[bold red]Scanning repositories..."):
        for root in root_paths:
            if not root.exists():
                console.print(f"[yellow]Warning: Root {root} does not exist, skipping[/]")
                continue

            repos = find_git_repos(root)

            for repo_path in repos:
                total_repos += 1

                commit_info = get_last_commit_info(repo_path)
                if not commit_info:
                    continue

                last_commit_date, last_commit_message = commit_info

                # Check age filters
                if older_cutoff and last_commit_date >= older_cutoff:
                    continue  # Too recent
                if younger_cutoff and last_commit_date < younger_cutoff:
                    continue  # Too old

                # Get GitHub remote if needed
                github_remote = get_github_remote(repo_path) if github else None

                stale_projects.append({
                    "path": repo_path,
                    "name": repo_path.name,
                    "last_commit_date": last_commit_date,
                    "last_commit_message": last_commit_message,
                    "github_remote": github_remote,
                    "days_stale": (datetime.now() - last_commit_date).days,
                })

    if not stale_projects:
        console.print("\n[green]No stale projects found![/]")
        raise typer.Exit(0)

    console.print(f"\nScanned {total_repos} repositories")

    # Display results in table
    from rich.table import Table

    table = Table(title=f"Stale Projects - WILL BE DELETED ({filter_desc})")
    table.add_column("#", style="dim", width=4)
    table.add_column("Project", style="cyan")
    table.add_column("Last Commit", style="yellow")
    table.add_column("Days Stale", justify="right")
    if github:
        table.add_column("GitHub", style="magenta")

    for idx, project in enumerate(stale_projects, 1):
        row = [
            str(idx),
            project["name"],
            project["last_commit_date"].strftime("%Y-%m-%d"),
            str(project["days_stale"]),
        ]
        if github:
            row.append(project["github_remote"] or "[dim]no remote[/]")
        table.add_row(*row)

    console.print(table)

    # Interactive selection
    choices = [
        Choice(
            value=project,
            name=f"{project['name']} - {project['days_stale']} days stale"
            + (f" - {project['github_remote']}" if github and project['github_remote'] else ""),
        )
        for project in stale_projects
    ]

    console.print("\n")
    selected = inquirer.checkbox(
        message="[bold red]Select projects to DELETE ENTIRELY:[/]",
        choices=choices,
        instruction="(Use arrow keys to navigate, space to select, enter to confirm)",
    ).execute()

    if not selected:
        console.print("\n[yellow]No projects selected. Exiting.[/]")
        raise typer.Exit(0)

    # Show what will be deleted
    console.print("\n[bold red]Projects to be deleted:[/]")
    for project in selected:
        console.print(f"  - {project['path']}")
        if github and project['github_remote']:
            console.print(f"    [magenta]GitHub: {project['github_remote']}[/]")

    if not execute:
        console.print("\n[yellow]This was a dry run. Use --execute to actually delete.[/]")
        raise typer.Exit(0)

    # Multiple confirmations
    console.print("\n[bold red]⚠️  WARNING ⚠️[/]")
    console.print("[red]This will permanently delete entire project directories![/]")

    if not Confirm.ask(f"\n[bold]Delete {len(selected)} local projects?[/]"):
        console.print("[yellow]Cancelled.[/]")
        raise typer.Exit(0)

    if github:
        github_projects = [p for p in selected if p['github_remote']]
        if github_projects and not Confirm.ask(
            f"\n[bold red]Also delete {len(github_projects)} repositories from GitHub? THIS CANNOT BE UNDONE![/]"
        ):
            console.print("[yellow]Skipping GitHub deletion.[/]")
            github = False

    # Execute deletion
    console.print("\n[bold red]Deleting projects...[/]")

    success_count = 0
    fail_count = 0
    github_success = 0
    github_fail = 0

    for project in selected:
        project_path = project["path"]

        # Delete local project
        with console.status(f"Trashing {project['name']}..."):
            if trash_directory(project_path, execute=True):
                console.print(f"  [green]✓[/] {project_path}")
                success_count += 1
            else:
                console.print(f"  [red]✗[/] {project_path}")
                fail_count += 1

        # Delete from GitHub if requested
        if github and project['github_remote']:
            import subprocess

            with console.status(f"Deleting {project['github_remote']} from GitHub..."):
                try:
                    subprocess.run(
                        ["gh", "repo", "delete", project['github_remote'], "--yes"],
                        check=True,
                        capture_output=True,
                        timeout=30,
                    )
                    console.print(f"  [green]✓[/] Deleted from GitHub: {project['github_remote']}")
                    github_success += 1
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                    console.print(f"  [red]✗[/] Failed to delete from GitHub: {project['github_remote']}")
                    github_fail += 1

    # Final summary
    console.print("\n[bold green]Done![/]")
    console.print(f"  Deleted locally: {success_count} projects")
    if fail_count:
        console.print(f"  [red]Failed locally: {fail_count} projects[/]")
    if github:
        console.print(f"  Deleted from GitHub: {github_success} repositories")
        if github_fail:
            console.print(f"  [red]Failed GitHub deletion: {github_fail} repositories[/]")


if __name__ == "__main__":
    app()
