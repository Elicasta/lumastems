from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .engine import LumaStemEngine
from .jobs import JobManager
from .models import JobRecord, SeparationPreset
from .presets import PRESETS, get_preset

APP_HOME = Path.home() / ".lumastems"
UPLOAD_DIR = APP_HOME / "uploads"
OUTPUT_DIR = APP_HOME / "outputs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

engine = LumaStemEngine(model_dir=APP_HOME / "models")
jobs = JobManager(engine)

app = FastAPI(
    title="LumaStems",
    version="0.1.0",
    description="Local stem-separation service for Ableton and LumaStudio.",
)


class PathJobRequest(BaseModel):
    path: str
    preset: str = "worship"
    output_format: str = "WAV"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "lumastems"}


@app.get("/presets", response_model=list[SeparationPreset])
def presets() -> list[SeparationPreset]:
    return list(PRESETS.values())


@app.post("/jobs/from-path", response_model=JobRecord, status_code=202)
def create_path_job(request: PathJobRequest) -> JobRecord:
    try:
        get_preset(request.preset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    source = Path(request.path).expanduser()
    if not source.exists():
        raise HTTPException(status_code=404, detail=f"Audio file not found: {source}")

    return jobs.submit(
        source,
        preset_id=request.preset,
        output_root=OUTPUT_DIR,
        output_format=request.output_format,
    )


@app.post("/jobs/upload", response_model=JobRecord, status_code=202)
def create_upload_job(
    file: UploadFile = File(...),
    preset: str = Form("worship"),
    output_format: str = Form("WAV"),
) -> JobRecord:
    try:
        get_preset(preset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    safe_name = Path(file.filename or "audio.wav").name
    destination = UPLOAD_DIR / f"{uuid4().hex}_{safe_name}"

    with destination.open("wb") as target:
        shutil.copyfileobj(file.file, target)

    return jobs.submit(
        destination,
        preset_id=preset,
        output_root=OUTPUT_DIR,
        output_format=output_format,
    )


@app.get("/jobs", response_model=list[JobRecord])
def list_jobs() -> list[JobRecord]:
    return jobs.list()


@app.get("/jobs/{job_id}", response_model=JobRecord)
def get_job(job_id: str) -> JobRecord:
    try:
        return jobs.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
