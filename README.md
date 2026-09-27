# LumaStems

Local AI stem separation built for rehearsal, church playback, Ableton Live, and LumaStudio.

LumaStems wraps [python-audio-separator](https://github.com/nomadkaraoke/python-audio-separator) behind a stable Luma API so the separation engine is not tied to one DAW or UI.

## What v1 does

Three presets are available:

| Preset | Output |
| --- | --- |
| `quick` | vocals, drums, bass, other |
| `band` | vocals, drums, bass, guitar, piano, other |
| `worship` | vocals, drums, bass, guitar, piano, other |

`band` and `worship` currently use Demucs `htdemucs_6s.yaml`.

The worship preset intentionally does **not** rename residual audio as fake synth, strings, organ, or BGV stems. Those become specialist stages only when a model actually targets that source.

Every separation gets its own output directory and a `lumastems.json` manifest. That manifest is the contract Ableton and LumaStudio can consume later.

## Architecture

```text
Audio file
   |
   v
LumaStems Engine
   |
   +-- preset / model pipeline
   +-- model cache
   +-- stable output naming
   +-- JSON manifest
   |
   +--------------+----------------+
   |              |                |
   v              v                v
CLI          Local API       Future adapters
                              Ableton / LumaStudio
```

The local job queue uses one separation worker by default. That is intentional. Running several large separation models at once on one MPS/GPU device can make the workstation unstable without producing a useful throughput gain.

## macOS setup

Target: Apple Silicon, macOS Sonoma or newer.

### 1. Clone

```bash
git clone https://github.com/Elicasta/lumastems.git
cd lumastems
```

### 2. Bootstrap

```bash
bash scripts/bootstrap-macos.sh
source .venv/bin/activate
```

The bootstrap script:

- creates `.venv`
- installs FFmpeg with Homebrew if needed
- installs LumaStems
- installs `audio-separator[cpu]`, which uses MPS/CoreML where supported on Apple Silicon

### 3. Warm the model cache

```bash
lumastems warm --preset worship
```

Models are cached under:

```text
~/.lumastems/models
```

## Split a song

```bash
lumastems split "/path/to/song.wav" --preset worship
```

Choose an output directory:

```bash
lumastems split "/path/to/song.wav" \
  --preset band \
  --output "/path/to/Stems"
```

Machine-readable CLI output:

```bash
lumastems split "/path/to/song.wav" --preset band --json
```

## Local integration API

Start the service:

```bash
lumastems serve
```

Default address:

```text
http://127.0.0.1:8765
```

Keep it on localhost unless you intentionally add authentication and network hardening.

### Health

```bash
curl http://127.0.0.1:8765/health
```

### List presets

```bash
curl http://127.0.0.1:8765/presets
```

### Separate an existing local file

```bash
curl -X POST http://127.0.0.1:8765/jobs/from-path \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/Users/me/Music/song.wav",
    "preset": "worship",
    "output_format": "WAV"
  }'
```

The call returns a job ID immediately. Poll:

```bash
curl http://127.0.0.1:8765/jobs/JOB_ID
```

### Upload audio

```bash
curl -X POST http://127.0.0.1:8765/jobs/upload \
  -F "file=@/path/to/song.wav" \
  -F "preset=worship"
```

## Output contract

Example:

```text
outputs/
└── song-a1b2c3d4/
    ├── main/
    │   ├── vocals.wav
    │   ├── drums.wav
    │   ├── bass.wav
    │   ├── guitar.wav
    │   ├── piano.wav
    │   └── other.wav
    └── lumastems.json
```

`lumastems.json` records:

- original source
- preset
- output format
- canonical stem name
- file path
- model used
- pipeline stage

See [docs/INTEGRATION.md](docs/INTEGRATION.md).

## Next specialist passes

The pipeline schema already supports additional stages. The next useful targets are:

1. backing-vocal extraction using a dedicated BGV model such as `UVR-BVE-4B_SN-44100-2.pth`
2. drum-piece separation using `MDX23C-DrumSep-aufr33-jarredou.ckpt`
3. verified keyboard/synth/string models before exposing those names
4. Ableton adapter that creates aligned tracks from `lumastems.json`
5. LumaStudio adapter using the same manifest

The rule is simple: a stem name must represent a model that actually attempts to isolate that source.

## Development

Install:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run checks:

```bash
ruff check src tests
pytest
```

The unit tests use a fake separator, so CI validates LumaStems behavior without downloading multi-gigabyte AI models.

## License

MIT.
