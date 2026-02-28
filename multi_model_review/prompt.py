"""Review prompt construction for multi-model peer review."""

import re
from pathlib import Path


REVIEW_PROMPT = """\
You are reviewing a research paper for pre-publication quality. Your job is to find errors, not encourage.

For each substantive claim you identify in the paper:
1. State the claim in one sentence
2. Is it derived from stated axioms, or reverse-engineered from the known answer?
3. Is the supporting evidence sufficient?
4. Does it contradict any other claim in the paper?

Rate each claim: PASS (no issues), CONCERN (minor, doesn't block), BLOCK (must be addressed).

Do not be diplomatic. Do not hedge. If a claim is wrong, say so directly.

Output your review in this exact format:

## Claims

### claim-short-id
VERDICT: PASS|CONCERN|BLOCK
CLAIM: One-sentence statement of the claim
REASONING: Your assessment
---

## Summary
GATE: PASS|BLOCK
TOTAL_CLAIMS: N
PASS: N
CONCERN: N
BLOCK: N
"""


def build_prompt(document: str,
                 beliefs: str | None = None,
                 nogoods: str | None = None,
                 entries: list[str] | None = None) -> str:
    """Build the full review prompt with document and optional context."""
    parts = [REVIEW_PROMPT]

    parts.append("## Document Under Review\n")
    parts.append(document)

    if beliefs:
        parts.append("\n## Belief Registry\n")
        parts.append("The following belief registry shows claim status (IN/OUT/STALE) "
                      "and known contradictions. Flag any claims in the paper that "
                      "contradict OUT or STALE beliefs.\n")
        parts.append(beliefs)

    if nogoods:
        parts.append("\n## Known Contradictions (Nogoods)\n")
        parts.append("The following are CONFIRMED contradictions established by independent "
                      "verification. Treat these as ground truth. Do NOT accept any claim "
                      "in the paper or belief registry that contradicts a nogood — these "
                      "have already been adjudicated.\n")
        parts.append(nogoods)

    if entries:
        parts.append("\n## Recent Entries (Chronological Context)\n")
        parts.append("These entries show the research trail. Use them to detect "
                      "cosmetic fixes, unresolved problems, or claims that evolved "
                      "without adequate justification.\n")
        for entry in entries:
            parts.append(entry)
            parts.append("\n---\n")

    return "\n".join(parts)


def split_sections(document: str) -> list[tuple[str, str]]:
    """Split a document into (title, content) sections on top-level headers.

    Supports markdown (## Header) and LaTeX (\\section{Title}).
    The content before the first header is returned as ("preamble", content).
    """
    # Match ## headers or \section{...} / \subsection{...}
    header_re = re.compile(
        r'^(?:##\s+(.+)|\\(?:sub)?section\{([^}]+)\})',
        re.MULTILINE,
    )

    sections: list[tuple[str, str]] = []
    last_end = 0
    last_title = "preamble"

    for m in header_re.finditer(document):
        # Flush previous section
        chunk = document[last_end:m.start()].strip()
        if chunk or last_title == "preamble":
            sections.append((last_title, chunk))
        last_title = (m.group(1) or m.group(2)).strip()
        last_end = m.end()

    # Final section
    chunk = document[last_end:].strip()
    if chunk or last_title != "preamble":
        sections.append((last_title, chunk))

    return sections


SECTION_REVIEW_PROMPT = """\
You are reviewing ONE SECTION of a larger research paper. Your job is to find errors, not encourage.

You will receive a brief preamble (title/abstract) for context, followed by the section to review.

For each substantive claim you identify in this section:
1. State the claim in one sentence
2. Is it derived from stated axioms, or reverse-engineered from the known answer?
3. Is the supporting evidence sufficient?
4. Does it contradict any other claim?

Rate each claim: PASS (no issues), CONCERN (minor, doesn't block), BLOCK (must be addressed).

Do not be diplomatic. Do not hedge. If a claim is wrong, say so directly.

Output your review in this exact format:

## Claims

### claim-short-id
VERDICT: PASS|CONCERN|BLOCK
CLAIM: One-sentence statement of the claim
REASONING: Your assessment
---

## Summary
GATE: PASS|BLOCK
TOTAL_CLAIMS: N
PASS: N
CONCERN: N
BLOCK: N
"""


def build_section_prompt(preamble: str,
                         section_title: str,
                         section_content: str,
                         beliefs: str | None = None,
                         nogoods: str | None = None,
                         entries: list[str] | None = None) -> str:
    """Build a review prompt scoped to a single document section."""
    parts = [SECTION_REVIEW_PROMPT]

    parts.append(f"## Document Preamble (for context)\n")
    parts.append(preamble)

    parts.append(f"\n## Section Under Review: {section_title}\n")
    parts.append(section_content)

    if beliefs:
        parts.append("\n## Belief Registry\n")
        parts.append("The following belief registry shows claim status (IN/OUT/STALE) "
                      "and known contradictions. Flag any claims in the section that "
                      "contradict OUT or STALE beliefs.\n")
        parts.append(beliefs)

    if nogoods:
        parts.append("\n## Known Contradictions (Nogoods)\n")
        parts.append("The following are CONFIRMED contradictions established by independent "
                      "verification. Treat these as ground truth. Do NOT accept any claim "
                      "that contradicts a nogood.\n")
        parts.append(nogoods)

    if entries:
        parts.append("\n## Recent Entries (Chronological Context)\n")
        parts.append("These entries show the research trail. Use them to detect "
                      "cosmetic fixes, unresolved problems, or claims that evolved "
                      "without adequate justification.\n")
        for entry in entries:
            parts.append(entry)
            parts.append("\n---\n")

    return "\n".join(parts)


def load_document(path: Path) -> str:
    """Load a document file."""
    return path.read_text()


def load_beliefs(path: Path) -> str | None:
    """Load a belief registry file, or None if it doesn't exist."""
    if path and path.exists():
        return path.read_text()
    return None


def load_nogoods(path: Path) -> str | None:
    """Load a nogoods file, or None if it doesn't exist."""
    if path and path.exists():
        return path.read_text()
    return None


def load_entries(directory: Path) -> list[str] | None:
    """Load entry files from a directory, sorted by name."""
    if not directory or not directory.exists():
        return None
    entries = []
    for f in sorted(directory.glob("**/*.md")):
        entries.append(f"### {f.name}\n\n{f.read_text()}")
    return entries if entries else None
