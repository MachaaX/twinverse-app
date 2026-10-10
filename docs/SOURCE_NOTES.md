# Sources and adaptations

The supplied archive contained:

- `faculty-provided-sample-patient-details.csv`: eight personas with UUIDs, names, ages, backgrounds, notes, image references, personality descriptions, ethnicity, and summaries.
- `SHP_C1_Virtual_Patient_Encounter_System_Overview.pdf`: challenge specification.
- `evaluation rubrics/encounter_evaluation_rubric.json`: the seven-domain official 1–4/N/A rubric used in the application, unchanged.
- `evaluation rubrics/Patient Encounter Performance Rubric.pdf`: the corresponding reference document.
- `evaluation rubrics/Rubric for Pediatric Treatment.docx`: a separate pediatric hearing-treatment rubric; included as a reference, not applied to these adult cases.
- `sample courses/SYLLABUS MLSC 4329 Hematology II Fall 2026.pdf`: included as course context; not a patient-specific clinical source.
- `sample patient profiles for student interaction/Sample Patient Profile dataset.boxnote`: contains links to external datasets. The linked datasets were not downloaded or silently combined with the eight supplied profiles.
- Eight patient portraits, including Dominic Rivera's uppercase `.PNG` filename.
- A nested `patient-images.zip` containing the same eight images plus macOS metadata. The duplicate nested archive and macOS metadata are omitted; all eight original portraits are preserved in `samples/`.

## Explicit adaptations

- `data/raw_patients.json` normalizes the CSV's surrounding extra quote characters. The original CSV is retained unchanged.
- `backend/seed.py` defines explicit demo fact records and paraphrased patient utterances based on the supplied fields. These utterances are adaptations, not quoted real encounters.
- Per-fact trigger phrases and learning checkpoints are prototype-authored demonstration rules. They were not supplied or separately approved by the organizers.
- Seed cases are available immediately for demo convenience. The UI labels their origin; this is not evidence of independent clinical validation or faculty sign-off on our mappings.
- The CSV uses **Vladko Bareche** while the source image filename says **Vadko Bareche**. The application uses the CSV name and maps the provided image by explicit association.
- Marcus's summary says **Heart Failure NYHA Stage C**. This terminology is preserved in the source summary and flagged for faculty review rather than silently corrected.
- Lipid units and sample collection dates are absent for Wyatt and Omar. No units, dates, medications, allergies, doses, or diagnostic images are invented.
- Walter's source note uses “Noncompliant with diet.” Adapted patient wording describes difficulty following the diet without introducing a new diagnosis.
- Ethnicity remains in the original/normalized source data. It is not used to infer behaviors, disease, personality, accent, or grading.
- Original S3 image references are not requested. The application serves included local portraits instead.

## Limits of the sample adapter

- Returns fixed, approved sample phrases for matching topics. It does not synthesize fluent new clinical responses or interpret arbitrary language.
- Unrecognized questions return an explicit not-provided response. Known facts may be missed when the question uses unconfigured wording.
- The input filter and topic matcher are simple demonstration rules, not an adversarially complete security system.
- Structural case checks do not establish clinical consistency inside attached documents or nuanced case content. Faculty review remains necessary.
- The official rubric is unchanged. Scores are manually entered by faculty; automated markers merely point to transcript evidence. No claim of reliable autonomous clinical grading is made.
