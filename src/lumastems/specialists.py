from __future__ import annotations

import shutil
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

SYNTH_MODEL_FILENAME = "bs_mega_53stem_synth_mvsep.ckpt"
SYNTH_CONFIG_FILENAME = "bs_mega_53stem_synth_mvsep_config.yaml"
SYNTH_MODEL_URL = (
    "https://huggingface.co/noblebarkrr/BS-Roformer-MVSep-Mega-53-stems/"
    "resolve/main/v1/bs_mega_53stem_synth_mvsep.ckpt?download=true"
)
SYNTH_CONFIG_URL = (
    "https://huggingface.co/noblebarkrr/BS-Roformer-MVSep-Mega-53-stems/"
    "resolve/main/v1/bs_mega_53stem_synth_mvsep_config.yaml?download=true"
)


class SpecialistError(RuntimeError):
    """Raised when a specialist separation pass fails."""


class SynthSpecialist:
    """MVSep Mega 53 synth-vs-rest specialist.

    The broad six-stem pass first removes vocals, drums, bass, guitar, and piano.
    This specialist then receives only the residual other stem.
    """

    def __init__(
        self,
        model_dir: Path,
        *,
        session_factory: Callable[..., object] | None = None,
    ) -> None:
        self.model_dir = model_dir / "synth"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.model_path = self.model_dir / SYNTH_MODEL_FILENAME
        self.config_path = self.model_dir / SYNTH_CONFIG_FILENAME
        self._session_factory = session_factory

    def ensure_assets(
        self,
        progress: Callable[[float, str], None] | None = None,
    ) -> list[str]:
        self._download(
            SYNTH_CONFIG_URL,
            self.config_path,
            progress=progress,
            label="Synth config",
        )
        self._download(
            SYNTH_MODEL_URL,
            self.model_path,
            progress=progress,
            label="Synth model",
        )
        return [str(self.model_path), str(self.config_path)]

    def separate(
        self,
        input_path: Path,
        output_dir: Path,
        *,
        progress: Callable[[float, str], None] | None = None,
    ) -> dict[str, Path]:
        if input_path.suffix.lower() != ".wav":
            raise SpecialistError("Synth specialist currently requires a WAV input stem.")

        self.ensure_assets(progress=progress)
        output_dir.mkdir(parents=True, exist_ok=True)
        input_dir = output_dir / "_input"
        raw_dir = output_dir / "_raw"
        input_dir.mkdir(parents=True, exist_ok=True)
        raw_dir.mkdir(parents=True, exist_ok=True)

        staged_input = input_dir / "other.wav"
        shutil.copy2(input_path, staged_input)

        if progress:
            progress(0.0, "Loading synth specialist")

        session_factory = self._get_session_factory()
        session = session_factory(
            model_name="lumastems-mvsep-synth",
            model_path=self.model_path,
            config_path=self.config_path,
            device="cpu",
            progress=False,
        )

        try:
            session.load()
            manifest = session.infer(
                input_dir,
                store_dir=raw_dir,
                verbose=False,
                output_format="wav_float32",
            )
        finally:
            session.close()

        synth_source = self._find_synth_output(manifest)
        synth_path = output_dir / "synth.wav"
        shutil.copy2(synth_source, synth_path)

        other_path = output_dir / "other.wav"
        self._write_residual(staged_input, synth_path, other_path)

        shutil.rmtree(input_dir, ignore_errors=True)
        shutil.rmtree(raw_dir, ignore_errors=True)

        if progress:
            progress(1.0, "Synth specialist complete")

        return {"synth": synth_path.resolve(), "other": other_path.resolve()}

    def _get_session_factory(self) -> Callable[..., object]:
        if self._session_factory is not None:
            return self._session_factory

        try:
            from bs_roformer.clean_api import BSRoformerSession
        except ImportError as exc:
            raise SpecialistError(
                "bs-roformer-infer is not installed in the LumaStems runtime."
            ) from exc
        return BSRoformerSession

    @staticmethod
    def _find_synth_output(manifest: object) -> Path:
        outputs = getattr(manifest, "outputs", ())
        for output in outputs:
            if getattr(output, "output_id", "").lower() == "synth":
                path = Path(output.output_path)
                if path.exists():
                    return path
        raise SpecialistError("Synth model completed without producing a synth stem.")

    @staticmethod
    def _write_residual(source: Path, synth: Path, destination: Path) -> None:
        try:
            import numpy as np
            import soundfile as sf
        except ImportError as exc:
            raise SpecialistError("numpy and soundfile are required for synth residual output.") from exc

        mixture, sample_rate = sf.read(source, always_2d=True, dtype="float32")
        synth_audio, synth_rate = sf.read(synth, always_2d=True, dtype="float32")
        if sample_rate != synth_rate:
            raise SpecialistError(
                f"Synth output sample rate changed unexpectedly: {sample_rate} -> {synth_rate}"
            )

        if synth_audio.shape[1] != mixture.shape[1]:
            if synth_audio.shape[1] == 1 and mixture.shape[1] == 2:
                synth_audio = np.repeat(synth_audio, 2, axis=1)
            else:
                raise SpecialistError(
                    "Synth output channel count does not match the source residual."
                )

        if synth_audio.shape[0] < mixture.shape[0]:
            pad = np.zeros(
                (mixture.shape[0] - synth_audio.shape[0], synth_audio.shape[1]),
                dtype=synth_audio.dtype,
            )
            synth_audio = np.concatenate([synth_audio, pad], axis=0)
        elif synth_audio.shape[0] > mixture.shape[0]:
            synth_audio = synth_audio[: mixture.shape[0]]

        residual = mixture - synth_audio
        sf.write(destination, residual, sample_rate, subtype="FLOAT")

    @staticmethod
    def _download(
        url: str,
        destination: Path,
        *,
        progress: Callable[[float, str], None] | None,
        label: str,
    ) -> None:
        if destination.exists() and destination.stat().st_size > 0:
            return

        partial = destination.with_suffix(destination.suffix + ".part")
        offset = partial.stat().st_size if partial.exists() else 0
        headers = {"User-Agent": "LumaStems/0.2"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = urllib.request.Request(url, headers=headers)

        try:
            response = urllib.request.urlopen(request, timeout=60)
        except urllib.error.URLError as exc:
            raise SpecialistError(f"Could not download {label.lower()}: {exc}") from exc

        status = getattr(response, "status", 200)
        append = offset > 0 and status == 206
        if not append:
            offset = 0

        content_length = int(response.headers.get("Content-Length", "0") or 0)
        total = offset + content_length if content_length else 0
        mode = "ab" if append else "wb"
        downloaded = offset

        destination.parent.mkdir(parents=True, exist_ok=True)
        with response, partial.open(mode) as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                downloaded += len(chunk)
                if progress and total:
                    progress(min(downloaded / total, 0.99), f"Downloading {label}")

        if downloaded <= 0:
            raise SpecialistError(f"Downloaded {label.lower()} is empty.")

        partial.replace(destination)
