---
name: roi-deep-review
description: Run mandatory CFO + Head of Product (HoP) sub-agent review on a per-feature ROI workbook — catches cell-level math bugs and methodological gaps that the inline validator architecturally cannot see. Use when the user says "deep review X", "ตรวจ ROI ของ Y", "CFO review", "audit feature", or when chained from roi-build (high-stakes feature with Y1 ROI > 5x or effort > 30 MD) or roi-adjust (after a tier shift). Iterates up to 2 rounds (configurable to 3) with auto-fix whitelist applied between iterations. Empirically catches 71% of cell-level bugs that the validator misses (5/7 features in 2026-05-04 batch). Output is APPROVE verdict or ESCALATE doc with 3 user options.
---

# ROI Deep Review (CFO + HoP)

> **v1.0** — extracted from `business-case-modeling` Step 6. Optimized: default `max_iter=2`, diff-based re-review on iter 2+, shared boilerplate extracted from agent prompts.

Review an existing ROI workbook for **methodological correctness** (not financial threshold). Honest-low ROI APPROVES if math is right.

## Why this skill exists

Empirical: 5/7 features in 2026-05-04 batch had cell-level bugs that the validator (rule-based) architecturally cannot see. Cost: ~30-50K tokens per feature, justified by audit trail + bug-catch rate.

**Persona separation is load-bearing** (data-driven decision):
- CFO + HoP overlap only ~10-25% — different lenses, different bugs
- HoP catches 7+ HIGH discovery_debt issues per batch that CFO architecturally cannot see
- Merging personas → regression bug rate (lose discovery debt detection)

---

## When this skill runs

Triggered manually OR auto-chained from:
- **roi-build** when (Y1 Base ROI > 5x) OR (effort > 30 MD) OR (validator red flags) OR (`feature.review_policy: always` in inputs.json)
- **roi-adjust** when tier shift detected (post-cascade)

---

## Verdict criterion (load-bearing rule)

**APPROVE = methodological correctness, NOT financial threshold.**

- Y1 ROI 0.15x with correct math → **APPROVE** (Priority Score deprioritizes via Pure ROI × SF)
- Y1 ROI 8.0x with broken formula → **REJECT-CRITICAL**

Reviewers are explicitly forbidden from marking "low ROI" as Critical or High. The roadmap rank handles low-ROI features; reviewer's job is correctness only.

---

## Severity rubric

| Severity | Definition | Auto-fix? | Blocks APPROVE? |
|---|---|---|---|
| 🔴 CRITICAL | Provable math/cell/structural error, mechanically patchable | ✅ if whitelisted | ✅ |
| 🟠 HIGH | Load-bearing assumption with no source / discovery debt invalidates value-risk CF | ❌ human action | ✅ |
| 🟡 MEDIUM | Methodology gap that doesn't move tier (incl. honest-low ROI commentary) | ❌ | ❌ |
| 🟢 LOW | Polish, labels, secondary metric suggestions | ❌ | ❌ |

For full rubric, examples, edge cases, YAML schema → `references/review_loop_protocol.md` (load on demand at iter 1 prep).

---

## Workflow

```
[Pre-loop] Validator snapshot + auto-repair RF-06 (formula errors) if any
    ↓
[Iter 1..max_iters (default 2, configurable to 3)]
  [A] Prep prompts (review_loop.py --prep)
        - iter 1: full context to both reviewers
        - iter 2+: diff context (cells changed since prev iter only) — Lever A optimization
  [B] Dispatch CFO + HoP sub-agents in parallel (single Task message, 2 calls)
        Each writes review/{CODE}_iter_N_{cfo,hop}.md with YAML verdict_block
  [C] Continue (review_loop.py --continue)
        Parse + gate + auto-fix + rebuild → return one of:
          APPROVE     — both APPROVE + 0 CRITICAL/HIGH → DONE
          NEXT_ITER   — auto-fixable CRITICAL applied → loop
          ESCALATE    — all blocking are HUMAN_REQUIRED OR max_iters hit
    ↓
[Output] Approved workbook + reviewer files + iter_history.json
```

---

## Step 1: Pre-loop

Run validator + auto-repair formula errors (RF-06):
```bash
python scripts/validate_roi.py <workbook> > /tmp/initial_validator.json
python scripts/apply_fixes.py <inputs.json> --auto-repair-formula-errors --validator-json /tmp/initial_validator.json
```

Why: RF-06 (formula errors like #REF!) is purely mechanical and shouldn't burn an iter cycle.

---

## Step 2: Per-iteration loop

### 2A. Prep (Claude orchestrator runs Python)

```bash
python scripts/review_loop.py <workbook> <inputs.json> --prep --iter N
```

For iter 2+, this includes a **diff section** showing cells changed since prev iter (Lever A optimization). Reviewers focus on changes; sycophancy contract still requires verifying each prior CRITICAL/HIGH independently.

### 2B. Dispatch sub-agents (Claude orchestrator)

Single message with 2 Task tool calls in parallel:

```
Task #1 (cfo_reviewer):
  Read review/{CODE}_iter_N_prompt_cfo.md and follow its instructions.
  Save your review to review/{CODE}_iter_N_cfo.md with a fenced ```yaml verdict_block at the end.

Task #2 (hop_reviewer):
  Read review/{CODE}_iter_N_prompt_hop.md and follow its instructions.
  Save your review to review/{CODE}_iter_N_hop.md with a fenced ```yaml verdict_block at the end.
```

### 2C. Continue

```bash
python scripts/review_loop.py <workbook> <inputs.json> --continue --iter N
```

Returns JSON with status:
- `APPROVE` → exit loop, hand off to next caller (roi-portfolio refresh, summary regen, etc.)
- `NEXT_ITER` → apply_fixes ran successfully on whitelist, rebuild done, loop again with N+1
- `ESCALATE` → write `review/{CODE}_escalation.md` with diff + 3 user options

---

## Auto-fix whitelist (anti-confirmation-bias)

| Allowed fix type | What it edits |
|---|---|
| `formula_correction` | `value_components[*].steps[*].cf_id`, `output_currency`, `metric`, `type`, `label`, `note`, reorder |
| `unit_conversion` | `tam_sam_som.tam.unit`, `tam_sam_som.tam.label`, append sam_filters |
| `filter_addition` | append `tam_sam_som.sam_filters[]` (only if source already in research_validation.md) |
| `timing_correction` | `value_components[*].steps[*].applies_to_year`, `value_components[*].applies_to_year` |
| `cost_addition` | append `effort.breakdown[]` from closed catalog (training_md, infra_thb, change_mgmt_md, app_specialist_md) |
| `cost_avoidance_split` | set `value_components[*].is_system_value: true`, `driver_tree` (narrative only) |

**Forbidden** (whitelist rejects → HUMAN_ACTION_REQUIRED):
- `tam.{worst,base,best}` (volume tuning)
- `sam_filters[*].{worst,base,best}` (rate tuning)
- `conversion_factors[*].{worst,base,best,tier}` (research-frozen)
- `confidence.tier`, `strategic_fit.multiplier`, `baseline[*].value`

**Why these are forbidden:** preventing the MCT-1.0 confirmation-bias trap (auto-tuning TAM/CF rates to "match" a target ROI). Reviewers must mark these as `auto_fixable: false` with explicit `human_action`.

---

## Anti-sycophancy contract (iter ≥ 2)

Reviewers receive prior iter history in their prompt + diff context (Lever A). They must:
- Verify each prior CRITICAL/HIGH independently (NOT trust that the fix worked)
- Flag NEW CRITICAL if a prior fix introduced a new bug
- Justify any softened verdict explicitly in `iteration_check.softened_verdicts`

If after re-reading the same blockers persist with no real change → REJECT again with same severity. Escalation at max_iters is the **correct** outcome, not "let it pass."

---

## Configuration (in inputs.json)

```json
{
  "feature": {
    "review_mode": "mandatory_loop",   // default — full loop
    "max_review_iters": 2,             // default 2 (was 3 in v1) — Lever C optimization
    "review_policy": "auto_threshold"  // for upstream roi-build to decide whether to chain
  }
}
```

For high-stakes features (e.g., Y1 ROI > 8x, effort > 80 MD), Kim can override `max_review_iters: 3` to allow extra fix cycles.

---

## Escalation paths

Loop exits with ESCALATE when:
- `max_iters_reached`: writes `review/{CODE}_escalation.md` with cumulative diff + 3 user options (override / defer / manual fix)
- `no_autofix_possible`: all blocking issues are HUMAN_ACTION_REQUIRED — exits early without burning iters
- `rebuild_required`: workbook structural error — caller must restart from roi-build

---

## File reference

- `scripts/review_loop.py` — orchestrator (--prep + --continue modes)
- `scripts/apply_fixes.py` — deterministic fix executor (whitelist-enforced)
- `scripts/validate_roi.py` — Stage A validator (also used pre-loop)
- `scripts/build_roi_workbook.py` — for rebuild after fix
- `scripts/recalc.py` — formula recalc
- `agents/cfo_reviewer.md` — CFO persona (load when triggering CFO sub-agent)
- `agents/head_of_product_reviewer.md` — HoP persona (load when triggering HoP sub-agent)
- `agents/_reviewer_shared.md` — shared boilerplate (severity rubric, YAML schema, sycophancy guards) — both personas reference this
- `references/review_loop_protocol.md` — full protocol spec (load at iter 1 prep, optional)
- `references/reviewer_personas.md` — persona DNA detail
- `templates/escalation.md` — escalation output template
- `templates/reviewer_verdict_schema.yaml` — canonical YAML schema

---

## Handoffs

- After APPROVE → caller (roi-build or roi-adjust) takes over for summary regen + portfolio refresh
- After ESCALATE → user reviews escalation.md, picks one of 3 options:
  1. **Override APPROVE** — accept current state, ship to portfolio (audit trail logged)
  2. **DEFER** — set `feature.status: DEFERRED`, exit roadmap, reviewer files preserved
  3. **Manual fix** — Kim edits inputs.json directly, re-run roi-deep-review with `--iter 1` (fresh start)

---

## Cost expectations

Per feature (with Lever A + B + C optimizations):
- 1 iter (typical APPROVE): ~25-35K tokens (was ~50K)
- 2 iter (some fixes needed): ~50-65K tokens (was ~100K)
- 3 iter (rare, high-stakes): ~80-100K tokens (was ~150K)

Per 30-feature batch (50% chained from roi-build): ~700K tokens (was ~1.5M)
