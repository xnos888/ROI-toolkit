# Review Loop Protocol (canonical reference)

**Version:** v1.0
**Owner:** business-case-modeling skill
**When to load:** Step 6 (mandatory review loop) of SKILL.md

This is the long-form spec that SKILL.md references. It contains the iteration loop pseudocode, severity rubric (canonical), YAML schema, and edge-case handling.

---

## Loop architecture (high-level)

```
Pre-loop: build → validate → (auto-repair RF-06 formula errors if any) → re-validate

For iter in 1..max_iters (default 3):
  1. Run validator (snapshot to review/<CODE>_iter_N_validator.json)
  2. Generate prompt files (review_loop.py --prep --iter N)
  3. Claude orchestrator dispatches CFO + HoP sub-agents in parallel
  4. Sub-agents save reviews to review/<CODE>_iter_N_{cfo,hop}.md
  5. Continue: parse YAML verdict_blocks (review_loop.py --continue --iter N)
  6. Gate decision:
       - both APPROVE + zero CRITICAL/HIGH → DONE (status: APPROVE)
       - has auto_fixable CRITICAL → apply_fixes.py + rebuild → next iter
       - all blocking are HUMAN_REQUIRED → ESCALATE early
  7. If iter == max_iters and not APPROVE → ESCALATE (max_iters_reached)
```

---

## Step-by-step Claude orchestration

### Pre-loop (once)

```bash
# 1. Build workbook (Step 4)
python scripts/build_roi_workbook.py <inputs.json> <output_dir>

# 2. Recalc cached values
python scripts/recalc.py <output_dir>/<CODE>_ROI.xlsx

# 3. Initial validate (Step 5) + auto-repair RF-06 if present
python scripts/validate_roi.py <output_dir>/<CODE>_ROI.xlsx > /tmp/initial_validator.json
python scripts/apply_fixes.py <inputs.json> --auto-repair-formula-errors --validator-json /tmp/initial_validator.json
```

### Per-iteration (loops 1..max_iters)

**Step A: Prep prompts**

```bash
python scripts/review_loop.py <workbook> <inputs.json> --prep --iter N
```

Output:
- `review/<CODE>_iter_N_prompt_cfo.md`
- `review/<CODE>_iter_N_prompt_hop.md`
- `review/<CODE>_iter_N_validator.json`
- JSON to stdout with paths + ROI snapshot

**Step B: Claude dispatches sub-agents in parallel**

Send a single message with two Task tool calls:

```
Task #1 (cfo_reviewer):
  prompt: "Read /path/to/review/<CODE>_iter_N_prompt_cfo.md and follow its
           instructions exactly. Save your review to /path/to/review/<CODE>_iter_N_cfo.md
           with a fenced ```yaml verdict_block at the end."

Task #2 (hop_reviewer):
  prompt: "Read /path/to/review/<CODE>_iter_N_prompt_hop.md and follow its
           instructions exactly. Save your review to /path/to/review/<CODE>_iter_N_hop.md
           with a fenced ```yaml verdict_block at the end."
```

Both run in parallel. Wait for both to complete.

**Step C: Continue (parse + gate + fix + rebuild)**

```bash
python scripts/review_loop.py <workbook> <inputs.json> --continue --iter N
```

Returns one of:
- `{"status": "APPROVE", ...}` → loop exits; proceed to Step 7 (synthesis)
- `{"status": "NEXT_ITER", "next_iter": N+1, "new_workbook": ..., ...}` → loop continues with new files
- `{"status": "ESCALATE", "reason": "...", "escalation_path": ...}` → human decision required

**Step D (if NEXT_ITER): repeat from Step A with N+1 and new paths**

---

## Severity rubric (canonical — single source of truth)

| Severity | Definition | Examples | Auto-fix? | Blocks APPROVE? |
|---|---|---|---|---|
| 🔴 **CRITICAL** | Provable math/cell/structural error, mechanically patchable via the apply_fixes whitelist | Wrong cell ref, cohort×visit double-count, RF-08 unit mismatch, Y2 in Y1, missing RF-04 split, formula error #REF! | ✅ YES (if target_field in whitelist) | ✅ YES |
| 🟠 **HIGH** | Load-bearing assumption with no source / discovery debt invalidates Value-risk CF / material cost gap requiring research | "0 customer interviews on D1", T1 claimed but actually T4, training/infra/change-mgmt cost reviewer can't quantify | ❌ NO (escalate to human) | ✅ YES |
| 🟡 **MEDIUM** | Methodology gap that tightens but doesn't move Base ROI tier. **Honest-low ROI commentary lives here.** | "Pure ROI 0.15x — Priority Score deprioritizes", "consider Hospital/System split for clarity", "Best:Worst ratio is wide" | ❌ NO | ❌ NO |
| 🟢 **LOW** | Polish, labels, secondary-metric suggestions | "rename driver tree node", "decision-tier emoji inconsistent", "add post-launch tracking row" | ❌ NO | ❌ NO |

### Anti-confirmation-bias bright line

Reviewers are explicitly forbidden from marking "low ROI" as Critical or High. Pure ROI 0.15x with correct math is APPROVE. The Priority Score (Pure ROI × Strategic Fit) is what deprioritizes the feature in the roadmap — that is its job. The reviewer's job is methodological correctness only.

---

## YAML verdict_block schema

See `templates/reviewer_verdict_schema.yaml` for the canonical version. Summary:

```yaml
verdict_block:
  reviewer: cfo  # or hop
  iteration: 1
  feature_code: APT-2.0
  verdict: APPROVE  # or REJECT (CONDITIONAL deprecated)
  verdict_basis: "math correct, low ROI is honest"
  issues:
    - id: I1
      severity: CRITICAL  # CRITICAL | HIGH | MEDIUM | LOW
      category: model_bug
      cell_ref: "3_Value_Calc!B11"
      description: "..."
      auto_fixable: true
      fix_instruction:
        type: timing_correction
        target_field: "value_components[0].steps[2].applies_to_year"
        new_value: 2
        rationale: "..."
      # OR for auto_fixable: false:
      # human_action: "..."
  iteration_check:  # only on iter ≥ 2
    prior_iter: 1
    fixes_verified: ["..."]
    fixes_unresolved: ["..."]
    new_issues_found: ["..."]
    softened_verdicts:
      - issue_id: "I2 (iter 1)"
        prior_severity: HIGH
        new_severity: MEDIUM
        justification: "..."
```

---

## Auto-fix whitelist (apply_fixes.py enforces)

### Allowed fix types and target_field paths

| Fix type | Allowed paths in inputs.json |
|---|---|
| `formula_correction` | `value_components[*].steps[*].cf_id`, `output_currency`, `metric`, `type`, `label`, `note`, `[reorder]` |
| `unit_conversion` | `tam_sam_som.tam.unit`, `tam_sam_som.tam.label`, `tam_sam_som.sam_filters[append]` |
| `filter_addition` | `tam_sam_som.sam_filters[append]` (only if source already in research_validation.md) |
| `timing_correction` | `value_components[*].steps[*].applies_to_year`, `value_components[*].applies_to_year` |
| `cost_addition` | `effort.breakdown[append]` from closed catalog: `training_md`, `infra_thb`, `change_mgmt_md`, `app_specialist_md` |
| `cost_avoidance_split` | `value_components[*].is_system_value`, `driver_tree` (narrative only) |

### Forbidden paths (whitelist rejects → HUMAN_ACTION_REQUIRED)

- `tam_sam_som.tam.{worst,base,best}` (volume tuning)
- `tam_sam_som.sam_filters[*].{worst,base,best}` (rate tuning)
- `tam_sam_som.som_y{1,2,3}` (SOM ramp tuning)
- `conversion_factors[*].{worst,base,best,tier}` (research-frozen)
- `confidence.{tier,reason}` (Step 2.5 output)
- `strategic_fit.{multiplier,reason}` (would mask honest-low ROI)
- `baseline[*].value` (research-frozen)

**Why these are forbidden:** preventing the MCT-1.0 confirmation-bias trap (auto-tuning TAM volumes or CF rates to "match" prior calibrations or hit ROI targets). Reviewers must mark these as `auto_fixable: false` with `human_action`.

---

## Edge cases

| Case | Resolution |
|---|---|
| Validator red but both reviewers APPROVE | **Reviewer wins.** Validator is rule-based; can't read semantics. Summary logs dissent. |
| Auto-fix changes ROI 8x → 0.3x | **Success.** The 8x was inflated; 0.3x is correct. Loop continues; summary highlights as evidence. |
| CFO APPROVE, HoP REJECT (or vice versa) | **Fail-closed — both must approve.** Loop continues. If persistent split at iter `max_iters`, escalate. |
| All remaining issues HUMAN_REQUIRED before iter `max_iters` | **Early exit immediately** with `reason="no_autofix_possible"`. Don't waste iters. |
| Strategic-low-ROI feature (PFE-1.0 case) | **Verdict Criterion priming handles.** MEDIUM commentary, both APPROVE → exit iter 1. |
| Fix introduces NEW issue not in prior iter | **Counts toward iter limit.** Anti-sycophancy primer (iter ≥ 2) requires reviewer to look for this. |
| Reviewer marks `auto_fixable: true` on forbidden field | `apply_fixes.py` rejects at whitelist; fix returned in `denied`. Next iter the issue re-raises; reviewer can re-classify HIGH. **Whitelist-laundering protection.** |
| Workbook structure error (Sheet 5 missing, etc.) | Validator returns `status: error`. Pre-loop should detect and abort with `REBUILD_REQUIRED` escalation. |
| Reviewer output missing YAML verdict_block | Treated as REJECT-CRITICAL with synthetic SCHEMA1/SCHEMA2 issue. Forces re-review next iter. |
| Reviewer output has parseable YAML but verdict missing | Same as above — schema enforcement is strict. |

---

## State management (file-based, versioned)

```
<workspace>/Per-Feature ROI/
├── _inputs/
│   ├── <CODE>_inputs.json           # latest (or symlink to latest .vN.json)
│   ├── <CODE>_inputs.v1.json        # original (auto-saved before iter 1)
│   ├── <CODE>_inputs.v2.json        # post-iter-1 fixes
│   └── <CODE>_inputs.v3.json        # post-iter-2 fixes
├── <CODE>_ROI.xlsx                  # always = latest inputs
└── review/
    ├── <CODE>_iter_1_prompt_cfo.md      # generated by --prep
    ├── <CODE>_iter_1_prompt_hop.md
    ├── <CODE>_iter_1_validator.json     # validator snapshot at iter 1
    ├── <CODE>_iter_1_cfo.md             # written by sub-agent
    ├── <CODE>_iter_1_hop.md             # written by sub-agent
    ├── <CODE>_iter_1_fixes.yaml         # auto-fixable issues extracted (--continue)
    ├── <CODE>_iter_history.json         # SOURCE OF TRUTH — append-only loop state
    └── <CODE>_escalation.md             # only if escalated
```

`iter_history.json` schema:
```json
{
  "feature_code": "...",
  "workbook": "...",
  "iterations": [
    {
      "iter": 1,
      "outcome": "APPROVE | FIXES_APPLIED | ESCALATE_<reason>",
      "verdicts": [{...cfo verdict_block...}, {...hop verdict_block...}],
      "fixes_applied": [...],
      "fixes_denied": [...],
      "inputs_version": ".../path/to/inputs.v2.json",
      "workbook_after": "...",
      "roi_snapshot": {"y1_base": ..., "y3_base": ...},
      "timestamp": "2026-..."
    }
  ]
}
```

---

## Configuration

In `inputs.json` you can set:
```json
{
  "feature": {
    ...,
    "review_mode": "mandatory_loop"  // or "advisor" (legacy fallback)
  }
}
```

Default = `mandatory_loop`. The `advisor` fallback retains the old conditional Step 6 behavior (no loop, single advisory run if validator triggers).

---

## Cost expectations

Per 10-feature batch:
- Sub-agent runs: ~33 (vs current ~12 advisor mode) — `2 × 1.65 avg iters × 10 features`
- Validator runs: ~27 (per-iter + pre-loop)
- Worst case (every feature hits iter 3): 60 sub-agent runs (still bounded)

This is ~2.75× sub-agent cost vs current advisor mode. Justified by empirical evidence: 5/7 features in the 2026-05-04 Batch 3+4 build had cell-level bugs that the validator architecturally cannot see.
