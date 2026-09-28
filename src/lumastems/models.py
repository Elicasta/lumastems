from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class StageBackend(StrEnum):
    AUDIO_SEPARATOR = "audio_separator"


class StemSpec(BaseModel):
    source_label: str
    output_name: str


class SeparationStage(BaseModel):
    id: str
    model_filename: str | None = None
    ensemble_preset: str | None = None
    backend: StageBackend = StageBackend.AUDIO_SEPARATOR
    input_stem: str | None = None
    stems: tuple[StemSpec, ...]
    separator_options: dict[str, Any] = Field(default_factory=dict)
    description: str = ""


class SeparationPreset(BaseModel):
    id: str
    name: str
    description: str
    stages: tuple[SeparationStage, ...]
    expected_stems: tuple[str, ...]


class StemFile(BaseModel):
    stem: str
    path: str
    model: str
    stage: str


class SeparationManifest(BaseModel):
    schema_version: Literal[1] = 1
    source: str
    preset: str
    output_format: str
    stems: list[StemFile]
    created_at: str


class SeparationResult(BaseModel):
    output_dir: Path
    manifest_path: Path
    stems: list[StemFile]


class JobRecord(BaseModel):
    id: str
    status: JobStatus
    source: str
    preset: str
    output_dir: str | None = None
    manifest_path: str | None = None
    error: str | None = None
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
