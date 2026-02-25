"""Fetch paper metadata and abstracts from academic APIs."""

import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from . import Reference

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "multi-model-review" / "refs"

# Rate limit: service -> minimum seconds between requests
RATE_LIMITS = {
    "semantic_scholar": 0.1,
    "crossref": 1.0,
    "arxiv": 3.0,
}

# Track last call time per service
_last_call: dict[str, float] = {}

# Journal-like substrings used to filter titles from venue names
_JOURNAL_MARKERS = {
    "Trans.", "J.", "Rev.", "Proc.", "Lett.", "Ann.", "Phys.",
    "Math.", "Commun.", "Acad.", "Soc.", "Bull.", "Arch.",
    "Journal", "Review", "Proceedings", "Letters", "Annals",
}


@dataclass
class FetchResult:
    source: str = "none"  # "semantic_scholar", "crossref", "arxiv", "none"
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: str = ""
    venue: str = ""
    abstract: str = ""
    doi: str = ""
    open_access_url: str = ""
    error: str = ""

    def to_prompt_text(self) -> str:
        """Format for inclusion in a verification prompt."""
        if self.source == "none":
            return ""
        parts = [f"Source: {self.source}"]
        if self.title:
            parts.append(f"Title: {self.title}")
        if self.authors:
            parts.append(f"Authors: {', '.join(self.authors)}")
        if self.year:
            parts.append(f"Year: {self.year}")
        if self.venue:
            parts.append(f"Venue: {self.venue}")
        if self.doi:
            parts.append(f"DOI: {self.doi}")
        if self.abstract:
            parts.append(f"Abstract: {self.abstract}")
        if self.open_access_url:
            parts.append(f"Open access: {self.open_access_url}")
        return "\n".join(parts)


def _rate_limit(service: str) -> None:
    """Sleep if needed to respect rate limits."""
    min_interval = RATE_LIMITS.get(service, 1.0)
    last = _last_call.get(service, 0.0)
    elapsed = time.time() - last
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _last_call[service] = time.time()


def _url_fetch(url: str, timeout: int = 15) -> bytes:
    """Fetch URL content with a user-agent header."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "multi-model-review/0.1 (academic reference checker)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# --- Search query construction ---

def _parse_search_query(entry_text: str) -> str:
    """Extract a search query from a bibliography entry.

    Strategy:
    1. Look for title in \\textit{}, \\emph{}, {\\em }, or ``...''
    2. Filter out journal-like strings
    3. Extract first author surname
    4. Return "title author_surname"
    """
    title = _extract_title(entry_text)
    author = _extract_first_author(entry_text)

    parts = []
    if title:
        parts.append(title)
    if author:
        parts.append(author)
    if not parts:
        # Fallback: use cleaned entry text
        cleaned = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", entry_text)
        cleaned = re.sub(r"[{}\\]", "", cleaned)
        parts.append(cleaned[:120])
    return " ".join(parts)


def _extract_title(entry_text: str) -> str:
    """Try to extract a paper title from a bib entry."""
    # Try \textit{...}
    m = re.search(r"\\textit\{([^}]+)\}", entry_text)
    if m:
        return _clean_title(m.group(1))

    # Try \emph{...}
    m = re.search(r"\\emph\{([^}]+)\}", entry_text)
    if m:
        return _clean_title(m.group(1))

    # Try {\em ...}
    m = re.search(r"\{\\em\s+([^}]+)\}", entry_text)
    if m:
        return _clean_title(m.group(1))

    # Try ``...''
    m = re.search(r"``([^']+)''", entry_text)
    if m:
        return _clean_title(m.group(1))

    # Try "..."
    m = re.search(r'"([^"]{10,})"', entry_text)
    if m:
        return _clean_title(m.group(1))

    return ""


def _clean_title(text: str) -> str:
    """Clean LaTeX artifacts from a title."""
    text = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", text)
    text = re.sub(r"[{}\\]", "", text)
    text = text.strip().rstrip(".,;:")
    # Check if this looks like a journal name
    if _looks_like_journal(text):
        return ""
    return text


def _looks_like_journal(text: str) -> bool:
    """Heuristic: does this text look like a journal name?"""
    for marker in _JOURNAL_MARKERS:
        if marker in text:
            return True
    return False


def _extract_first_author(entry_text: str) -> str:
    """Extract the first author surname from a bib entry."""
    # Remove the \bibitem{...} prefix
    text = re.sub(r"\\bibitem\{[^}]*\}\s*", "", entry_text)
    # Remove leading numbers like [1]
    text = re.sub(r"^\s*\[\d+\]\s*", "", text)
    # The first word(s) before a comma or "and" is typically the author
    text = text.strip()
    # Try "Surname, First" pattern
    m = re.match(r"([A-Z][a-zA-Z'-]+),", text)
    if m:
        return m.group(1)
    # Try "F. Surname" or "First Surname," pattern
    m = re.match(r"[A-Z]\.\s*(?:[A-Z]\.\s*)*([A-Z][a-zA-Z'-]+)", text)
    if m:
        return m.group(1)
    # Try "First Surname,"
    m = re.match(r"[A-Z][a-z]+\s+([A-Z][a-zA-Z'-]+)", text)
    if m:
        return m.group(1)
    return ""


def _extract_arxiv_id(entry_text: str) -> Optional[str]:
    """Try to extract an arXiv ID from a bib entry."""
    # Match patterns like arXiv:1234.5678, arxiv:1234.5678v2
    m = re.search(r"arXiv[:\s]+(\d{4}\.\d{4,5}(?:v\d+)?)", entry_text, re.IGNORECASE)
    if m:
        return m.group(1)
    # Match old-style arXiv IDs like hep-th/9901001
    m = re.search(r"arXiv[:\s]+([a-z-]+/\d{7})", entry_text, re.IGNORECASE)
    if m:
        return m.group(1)
    # Match arxiv URLs
    m = re.search(r"arxiv\.org/abs/(\d{4}\.\d{4,5}(?:v\d+)?)", entry_text, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"arxiv\.org/abs/([a-z-]+/\d{7})", entry_text, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


# --- Title similarity ---

def _title_similarity(a: str, b: str) -> float:
    """Jaccard word-overlap similarity between two titles."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


# --- API clients ---

def _search_semantic_scholar(query: str) -> Optional[FetchResult]:
    """Search Semantic Scholar API."""
    _rate_limit("semantic_scholar")
    params = urllib.parse.urlencode({
        "query": query,
        "fields": "title,authors,year,venue,abstract,externalIds,openAccessPdf",
        "limit": "3",
    })
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?{params}"
    try:
        data = json.loads(_url_fetch(url))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError,
            OSError, TimeoutError) as e:
        return FetchResult(source="none", error=f"semantic_scholar: {e}")

    papers = data.get("data", [])
    if not papers:
        return None

    # Find best title match
    query_title = query.rsplit(" ", 1)[0] if " " in query else query
    best = None
    best_score = 0.0
    for paper in papers:
        score = _title_similarity(query_title, paper.get("title", ""))
        if score > best_score:
            best_score = score
            best = paper

    if best is None or best_score < 0.4:
        return None

    authors = [a.get("name", "") for a in best.get("authors", [])]
    ext_ids = best.get("externalIds", {}) or {}
    oa_pdf = best.get("openAccessPdf", {}) or {}

    return FetchResult(
        source="semantic_scholar",
        title=best.get("title", ""),
        authors=authors,
        year=str(best.get("year", "")),
        venue=best.get("venue", ""),
        abstract=best.get("abstract", "") or "",
        doi=ext_ids.get("DOI", ""),
        open_access_url=oa_pdf.get("url", ""),
    )


def _search_crossref(query: str) -> Optional[FetchResult]:
    """Search CrossRef API."""
    _rate_limit("crossref")
    params = urllib.parse.urlencode({
        "query.bibliographic": query,
        "rows": "3",
        "mailto": "multi-model-review@example.com",
    })
    url = f"https://api.crossref.org/works?{params}"
    try:
        data = json.loads(_url_fetch(url))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError,
            OSError, TimeoutError) as e:
        return FetchResult(source="none", error=f"crossref: {e}")

    items = data.get("message", {}).get("items", [])
    if not items:
        return None

    # Find best title match
    query_title = query.rsplit(" ", 1)[0] if " " in query else query
    best = None
    best_score = 0.0
    for item in items:
        titles = item.get("title", [])
        item_title = titles[0] if titles else ""
        score = _title_similarity(query_title, item_title)
        if score > best_score:
            best_score = score
            best = item

    if best is None or best_score < 0.4:
        return None

    titles = best.get("title", [])
    title = titles[0] if titles else ""
    authors = []
    for a in best.get("author", []):
        given = a.get("given", "")
        family = a.get("family", "")
        authors.append(f"{given} {family}".strip())

    published = best.get("published-print", best.get("published-online", {}))
    year = ""
    if published and published.get("date-parts"):
        year = str(published["date-parts"][0][0])

    venue_list = best.get("container-title", [])
    venue = venue_list[0] if venue_list else ""

    return FetchResult(
        source="crossref",
        title=title,
        authors=authors,
        year=year,
        venue=venue,
        abstract="",  # CrossRef rarely has abstracts
        doi=best.get("DOI", ""),
    )


def _fetch_arxiv(arxiv_id: str) -> Optional[FetchResult]:
    """Fetch metadata from arXiv API by ID."""
    _rate_limit("arxiv")
    url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
    try:
        xml_bytes = _url_fetch(url)
    except (urllib.error.URLError, urllib.error.HTTPError,
            OSError, TimeoutError) as e:
        return FetchResult(source="none", error=f"arxiv: {e}")

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        return FetchResult(source="none", error=f"arxiv XML parse: {e}")

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entry = root.find("atom:entry", ns)
    if entry is None:
        return None

    title_el = entry.find("atom:title", ns)
    title = title_el.text.strip() if title_el is not None and title_el.text else ""
    # Normalize whitespace in title
    title = re.sub(r"\s+", " ", title)

    summary_el = entry.find("atom:summary", ns)
    abstract = summary_el.text.strip() if summary_el is not None and summary_el.text else ""
    abstract = re.sub(r"\s+", " ", abstract)

    authors = []
    for author_el in entry.findall("atom:author", ns):
        name_el = author_el.find("atom:name", ns)
        if name_el is not None and name_el.text:
            authors.append(name_el.text.strip())

    published_el = entry.find("atom:published", ns)
    year = ""
    if published_el is not None and published_el.text:
        year = published_el.text[:4]

    # Get DOI link if present
    doi = ""
    for link in entry.findall("atom:link", ns):
        if link.get("title") == "doi":
            doi = link.get("href", "")
            break

    pdf_url = ""
    for link in entry.findall("atom:link", ns):
        if link.get("type") == "application/pdf":
            pdf_url = link.get("href", "")
            break

    return FetchResult(
        source="arxiv",
        title=title,
        authors=authors,
        year=year,
        abstract=abstract,
        doi=doi,
        open_access_url=pdf_url,
    )


# --- Cache ---

def _cache_key(entry_text: str) -> str:
    """Generate a cache key from entry text."""
    normalized = re.sub(r"\s+", " ", entry_text.strip().lower())
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _cache_get(entry_text: str, cache_dir: Path) -> Optional[FetchResult]:
    """Try to load a cached result."""
    path = cache_dir / f"{_cache_key(entry_text)}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return FetchResult(**data)
    except (json.JSONDecodeError, TypeError, KeyError):
        return None


def _cache_put(entry_text: str, result: FetchResult, cache_dir: Path) -> None:
    """Save a result to cache."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{_cache_key(entry_text)}.json"
    path.write_text(json.dumps(asdict(result), indent=2))


# --- Orchestration ---

def fetch_one(ref: Reference, cache_dir: Path) -> FetchResult:
    """Fetch metadata for a single reference.

    Pipeline:
    1. Check cache
    2. If entry has arXiv ID, try arXiv API
    3. Try Semantic Scholar
    4. Fall back to CrossRef
    5. Return source="none" if all fail
    """
    # 1. Cache check
    cached = _cache_get(ref.entry_text, cache_dir)
    if cached is not None:
        return cached

    # 2. arXiv by ID
    arxiv_id = _extract_arxiv_id(ref.entry_text)
    if arxiv_id:
        result = _fetch_arxiv(arxiv_id)
        if result and result.source != "none":
            _cache_put(ref.entry_text, result, cache_dir)
            return result

    # 3. Semantic Scholar
    query = _parse_search_query(ref.entry_text)
    if query.strip():
        result = _search_semantic_scholar(query)
        if result and result.source != "none":
            _cache_put(ref.entry_text, result, cache_dir)
            return result

    # 4. CrossRef
    if query.strip():
        result = _search_crossref(query)
        if result and result.source != "none":
            _cache_put(ref.entry_text, result, cache_dir)
            return result

    # 5. All failed
    miss = FetchResult(source="none")
    _cache_put(ref.entry_text, miss, cache_dir)
    return miss


def fetch_refs(refs: list[Reference], cache_dir: Path = DEFAULT_CACHE_DIR,
               quiet: bool = False) -> None:
    """Fetch metadata for all references, populating ref.fetched_content in place.

    Fetches are best-effort: failures are logged but never fatal.
    """
    for i, ref in enumerate(refs, 1):
        if not quiet:
            print(f"Fetching [{ref.key}] ({i}/{len(refs)})...", end=" ", file=sys.stderr)
        try:
            result = fetch_one(ref, cache_dir)
            ref.fetched_content = result.to_prompt_text()
            if not quiet:
                if result.source != "none":
                    short_title = result.title[:60] + "..." if len(result.title) > 60 else result.title
                    print(f"Found via {result.source}: {short_title}", file=sys.stderr)
                else:
                    msg = f"Not found"
                    if result.error:
                        msg += f" ({result.error})"
                    print(msg, file=sys.stderr)
        except Exception as e:
            if not quiet:
                print(f"Error: {e}", file=sys.stderr)
            ref.fetched_content = ""
