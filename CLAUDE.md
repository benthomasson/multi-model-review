# multi-model-review

Multi-model peer review gate. Sends documents to multiple AI models (claude, gemini) via their CLIs, parses structured verdicts, and flags disagreements.

## Architecture

```
cli.py                  # Argument parsing, command dispatch
prompt.py               # Builds adversarial review prompt (claims -> PASS/CONCERN/BLOCK)
reviewer.py             # Invokes model CLIs (claude -p, gemini -p), parses claim verdicts
report.py               # Human-readable and JSON report formatting
refs.py                 # Extracts references + citation contexts from LaTeX/markdown
ref_prompt.py           # Per-reference verification prompt (EXISTS/ATTRIBUTION/SUPPORTS_CLAIMS)
ref_reviewer.py         # Runs per-reference verification across models
ref_report.py           # Reference check report formatting
fetcher.py              # Academic API clients (arXiv, Semantic Scholar, CrossRef) + local paper loading
__init__.py             # Dataclasses: Reference, ClaimVerdict, ReviewResult, AggregateResult, etc.
data/SKILL.md           # Claude Code skill definition (installed via install-skill)
```

## Commands

- `review` — Full claim-by-claim review. PASS/CONCERN/BLOCK per claim.
- `compare` — Same as review but focuses output on inter-model disagreements.
- `gate` — Binary PASS/BLOCK for CI. Exit code 0 = PASS, 1 = BLOCK.
- `check-refs` — Per-reference verification (exists? attribution correct? supports claims?).
  - `--fetch` — Fetch metadata from academic APIs before model verification.
  - `--papers-dir` — Directory of local PDFs/TXT/MD. Also downloads open-access papers there.
- `install-skill` — Install Claude Code skill to `.claude/skills/`.

## Key design decisions

**Model invocation via CLI**: Models are called through `claude -p` and `gemini -p` with prompts piped via stdin. No SDK dependency — just subprocess calls. Add new models by extending `MODEL_COMMANDS` in `reviewer.py`.

**Structured output parsing**: Models are prompted to produce a fixed format (VERDICT/CLAIM/REASONING blocks). Parsing is regex-based in `reviewer.py` and `ref_reviewer.py`. If parsing fails, defaults are conservative (BLOCK/UNCERTAIN).

**Reference fetching pipeline**: `fetcher.py` tries sources in order: cache -> local paper -> arXiv API -> Semantic Scholar -> CrossRef -> none. When `--papers-dir` is set, open-access PDFs are downloaded and their full text replaces API abstracts.

**No test suite**: The project has no tests directory. Test new functionality manually or add a `tests/` directory.

## Dependencies

- Python >= 3.10
- `pypdf` (required, for PDF text extraction)
- Model CLIs (`claude`, `gemini`) on PATH

## Install

```bash
pip install -e .
# or
uv tool install -e .
```

## Conventions

- Dataclasses live in `__init__.py`. Import them from the package root.
- Prompts live in `prompt.py` (review) and `ref_prompt.py` (references). Keep prompt text in module-level constants.
- Report formatting is separate from data collection (report.py / ref_report.py).
- All model calls go through `reviewer.run_model()` — never call subprocess directly elsewhere.
- Fetcher results are cached to `~/.cache/multi-model-review/refs/` as JSON files keyed by content hash.
