# Working in this repository

K-Writer exists so that AI models write Korean the way Korean people write. Models imitate the text they read: when the skill documents used "낱말" 107 times, articles written after reading them used it 29 times, against 0 in 600 human posts. Awkward Korean anywhere in this repo therefore lowers the plugin's quality directly. Keep all Korean here natural.

## Writing Korean here (recursive dogfooding)

Any Korean you add or change, including README files, reference documents, rule hints, runtime messages, and commit messages, goes through the plugin's own process:

1. Write under `core/references/style-guide.md`. Choose words by how human tech blogs name things: 출력한다 (not 낸다), 사용한다 (not 쓴다 for "use"), 수정한다 (not 고친다), 측정한다 (not 잰다), 제외한다 (not 뺀다), 삭제한다 (not 지운다), 추가한다 (not 더한다), 검출된 표현 (not 걸린 말), 섹션 (not 절 for a document section), 플러그인, 스킬.
2. Run the lint on the file and read every hit: `python skills/techblog/scripts/lint_ko.py <file> --tone default`. Run `python dev/sync_core.py` first if you changed `core/scripts/`. Reference documents use 해라체, so lint them with `--tone plain`. They are lists of rules and fail the distribution items (list share, ending share, three-item lists) by design; read the word-choice items (`A5.*`, `A6.*`, `A14.*`) and the 점검 후보 section.
3. Read every sentence with the questions in `core/references/korean-review.md`. For README files and other documents people read first, have a subagent that did not write the text do this and run the reader check in `core/references/reader-check.md`.
4. `tests/test_repo_language.py` and `PlainTermsDocsTest` in `tests/test_lint_ko.py` guard part of this. Passing them does not replace reading.

A word that the owner or a measurement rejects goes into the tables of `core/references/korean-review.md` and `core/references/ai-patterns.md`. Documents read before drafting (`style-guide.md`, `fact-sheet.md`, `skills/*/references/drafting.md`, `skills/*/references/genre.md`) show only the words to use, because a model that reads a bad form before writing tends to repeat it.

## Code comments

Comments and docstrings in code are in English. Korean stays in code only where it is data or is read by Korean readers: regexes, fixtures and sample sentences, words a comment discusses (in quotes), runtime messages of the skill scripts, and judge prompts.

## What not to rewrite

- `evals/*/results/`: outputs recorded from past runs. `EVALUATION.md` cites them.
- `evals/*/article*.md`, `evals/*/source.md`, and Korean samples in `tests/`: fixtures, some awkward on purpose.
- Example rows in `ai-patterns.md` and `korean-review.md` that show the form to avoid.
- Numbers, dates, versions, and verdicts in `EVALUATION.md` and `dev/*/REPORT.md`. The writing may improve; the record does not change.

## Repository mechanics

- `core/` is the source of the shared documents and scripts. After editing it, run `python dev/sync_core.py`. Do not edit the copies under `skills/<name>/references/` and `skills/<name>/scripts/` that have a source in `core/`.
- Run `python -m unittest discover -s tests` before committing.
- `ARCHITECTURE.md` describes the structure and how to add a skill.
