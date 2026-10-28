# sample-forge

Generates sound effects, foley and spoken voices with the ElevenLabs API and turns them into a **searchable sample library**, ready to drag into Ableton.

> **About AI assistance:** the code was written by Claude Code (an AI coding assistant) under my direction. I defined the problem and the design, and I test and review the result. I have not tried it against the real ElevenLabs API yet: the tests use a simulated API.

Problem it solves: a producer loses time hunting for foley and one-shots, and generation tools hand back a loose mp3 with no idea of what note it is, how long it is or what it cost.

## What it does

- **Generates** SFX/foley (`sound-generation`) and spoken voice (`text-to-speech`), with several takes per prompt.
- **Analyzes** every take: trims silence, normalizes to −1 dBFS, measures duration, peak and RMS, and **detects the note** (handy for dropping a spoken "ahh" into key).
- **Stores** everything in SQLite with full-text search: `search riser --note A --max-dur 3`.
- **Exports** 24-bit WAV files named like `Riser_A4_2.4s_ab12.wav`. Ableton does not read WAV tags, so the information goes in the filename.
- **Controls spending**: hash-based cache (the same request never calls the API twice), cost estimate before generating, a monthly credit cap, and backoff retries on `429`.
- **API + web** (FastAPI, a single HTML page) with a job queue and 2 workers.

## Usage

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
set ELEVEN_API_KEY=your_key              # the free plan is enough
```

```bash
python -m sample_forge gen sfx "heavy wooden door slam, big hall" -d 2 -n 3
python -m sample_forge gen vox "yeah!" --dry-run          # only estimates the cost
python -m sample_forge search door --max-dur 3
python -m sample_forge export "C:\Samples\forge" riser --note A
python -m sample_forge serve                              # web UI at http://127.0.0.1:8000
```

Optional environment variables: `SF_MONTHLY_CREDITS` (cap, 8000 by default), `SF_DATA` (data folder), `SF_VOICE` (default voice id), `SF_API_KEY` (if set, the API requires an `x-api-key` header).

## Design

```
cli / web ──► api.py (jobs, auth) ──► core.Forge ──► eleven.py   (HTTP + retries)
                                          │       └─► analyze.py (decode, trim, pitch)
                                          └────────► db.py       (SQLite + FTS5, credit ledger)
```

Decisions:

- **Hash cache** over `(kind, prompt, parameters, take number)`. Takes carry an index, so `-n 4` gives four different ones and repeating the command costs nothing.
- **No SDK, no librosa**: just `httpx` and `numpy`. Pitch detection is autocorrelation with parabolic interpolation and octave-error correction.
- **mp3 → WAV locally**: ElevenLabs' 44.1 kHz WAV/PCM output needs the Pro plan, while mp3 works on the free one.
- **The API validates everything at the edge** (pydantic), ids are checked with a regex before touching the disk, and search only accepts `\w` terms, so FTS syntax cannot leak in.

## Tests

```bash
.venv\Scripts\python -m pytest
```

Analysis is tested with synthetic tones of known frequency (a 440 Hz tone must come out as `A4`), and ElevenLabs is simulated: the tests spend no credits.

## Limits

- The credit costs in `core.py` are **estimates**; your ElevenLabs dashboard is the source of truth.
- Note detection works on tonal sounds; noise and percussion return `—`.
- Jobs live in memory: they are lost when the server restarts.
- No per-user authentication: meant for local use (it only listens on `127.0.0.1`).
- ElevenLabs' free plan requires attribution and is non-commercial.
