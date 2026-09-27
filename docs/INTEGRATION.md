# LumaStems Integration Contract

LumaStems is intended to be the shared separation engine for several clients. Clients should consume the manifest rather than infer stems from filenames.

## Service

Default local endpoint:

```text
http://127.0.0.1:8765
```

### Submit a local path

`POST /jobs/from-path`

```json
{
  "path": "/absolute/path/song.wav",
  "preset": "worship",
  "output_format": "WAV"
}
```

### Read job state

`GET /jobs/{job_id}`

Terminal states:

- `succeeded`
- `failed`

Jobs move through:

```text
queued -> running -> succeeded
                   -> failed
```

## Manifest schema v1

```json
{
  "schema_version": 1,
  "source": "/absolute/path/song.wav",
  "preset": "worship",
  "output_format": "WAV",
  "stems": [
    {
      "stem": "drums",
      "path": "/absolute/path/output/main/drums.wav",
      "model": "htdemucs_6s.yaml",
      "stage": "main"
    }
  ],
  "created_at": "2026-09-27T19:00:00+00:00"
}
```

Consumers should use `stem` as the canonical identity and `path` as the media location.

Do not depend on directory names, random run suffixes, or model filenames.

## Canonical v1 stem IDs

```text
vocals
drums
bass
guitar
piano
other
```

Quick mode exposes only:

```text
vocals
drums
bass
other
```

Future specialist passes may add IDs such as:

```text
lead_vocals
backing_vocals
kick
snare
toms
cymbals
synth
strings
organ
```

A new stem ID should only be published after the underlying stage is implemented and quality-checked.

## Ableton adapter behavior

The future Ableton adapter should:

1. submit the selected audio file path
2. poll the returned job
3. read `lumastems.json`
4. create one audio track per returned stem
5. preserve sample alignment at the source start time
6. name tracks from canonical stem IDs
7. group the generated tracks under `STEMS`
8. preserve the original mix as a disabled/reference track
9. never resubmit the same job because a UI button was tapped twice

The last point matters. Adapter requests should gain an idempotency key before we expose this as a one-click Live action.

## LumaStudio behavior

LumaStudio should use the same API and manifest. It should not ship its own copy of the model-selection logic.

That keeps model upgrades, naming, and specialist-stage behavior in one place.
