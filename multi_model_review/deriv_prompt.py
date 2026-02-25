"""Prompt construction for derivation verification."""

from pathlib import Path


DERIV_PROMPT = """\
You are auditing every derivation and equation in a research paper. Your job is to find errors, circular reasoning, and misclassified results — not to encourage.

For each equation or derivation step in the paper:

1. **Classify** the result:
   - DERIVED — follows from the paper's stated axioms/assumptions through explicit steps
   - MATCHED — reproduces a known result but the derivation has gaps or unstated assumptions
   - INHERITED — standard textbook result repackaged in the paper's notation (not a new result)
   - PREDICTED — a genuinely novel prediction that differs from established theory
   - AXIOM — stated as an assumption or starting point, not derived

2. **Assess validity**:
   - VALID — all steps are explicit and logically complete
   - GAP — the conclusion may be correct but steps are missing, hand-waved, or under-justified
   - INVALID — contains a mathematical error, unjustified leap, or contradicts other results in the paper

3. **Check for circularity** — this is critical:
   - NONE — no circular reasoning detected
   - SUSPECTED — the derivation may be reverse-engineered from the known answer (e.g., inserting a known solution's structure and calling it a derivation)
   - CONFIRMED — the derivation demonstrably assumes what it claims to prove

   Common circularity patterns to watch for:
   - A "verification test" that compares a function to itself or its own derivative
   - Inserting the known answer's functional form and then "deriving" parameters to match
   - Using a result from general relativity as an intermediate step while claiming to derive GR from first principles
   - Algebraically identical computations presented as independent confirmations
   - Precision in numerical results that masks the absence of an independent derivation

Do not be diplomatic. Do not hedge. If a derivation is circular, say so directly.

Output your analysis in this exact format:

## Derivations

### deriv-short-id
VERDICT: VALID|GAP|INVALID
CLASSIFICATION: DERIVED|MATCHED|INHERITED|PREDICTED|AXIOM
CIRCULARITY: NONE|SUSPECTED|CONFIRMED
EQUATION: the equation or key step
REASONING: detailed assessment
---

(Repeat for every derivation/equation found.)

## Summary
TOTAL: N
VALID: N
GAP: N
INVALID: N
DERIVED: N
MATCHED: N
INHERITED: N
PREDICTED: N
AXIOM: N
CIRCULARITY_ISSUES: N
"""


def build_deriv_prompt(document: str,
                       beliefs: str | None = None,
                       entries: list[str] | None = None) -> str:
    """Build the full derivation verification prompt with document and optional context."""
    parts = [DERIV_PROMPT]

    parts.append("## Document Under Review\n")
    parts.append(document)

    if beliefs:
        parts.append("\n## Belief Registry\n")
        parts.append("The following belief registry shows claim status (IN/OUT/STALE) "
                      "and known contradictions. Pay special attention to derivations "
                      "that support OUT or STALE beliefs — these may indicate circular "
                      "reasoning or invalidated steps.\n")
        parts.append(beliefs)

    if entries:
        parts.append("\n## Recent Entries (Chronological Context)\n")
        parts.append("These entries show the research trail. Use them to detect "
                      "derivations that were later found to be circular, results "
                      "that were reclassified, or steps that were patched without "
                      "fixing the underlying gap.\n")
        for entry in entries:
            parts.append(entry)
            parts.append("\n---\n")

    return "\n".join(parts)
