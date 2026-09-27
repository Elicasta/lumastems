from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from uuid import uuid4

from .engine import LumaStemEngine
from .models import JobRecord, JobStatus


class JobManager:
    """Small in-process queue.

    Separation is intentionally serialized by default. Running multiple large models
    at once on the same GPU/MPS device tends to make a workstation less stable and
    rarely improves end-to-end throughput.
    """

    def __init__(self, engine: LumaStemEngine | None = None, *, max_workers: int = 1) -> None:
        self.engine = engine or LumaStemEngine()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="lumastems")
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()

    def submit(
        self,
        source: Path,
        *,
        preset_id: str,
        output_root: Path,
        output_format: str = "WAV",
    ) -> JobRecord:
        job = JobRecord(
            id=uuid4().hex,
            status=JobStatus.QUEUED,
            source=str(source.expanduser()),
            preset=preset_id,
        )
        with self._lock:
            self._jobs[job.id] = job

        self._executor.submit(
            self._run,
            job.id,
            source,
            preset_id,
            output_root,
            output_format,
        )
        return self.get(job.id)

    def get(self, job_id: str) -> JobRecord:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            return job.model_copy(deep=True)

    def list(self) -> list[JobRecord]:
        with self._lock:
            return [job.model_copy(deep=True) for job in self._jobs.values()]

    def _patch(self, job_id: str, **changes: object) -> None:
        with self._lock:
            current = self._jobs[job_id]
            self._jobs[job_id] = current.model_copy(update=changes)

    def _run(
        self,
        job_id: str,
        source: Path,
        preset_id: str,
        output_root: Path,
        output_format: str,
    ) -> None:
        self._patch(job_id, status=JobStatus.RUNNING, progress=0.01)

        def on_progress(value: float, _: str) -> None:
            self._patch(job_id, progress=max(0.01, min(value, 0.99)))

        try:
            result = self.engine.separate(
                source,
                preset_id=preset_id,
                output_root=output_root,
                output_format=output_format,
                progress=on_progress,
            )
        except Exception as exc:  # noqa: BLE001 - worker boundary must convert failures into job state
            self._patch(
                job_id,
                status=JobStatus.FAILED,
                progress=1.0,
                error=f"{type(exc).__name__}: {exc}",
            )
            return

        self._patch(
            job_id,
            status=JobStatus.SUCCEEDED,
            progress=1.0,
            output_dir=str(result.output_dir),
            manifest_path=str(result.manifest_path),
        )
