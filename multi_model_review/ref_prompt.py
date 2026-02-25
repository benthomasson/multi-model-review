"""Build per-reference verification prompts."""

from . import Reference


REF_PROMPT_TEMPLATE = """\
You are verifying a single reference in a research paper. Your job is to check three things:

1. **EXISTS**: Does this reference appear to be a real publication? Check author names, title, year, and venue for plausibility. If you recognize the work, confirm it exists. If you don't recognize it but the details are plausible, say UNCERTAIN.

2. **ATTRIBUTION**: Does the paper correctly describe what this reference says? Check each citation context — is the claim attributed to this reference actually something the referenced work establishes?

3. **SUPPORTS_CLAIMS**: Does the reference actually support the claims made where it is cited? A reference can exist and be correctly attributed but still not support the specific claim being made (e.g., citing a general result for a specific case it doesn't cover).

{knowledge_note}
## Reference Entry

Key: {key}

{entry_text}
{fetched_section}
## Citation Contexts

The following paragraphs cite this reference:

{contexts}

## Output Format

Respond in exactly this format:

EXISTS: YES|NO|UNCERTAIN
ATTRIBUTION: YES|NO|PARTIAL
SUPPORTS_CLAIMS: YES|NO|PARTIAL
REASONING: Your detailed assessment. Be specific about any problems found.\
"""

_KNOWLEDGE_ONLY_NOTE = """\
You are checking this reference from your knowledge only. If you do not recognize it, say UNCERTAIN for EXISTS rather than guessing."""

_FETCHED_NOTE = """\
Retrieved paper information is provided below. Use this as primary evidence for your verification. For EXISTS, verify that the bib entry matches the retrieved record. For ATTRIBUTION and SUPPORTS_CLAIMS, use the abstract and metadata to assess the claims."""

_FETCHED_SECTION_TEMPLATE = """
## Retrieved Paper Information

{fetched_content}
"""


def build_ref_prompt(ref: Reference) -> str:
    """Build a verification prompt for a single reference."""
    if ref.contexts:
        contexts = "\n\n---\n\n".join(ref.contexts)
    else:
        contexts = "(No citation contexts found in the document body.)"

    has_fetched = bool(ref.fetched_content)

    knowledge_note = _FETCHED_NOTE if has_fetched else _KNOWLEDGE_ONLY_NOTE

    if has_fetched:
        fetched_section = _FETCHED_SECTION_TEMPLATE.format(
            fetched_content=ref.fetched_content,
        )
    else:
        fetched_section = ""

    return REF_PROMPT_TEMPLATE.format(
        key=ref.key,
        entry_text=ref.entry_text,
        contexts=contexts,
        knowledge_note=knowledge_note,
        fetched_section=fetched_section,
    )
