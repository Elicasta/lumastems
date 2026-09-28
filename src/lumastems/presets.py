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

QUALITY_DEMUCS = {
    "demucs_params": {
        "segment_size": "Default",
        "shifts": 4,
        "overlap": 0.5,
        "segments_enabled": True,
    },
    "use_soundfile": True,
}

QUALITY_VR = {
    "vr_params": {
        "batch_size": 1,
        "window_size": 320,
        "aggression": 5,
        "enable_tta": True,
        "enable_post_process": False,
        "post_process_threshold": 0.2,
        "high_end_process": False,
    },
    "use_soundfile": True,
}

AUTO_CORE_STAGES = (
    SeparationStage(
        id="vocal_ensemble",
        ensemble_preset="vocal_balanced",
        description="Curated two-model vocal ensemble",
        stems=_stems(
            ("Vocals", "vocals"),
            ("Instrumental", "instrumental"),
        ),
        separator_options={"use_soundfile": True},
    ),
    SeparationStage(
        id="rhythm",
        model_filename="htdemucs_ft.yaml",
        input_stem="instrumental",
        description="Higher-SDR rhythm split from the clean instrumental",
        stems=_stems(
            ("Drums", "drums"),
            ("Bass", "bass"),
        ),
        separator_options=QUALITY_DEMUCS,
    ),
    SeparationStage(
        id="band_detail",
        model_filename="htdemucs_6s.yaml",
        input_stem="instrumental",
        description="Guitar, piano, and residual band detail",
        stems=_stems(
            ("Guitar", "guitar"),
            ("Piano", "piano"),
            ("Other", "other"),
        ),
        separator_options=QUALITY_DEMUCS,
    ),
)

PRESETS: dict[str, SeparationPreset] = {
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
    "worship7": SeparationPreset(
        id="worship7",
        name="Worship Vocals 7",
        description="Stable Band 6 plus lead/backing vocal separation.",
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
                separator_options=QUALITY_VR,
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
    "auto6": SeparationPreset(
        id="auto6",
        name="Auto Quality 6",
        description=(
            "Automatic quality pipeline using the built-in vocal ensemble plus "
            "higher-quality Demucs rhythm and band-detail passes."
        ),
        stages=AUTO_CORE_STAGES,
        expected_stems=("vocals", "drums", "bass", "guitar", "piano", "other"),
    ),
    "auto7": SeparationPreset(
        id="auto7",
        name="Auto Worship 7",
        description=(
            "Auto Quality 6 followed by the backing-vocal specialist with "
            "quality VR settings."
        ),
        stages=AUTO_CORE_STAGES
        + (
            SeparationStage(
                id="vocals_split",
                model_filename="UVR-BVE-4B_SN-44100-2.pth",
                input_stem="vocals",
                description="Lead-vocal and BGV specialist",
                stems=_stems(
                    ("Instrumental", "lead_vocals"),
                    ("Vocals", "backing_vocals"),
                ),
                separator_options=QUALITY_VR,
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
