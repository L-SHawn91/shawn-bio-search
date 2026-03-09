#!/usr/bin/env python3
"""Build paper-writing evidence report (support/contradict/uncertain + gaps) from bundle JSON.

P1 tuning:
- 4-way direction: support / contradict / mixed / uncertain
- uncertainty-pattern penalty for confidence
- conflict_count includes high-confidence contradict + mixed
- DOI/ID de-duplication for summary counts and review priority
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


UNCERTAIN_PATTERNS = [
    r"\buncertain\b",
    r"\blimited\b",
    r"\blow[-\s]?quality\b",
    r"\bno\s+statistically\s+significant\s+difference\b",
    r"\bnot\s+explicit\b",
    r"\binconclusive\b",
    r"\bheterogeneity\b",
]


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def canonical_key(p: Dict[str, Any]) -> str:
    doi = (p.get("doi") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    pid = (p.get("id") or "").strip().lower()
    if pid:
        return f"id:{pid}"
    title = (p.get("title") or "").strip().lower()
    return f"title:{title}"


def dedupe_papers(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # keep highest evidence_score record per key
    best: Dict[str, Dict[str, Any]] = {}
    for p in papers:
        k = canonical_key(p)
        prev = best.get(k)
        if prev is None or float(p.get("evidence_score") or 0) > float(prev.get("evidence_score") or 0):
            best[k] = p
    return list(best.values())


def has_uncertainty_language(p: Dict[str, Any]) -> bool:
    text = " ".join(
        [
            str(p.get("title") or ""),
            str(p.get("abstract") or ""),
            str(p.get("best_support_sentence") or ""),
            str(p.get("best_contradict_sentence") or ""),
        ]
    ).lower()
    return any(re.search(pat, text) for pat in UNCERTAIN_PATTERNS)


def classify(p: Dict[str, Any]) -> str:
    s = float(p.get("support_score") or 0)
    c = float(p.get("contradiction_score") or 0)
    ev = float(p.get("evidence_score") or 0)

    # mixed when both sides are non-trivial and close
    if s >= 0.35 and c >= 0.30 and abs(s - c) <= 0.12:
        return "mixed"

    if s >= c + 0.10:
        return "support"
    if c >= s + 0.10:
        return "contradict"

    # if low evidence overall and close, keep uncertain
    if ev < 0.25:
        return "uncertain"
    return "mixed"


def evidence_confidence(p: Dict[str, Any]) -> float:
    """Return confidence (0~1) for claim-direction classification."""
    s = float(p.get("support_score") or 0)
    c = float(p.get("contradiction_score") or 0)
    ev = float(p.get("evidence_score") or 0)
    margin = abs(s - c)
    conf = 0.32 + 0.43 * clamp(margin) + 0.25 * clamp(ev)

    if not (p.get("abstract") or "").strip():
        conf -= 0.10
    if has_uncertainty_language(p):
        conf -= 0.12

    direction = p.get("direction")
    if direction in {"mixed", "uncertain"}:
        conf -= 0.08

    return round(clamp(conf), 3)


def first_author(authors: Any) -> str:
    if isinstance(authors, list) and authors:
        return str(authors[0])
    return "NA"


def fmt_ref(p: Dict[str, Any]) -> str:
    author = first_author(p.get("authors"))
    year = p.get("year") or "n.d."
    title = p.get("title") or "(no title)"
    doi = p.get("doi") or "(no DOI)"
    url = p.get("url") or ""
    conf = p.get("evidence_confidence", 0)
    s = float(p.get("support_score") or 0)
    c = float(p.get("contradiction_score") or 0)
    d = p.get("direction")
    return (
        f"- [{d}] {author} ({year}). {title}. DOI: {doi}. "
        f"Support: {s:.3f}, Contradict: {c:.3f}, Confidence: {conf:.3f}. Link: {url}"
    ).strip()


def review_priority(p: Dict[str, Any]) -> float:
    """Higher means this item is more likely to need manual review."""
    ev = float(p.get("evidence_score") or 0)
    s = float(p.get("support_score") or 0)
    c = float(p.get("contradiction_score") or 0)
    tie_penalty = 1.0 - abs(s - c)
    contradiction_weight = c
    uncertain_bonus = 0.12 if has_uncertainty_language(p) else 0.0
    mixed_bonus = 0.15 if p.get("direction") == "mixed" else 0.0
    return round(0.50 * ev + 0.25 * tie_penalty + 0.15 * contradiction_weight + uncertain_bonus + mixed_bonus, 4)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--top", type=int, default=8)
    args = ap.parse_args()

    data = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    paper_block = data.get("papers") or {}
    papers: List[Dict[str, Any]] = paper_block.get("papers") or []
    claim = paper_block.get("claim") or ""
    hypothesis = paper_block.get("hypothesis") or ""
    warnings = paper_block.get("warnings") or []

    scored = sorted(papers, key=lambda x: float(x.get("evidence_score") or 0), reverse=True)
    unique_scored = sorted(dedupe_papers(scored), key=lambda x: float(x.get("evidence_score") or 0), reverse=True)

    labeled: List[Tuple[str, Dict[str, Any]]] = []
    for p in unique_scored:
        p = dict(p)
        p["direction"] = classify(p)
        p["evidence_confidence"] = evidence_confidence(p)
        labeled.append((p["direction"], p))

    support = [p for k, p in labeled if k == "support"][: args.top]
    contradict = [p for k, p in labeled if k == "contradict"][: args.top]
    mixed = [p for k, p in labeled if k == "mixed"][: args.top]
    uncertain = [p for k, p in labeled if k == "uncertain"][: args.top]

    evidence_count = sum(1 for _, p in labeled if p["direction"] == "support" and p["evidence_confidence"] >= 0.55)
    conflict_count = sum(
        1
        for _, p in labeled
        if p["direction"] in {"contradict", "mixed"} and p["evidence_confidence"] >= 0.50
    )

    review_needed = sorted([p for _, p in labeled], key=review_priority, reverse=True)[: args.top]

    gaps = []
    if not support:
        gaps.append("직접 지지 근거가 부족합니다. query/entity를 구체화하세요.")
    if not contradict and not mixed:
        gaps.append("반증/혼합 근거가 거의 없습니다. 반증 검색 쿼리를 별도로 추가하세요.")
    if sum(1 for p in unique_scored if p.get("doi")) < max(3, min(10, len(unique_scored))):
        gaps.append("DOI 없는 결과 비율이 높습니다. PubMed/OpenAlex 중심 재검색이 필요합니다.")

    lines = []
    lines.append("# Claim-Level Evidence Report (P1 tuned)")
    lines.append("")
    lines.append(f"- Claim: {claim}")
    lines.append(f"- Hypothesis: {hypothesis}")
    lines.append(f"- Total candidates (raw): {len(scored)}")
    lines.append(f"- Total candidates (deduped): {len(unique_scored)}")
    lines.append(f"- evidence_count (high-confidence support): {evidence_count}")
    lines.append(f"- conflict_count (high-confidence contradict + mixed): {conflict_count}")
    lines.append("")

    lines.append("## Supporting papers")
    lines.extend([fmt_ref(p) for p in support] if support else ["- (none)"])
    lines.append("")

    lines.append("## Contradicting papers")
    lines.extend([fmt_ref(p) for p in contradict] if contradict else ["- (none)"])
    lines.append("")

    lines.append("## Mixed papers (both supporting and conflicting signals)")
    lines.extend([fmt_ref(p) for p in mixed] if mixed else ["- (none)"])
    lines.append("")

    lines.append("## Uncertain papers")
    lines.extend([fmt_ref(p) for p in uncertain] if uncertain else ["- (none)"])
    lines.append("")

    lines.append("## Top review-needed claims (manual check priority)")
    if review_needed:
        for p in review_needed:
            author = first_author(p.get("authors"))
            year = p.get("year") or "n.d."
            title = p.get("title") or "(no title)"
            direction = p.get("direction")
            conf = p.get("evidence_confidence", 0)
            ev = float(p.get("evidence_score") or 0)
            pr = review_priority(p)
            lines.append(
                f"- [{direction}] {author} ({year}) {title} | evidence_score={ev:.3f}, confidence={conf:.3f}, review_priority={pr:.3f}"
            )
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Gaps / Next actions")
    lines.extend([f"- {g}" for g in gaps] if gaps else ["- 현재 기준으로 support/contradict 균형이 적절합니다."])
    lines.append("")

    if warnings:
        lines.append("## Warnings")
        lines.extend([f"- {w}" for w in warnings])
        lines.append("")

    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"saved: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
