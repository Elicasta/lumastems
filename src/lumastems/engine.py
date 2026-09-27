from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .models import SeparationManifest, SeparationResult, StemFile
from .presets import get_preset

SUPPORTED_INPUTS = {".wav", ".mp3", ".flac", ".m4a", ".aiff", ".aif", ".ogg"}


class SeparationError(RuntimeError):
    """Raised when a separation job cannot be completed safely."""


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-._")
    return slug or "audio"


class LumaStemEngine:
    def __init__(
        self,
        *,
        model_dir: Path | None = None,
        separator_factory: Callable[..., Any] | None = None,
        log_level: int = logging.INFO,
    ) -> None:
        self.model_dir = (model_dir or Path.home() / ".lumastems" / "models").expanduser()
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self._separator_factory = separator_factory
        self.log_level = log_level

    def _get_separator_factory(self) -> Callable[..., Any]:
        if self._separator_factory is not None:
            return self._separator_factory

        try:
            from audio_separator.separator import Separator
        except ImportError as exc:
            raise SeparationError(
                "audio-separator is not installed. Run: pip install -e ."
            ) from exc

        return Separator

    def warm_preset(self, preset_id: str) -> list[str]:
        """Download/load every unique model needed by a preset."""
        preset = get_preset(preset_id)
        factory = self._get_separator_factory()
        downloaded: list[str] = []

        for model in dict.fromkeys(stage.model_filename for stage in preset.stages):
            separator = factory(
                model_file_dir=str(self.model_dir),
                log_level=self.log_level,
                info_only=True,
            )
            separator.load_model(model)
            downloaded.append(model)

        return downloaded

    def separate(
        self,
        source: Path,
        *,
        preset_id: str = "worship",
        output_root: Path | None = None,
        output_format: str = "WAV",
        progress: Callable[[float, str], None] | None = None,
    ) -> SeparationResult:
        source = source.expanduser().resolve()
        self._validate_source(source)

        preset = get_preset(preset_id)
        root = (output_root or Path.cwd() / "outputs").expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)

        run_dir = root / f"{_safe_slug(source.stem)}-{uuid4().hex[:8]}"
        run_dir.mkdir(parents=True, exist_ok=False)

        factory = self._get_separator_factory()
        stem_paths: dict[str, Path] = {}
        stem_files: list[StemFile] = []
        total_stages = len(preset.stages)

        for index, stage in enumerate(preset.stages):
            stage_input = source if stage.input_stem is None else stem_paths.get(stage.input_stem)
            if stage_input is None:
                raise SeparationError(
                    f"Stage '{stage.id}' requires missing stem '{stage.input_stem}'."
                )

            stage_dir = run_dir / stage.id
            stage_dir.mkdir(parents=True, exist_ok=True)

            if progress:
                progress(index / total_stages, f"Loading {stage.model_filename}")

            separator = factory(
                model_file_dir=str(self.model_dir),
                output_dir=str(stage_dir),
                output_format=output_format.upper(),
                log_level=self.log_level,
            )
            separator.load_model(stage.model_filename)

            custom_names = {stem.source_label: stem.output_name for stem in stage.stems}
            produced = separator.separate(
                str(stage_input),
                custom_output_names=custom_names,
            )

            discovered = self._discover_outputs(
                stage_dir=stage_dir,
                produced=produced,
                expected_names=set(custom_names.values()),
            )

            missing = set(custom_names.values()) - set(discovered)
            if missing:
                missing_text = ", ".join(sorted(missing))
                raise SeparationError(
                    f"Model '{stage.model_filename}' did not produce expected stems: {missing_text}"
                )

            for spec in stage.stems:
                path = discovered[spec.output_name]
                stem_paths[spec.output_name] = path
                stem_files.append(
                    StemFile(
                        stem=spec.output_name,
                        path=str(path),
                        model=stage.model_filename,
                        stage=stage.id,
                    )
                )

            if progress:
                progress((index + 1) / total_stages, f"Finished {stage.id}")

        manifest = SeparationManifest(
            source=str(source),
            preset=preset.id,
            output_format=output_format.upper(),
            stems=stem_files,
            created_at=datetime.now(UTC).isoformat(),
        )
        manifest_path = run_dir / "lumastems.json"
        self._write_manifest(manifest_path, manifest)

        return SeparationResult(
            output_dir=run_dir,
            manifest_path=manifest_path,
            stems=stem_files,
        )

    @staticmethod
    def _validate_source(source: Path) -> None:
        if not source.exists():
            raise FileNotFoundError(f"Audio file does not exist: {source}")
        if not source.is_file():
            raise SeparationError(f"Audio source is not a file: {source}")
        if source.suffix.lower() not in SUPPORTED_INPUTS:
            supported = ", ".join(sorted(SUPPORTED_INPUTS))
            raise SeparationError(
                f"Unsupported audio format '{source.suffix}'. Supported: {supported}"
            )

    @staticmethod
    def _discover_outputs(
        *,
        stage_dir: Path,
        produced: list[str] | tuple[str, ...] | None,
        expected_names: set[str],
    ) -> dict[str, Path]:
        candidates: list[Path] = []

        for item in produced or []:
            path = Path(item)
            if not path.is_absolute():
                local = stage_dir / path
                path = local if local.exists() else path
            if path.exists():
                candidates.append(path.resolve())

        candidates.extend(
            path.resolve()
            for path in stage_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_INPUTS
        )

        discovered: dict[str, Path] = {}
        for path in dict.fromkeys(candidates):
            normalized = path.stem.lower().replace(" ", "_").replace("-", "_")
            for expected in expected_names:
                key = expected.lower().replace(" ", "_").replace("-", "_")
                if normalized == key or normalized.endswith(f"_{key}") or key in normalized:
                    discovered.setdefault(expected, path)

        return discovered

    @staticmethod
    def _write_manifest(path: Path, manifest: SeparationManifest) -> None:
        temp = path.with_suffix(".tmp")
        temp.write_text(
            json.dumps(manifest.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )
        temp.replace(path)
