"""Report formatting for derivation verification results."""

import json
from dataclasses import asdict

from . import DerivAggregateResult, DerivReviewResult


def format_deriv_report(result: DerivAggregateResult, verbose: bool = False) -> str:
    """Format derivation verification results for human reading."""
    lines = []
    lines.append(f"Derivation check: {result.file_reviewed}")
    lines.append(f"Models: {', '.join(result.models)}")
    lines.append("")

    if result.errors:
        lines.append("=== Model Errors ===")
        for model, error in result.errors.items():
            lines.append(f"  {model}: {error}")
        lines.append("")

    for review in result.reviews:
        lines.append(f"=== {review.model} ({len(review.verdicts)} derivations) ===")
        lines.append(f"  VALID: {review.valid_count}  GAP: {review.gap_count}  INVALID: {review.invalid_count}")

        # Classification breakdown
        class_counts: dict[str, int] = {}
        circ_count = 0
        for v in review.verdicts:
            class_counts[v.classification] = class_counts.get(v.classification, 0) + 1
            if v.circularity != "NONE":
                circ_count += 1
        class_parts = [f"{k}: {c}" for k, c in sorted(class_counts.items())]
        lines.append(f"  Classification: {', '.join(class_parts)}")
        if circ_count:
            lines.append(f"  Circularity issues: {circ_count}")
        lines.append("")

        # Show INVALID first, then GAP, then circularity, then VALID (verbose only)
        invalid = [v for v in review.verdicts if v.verdict == "INVALID"]
        gaps = [v for v in review.verdicts if v.verdict == "GAP"]
        circular = [v for v in review.verdicts
                    if v.circularity != "NONE" and v.verdict == "VALID"]
        clean = [v for v in review.verdicts
                 if v.verdict == "VALID" and v.circularity == "NONE"]

        if invalid:
            lines.append("  INVALID:")
            for v in invalid:
                _format_verdict(lines, v)

        if gaps:
            lines.append("  GAP:")
            for v in gaps:
                _format_verdict(lines, v)

        if circular:
            lines.append("  CIRCULARITY (verdict VALID but circular):")
            for v in circular:
                _format_verdict(lines, v)

        if clean and verbose:
            lines.append("  VALID:")
            for v in clean:
                _format_verdict(lines, v)
        elif clean:
            lines.append(f"  ({len(clean)} VALID derivation(s) — use -v to see details)")

        lines.append("")

    # Disagreements
    if result.disagreements:
        lines.append(f"=== Disagreements ({len(result.disagreements)}) ===")
        for d in result.disagreements:
            lines.append(f"  [{d['deriv_id']}] {d['axis']}")
            for model, val in d["verdicts"].items():
                lines.append(f"    {model}: {val}")
            lines.append("")

    return "\n".join(lines)


def _format_verdict(lines: list[str], v) -> None:
    """Append a single verdict block to the output lines."""
    lines.append(f"    [{v.deriv_id}] {v.verdict} / {v.classification} / circularity={v.circularity}")
    if v.equation:
        eq = v.equation[:120]
        if len(v.equation) > 120:
            eq += "..."
        lines.append(f"      eq: {eq}")
    if v.reasoning:
        short = v.reasoning[:200]
        if len(v.reasoning) > 200:
            short += "..."
        lines.append(f"      {short}")


def format_deriv_json(result: DerivAggregateResult) -> str:
    """Serialize DerivAggregateResult as JSON."""
    return json.dumps(asdict(result), indent=2)
