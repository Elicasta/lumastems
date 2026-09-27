from __future__ import annotations

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
    This specialist receives only the residual Other stem, runs the published
    BS-RoFormer model through bs-roformer-infer's supported public primitives,
    then writes Synth plus the remaining residual Other.
    """

    def __init__(self, model_dir: Path) -> None:
        self.model_dir = model_dir / "synth"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.model_path = self.model_dir / SYNTH_MODEL_FILENAME
        self.config_path = self.model_dir / SYNTH_CONFIG_FILENAME

    @staticmethod
    def validate_runtime_api() -> None:
        """Fail early if the installed bs-roformer-infer API is incompatible."""
        try:
            from bs_roformer import demix_track, get_model_from_config  # noqa: F401
            from bs_roformer.bs_roformer import MaskEstimator  # noqa: F401
            from bs_roformer.inference import SafeLoaderWithTuple  # noqa: F401
            from ml_collections import ConfigDict  # noqa: F401
        except ImportError as exc:
            raise SpecialistError(
                "The installed bs-roformer-infer runtime is incompatible with LumaStems."
            ) from exc

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

        self.validate_runtime_api()
        self.ensure_assets(progress=progress)
        output_dir.mkdir(parents=True, exist_ok=True)

        if progress:
            progress(0.0, "Loading synth specialist")

        try:
            import numpy as np
            import soundfile as sf
            import torch
            import yaml
            from bs_roformer import demix_track
            from bs_roformer.inference import SafeLoaderWithTuple
            from ml_collections import ConfigDict
        except ImportError as exc:
            raise SpecialistError(
                "Synth specialist dependencies are incomplete in the LumaStems runtime."
            ) from exc

        try:
            with self.config_path.open("r", encoding="utf-8") as handle:
                config = ConfigDict(yaml.load(handle, Loader=SafeLoaderWithTuple))

            model = self._build_compatible_model(config)
            checkpoint = torch.load(self.model_path, map_location=torch.device("cpu"))
            model.load_state_dict(checkpoint)
            device = torch.device("cpu")
            model = model.to(device)
            model.eval()

            mixture_audio, sample_rate = sf.read(
                input_path,
                always_2d=True,
                dtype="float32",
            )
            if mixture_audio.shape[1] == 1:
                mixture_audio = np.repeat(mixture_audio, 2, axis=1)

            mixture = torch.tensor(mixture_audio.T, dtype=torch.float32)

            if progress:
                progress(0.15, "Separating synth")

            separated, _ = demix_track(
                config,
                model,
                mixture,
                device,
                first_chunk_time=None,
            )
            target = self._resolve_target_instrument(config, separated)
            synth_audio = separated[target].T

            if synth_audio.ndim == 1:
                synth_audio = np.stack([synth_audio, synth_audio], axis=-1)

            synth_audio = self._match_shape(synth_audio, mixture_audio)
            other_audio = mixture_audio - synth_audio

            synth_path = output_dir / "synth.wav"
            other_path = output_dir / "other.wav"
            sf.write(synth_path, synth_audio, sample_rate, subtype="FLOAT")
            sf.write(other_path, other_audio, sample_rate, subtype="FLOAT")
        except SpecialistError:
            raise
        except Exception as exc:
            raise SpecialistError(f"Synth specialist inference failed: {exc}") from exc

        if progress:
            progress(1.0, "Synth specialist complete")

        return {
            "synth": synth_path.resolve(),
            "other": other_path.resolve(),
        }

    @staticmethod
    def _build_compatible_model(config: object):
        """Build the published MVSep checkpoint architecture exactly.

        bs-roformer-infer 0.1.5 filters out model.mlp_expansion_factor when it
        constructs BSRoformer. The MVSep Mega 53 checkpoints use factor 2,
        while the package's MaskEstimator defaults to factor 4. That doubles
        the hidden layer width and makes the published checkpoint impossible
        to load unless we repair the mask estimator after model construction.
        """
        import torch
        from bs_roformer import get_model_from_config
        from bs_roformer.bs_roformer import MaskEstimator

        model = get_model_from_config("bs_roformer", config)

        model_config = getattr(config, "model", None)
        expansion = int(getattr(model_config, "mlp_expansion_factor", 4))
        depth = int(getattr(model_config, "mask_estimator_depth", 2))

        if expansion != 4:
            repaired = []
            for estimator in model.mask_estimators:
                repaired.append(
                    MaskEstimator(
                        dim=int(model_config.dim),
                        dim_inputs=tuple(estimator.dim_inputs),
                        depth=depth,
                        mlp_expansion_factor=expansion,
                    )
                )
            model.mask_estimators = torch.nn.ModuleList(repaired)

        return model

    def validate_checkpoint_compatibility(self) -> None:
        """Download the specialist assets and prove the checkpoint loads."""
        self.validate_runtime_api()
        self.ensure_assets()

        try:
            import torch
            import yaml
            from bs_roformer.inference import SafeLoaderWithTuple
            from ml_collections import ConfigDict
        except ImportError as exc:
            raise SpecialistError(
                "Synth specialist dependencies are incomplete in the LumaStems runtime."
            ) from exc

        with self.config_path.open("r", encoding="utf-8") as handle:
            config = ConfigDict(yaml.load(handle, Loader=SafeLoaderWithTuple))

        model = self._build_compatible_model(config)
        checkpoint = torch.load(self.model_path, map_location=torch.device("cpu"))
        try:
            model.load_state_dict(checkpoint)
        except RuntimeError as exc:
            raise SpecialistError(
                f"Synth checkpoint does not match the configured model architecture: {exc}"
            ) from exc

    @staticmethod
    def _resolve_target_instrument(config: object, separated: dict[str, object]) -> str:
        training = getattr(config, "training", None)
        target = getattr(training, "target_instrument", None)
        if target and target in separated:
            return str(target)

        keys = list(separated)
        for key in keys:
            normalized = key.lower().replace("_", " ").replace("-", " ")
            if "synth" in normalized:
                return key

        instruments = list(getattr(training, "instruments", ()) or ())
        if len(instruments) == 1 and instruments[0] in separated:
            return str(instruments[0])

        raise SpecialistError(
            "Synth model ran but did not expose a synth target. "
            f"Available outputs: {', '.join(keys) or 'none'}"
        )

    @staticmethod
    def _match_shape(synth_audio: object, mixture_audio: object):
        import numpy as np

        if synth_audio.shape[1] != mixture_audio.shape[1]:
            if synth_audio.shape[1] == 1 and mixture_audio.shape[1] == 2:
                synth_audio = np.repeat(synth_audio, 2, axis=1)
            else:
                raise SpecialistError(
                    "Synth output channel count does not match the source residual."
                )

        if synth_audio.shape[0] < mixture_audio.shape[0]:
            pad = np.zeros(
                (mixture_audio.shape[0] - synth_audio.shape[0], synth_audio.shape[1]),
                dtype=synth_audio.dtype,
            )
            synth_audio = np.concatenate([synth_audio, pad], axis=0)
        elif synth_audio.shape[0] > mixture_audio.shape[0]:
            synth_audio = synth_audio[: mixture_audio.shape[0]]

        return synth_audio

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
