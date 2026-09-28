import pytest

from lumastems.presets import PRESETS, get_preset


def test_required_presets_exist():
    assert {"band", "worship7", "auto6", "auto7"} <= set(PRESETS)


@pytest.mark.parametrize(
    ("preset_id", "expected"),
    [
        ("band", ("vocals", "drums", "bass", "guitar", "piano", "other")),
        (
            "worship7",
            (
                "lead_vocals",
                "backing_vocals",
                "drums",
                "bass",
                "guitar",
                "piano",
                "other",
            ),
        ),
        ("auto6", ("vocals", "drums", "bass", "guitar", "piano", "other")),
        (
            "auto7",
            (
                "lead_vocals",
                "backing_vocals",
                "drums",
                "bass",
                "guitar",
                "piano",
                "other",
            ),
        ),
    ],
)
def test_expected_stems_are_stable(preset_id, expected):
    preset = get_preset(preset_id)
    assert preset.expected_stems == expected


def test_auto6_uses_existing_curated_models_automatically():
    preset = get_preset("auto6")

    assert [stage.id for stage in preset.stages] == [
        "vocal_ensemble",
        "rhythm",
        "band_detail",
    ]
    assert preset.stages[0].ensemble_preset == "vocal_balanced"
    assert preset.stages[1].model_filename == "htdemucs_ft.yaml"
    assert preset.stages[2].model_filename == "htdemucs_6s.yaml"
    assert preset.stages[1].separator_options["demucs_params"]["shifts"] == 4
    assert preset.stages[1].separator_options["demucs_params"]["overlap"] == 0.5


def test_auto7_adds_quality_vocal_specialist():
    preset = get_preset("auto7")
    specialist = preset.stages[-1]

    assert specialist.model_filename == "UVR-BVE-4B_SN-44100-2.pth"
    assert specialist.input_stem == "vocals"
    assert specialist.separator_options["vr_params"]["window_size"] == 320
    assert specialist.separator_options["vr_params"]["enable_tta"] is True
    assert [(stem.source_label, stem.output_name) for stem in specialist.stems] == [
        ("Instrumental", "lead_vocals"),
        ("Vocals", "backing_vocals"),
    ]


def test_stage_output_names_are_unique():
    for preset in PRESETS.values():
        for stage in preset.stages:
            names = [stem.output_name for stem in stage.stems]
            assert len(names) == len(set(names))


def test_unknown_preset_is_explicit():
    with pytest.raises(ValueError, match="Unknown preset"):
        get_preset("fake")
