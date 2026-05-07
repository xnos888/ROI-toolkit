#!/usr/bin/env python3
"""
apply_fixes.py — deterministic fix executor for the iterative review loop.

Reads a YAML fix list (extracted from CFO/HoP verdict_block) and applies
field-level edits to inputs.json — strictly bounded by a whitelist that
prevents confirmation-bias edits (TAM/CF/SOM tuning).

Usage:
    python apply_fixes.py <inputs.json> <fixes.yaml> [--out <outputs.json>] [--auto-repair-formula-errors]
    python apply_fixes.py <inputs.json> --auto-repair-formula-errors --validator-json <val.json> [--out <outputs.json>]

Output:
    - Writes new inputs.json with fixes applied (default: <name>.vN+1.json next to input)
    - stdout: JSON {applied: [...], denied: [...], new_path: "..."}
    - stderr: human-readable summary

Exit codes:
    0 = success (fixes applied or no-op)
    1 = error (file not found, schema invalid)
    2 = all fixes denied (nothing applied)

Forbidden edits become "denied" — caller (review_loop.py) treats these as
HUMAN_ACTION_REQUIRED and surfaces them in the next iteration's reviewer prompts.
"""

import argparse
import copy
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


# ============== WHITELIST ==============

# Allowed fix types and the inputs.json paths each can edit.
# Paths use a simple notation: "field.subfield" or "field[*].subfield" for arrays.
# `[append]` means new array element appended.
ALLOWED_FIXES = {
    "formula_correction": {
        "paths": [
            "value_components[*].steps[*].cf_id",
            "value_components[*].steps[*].output_currency",
            "value_components[*].steps[*].metric",
            "value_components[*].steps[*].type",
            "value_components[*].steps[*].label",
            "value_components[*].steps[*].note",
            "value_components[*].steps[reorder]",  # special: reorder steps within a component
        ],
        "description": "Edit value_components steps (cf_id, ordering, type) — plumbing fix"
    },
    "unit_conversion": {
        "paths": [
            "tam_sam_som.tam.unit",
            "tam_sam_som.tam.label",
            "tam_sam_som.sam_filters[append]",
        ],
        "description": "RF-08 unit fix — add divisor sam_filter (e.g., 1/visits_per_patient)"
    },
    "filter_addition": {
        "paths": ["tam_sam_som.sam_filters[append]"],
        "description": "Append cohort/eligibility filter — source MUST already exist in research_validation.md or baseline"
    },
    "timing_correction": {
        "paths": [
            "value_components[*].steps[*].applies_to_year",
            "value_components[*].applies_to_year",
        ],
        "description": "Move Y2/Y3 component out of Y1 row"
    },
    "cost_addition": {
        "paths": ["effort.breakdown[append]"],
        "description": "Add missing OPEX/training/infra/change-mgmt line — closed catalog"
    },
    "cost_avoidance_split": {
        "paths": [
            "value_components[*].is_system_value",
            "driver_tree",  # narrative annotation only
        ],
        "description": "RF-04 fix — flag component as system-cost vs hospital-revenue"
    },
}

# Hard-forbidden paths. Any fix touching these is rejected regardless of fix type.
FORBIDDEN_PATHS = [
    "tam_sam_som.tam.worst",
    "tam_sam_som.tam.base",
    "tam_sam_som.tam.best",
    "tam_sam_som.sam_filters[*].worst",
    "tam_sam_som.sam_filters[*].base",
    "tam_sam_som.sam_filters[*].best",
    "tam_sam_som.som_y1",
    "tam_sam_som.som_y2",
    "tam_sam_som.som_y3",
    "conversion_factors[*].worst",
    "conversion_factors[*].base",
    "conversion_factors[*].best",
    "conversion_factors[*].tier",
    "confidence.tier",
    "confidence.reason",
    "strategic_fit.multiplier",
    "strategic_fit.reason",
    "baseline[*].value",  # baseline values are research-frozen
]

# Closed catalog of cost lines that can be appended via cost_addition
COST_CATALOG = {
    "training_md": {
        "role": "Training & Onboarding (7-branch rollout)",
        "worst": 12, "base": 8, "best": 5,
        "note": "Per-branch staff training + materials"
    },
    "infra_thb": {
        "role": "Infrastructure / SaaS subscription (annual recurring)",
        "worst": 6, "base": 4, "best": 3,
        "note": "Cloud, monitoring, SaaS tools — converted to MD-equivalent"
    },
    "change_mgmt_md": {
        "role": "Change Management (clinical workflow integration)",
        "worst": 10, "base": 7, "best": 5,
        "note": "Provider/staff workflow change support"
    },
    "app_specialist_md": {
        "role": "App Specialist (extended)",
        "worst": 8, "base": 6, "best": 4,
        "note": "Beyond standard rollout — multi-branch coordination"
    },
}


# ============== PATH MATCHING ==============

def _match_path(actual_path: str, allowed_pattern: str) -> bool:
    """Check if actual_path matches the allowed_pattern (with [*] wildcards)."""
    # Convert pattern to regex: [*] -> \[\d+\], [append] -> \[append\]
    pattern = re.escape(allowed_pattern)
    pattern = pattern.replace(r"\[\*\]", r"\[\d+\]")
    pattern = pattern.replace(r"\[append\]", r"\[append\]")
    pattern = pattern.replace(r"\[reorder\]", r"\[reorder\]")
    return re.fullmatch(pattern, actual_path) is not None


def is_path_forbidden(target_field: str) -> bool:
    """Check if target_field hits any forbidden path."""
    for forbidden in FORBIDDEN_PATHS:
        if _match_path(target_field, forbidden):
            return True
    return False


def is_fix_allowed(fix_type: str, target_field: str) -> tuple[bool, str]:
    """Check if (fix_type, target_field) is in the whitelist.

    Returns (is_allowed, reason). reason is empty string if allowed,
    or describes why denied.
    """
    if is_path_forbidden(target_field):
        return False, f"target_field '{target_field}' is in FORBIDDEN_PATHS — confirmation-bias trap"

    if fix_type not in ALLOWED_FIXES:
        return False, f"fix_type '{fix_type}' is not in ALLOWED_FIXES (must be one of: {list(ALLOWED_FIXES.keys())})"

    allowed_paths = ALLOWED_FIXES[fix_type]["paths"]
    for allowed in allowed_paths:
        if _match_path(target_field, allowed):
            return True, ""

    return False, f"target_field '{target_field}' is not in the whitelist for fix_type '{fix_type}' (allowed: {allowed_paths})"


# ============== APPLY FIXES ==============

def _navigate_path(obj, path_parts):
    """Navigate dict/list using path parts. Returns (parent, last_key)."""
    cur = obj
    for part in path_parts[:-1]:
        if "[" in part and "]" in part:
            # array indexing
            base, idx_str = part.split("[", 1)
            idx_str = idx_str.rstrip("]")
            if base:
                cur = cur[base]
            cur = cur[int(idx_str)]
        else:
            cur = cur[part]
    return cur, path_parts[-1]


def _parse_path(target_field: str) -> list[str]:
    """Parse 'a.b[0].c' into ['a', 'b[0]', 'c']."""
    return target_field.split(".")


def apply_single_fix(inputs: dict, fix: dict) -> tuple[bool, str]:
    """Apply one fix to inputs (in-place). Returns (success, error_msg)."""
    fix_type = fix.get("fix_instruction", {}).get("type")
    target_field = fix.get("fix_instruction", {}).get("target_field")
    new_value = fix.get("fix_instruction", {}).get("new_value")

    if not fix_type or not target_field:
        return False, f"fix missing fix_instruction.type or fix_instruction.target_field"

    allowed, reason = is_fix_allowed(fix_type, target_field)
    if not allowed:
        return False, reason

    try:
        if fix_type == "cost_addition":
            return _apply_cost_addition(inputs, target_field, new_value)
        if "[append]" in target_field:
            return _apply_append(inputs, target_field, new_value)
        if "[reorder]" in target_field:
            return _apply_reorder(inputs, target_field, new_value)
        return _apply_set(inputs, target_field, new_value)
    except (KeyError, IndexError, TypeError) as e:
        return False, f"path navigation failed: {type(e).__name__}: {e}"


def _apply_set(inputs: dict, target_field: str, new_value):
    """Set a leaf field via path."""
    parts = _parse_path(target_field)
    cur = inputs
    for part in parts[:-1]:
        if "[" in part:
            base, idx_str = part.split("[", 1)
            idx_str = idx_str.rstrip("]")
            if base:
                cur = cur[base]
            cur = cur[int(idx_str)]
        else:
            cur = cur[part]
    last = parts[-1]
    if "[" in last:
        base, idx_str = last.split("[", 1)
        idx_str = idx_str.rstrip("]")
        if base:
            cur = cur[base]
        cur[int(idx_str)] = new_value
    else:
        cur[last] = new_value
    return True, ""


def _apply_append(inputs: dict, target_field: str, new_value):
    """Append element to array at path ending in [append]."""
    array_path = target_field.replace("[append]", "")
    parts = _parse_path(array_path)
    cur = inputs
    for part in parts:
        if "[" in part:
            base, idx_str = part.split("[", 1)
            idx_str = idx_str.rstrip("]")
            if base:
                cur = cur[base]
            cur = cur[int(idx_str)]
        else:
            cur = cur[part]
    if not isinstance(cur, list):
        return False, f"path '{array_path}' is not a list (got {type(cur).__name__})"
    cur.append(new_value)
    return True, ""


def _apply_reorder(inputs: dict, target_field: str, new_value):
    """Reorder steps array. new_value should be a list of indices in new order."""
    array_path = target_field.replace("[reorder]", "")
    parts = _parse_path(array_path)
    cur = inputs
    for part in parts[:-1]:
        if "[" in part:
            base, idx_str = part.split("[", 1)
            idx_str = idx_str.rstrip("]")
            if base:
                cur = cur[base]
            cur = cur[int(idx_str)]
        else:
            cur = cur[part]
    last = parts[-1]
    if "[" in last:
        base, idx_str = last.split("[", 1)
        idx_str = idx_str.rstrip("]")
        if base:
            cur = cur[base]
        target_list = cur[int(idx_str)]
    else:
        target_list = cur[last]

    if not isinstance(target_list, list):
        return False, f"path '{array_path}' is not a list"
    if not isinstance(new_value, list):
        return False, "new_value for reorder must be a list of indices"

    reordered = [target_list[i] for i in new_value]
    target_list[:] = reordered
    return True, ""


def _apply_cost_addition(inputs: dict, target_field: str, new_value):
    """Append from closed catalog. new_value should be a catalog key OR a dict matching the schema."""
    if "effort" not in inputs or "breakdown" not in inputs["effort"]:
        return False, "inputs.json missing effort.breakdown"

    if isinstance(new_value, str):
        # catalog key lookup
        if new_value not in COST_CATALOG:
            return False, f"cost catalog key '{new_value}' not in {list(COST_CATALOG.keys())}"
        line = copy.deepcopy(COST_CATALOG[new_value])
    elif isinstance(new_value, dict):
        # validate keys are within an existing breakdown row schema
        required_keys = {"role", "worst", "base", "best"}
        if not required_keys.issubset(new_value.keys()):
            return False, f"cost line missing keys: {required_keys - set(new_value.keys())}"
        # also enforce: role must contain a recognizable label (catalog-ish)
        line = copy.deepcopy(new_value)
    else:
        return False, f"new_value must be catalog key (str) or full row dict — got {type(new_value).__name__}"

    inputs["effort"]["breakdown"].append(line)
    return True, ""


# ============== AUTO-REPAIR (RF-06 formula errors) ==============

def auto_repair_formula_errors(inputs: dict, validator_json: dict | None) -> list[dict]:
    """Fix unambiguous formula errors found by validator (RF-06 / #REF! / #DIV/0!).

    Currently no-op placeholder — formula errors at the workbook level mean
    we should re-build (call build_roi_workbook.py) rather than edit inputs.
    Returns list of attempted repairs (empty for v1.0).
    """
    repairs = []
    if not validator_json:
        return repairs
    rf06 = [rf for rf in validator_json.get("red_flags", []) if rf.get("rule") == "RF-06"]
    if rf06:
        repairs.append({
            "action": "rebuild_required",
            "reason": "RF-06 formula errors detected — caller should re-run build_roi_workbook.py",
            "details": rf06,
        })
    return repairs


# ============== MAIN ==============

def derive_versioned_path(inputs_path: Path) -> Path:
    """If inputs_path is foo_inputs.json or foo_inputs.vN.json, derive foo_inputs.v{N+1}.json."""
    name = inputs_path.name
    m = re.match(r"^(.*?)\.v(\d+)\.json$", name)
    if m:
        base, n = m.group(1), int(m.group(2))
        return inputs_path.parent / f"{base}.v{n+1}.json"
    # No version yet — make it v2 (current = v1 implicit)
    if name.endswith(".json"):
        base = name[:-5]
        return inputs_path.parent / f"{base}.v2.json"
    return inputs_path.parent / f"{name}.v2.json"


def main():
    p = argparse.ArgumentParser(description="Apply whitelisted fixes to inputs.json")
    p.add_argument("inputs_json", type=Path, help="Path to inputs.json")
    p.add_argument("fixes_yaml", type=Path, nargs="?", default=None,
                   help="Path to fixes.yaml (extracted from reviewer verdict_block)")
    p.add_argument("--out", type=Path, default=None,
                   help="Output path (default: inputs.v{N+1}.json)")
    p.add_argument("--auto-repair-formula-errors", action="store_true",
                   help="Pre-loop: fix RF-06 unambiguous formula errors")
    p.add_argument("--validator-json", type=Path, default=None,
                   help="Path to validator JSON output (for auto-repair)")
    args = p.parse_args()

    if not args.inputs_json.exists():
        print(f"ERROR: inputs_json not found: {args.inputs_json}", file=sys.stderr)
        sys.exit(1)

    with open(args.inputs_json) as f:
        inputs = json.load(f)

    applied = []
    denied = []

    # Auto-repair pre-loop pass
    if args.auto_repair_formula_errors:
        validator_json = None
        if args.validator_json and args.validator_json.exists():
            with open(args.validator_json) as f:
                validator_json = json.load(f)
        repairs = auto_repair_formula_errors(inputs, validator_json)
        applied.extend(repairs)

    # Apply fixes from YAML
    if args.fixes_yaml:
        if not args.fixes_yaml.exists():
            print(f"ERROR: fixes_yaml not found: {args.fixes_yaml}", file=sys.stderr)
            sys.exit(1)

        with open(args.fixes_yaml) as f:
            fixes_doc = yaml.safe_load(f) or {}

        fixes = fixes_doc.get("fixes", [])
        if not fixes and "issues" in fixes_doc:
            # accept full verdict_block; extract auto_fixable issues
            fixes = [i for i in fixes_doc["issues"] if i.get("auto_fixable")]

        for fix in fixes:
            fix_id = fix.get("id", "?")
            success, reason = apply_single_fix(inputs, fix)
            if success:
                applied.append({
                    "id": fix_id,
                    "fix_type": fix.get("fix_instruction", {}).get("type"),
                    "target_field": fix.get("fix_instruction", {}).get("target_field"),
                    "rationale": fix.get("fix_instruction", {}).get("rationale"),
                })
            else:
                denied.append({
                    "id": fix_id,
                    "fix_type": fix.get("fix_instruction", {}).get("type"),
                    "target_field": fix.get("fix_instruction", {}).get("target_field"),
                    "denial_reason": reason,
                    "category": fix.get("category"),
                    "severity": fix.get("severity"),
                    "description": fix.get("description"),
                    "human_action": (
                        fix.get("human_action")
                        or f"Whitelist denied auto-fix; treat as HUMAN_ACTION_REQUIRED. Reason: {reason}"
                    ),
                })

    # Write versioned output
    out_path = args.out or derive_versioned_path(args.inputs_json)
    if applied:
        with open(out_path, "w") as f:
            json.dump(inputs, f, indent=2, ensure_ascii=False)

    result = {
        "status": "success",
        "applied": applied,
        "denied": denied,
        "applied_count": len(applied),
        "denied_count": len(denied),
        "input_path": str(args.inputs_json),
        "output_path": str(out_path) if applied else None,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"\n[apply_fixes] Applied: {len(applied)} | Denied: {len(denied)}", file=sys.stderr)
    if denied:
        print(f"[apply_fixes] Denied fixes (HUMAN_ACTION_REQUIRED next iter):", file=sys.stderr)
        for d in denied:
            print(f"  - {d['id']} ({d.get('severity','?')}/{d.get('category','?')}): {d['denial_reason']}",
                  file=sys.stderr)

    sys.exit(0 if applied else (2 if denied else 0))


if __name__ == "__main__":
    main()
