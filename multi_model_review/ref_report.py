"""Report formatting for reference check results."""

import json
from dataclasses import asdict

from . import RefAggregateResult, RefVerdict


def _verdict_ok(v: RefVerdict) -> bool:
    """Check if a verdict has no issues."""
    return (v.exists == "YES"
            and v.attribution_correct == "YES"
            and v.supports_claims == "YES")


def format_ref_report(result: RefAggregateResult, verbose: bool = False) -> str:
    """Format reference check results for human reading."""
    lines = []
    lines.append(f"Reference check: {result.file_reviewed}")
    lines.append(f"Models: {', '.join(result.models)}")
    lines.append(f"References found: {len(result.references)}")
    lines.append("")

    # Check if any refs have fetched content
    any_fetched = any(ref.fetched_content for ref in result.references)

    # Group verdicts by ref_key across all reviews
    ok_count = 0
    for ref in result.references:
        verdicts_for_ref = []
        for review in result.reviews:
            for v in review.verdicts:
                if v.ref_key == ref.key:
                    verdicts_for_ref.append((review.model, v))

        all_ok = all(_verdict_ok(v) for _, v in verdicts_for_ref)
        fetch_tag = ""
        if any_fetched:
            fetch_tag = " (fetched)" if ref.fetched_content else " (memory)"
        if all_ok:
            ok_count += 1
            if verbose:
                lines.append(f"  [{ref.key}]{fetch_tag}")
                for model, v in verdicts_for_ref:
                    lines.append(f"    {model}: OK")
                lines.append("")
            continue

        # Show refs with issues
        lines.append(f"  [{ref.key}]{fetch_tag}")
        for model, v in verdicts_for_ref:
            if _verdict_ok(v):
                lines.append(f"    {model}: OK")
            else:
                issues = []
                if v.exists != "YES":
                    issues.append(f"exists={v.exists}")
                if v.attribution_correct != "YES":
                    issues.append(f"attribution={v.attribution_correct}")
                if v.supports_claims != "YES":
                    issues.append(f"supports={v.supports_claims}")
                lines.append(f"    {model}: {', '.join(issues)}")
                if v.reasoning:
                    # Show first ~200 chars of reasoning, indented
                    short = v.reasoning[:200]
                    if len(v.reasoning) > 200:
                        short += "..."
                    lines.append(f"      {short}")
        lines.append("")

    if ok_count > 0 and not verbose:
        lines.append(f"({ok_count} reference(s) passed all checks — use -v to see details)")
        lines.append("")

    # Disagreements
    if result.disagreements:
        lines.append(f"=== Disagreements ({len(result.disagreements)}) ===")
        for d in result.disagreements:
            lines.append(f"  [{d['ref_key']}] {d['axis']}")
            for model, val in d["verdicts"].items():
                lines.append(f"    {model}: {val}")
            lines.append("")

    return "\n".join(lines)


def format_ref_json(result: RefAggregateResult) -> str:
    """Serialize RefAggregateResult as JSON."""
    return json.dumps(asdict(result), indent=2)
