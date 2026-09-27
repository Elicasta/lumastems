from __future__ import annotations

from .models import SeparationPreset, SeparationStage, StageBackend, StemSpec


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
        name="Band 6-Stem",
        description="Separates the main band parts used in rehearsal and live playback.",
        stages=(
            SeparationStage(
                id="main",
                model_filename="htdemucs_6s.yaml",
                description="Demucs 6-stem separation",
                stems=BAND_STEMS,
            ),
        ),
        expected_stems=("vocals", "drums", "bass", "guitar", "piano", "other"),
    ),
    "worship": SeparationPreset(
        id="worship",
        name="Worship 6-Stem",
        description="Church-oriented six-stem split with dedicated guitar and piano stems.",
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
        name="Worship 7",
        description=(
            "Deep worship split: six-stem Demucs first, then a dedicated MVSep "
            "BS-RoFormer synth specialist on the residual Other stem."
        ),
        stages=(
            SeparationStage(
                id="main",
                model_filename="htdemucs_6s.yaml",
                description="Primary worship-band separation",
                stems=BAND_STEMS,
            ),
            SeparationStage(
                id="synth",
                backend=StageBackend.SYNTH_SPECIALIST,
                model_filename="bs_mega_53stem_synth_mvsep.ckpt",
                input_stem="other",
                description="Dedicated synth-vs-rest specialist",
                stems=_stems(
                    ("Synth", "synth"),
                    ("Other", "other"),
                ),
            ),
        ),
        expected_stems=("vocals", "drums", "bass", "guitar", "piano", "synth", "other"),
    ),
}


def get_preset(preset_id: str) -> SeparationPreset:
    try:
        return PRESETS[preset_id]
    except KeyError as exc:
        valid = ", ".join(sorted(PRESETS))
        raise ValueError(f"Unknown preset '{preset_id}'. Choose one of: {valid}") from exc
