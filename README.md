# TwinVerse sample prototype

A working local frontend and sample-backed backend for the Rutgers virtual patient encounter challenge. Includes the eight organizer-provided synthetic personas, patient portraits, original source materials, progressive disclosure, a faculty case editor, persistent encounters, and evidence-based rubric review.

**Start here:** install Python 3.10 or newer, open a terminal in this folder, and run:

```bash
python3 run.py
```

Open **http://127.0.0.1:8000** in your browser. Keep the terminal running. Stop with Ctrl+C.

On Windows:

```powershell
py -3 run.py
```

No API keys, npm install, database server, Python package installation, or internet connection is needed for the core application. Browser text-to-speech is optional and depends on the browser/platform; it is not ElevenLabs integration and may use platform services.

If the port is busy:

```bash
python3 run.py --port 8001
```

Open http://127.0.0.1:8001 instead. The included `start.command` and `start.bat` are convenience launchers. Running the explicit terminal command is the most portable option.

## What you can do

- Browse all eight supplied patients using the original portraits, with name search and case filters.
- Conduct a text interview in a split-screen encounter: conversation on the left, disclosed medical information on the right.
- Inspect the chart, available documents, and timestamped event history.
- Leave and resume an encounter from Encounter history; each accepted turn is saved.
- Finish an encounter and see case checkpoints, candidate communication evidence, the original seven-domain rubric, and the transcript.
- Switch to Faculty to create/edit cases, set fact-release rules, add learning checkpoints, attach files, validate structure, and publish.
- Run a newly published case through the same engine without code changes.
- Enter faculty ratings from 1–4 or N/A, explain each rating, link real turn IDs, and save a versioned review.
- Download authorized clinical artifacts and export student-safe encounter JSON.
- Review the original source materials from the Faculty workspace.

## Quick demonstration

1. Start the app and select **Omar Sinclair** from the Practice library.
2. Ask: `Hello, my name is Alex. I'm a student clinician. What brings you in today?`
3. Ask: `Could you tell me about your work and home life?`
4. Ask: `What are your cholesterol results?`
5. Observe the source lipid values appearing in the chart. The supplied CSV does not specify lipid units or collection dates; the app does not add them.
6. Ask: `How do you feel about taking medication?`
7. Ask: `Do you have a penicillin allergy?` The adapter reports that the detail is not provided, rather than inventing a negative history.
8. Finish the encounter. Inspect the checkpoint evidence and original transcript.
9. Switch the top-right role to **Faculty** and enter the faculty password (`twinverse-faculty` by default). The feedback page stays open. Select ratings, explain your reasoning, optionally enter supporting turn IDs such as `t1, t3`, and save the review.
10. Give domain 6 or 7 a rating of 1 with an explanation to demonstrate the official review-trigger behavior.

## Create a patient through the UI

1. Switch to Faculty and open **Patient Studio → Create patient**.
2. Enter the name, age, gender, case summary, background, and conversational style.
3. The initial presenting-case and background facts can use those fields if their fact text is left empty. Review the resulting text after saving. For additional facts, enter explicit record text and approved patient wording.
4. Choose each fact's release behavior:
   - At encounter start: visible in the baseline chart.
   - When asked: shown after an inquiry matching one of its trigger phrases.
   - Faculty only: never available to the patient response engine or student chart.
5. Add trigger phrases. This version matches configured phrases; it does not perform general semantic inference.
6. Add learning checkpoints referencing the fact IDs. Several fact IDs on one checkpoint require all those facts for a fully observed status.
7. Save the draft. Upload artifacts or knowledge sources if wanted.
8. Run **Check structure**, review the content, check the faculty approval box, and publish.
9. Go to Practice library and start the new patient.

Draft changes do not modify the last published version. Publish to make edits available to new encounters. Existing encounters always retain the profile, attachments, and rubric snapshots they started with.

## Automatic scoring and faculty release

1. When a student finishes, the app drafts a score from `data/clinical_scoring_criteria.json` (communication, vital-sign/NEWS2 and per-patient clinical criteria).
2. The student sees **Submitted for faculty review**, with no scores.
3. Faculty open the encounter from **Encounter history**. Each domain shows the suggested score, the criteria met and missed with transcript evidence, and a pre-filled rating and note. A **Feedback to the student** section pre-fills strengths, areas to improve and next steps.
4. Faculty change anything, then **Save review** (draft) or **Save & release to student**.
5. The student then sees the final score and the faculty feedback. Later edits stay hidden until released again.

The clinical criteria are a draft and need faculty validation before real grading.

## Attachment behavior

- Supported uploads: PDF, PNG, JPG/JPEG, TXT, MD, and JSON; up to 5 MB per file.
- Knowledge sources stay faculty-only. Files are stored but not OCR'd, embedded, interpreted, or used for automatic RAG in this version.
- Clinical artifacts can be available at start or released on a relevant question matching their configured phrases.
- Publish again after attaching a file. Active encounters do not gain newly uploaded artifacts retroactively.
- Student downloads require both encounter access and an artifact-release event.
- Opening a document is recorded separately from releasing it.
- Upload files that are consistent with the case. The structural validator does not inspect clinical content inside PDFs/images.

## Assessment and reproducibility

The supplied official JSON rubric replaces the earlier proposed generic 0–2 rubric. Its seven domains use **4 Strong, 3 Competent, 2 Developing, 1 Unsafe or absent, or N/A**.

The prototype deliberately separates three things:

1. **Case checkpoint observations:** deterministic detection of configured question-and-response disclosures. These are prototype-authored checkpoints, not organizer-certified competence measures.
2. **Communication evidence candidates:** transparent phrase patterns that point a reviewer to relevant transcript turns. Matching a phrase does not establish empathy, reasoning quality, or clinical safety. A missing match does not establish absence of the skill.
3. **Official rubric assessment:** a faculty reviewer enters and explains each 1–4 or N/A rating using the published descriptors and complete transcript. Ratings begin **unreviewed**, not automatically N/A or zero.

Totals are calculated by code from numeric ratings. With all seven domains scored, the maximum is 28. With N/A or unreviewed domains, the UI shows the available denominator and counts so a partial assessment is visible. An all-N/A assessment has no numeric total. Any score of 1 in clinical reasoning/synthesis or professionalism/safety/closure triggers review even when the total is high. No pass/fail conclusion is generated.

The completed assessment is saved and reused. Explicit faculty revisions create a new review version and preserve the previous report internally. Stored assessments include engine/rubric versions and a SHA-256 fingerprint over their case, rubric, transcript, and engine inputs. Scores and saved responses are deterministic; broad paraphrase equivalence is **not** guaranteed by this phrase-matching adapter.

### Where the planned hybrid LLM integration goes

- `backend/engine.py::reply(profile, text)` is the replaceable dialogue adapter. A future implementation should receive server-filtered eligible facts, return response text with fact IDs, and validate content before displaying or speaking it.
- `backend/engine.py::assess(encounter, rubric)` builds candidate evidence and the saved report. Add structured LLM evidence extraction here, preserving exact turn references and model/prompt versions.
- `backend/engine.py::apply_review(...)` owns rating validation and deterministic score calculation. Keep the rubric frozen and preserve faculty review for ambiguous judgments.
- The current app has **no LLM API integration, medical content model, ElevenLabs API integration, autonomous clinical evaluator, or semantic embeddings**. No placeholder API keys are silently used.

## Implementation

- Frontend: responsive HTML, CSS, and browser JavaScript modules. No build step or framework runtime is required.
- Backend: Python standard-library `ThreadingHTTPServer`, with centralized JSON routing and a small SQLite persistence layer.
- Database: `data/twinverse.sqlite3`, created on first launch. Do not commit this runtime file.
- Assets: optimized JPEG versions of the supplied patient portraits; original PNGs are retained under `samples/`.
- Request flow: question → configured intent phrases → permitted fact IDs → approved sample wording → event commit → student-safe response/chart patch.
- The frontend only consumes API responses; it does not contain the complete patient profiles.

The earlier build plan proposed React/FastAPI/PostgreSQL. This downloadable sample uses dependency-free browser code and a standard-library local server so you can run and inspect it immediately. The API boundary and profile/event contracts provide a migration path to that production-oriented stack. The local HTTP server is not a public deployment architecture.

## File map

```text
twinverse/
  run.py                       Local launcher
  start.command                macOS convenience launcher
  start.bat                    Windows convenience launcher
  frontend/
    index.html                 Application shell
    app.js                     Views, routing, API calls, UI events
    styles.css                 Responsive visual design
    assets/patients/            Eight optimized supplied portraits
  backend/
    server.py                  JSON routes, access checks, static serving
    store.py                   SQLite storage
    seed.py                    Source normalization and explicit demo facts
    engine.py                  Deterministic dialogue, evidence, scoring
  data/
    raw_patients.json          Normalized CSV data
    rubric.json                Original official rubric
  samples/                     Original documents, CSV, Box note, portraits
  tests/
    test_app.py                24 backend integration tests
    test_frontend.cjs          12 dependency-free frontend render checks
  docs/
    API.md                     Endpoint contract
    SOURCE_NOTES.md            Source interpretation and limitations
    VERIFICATION.md            Test scope and remaining verification
```

## Tests

Backend tests need only Python and use an isolated temporary SQLite database and a temporary loopback API test server:

```bash
python3 -m unittest discover -s tests -v
```

Optional frontend rendering checks require Node.js but no npm dependencies:

```bash
node tests/test_frontend.cjs
```

If the frontend test's Python executable differs, set `PYTHON` to it. These tests exercise generated HTML and escaping; they are not visual browser tests.

## Local-only boundaries

- The server binds to `127.0.0.1`, validates Host/Origin, serves only the frontend directory, and uses HttpOnly SameSite cookies.
- **Faculty sign-in:** switching to Faculty requires the shared demo password, `twinverse-faculty` by default (also printed in the terminal at startup). Change `DEFAULT_FACULTY_PASSWORD` in `backend/server.py`, or start with `TWINVERSE_FACULTY_PASSWORD="..." python3 run.py`. Five wrong attempts lock that browser out for 60 seconds, and restarting the server signs every browser out of the faculty view. Switching back to Student signs out.
- The default password is visible in this repository, so it only keeps casual users out of the faculty view during a demo. It is not per-user accounts. Add real authentication before any shared deployment.
- Browser sessions have separate encounter ownership; Faculty can inspect local encounters for review.
- Do not expose this server publicly or use real patient information. Add real authentication, authorization, TLS, secure deployment, upload scanning, retention policy, and proper operational controls before any real deployment.
- Browser narration reads the same approved reply text; it does not evaluate speech, accents, facial expressions, or emotion.
- The app does not certify HIPAA compliance, clinical validity, or student competence.

## Resetting local data

Stop the application first. Back up any encounters you want to retain. To intentionally reset the local demo, remove `data/twinverse.sqlite3` and restart. The eight seed patients will be loaded again. This removes locally authored cases, uploads, encounters, and reviews.

## Source rights

Original challenge materials and images are included as provided for the user's challenge work. Their original authors retain their rights; this package does not grant an additional redistribution license for them. See `docs/SOURCE_NOTES.md` for the exact sources and adaptations.

## Demo cases (static, deterministic)

Curated cases live in `data/cases/` and are installed automatically when the server starts (re-installed whenever `case_file_version` changes):

| Case | File | Role | Scripted run |
|---|---|---|---|
| Nisha Patel, 29 (newly diagnosed MS) | `data/cases/adult-nisha-patel.json` | Main demo (adult) | `docs/demo/demo-adult-nisha.md` |
| Yvette Armstrong, 64 (hypertension) | `data/cases/adult-yvette-armstrong.json` | Alternate adult case | `docs/demo/demo-adult-yvette.md` |
| Sofia Reyes, 9, with her mom (pediatric hearing loss) | `data/cases/child-sofia-reyes.json` | Backup demo (child) | `docs/demo/demo-child-sofia.md` |

Each case file holds the patient **profile** (facts, release rules, objectives, plus `reactions` — scripted, non-disclosing replies to explanations, summaries and teach-back), a **case rubric** (case-specific categories on top of the universal 7 domains; the child case adds the organizer's 100-point pediatric rubric), and a **demo script** of clinician lines.

`python3 tools/run_demo_script.py --all` runs every script through the real engine and scorer and regenerates the stage scripts in `docs/demo/` with exact replies, chart updates, and expected scores.

## Hugging Face clinician-behaviour reference

```bash
pip install datasets
python3 tools/hf_conversations.py          # -> data/hf/conversations.json
python3 tools/build_rubric_reference.py    # -> data/hf/rubric_reference.json
```

The reference scores every [Postzeun/Patient-Doctor](https://huggingface.co/datasets/Postzeun/Patient-Doctor) conversation with our universal criteria and records how often clinicians show each rubric behaviour, example clinician lines, and a benchmark score distribution. The dataset has no license or card on Hugging Face; treat it as reference material.
