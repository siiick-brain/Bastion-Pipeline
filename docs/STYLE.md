# Writing style

This guide applies to every Markdown and text file in the repository. `scripts/check-style.ps1` enforces the punctuation rules before every commit and in CI.

## Principles

- Write direct technical English in the active voice.
- Define a term at its first use. Shared terms live in [the glossary](GLOSSARY.md).
- Keep paragraphs short. Use the present tense.
- State facts and measurements only. Avoid marketing language.
- Every result names its command, its date and its evidence artifact.
- Use one of these status words for every claim: PASS, FAIL, NOT VERIFIED, PLANNED, NOT APPLICABLE. Each is defined in [the glossary](GLOSSARY.md).

## Punctuation

- Do not use em dashes or en dashes. Use a period, a colon or parentheses.
- Do not use a double hyphen as a dash.
- Do not put a comma before "and". Write "a, b and c".
- Join two full clauses with a period or with "so". Never write `and,` to join them.
- Avoid a comma before "or".
- These rules do not apply to commands, code, quoted text or identifiers.

## Format

- Dates use ISO 8601: 2026-11-15.
- Headings use sentence case.
- Link text describes the target. Avoid "here" and "this link".
- Commit titles follow Conventional Commits, for example `fix(app): reject control characters`.

## Enforcement

- `scripts/check-style.ps1` checks tracked `.md` and `.txt` files. It skips code fences, inline code and table separator rows.
- `tests/style/check-style.tests.ps1` proves that a good fixture passes and a bad fixture fails each rule.
- Allowed exceptions live in `.style-allow` as `<path glob>|<rule id>|<reason>`. An entry without a reason is rejected.
- The `policy` job in `.github/workflows/ci.yml` runs the script on every pull request.
