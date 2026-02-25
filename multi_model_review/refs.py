"""Extract references and citation contexts from LaTeX or markdown."""

import re
from pathlib import Path

from . import Reference


def extract_references(text: str) -> list[Reference]:
    """Extract references from a document, auto-detecting format."""
    if r"\begin{thebibliography}" in text or r"\bibitem" in text:
        return _extract_latex(text)
    return _extract_markdown(text)


def _extract_latex(text: str) -> list[Reference]:
    """Extract references from LaTeX with \\bibitem and \\cite."""
    # Extract bibliography entries
    bib_entries: dict[str, str] = {}
    for match in re.finditer(
        r'\\bibitem\{([^}]+)\}\s*(.*?)(?=\\bibitem|\\end\{thebibliography\})',
        text, re.DOTALL
    ):
        key = match.group(1)
        entry = match.group(2).strip()
        # Clean up LaTeX commands for readability
        entry = re.sub(r'\\newblock\s*', '', entry)
        bib_entries[key] = entry

    if not bib_entries:
        return []

    # Split body into paragraphs (before the bibliography)
    bib_start = text.find(r'\begin{thebibliography}')
    body = text[:bib_start] if bib_start != -1 else text
    paragraphs = re.split(r'\n\s*\n', body)

    # For each reference, find paragraphs that cite it
    refs = []
    for key, entry in bib_entries.items():
        contexts = []
        # Match \cite{...key...} — key may appear with others in a multi-cite
        cite_pattern = re.compile(r'\\cite\{[^}]*\b' + re.escape(key) + r'\b[^}]*\}')
        for para in paragraphs:
            if cite_pattern.search(para):
                cleaned = para.strip()
                if cleaned:
                    contexts.append(cleaned)
        refs.append(Reference(key=key, entry_text=entry, contexts=contexts))

    return refs


def _extract_markdown(text: str) -> list[Reference]:
    """Extract references from markdown with [N] style citations."""
    # Find the references section
    ref_section_match = re.search(
        r'^##\s*References\s*\n(.*)',
        text, re.MULTILINE | re.DOTALL
    )
    if not ref_section_match:
        return []

    ref_section = ref_section_match.group(1)

    # Extract entries: [N] Author, Title, ...
    bib_entries: dict[str, str] = {}
    for match in re.finditer(r'^\[(\w+)\]\s*(.*?)(?=^\[\w+\]|\Z)', ref_section, re.MULTILINE | re.DOTALL):
        key = match.group(1)
        entry = match.group(2).strip()
        bib_entries[key] = entry

    if not bib_entries:
        return []

    # Body is everything before the references section
    ref_start = ref_section_match.start()
    body = text[:ref_start]
    paragraphs = re.split(r'\n\s*\n', body)

    refs = []
    for key, entry in bib_entries.items():
        contexts = []
        # Match [key] citations in body text
        cite_pattern = re.compile(r'\[' + re.escape(key) + r'\]')
        for para in paragraphs:
            if cite_pattern.search(para):
                cleaned = para.strip()
                if cleaned:
                    contexts.append(cleaned)
        refs.append(Reference(key=key, entry_text=entry, contexts=contexts))

    return refs


def load_and_extract(path: Path) -> list[Reference]:
    """Load a file and extract its references."""
    text = path.read_text()
    return extract_references(text)
