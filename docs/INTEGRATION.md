# LumaStems Integration Contract

Clients should consume `lumastems.json` rather than infer stems from filenames.

## Stable presets

### Band 6

Canonical stem IDs:

```text
vocals
drums
bass
guitar
piano
other
```

### Worship Vocals 7

Canonical stem IDs:

```text
lead_vocals
backing_vocals
drums
bass
guitar
piano
other
```

The Worship Vocals pipeline first creates Band 6, then replaces the final manifest's `vocals` entry with `lead_vocals` and `backing_vocals`.

## Service

Default local endpoint:

```text
http://127.0.0.1:8765
```

Submit an existing local file:

`POST /jobs/from-path`

```json
{
  "path": "/absolute/path/song.wav",
  "preset": "worship7",
  "output_format": "WAV"
}
```

Read state:

`GET /jobs/{job_id}`

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
  "preset": "worship7",
  "output_format": "WAV",
  "stems": [
    {
      "stem": "lead_vocals",
      "path": "/absolute/path/output/vocals/lead_vocals.wav",
      "model": "UVR-BVE-4B_SN-44100-2.pth",
      "stage": "vocals"
    }
  ],
  "created_at": "2026-09-27T19:00:00+00:00"
}
```

Consumers should use `stem` as the canonical identity and `path` as the media location.

Do not depend on directory names, random run suffixes, or model filenames.

## Ableton adapter behavior

The future Ableton adapter should:

1. submit the selected audio file path
2. poll the returned job
3. read `lumastems.json`
4. create one audio track per returned stem
5. preserve sample alignment at the source start time
6. name tracks from canonical stem IDs
7. group generated tracks under `STEMS`
8. preserve the original mix as a disabled/reference track
9. never resubmit the same job because a UI button was tapped twice

The adapter should use an idempotency key before one-click creation is exposed.

## LumaStudio behavior

LumaStudio should use this same API and manifest rather than duplicate model-selection logic.
