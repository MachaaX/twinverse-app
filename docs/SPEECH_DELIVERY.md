# Optional speech delivery coaching

In an encounter, select **Voice** and check **Record my speaking turns for delivery coaching** before speaking. Stop listening to end a turn; the browser also ends a turn when speech recognition finishes. Each clip is capped at 90 seconds. Longer encounters use multiple clips. Recording is off by default and resets for another encounter or account. Navigation, logout and recognition errors discard the current unsent clip and release the microphone.

## Video mode

Select **Video Mode** during an active encounter and allow camera and microphone
access in Chrome. A muted, mirrored camera preview appears at the upper right of
the patient animation frame. It is square with rounded corners and uses at most
1/16 (6.25%) of that frame's area, including after resizing.

Camera frames stay in a live browser preview: no video recording, snapshots,
uploads, storage, or visual analysis. The browser separates the microphone
tracks using [`getAudioTracks()`](https://developer.mozilla.org/en-US/docs/Web/API/MediaStream/getAudioTracks).
If the student checks the existing audio-coaching consent box, each speaking
turn records an audio-only clone as a PCM WAV through the same S3/PostgreSQL
pipeline and seven-day retention rules described below. The preview remains
active between turns; switching to Voice/Chat, leaving the encounter, finishing,
logging out, or closing the page stops its camera and microphone tracks. Reopening
an encounter requires selecting Video Mode again. Denied permission, missing
devices, or disconnection leave Voice and Chat modes available.

Video mode adds no emotion or empathy inference from voice or appearance. Audio
coaching uses the objective delivery measurements below; communication and empathy
feedback still comes from transcript evidence and faculty review.

The encounter and feedback pages show estimated words per minute, quiet gaps of at least 0.5 seconds, recording length, peak level/clipping and approximate microphone overlap with patient playback. Students can replay their recordings and delete them early. Faculty can review students' recordings but cannot delete or replace them. Audio results are available as personal coaching before official feedback is released.

These are measurements for reflection, not emotion, empathy or personality classifications. There are no audio-derived labels such as “rude” or “empathetic”, and no additional score. Existing transcript-based rubric suggestions and faculty review/release are unchanged. Pace uses browser-recognized words divided by an energy-based span; quiet gaps can include pauses, noise suppression or microphone artifacts. Playback overlap is browser timing, not proof of interruption. No normative pace or volume threshold is used to grade students.

## Storage and retention

- **AWS mode:** private WAV objects in the configured S3 bucket, under `<TWINVERSE_S3_PREFIX>/speech/<clip-id>.wav`. The existing bucket encryption settings apply; `TWINVERSE_S3_KMS_KEY_ID` is respected. No public ACL or public/presigned playback link is created. Audio is served through authenticated encounter endpoints.
- **PostgreSQL:** `public.twinverse_speech_clips` stores clip/encounter/turn/student identifiers, measurements, timestamps, object key and version ID. No raw audio or credentials are stored in this table.
- **SQLite:** `speech_jobs` is a durable upload/deletion outbox and metadata cache beside the existing encounter store. Transcript and encounter history continue to use the app's existing SQLite store. This feature does not migrate encounter history to PostgreSQL.
- **Staging:** raw clips temporarily live in `speech-audio/` beside `TWINVERSE_DB_PATH`, with private directory/file permissions. Successful AWS uploads remove the staging file. In local storage mode, this directory holds playback recordings instead of S3.
- **Retention:** playback is denied at seven days or immediately after an owner requests deletion. The app worker deletes raw local/S3 audio, including the specific S3 version where available. It preserves transcript/measurements. Remote cleanup retries with backoff; physical deletion requires the app to be running with valid AWS permissions. Expired credentials or downtime can delay cleanup. A failed upload never silently falls back from AWS to local mode.
- S3 version IDs are preserved, so early deletion removes the recorded object version rather than merely creating a delete marker. Conditional uploads prevent duplicate versions after an uncertain upload response. The app must be allowed to read and delete object versions if bucket versioning is enabled.

## AWS setup

Use the existing PostgreSQL and S3 environment variables; this feature needs no new service or model API key.

1. Install the existing `requirements-cloud.txt` dependencies.
2. Run `python -m backend.speech init-db` with the app's private environment loaded. It creates the new table/index without modifying patient or account tables. The database user needs permission to create these objects once and then select/insert/update rows.
3. Allow the app credentials `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` on the configured `speech/*` prefix. For a versioned bucket, also allow `s3:GetObjectVersion` and `s3:DeleteObjectVersion`. Optional KMS encryption needs the existing key permissions.
4. Run the app using `run.py`; it starts the upload/expiry worker. Restarting the app resumes jobs from the durable outbox. Keep the database and staging directory on persistent storage.
5. Serve the app over HTTPS (localhost is also supported). Use a browser with Web Speech recognition, microphone capture and AudioWorklet support. Permit microphone access when prompted. Existing browser speech recognition may use the browser vendor's service; no new transcription provider is introduced here.
6. Verify a synthetic speaking turn becomes **Measurements saved**, plays back only to its owner/faculty, and disappears from playback after **Delete recording**. An AWS failure appears in the panel and retries automatically.

For defense against a stopped app, an administrator can add a narrowly scoped S3 lifecycle rule for this `speech/` prefix, including noncurrent-version expiration if versioning is enabled. Preserve any existing lifecycle rules. S3 lifecycle deletion is asynchronous and does not replace the app's immediate playback cutoff.

## API

All routes require the existing authenticated account and encounter authorization. Mutations also require the session CSRF header.

| Route | Purpose |
| --- | --- |
| `GET /api/encounters/{id}/speech` | Authorized clip measurements/status and owner delete capability |
| `POST /api/encounters/{id}/speech` | Owner-only queue: JSON `turn_id`, `consent: true`, base64 PCM WAV `content`, optional integer `overlap_ms`; returns 202 |
| `GET /api/encounters/{id}/speech/{clip}/audio` | Private WAV playback; 410 when expired/deleted, 503 during a storage outage |
| `DELETE /api/encounters/{id}/speech/{clip}/audio` | Owner-only immediate playback revocation and queued deletion; measurements remain |

The server verifies mono 16-bit 16 kHz PCM WAV format, a 0.1–90 second duration, payload size, student-turn binding and overlap bounds. It recomputes measurements from the recording and checks SHA-256 integrity on playback. Repeating the same turn/recording is idempotent; replacing it with different audio is rejected.

## Verification

`python -m unittest discover -s tests -v` covers measurement bounds, consent, CSRF, student isolation, faculty read-only access, durable retries, uncertain PUT recovery, concurrent deletion, retention and unchanged rubric results. `node tests/test_frontend.cjs` includes PCM encoding, opt-in rendering and microphone cancellation checks.
