# Working in this repository

K-Writer exists so that AI models write Korean the way Korean people write. Models imitate the text they read: when the skill documents used "낱말" 107 times, articles written after reading them used it 29 times, against 0 in 600 human posts. Awkward Korean anywhere in this repo therefore lowers the plugin's quality directly. Keep all Korean here natural. Natural wording is not enough: a text also has to stay on its main point and say what the reader needs without skipping steps, so texts are planned top-down before they are written (`core/references/planning.md`).

This way of writing belongs to the plugin, not to one skill. A session-start hook (`hooks/`) adds the base method to every session that has the plugin, so answers, documents and commit messages written without a skill call follow it too, and every skill follows the same order in its own workflow. On 2026-11-27 the owner rejected a release that had added the design step to `write` and `techblog` only. When you change how K-Writer writes, change the base method (`hooks/writing-method.md`) and every skill together, and say so if a skill is left out.

## Writing Korean here (recursive dogfooding)

Any Korean you add or change, including README files, reference documents, rule hints, runtime messages, and commit messages, goes through the plugin's own process:

1. For a new document or a section you rewrite, plan before writing (`core/references/planning.md`): the main point of the document, what each unit (a paragraph or a section on one subtopic) tells the reader, and what each sentence tells. Leave out what does not serve the main point, even when it is true, and do not skip a reason, step, or value the reader needs.
2. Write under `core/references/style-guide.md`. Choose words by how human tech blogs name things: 출력한다 (not 낸다), 사용한다 (not 쓴다 for "use"), 수정한다 (not 고친다), 측정한다 (not 잰다), 제외한다 (not 뺀다), 삭제한다 (not 지운다), 추가한다 (not 더한다), 검출된 표현 (not 걸린 말), 섹션 (not 절 for a document section), 플러그인, 스킬.
3. Run the lint on the file and read every hit: `python skills/techblog/scripts/lint_ko.py <file> --tone default`. Run `python dev/sync_core.py` first if you changed `core/scripts/`. Reference documents use 해라체, so lint them with `--tone plain`. They are lists of rules and fail the distribution items (list share, ending share, three-item lists) by design; read the word-choice items (`A5.*`, `A6.*`, `A14.*`) and the 점검 후보 section, including the sentences without a link to the sentences before them (`A23.unlinked`).
4. Read every sentence with the questions in `core/references/korean-review.md` ("읽는 순서"). Check the structure as well as the wording: write down what each paragraph tells the reader, ask whether each sentence explains it or adds a reason, condition or example, and keep details in the section that covers them (types V and W). Ask whether each paragraph serves the main point of the document (type Z) and whether the reader has to fill in a reason or a step between two sentences (type Y). A short declarative sentence that only states a conclusion, category or count usually belongs merged into the sentence before or after it. Titles and headings end in a noun or a nominal form, never in a sentence ending such as "~합니다" or "~한다" (type X). For README files and other documents people read first, have a subagent that did not write the text read it with `core/references/independent-review.md` and report what it finds.
5. `tests/test_repo_language.py` and `PlainTermsDocsTest` in `tests/test_lint_ko.py` guard part of this. Passing them does not replace reading.

A word that the owner or a measurement rejects goes into the tables of `core/references/korean-review.md` and `core/references/ai-patterns.md`. Documents read before drafting (`hooks/writing-method.md`, `hooks/document-steps.md`, `style-guide.md`, `style-sources.md`, `planning.md`, `fact-sheet.md`, `skills/*/references/drafting.md`, `skills/*/references/genre.md`) show only the words to use, because a model that reads a bad form before writing tends to repeat it. They also hold only rules, reasons and examples: the record of the review or test run that led to a rule goes into `dev/style-guide-history.md`, `korean-review.md` ("유형을 추가한 경위") or `EVALUATION.md`.

## Keeping a run cheap

A skill run pays for every document it reads on every later turn, and for every pass that rereads the article. Keep both small when you change the workflow:

- Each step reads only the documents and sections it needs. `ai-patterns.md`, `korean-review.md` and `revision.md` are looked up by section when an item is flagged, never read whole during a run.
- Writing is planned top-down and checked bottom-up. The plan (`<name>.plan.md`: main point, units, one line per sentence) is checked once by `plan_ko.py` before drafting. While drafting, the writer checks each sentence as it is written and each unit once when its sentences are done. These checks look at text that has not been checked yet; they are not rereads.
- The whole article is checked twice: once by `check_ko.py`, which also compares the article with the plan, and once by one independent reviewer that only reports (`independent-review.md`). After that, only the changed sentences and three sentences around them are checked again (`check_ko.py` prints them). Do not add a step that rereads or relints text that already passed, and do not add a pass in which a model rereads the article against the plan: the script does that comparison, and the reviewer's one-line summary of each paragraph is compared with the plan without opening the article again.
- A new check goes into the scripts when a regex can find it, and into the reviewer's table in `independent-review.md` when it needs reading. Do not add another subagent pass.
- The base method (`hooks/writing-method.md`) is added to every session and every subagent of every user, including sessions that write no Korean. Keep it under 3,200 characters (`tests/test_hooks.py`; Codex also cuts hook output at about 2,500 tokens). It holds the order and the rules that change a text the most; details stay in `document-steps.md`, which a session prints only when it writes a document file, and in the skills' documents. Outside a skill run nothing is read as a file from the plugin folder, because a session has to ask before it reads outside its project: the steps are printed by `writing_method.py --document`, and the work files of a check go to a work folder (`check_ko.py --work`), not next to the user's document.

## Code comments

Comments and docstrings in code are in English. Korean stays in code only where it is data or is read by Korean readers: regexes, fixtures and sample sentences, words a comment discusses (in quotes), runtime messages of the skill scripts, and judge prompts.

## What not to rewrite

- `evals/*/results/` and `dev/dogfood/results/`: outputs recorded from past runs. `EVALUATION.md` cites them.
- `evals/*/article*.md`, `evals/*/source.md`, and Korean samples in `tests/`: fixtures, some awkward on purpose.
- Example rows in `ai-patterns.md` and `korean-review.md` that show the form to avoid.
- Numbers, dates, versions, and verdicts in `EVALUATION.md` and `dev/*/REPORT.md`. The writing may improve; the record does not change.

## Repository mechanics

- `core/` is the source of the shared documents and scripts. After editing it, run `python dev/sync_core.py`. Do not edit the copies under `skills/<name>/references/` and `skills/<name>/scripts/` that have a source in `core/`.
- `hooks/` is loaded by Claude Code and Codex from the plugin root (`hooks/hooks.json`). It is not copied into the skill folders, so a skill folder installed on its own does not get the base method. `writing_method.py --document` prints the plan format from `skills/write/references/planning.md`; keep the section name "설계 문서 형식" when you edit that document.
- Run `python -m unittest discover -s tests` before committing.
- `ARCHITECTURE.md` describes the structure and how to add a skill.
