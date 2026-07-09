"""Marimo single-task review workspace."""
import marimo

__generated_with = "0.23.13"
app = marimo.App(width="full")


@app.cell
def __():
    import os
    import json
    from pathlib import Path
    import marimo as mo

    task_id = os.environ.get("DATA_AGENT_TASK_ID", "")
    workspace_path = os.environ.get("DATA_AGENT_WORKSPACE", "./workspace")

    task_dir = Path(workspace_path) / "tasks" / task_id
    manifest_data = {}
    if task_dir.exists():
        manifest_path = task_dir / "manifest.json"
        if manifest_path.exists():
            manifest_data = json.loads(manifest_path.read_text())

    mo.md(f"## Task Review: `{task_id}`")
    return mo, json, task_dir, task_id, workspace_path, manifest_data


@app.cell
def __(manifest_data, mo):
    mo.md(f"""
    ### Manifest
    - Status: `{manifest_data.get('status', 'unknown')}`
    - Input Files: {', '.join(manifest_data.get('input_files', []))}
    - Objects: {len(manifest_data.get('object_ids', []))}
    - Runs: {len(manifest_data.get('run_ids', []))}
    - Flags: {len(manifest_data.get('flag_ids', []))}
    - Reviews: {len(manifest_data.get('review_ids', []))}
    - Derived Files: {len(manifest_data.get('derived_files', []))}
    """)
    return


@app.cell
def __(mo, task_dir):
    raw_files = list((task_dir / "raw").glob("*")) if task_dir.exists() else []
    raw_list = [f.name for f in raw_files if not f.name.startswith(".")]
    derived_files = list((task_dir / "derived").glob("*")) if task_dir.exists() else []
    derived_list = [f.name for f in derived_files if not f.name.startswith(".")]

    mo.md(f"""
    ### Raw Files (L1)
    {chr(10).join(['- ' + f for f in raw_list]) if raw_list else '- None'}

    ### Derived Files (L2)
    {chr(10).join(['- ' + f for f in derived_list]) if derived_list else '- None'}
    """)
    return derived_files, derived_list, raw_files, raw_list


@app.cell
def __(mo, json, task_dir):
    runs_path = task_dir / "logs" / "processing_runs.json"
    runs = json.loads(runs_path.read_text()) if runs_path.exists() else []
    runs_json = json.dumps(runs, ensure_ascii=False, indent=2) if runs else "[]"
    mo.md(f"### Processing Runs ({len(runs)})")
    mo.plain_text(runs_json)
    return runs, runs_json


@app.cell
def __(mo, json, task_dir):
    flags_path = task_dir / "logs" / "quality_flags.json"
    flags = json.loads(flags_path.read_text()) if flags_path.exists() else []
    flags_json = json.dumps(flags, ensure_ascii=False, indent=2) if flags else "[]"
    mo.md(f"### Quality Flags ({len(flags)})")
    mo.plain_text(flags_json)
    return flags, flags_json


@app.cell
def __(mo, json, task_dir):
    rels_path = task_dir / "logs" / "relationships.json"
    rels = json.loads(rels_path.read_text()) if rels_path.exists() else []
    rels_json = json.dumps(rels, ensure_ascii=False, indent=2) if rels else "[]"
    mo.md(f"### Relationships ({len(rels)})")
    mo.plain_text(rels_json)
    return rels, rels_json


@app.cell
def __(mo, json, task_dir):
    reviews_path = task_dir / "reviews" / "review_records.json"
    reviews = json.loads(reviews_path.read_text()) if reviews_path.exists() else []
    reviews_json = json.dumps(reviews, ensure_ascii=False, indent=2) if reviews else "[]"
    mo.md(f"### Review Records ({len(reviews)})")
    mo.plain_text(reviews_json)
    return reviews, reviews_json


@app.cell
def __(mo):
    mo.md("""
    ### Actions
    Run the following CLI commands to perform review actions:

    - **Approve**: `.venv/bin/python -m data_agent review --workspace ./workspace --task <TASK> --action approve --reviewer <NAME>`
    - **Rerun**: `.venv/bin/python -m data_agent review --workspace ./workspace --task <TASK> --action return_for_rerun --reviewer <NAME>`
    - **Low Confidence**: `.venv/bin/python -m data_agent review --workspace ./workspace --task <TASK> --action mark_low_confidence --reviewer <NAME>`
    - **Deprecate**: `.venv/bin/python -m data_agent review --workspace ./workspace --task <TASK> --action deprecate --reviewer <NAME>`
    """)
    return


if __name__ == "__main__":
    app.run()
