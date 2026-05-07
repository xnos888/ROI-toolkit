#!/usr/bin/env python3
"""
classify_change.py — Classify an inputs.json change by cascade severity.

Outputs JSON with:
- severity: LIGHT | MEDIUM | HEAVY | STRUCTURAL
- downstream_files: list of artifact types affected
- research_frozen_override: bool (true if change touches a research-frozen field)
- requires_re_research: bool
- recommend_re_review: bool
- rationale: human-readable explanation

Usage:
    python classify_change.py <inputs.json> <change.json> > <classification.json>

change.json schema:
    {"field_path": "effort.base", "new_value": 25, "rationale": "optional"}
"""

import json
import re
import sys
from pathlib import Path


# Field-path classification rules. First match wins.
# Each rule: (regex, severity, requires_re_research, recommend_re_review, rationale)
RULES = [
    # STRUCTURAL — invalidates research, escalate to roi-build
    (r"^feature\.sub_features", "STRUCTURAL", True, True,
     "Sub-feature change invalidates decomposition + research."),
    (r"^feature\.scope$", "STRUCTURAL", True, True,
     "Scope rewording may change mechanism — invalidates research."),
    (r"^driver_tree$", "STRUCTURAL", False, True,
     "Driver tree change reframes value attribution — re-review needed."),
    (r"^value_components", "STRUCTURAL", False, True,
     "Value component structure change — invalidates verdict."),

    # HEAVY — research-frozen fields
    (r"^conversion_factors\[\d+\]\.(worst|base|best|tier)$", "HEAVY", True, True,
     "Conversion factor value/tier is research-frozen. Override forces tier=T4 + warning."),
    (r"^tam_sam_som\.tam\.(worst|base|best)$", "HEAVY", True, True,
     "TAM volume tuning forbidden by anti-confirmation-bias whitelist; override forces T4."),
    (r"^tam_sam_som\.sam_filters\[\d+\]\.(worst|base|best)$", "HEAVY", True, True,
     "SAM filter rate tuning forbidden by whitelist; override forces T4."),
    (r"^confidence\.tier$", "HEAVY", False, True,
     "Confidence tier is metadata; manual override flagged."),

    # MEDIUM — affects ROI calculation, requires rebuild
    (r"^effort\.", "MEDIUM", False, True,
     "Effort change affects cost denominator → ROI shifts → likely tier change."),
    (r"^effort\.breakdown", "MEDIUM", False, True,
     "Effort breakdown change (role-level) affects total cost."),
    (r"^tam_sam_som\.tam\.unit$", "MEDIUM", False, False,
     "TAM unit change requires structural rebuild but doesn't shift research."),
    (r"^tam_sam_som\.som_y[123]\.(worst|base|best)$", "MEDIUM", False, True,
     "SOM ramp change affects Y1/Y2/Y3 phasing → ROI shifts."),
    (r"^baseline\[\d+\]\.value$", "MEDIUM", False, True,
     "Baseline metric change cascades to all CFs that =ref: it."),

    # LIGHT — text/metadata, low ROI impact
    (r"^strategic_fit\.multiplier$", "LIGHT", False, False,
     "Strategic Fit feeds Priority Score only (not headline ROI). Affects roadmap rank only."),
    (r"^feature\.(name|owner|status|date)$", "LIGHT", False, False,
     "Metadata field — no ROI impact."),
    (r"label$|note$|source$", "LIGHT", False, False,
     "Annotation text — no ROI impact."),
    (r"^primary_outcome$|^secondary_metrics$|^hypothesis$", "LIGHT", False, False,
     "Narrative field — no ROI impact."),
    (r"^cagan_risks", "LIGHT", False, False,
     "Risk descriptor — no ROI impact, may affect re-review priority."),
]


# Downstream files mapping per severity
DOWNSTREAM_FILES = {
    "LIGHT":      ["xlsx (patch only)", "summary.md", "Pipeline_Summary"],
    "MEDIUM":     ["xlsx (full rebuild)", "summary.md", "Pipeline_Summary", "Phase_Plan"],
    "HEAVY":      ["xlsx (full rebuild)", "summary.md", "research_validation.md (force T4)",
                   "Pipeline_Summary", "Phase_Plan", "review/*.stale (predicted)"],
    "STRUCTURAL": ["ALL — escalate to roi-build (full restart)"],
}


def classify(field_path: str) -> dict:
    """Match field_path against rules. Return classification dict."""
    for pattern, severity, re_research, re_review, rationale in RULES:
        if re.search(pattern, field_path):
            return {
                "severity": severity,
                "downstream_files": DOWNSTREAM_FILES[severity],
                "research_frozen_override": severity == "HEAVY" and "tier" not in field_path,
                "requires_re_research": re_research,
                "recommend_re_review": re_review,
                "matched_rule": pattern,
                "rationale": rationale,
            }
    # Default fallback for unrecognized fields
    return {
        "severity": "MEDIUM",
        "downstream_files": DOWNSTREAM_FILES["MEDIUM"],
        "research_frozen_override": False,
        "requires_re_research": False,
        "recommend_re_review": True,
        "matched_rule": "default_fallback",
        "rationale": f"Field path '{field_path}' not recognized — defaulting to MEDIUM (rebuild + cascade). Verify cascade by inspecting outputs.",
    }


def main():
    if len(sys.argv) != 3:
        print("Usage: classify_change.py <inputs.json> <change.json>", file=sys.stderr)
        sys.exit(2)

    inputs_path = Path(sys.argv[1])
    change_path = Path(sys.argv[2])

    if not inputs_path.exists():
        print(f"ERROR: inputs.json not found: {inputs_path}", file=sys.stderr)
        sys.exit(1)
    if not change_path.exists():
        print(f"ERROR: change.json not found: {change_path}", file=sys.stderr)
        sys.exit(1)

    change = json.loads(change_path.read_text())
    field_path = change.get("field_path", "")
    if not field_path:
        print("ERROR: change.json missing 'field_path'", file=sys.stderr)
        sys.exit(1)

    result = classify(field_path)
    result["field_path"] = field_path
    result["new_value"] = change.get("new_value")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
