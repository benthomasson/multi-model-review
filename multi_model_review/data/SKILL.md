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

# Verify every derivation/equation in a paper
multi-model-review check-derivs <file.md>

# Check derivations with belief context
multi-model-review check-derivs <file.md> --beliefs beliefs.md --entries entries/

# Review a long paper section-by-section (avoids timeouts on large documents)
multi-model-review review <file.md> --by-section

# Section-by-section with a single model
multi-model-review review <file.md> --by-section --models gemini

# Save per-section prompts to inspect before running
multi-model-review review <file.md> --by-section --save-prompt /tmp/sections/
```

## Exit codes

- `0` — review complete, gate PASS
- `1` — error (missing model CLI, file not found, no references found)
- `2` — review complete, gate BLOCK (models found issues — read the output)

**Exit code 2 is not an error.** It means the review ran successfully and the models found issues that need attention. Read stdout for the full report.

## What it does

Sends a document to multiple AI models via their CLI tools (`claude -p`, `gemini -p`), parses structured claim-by-claim verdicts, and aggregates results. Any BLOCK from any model blocks the gate. Disagreements between models are highlighted — these are where human attention should focus.

## Subcommands

- `review` — Full review with all claims and verdicts
- `compare` — Disagreement-focused output
- `gate` — Binary exit code (0=PASS, 2=BLOCK) for CI use
- `check-derivs` — Verify every derivation/equation (validity, classification, circularity)
- `install-skill` — Install this skill file
