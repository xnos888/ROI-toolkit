---
name: roi-build
description: Build defendable per-feature ROI for a NEW feature using driver-based bottom-up modeling, 3-scenario forecasting (Worst/Base/Best), TAM-SAM-SOM funneling, web-research-validated conversion factors with TH discount + tier classification (T1-T4), and Cagan 4-risk discovery. Output is a 6-sheet xlsx workbook + research audit trail + summary.md. Use whenever the user asks to "ทำ ROI", "build ROI", "feature business case", "วิเคราะห์ feature", "ปั้น ROI", or describes a feature problem and asks if it's worth building — even without saying "ROI". Use ONLY for new features (no existing inputs.json). For modifying an existing feature, use roi-adjust instead.
---

# ROI Build (per feature)

> **v2.0** — slimmed from `business-case-modeling` v1.0. Research-validated, defendable to C-Level.

Build per-feature ROI that **survives CFO scrutiny** — every output traces to inputs via explicit driver tree, every conversion factor cites a source found at build-time, US benchmarks are TH-discounted, cost-avoidance is split from hospital revenue.

## Core Philosophy + Rules (single source of truth)

1. **Driver tree mandatory** — every output value traces via explicit cause-effect chain, not top-down guess
2. **3-point estimation (PERT)** — Worst/Base/Best for every input, never single-point
3. **Source-cited per CF** — research at build-time via WebSearch; tier classify (T1-T4); cite URL
4. **TH discount on US benchmarks** — ~43% of US value for Base. Why: TH market reality differs (lower urgency for digital, longer adoption curve, lower revenue per VN)
5. **Hospital ROI vs System ROI split** — when cost-avoidance dominates (ER avoidance, insurance saving), set `is_system_value: true` on the component. Hospital headline excludes system value. Why: leadership sees only what hospital captures
6. **Cap Best case at 20x** — higher = sanity check fail (RF-01)
7. **Pure ROI never multiplied** — Confidence Tier (T1-T4) is metadata only. Strategic Fit feeds Priority Score (= Pure ROI × SF) for roadmap ranking ONLY. Headline ROI shown to leadership = Pure ROI

## Anti-patterns to avoid

- Top-down guess ("น่าจะได้ 10M")
- Single-point estimate (no scenarios)
- US benchmark without discount
- Cost-avoidance counted as hospital revenue
- Best-case ROI > 20x without sanity check
- Confidence Tier × ROI (tier is metadata, not multiplier)

---

## Workflow

```
[1] Detect environment + check feature is new
    ↓
[2] Collect inputs (3 required + auto-detect)
    ↓
[2.5a] Decompose sub-features → distinct mechanisms
[2.5b] Plan + execute web research per CF
[2.5c] Tier classify + TH discount + ingest
[2.5d] Save research_validation.md (audit trail)
    ↓
[3] Stage 1 — Assumption Preview (inline approve)
    ↓
[4] Build 6-sheet xlsx workbook
    ↓
[5] Inline validator (Stage A — always)
    ↓
[6] Suggest deep review (handoff → roi-deep-review)
    ↓
[7] Generate summary.md + present
    ↓
[8] Auto-handoff → roi-portfolio (refresh master rollup)
```

---

## Step 1: Detect Environment

Check feature does NOT already exist (else handoff to roi-adjust):

```bash
# Detect project structure (recursive search from cwd)
find . -name "Hospital_Baseline_DB.xlsx" -not -path "*/node_modules/*" 2>/dev/null
find . -path "*/Per-Feature ROI/_inputs/*_inputs.json" 2>/dev/null
```

If `_inputs/{CODE}_inputs.json` already exists → **stop and handoff to `roi-adjust`** (don't rebuild from scratch).

If `Hospital_Baseline_DB.xlsx` not found → **portable mode** (ask user to paste baseline values).

---

## Step 2: Collect Inputs

### Required (3 fields)

| Field | Question |
|-------|----------|
| Feature Name | "ชื่อ feature?" |
| Problem | "ปัญหาคืออะไร? (1-2 sentences)" |
| Effort | "Effort กี่ MD? (Worst/Base/Best หรือ single)" |

### Auto-detect (skill propose)

- **Category** — from feature name + problem keywords (Appointment / Queue / Medication / Results / Payment / Documents / etc.)
- **Mechanism** — propose driver tree from `references/driver_tree_patterns.md` (load on demand)
- **Confidence Tier** — default T3 (industry benchmark + geo proxy)

### Auto-derived (never ask)

- Hospital baseline (from `Hospital_Baseline_DB.xlsx`)
- TAM scope from category
- MD blended cost (default 24,000 THB; configurable in `_inputs/_capacity_config.json` if exists)
- MA rate (default 30% = 20% × 1.5 multi-branch premium)

User can choose: **conversational** (Q&A one by one) or **YAML structured** (paste — see `templates/input_form.yaml`).

---

## Step 2.5: Research & Verify (mandatory)

Why mandatory: skill's value depends on defendable CF numbers. Static library is stale; user-provided "Industry Evidence" is unverified. Research at build-time ensures every primary CF traces to a real source.

### Stage 2.5a — Sub-feature Decomposition

```bash
python scripts/decompose_subfeatures.py <inputs.json> <decomposition.json> <decomposition.md>
```

Catches: bundled mechanisms (double-count risk), cost-avoidance mixed with revenue, stated outcome ≠ actual sub-features.

If HIGH severity concern → show `decomposition.md` + ask: split into separate features OR model multi-outcome explicitly. User decision recorded.

### Stage 2.5b — Plan Research Queries

```bash
python scripts/research_cf.py <inputs.json>
```

Produces query plan (2 per CF max). Cache: same mechanism → same key → reused across batch.

### Stage 2.5c — Execute Web Searches

For each planned query, call **`WebSearch`** tool (PascalCase — Claude Code's built-in). Capture top 3-5 results per query.

### Stage 2.5d — Ingest + Save Audit

Feed results back via `session.ingest_results()`. Engine performs:
1. **Source tier** — T1 (academic peer-reviewed) / T2 (PubMed/gov) / T3 (McKinsey/industry analyst) / T4 (vendor blog/press)
2. **Numeric extraction** — regex from snippets ("20-40%", "21.5%")
3. **TH discount** — ~43× of US for Base; no discount for TH-direct sources
4. **Aggregate** — average across sources, set Worst/Base/Best

Then:
```bash
session.save_audit_trail("research_validation.md")
```

This is the **defensibility record** — present alongside ROI sheet to C-Level.

### Fallback rules

- 0 sources → fallback to library (`references/conversion_factor_library.md`) + force T4 + warning
- 0 numeric extracted → same as above
- All T4 → use values but flag low confidence

Skill never blocks — always produces result with explicit tier + warning.

### Why research-first (not library-first)

Static CF library rots. Web search at build-time = current data. Library is fallback only — when search yields nothing or rate-limited.

---

## Step 3: Stage 1 — Assumption Preview

By this point CFs are researched + verified. Preview shows **researched values** (not user-provided guesses) with source citations.

```bash
python scripts/preview_assumptions.py <inputs.json> <preview.md>
```

Produces structured md:
- TAM-SAM-SOM (3 scenarios with sources)
- All Conversion Factors (researched Tier + URL)
- Confidence Tier (metadata) + Strategic Fit (Priority Score input)
- Build effort breakdown
- Cagan 4-Risk status
- Top 3 assumptions to verify
- Research summary (sources found, cache hits, fallbacks)

Show preview inline to user, then:
- **Approve:** proceed to Step 4
- **Adjust X:** modify only that field in inputs.json, re-run preview (research stays cached)
- **Reject:** ask why, restart input collection

Always use the script — never improvise. Consistency across sessions.

---

## Step 4: Build Xlsx Workbook

```bash
python scripts/build_roi_workbook.py <inputs.json> <output_dir>
```

Produces 6-sheet workbook:

| Sheet | Content |
|-------|---------|
| 1_Feature_Info | Identity + Problem + Mechanism + Cagan 4 Risks |
| 2_Inputs | Hospital Baseline + TAM-SAM-SOM + Conversion Factors + Confidence Tier (metadata) + Strategic Fit (Priority Score input) |
| 3_Value_Calc | Y1 + Y2 + Y3 + 3-Year Cumulative Total Value (formulas, no multipliers) |
| 4_Effort_Cost | Build effort by role + Build cost + MA cost |
| 5_Output | Pure ROI + Decision tier + Priority Score (roadmap only) + CEO 1-liner + Post-launch tracking |
| 6_Flagged_Assumptions | All assumptions with source + verification + risk register + validation plan |

**Color coding** (industry standard):
- Yellow fill = INPUT (user can change)
- Blue text = hardcoded value
- Black text = formula
- Green text = cross-sheet reference
- Orange fill = totals / key outputs

After build, **always run** recalc:
```bash
python scripts/recalc.py <workbook>
```

Why: openpyxl doesn't evaluate formulas. Skipping recalc = cells read stale cache (caused AHC-1.0 REV2 bug).

---

## Step 5: Inline Validator (Stage A — always runs)

```bash
python scripts/validate_roi.py <workbook>
```

Returns JSON with `red_flags`, `warnings`, `passed_checks`, `metrics`.

Common flags (full list in `references/sanity_check_rules.md`, load on demand):
- **RF-01** — Y1 ROI > 5x (verify TAM logic)
- **RF-04** — cost-avoidance > 50% of value (recommend Hospital/System split)
- **RF-08** — unit mismatch (e.g., per-VN × per-year)
- **FI-01..FI-03** — formula integrity (load-bearing cells must be formulas not hardcoded; cross-sheet refs resolve; no leftover `=ref:` placeholders)

---

## Step 6: Suggest Deep Review

Read `inputs.json` → check `feature.review_policy`:
- `"always"` → handoff to `roi-deep-review` automatically
- `"never"` → skip
- `"auto_threshold"` (default) → suggest if **Y1 Base ROI > 5x** OR **effort > 30 MD** OR **validator has any red flag**
- `"ask"` → prompt user

If suggested + user accepts → handoff to `roi-deep-review` skill (it owns the CFO + HoP loop).

---

## Step 7: Synthesize + Present

```bash
python scripts/generate_summary.py <workbook> <validator.json> <summary.md> [cfo_review.md] [hop_review.md]
```

Auto-fills `templates/summary.md` with ROI numbers from Sheet 5, driver tree from Sheet 1, risks + validation plan from Sheet 6, validator flags, top-3 reviewer concerns, decision tier from Y1 Base ROI:
- 🟢 STRONG GO — Y1 ≥ 5x
- 🟡 CONDITIONAL — 1.5x–5x
- 🟠 DEFER — 1x–1.5x
- 🔴 KILL — < 1x

Always use the script — guarantees format consistency.

User-facing chat output:
```
✅ ROI Build Complete — [CODE] [Name]

📊 BOTTOM LINE
  Y1 Base ROI:  [X.XX]x  → [tier emoji] [Decision]
  3-Yr Base ROI: [X.XX]x → [tier emoji] [Decision]
  Build Effort: [Base] MD ([Worst]/[Best])

📁 FILES
  - {CODE}_ROI.xlsx
  - {CODE}_summary.md
  - research_validation.md

⚠️  VALIDATOR FLAGS — [list or "None"]

📊 RECOMMENDATION
  [2-3 sentences max]
```

---

## Step 8: Auto-handoff to Portfolio Refresh

After summary saved → auto-trigger `roi-portfolio` (Mode A: single-feature refresh) to update `Feature_ROI_Summary.xlsx` Pipeline_Summary + Phase_Plan tabs.

Why mandatory: per project rule, master rollup is data authority. Per-feature ROI without rollup refresh = silent drift.

---

## Save Files

- Excel: `{FEATURE_CODE}_ROI.xlsx` → `Per-Feature ROI/`
- Summary: `{CODE}_summary.md` → same
- Inputs: `_inputs/{CODE}_inputs.json` (will become `inputs.v1.json` after first adjust)
- Research: `_inputs/{CODE}_research_validation.md`
- Decomposition: `_inputs/{CODE}_decomposition.{json,md}`
- Preview: `_inputs/{CODE}_preview.md`

---

## On-demand reference loading

Don't load all references at start. Load only when the workflow step needs:

| Reference | When to load |
|---|---|
| `references/driver_tree_patterns.md` | Step 2 — proposing driver tree for category |
| `references/conversion_factor_library.md` | Step 2.5e — fallback only when WebSearch fails |
| `references/sanity_check_rules.md` | Step 5 — when interpreting validator flags |
| `examples/research_walkthrough.md` | If user asks "show me an example" |
| `examples/MED-1.0.3_walkthrough.md` | If user asks for project-mode example |
| `examples/portable_mode_example.md` | If portable mode (no project files) |

Why on-demand: each reference is 200-300 lines. Loading all 3 = ~7,800 tokens wasted per trigger when most CFs cache-hit.

---

## File reference

- `scripts/decompose_subfeatures.py` — Stage 2.5a
- `scripts/research_cf.py` — Stage 2.5b-d (web research engine, session cache)
- `scripts/preview_assumptions.py` — Step 3
- `scripts/build_roi_workbook.py` — Step 4 (xlsx generator with strict =ref: resolver)
- `scripts/recalc.py` — formula recalc (LibreOffice)
- `scripts/validate_roi.py` — Step 5 (Stage A inline validator)
- `scripts/generate_summary.py` — Step 7

---

## Handoffs

- After Step 5 (high stakes) → `roi-deep-review`
- After Step 7 (always) → `roi-portfolio`
- If `_inputs/{CODE}_inputs.json` already exists → `roi-adjust`
