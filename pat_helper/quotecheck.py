"""Mechanical quote grounding: does a model's quote actually appear in the paper?

Zero API cost. Exact/normalized substring match first, then a fuzzy fallback
(difflib ratio over candidate windows). This kills the most embarrassing
hallucination class — critiques anchored to sentences that don't exist —
before any model is asked to verify anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from pat_helper.latex import FlattenedPaper
from pat_helper.models import SourceLocation

FUZZY_THRESHOLD = 0.85

# Single-char replacements applied during normalization
_CHAR_MAP = {
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "–": "-",  # en dash
    "—": "-",  # em dash
    "~": " ",  # LaTeX non-breaking space
}
# Multi-char sequences, longest first
_SEQ_MAP = [("---", "-"), ("--", "-"), ("\\%", "%"), ("``", '"'), ("''", '"')]


@dataclass
class QuoteMatch:
    found: bool
    score: float
    location: SourceLocation | None


def _normalize(s: str) -> tuple[str, list[int]]:
    """Normalize text; return (normalized, map from normalized index -> original offset)."""
    out: list[str] = []
    offsets: list[int] = []
    i = 0
    n = len(s)
    while i < n:
        matched_seq = False
        for seq, repl in _SEQ_MAP:
            if s.startswith(seq, i):
                for ch in repl:
                    out.append(ch)
                    offsets.append(i)
                i += len(seq)
                matched_seq = True
                break
        if matched_seq:
            continue
        ch = s[i]
        ch = _CHAR_MAP.get(ch, ch)
        if ch.isspace():
            # collapse whitespace runs to a single space
            if out and out[-1] != " ":
                out.append(" ")
                offsets.append(i)
        else:
            out.append(ch.casefold())
            offsets.append(i)
        i += 1
    # trim leading/trailing space
    if out and out[0] == " ":
        out.pop(0)
        offsets.pop(0)
    if out and out[-1] == " ":
        out.pop()
        offsets.pop()
    return "".join(out), offsets


def _fuzzy_best(nq: str, nt: str) -> tuple[float, int]:
    """Best (ratio, start) of nq against windows of nt, anchored on a distinctive word."""
    words = sorted(nq.split(), key=len, reverse=True)
    candidates: set[int] = set()
    for w in words[:3]:
        w_pos_in_quote = nq.find(w)
        start = 0
        while (idx := nt.find(w, start)) != -1:
            # align the window so the anchor word lines up with its position in the quote
            candidates.add(max(0, idx - w_pos_in_quote))
            start = idx + 1
        if candidates:
            break
    if not candidates:
        # coarse scan fallback
        step = max(1, len(nq) // 4)
        candidates = set(range(0, max(1, len(nt) - len(nq) + 1), step))
    best_score, best_start = 0.0, 0
    wlen = len(nq) + 10
    for anchor_start in candidates:
        for start in {anchor_start, max(0, anchor_start - 5), anchor_start + 5}:
            window = nt[start : start + wlen]
            sm = SequenceMatcher(None, nq, window, autojunk=False)
            if sm.real_quick_ratio() < best_score or sm.quick_ratio() < best_score:
                continue
            r = sm.ratio()
            if r > best_score:
                best_score, best_start = r, start
    return best_score, best_start


def check_quote(
    quote: str, paper: FlattenedPaper, threshold: float = FUZZY_THRESHOLD
) -> QuoteMatch:
    nq, _ = _normalize(quote)
    nt, tmap = _normalize(paper.text)
    if not nq:
        return QuoteMatch(found=False, score=0.0, location=None)
    idx = nt.find(nq)
    if idx != -1:
        return QuoteMatch(found=True, score=1.0, location=paper.locate(tmap[idx]))
    score, start = _fuzzy_best(nq, nt)
    if score >= threshold:
        return QuoteMatch(found=True, score=score, location=paper.locate(tmap[start]))
    return QuoteMatch(found=False, score=score, location=None)
