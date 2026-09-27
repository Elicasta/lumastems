from __future__ import annotations

from .models import SeparationPreset, SeparationStage, StemSpec


def _stems(*pairs: tuple[str, str]) -> tuple[StemSpec, ...]:
    return tuple(StemSpec(source_label=source, output_name=output) for source, output in pairs)


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
        name="Band 6-Stem",
        description="Separates the main band parts used in rehearsal and live playback.",
        stages=(
            SeparationStage(
                id="main",
                model_filename="htdemucs_6s.yaml",
                description="Demucs 6-stem separation",
                stems=_stems(
                    ("Vocals", "vocals"),
                    ("Drums", "drums"),
                    ("Bass", "bass"),
                    ("Guitar", "guitar"),
                    ("Piano", "piano"),
                    ("Other", "other"),
                ),
            ),
        ),
        expected_stems=("vocals", "drums", "bass", "guitar", "piano", "other"),
    ),
    "worship": SeparationPreset(
        id="worship",
        name="Worship 6-Stem",
        description=(
            "Church-oriented six-stem split. v1 intentionally exposes only stems the "
            "selected model can actually separate. Specialist BGV, drum-piece, synth, "
            "strings, and keys stages can be added without changing the output contract."
        ),
        stages=(
            SeparationStage(
                id="main",
                model_filename="htdemucs_6s.yaml",
                description="Primary worship-band separation",
                stems=_stems(
                    ("Vocals", "vocals"),
                    ("Drums", "drums"),
                    ("Bass", "bass"),
                    ("Guitar", "guitar"),
                    ("Piano", "piano"),
                    ("Other", "other"),
                ),
            ),
        ),
        expected_stems=("vocals", "drums", "bass", "guitar", "piano", "other"),
    ),
}


def get_preset(preset_id: str) -> SeparationPreset:
    try:
        return PRESETS[preset_id]
    except KeyError as exc:
        valid = ", ".join(sorted(PRESETS))
        raise ValueError(f"Unknown preset '{preset_id}'. Choose one of: {valid}") from exc
