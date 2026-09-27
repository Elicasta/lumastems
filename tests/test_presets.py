import pytest

from lumastems.models import StageBackend
from lumastems.presets import PRESETS, get_preset


def test_required_presets_exist():
    assert {"quick", "band", "worship", "worship7"} <= set(PRESETS)


@pytest.mark.parametrize(
    ("preset_id", "expected"),
    [
        ("quick", ("vocals", "drums", "bass", "other")),
        ("band", ("vocals", "drums", "bass", "guitar", "piano", "other")),
        ("worship", ("vocals", "drums", "bass", "guitar", "piano", "other")),
        ("worship7", ("vocals", "drums", "bass", "guitar", "piano", "synth", "other")),
    ],
)
def test_expected_stems_are_stable(preset_id, expected):
    preset = get_preset(preset_id)
    assert preset.expected_stems == expected


def test_worship7_uses_synth_specialist_on_other():
    preset = get_preset("worship7")
    assert len(preset.stages) == 2
    assert preset.stages[1].backend == StageBackend.SYNTH_SPECIALIST
    assert preset.stages[1].input_stem == "other"


def test_stage_output_names_are_unique():
    for preset in PRESETS.values():
        for stage in preset.stages:
            names = [stem.output_name for stem in stage.stems]
            assert len(names) == len(set(names))


def test_unknown_preset_is_explicit():
    with pytest.raises(ValueError, match="Unknown preset"):
        get_preset("fake")
