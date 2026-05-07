#!/usr/bin/env python3
"""
compute_impact.py — Generate human-readable impact preview md for an adjust.

Reads inputs.json + change spec + classification, produces preview.md showing:
- Diff (before → after)
- Files affected (concrete paths)
- ROI delta estimate (rough — actual rebuild for exact)
- Tier shift prediction (🟢/🟡/🟠/🔴 transitions)
- Reviewer staleness prediction
- Reversibility note

Usage:
    python compute_impact.py <inputs.json> <change.json> <classification.json> <preview.md>
"""

import json
import sys
from pathlib import Path


def get_nested(data: dict, path: str):
    """Get nested value using dotted path with [N] for arrays."""
    parts = []
    for token in path.split("."):
        # Handle "field[N]" syntax
        if "[" in token:
            field, idx_str = token.split("[")
            idx = int(idx_str.rstrip("]"))
            parts.append((field, idx))
        else:
            parts.append((token, None))

    cursor = data
    for field, idx in parts:
        if cursor is None:
            return None
        cursor = cursor.get(field) if isinstance(cursor, dict) else None
        if idx is not None and isinstance(cursor, list):
            cursor = cursor[idx] if idx < len(cursor) else None
    return cursor


def estimate_roi_delta(inputs: dict, field_path: str, new_value, severity: str) -> dict:
    """
    Rough ROI delta estimate. Heuristic only — actual rebuild required for exact.

    - effort change → cost denominator delta → ROI scales inversely
    - TAM/SAM/CF change → value numerator delta → ROI scales proportionally
    - strategic_fit → Priority Score only, not Pure ROI
    """
    if severity == "STRUCTURAL":
        return {"note": "STRUCTURAL change — ROI delta unpredictable. Full rebuild required.",
                "estimated_pct": None}

    if "strategic_fit" in field_path:
        return {"note": "Strategic Fit feeds Priority Score only — Pure ROI unchanged.",
                "estimated_pct": 0.0}

    if "effort" in field_path:
        old = get_nested(inputs, field_path)
        if old and isinstance(old, (int, float)) and old > 0:
            # ROI scales inversely with effort (1/eff_ratio - 1)
            ratio = old / new_value
            delta_pct = (ratio - 1) * 100
            return {
                "note": f"Effort {old} → {new_value} MD: cost denominator changes by ratio {old/new_value:.2f}x.",
                "estimated_pct": delta_pct,
                "direction": "increase" if delta_pct > 0 else "decrease",
            }

    if any(k in field_path for k in ["tam.", "sam_filters", "som_y"]):
        old = get_nested(inputs, field_path)
        if old and isinstance(old, (int, float)) and old > 0:
            ratio = new_value / old
            delta_pct = (ratio - 1) * 100
            return {
                "note": f"TAM/SAM/SOM scale: {old} → {new_value} (ratio {ratio:.2f}x). Value numerator scales proportionally.",
                "estimated_pct": delta_pct,
                "direction": "increase" if delta_pct > 0 else "decrease",
            }

    if "conversion_factors" in field_path and any(k in field_path for k in [".worst", ".base", ".best"]):
        old = get_nested(inputs, field_path)
        if old and isinstance(old, (int, float)) and old > 0:
            ratio = new_value / old
            delta_pct = (ratio - 1) * 100
            return {
                "note": f"CF {field_path}: {old} → {new_value} (ratio {ratio:.2f}x). Affects component value calc.",
                "estimated_pct": delta_pct,
                "direction": "increase" if delta_pct > 0 else "decrease",
            }

    return {"note": "Delta estimate unavailable for this field type. Rebuild for actual ROI.",
            "estimated_pct": None}


def predict_tier_shift(inputs: dict, delta_pct: float | None) -> str:
    """Best-guess tier shift based on current ROI + delta. Heuristic."""
    if delta_pct is None:
        return "Unpredictable — rebuild to see actual tier."

    # Try to read current Y1 ROI from inputs metadata if cached, else say unknown
    current_y1 = inputs.get("_meta", {}).get("last_y1_base_roi")
    if current_y1 is None:
        return f"Y1 ROI delta ~{delta_pct:+.0f}% (current ROI unknown — rebuild required for tier prediction)."

    new_y1 = current_y1 * (1 + delta_pct / 100)

    def tier(roi):
        if roi >= 5: return "🟢 STRONG GO"
        if roi >= 1.5: return "🟡 CONDITIONAL"
        if roi >= 1.0: return "🟠 DEFER"
        return "🔴 KILL"

    old_tier, new_tier = tier(current_y1), tier(new_y1)
    if old_tier != new_tier:
        return f"⚠ TIER SHIFT predicted: {old_tier} → {new_tier} (Y1 {current_y1:.2f}x → {new_y1:.2f}x)"
    return f"No tier shift expected ({old_tier}, Y1 {current_y1:.2f}x → {new_y1:.2f}x)"


def main():
    if len(sys.argv) != 5:
        print("Usage: compute_impact.py <inputs.json> <change.json> <classification.json> <preview.md>",
              file=sys.stderr)
        sys.exit(2)

    inputs = json.loads(Path(sys.argv[1]).read_text())
    change = json.loads(Path(sys.argv[2]).read_text())
    classification = json.loads(Path(sys.argv[3]).read_text())
    preview_path = Path(sys.argv[4])

    field_path = change["field_path"]
    new_value = change["new_value"]
    old_value = get_nested(inputs, field_path)

    delta = estimate_roi_delta(inputs, field_path, new_value, classification["severity"])
    tier_pred = predict_tier_shift(inputs, delta.get("estimated_pct"))
    code = inputs["feature"]["code"]

    md = f"""# Impact Preview — {code} adjust

## Change

| Field | Before | After |
|---|---|---|
| `{field_path}` | `{old_value}` | `{new_value}` |

**Severity:** {classification['severity']}
**Rationale (classifier):** {classification['rationale']}

## Files Affected

"""
    for f in classification["downstream_files"]:
        md += f"- `{f}`\n"

    md += f"""
## ROI Delta Estimate

{delta.get('note', '')}
"""
    if delta.get("estimated_pct") is not None:
        md += f"\n**Estimated change:** {delta['estimated_pct']:+.1f}% ({delta.get('direction', '?')})\n"

    md += f"""
## Tier Prediction

{tier_pred}

## Reviewer Staleness

"""
    if classification["recommend_re_review"]:
        md += "⚠ Tier shift / methodology change likely → existing reviewer files will be marked `.stale`. Re-run `roi-deep-review` recommended.\n"
    else:
        md += "✓ Reviewer files retain validity (no tier/methodology shift expected).\n"

    if classification.get("research_frozen_override"):
        md += """
## ⚠ RESEARCH-FROZEN OVERRIDE

This change touches a field protected by the anti-confirmation-bias whitelist (CFs / TAM volumes / SF multiplier).
Per project rule, this is permitted as **manual override** but:

1. CF tier will be forced to `T4` + warning logged
2. `research_validation.md` updated to flag override
3. Strong recommendation: re-research via WebSearch before committing the new value

Proceed only if Kim has independent reason (post-pilot data, new Tableau audit, etc.) — NOT to "match a target ROI".
"""

    md += f"""
## Reversibility

- Current `inputs.json` will be saved as `inputs.v{{N}}.json` before applying change
- Rollback: `cp _inputs/{code}_inputs.v{{N-1}}.json _inputs/{code}_inputs.json && roi-adjust --rebuild`
- Last 5 versions kept; older archived to `_inputs/_archive/`

---

**Approve to proceed?** (yes/no)
"""

    preview_path.write_text(md, encoding="utf-8")
    print(json.dumps({
        "status": "preview_generated",
        "preview_path": str(preview_path),
        "severity": classification["severity"],
        "delta_pct": delta.get("estimated_pct"),
        "research_frozen_override": classification.get("research_frozen_override", False),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
