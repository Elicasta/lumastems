# LumaStems

Local AI stem separation for rehearsal, church playback, Ableton Live, and LumaStudio.

LumaStems wraps [python-audio-separator](https://github.com/nomadkaraoke/python-audio-separator) behind a stable local engine and manifest contract.

## 0.3.0 direction

The desktop app intentionally focuses on two reliable workflows:

| Preset | Output |
| --- | --- |
| `Band 6` | vocals, drums, bass, guitar, piano, other |
| `Worship Vocals 7` | lead vocals, backing vocals, drums, bass, guitar, piano, other |

`Band 6` uses Demucs `htdemucs_6s.yaml`.

`Worship Vocals 7` first creates the same six stems, then sends only the isolated vocal stem through `UVR-BVE-4B_SN-44100-2.pth` to separate lead vocals from backing vocals / choir.

The experimental synth specialist has been removed from the shipping app. It was not stable enough to justify keeping it in the production path.

Every run gets its own output directory and a `lumastems.json` manifest.

## Architecture

```text
Stereo master
   |
   v
Band 6 / htdemucs_6s
   |
   +-- Vocals
   +-- Drums
   +-- Bass
   +-- Guitar
   +-- Piano
   +-- Other
   |
   +-- optional Worship Vocals pass
          |
          +-- Lead Vocals
          +-- Backing Vocals
```

The full `vocals` stem is replaced by `lead_vocals` and `backing_vocals` in the Worship Vocals manifest so consumers do not double-count vocal audio.

## macOS app

Target: Apple Silicon.

The app manages its own:

- Python 3.12 runtime
- FFmpeg binary
- `audio-separator` dependencies
- model cache
- output folders

No Homebrew setup is required for the packaged app.

Models live in the LumaStems Application Support directory and are reused between runs.

## CLI

For development or automation:

```bash
lumastems split "/path/to/song.wav" --preset band
```

Worship vocals:

```bash
lumastems split "/path/to/song.wav" --preset worship7
```

Machine-readable output:

```bash
lumastems split "/path/to/song.wav" --preset worship7 --json
```

## Output examples

Band 6:

```text
song/
├── main/
│   ├── vocals.wav
│   ├── drums.wav
│   ├── bass.wav
│   ├── guitar.wav
│   ├── piano.wav
│   └── other.wav
└── lumastems.json
```

Worship Vocals 7:

```text
song/
├── main/
│   ├── vocals.wav
│   ├── drums.wav
│   ├── bass.wav
│   ├── guitar.wav
│   ├── piano.wav
│   └── other.wav
├── vocals/
│   ├── lead_vocals.wav
│   └── backing_vocals.wav
└── lumastems.json
```

The intermediate full vocal file may remain on disk for diagnosis, but the manifest exposes the final seven canonical stems.

## Local integration API

Start:

```bash
lumastems serve
```

Default:

```text
http://127.0.0.1:8765
```

See [docs/INTEGRATION.md](docs/INTEGRATION.md) for the manifest and future Ableton/LumaStudio adapter contract.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

ruff check src tests
pytest
```

Unit tests use fake separators. The macOS release workflow also runs the real backing-vocal model before publishing the DMG.

## License

MIT.
