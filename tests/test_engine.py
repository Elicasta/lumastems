import json
from pathlib import Path
from typing import ClassVar

import pytest

from lumastems.engine import LumaStemEngine, SeparationError


class FakeSeparator:
    instances: ClassVar[list["FakeSeparator"]] = []

    def __init__(self, **kwargs):
        self.output_dir = Path(kwargs.get("output_dir", "."))
        self.model_file_dir = Path(kwargs.get("model_file_dir", "."))
        self.model = None
        self.kwargs = kwargs
        self.__class__.instances.append(self)

    def load_model(self, model=None):
        self.model = model or f"ensemble:{self.kwargs.get('ensemble_preset')}"

    def separate(self, source, custom_output_names=None):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        outputs = []
        for name in (custom_output_names or {}).values():
            path = self.output_dir / f"{name}.wav"
            path.write_bytes(b"RIFFfake")
            outputs.append(str(path))
        return outputs


@pytest.fixture(autouse=True)
def reset_fake():
    FakeSeparator.instances = []


def make_audio(tmp_path: Path, name: str = "song.wav") -> Path:
    path = tmp_path / name
    path.write_bytes(b"RIFFsource")
    return path


def make_engine(tmp_path: Path) -> LumaStemEngine:
    return LumaStemEngine(
        model_dir=tmp_path / "models",
        separator_factory=FakeSeparator,
    )


def test_band_split_creates_six_stems_and_manifest(tmp_path):
    source = make_audio(tmp_path)
    engine = make_engine(tmp_path)

    result = engine.separate(
        source,
        preset_id="band",
        output_root=tmp_path / "out",
    )

    assert [stem.stem for stem in result.stems] == [
        "vocals",
        "drums",
        "bass",
        "guitar",
        "piano",
        "other",
    ]
    assert result.manifest_path.exists()

    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["schema_version"] == 1
    assert manifest["preset"] == "band"
    assert len(manifest["stems"]) == 6
    assert all(Path(item["path"]).exists() for item in manifest["stems"])

    assert len(FakeSeparator.instances) == 1
    assert FakeSeparator.instances[0].model == "htdemucs_6s.yaml"


def test_worship7_replaces_full_vocals_with_lead_and_backing(tmp_path):
    source = make_audio(tmp_path)
    engine = make_engine(tmp_path)

    result = engine.separate(
        source,
        preset_id="worship7",
        output_root=tmp_path / "out",
    )

    assert [stem.stem for stem in result.stems] == [
        "lead_vocals",
        "backing_vocals",
        "drums",
        "bass",
        "guitar",
        "piano",
        "other",
    ]

    assert len(FakeSeparator.instances) == 2
    assert FakeSeparator.instances[0].model == "htdemucs_6s.yaml"
    assert FakeSeparator.instances[1].model == "UVR-BVE-4B_SN-44100-2.pth"

    # The specialist receives the first pass vocal stem, not the full mix.
    assert Path(FakeSeparator.instances[1].kwargs["output_dir"]).name == "vocals"
    assert all(stem.stem != "vocals" for stem in result.stems)


def test_warm_worship7_loads_both_real_model_names(tmp_path):
    engine = make_engine(tmp_path)

    warmed = engine.warm_preset("worship7")

    assert warmed == [
        "htdemucs_6s.yaml",
        "UVR-BVE-4B_SN-44100-2.pth",
    ]


def test_auto6_combines_existing_models_without_manual_tuning(tmp_path):
    source = make_audio(tmp_path)
    engine = make_engine(tmp_path)

    result = engine.separate(source, preset_id="auto6", output_root=tmp_path / "out")

    assert [stem.stem for stem in result.stems] == [
        "vocals",
        "drums",
        "bass",
        "guitar",
        "piano",
        "other",
    ]
    assert len(FakeSeparator.instances) == 3
    assert FakeSeparator.instances[0].kwargs["ensemble_preset"] == "vocal_balanced"
    assert FakeSeparator.instances[1].model == "htdemucs_ft.yaml"
    assert FakeSeparator.instances[2].model == "htdemucs_6s.yaml"


def test_output_folder_is_unique_per_run(tmp_path):
    source = make_audio(tmp_path)
    engine = make_engine(tmp_path)

    first = engine.separate(source, preset_id="band", output_root=tmp_path / "out")
    second = engine.separate(source, preset_id="band", output_root=tmp_path / "out")

    assert first.output_dir != second.output_dir


def test_missing_source_fails_before_model_load(tmp_path):
    engine = make_engine(tmp_path)

    with pytest.raises(FileNotFoundError):
        engine.separate(tmp_path / "missing.wav")

    assert FakeSeparator.instances == []


def test_unsupported_extension_is_rejected(tmp_path):
    source = tmp_path / "song.txt"
    source.write_text("not audio")
    engine = make_engine(tmp_path)

    with pytest.raises(SeparationError, match="Unsupported audio format"):
        engine.separate(source)
