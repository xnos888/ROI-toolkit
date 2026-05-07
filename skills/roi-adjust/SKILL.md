---
name: roi-adjust
description: Modify an EXISTING feature's ROI assumption (effort, TAM, CF value, Strategic Fit, scope) and enforce cascade across all dependent artifacts (workbook, summary, master rollup, phase plan, reviewer staleness) — preventing silent drift. Use whenever the user says "ปรับ effort X", "เปลี่ยน TAM/CF/SF ของ Y", "อัพ ROI ตาม feedback CFO", "rebuild ROI ของ Z", "ลด/เพิ่ม assumption", or describes a feedback-driven adjustment to a feature that already has _inputs/{CODE}_inputs.json. Classifies changes (LIGHT/MEDIUM/HEAVY/STRUCTURAL), shows impact preview, requires approval, then cascades in dependency order with audit trail. For new features (no inputs.json yet), use roi-build instead.
---

# ROI Adjust (existing feature)

> **v1.0** — primary value-add: enforce CLAUDE.md cascade rule. Most-used skill in steady-state operations.

Modify an existing ROI assumption + cascade ALL dependent artifacts in lockstep. Prevents the "silent drift" pattern where one file gets edited and rollup/phase-plan/reviewer-files become stale.

## Why this skill exists

Project rule (CLAUDE.md "Assumption Changes — Keep Artifacts Live"): when an assumption changes, the impact cascades across 6+ files. Silent edits = stale artifacts = leadership gets inconsistent numbers.

This skill enforces:
1. **Trace impact ก่อนแก้** — never silent edit
2. **Approve with full impact list** — Kim sees what will change
3. **Rebuild in dependency order** — no cycles, no orphans
4. **Mark superseded reviewer files `.stale`** — audit trail preserved
5. **Auto-handoff to roi-portfolio** — master rollup never lags

---

## Change Classification (decides cascade depth)

Classification is based on **downstream files affected count**, not field name (heuristic):

| Severity | Downstream affected | Examples | Action |
|---|---|---|---|
| **LIGHT** | 1-2 files | strategic_fit, label, scenario range tweak, narrative text | Patch xlsx + regen summary + rollup |
| **MEDIUM** | 3-4 files | effort MD, TAM volume, SAM filter, scope (text-only) | Rebuild xlsx + recalc + validate + summary + rollup |
| **HEAVY** | 5+ files (research-frozen fields) | CF value, CF tier change, mechanism rewording | Re-research + rebuild + cascade + likely re-review |
| **STRUCTURAL** | Invalidates research | sub-feature add/remove, mechanism change | **Escalate to roi-build** (full restart, archive old as v_prev) |

**Bright line — research-frozen fields** (per `roi-deep-review` whitelist):
- `conversion_factors[*].{worst,base,best,tier}` — Kim CAN override but **must force tier=T4 + warning** (anti confirmation-bias)
- `tam_sam_som.tam.{worst,base,best}` — same
- `confidence.tier`, `strategic_fit.multiplier` — same

---

## Workflow

```
[1] Load existing inputs.json + show current value
    ↓
[2] Classify change → predict cascade scope
    ↓
[3] Compute impact preview (diff + files + ROI delta estimate)
    ↓
[4] Gate decision:
    LIGHT/MEDIUM → ขอ approve (1 click)
    HEAVY/STRUCTURAL → mandatory gate + extra impact
    ↓ on approve
[5] Execute cascade (dependency order):
    a. inputs.json → inputs.v{N}.json (audit, ห้ามทับ)
    b. update inputs.json
    c. rebuild xlsx (light=patch / medium+=full rebuild)
    d. recalc + validate
    e. regen summary.md
    f. tier shift check → mark old reviewer .stale + suggest deep-review
    ↓
[6] Auto-handoff → roi-portfolio (debounced 60s for batch adjust)
    ↓
[7] Final report: diff applied, ROI delta, files touched, suggested follow-ups
```

---

## Step 1: Load + Show Current

Required: feature CODE + change spec (field path + new value).

Auto-detect inputs.json:
```bash
find "Per-Feature ROI/_inputs" -name "{CODE}_inputs.json"
```

If not found → **fall through to roi-build** (this is a NEW feature).

Show user the current value of the field about to change:
```
Current: feature.effort.base = 18 MD
Proposed: feature.effort.base = 25 MD
```

---

## Step 2: Classify Change

```bash
python scripts/classify_change.py <inputs.json> <change.json>
```

`change.json` schema:
```json
{
  "field_path": "effort.base",
  "new_value": 25,
  "rationale": "Optional: why changing"
}
```

Output:
```json
{
  "severity": "MEDIUM",
  "downstream_files": ["xlsx", "summary", "rollup", "phase_plan"],
  "research_frozen_override": false,
  "requires_re_research": false,
  "recommend_re_review": true,
  "rationale": "Effort affects cost denominator → ROI changes → likely tier shift on borderline features"
}
```

**Critical safety:** if `field_path` matches a research-frozen pattern → output `research_frozen_override: true` + warning. Kim must explicitly acknowledge to proceed (anti confirmation-bias trap from MCT-1.0).

---

## Step 3: Compute Impact Preview

```bash
python scripts/compute_impact.py <inputs.json> <change.json> <classification.json> <preview.md>
```

Produces preview md showing:
- **Diff** — before/after value
- **Files affected** — actual paths that will rebuild
- **ROI delta estimate** — predicted Y1/3Y change (rough — rebuild for exact)
- **Tier shift prediction** — current tier vs likely new tier (🟢→🟡 etc.)
- **Reviewer staleness prediction** — will old reviewer files become .stale?
- **Phase plan rank prediction** — current rank vs likely new (Q1 → Q3 etc.)
- **Reversibility** — can this be undone via inputs.v{N-1}.json? (yes for all LIGHT/MEDIUM)

Show preview inline. User confirms before Step 4.

---

## Step 4: Gate Decision

| Severity | Gate behavior |
|---|---|
| LIGHT | Auto-approve unless ROI delta > 10% (rare for LIGHT) |
| MEDIUM | Show preview + ask approve |
| HEAVY | Show preview + extra warnings (research-frozen acknowledgment if applicable) + ask approve |
| STRUCTURAL | Stop. Output: "นี่เป็น STRUCTURAL change. ผมแนะนำใช้ roi-build (clone existing as v_prev + start fresh)." Wait for explicit user override |

---

## Step 5: Execute Cascade

```bash
python scripts/apply_adjust.py <inputs.json> <change.json> <classification.json>
```

This script orchestrates the full cascade:

### 5a. Versioning (audit trail)

```python
# Rename current inputs.json → inputs.v{N}.json
# N = next sequential number from existing inputs.v*.json files
shutil.copy("BIL-1.0_inputs.json", f"BIL-1.0_inputs.v{N}.json")
```

Cleanup: keep last 5 versions, archive older to `_inputs/_archive/` (don't delete — audit retention).

### 5b. Update inputs.json

Apply `change.field_path = change.new_value` using deep-merge logic.

### 5c. Rebuild workbook

- LIGHT: patch only the affected sheet/cell via openpyxl direct write (skip full build)
- MEDIUM/HEAVY: full rebuild via `build_roi_workbook.py`
- After rebuild: `recalc.py` (LibreOffice formula evaluation)

### 5d. Validate

```bash
python scripts/validate_roi.py <new_workbook>
```

If new red_flags appear that didn't exist before → flag in final report ("change introduced new validator flags: [...]").

### 5e. Regen summary

```bash
python scripts/generate_summary.py <workbook> <validator.json> <summary.md> [reviewer files if not stale]
```

### 5f. Tier shift check

Compare prev Y1 Base ROI tier vs new:
- 🟢→🟡, 🟡→🟠, 🟢→🟠, 🟠→🔴 etc. (downward) → **mark old reviewer .stale + recommend re-review**
- Same tier → keep reviewer
- Driver tree text changed → mark .stale (cited evidence may no longer apply)

```bash
# Mark reviewer files stale
mv review/{CODE}_iter_{N}_cfo.md review/{CODE}_iter_{N}_cfo.md.stale
mv review/{CODE}_iter_{N}_hop.md review/{CODE}_iter_{N}_hop.md.stale
```

---

## Step 6: Auto-handoff to Portfolio

Mandatory per CLAUDE.md ("master rollup is mandatory, not optional").

Handoff:
- **Single adjust** → trigger `roi-portfolio` Mode A (single feature refresh) immediately
- **Bulk adjust mode** (`--batch` flag) → debounce 60s, batch portfolio refresh once at end
- **Detection of batch:** if next adjust comes within 60s for same project, defer portfolio call

---

## Step 7: Final Report

Output to user:

```
✅ Adjust Complete — [CODE] [field_path]: [old_value] → [new_value]

📊 ROI DELTA
  Y1 Base:  [old]x → [new]x  (Δ [+/-]N%)  [tier emoji change]
  3-Yr Base: [old]x → [new]x  (Δ [+/-]N%)
  Effort:   [unchanged or new]

📁 FILES UPDATED
  ✓ _inputs/{CODE}_inputs.json (was → inputs.v{N-1}.json)
  ✓ {CODE}_ROI.xlsx (rebuilt)
  ✓ {CODE}_summary.md (regenerated)
  ✓ Feature_ROI_Summary.xlsx Pipeline_Summary tab (rolled-up)
  ⚠ review/{CODE}_iter_*_{cfo,hop}.md → .stale (tier shifted)

🔍 SUGGESTED FOLLOW-UPS
  - re-run roi-deep-review (tier dropped from 🟢→🟡)
  - validate Phase_Plan rank (was #4, now #7 — moved Q2 → Q3)

⏪ ROLLBACK
  Revert: cp _inputs/{CODE}_inputs.v{N-1}.json _inputs/{CODE}_inputs.json && roi-adjust --rebuild
```

---

## Bulk Adjust Mode

For "ลด TAM ทั้ง batch 4 ลง 20%" scenarios:

```bash
python scripts/apply_adjust.py --batch <batch_spec.json>
```

`batch_spec.json`:
```json
{
  "features": ["BIL-1.0", "INS-1.0", "DIC-1.0", ...],
  "change": {
    "field_path": "tam_sam_som.tam.base",
    "new_value": "* 0.8"  // multiplier syntax
  },
  "rationale": "Q1 capacity tightened — derate TAM 20%"
}
```

Behavior:
- Loop classify+execute each feature
- Defer portfolio refresh until end
- Single batch portfolio call refreshes all rows once
- Final report aggregates: "5 features adjusted, 2 tier shifts, total ROI shift Σ -8M"

---

## Dry-run Mode

```bash
python scripts/apply_adjust.py --dry-run <inputs.json> <change.json>
```

Computes impact + shows preview. Does NOT touch files. Use case: "ถ้าลด TAM 20% Y1 ROI จะตกเท่าไหร่?"

---

## Reversibility

- All changes versioned via `inputs.v{N}.json`
- Last 5 kept; older archived to `_inputs/_archive/`
- Rollback = `cp inputs.v{N-1}.json inputs.json && rebuild`
- Reviewer `.stale` files preserved (audit trail) — can reapply if rollback decision

---

## File reference

- `scripts/classify_change.py` — Step 2 (classify severity + downstream prediction)
- `scripts/compute_impact.py` — Step 3 (delta + preview md generator)
- `scripts/apply_adjust.py` — Step 5 (orchestrate cascade)
- `scripts/build_roi_workbook.py` — shared with roi-build (rebuild workbook)
- `scripts/recalc.py` — shared (formula evaluation)
- `scripts/validate_roi.py` — shared (Stage A validator)
- `scripts/generate_summary.py` — shared (summary regen)

---

## Anti-patterns to avoid

- **Silent edit** (just patch xlsx without rebuilding rollup) — violates CLAUDE.md cascade rule
- **Skip versioning** (overwrite inputs.json without v{N} backup) — destroys audit trail
- **Auto-approve HEAVY changes** — research-frozen fields require explicit Kim acknowledgment
- **Forget reviewer staleness** — stale reviewer files = misleading audit
- **Skip portfolio handoff** — master rollup goes stale immediately

---

## Handoffs

- After cascade complete (always) → `roi-portfolio`
- If tier shift detected → suggest `roi-deep-review` (Kim's call)
- If STRUCTURAL change → escalate to `roi-build` (full restart)
- If feature has no inputs.json → escalate to `roi-build` (NEW feature, not adjust)
