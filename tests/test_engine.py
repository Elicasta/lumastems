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

    def load_model(self, model):
        self.model = model

    def separate(self, source, custom_output_names=None):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        outputs = []
        for name in (custom_output_names or {}).values():
            path = self.output_dir / f"{name}.wav"
            path.write_bytes(b"RIFFfake")
            outputs.append(str(path))
        return outputs


class FakeSynthSpecialist:
    instances: ClassVar[list["FakeSynthSpecialist"]] = []

    def __init__(self, model_dir):
        self.model_dir = Path(model_dir)
        self.__class__.instances.append(self)

    def ensure_assets(self, progress=None):
        return ["fake-synth.ckpt", "fake-synth.yaml"]

    def separate(self, input_path, output_dir, progress=None):
        assert Path(input_path).name == "other.wav"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        synth = output_dir / "synth.wav"
        other = output_dir / "other.wav"
        synth.write_bytes(b"RIFFsynth")
        other.write_bytes(b"RIFFresidual")
        if progress:
            progress(1.0, "done")
        return {"synth": synth.resolve(), "other": other.resolve()}


@pytest.fixture(autouse=True)
def reset_fakes():
    FakeSeparator.instances = []
    FakeSynthSpecialist.instances = []


def make_audio(tmp_path: Path, name: str = "song.wav") -> Path:
    path = tmp_path / name
    path.write_bytes(b"RIFFsource")
    return path


def make_engine(tmp_path: Path, *, specialist: bool = False) -> LumaStemEngine:
    return LumaStemEngine(
        model_dir=tmp_path / "models",
        separator_factory=FakeSeparator,
        specialist_factory=FakeSynthSpecialist if specialist else None,
    )


def test_band_split_creates_stems_and_manifest(tmp_path):
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


def test_worship7_replaces_other_with_synth_specialist_residual(tmp_path):
    source = make_audio(tmp_path)
    engine = make_engine(tmp_path, specialist=True)

    result = engine.separate(
        source,
        preset_id="worship7",
        output_root=tmp_path / "out",
    )

    assert [stem.stem for stem in result.stems] == [
        "vocals",
        "drums",
        "bass",
        "guitar",
        "piano",
        "synth",
        "other",
    ]
    assert len([stem for stem in result.stems if stem.stem == "other"]) == 1
    assert next(stem for stem in result.stems if stem.stem == "synth").stage == "synth"
    assert next(stem for stem in result.stems if stem.stem == "other").stage == "synth"
    assert len(FakeSynthSpecialist.instances) == 1


def test_output_folder_is_unique_per_run(tmp_path):
    source = make_audio(tmp_path)
    engine = make_engine(tmp_path)

    first = engine.separate(source, preset_id="quick", output_root=tmp_path / "out")
    second = engine.separate(source, preset_id="quick", output_root=tmp_path / "out")

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
