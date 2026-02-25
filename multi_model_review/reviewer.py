"""Model invocation and verdict parsing for multi-model peer review."""

import os
import re
import shutil
import subprocess

from . import ClaimVerdict, ReviewResult


# Commands for stdin-piped invocation.
# claude: -p is --print (boolean flag), prompt comes from stdin
# gemini: -p is --prompt (takes string), empty string makes it read stdin
MODEL_COMMANDS = {
    "claude": ["claude", "-p"],
    "gemini": ["gemini", "-p", ""],
}


def check_model_available(model: str) -> bool:
    """Check if a model's CLI tool is available on PATH."""
    cmd = MODEL_COMMANDS.get(model)
    if not cmd:
        return False
    return shutil.which(cmd[0]) is not None


def run_model(model: str, prompt: str, timeout: int = 300) -> str:
    """Run a model CLI and return its response text.

    Pipes the prompt via stdin to avoid OS argument length limits
    on large documents.
    """
    cmd = MODEL_COMMANDS.get(model)
    if not cmd:
        raise ValueError(f"Unknown model: {model}. Known models: {', '.join(MODEL_COMMANDS)}")

    # Remove CLAUDECODE env var to allow running from within Claude Code
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    # Pipe prompt via stdin — CLI arg would hit OS limits on large docs
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
        env=env, input=prompt,
    )
    if result.returncode != 0:
        raise RuntimeError(f"{model} failed (exit {result.returncode}): {result.stderr}")
    return result.stdout


def parse_review(model: str, response: str) -> ReviewResult:
    """Parse structured review output into ReviewResult."""
    claims = []

    # Parse claim blocks: ### claim-id followed by VERDICT/CLAIM/REASONING
    claim_pattern = re.compile(
        r'###\s+(\S+)\s*\n'
        r'VERDICT:\s*(PASS|CONCERN|BLOCK)\s*\n'
        r'CLAIM:\s*(.*?)\n'
        r'REASONING:\s*(.*?)(?=\n---|\n###|\n##|$)',
        re.DOTALL
    )

    for match in claim_pattern.finditer(response):
        claim_id = match.group(1)
        verdict = match.group(2).strip()
        claim_text = match.group(3).strip()
        reasoning = match.group(4).strip()
        claims.append(ClaimVerdict(
            claim_id=claim_id,
            claim_text=claim_text,
            verdict=verdict,
            reasoning=reasoning,
        ))

    # Parse summary
    gate = "BLOCK"  # default to BLOCK if we can't parse
    total = len(claims)
    pass_count = sum(1 for c in claims if c.verdict == "PASS")
    concern_count = sum(1 for c in claims if c.verdict == "CONCERN")
    block_count = sum(1 for c in claims if c.verdict == "BLOCK")

    # Try to extract gate from summary section
    gate_match = re.search(r'GATE:\s*(PASS|BLOCK)', response)
    if gate_match:
        gate = gate_match.group(1)
    else:
        # Infer gate from claims
        gate = "BLOCK" if block_count > 0 else "PASS"

    # Try to extract counts from summary (override computed if present)
    for label, attr in [("TOTAL_CLAIMS", "total"), ("PASS", "pass_count"),
                        ("CONCERN", "concern_count"), ("BLOCK", "block_count")]:
        match = re.search(rf'^{label}:\s*(\d+)', response, re.MULTILINE)
        if match:
            locals()[attr]  # just validate the name exists
            if attr == "total":
                total = int(match.group(1))
            elif attr == "pass_count":
                pass_count = int(match.group(1))
            elif attr == "concern_count":
                concern_count = int(match.group(1))
            elif attr == "block_count":
                block_count = int(match.group(1))

    return ReviewResult(
        model=model,
        gate=gate,
        claims=claims,
        raw_response=response,
        total=total,
        pass_count=pass_count,
        concern_count=concern_count,
        block_count=block_count,
    )


def review_file(model: str, prompt: str, timeout: int = 300) -> ReviewResult:
    """Run a model review and parse the result."""
    response = run_model(model, prompt, timeout=timeout)
    return parse_review(model, response)
