import pytest

from lumastems.presets import PRESETS, get_preset


def test_required_presets_exist():
    assert {"quick", "band", "worship", "worship7"} <= set(PRESETS)


@pytest.mark.parametrize(
    ("preset_id", "expected"),
    [
        ("quick", ("vocals", "drums", "bass", "other")),
        ("band", ("vocals", "drums", "bass", "guitar", "piano", "other")),
        ("worship", ("vocals", "drums", "bass", "guitar", "piano", "other")),
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
    ],
)
def test_expected_stems_are_stable(preset_id, expected):
    preset = get_preset(preset_id)
    assert preset.expected_stems == expected


def test_worship7_splits_the_isolated_vocal_stem():
    preset = get_preset("worship7")

    assert len(preset.stages) == 2
    specialist = preset.stages[1]

    assert specialist.model_filename == "UVR-BVE-4B_SN-44100-2.pth"
    assert specialist.input_stem == "vocals"
    assert [stem.output_name for stem in specialist.stems] == [
        "lead_vocals",
        "backing_vocals",
    ]


def test_stage_output_names_are_unique():
    for preset in PRESETS.values():
        for stage in preset.stages:
            names = [stem.output_name for stem in stage.stems]
            assert len(names) == len(set(names))


def test_unknown_preset_is_explicit():
    with pytest.raises(ValueError, match="Unknown preset"):
        get_preset("fake")
