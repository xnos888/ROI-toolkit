# Reviewer Shared Boilerplate

> **For both `cfo_reviewer.md` and `head_of_product_reviewer.md`** — extracted to avoid 42% prompt overlap.
>
> Persona-specific instructions live in the per-role agent_md files. This file holds rubric, schema, and contracts that apply to both.

---

## Severity rubric (canonical — single source of truth)

| Severity | Definition | Auto-fix? | Blocks APPROVE? |
|---|---|---|---|
| 🔴 CRITICAL | Provable math/cell/structural error, mechanically patchable via whitelist | ✅ if target_field in whitelist | ✅ |
| 🟠 HIGH | Load-bearing assumption with no source / discovery debt invalidates Value-risk CF / material cost gap | ❌ HUMAN_REQUIRED | ✅ |
| 🟡 MEDIUM | Methodology gap that doesn't move Base ROI tier. **Honest-low ROI commentary lives here.** | ❌ | ❌ |
| 🟢 LOW | Polish, labels, secondary-metric suggestions | ❌ | ❌ |

### Anti-confirmation-bias bright line

You are explicitly **forbidden** from marking "low ROI" as Critical or High. Pure ROI 0.15x with correct math is APPROVE. The Priority Score (Pure ROI × Strategic Fit) is what deprioritizes the feature in the roadmap — that is its job. Your job is methodological correctness only.

---

## Forbidden auto-fix targets (whitelist enforces)

If you flag any of these as `auto_fixable: true`, the parser will reject and force HUMAN_REQUIRED:

- `tam_sam_som.tam.{worst,base,best}` (volume tuning)
- `tam_sam_som.sam_filters[*].{worst,base,best}` (rate tuning)
- `tam_sam_som.som_y{1,2,3}.{worst,base,best}` (SOM ramp tuning)
- `conversion_factors[*].{worst,base,best,tier}` (research-frozen)
- `confidence.{tier,reason}` (Step 2.5 output)
- `strategic_fit.{multiplier,reason}` (would mask honest-low ROI)
- `baseline[*].value` (research-frozen)

**Why these are forbidden:** preventing the MCT-1.0 confirmation-bias trap (auto-tuning TAM volumes or CF rates to "match" prior calibrations or hit ROI targets). Mark these as `auto_fixable: false` with explicit `human_action`.

---

## YAML verdict_block schema (mandatory at end of file)

Output **must** end with a fenced ```yaml block. Missing or invalid YAML = treated as REJECT-CRITICAL (synthetic SCHEMA1/SCHEMA2 issue).

```yaml
verdict_block:
  reviewer: cfo  # or hop
  iteration: 1
  feature_code: APT-2.0
  verdict: APPROVE  # or REJECT
  verdict_basis: "math correct, low ROI is honest"
  issues:
    - id: I1
      severity: CRITICAL  # CRITICAL | HIGH | MEDIUM | LOW
      category: model_bug  # see categories below
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
    fixes_verified: ["..."]      # IDs of prior issues you've now confirmed resolved
    fixes_unresolved: ["..."]    # IDs that still apply
    new_issues_found: ["..."]    # NEW CRITICAL/HIGH introduced by fixes
    softened_verdicts:           # only if you downgrade prior severity — explicit justification required
      - issue_id: "I2 (iter 1)"
        prior_severity: HIGH
        new_severity: MEDIUM
        justification: "..."
```

### Issue category enum

- `model_bug` — formula error, wrong cell ref, calc bug
- `rf04_split` — Hospital ROI vs System ROI not separated
- `rf08_unit` — unit mismatch (per-VN × per-yr etc.)
- `source_weak` — assumption with weak/no citation
- `cost_gap` — missing training/change-mgmt/infra cost
- `discovery_debt` — 0 customer interviews, no spike, capacity unverified
- `pilot_design` — kill threshold weak, control group missing
- `outcome_metric` — output mistaken for outcome, vanity metric
- `build_trap` — sub-feature bundling masking weak primary
- `other` — narrative/text issues

---

## Iteration awareness

### Iter 1
First review of the workbook. Be thorough. Catch the bugs the validator can't see. Required: identify ≥1 issue the validator missed (independent thought check).

### Iter ≥ 2 — Anti-sycophancy contract

You will receive in your prompt:
- The full prior-iter reviewer outputs (CFO + HoP)
- A diff section listing cells changed since prev iter (Lever A optimization)
- The prior verdict_block YAML

You **must**:
1. Verify each prior CRITICAL/HIGH independently — do NOT trust that the fix worked
2. If a prior fix introduced a NEW bug, flag it CRITICAL with full description
3. If you DO downgrade a prior issue, populate `iteration_check.softened_verdicts` with explicit justification — this is audited
4. Discovery debt does NOT resolve via inputs.json text edits. Real research must have happened between iters.

If after re-reading the same blockers persist with no real change → **REJECT again with the same severity**. Escalation at max_iters is the **correct** outcome, not "let it pass."

---

## What APPROVE means

- Both reviewers (CFO + HoP) write `verdict: APPROVE`
- Zero CRITICAL issues, zero HIGH issues
- MEDIUM/LOW issues are commentary — they don't block APPROVE
- Honest-low ROI APPROVES. Roadmap rank handles low-ROI features via Priority Score.

## What REJECT means

- One or more CRITICAL or HIGH issues exist
- Verdict basis must explain which issue(s) drive the REJECT
- Each blocker must be classified as `auto_fixable: true` (with `fix_instruction` matching whitelist) OR `auto_fixable: false` (with `human_action`)

---

## File outputs you must save

- Markdown review at the path provided in your prompt
- YAML `verdict_block` MUST be at end of file in fenced ```yaml block
- Use clear section headers; reviewer reads top-down

The orchestrator will parse the YAML and gate accordingly. Quality of human-readable markdown matters for audit trail; YAML correctness matters for orchestration.
