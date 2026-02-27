"""CLI for multi-model peer review gate."""

import sys
import argparse
from datetime import datetime
from pathlib import Path

from . import AggregateResult, RefAggregateResult, DerivAggregateResult
from .prompt import build_prompt, load_document, load_beliefs, load_nogoods, load_entries
from .reviewer import check_model_available, review_file
from .report import format_report, format_compare, format_json, format_gate
from .refs import load_and_extract
from .ref_prompt import build_ref_prompt
from .ref_reviewer import review_refs
from .ref_report import format_ref_report, format_ref_json
from .fetcher import fetch_refs, DEFAULT_CACHE_DIR
from .deriv_prompt import build_deriv_prompt
from .deriv_reviewer import review_derivations
from .deriv_report import format_deriv_report, format_deriv_json


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


def save_results(result: AggregateResult, save_dir: Path, quiet: bool) -> Path:
    """Save raw responses and aggregate JSON to a timestamped directory."""
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    out = save_dir / ts
    out.mkdir(parents=True, exist_ok=True)

    for review in result.reviews:
        (out / f"{review.model}.raw.md").write_text(review.raw_response)

    (out / "aggregate.json").write_text(format_json(result))

    if not quiet:
        print(f"Saved to {out}/", file=sys.stderr)

    return out


def run_reviews(file_path: Path, models: list[str], prompt: str,
                timeout: int, quiet: bool) -> AggregateResult:
    """Run reviews sequentially across all models and aggregate."""
    reviews = []
    errors = {}
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
            errors[model] = str(e)

    result = aggregate_reviews(str(file_path), reviews)
    result.errors = errors
    return result


def maybe_save(result: AggregateResult, args, quiet: bool) -> None:
    """Save results if --save-dir was provided."""
    if getattr(args, "save_dir", None):
        save_results(result, args.save_dir, quiet)


def cmd_review(args):
    document = load_document(args.file)
    beliefs = load_beliefs(args.beliefs) if args.beliefs else None
    nogoods = load_nogoods(args.nogoods) if args.nogoods else None
    entries = load_entries(args.entries) if args.entries else None
    prompt = build_prompt(document, beliefs=beliefs, nogoods=nogoods, entries=entries)

    if args.save_prompt:
        args.save_prompt.write_text(prompt)
        print(f"Prompt saved to {args.save_prompt}", file=sys.stderr)
        sys.exit(0)

    models = parse_models(args.models)
    if not preflight_check(models, quiet=args.quiet):
        sys.exit(1)

    result = run_reviews(args.file, models, prompt, args.timeout, args.quiet)
    if not result.reviews:
        print("Error: all models failed — no reviews collected", file=sys.stderr)
        sys.exit(1)
    maybe_save(result, args, args.quiet)

    if args.json:
        print(format_json(result))
    else:
        print(format_report(result, verbose=args.verbose))

    sys.exit(2 if result.gate == "BLOCK" else 0)


def cmd_compare(args):
    document = load_document(args.file)
    beliefs = load_beliefs(args.beliefs) if args.beliefs else None
    nogoods = load_nogoods(args.nogoods) if args.nogoods else None
    entries = load_entries(args.entries) if args.entries else None
    prompt = build_prompt(document, beliefs=beliefs, nogoods=nogoods, entries=entries)

    if args.save_prompt:
        args.save_prompt.write_text(prompt)
        print(f"Prompt saved to {args.save_prompt}", file=sys.stderr)
        sys.exit(0)

    models = parse_models(args.models)
    if not preflight_check(models, quiet=args.quiet):
        sys.exit(1)

    result = run_reviews(args.file, models, prompt, args.timeout, args.quiet)
    if not result.reviews:
        print("Error: all models failed — no reviews collected", file=sys.stderr)
        sys.exit(1)
    maybe_save(result, args, args.quiet)

    if args.json:
        print(format_json(result))
    else:
        print(format_compare(result))

    sys.exit(2 if result.gate == "BLOCK" else 0)


def cmd_gate(args):
    document = load_document(args.file)
    beliefs = load_beliefs(args.beliefs) if args.beliefs else None
    nogoods = load_nogoods(args.nogoods) if args.nogoods else None
    entries = load_entries(args.entries) if args.entries else None
    prompt = build_prompt(document, beliefs=beliefs, nogoods=nogoods, entries=entries)

    if args.save_prompt:
        args.save_prompt.write_text(prompt)
        print(f"Prompt saved to {args.save_prompt}", file=sys.stderr)
        sys.exit(0)

    models = parse_models(args.models)
    if not preflight_check(models, quiet=True):
        # Print just the missing models for gate mode
        for model in models:
            if not check_model_available(model):
                print(f"missing: {model}", file=sys.stderr)
        sys.exit(1)

    result = run_reviews(args.file, models, prompt, args.timeout, quiet=True)
    if not result.reviews:
        print("Error: all models failed — no reviews collected", file=sys.stderr)
        sys.exit(1)
    maybe_save(result, args, True)
    print(format_gate(result))
    sys.exit(2 if result.gate == "BLOCK" else 0)


def aggregate_ref_reviews(file_path: str, refs, reviews: list) -> RefAggregateResult:
    """Aggregate per-reference reviews into a RefAggregateResult with disagreements."""
    result = RefAggregateResult(
        file_reviewed=file_path,
        models=[r.model for r in reviews],
        reviews=reviews,
        references=refs,
    )

    # Find disagreements: per ref_key, per axis, check if models differ
    axes = ["exists", "attribution_correct", "supports_claims"]
    # Build map: ref_key -> axis -> {model: value}
    ref_axes: dict[str, dict[str, dict[str, str]]] = {}
    for review in reviews:
        for v in review.verdicts:
            if v.ref_key not in ref_axes:
                ref_axes[v.ref_key] = {a: {} for a in axes}
            ref_axes[v.ref_key]["exists"][review.model] = v.exists
            ref_axes[v.ref_key]["attribution_correct"][review.model] = v.attribution_correct
            ref_axes[v.ref_key]["supports_claims"][review.model] = v.supports_claims

    for ref_key, axis_map in ref_axes.items():
        for axis, model_vals in axis_map.items():
            if len(set(model_vals.values())) > 1:
                result.disagreements.append({
                    "ref_key": ref_key,
                    "axis": axis,
                    "verdicts": dict(model_vals),
                })

    return result


def save_ref_results(result: RefAggregateResult, save_dir: Path, quiet: bool) -> Path:
    """Save per-model per-ref raw responses and aggregate JSON."""
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    out = save_dir / f"check-refs-{ts}"
    out.mkdir(parents=True, exist_ok=True)

    for review in result.reviews:
        model_dir = out / review.model
        model_dir.mkdir(exist_ok=True)
        for ref_key, raw in review.raw_responses.items():
            (model_dir / f"ref-{ref_key}.md").write_text(raw)

    (out / "aggregate.json").write_text(format_ref_json(result))

    if not quiet:
        print(f"Saved to {out}/", file=sys.stderr)

    return out


def cmd_check_refs(args):
    refs = load_and_extract(args.file)
    if not refs:
        print(f"No references found in {args.file}", file=sys.stderr)
        sys.exit(1)

    if not args.quiet:
        print(f"Found {len(refs)} references in {args.file}", file=sys.stderr)

    if getattr(args, "fetch", False):
        cache_dir = getattr(args, "cache_dir", None) or DEFAULT_CACHE_DIR
        papers_dir = getattr(args, "papers_dir", None)
        fetch_refs(refs, cache_dir=cache_dir, papers_dir=papers_dir, quiet=args.quiet)
        fetched = sum(1 for r in refs if r.fetched_content)
        if not args.quiet:
            print(f"Fetched metadata for {fetched}/{len(refs)} references", file=sys.stderr)

    if args.save_prompt:
        args.save_prompt.mkdir(parents=True, exist_ok=True)
        for ref in refs:
            prompt = build_ref_prompt(ref)
            (args.save_prompt / f"ref-{ref.key}.md").write_text(prompt)
        print(f"Saved {len(refs)} prompts to {args.save_prompt}/", file=sys.stderr)
        sys.exit(0)

    models = parse_models(args.models)
    if not preflight_check(models, quiet=args.quiet):
        sys.exit(1)

    reviews = []
    errors = {}
    for model in models:
        if not args.quiet:
            print(f"Sending to {model}...", file=sys.stderr)
        try:
            review = review_refs(model, refs, timeout=args.timeout, quiet=args.quiet)
            reviews.append(review)
        except Exception as e:
            print(f"Error from {model}: {e}", file=sys.stderr)
            errors[model] = str(e)

    if not reviews:
        print("Error: all models failed — no reviews collected", file=sys.stderr)
        sys.exit(1)

    result = aggregate_ref_reviews(str(args.file), refs, reviews)
    result.errors = errors

    if getattr(args, "save_dir", None):
        save_ref_results(result, args.save_dir, args.quiet)

    if args.json:
        print(format_ref_json(result))
    else:
        print(format_ref_report(result, verbose=args.verbose))


def aggregate_deriv_reviews(file_path: str, reviews: list) -> DerivAggregateResult:
    """Aggregate derivation reviews with per-axis disagreement detection."""
    result = DerivAggregateResult(
        file_reviewed=file_path,
        models=[r.model for r in reviews],
        reviews=reviews,
    )

    # Find disagreements: per deriv_id, per axis, check if models differ
    axes = ["verdict", "classification", "circularity"]
    # Build map: deriv_id -> axis -> {model: value}
    deriv_axes: dict[str, dict[str, dict[str, str]]] = {}
    for review in reviews:
        for v in review.verdicts:
            if v.deriv_id not in deriv_axes:
                deriv_axes[v.deriv_id] = {a: {} for a in axes}
            deriv_axes[v.deriv_id]["verdict"][review.model] = v.verdict
            deriv_axes[v.deriv_id]["classification"][review.model] = v.classification
            deriv_axes[v.deriv_id]["circularity"][review.model] = v.circularity

    for deriv_id, axis_map in deriv_axes.items():
        for axis, model_vals in axis_map.items():
            if len(set(model_vals.values())) > 1:
                result.disagreements.append({
                    "deriv_id": deriv_id,
                    "axis": axis,
                    "verdicts": dict(model_vals),
                })

    return result


def save_deriv_results(result: DerivAggregateResult, save_dir: Path, quiet: bool) -> Path:
    """Save per-model raw responses and aggregate JSON."""
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    out = save_dir / f"check-derivs-{ts}"
    out.mkdir(parents=True, exist_ok=True)

    for review in result.reviews:
        (out / f"{review.model}.raw.md").write_text(review.raw_response)

    (out / "aggregate.json").write_text(format_deriv_json(result))

    if not quiet:
        print(f"Saved to {out}/", file=sys.stderr)

    return out


def cmd_check_derivs(args):
    document = load_document(args.file)
    beliefs = load_beliefs(args.beliefs) if args.beliefs else None
    nogoods = load_nogoods(args.nogoods) if args.nogoods else None
    entries = load_entries(args.entries) if args.entries else None
    prompt = build_deriv_prompt(document, beliefs=beliefs, nogoods=nogoods, entries=entries)

    if args.save_prompt:
        args.save_prompt.write_text(prompt)
        print(f"Prompt saved to {args.save_prompt}", file=sys.stderr)
        sys.exit(0)

    models = parse_models(args.models)
    if not preflight_check(models, quiet=args.quiet):
        sys.exit(1)

    reviews = []
    errors = {}
    for model in models:
        if not args.quiet:
            print(f"Sending to {model}...", file=sys.stderr)
        try:
            review = review_derivations(model, prompt, timeout=args.timeout)
            reviews.append(review)
            if not args.quiet:
                print(f"  {model}: {review.valid_count}V / {review.gap_count}G / {review.invalid_count}I",
                      file=sys.stderr)
        except Exception as e:
            print(f"Error from {model}: {e}", file=sys.stderr)
            errors[model] = str(e)

    if not reviews:
        print("Error: all models failed — no reviews collected", file=sys.stderr)
        sys.exit(1)

    result = aggregate_deriv_reviews(str(args.file), reviews)
    result.errors = errors

    if getattr(args, "save_dir", None):
        save_deriv_results(result, args.save_dir, args.quiet)

    if args.json:
        print(format_deriv_json(result))
    else:
        print(format_deriv_report(result, verbose=args.verbose))


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
        p.add_argument("--nogoods", type=Path, default=None,
                       help="Path to nogoods file (nogoods.md) — known contradictions treated as ground truth")
        p.add_argument("--entries", type=Path, default=None,
                       help="Path to entries directory for chronological context")
        p.add_argument("--timeout", type=int, default=600,
                       help="Timeout per model in seconds (default: 600)")
        p.add_argument("--save-dir", type=Path, default=Path("reviews"),
                       help="Save raw responses and aggregate JSON to this directory (default: reviews/)")
        p.add_argument("--save-prompt", type=Path, default=None,
                       help="Save the review prompt to a file (or directory for check-refs) and exit")

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

    # check-refs
    refs_p = sub.add_parser("check-refs", help="Verify each reference independently")
    add_review_args(refs_p)
    refs_p.set_defaults(timeout=120)  # shorter per-ref timeout
    refs_p.add_argument("--json", action="store_true", help="Output as JSON")
    refs_p.add_argument("--verbose", "-v", action="store_true", help="Show passing refs too")
    refs_p.add_argument("--fetch", action="store_true",
                        help="Fetch paper metadata from academic APIs before verification")
    refs_p.add_argument("--cache-dir", type=Path, default=None,
                        help=f"Cache directory for fetched metadata (default: {DEFAULT_CACHE_DIR})")
    refs_p.add_argument("--papers-dir", type=Path, default=None,
                        help="Directory containing locally downloaded papers (PDF/TXT/MD)")

    # check-derivs
    derivs_p = sub.add_parser("check-derivs", help="Verify every derivation/equation in a paper")
    add_review_args(derivs_p)
    derivs_p.add_argument("--json", action="store_true", help="Output as JSON")
    derivs_p.add_argument("--verbose", "-v", action="store_true", help="Show VALID derivations too")

    # install-skill
    skill_p = sub.add_parser("install-skill", help="Install Claude Code skill")
    skill_p.add_argument("--skill-dir", type=Path, default=Path(".claude/skills"),
                         help="Target skills directory (default: .claude/skills)")

    args = parser.parse_args()

    commands = {
        "review": cmd_review,
        "compare": cmd_compare,
        "gate": cmd_gate,
        "check-refs": cmd_check_refs,
        "check-derivs": cmd_check_derivs,
        "install-skill": cmd_install_skill,
    }
    commands[args.command](args)
