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


@dataclass
class Reference:
    key: str               # "Kesten1959" or "1"
    entry_text: str        # Full bibliography entry
    contexts: list[str] = field(default_factory=list)  # Paragraphs citing this reference
    fetched_content: str = ""  # Retrieved paper metadata+abstract (from fetcher)


@dataclass
class RefVerdict:
    ref_key: str
    exists: str            # YES / NO / UNCERTAIN
    attribution_correct: str  # YES / NO / PARTIAL
    supports_claims: str   # YES / NO / PARTIAL
    reasoning: str


@dataclass
class RefReviewResult:
    model: str
    verdicts: list[RefVerdict] = field(default_factory=list)
    raw_responses: dict[str, str] = field(default_factory=dict)  # ref_key -> raw output


@dataclass
class RefAggregateResult:
    file_reviewed: str
    models: list[str] = field(default_factory=list)
    reviews: list[RefReviewResult] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
    disagreements: list[dict] = field(default_factory=list)  # per-axis disagreements


@dataclass
class DerivVerdict:
    deriv_id: str          # "poisson-eq", "eq-3", etc.
    equation: str          # the equation text
    verdict: str           # VALID / GAP / INVALID
    classification: str    # DERIVED / MATCHED / INHERITED / PREDICTED / AXIOM
    circularity: str       # NONE / SUSPECTED / CONFIRMED
    reasoning: str


@dataclass
class DerivReviewResult:
    model: str
    verdicts: list[DerivVerdict] = field(default_factory=list)
    raw_response: str = ""
    valid_count: int = 0
    gap_count: int = 0
    invalid_count: int = 0


@dataclass
class DerivAggregateResult:
    file_reviewed: str
    models: list[str] = field(default_factory=list)
    reviews: list[DerivReviewResult] = field(default_factory=list)
    disagreements: list[dict] = field(default_factory=list)
