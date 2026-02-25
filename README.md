# multi-model-review

Multi-model peer review gate for pre-publication quality checks.

Sends a document to multiple AI models (via their CLI tools) for adversarial review, parses structured verdicts, and reports disagreements. Any BLOCK from any model blocks the gate.

## Usage

```bash
# Full review
multi-model-review review paper.md --models claude,gemini

# Focus on disagreements
multi-model-review compare paper.md

# Binary gate for CI/scripting (exit 0 = PASS, exit 1 = BLOCK)
multi-model-review gate paper.md

# With belief registry and entry history
multi-model-review review paper.md --beliefs beliefs.md --entries entries/

# JSON output
multi-model-review review paper.md --json
```

## Install

```bash
uv tool install -e .
```

## How it works

1. Constructs an adversarial review prompt with the document
2. Sends to each model via CLI (`claude -p`, `gemini -p`)
3. Parses structured claim-by-claim verdicts (PASS/CONCERN/BLOCK)
4. Aggregates: any BLOCK from any model = gate BLOCK
5. Highlights disagreements — where human attention should focus
