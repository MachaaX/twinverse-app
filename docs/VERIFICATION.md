# Verification record

Completed for the packaged source:

- Python source compilation.
- JavaScript syntax check with `node --check frontend/app.js`.
- **24 Python API integration tests**, all passed.
- **12 frontend render checks**, all passed.

The API tests cover eight-case loading and portrait availability, initial hidden-fact filtering, progressive disclosure, unsupported questions, a simple injection attempt, idempotent turn handling, deduplicated disclosures, encounter ownership, new-case publication, immutable active case versions, stable completed feedback, original rubric preservation, score totals and review triggers, N/A versus unreviewed, evidence validation, faculty-only scoring, source/attachment isolation, cross-origin rejection, path traversal rejection, invalid objective references, two configured paraphrases, negated-question handling, and student-safe export.

The frontend checks execute the view generators against real sample-derived fixtures. They cover the library, search, Studio, new/existing editors, encounter view, faculty/student report differences, official rubric display, all-N/A display, and HTML escaping.

**Verification limit:** no visual browser or end-to-end browser interaction test was available in the execution environment. Render checks do not verify pixel layout, browser event behavior, speech synthesis, or accessibility with assistive technology. Responsive layouts and keyboard behavior are implemented but still need a browser walkthrough on your machine before judging.

## Recommended five-minute browser smoke test

1. Start the application and verify the library shows eight portraits.
2. Open Omar, ask for cholesterol results, and confirm the chart updates.
3. Reload; confirm the same conversation remains.
4. Finish; open evidence; inspect the transcript.
5. Log in with a Faculty account, reopen the encounter from history, enter a rating and explanation, save, then reload.
6. Open Patient Studio, change a draft, save, approve, and publish.
7. Create a new patient and start it from the library.
8. Attach a small synthetic text record, republish, and verify request-based download.
9. Inspect the layout at a narrow phone width.
10. If using narration, enable Read replies and verify it reads the accepted response.

The application is a runnable local prototype, not a completed or clinically validated hackathon submission.
