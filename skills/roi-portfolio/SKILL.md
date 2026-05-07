---
name: roi-portfolio
description: Maintain the master rollup (Feature_ROI_Summary.xlsx Pipeline_Summary + Phase_Plan tabs) and per-batch narratives — the single source of truth that leadership reads to make commit/KILL/DEFER decisions across the PE roadmap. Use when the user says "refresh master rollup", "อัพ Pipeline_Summary", "ทำ Phase Plan", "decide KILL/DEFER batch X", "rank features by Priority Score", "เช็ค capacity Q1-Q4", or whenever a per-feature workbook has been built or adjusted (auto-chain target — mandatory per project rule, master rollup is data authority). Three modes: Mode A (single-feature refresh, debounced 60s for batch ops), Mode B (full batch aggregation + Phase Plan generation + capacity check), Mode C (decision support for KILL/DEFER proposals). Use roi-build or roi-adjust first to update individual features; this skill aggregates them.
---

# ROI Portfolio (cross-feature aggregation)

> **v1.0** — fills the gap in the original `business-case-modeling` skill (Step 8 missing). Per CLAUDE.md project rule: "master rollup is mandatory, not optional".

Maintain `Feature_ROI_Summary.xlsx` (Pipeline_Summary + Phase_Plan tabs) and `PE_Roadmap_Phase_Plan_*.md` so leadership always reads consistent numbers across all features.

## Why this skill exists

Project rule (CLAUDE.md): "Any time a feature's Y1/3-Yr ROI, effort MD, decision tier, or quarter assignment changes, `Feature_ROI_Summary.xlsx` MUST be refreshed in the same change set. It is the data authority — leadership reads from this file."

Before this skill: rollup refresh was manual + ad-hoc → silent drift across batch 3, 4, 5, 6 happened multiple times (see `.bak` files in Per-Feature ROI/).

This skill enforces: **never let per-feature workbooks and rollup drift apart**.

---

## Three Modes

### Mode A — Single feature refresh (auto-chain)

Triggered automatically after `roi-build` (post-summary) or `roi-adjust` (post-cascade). Updates ONE feature's row in Pipeline_Summary + reorders Phase_Plan if rank shifts.

```bash
python scripts/refresh_master_rollup.py --feature {CODE} <project_root>
```

Behavior:
1. Read updated `{CODE}_summary.md` + `{CODE}_ROI.xlsx` (Sheet 5 metrics)
2. Locate `Feature_ROI_Summary_*.xlsx` in `Per-Feature ROI/`
3. Update existing row in `Pipeline_Summary` tab (or append if new)
4. Recompute Priority Score = Pure ROI × Strategic Fit
5. Reorder `Phase_Plan` tab (rank may shift)
6. Flag if rank crosses Q boundary ("APT-2.0 ขยับจาก Q2 → Q3")

**Debounce logic:** if multiple Mode A calls arrive within 60s for the same project (signal: batch adjust in progress) — coalesce into a single Mode B run at end of debounce window. Avoids N×portfolio refresh during bulk adjust.

### Mode B — Batch ops (manual or end-of-debounce)

Full re-aggregation of all features. Run at:
- End of batch (week 4, monthly)
- Post-debounce after bulk roi-adjust
- When Pipeline_Summary appears stale (manual sanity check)

```bash
python scripts/update_phase_plan.py <project_root>
```

Behavior:
1. Scan all `Per-Feature ROI/{CODE}_ROI.xlsx` workbooks
2. Re-aggregate `Pipeline_Summary` tab from scratch
3. Apply decision tier:
   - 🟢 STRONG GO — Y1 Base ≥ 5x
   - 🟡 CONDITIONAL — 1.5x – 5x
   - 🟠 DEFER — 1x – 1.5x
   - 🔴 KILL — < 1x
4. Compute Priority Score per feature (= Pure ROI × Strategic Fit)
5. Rank features for `Phase_Plan` tab
6. Capacity check: sum(MD requested) per quarter vs annual capacity (default 600, configurable via `_inputs/_capacity_config.json`)
7. Flag oversubscription per quarter
8. Generate `PE_Roadmap_Phase_Plan_YYYY-MM-DD.md` markdown narrative

### Mode C — Decision support (Kim-driven)

Triggered when user asks "ของ batch X ตัวไหน KILL ดี?" or "เช็ค Q1 oversubscription ทำยังไง?"

```bash
python scripts/update_phase_plan.py --propose-kill-defer <project_root>
```

Decision criterion (per Kim's preference):
- KILL = (Pure ROI < 1.0x) AND (Strategic Fit < 1.2) AND (capacity tight that quarter)
- DEFER = (Pure ROI 1.0-1.5x) AND not strategic
- (Strategic Fit ≥ 1.4 with low ROI) → keep, surface as strategic case

Output: ranked list of KILL/DEFER candidates with rationale. Kim approves, then update `inputs.json` with `feature.status: "KILLED"` or `"DEFERRED_Q3"` etc., re-run Mode B.

---

## Workflow Diagram

```
┌─────────────────────────────────────────────────────┐
│  Caller (roi-build / roi-adjust / Kim manual)       │
└────┬─────────────────┬────────────────────┬─────────┘
     │ Mode A          │ Mode B             │ Mode C
     ↓                 ↓                    ↓
┌────────────┐    ┌──────────────┐    ┌──────────────┐
│ Single     │    │ Full batch   │    │ Decision     │
│ feature    │    │ aggregation  │    │ support      │
│ refresh    │    │ + Phase_Plan │    │ (KILL/DEFER) │
└────┬───────┘    └──────┬───────┘    └──────┬───────┘
     │                   │                    │
     └─────────┬─────────┴────────────────────┘
               ↓
    ┌──────────────────────────────────┐
    │ Update Feature_ROI_Summary.xlsx  │
    │   - Pipeline_Summary tab         │
    │   - Phase_Plan tab               │
    │ + PE_Roadmap_Phase_Plan_*.md     │
    └──────────────────────────────────┘
```

---

## File reference

- `scripts/refresh_master_rollup.py` — Mode A (single feature, fast)
- `scripts/update_phase_plan.py` — Mode B + C (full batch + Phase Plan + KILL/DEFER)
- `scripts/build_comparison.py` — auxiliary: side-by-side comparison xlsx for N features

---

## Configuration

`_inputs/_capacity_config.json` (optional, project-level):
```json
{
  "annual_capacity_md": 600,
  "buffer_pct": 0.15,
  "quarters": {
    "Q1": 150,
    "Q2": 150,
    "Q3": 150,
    "Q4": 150
  }
}
```

Default annual capacity = 600 MD if config missing.

---

## Anti-patterns to avoid

- **Edit master rollup directly** — it's derived. Always refresh from per-feature workbooks
- **Skip portfolio refresh after build/adjust** — silent drift starts immediately
- **Run Mode A in a loop without debounce** — wastes tokens on intermediate states
- **KILL based on ROI alone** — must check Strategic Fit + capacity (criterion above)

---

## Handoffs

- After Mode A complete → return to caller (roi-build or roi-adjust) for final report
- After Mode B with capacity oversubscription → suggest Mode C (KILL/DEFER decision support)
- After Mode C decisions made → loop back to roi-adjust (`feature.status` = KILLED/DEFERRED) → roi-portfolio Mode B (re-aggregate)

---

## Output artifacts

- `Per-Feature ROI/Feature_ROI_Summary_YYYY-MM-DD.xlsx` (Pipeline_Summary + Phase_Plan tabs — **data authority**)
- `Per-Feature ROI/PE_Roadmap_Phase_Plan_YYYY-MM-DD.md` (narrative + KILL/DEFER decisions)
- `Per-Feature ROI/Batch{N}_Master_Summary.md` (per-batch narrative — generated optionally for batch end)
- Console JSON output with summary stats (total features, MD, oversubscription flags)
