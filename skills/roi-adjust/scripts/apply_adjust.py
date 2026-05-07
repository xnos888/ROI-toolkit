#!/usr/bin/env python3
"""
apply_adjust.py — Execute the cascade for an approved roi-adjust.

Workflow:
    1. Version current inputs.json → inputs.v{N}.json (audit trail)
    2. Apply change.field_path = change.new_value to inputs.json
    3. Rebuild xlsx workbook (full rebuild for MEDIUM+, patch-only logic stub for LIGHT)
    4. Recalc + validate
    5. Regenerate summary.md
    6. Tier shift detection → mark prior reviewer .stale if shifted
    7. Print handoff signal for roi-portfolio (caller actually invokes the skill)

Usage:
    python apply_adjust.py <inputs.json> <change.json> <classification.json> <output_dir>

Optional:
    --dry-run            : show what would happen, don't modify files
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).parent


def set_nested(data: dict, path: str, new_value):
    """Set nested value using dotted path with [N] for arrays."""
    parts = []
    for token in path.split("."):
        if "[" in token:
            field, idx_str = token.split("[")
            idx = int(idx_str.rstrip("]"))
            parts.append((field, idx))
        else:
            parts.append((token, None))

    cursor = data
    for i, (field, idx) in enumerate(parts):
        is_last = (i == len(parts) - 1)
        if is_last:
            if idx is None:
                cursor[field] = new_value
            else:
                cursor[field][idx] = new_value
        else:
            cursor = cursor[field] if idx is None else cursor[field][idx]


def next_version_number(inputs_dir: Path, code: str) -> int:
    """Find next .vN suffix that doesn't exist yet."""
    existing = list(inputs_dir.glob(f"{code}_inputs.v*.json"))
    nums = []
    for p in existing:
        m = re.search(r"\.v(\d+)\.json$", p.name)
        if m:
            nums.append(int(m.group(1)))
    return max(nums, default=0) + 1


def archive_old_versions(inputs_dir: Path, code: str, keep: int = 5):
    """Move versions beyond keep limit to _archive/."""
    archive_dir = inputs_dir / "_archive"
    versions = sorted(
        inputs_dir.glob(f"{code}_inputs.v*.json"),
        key=lambda p: int(re.search(r"\.v(\d+)", p.name).group(1)),
        reverse=True,
    )
    if len(versions) > keep:
        archive_dir.mkdir(exist_ok=True)
        for old in versions[keep:]:
            shutil.move(str(old), archive_dir / old.name)


def run_script(script_name: str, *args, cwd: Path = None) -> subprocess.CompletedProcess:
    """Invoke a bundled script via subprocess. Returns the completed process."""
    script_path = SCRIPT_DIR / script_name
    cmd = [sys.executable, str(script_path)] + [str(a) for a in args]
    return subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=cwd)


def detect_tier(y1_roi: float | None) -> str | None:
    """Return tier emoji+label for a Y1 Base ROI."""
    if y1_roi is None:
        return None
    if y1_roi >= 5: return "🟢 STRONG GO"
    if y1_roi >= 1.5: return "🟡 CONDITIONAL"
    if y1_roi >= 1.0: return "🟠 DEFER"
    return "🔴 KILL"


def mark_reviewer_stale(review_dir: Path, code: str):
    """Rename current iter reviewer outputs to .stale (preserve audit trail)."""
    if not review_dir.exists():
        return []
    stale_marked = []
    for pattern in [f"{code}_iter_*_cfo.md", f"{code}_iter_*_hop.md",
                    f"{code}_iter_history.json", f"{code}_escalation.md"]:
        for p in review_dir.glob(pattern):
            if p.name.endswith(".stale"):
                continue
            new = p.with_suffix(p.suffix + ".stale")
            shutil.move(str(p), str(new))
            stale_marked.append(p.name)
    return stale_marked


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs_json", type=Path)
    parser.add_argument("change_json", type=Path)
    parser.add_argument("classification_json", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    inputs = json.loads(args.inputs_json.read_text())
    change = json.loads(args.change_json.read_text())
    classification = json.loads(args.classification_json.read_text())

    code = inputs["feature"]["code"]
    inputs_dir = args.inputs_json.parent
    severity = classification["severity"]

    if severity == "STRUCTURAL":
        print(json.dumps({
            "status": "ESCALATE",
            "reason": "STRUCTURAL change — escalate to roi-build for full restart.",
            "code": code,
        }, indent=2, ensure_ascii=False))
        sys.exit(0)

    # Capture pre-state ROI for tier-shift detection
    prev_y1 = inputs.get("_meta", {}).get("last_y1_base_roi")
    prev_tier = detect_tier(prev_y1)

    if args.dry_run:
        # Apply in-memory only, predict outcome, don't touch files
        set_nested(inputs, change["field_path"], change["new_value"])
        print(json.dumps({
            "status": "DRY_RUN",
            "would_set": f"{change['field_path']} = {change['new_value']}",
            "severity": severity,
            "downstream": classification["downstream_files"],
            "prev_tier": prev_tier,
        }, indent=2, ensure_ascii=False))
        return

    # === STEP 5a: Version inputs.json ===
    next_n = next_version_number(inputs_dir, code)
    version_path = inputs_dir / f"{code}_inputs.v{next_n}.json"
    shutil.copy(args.inputs_json, version_path)

    # === STEP 5b: Update inputs.json ===
    if classification.get("research_frozen_override"):
        # Force tier=T4 on overridden CF
        if "conversion_factors" in change["field_path"]:
            m = re.match(r"^conversion_factors\[(\d+)\]", change["field_path"])
            if m:
                idx = int(m.group(1))
                inputs["conversion_factors"][idx]["tier"] = "T4"
                # Append warning to source
                src = inputs["conversion_factors"][idx].get("source", "")
                inputs["conversion_factors"][idx]["source"] = (
                    f"{src} | OVERRIDE {datetime.now().strftime('%Y-%m-%d')}: "
                    f"manual user override, tier forced T4 (anti-confirmation-bias)."
                )

    set_nested(inputs, change["field_path"], change["new_value"])
    inputs["_meta"] = inputs.get("_meta", {})
    inputs["_meta"]["last_adjust"] = {
        "timestamp": datetime.now().isoformat(),
        "field_path": change["field_path"],
        "old_version_file": version_path.name,
        "rationale": change.get("rationale", ""),
    }
    args.inputs_json.write_text(json.dumps(inputs, indent=2, ensure_ascii=False), encoding="utf-8")

    # === STEP 5c: Rebuild xlsx ===
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rebuild = run_script("build_roi_workbook.py", args.inputs_json, args.output_dir)
    if rebuild.returncode != 0:
        print(json.dumps({
            "status": "REBUILD_FAILED",
            "stderr": rebuild.stderr[-500:],
            "stdout": rebuild.stdout[-500:],
            "rollback_with": f"cp {version_path} {args.inputs_json}",
        }, indent=2, ensure_ascii=False))
        sys.exit(1)

    workbook = args.output_dir / f"{code}_ROI.xlsx"

    # === STEP 5d: Recalc + validate ===
    run_script("recalc.py", workbook)
    val = run_script("validate_roi.py", workbook)
    try:
        validator_out = json.loads(val.stdout)
    except json.JSONDecodeError:
        validator_out = {"status": "error", "stdout": val.stdout, "stderr": val.stderr}

    new_y1 = validator_out.get("metrics", {}).get("y1_roi_base")
    new_y3 = validator_out.get("metrics", {}).get("y3_roi_base")
    new_tier = detect_tier(new_y1)

    # Persist new ROI to _meta for next adjust
    inputs["_meta"]["last_y1_base_roi"] = new_y1
    inputs["_meta"]["last_y3_base_roi"] = new_y3
    inputs["_meta"]["last_tier"] = new_tier
    args.inputs_json.write_text(json.dumps(inputs, indent=2, ensure_ascii=False), encoding="utf-8")

    # === STEP 5e: Regen summary ===
    summary_path = args.output_dir / f"{code}_summary.md"
    validator_path = args.output_dir / f"{code}_validator.json"
    validator_path.write_text(json.dumps(validator_out, indent=2, ensure_ascii=False), encoding="utf-8")
    run_script("generate_summary.py", workbook, validator_path, summary_path)

    # === STEP 5f: Tier shift check ===
    review_dir = workbook.parent / "review"
    stale_marked = []
    tier_shifted = (prev_tier and new_tier and prev_tier != new_tier)
    if tier_shifted or classification.get("requires_re_research"):
        stale_marked = mark_reviewer_stale(review_dir, code)

    # === STEP 6: Print handoff signal for caller ===
    result = {
        "status": "ADJUST_COMPLETE",
        "code": code,
        "severity": severity,
        "field_path": change["field_path"],
        "old_version_file": version_path.name,
        "workbook": str(workbook),
        "summary": str(summary_path),
        "roi_delta": {
            "prev_y1": prev_y1,
            "new_y1": new_y1,
            "prev_tier": prev_tier,
            "new_tier": new_tier,
            "tier_shifted": tier_shifted,
        },
        "reviewer_files_marked_stale": stale_marked,
        "next_action": "Invoke roi-portfolio (Mode A: single-feature refresh) to update Pipeline_Summary + Phase_Plan",
        "recommend_re_review": classification["recommend_re_review"] and tier_shifted,
    }

    archive_old_versions(inputs_dir, code, keep=5)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
