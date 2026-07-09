"""CLI entry point using Typer."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .config import resolve_workspace, get_tasks_dir
from .db import get_conn, init_db
from .ingest import ingest_inbox
from .process import process_all_tasks, process_single_task
from .reviews import write_review
from .package import load_manifest, get_processing_runs, get_quality_flags, get_review_records

app = typer.Typer(help="Material R&D Data Processing Agent MVP")
console = Console()


@app.command()
def ingest(
    inbox: str = typer.Option(..., help="Path to the inbox directory containing raw data files"),
    workspace: str = typer.Option("./workspace", help="Path to the workspace directory"),
):
    inbox_path = Path(inbox).resolve()
    ws = resolve_workspace(workspace)
    tasks_dir = get_tasks_dir(ws)

    if not inbox_path.exists():
        console.print(f"[red]Inbox directory not found: {inbox_path}[/red]")
        raise typer.Exit(1)

    conn = init_db(ws)

    console.print(f"Scanning inbox: {inbox_path}")
    task_ids = ingest_inbox(inbox_path, ws, conn)
    conn.close()

    console.print(f"\n[green]Created {len(task_ids)} tasks:[/green]")
    for tid in task_ids:
        manifest = load_manifest(tasks_dir / tid)
        if manifest:
            files = manifest.input_files
            console.print(f"  {tid}: {', '.join(files)}")

    console.print(f"\n[bold]Workspace: {ws}[/bold]")


@app.command()
def process(
    workspace: str = typer.Option("./workspace", help="Path to the workspace directory"),
    task: Optional[str] = typer.Option(None, help="Process a specific task ID"),
    all: bool = typer.Option(False, "--all", help="Process all tasks"),
    models: str = typer.Option("local", help="Model mode: local, cloud, or auto"),
):
    ws = resolve_workspace(workspace)
    console.print(f"Workspace: {ws}")
    console.print(f"Model mode: {models}")

    if task:
        console.print(f"Processing task: {task}")
        ok = process_single_task(ws, task, models)
        if ok:
            console.print(f"[green]Task {task} processed successfully.[/green]")
    elif all:
        count = process_all_tasks(ws, models)
        console.print(f"[green]Processed {count} task(s).[/green]")
    else:
        console.print("[red]Specify --task <id> or --all[/red]")
        raise typer.Exit(1)


@app.command()
def review(
    workspace: str = typer.Option("./workspace", help="Path to the workspace directory"),
    task: str = typer.Option(..., help="Task ID to review"),
    action: str = typer.Option(..., help="Review action: approve, return_for_rerun, mark_low_confidence, deprecate, link_related_data"),
    reviewer: str = typer.Option(..., help="Reviewer identifier"),
    comment: str = typer.Option("", help="Review comment"),
    target: str = typer.Option("", help="Target ID for the review"),
):
    ws = resolve_workspace(workspace)
    review_record = write_review(ws, task, action, reviewer, comment, target)
    console.print(f"[green]Review recorded: {review_record.action.value} by {review_record.reviewer}[/green]")
    if comment:
        console.print(f"  Comment: {comment}")


@app.command()
def open(
    workspace: str = typer.Option("./workspace", help="Path to the workspace directory"),
    task: Optional[str] = typer.Option(None, help="Task ID to open"),
    print_command: bool = typer.Option(False, "--print-command", help="Print the marimo command without starting the server"),
):
    ws = resolve_workspace(workspace)
    task_id = task or ""

    import subprocess
    import os
    import sys

    env = os.environ.copy()
    env["DATA_AGENT_WORKSPACE"] = str(ws.resolve())
    if task_id:
        env["DATA_AGENT_TASK_ID"] = task_id

    marimo_path = Path(__file__).parent.parent / "marimo_apps" / "task_review.py"
    cmd = [sys.executable, "-m", "marimo", "run", str(marimo_path)]

    console.print(f"[bold]Marimo command:[/bold]")
    console.print(f"  Executable: {sys.executable}")
    console.print(f"  Arguments: -m marimo run {marimo_path}")
    console.print(f"  Workspace: {ws.resolve()}")
    if task_id:
        console.print(f"  Task ID: {task_id}")
    console.print(f"  [dim]{' '.join(cmd)}[/dim]")
    console.print(f"  DATA_AGENT_WORKSPACE={env['DATA_AGENT_WORKSPACE']}")
    if task_id:
        console.print(f"  DATA_AGENT_TASK_ID={env['DATA_AGENT_TASK_ID']}")

    if not print_command:
        console.print("\nStarting marimo...")
        subprocess.run(cmd, env=env)
    else:
        console.print("\n[green]--print-command mode: not starting server.[/green]")


@app.command()
def info(
    workspace: str = typer.Option("./workspace", help="Path to the workspace directory"),
):
    ws = resolve_workspace(workspace)
    tasks_dir = get_tasks_dir(ws)

    table = Table(title="Tasks")
    table.add_column("Task ID")
    table.add_column("Status")
    table.add_column("Input Files")
    table.add_column("Runs")
    table.add_column("Flags")
    table.add_column("Reviews")

    if tasks_dir.exists():
        for task_dir in sorted(tasks_dir.iterdir()):
            if task_dir.is_dir() and task_dir.name.startswith("task_"):
                manifest = load_manifest(task_dir)
                if manifest:
                    files = ", ".join(manifest.input_files)
                    table.add_row(
                        task_dir.name,
                        manifest.status,
                        files,
                        str(len(manifest.run_ids or [])),
                        str(len(manifest.flag_ids or [])),
                        str(len(manifest.review_ids or [])),
                    )

    console.print(table)


def main():
    app()


if __name__ == "__main__":
    main()
