from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from .engine import LumaStemEngine
from .presets import PRESETS

app = typer.Typer(
    name="lumastems",
    no_args_is_help=True,
    help="Local stem separation for Ableton and LumaStudio.",
)


@app.command("presets")
def list_presets() -> None:
    """Show available separation presets."""
    for preset in PRESETS.values():
        typer.echo(f"{preset.id:10} {preset.name}")
        typer.echo(f"           {preset.description}")


@app.command()
def warm(
    preset: Annotated[str, typer.Option("--preset", "-p")] = "worship",
) -> None:
    """Download/load the models required by a preset."""
    engine = LumaStemEngine()
    models = engine.warm_preset(preset)
    for model in models:
        typer.echo(f"ready: {model}")


@app.command()
def split(
    source: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    preset: Annotated[str, typer.Option("--preset", "-p")] = "worship",
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("outputs"),
    output_format: Annotated[str, typer.Option("--format", "-f")] = "WAV",
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Separate one audio file."""
    engine = LumaStemEngine()

    def progress(value: float, message: str) -> None:
        if not json_output:
            typer.echo(f"[{value * 100:5.1f}%] {message}")

    result = engine.separate(
        source,
        preset_id=preset,
        output_root=output,
        output_format=output_format,
        progress=progress,
    )

    payload = {
        "output_dir": str(result.output_dir),
        "manifest": str(result.manifest_path),
        "stems": [stem.model_dump() for stem in result.stems],
    }

    if json_output:
        typer.echo(f"LUMASTEMS_RESULT={json.dumps(payload, separators=(',', ':'))}")
        return

    typer.echo(f"Done: {result.output_dir}")
    typer.echo(f"Manifest: {result.manifest_path}")


@app.command()
def serve(
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port")] = 8765,
) -> None:
    """Run the local API used by Ableton/LumaStudio integrations."""
    import uvicorn

    uvicorn.run("lumastems.api:app", host=host, port=port, reload=False)
