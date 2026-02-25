"""CLI for multi-model peer review gate."""

import sys
import argparse
from pathlib import Path

from . import AggregateResult
from .prompt import build_prompt, load_document, load_beliefs, load_entries
from .reviewer import check_model_available, review_file
from .report import format_report, format_compare, format_json, format_gate


DEFAULT_MODELS = ["claude", "gemini"]


def parse_models(models_str: str) -> list[str]:
    """Parse comma-separated model list."""
    return [m.strip() for m in models_str.split(",") if m.strip()]


def aggregate_reviews(file_path: str, reviews: list) -> AggregateResult:
    """Aggregate individual reviews into an AggregateResult with disagreements."""
    result = AggregateResult(
        file_reviewed=file_path,
        models=[r.model for r in reviews],
        reviews=reviews,
    )

    # Gate: BLOCK if any model has BLOCKs
    result.gate = "PASS"
    for r in reviews:
        if r.gate == "BLOCK" or r.block_count > 0:
            result.gate = "BLOCK"
            break

    # Find disagreements: claims where models gave different verdicts
    # Build a map of claim_id -> {model: verdict}
    claim_verdicts: dict[str, dict[str, str]] = {}
    claim_reasonings: dict[str, dict[str, str]] = {}
    for review in reviews:
        for claim in review.claims:
            if claim.claim_id not in claim_verdicts:
                claim_verdicts[claim.claim_id] = {}
                claim_reasonings[claim.claim_id] = {}
            claim_verdicts[claim.claim_id][review.model] = claim.verdict
            claim_reasonings[claim.claim_id][review.model] = claim.reasoning

    for claim_id, verdicts in claim_verdicts.items():
        if len(set(verdicts.values())) > 1:
            result.disagreements.append({
                "claim_id": claim_id,
                "verdicts": verdicts,
                "reasonings": claim_reasonings.get(claim_id, {}),
            })

    return result


def preflight_check(models: list[str], quiet: bool = False) -> bool:
    """Check that all model CLIs are available. Returns True if all OK."""
    all_ok = True
    for model in models:
        if not check_model_available(model):
            if not quiet:
                print(f"Error: '{model}' CLI not found on PATH", file=sys.stderr)
            all_ok = False
    return all_ok


def run_reviews(file_path: Path, models: list[str], prompt: str,
                timeout: int, quiet: bool) -> AggregateResult:
    """Run reviews sequentially across all models and aggregate."""
    reviews = []
    for model in models:
        if not quiet:
            print(f"Sending to {model}...", file=sys.stderr)
        try:
            review = review_file(model, prompt, timeout=timeout)
            reviews.append(review)
            if not quiet:
                print(f"  {model}: {review.pass_count}P / {review.concern_count}C / {review.block_count}B",
                      file=sys.stderr)
        except Exception as e:
            print(f"Error from {model}: {e}", file=sys.stderr)
            # Continue with other models

    return aggregate_reviews(str(file_path), reviews)


def cmd_review(args):
    models = parse_models(args.models)
    if not preflight_check(models, quiet=args.quiet):
        sys.exit(1)

    document = load_document(args.file)
    beliefs = load_beliefs(args.beliefs) if args.beliefs else None
    entries = load_entries(args.entries) if args.entries else None
    prompt = build_prompt(document, beliefs=beliefs, entries=entries)

    result = run_reviews(args.file, models, prompt, args.timeout, args.quiet)

    if args.json:
        print(format_json(result))
    else:
        print(format_report(result, verbose=args.verbose))

    sys.exit(1 if result.gate == "BLOCK" else 0)


def cmd_compare(args):
    models = parse_models(args.models)
    if not preflight_check(models, quiet=args.quiet):
        sys.exit(1)

    document = load_document(args.file)
    beliefs = load_beliefs(args.beliefs) if args.beliefs else None
    entries = load_entries(args.entries) if args.entries else None
    prompt = build_prompt(document, beliefs=beliefs, entries=entries)

    result = run_reviews(args.file, models, prompt, args.timeout, args.quiet)

    if args.json:
        print(format_json(result))
    else:
        print(format_compare(result))

    sys.exit(1 if result.gate == "BLOCK" else 0)


def cmd_gate(args):
    models = parse_models(args.models)
    if not preflight_check(models, quiet=True):
        # Print just the missing models for gate mode
        for model in models:
            if not check_model_available(model):
                print(f"missing: {model}", file=sys.stderr)
        sys.exit(1)

    document = load_document(args.file)
    beliefs = load_beliefs(args.beliefs) if args.beliefs else None
    entries = load_entries(args.entries) if args.entries else None
    prompt = build_prompt(document, beliefs=beliefs, entries=entries)

    result = run_reviews(args.file, models, prompt, args.timeout, quiet=True)
    print(format_gate(result))
    sys.exit(1 if result.gate == "BLOCK" else 0)


def cmd_install_skill(args):
    import shutil
    skill_source = Path(__file__).parent / "data" / "SKILL.md"
    if not skill_source.exists():
        print("Error: SKILL.md not found in package data", file=sys.stderr)
        sys.exit(1)

    target_dir = args.skill_dir / "multi-model-review"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "SKILL.md"

    shutil.copy2(skill_source, target)
    if not args.quiet:
        print(f"Installed {target}")


def main():
    parser = argparse.ArgumentParser(
        prog="multi-model-review",
        description="Multi-model peer review gate for pre-publication quality checks",
    )
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress progress output")

    sub = parser.add_subparsers(dest="command", required=True)

    # Shared arguments for review commands
    def add_review_args(p):
        p.add_argument("file", type=Path, help="Markdown file to review")
        p.add_argument("--models", default="claude,gemini",
                       help="Comma-separated model list (default: claude,gemini)")
        p.add_argument("--beliefs", type=Path, default=None,
                       help="Path to belief registry (beliefs.md)")
        p.add_argument("--entries", type=Path, default=None,
                       help="Path to entries directory for chronological context")
        p.add_argument("--timeout", type=int, default=600,
                       help="Timeout per model in seconds (default: 600)")

    # review
    review_p = sub.add_parser("review", help="Send file to all models for review")
    add_review_args(review_p)
    review_p.add_argument("--json", action="store_true", help="Output as JSON")
    review_p.add_argument("--verbose", "-v", action="store_true", help="Show PASS claims too")

    # compare
    compare_p = sub.add_parser("compare", help="Review and highlight disagreements between models")
    add_review_args(compare_p)
    compare_p.add_argument("--json", action="store_true", help="Output as JSON")

    # gate
    gate_p = sub.add_parser("gate", help="Binary pass/fail gate check (for scripting/CI)")
    add_review_args(gate_p)

    # install-skill
    skill_p = sub.add_parser("install-skill", help="Install Claude Code skill")
    skill_p.add_argument("--skill-dir", type=Path, default=Path(".claude/skills"),
                         help="Target skills directory (default: .claude/skills)")

    args = parser.parse_args()

    commands = {
        "review": cmd_review,
        "compare": cmd_compare,
        "gate": cmd_gate,
        "install-skill": cmd_install_skill,
    }
    commands[args.command](args)
