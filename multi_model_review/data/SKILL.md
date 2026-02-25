# Multi-Model Review

Run multi-model peer review on a document before publication.

## Usage

```bash
# Review a paper draft with Claude and Gemini
multi-model-review review <file.md> --models claude,gemini

# Compare — focus on disagreements between models
multi-model-review compare <file.md>

# Gate check — binary pass/fail for scripting
multi-model-review gate <file.md>

# Include belief registry for richer review
multi-model-review review <file.md> --beliefs beliefs.md

# Include entry history for full chronological context
multi-model-review review <file.md> --entries entries/

# JSON output for programmatic use
multi-model-review review <file.md> --json
```

## What it does

Sends a document to multiple AI models via their CLI tools (`claude -p`, `gemini -p`), parses structured claim-by-claim verdicts, and aggregates results. Any BLOCK from any model blocks the gate. Disagreements between models are highlighted — these are where human attention should focus.

## Subcommands

- `review` — Full review with all claims and verdicts
- `compare` — Disagreement-focused output
- `gate` — Binary exit code (0=PASS, 1=BLOCK) for CI use
- `install-skill` — Install this skill file
