#!/usr/bin/env python3
"""
review_loop.py — orchestrator for the mandatory iterative CFO+HoP review loop.

This script CANNOT spawn sub-agents directly (it's a Python script, not a Claude
agent). Instead it operates in two modes that bracket Claude-mediated sub-agent
invocations:

    Mode 1: --prep --iter N
        Generates iter_N prompt files for CFO + HoP sub-agents.
        Claude (parent) reads these prompts and dispatches both sub-agents in
        parallel via the Task tool, capturing outputs to:
            review/<CODE>_iter_N_cfo.md
            review/<CODE>_iter_N_hop.md

    Mode 2: --continue --iter N
        Parses verdict_block YAML from saved sub-agent outputs, runs apply_fixes
        on auto-fixable CRITICAL issues, rebuilds the workbook, and decides:
          - both APPROVE + zero CRITICAL/HIGH → exits with status APPROVE
          - has auto-fixable CRITICAL → applies fixes, returns NEXT_ITER signal
          - all blocking are human-required → returns ESCALATE
          - max iter reached → returns ESCALATE

Mode 3: --auto (orchestrator-friendly mode for testing without sub-agents — uses
    a stub reviewer that always APPROVEs. Useful for smoke testing the loop
    machinery; not for real reviews.)

Standard usage:
    # Initial preparation
    python review_loop.py <workbook> <inputs.json> --prep --iter 1

    # ... Claude dispatches sub-agents to write review/<CODE>_iter_1_*.md ...

    # Continue: parse, fix, rebuild, decide
    python review_loop.py <workbook> <inputs.json> --continue --iter 1
    # → exits with one of: APPROVE | NEXT_ITER | ESCALATE
"""

import argparse
import copy
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Run: python3 -m pip install --user --break-system-packages pyyaml", file=sys.stderr)
    sys.exit(1)


SCRIPT_DIR = Path(__file__).parent
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATES_DIR = SKILL_DIR / "templates"

DEFAULT_MAX_ITERS = 2  # v2.0 — Lever C optimization (was 3). Override via inputs.json feature.max_review_iters for high-stakes features.


# ============== HELPERS ==============

def _load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def _save_json(path: Path, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _feature_code(inputs: dict) -> str:
    return inputs["feature"]["code"]


def _review_dir(workbook: Path) -> Path:
    """review/ folder lives next to the workbook."""
    d = workbook.parent / "review"
    d.mkdir(exist_ok=True)
    return d


def _history_path(workbook: Path, code: str) -> Path:
    return _review_dir(workbook) / f"{code}_iter_history.json"


def _load_history(workbook: Path, code: str) -> dict:
    p = _history_path(workbook, code)
    if p.exists():
        return _load_json(p)
    return {"feature_code": code, "workbook": str(workbook), "iterations": []}


def _save_history(workbook: Path, code: str, history: dict):
    _save_json(_history_path(workbook, code), history)


def _extract_yaml_verdict_block(md_path: Path) -> dict | None:
    """Parse fenced ```yaml block under '## Machine-Readable Verdict' header."""
    if not md_path.exists():
        return None
    text = md_path.read_text()
    # Find ```yaml ... ``` block (greedy match to last triple-backtick before EOF)
    m = re.search(r"```yaml\s*\n(.*?)\n```", text, re.DOTALL)
    if not m:
        return None
    try:
        parsed = yaml.safe_load(m.group(1))
        return parsed.get("verdict_block") if isinstance(parsed, dict) else None
    except yaml.YAMLError as e:
        print(f"[review_loop] WARN: YAML parse error in {md_path}: {e}", file=sys.stderr)
        return None


def _run_validator(workbook: Path) -> dict:
    """Invoke validate_roi.py. Returns parsed JSON."""
    validator = SCRIPT_DIR / "validate_roi.py"
    result = subprocess.run(
        [sys.executable, str(validator), str(workbook)],
        capture_output=True, text=True, check=False
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"status": "error", "stderr": result.stderr, "stdout": result.stdout}


def _rebuild_workbook(inputs_path: Path, output_dir: Path) -> Path:
    """Invoke build_roi_workbook.py. Returns path to rebuilt xlsx."""
    builder = SCRIPT_DIR / "build_roi_workbook.py"
    result = subprocess.run(
        [sys.executable, str(builder), str(inputs_path), str(output_dir)],
        capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        print(f"[review_loop] ERROR: build_roi_workbook failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    # Recalc cached values
    recalc = SCRIPT_DIR / "recalc.py"
    code = _load_json(inputs_path)["feature"]["code"]
    wb_path = output_dir / f"{code}_ROI.xlsx"
    subprocess.run([sys.executable, str(recalc), str(wb_path)], check=False, capture_output=True)
    return wb_path


def _extract_roi_snapshot(validator_out: dict) -> dict:
    """Pull Y1/3Y Base ROI from validator metrics."""
    m = validator_out.get("metrics", {}) or {}
    return {
        "y1_base": m.get("y1_roi_base"),
        "y1_best": m.get("y1_roi_best"),
        "y3_base": m.get("y3_roi_base"),
    }


def _fmt_roi(snap: dict) -> str:
    if not snap or snap.get("y1_base") is None:
        return "N/A"
    return f"Y1 {snap['y1_base']:.2f}x | 3Y {snap['y3_base']:.2f}x"


# ============== PROMPT FILE GENERATION ==============

PROMPT_HEADER = """# {role} Review — {code} (iter {iter})

You are reviewing the per-feature ROI workbook for **{code}** at iteration **{iter}**.

## Files to read

- Workbook: `{workbook_path}`  (6 sheets)
- Inputs JSON: `{inputs_path}`
- Validator output: `{validator_path}`
- Hospital baseline DB: `{baseline_db}`
- Reviewer agent instructions (READ FIRST, in full): `{agent_md}`

## Output paths

- Save your review markdown to: `{output_md}`
- Final block MUST be a fenced ```yaml verdict_block matching `templates/reviewer_verdict_schema.yaml`

## Mandatory contracts

1. **APPROVE = methodological correctness, NOT financial threshold.** Honest-low ROI APPROVES if math is correct.
2. **You MAY NOT mark "low ROI" as Critical or High.** Only mark Critical/High if the ROI is *wrong* (a bug exists).
3. **YAML verdict_block at end of file** is mandatory. Parser will treat missing/invalid YAML as REJECT-CRITICAL.
4. **Whitelist for auto_fixable**: see agent_md "Forbidden auto-fix targets" — do NOT mark forbidden fields as auto_fixable.

"""

PROMPT_ITER1_NOTE = """## Iteration context

This is iteration **1** — first review of this workbook.
"""

PROMPT_ITER_N_NOTE = """## Iteration context

This is iteration **{iter}** (of max {max_iters}).

### Prior iteration history

{prior_history_md}

### Anti-sycophancy contract

You MUST re-read all 6 sheets fresh and verify each prior CRITICAL/HIGH issue independently.

- Do NOT lower severity of unresolved prior issues just because effort was spent.
- If prior fix introduced a NEW bug, flag it CRITICAL.
- If you DO downgrade a prior issue, populate `iteration_check.softened_verdicts` with explicit justification — this is audited.
- Discovery debt does NOT resolve via inputs.json text edits. Real research must have happened between iters.

If after re-reading you find the same blockers persist with no real change → **REJECT again with the same severity**. Escalation to user at iter {max_iters} is the correct outcome, not "let it pass."
"""


def _format_prior_history(history: dict, current_iter: int) -> str:
    """Render prior iters as markdown for inclusion in iter N prompt."""
    lines = []
    for it in history.get("iterations", [])[: current_iter - 1]:
        n = it["iter"]
        outcome = it.get("outcome", "?")
        roi = _fmt_roi(it.get("roi_snapshot", {}))
        lines.append(f"#### Iter {n} — outcome: {outcome} | ROI: {roi}")
        for v in it.get("verdicts", []):
            reviewer = v.get("reviewer", "?")
            verdict = v.get("verdict", "?")
            basis = v.get("verdict_basis", "")
            n_crit = sum(1 for i in v.get("issues", []) if i.get("severity") == "CRITICAL")
            n_high = sum(1 for i in v.get("issues", []) if i.get("severity") == "HIGH")
            lines.append(f"  - **{reviewer.upper()}**: {verdict} ({n_crit} CRITICAL, {n_high} HIGH) — {basis}")
        applied = it.get("fixes_applied", [])
        denied = it.get("fixes_denied", [])
        if applied:
            lines.append(f"  - Fixes applied: {len(applied)} ({', '.join(a.get('id','?') for a in applied)})")
        if denied:
            lines.append(f"  - Fixes denied (whitelist rejected): {len(denied)} ({', '.join(d.get('id','?') for d in denied)})")
        lines.append("")
    return "\n".join(lines) if lines else "(none)"


def _generate_prompt(role: str, args, paths: dict, history: dict) -> str:
    """role = 'cfo' or 'hop'."""
    role_label = "CFO" if role == "cfo" else "Head of Product"
    agent_md = SKILL_DIR / "agents" / ("cfo_reviewer.md" if role == "cfo" else "head_of_product_reviewer.md")
    output_md = paths["review_dir"] / f"{paths['code']}_iter_{args.iter}_{role}.md"

    header = PROMPT_HEADER.format(
        role=role_label,
        code=paths["code"],
        iter=args.iter,
        workbook_path=paths["workbook"],
        inputs_path=paths["inputs"],
        validator_path=paths["validator_path"],
        baseline_db=paths["baseline_db"],
        agent_md=agent_md,
        output_md=output_md,
    )
    if args.iter == 1:
        return header + "\n" + PROMPT_ITER1_NOTE
    return header + "\n" + PROMPT_ITER_N_NOTE.format(
        iter=args.iter,
        max_iters=args.max_iters,
        prior_history_md=_format_prior_history(history, args.iter),
    )


# ============== PREP MODE ==============

def cmd_prep(args, workbook: Path, inputs_path: Path):
    """Mode 1: write iter prompt files for both reviewers."""
    inputs = _load_json(inputs_path)
    code = _feature_code(inputs)
    review_dir = _review_dir(workbook)
    history = _load_history(workbook, code)

    # Run validator and snapshot output
    validator_out = _run_validator(workbook)
    validator_path = review_dir / f"{code}_iter_{args.iter}_validator.json"
    _save_json(validator_path, validator_out)

    paths = {
        "code": code,
        "workbook": workbook.resolve(),
        "inputs": inputs_path.resolve(),
        "validator_path": validator_path.resolve(),
        "baseline_db": (workbook.parent.parent / "Hospital_Baseline_DB.xlsx").resolve(),
        "review_dir": review_dir.resolve(),
    }

    cfo_prompt = _generate_prompt("cfo", args, paths, history)
    hop_prompt = _generate_prompt("hop", args, paths, history)

    cfo_path = review_dir / f"{code}_iter_{args.iter}_prompt_cfo.md"
    hop_path = review_dir / f"{code}_iter_{args.iter}_prompt_hop.md"
    cfo_path.write_text(cfo_prompt)
    hop_path.write_text(hop_prompt)

    result = {
        "status": "prep_complete",
        "iter": args.iter,
        "feature_code": code,
        "prompts": {
            "cfo": str(cfo_path),
            "hop": str(hop_path),
        },
        "expected_outputs": {
            "cfo": str(review_dir / f"{code}_iter_{args.iter}_cfo.md"),
            "hop": str(review_dir / f"{code}_iter_{args.iter}_hop.md"),
        },
        "validator_snapshot": validator_path.name,
        "roi_snapshot": _extract_roi_snapshot(validator_out),
        "next_action": (
            f"Claude orchestrator: dispatch CFO + HoP sub-agents in parallel "
            f"using prompts above. After both save outputs, run: "
            f"python review_loop.py {workbook} {inputs_path} --continue --iter {args.iter}"
        ),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


# ============== CONTINUE MODE ==============

def cmd_continue(args, workbook: Path, inputs_path: Path):
    """Mode 2: parse reviewer outputs, gate, fix, rebuild, decide."""
    inputs = _load_json(inputs_path)
    code = _feature_code(inputs)
    review_dir = _review_dir(workbook)
    history = _load_history(workbook, code)

    cfo_md = review_dir / f"{code}_iter_{args.iter}_cfo.md"
    hop_md = review_dir / f"{code}_iter_{args.iter}_hop.md"

    cfo_v = _extract_yaml_verdict_block(cfo_md)
    hop_v = _extract_yaml_verdict_block(hop_md)

    # Defensive: missing verdict block = treat as REJECT-CRITICAL
    if cfo_v is None:
        cfo_v = {"reviewer": "cfo", "iteration": args.iter, "verdict": "REJECT",
                 "verdict_basis": "MISSING or invalid YAML verdict_block in CFO output",
                 "issues": [{"id": "SCHEMA1", "severity": "CRITICAL", "category": "other",
                             "cell_ref": str(cfo_md), "description": "CFO output missing parseable verdict_block",
                             "auto_fixable": False, "human_action": "Re-run CFO sub-agent with strict YAML schema enforcement"}]}
    if hop_v is None:
        hop_v = {"reviewer": "hop", "iteration": args.iter, "verdict": "REJECT",
                 "verdict_basis": "MISSING or invalid YAML verdict_block in HoP output",
                 "issues": [{"id": "SCHEMA2", "severity": "CRITICAL", "category": "other",
                             "cell_ref": str(hop_md), "description": "HoP output missing parseable verdict_block",
                             "auto_fixable": False, "human_action": "Re-run HoP sub-agent with strict YAML schema enforcement"}]}

    all_issues = (cfo_v.get("issues") or []) + (hop_v.get("issues") or [])
    critical = [i for i in all_issues if i.get("severity") == "CRITICAL"]
    high = [i for i in all_issues if i.get("severity") == "HIGH"]

    # Gate: both APPROVE + zero CRITICAL/HIGH → APPROVED
    if (cfo_v.get("verdict") == "APPROVE"
            and hop_v.get("verdict") == "APPROVE"
            and not critical and not high):
        # Snapshot final iter
        validator_out = _run_validator(workbook)
        roi_snap = _extract_roi_snapshot(validator_out)
        history["iterations"].append({
            "iter": args.iter,
            "outcome": "APPROVE",
            "verdicts": [cfo_v, hop_v],
            "roi_snapshot": roi_snap,
            "timestamp": datetime.now().isoformat(),
        })
        _save_history(workbook, code, history)
        result = {
            "status": "APPROVE",
            "iter": args.iter,
            "roi_snapshot": roi_snap,
            "history_path": str(_history_path(workbook, code)),
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    # Triage critical issues
    auto_fixable = [i for i in critical if i.get("auto_fixable")]
    human_required = [i for i in critical if not i.get("auto_fixable")] + high

    # Early exit: nothing fix_executor can do
    if not auto_fixable:
        return _escalate(args, workbook, inputs_path, code, history,
                         reason="no_autofix_possible",
                         cfo_v=cfo_v, hop_v=hop_v,
                         human_required=human_required)

    # Apply auto-fixes
    fixes_yaml_path = review_dir / f"{code}_iter_{args.iter}_fixes.yaml"
    fixes_doc = {"fixes": auto_fixable}
    with open(fixes_yaml_path, "w") as f:
        yaml.dump(fixes_doc, f, sort_keys=False, allow_unicode=True)

    apply_script = SCRIPT_DIR / "apply_fixes.py"
    result = subprocess.run(
        [sys.executable, str(apply_script), str(inputs_path), str(fixes_yaml_path)],
        capture_output=True, text=True, check=False
    )
    try:
        apply_result = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"[review_loop] ERROR: apply_fixes returned non-JSON:\n{result.stdout}\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    new_inputs_path = Path(apply_result["output_path"]) if apply_result.get("output_path") else inputs_path

    # Rebuild workbook with new inputs
    new_workbook = _rebuild_workbook(new_inputs_path, workbook.parent) if apply_result["applied_count"] else workbook

    # Update inputs symlink to point to latest version
    _update_inputs_symlink(inputs_path, new_inputs_path)

    # Snapshot iter
    validator_out_post = _run_validator(new_workbook)
    roi_snap = _extract_roi_snapshot(validator_out_post)

    history["iterations"].append({
        "iter": args.iter,
        "outcome": "FIXES_APPLIED",
        "verdicts": [cfo_v, hop_v],
        "fixes_applied": apply_result["applied"],
        "fixes_denied": apply_result["denied"],
        "inputs_version": str(new_inputs_path),
        "workbook_after": str(new_workbook),
        "roi_snapshot": roi_snap,
        "timestamp": datetime.now().isoformat(),
    })
    _save_history(workbook, code, history)

    # Check if we hit max iter
    if args.iter >= args.max_iters:
        return _escalate(args, new_workbook, new_inputs_path, code, history,
                         reason="max_iters_reached",
                         cfo_v=cfo_v, hop_v=hop_v,
                         human_required=human_required)

    # Signal NEXT_ITER
    result_obj = {
        "status": "NEXT_ITER",
        "iter": args.iter,
        "next_iter": args.iter + 1,
        "fixes_applied": apply_result["applied_count"],
        "fixes_denied": apply_result["denied_count"],
        "new_inputs_path": str(new_inputs_path),
        "new_workbook": str(new_workbook),
        "roi_snapshot": roi_snap,
        "next_action": (
            f"Run: python review_loop.py {new_workbook} {new_inputs_path} "
            f"--prep --iter {args.iter + 1}"
        ),
    }
    print(json.dumps(result_obj, indent=2, ensure_ascii=False))
    return 0


def _update_inputs_symlink(symlink_path: Path, target: Path):
    """Make symlink_path point to target. If symlink_path is regular file, leave as-is."""
    # Only manage symlink if symlink_path is already a symlink, or doesn't exist
    if symlink_path.is_symlink():
        symlink_path.unlink()
        symlink_path.symlink_to(target.name)


def _escalate(args, workbook: Path, inputs_path: Path, code: str, history: dict,
              reason: str, cfo_v: dict, hop_v: dict, human_required: list):
    """Generate escalation.md and return ESCALATE result."""
    review_dir = _review_dir(workbook)
    template = TEMPLATES_DIR / "escalation.md"
    if not template.exists():
        print(f"[review_loop] WARN: escalation template not found at {template}", file=sys.stderr)
        template_text = "# Escalation\n\n{REASON}\n\n## Unresolved\n{UNRESOLVED_TABLE}\n"
    else:
        template_text = template.read_text()

    # Cumulative diff
    v1_path = inputs_path.parent / f"{code}_inputs.v1.json"
    if not v1_path.exists():
        v1_path = inputs_path.parent / f"{code}_inputs.json"
    diff_text = _compute_diff(v1_path, inputs_path)

    # Build unresolved table
    unresolved_rows = []
    for issue in human_required:
        unresolved_rows.append(
            f"| {issue.get('id','?')} | {(cfo_v.get('issues') or hop_v.get('issues') or [])[0].get('reviewer', '?') if False else '?'} | "
            f"{issue.get('severity','?')} | {issue.get('category','?')} | "
            f"{(issue.get('description') or '')[:80]} | "
            f"{(issue.get('human_action') or 'whitelist denied')[:80]} |"
        )
    unresolved_table = "\n".join(unresolved_rows) or "| (none) | | | | | |"

    # ROI movement
    roi_rows = []
    for it in history.get("iterations", []):
        snap = it.get("roi_snapshot", {})
        roi_rows.append(f"| iter {it.get('iter','?')} | {snap.get('y1_base', '?')} | {snap.get('y3_base', '?')} |")
    roi_movement = "| iter | Y1 Base | 3Y Base |\n|---|---|---|\n" + "\n".join(roi_rows) if roi_rows else "(none)"

    # Iter history rendered as block
    iter_history_section = json.dumps(history.get("iterations", []), indent=2, ensure_ascii=False)

    last_snap = (history.get("iterations") or [{}])[-1].get("roi_snapshot", {}) or {}

    out = template_text
    replacements = {
        "{FEATURE_CODE}": code,
        "{REASON}": reason,
        "{DATE}": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "{WORKBOOK_PATH}": str(workbook),
        "{N}": str(args.iter),
        "{y1_worst}": str(last_snap.get("y1_worst", "?")),
        "{y1_base}": str(last_snap.get("y1_base", "?")),
        "{y1_best}": str(last_snap.get("y1_best", "?")),
        "{y3_worst}": str(last_snap.get("y3_worst", "?")),
        "{y3_base}": str(last_snap.get("y3_base", "?")),
        "{y3_best}": str(last_snap.get("y3_best", "?")),
        "{md_worst}": "?", "{md_base}": "?", "{md_best}": "?",
        "{ROI_MOVEMENT_TABLE}": roi_movement,
        "{UNIFIED_DIFF}": diff_text or "(no diff — iter 1 escalation)",
        "{n_applied}": str(sum(len(it.get("fixes_applied") or []) for it in history.get("iterations", []))),
        "{n_denied}": str(sum(len(it.get("fixes_denied") or []) for it in history.get("iterations", []))),
        "{UNRESOLVED_TABLE}": unresolved_table,
        "{INPUTS_PATH}": str(inputs_path),
        "{HISTORY_JSON_PATH}": str(_history_path(workbook, code)),
        "{ITER_HISTORY_SECTION}": "```json\n" + iter_history_section + "\n```",
    }
    for k, v in replacements.items():
        out = out.replace(k, v)

    escalation_path = review_dir / f"{code}_escalation.md"
    escalation_path.write_text(out)

    # Final history outcome — append iter snapshot (don't try to mutate non-existent last entry)
    history["iterations"].append({
        "iter": args.iter,
        "outcome": f"ESCALATE_{reason}",
        "verdicts": [cfo_v, hop_v],
        "human_required_count": len(human_required),
        "timestamp": datetime.now().isoformat(),
    })
    _save_history(workbook, code, history)

    result = {
        "status": "ESCALATE",
        "iter": args.iter,
        "reason": reason,
        "escalation_path": str(escalation_path),
        "human_required_count": len(human_required),
        "human_required": [
            {"id": i.get("id"), "severity": i.get("severity"),
             "category": i.get("category"), "human_action": i.get("human_action")}
            for i in human_required
        ],
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _compute_diff(v1: Path, vN: Path) -> str:
    """Simple diff: return unified diff between v1 and vN inputs."""
    if not v1.exists() or not vN.exists() or v1 == vN:
        return ""
    try:
        result = subprocess.run(
            ["diff", "-u", str(v1), str(vN)],
            capture_output=True, text=True, check=False
        )
        return result.stdout[:10000]  # cap at 10KB
    except FileNotFoundError:
        return f"(diff binary not available; v1={v1}, vN={vN})"


# ============== MAIN ==============

def main():
    p = argparse.ArgumentParser(description="Iterative review loop orchestrator")
    p.add_argument("workbook", type=Path, help="Path to ROI workbook .xlsx")
    p.add_argument("inputs", type=Path, help="Path to inputs.json")
    p.add_argument("--iter", type=int, required=True, help="Iteration number (1-based)")
    p.add_argument("--max-iters", type=int, default=DEFAULT_MAX_ITERS, help=f"Max iters (default {DEFAULT_MAX_ITERS})")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prep", action="store_true", help="Mode 1: prepare prompt files for sub-agents")
    mode.add_argument("--continue", dest="continue_", action="store_true", help="Mode 2: parse outputs + apply fixes + decide")
    args = p.parse_args()

    if not args.workbook.exists():
        print(f"ERROR: workbook not found: {args.workbook}", file=sys.stderr)
        return 1
    if not args.inputs.exists():
        print(f"ERROR: inputs not found: {args.inputs}", file=sys.stderr)
        return 1

    if args.iter < 1 or args.iter > args.max_iters:
        print(f"ERROR: iter must be 1..{args.max_iters}, got {args.iter}", file=sys.stderr)
        return 1

    if args.prep:
        return cmd_prep(args, args.workbook, args.inputs)
    return cmd_continue(args, args.workbook, args.inputs)


if __name__ == "__main__":
    sys.exit(main())
