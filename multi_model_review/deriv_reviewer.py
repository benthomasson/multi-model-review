"""Model invocation and response parsing for derivation verification."""

import re

from . import DerivVerdict, DerivReviewResult
from .reviewer import run_model


def parse_deriv_review(model: str, response: str) -> DerivReviewResult:
    """Parse structured derivation review output into DerivReviewResult."""
    verdicts = []

    # Parse derivation blocks: ### deriv-id followed by VERDICT/CLASSIFICATION/CIRCULARITY/EQUATION/REASONING
    deriv_pattern = re.compile(
        r'###\s+(\S+)\s*\n'
        r'VERDICT:\s*(VALID|GAP|INVALID)\s*\n'
        r'CLASSIFICATION:\s*(DERIVED|MATCHED|INHERITED|PREDICTED|AXIOM)\s*\n'
        r'CIRCULARITY:\s*(NONE|SUSPECTED|CONFIRMED)\s*\n'
        r'EQUATION:\s*(.*?)\n'
        r'REASONING:\s*(.*?)(?=\n---|\n###|\n##|$)',
        re.DOTALL
    )

    for match in deriv_pattern.finditer(response):
        verdicts.append(DerivVerdict(
            deriv_id=match.group(1),
            equation=match.group(5).strip(),
            verdict=match.group(2).strip(),
            classification=match.group(3).strip(),
            circularity=match.group(4).strip(),
            reasoning=match.group(6).strip(),
        ))

    valid_count = sum(1 for v in verdicts if v.verdict == "VALID")
    gap_count = sum(1 for v in verdicts if v.verdict == "GAP")
    invalid_count = sum(1 for v in verdicts if v.verdict == "INVALID")

    return DerivReviewResult(
        model=model,
        verdicts=verdicts,
        raw_response=response,
        valid_count=valid_count,
        gap_count=gap_count,
        invalid_count=invalid_count,
    )


def review_derivations(model: str, prompt: str, timeout: int = 600) -> DerivReviewResult:
    """Run derivation verification for one model and parse the result."""
    response = run_model(model, prompt, timeout=timeout)
    return parse_deriv_review(model, response)
