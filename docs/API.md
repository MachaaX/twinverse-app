# Local API contract

All mutation requests use `Content-Type: application/json`. The frontend and API share the same origin. Session identity is an HttpOnly cookie set by the server. The faculty role requires the shared demo password (default `twinverse-faculty`, override with `TWINVERSE_FACULTY_PASSWORD`); it is not per-user accounts.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Engine status and explicit `llm_connected: false` |
| GET / POST | `/api/session` | Get role / switch role. Faculty requires `{role: "faculty", password: "..."}` (403 if wrong, 429 after 5 failures); `{role: "student"}` signs out |
| GET | `/api/rubric` | Unchanged official rubric |
| GET | `/api/patients` | Safe patient cards; faculty also sees draft status |
| POST | `/api/patients` | Faculty creates `{profile: ...}` |
| GET / PUT | `/api/patients/{id}` | Faculty reads / saves a draft; version prevents stale writes |
| POST | `/api/validate` | Faculty validates `{profile: ...}` without saving |
| POST | `/api/patients/{id}/publish` | Publish after `{approved: true}` |
| POST | `/api/patients/{id}/attachments` | Faculty uploads a source or artifact |
| GET | `/api/attachments/{id}` | Faculty-only attachment download |
| GET / POST | `/api/encounters` | List visible encounters / start using `{patient_id: ...}` |
| GET | `/api/encounters/{id}` | Student-safe encounter snapshot |
| POST | `/api/encounters/{id}/turns` | `{text: ..., request_id: ...}`; request ID enables idempotency |
| POST | `/api/encounters/{id}/finish` | Finish and save initial observations, idempotently |
| POST | `/api/encounters/{id}/review` | Faculty saves ratings and optional `summary` feedback with optimistic review-version check |
| POST | `/api/encounters/{id}/release` | Faculty releases the saved review to the student `{reviewer, review_version}`; requires all seven domains rated or N/A |
| GET | `/api/encounters/{id}/artifacts/{artifact_id}` | Authorized released artifact download; logs open event |
| GET | `/api/encounters/{id}/export` | Student-safe JSON export, excluding unreleased case facts |
| GET | `/api/resources` | Faculty list of original source documents |
| GET | `/api/resources/{index}` | Faculty source download |

## Fact contract

```json
{
  "id": "f_access",
  "label": "Access to medication",
  "topic": "medication",
  "record": "Explicit faculty-authored case fact.",
  "patient_text": "Explicit faculty-approved patient wording.",
  "keywords": ["afford", "cost", "get your medicine"],
  "release": "question",
  "source": "Faculty-authored synthetic case"
}
```

Allowed release values are `initial`, `question`, and `faculty_only`. Missing clinical data is not converted into a negative finding. Matching is deterministic, phrase-based, and English-focused; it is not a semantic equivalence guarantee.

## Attachment contract

```json
{
  "name": "synthetic-record.txt",
  "content": "BASE64_BYTES",
  "kind": "artifact",
  "release": "question",
  "keywords": ["show records"]
}
```

`kind` is `artifact` or `source`. Only artifacts can reach students. Published cases pin an attachment ID list; later uploads require publication before new encounters include them. Uploads are forced to download rather than execute in the page.

## Faculty review contract

```json
{
  "reviewer": "Faculty reviewer",
  "review_version": 0,
  "ratings": [
    {
      "key": "opening_and_purpose",
      "score": 3,
      "review_note": "An explanation supported by the encounter.",
      "evidence_ids": ["t1"]
    }
  ]
}
```

Include exactly one entry for all seven official domain keys. `score` is an integer 1–4, `"N/A"`, or `null` for unreviewed. Every rated or N/A domain requires an explanation. Evidence IDs must exist in that encounter. An absent behavior may have no direct quotation; its explanation should identify the missing opportunity.

Changing a review increments `review_version`. Reusing a stale version returns 409. Numeric totals exclude N/A and unreviewed domains and report both counts. Review triggers for domains 6/7 are independent of the total.

## Automatic draft scoring and release

When an encounter finishes, `backend/scoring.py` scores it against `data/clinical_scoring_criteria.json` (universal communication criteria, generic vital-sign/NEWS2 rules, and per-patient clinical criteria; faculty-created patients use their learning checkpoints). Faculty receive, per domain, `suggested_score`, `suggested_note`, `suggested_evidence_ids` and the `criteria` checklist (met/missed with evidence turn IDs), plus `auto_score` (suggested total, unsafe-statement flags, vitals/NEWS2) and a pre-filled `summary`. Final `score` values stay `null` until faculty save them.

Optional `summary` on `/review`:

```json
{"comments": "Overall feedback.", "strengths": ["..."], "improvements": ["..."], "next_steps": ["..."]}
```

Students never receive auto-suggestions. Before release they get `status: "awaiting_release"` with checkpoints only. `/release` stores a student snapshot; later faculty edits stay hidden (`update_pending: true`) until released again.
