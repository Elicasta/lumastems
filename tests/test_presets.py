import pytest

from lumastems.presets import PRESETS, get_preset


def test_required_presets_exist():
    assert {"quick", "band", "worship"} <= set(PRESETS)


@pytest.mark.parametrize(
    ("preset_id", "expected"),
    [
        ("quick", ("vocals", "drums", "bass", "other")),
        ("band", ("vocals", "drums", "bass", "guitar", "piano", "other")),
        ("worship", ("vocals", "drums", "bass", "guitar", "piano", "other")),
    ],
)
def test_expected_stems_are_stable(preset_id, expected):
    preset = get_preset(preset_id)
    assert preset.expected_stems == expected


def test_stage_output_names_are_unique():
    for preset in PRESETS.values():
        for stage in preset.stages:
            names = [stem.output_name for stem in stage.stems]
            assert len(names) == len(set(names))


def test_unknown_preset_is_explicit():
    with pytest.raises(ValueError, match="Unknown preset"):
        get_preset("fake")
