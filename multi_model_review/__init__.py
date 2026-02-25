"""Multi-model peer review gate for pre-publication quality checks."""

from dataclasses import dataclass, field


@dataclass
class ClaimVerdict:
    claim_id: str       # short identifier
    claim_text: str     # one-sentence statement
    verdict: str        # PASS, CONCERN, or BLOCK
    reasoning: str      # model's assessment


@dataclass
class ReviewResult:
    model: str          # "claude" or "gemini"
    gate: str           # overall PASS or BLOCK
    claims: list[ClaimVerdict] = field(default_factory=list)
    raw_response: str = ""
    total: int = 0
    pass_count: int = 0
    concern_count: int = 0
    block_count: int = 0


@dataclass
class AggregateResult:
    file_reviewed: str
    models: list[str] = field(default_factory=list)
    reviews: list[ReviewResult] = field(default_factory=list)
    gate: str = "PASS"  # PASS only if all models PASS
    disagreements: list[dict] = field(default_factory=list)
