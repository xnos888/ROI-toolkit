# Sanity Check Rules

Rules for inline validator (Stage A). Implemented in `scripts/validate_roi.py`.

## Rule Categories

- **Red Flags** = blocking-level issues, indicate logic errors. Trigger subagent review.
- **Warnings** = soft issues, indicate weak evidence or pattern of risk. 2+ warnings trigger review.
- **Passed Checks** = sanity confirmed, log for transparency.

---

## Red Flag Rules (block-level)

### RF-01: Y1 Best ROI > 20x
**Logic:** Best case ROI exceeding 20x indicates either:
- TAM logic error (double-counting)
- Conversion factor too aggressive
- Missing cost components

**Action:** Force review, suggest cap.

### RF-02: Y1 Base ROI > 10x
**Logic:** Base ROI > 10x is rare in healthcare digital products. Likely TAM or conversion factor issue.

**Action:** Trigger CFO review with TAM challenge.

### RF-03: TAM > 1.5x of total org VN
**Logic:** TAM should be subset of organization's existing patient volume. If TAM > total VN of all branches, scope is wrong.

**Threshold:** TAM > 1.5 × Hospital_Baseline_DB total VN
**Action:** Block, ask user to redefine TAM.

### RF-04: Cost avoidance > 50% of total value (or > 30% without separate Hospital ROI breakdown)
**Logic:** Cost avoidance for patient/insurance is NOT hospital revenue. If it dominates, ROI is overstated for hospital.

**Two-tier check:**
- **Hard threshold:** Cost avoidance > 50% → red flag regardless of structure
- **Soft threshold:** Cost avoidance > 30% AND no separate "Hospital ROI" sheet/section → red flag

**What counts as "separate breakdown":**
- A sheet named with both "Hospital" and "ROI" in the name, OR
- A row/section in Sheet 5 explicitly labeled "Hospital ROI" or "Hospital-only"

**Action:** Recommend split into "Hospital ROI" vs "System ROI" sheets. Just splitting columns or labels in the same row is insufficient — must be a structural separation.

### RF-05: Build cost = 0 or negative net value across all 3 scenarios
**Logic:** Indicates missing data or feature not viable.

**Action:** Block, request input verification.

### RF-06: Formula errors in workbook
**Logic:** #REF!, #DIV/0!, #VALUE!, #NAME? indicate broken model.

**Action:** Block, recalc and fix before review.

### RF-07: Confidence T1 + Best:Worst ratio > 30x
**Logic:** T1 = high confidence (internal data). If range is huge, confidence claim is inconsistent.

**Action:** Either reduce range or downgrade to T3.

### FI-01: Load-bearing 5_Output cell hardcoded (formula expected)
**Logic:** Headline ROI cells in `5_Output` (Total Value, Y1 ROI, 3-Year Total Value, 3-Year ROI in columns B/C/D) must be formulas so input changes propagate. If any are hardcoded numbers, the workbook is statically frozen — future edits to inputs will silently fail to update outputs.

**Background:** AHC-1.0 REV2 (2026-05-04) needed a manual rebuild because `recalc_manual.py` overwrote formulas with computed values; subsequent input edits would have produced stale ROI without notice.

**Detection:** Read workbook with `data_only=False`, locate rows by label (`Total Value (THB)`, `Y1 ROI (Value ÷ Cost)`, `3-Year Total Value`, `3-Year ROI`), check that B/C/D cells start with `=`.

**Action:** Block. Restore formula chain via `restore_formulas` pattern or rebuild from `inputs.json`.

### FI-02: Cross-sheet reference broken in 5_Output
**Logic:** Every formula in `5_Output` that references another sheet (`'3_Value_Calc'!B18`, `'4_Effort_Cost'!B21`, etc.) must resolve to a non-empty target. Empty target = chain ruptured upstream — Sheet 5 will display 0 with no error indicator.

**Detection:** Regex-match cross-sheet refs in `5_Output` formulas, verify target sheet exists and target cell value is not None.

**Action:** Block. Investigate upstream sheet — usually `3_Value_Calc` row was renumbered or deleted during a partial rebuild.

### FI-03: Unresolved 'ref:' placeholder
**Logic:** `build_roi_workbook.py` uses an internal `ref:<cf_id>` placeholder syntax that gets rewritten to actual cell coordinates during build. If any cell still contains `ref:...` text after build, the resolver pass missed it — formula will not compute.

**Detection:** Scan all cells across all sheets for `ref:[A-Za-z0-9_-]+` pattern in cell value.

**Action:** Block. Re-run `build_roi_workbook.py` from `inputs.json` (don't manually patch — the resolver bug needs a clean pass).

### RF-08: TAM unit mismatch (visits vs patient cohort)
**Logic:** TAM should be measured in the same unit as the problem describes. Common error:

- TAM = X "VN/visits per year" 
- Problem describes a patient cohort (e.g., "NCD patients", "ผู้ป่วย", "user")
- Each patient has multiple visits per year (NCD = 6 cycles)
- → TAM is **6× inflated** relative to what the feature actually addresses

**Detection:**
- TAM unit field contains "VN", "visit", "visits", OR
- Problem text contains: "patient", "ผู้ป่วย", "cohort", "user", "NCD", "ncd", "คนไข้", "unique"
- → Both true = flag

**Action:** Either:
1. Convert TAM to unique patients (TAM_visits ÷ avg cycles per patient)
2. Or explicitly state "TAM = X visits, addressing Y unique patients" with both numbers
3. Or confirm in justification why visit-level TAM is correct (rare — usually applies only when feature works per-visit, e.g., wait-time visibility)

---

## Warning Rules (soft)

### W-01: Y1 Base ROI > 5x
**Logic:** ROI > 5x worth a second look but not necessarily wrong.
**Action:** Note in output.

### W-02: Confidence Tier T4 + Pure Y1 ROI > 3x
**Logic:** Low evidence + high claim = risky. Tier is metadata only (v1.1, not multiplied), but the signal still matters.
**Action:** Note, suggest pilot validation.

### W-03: Strategic Fit > 1.5x (Priority Score integrity)
**Logic:** v1.1 — SF used as Priority Score input only (never multiplied into Pure ROI). Cap at 1.5x prevents Priority Score inflation that would distort roadmap ranking.
**Action:** Request justification for SF input.

### W-04: Best:Worst ratio > 50x
**Logic:** Wide range = high uncertainty. Don't claim Base with confidence.
**Action:** Note uncertainty in output.

### W-05: Missing source citation in any CF
**Logic:** Every CF should have source in Sheet 6.
**Action:** List unsourced CFs.

### W-06: Effort < 30 MD + Y1 ROI > 5x
**Logic:** "Cheap and easy with huge return" = pattern of overestimation.
**Action:** Note, suggest verification.

### W-07: Single conversion factor responsible for > 70% of value
**Logic:** Single point of failure in ROI calculation.
**Action:** Suggest sensitivity analysis.

### W-08: TAM = SAM (no SAM filtering)
**Logic:** TAM should typically be larger than SAM (some patients not addressable).
**Action:** Verify SAM filters were applied.

### W-09: SOM Y1 = SOM Y3 (no adoption ramp)
**Logic:** Realistic adoption has ramp. Flat = unrealistic.
**Action:** Verify adoption assumption.

### W-10: Build effort range > 3x (Best to Worst)
**Logic:** Estimate uncertainty too high for commitment.
**Action:** Suggest engineering spike for clarity.

### W-11: Low source quality from research (NEW v1.0)
**Logic:** Step 2.5 research yielded fallbacks (search no usable result) for ≥50% of CFs. ROI numbers rely heavily on library defaults rather than fresh research.

**Detection:**
- Reads `research_validation.md` if present
- Counts fallback rate: fallbacks ÷ total_cfs ≥ 0.5

**Action:** Note in output. Suggest user re-run research (different time, more queries) or accept lower confidence.

**Pre-research workbooks** (built without Step 2.5): rule silently skipped, no warning issued.

---

## Passed Check Items (log for transparency)

These are confirmed-OK signals shown in output:

- `formula_errors_zero` — all formulas calculate without errors
- `load_bearing_cells_are_formulas` — 5_Output headline cells are formulas, not hardcoded
- `cross_sheet_refs_resolve` — every cross-sheet reference in 5_Output points to a populated target
- `no_unresolved_ref_placeholders` — no leftover `ref:` placeholders from build resolver
- `tam_within_org_total` — TAM ≤ org total VN
- `tam_unit_consistent` — TAM unit matches problem description (no patient/visit mismatch)
- `confidence_tier_present` — Confidence Tier label exists in inputs (v1.1: metadata only, not multiplied)
- `strategic_fit_within_cap` — SF input ≤ 1.5x (Priority Score integrity)
- `cost_avoidance_separated` — separate Hospital ROI sheet/section exists
- `cost_avoidance_within_threshold` — cost avoidance < 30% (no separation needed)
- `three_scenarios_present` — Worst/Base/Best all populated
- `driver_tree_documented` — Sheet 1 has driver tree
- `validation_plan_present` — Sheet 6 has leading indicators + kill criteria
- `source_citations_complete` — all CFs have source in Sheet 6

---

## Trigger Review Logic

```python
def should_trigger_review(red_flags, warnings, user_high_stakes):
    if len(red_flags) >= 1:
        return True, f"Triggered: {len(red_flags)} red flag(s)"
    if len(warnings) >= 2:
        return True, f"Triggered: {len(warnings)} warnings (≥2 threshold)"
    if user_high_stakes:
        return True, "Triggered: user requested deep review"
    
    # Skipped reasons
    if len(warnings) == 1:
        return False, "Skipped: 1 warning (within threshold), clean otherwise"
    return False, "Skipped: clean output, ROI within normal range"
```

---

## Calibration Notes

**If review triggers > 80% of features over time:** thresholds too tight. Loosen RF-01 to 25x, W-01 to 7x.

**If review triggers < 20% of features:** thresholds too loose. Tighten.

**Sweet spot:** 30-50% trigger rate — catches real issues without noise.

---

## Validator Output Format

```json
{
  "feature_code": "MED-1.0.3",
  "red_flags": [
    {
      "rule": "RF-02",
      "name": "y1_base_roi_too_high",
      "value": 6.76,
      "threshold": 10.0,
      "severity": "red",
      "message": "Y1 Base ROI 6.76x is high — review TAM logic"
    }
  ],
  "warnings": [
    {
      "rule": "W-01",
      "name": "y1_roi_above_warning",
      "value": 6.76,
      "threshold": 5.0,
      "severity": "warning",
      "message": "Y1 Base ROI exceeds 5x"
    },
    {
      "rule": "RF-04",
      "name": "cost_avoidance_dominant",
      "value": 0.61,
      "threshold": 0.5,
      "severity": "red",
      "message": "Cost avoidance 61% of value — recommend split"
    }
  ],
  "passed_checks": [
    "formula_errors_zero",
    "tam_within_org_total",
    "confidence_tier_present",
    "three_scenarios_present"
  ],
  "trigger_review": true,
  "trigger_reason": "Triggered: 2 red flag(s)"
}
```
