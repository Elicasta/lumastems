from __future__ import annotations

from .models import SeparationPreset, SeparationStage, StemSpec


def _stems(*pairs: tuple[str, str]) -> tuple[StemSpec, ...]:
    return tuple(StemSpec(source_label=source, output_name=output) for source, output in pairs)


BAND_STEMS = _stems(
    ("Vocals", "vocals"),
    ("Drums", "drums"),
    ("Bass", "bass"),
    ("Guitar", "guitar"),
    ("Piano", "piano"),
    ("Other", "other"),
)

PRESETS: dict[str, SeparationPreset] = {
    "quick": SeparationPreset(
        id="quick",
        name="Quick 4-Stem",
        description="Fast general-purpose split for playback and practice.",
        stages=(
            SeparationStage(
                id="main",
                model_filename="htdemucs_ft.yaml",
                description="Demucs 4-stem separation",
                stems=_stems(
                    ("Vocals", "vocals"),
                    ("Drums", "drums"),
                    ("Bass", "bass"),
                    ("Other", "other"),
                ),
            ),
        ),
        expected_stems=("vocals", "drums", "bass", "other"),
    ),
    "band": SeparationPreset(
        id="band",
        name="Band 6",
        description="Stable six-stem band split with dedicated guitar and piano.",
        stages=(
            SeparationStage(
                id="main",
                model_filename="htdemucs_6s.yaml",
                description="Primary six-stem band separation",
                stems=BAND_STEMS,
            ),
        ),
        expected_stems=("vocals", "drums", "bass", "guitar", "piano", "other"),
    ),
    "worship": SeparationPreset(
        id="worship",
        name="Worship 6",
        description="Stable worship-band six-stem split.",
        stages=(
            SeparationStage(
                id="main",
                model_filename="htdemucs_6s.yaml",
                description="Primary worship-band separation",
                stems=BAND_STEMS,
            ),
        ),
        expected_stems=("vocals", "drums", "bass", "guitar", "piano", "other"),
    ),
    "worship7": SeparationPreset(
        id="worship7",
        name="Worship Vocals 7",
        description=(
            "Stable six-stem band split followed by UVR backing-vocal extraction "
            "on the isolated vocal stem."
        ),
        stages=(
            SeparationStage(
                id="main",
                model_filename="htdemucs_6s.yaml",
                description="Primary worship-band separation",
                stems=BAND_STEMS,
            ),
            SeparationStage(
                id="vocals",
                model_filename="UVR-BVE-4B_SN-44100-2.pth",
                input_stem="vocals",
                description="Lead-vocal and backing-vocal specialist",
                stems=_stems(
                    ("Instrumental", "lead_vocals"),
                    ("Vocals", "backing_vocals"),
                ),
            ),
        ),
        expected_stems=(
            "lead_vocals",
            "backing_vocals",
            "drums",
            "bass",
            "guitar",
            "piano",
            "other",
        ),
    ),
}


def get_preset(preset_id: str) -> SeparationPreset:
    try:
        return PRESETS[preset_id]
    except KeyError as exc:
        valid = ", ".join(sorted(PRESETS))
        raise ValueError(f"Unknown preset '{preset_id}'. Choose one of: {valid}") from exc
