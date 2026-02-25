"""Per-reference model invocation and response parsing."""

import re
import sys

from . import Reference, RefVerdict, RefReviewResult
from .reviewer import run_model
from .ref_prompt import build_ref_prompt


def parse_ref_response(ref_key: str, response: str) -> RefVerdict:
    """Parse a structured reference verification response into a RefVerdict."""
    exists = "UNCERTAIN"
    attribution = "PARTIAL"
    supports = "PARTIAL"
    reasoning = ""

    for line in response.splitlines():
        line = line.strip()
        if line.startswith("EXISTS:"):
            val = line.split(":", 1)[1].strip().upper()
            if val in ("YES", "NO", "UNCERTAIN"):
                exists = val
        elif line.startswith("ATTRIBUTION:"):
            val = line.split(":", 1)[1].strip().upper()
            if val in ("YES", "NO", "PARTIAL"):
                attribution = val
        elif line.startswith("SUPPORTS_CLAIMS:"):
            val = line.split(":", 1)[1].strip().upper()
            if val in ("YES", "NO", "PARTIAL"):
                supports = val
        elif line.startswith("REASONING:"):
            reasoning = line.split(":", 1)[1].strip()

    # If REASONING was multi-line, grab everything after the REASONING: line
    reasoning_match = re.search(r'REASONING:\s*(.*)', response, re.DOTALL)
    if reasoning_match:
        reasoning = reasoning_match.group(1).strip()

    return RefVerdict(
        ref_key=ref_key,
        exists=exists,
        attribution_correct=attribution,
        supports_claims=supports,
        reasoning=reasoning,
    )


def review_refs(model: str, refs: list[Reference],
                timeout: int = 120, quiet: bool = False) -> RefReviewResult:
    """Run per-reference verification for one model across all references."""
    result = RefReviewResult(model=model)

    for i, ref in enumerate(refs):
        if not quiet:
            print(f"  {model}: [{ref.key}] ({i+1}/{len(refs)})...", file=sys.stderr)

        prompt = build_ref_prompt(ref)
        try:
            response = run_model(model, prompt, timeout=timeout)
            result.raw_responses[ref.key] = response
            verdict = parse_ref_response(ref.key, response)
            result.verdicts.append(verdict)
        except Exception as e:
            if not quiet:
                print(f"    Error: {e}", file=sys.stderr)
            # Record a failed verdict
            result.raw_responses[ref.key] = f"ERROR: {e}"
            result.verdicts.append(RefVerdict(
                ref_key=ref.key,
                exists="UNCERTAIN",
                attribution_correct="PARTIAL",
                supports_claims="PARTIAL",
                reasoning=f"Model call failed: {e}",
            ))

    return result
