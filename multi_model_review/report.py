"""Report formatting for multi-model peer review results."""

import json
from dataclasses import asdict

from . import AggregateResult, ReviewResult


def format_review(review: ReviewResult, verbose: bool = False) -> str:
    """Format a single model's review for human reading."""
    lines = []
    lines.append(f"=== {review.model.capitalize()} ===")
    lines.append(f"Claims found: {review.total}")
    lines.append(f"  PASS: {review.pass_count}  CONCERN: {review.concern_count}  BLOCK: {review.block_count}")
    lines.append("")

    # Show BLOCKs first, then CONCERNs
    for verdict_type in ["BLOCK", "CONCERN"]:
        for claim in review.claims:
            if claim.verdict == verdict_type:
                lines.append(f"  {claim.verdict:7s}  {claim.claim_id}")
                lines.append(f'           "{claim.claim_text}"')
                lines.append(f"           Reasoning: {claim.reasoning}")
                lines.append("")

    if verbose:
        # Show PASSes too
        for claim in review.claims:
            if claim.verdict == "PASS":
                lines.append(f"  PASS     {claim.claim_id}")
                lines.append(f'           "{claim.claim_text}"')
                lines.append("")

    return "\n".join(lines)


def format_disagreements(result: AggregateResult) -> str:
    """Format disagreements between models."""
    if not result.disagreements:
        return "No disagreements between models."

    lines = ["=== Disagreements ==="]
    for d in result.disagreements:
        lines.append(f"  claim: {d['claim_id']}")
        for model, verdict in d["verdicts"].items():
            reasoning = d.get("reasonings", {}).get(model, "")
            reason_str = f' "{reasoning}"' if reasoning else ""
            lines.append(f"    {model}: {verdict}{reason_str}")
        lines.append("")

    return "\n".join(lines)


def format_gate(result: AggregateResult) -> str:
    """Format the final gate verdict."""
    if result.gate == "PASS":
        return f"=== Gate: PASS (all models passed) ==="

    block_count = 0
    block_models = 0
    for review in result.reviews:
        if review.block_count > 0:
            block_count += review.block_count
            block_models += 1

    return f"=== Gate: BLOCK ({block_count} unresolved BLOCKs across {block_models} model(s)) ==="


def format_report(result: AggregateResult, verbose: bool = False) -> str:
    """Format the full human-readable report."""
    lines = []
    lines.append(f"Reviewing: {result.file_reviewed}")
    lines.append(f"Models: {', '.join(result.models)}")
    lines.append("")

    for review in result.reviews:
        lines.append(format_review(review, verbose=verbose))

    lines.append(format_disagreements(result))
    lines.append("")
    lines.append(format_gate(result))

    return "\n".join(lines)


def format_compare(result: AggregateResult) -> str:
    """Format a comparison-focused report highlighting disagreements."""
    lines = []
    lines.append(f"Comparing reviews: {result.file_reviewed}")
    lines.append(f"Models: {', '.join(result.models)}")
    lines.append("")

    if not result.disagreements:
        lines.append("All models agree on all claims.")
        lines.append("")
        lines.append(format_gate(result))
        return "\n".join(lines)

    lines.append(f"Found {len(result.disagreements)} disagreement(s):")
    lines.append("")
    lines.append(format_disagreements(result))
    lines.append("")

    # Show model summaries briefly
    for review in result.reviews:
        lines.append(f"  {review.model}: {review.pass_count}P / {review.concern_count}C / {review.block_count}B")

    lines.append("")
    lines.append(format_gate(result))

    return "\n".join(lines)


def format_json(result: AggregateResult) -> str:
    """Serialize AggregateResult as JSON."""
    return json.dumps(asdict(result), indent=2)
