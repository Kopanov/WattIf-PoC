"""Defense-in-depth guardrail: reject any text containing recommendation/advice/optimization
language, and log every decision. Descriptive statements pass; prescriptive ones are blocked.

This is the secondary layer; the primary guarantee is structural (the explainer can only fill
descriptive slots). Together they make advice provably impossible — Moat 2. The red-team demo
(scripts/redteam_demo.py) shows this blocking seeded advice at 100%.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Curated prescriptive/advice/optimization patterns (case-insensitive).
_ADVICE_PATTERNS = [
    r"\byou (should|shouldn'?t|could|can|may want to|might want to|ought to|need to|must)\b",
    r"\b(we|i) (recommend|suggest|advise|propose)\b",
    r"\brecommend(ed|ation|ations|ing)?\b",
    r"\bsuggest(ion|ions|ed|ing)?\b",
    r"\badvis(e|ed|able|ory)\b",
    r"\bconsider (installing|adding|switching|using|increasing|reducing|buying|getting|a |the |moving|shifting)\b",
    r"\b(it'?s|it is)? ?(best|better|advisable|wise|worth|smart|ideal) (to|if|that|would)\b",
    r"\boptimi[sz]e\b",
    r"\b(maximi[sz]e|minimi[sz]e) (your|the)\b",
    r"\bto (save|cut|lower|reduce) (money|energy|costs?|your bill)\b",
    r"\bin order to (save|reduce|increase|maximi|minimi)",
    r"\bshould (install|add|switch|consider|choose|increase|reduce|buy|get|use|move|shift)\b",
    r"\b(try|consider) (installing|switching|adding|reducing|increasing|using)\b",
    r"\bif you want to\b",
]

# Imperative opening verbs (sentence-initial) — a command, not a description.
_IMPERATIVE_START = re.compile(
    r"^\s*(install|switch|add|buy|get|choose|reduce|increase|consider|optimi[sz]e|"
    r"upgrade|use|shift|move|enable|disable|set)\b",
    re.IGNORECASE,
)

_ADVICE_RE = [re.compile(p, re.IGNORECASE) for p in _ADVICE_PATTERNS]

# Human-readable description of the checks, surfaced in the audit panel.
CHECKS = [
    "modal advice (you should / we recommend / you need to / ...)",
    "suggestion & advisory language (suggest / advise / recommendation)",
    "optimization verbs (optimize / maximize your / minimize your)",
    "save-money framing (to save money / in order to reduce ...)",
    "imperative opening verbs (Install... / Switch... / Add... / Consider...)",
]


@dataclass
class GuardrailResult:
    passed: bool
    reasons: list = field(default_factory=list)  # matched phrases (why it was blocked)
    text: str = ""


def _sentences(text: str) -> list:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def check(text: str) -> GuardrailResult:
    """Return pass/fail with the matched advice phrases (empty when it passes)."""
    reasons: list = []
    for rx in _ADVICE_RE:
        for m in rx.finditer(text):
            reasons.append(m.group(0).strip())
    for sentence in _sentences(text):
        if _IMPERATIVE_START.match(sentence):
            reasons.append(f"imperative opening: '{sentence[:40]}...'")
    # De-duplicate while preserving order.
    seen = set()
    reasons = [r for r in reasons if not (r.lower() in seen or seen.add(r.lower()))]
    return GuardrailResult(passed=(len(reasons) == 0), reasons=reasons, text=text)


def audit_record(text: str, result: GuardrailResult) -> dict:
    """Structured record of which checks ran and the outcome."""
    return {
        "checks_run": CHECKS,
        "passed": result.passed,
        "matches": result.reasons,
        "verdict": "descriptive — allowed" if result.passed else "prescriptive — blocked",
    }
