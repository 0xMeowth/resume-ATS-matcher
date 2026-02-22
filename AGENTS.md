# AGENTS.md

Guidance for coding agents working in this repository.

## Project Snapshot

- Language: Python (`>=3.11,<3.13`)
- Package manager / runner: `uv`
- App entrypoint (current UI): `app.py` (Streamlit)
- Library code: `src/ats_matcher/`
- Current state: no formal `tests/` directory yet

## Repository Layout

- `app.py`: Streamlit orchestration/UI for the full workflow.
- `main.py`: tiny CLI stub that points to Streamlit usage.
- `src/ats_matcher/models.py`: dataclasses and shared domain models.
- `src/ats_matcher/*_engine.py`: matching/embedding/rewrite logic.
- `src/ats_matcher/*_parser.py`: resume and JD parsing logic.
- `src/ats_matcher/exporter.py`: applies accepted edits to DOCX output.
- `README.md`: quick-start and feature scope.

## Environment Setup Commands

- Install dependencies:
  - `uv sync`
- Install spaCy model (required):
  - `uv run python -m spacy download en_core_web_sm`
- Run app locally:
  - `uv run streamlit run app.py`
- Alternative message entrypoint:
  - `uv run python main.py`

## Build / Check / Test Commands

This repo currently has no committed test suite or lint config file.
Use commands below depending on what exists in your branch.

### Smoke checks (always valid)

- Python import smoke check:
  - `uv run python -c "import ats_matcher"`
- Syntax compile check:
  - `uv run python -m compileall src app.py main.py`

### Lint / format (if tools are available)

- Ruff lint all:
  - `uv run ruff check .`
- Ruff lint specific file:
  - `uv run ruff check src/ats_matcher/matching_engine.py`
- Ruff format all:
  - `uv run ruff format .`
- Ruff format specific file:
  - `uv run ruff format src/ats_matcher/jd_parser.py`

If `ruff` is not installed, add it as a dev dependency first:

- `uv add --dev ruff`

### Tests (current and future)

No tests are present today, but agents should use `pytest` conventions.

- Run all tests (when tests exist):
  - `uv run pytest`
- Run one test file:
  - `uv run pytest tests/test_matching_engine.py`
- Run one test function:
  - `uv run pytest tests/test_matching_engine.py::test_exact_match`
- Run tests by keyword:
  - `uv run pytest -k "skill and missing"`
- Stop on first failure:
  - `uv run pytest -x`

If `pytest` is not installed, add it as a dev dependency first:

- `uv add --dev pytest`

## Single-Test Workflow (Preferred)

When iterating on one behavior:

1. Run exactly one focused test:
   - `uv run pytest path/to/test_file.py::test_name`
2. Fix code.
3. Re-run the same single test.
4. Run nearby file/module tests.
5. Run full test suite before finalizing.

If no tests exist yet for the changed module, add a targeted test first.

## Code Style and Conventions

Follow existing patterns in `src/ats_matcher/`.

### Imports

- Use absolute imports from package root, e.g.:
  - `from ats_matcher.models import ResumeData`
- Group imports in this order:
  1. Standard library
  2. Third-party
  3. Local package imports
- Keep imports explicit; avoid wildcard imports.
- Prefer one import per line unless tightly related.

### Formatting

- Follow PEP 8 and keep line length reasonable (88-100 range).
- Use 4 spaces; no tabs.
- Keep functions small and focused.
- Prefer early returns for guard conditions.
- Avoid adding comments for obvious code.

### Types

- Type annotate all public function signatures.
- Keep `from __future__ import annotations` in Python modules.
- Use `dataclass` models for structured domain objects.
- Prefer concrete types (`list[str]` or `List[str]`) consistently per file.
- Avoid `Any` unless unavoidable.

### Naming

- Modules/functions/variables: `snake_case`.
- Classes/dataclasses: `PascalCase`.
- Constants: `UPPER_SNAKE_CASE`.
- Keep names domain-specific (`skill_matches`, `rewrite_suggestions`).

### Error Handling

- Validate inputs early and return safe defaults when practical.
- Raise clear exceptions at integration boundaries.
- Do not swallow exceptions silently.
- For network/file operations, fail with actionable messages.
- Preserve existing behavior unless task explicitly changes behavior.

### Data and State

- Keep business logic inside `src/ats_matcher/`, not UI glue.
- Maintain separation between parsing, matching, rewriting, exporting.
- Avoid hidden global state in core modules.
- In Streamlit code, keep session state keys stable and explicit.

## Change Scope Rules for Agents

- Do not change business logic unless explicitly asked.
- Prefer minimal diffs that solve the requested task.
- Avoid broad refactors in the same PR as feature/bug fixes.
- Do not introduce new heavy dependencies without clear need.
- Keep backward-compatible interfaces for existing call sites.

## Validation Checklist Before Finishing

- Run relevant checks/tests for touched files.
- If available, run full tests.
- Ensure app still launches:
  - `uv run streamlit run app.py`
- Update docs when behavior or commands change.

## Git and Safety Expectations

- Never commit secrets (`.env`, tokens, credentials files).
- Do not revert user-authored unrelated changes.
- Keep commits focused and descriptive.
- Do not use destructive git operations unless explicitly requested.

## Rules Files Status

Checked for additional agent instructions:

- `.cursorrules`: not found
- `.cursor/rules/`: not found
- `.github/copilot-instructions.md`: not found

If these files are added later, treat them as higher-priority constraints.
