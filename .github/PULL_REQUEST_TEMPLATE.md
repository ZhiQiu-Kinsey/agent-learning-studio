## What changes

<!-- The behavior change for learners or contributors. Link related issues. -->

## Verification

<!-- Commands you ran and their results, e.g.
- `uv run python -m unittest discover -s tests` — N tests OK
- `uv run python scripts/validate_lessons.py` — passed
- `npm --prefix frontend run test` — N passed
- `npx playwright test` (frontend/) — N passed
-->

### Offline vs real model

<!-- Keep these separate. Offline fixtures don't prove real-model behavior. -->

- Offline (deterministic fixtures, real Python tools):
- Real model: <!-- model, provider, samples/exercises, number of calls — or "not verified with a real model" -->

## Checklist

- [ ] Tests added or updated for changed behavior; existing tests pass.
- [ ] Red lines respected: run data only from real events, replay read-only, SDK data not labelled as raw HTTP, no secrets in code, logs or run records.
- [ ] Generated files regenerated where needed (`export_curriculum.py`, `export_trace_contract.py`, `export_content_schema.py` + `content:types`).
- [ ] Translations updated for both `zh-CN` and `en` (UI strings and course overlays), or stale entries noted below.
- [ ] Screenshots attached for UI changes.
- [ ] Reused third-party text or code is license-checked and recorded in `THIRD_PARTY_NOTICES.md`.
- [ ] New lessons stay `planned` until implementation, tests and teaching review are done.

## Screenshots

<!-- For UI changes: before/after, ideally in both languages. -->
