# Worked Example: MED-1.0.3 Refill Alert

End-to-end walkthrough of how this skill processes a feature.

---

## Step 1: User Request

User: "ทำ ROI ให้ feature Refill Alert หน่อย"

Or with more context: "ขอ ROI สำหรับ MED-1.0.3 Refill Alert — เตือนเมื่อยาใกล้หมด สำหรับผู้ป่วย NCD"

---

## Step 2: Skill Detects Environment

Check files in order:
1. `/mnt/project/Hospital_Baseline_DB.xlsx` ✅ Found
2. `/mnt/project/PE_Feature_List_Merged_*.xlsx` ✅ Found

Skill reads:
- `references/driver_tree_patterns.md` (always)
- `references/conversion_factor_library.md` (always)
- `references/sanity_check_rules.md` (always)

From `Hospital_Baseline_DB.xlsx`:
- Total VN: 1,304,162
- Avg Revenue per OPD VN: 3,000 THB
- MD Cost: 24,000 THB/MD

From `PE_Feature_List_Merged_*.xlsx`:
- MED-1.0 has 3 sub-features: Med Info / Med Reminder / Refill Alert
- Refill Alert = MED-1.0.3
- Category: Medication

---

## Step 3: Skill Asks Clarifying Questions (max 3)

```
มีคำถาม 3 ข้อก่อน build:

1. Effort estimate (MD): ใส่ Worst/Base/Best หรือ single number?
   ตัวอย่าง: 100/72/52 MD (Worst/Base/Best)

2. Confidence Tier (T1-T4)?
   - T1: ข้อมูล internal (Tableau/HIS)
   - T2: 1 case study + 1 corroborating
   - T3: industry benchmark + geo proxy [default]
   - T4: single source / heavy proxy

3. Strategic Fit components — ติ๊กที่ใช่:
   - Cost saving (ลด ops cost)
   - Catch-up (Bumrungrad/Samitivej มีแล้ว)
   - Patient retention/value
```

---

## Step 4: Stage 1 — Assumption Preview

```
📋 Stage 1/3: Proposed Assumptions for MED-1.0.3 Refill Alert

CATEGORY: Medication

📊 TAM-SAM-SOM (3 scenarios)
  TAM:    326K NCD VN/yr (25% of 1.3M total VN)
  SAM filter 1: % NCD active SPC user — 20/30/40%
  SAM filter 2: % opt-in for notif — 50/65/80%
  SOM Y1: 30/50/70%
  SOM Y2: 50/70/85%
  SOM Y3: 65/80/90%

🔧 CONVERSION FACTORS
  D1 Refill conversion (alert → action) — 20/35/50% [T3]
       Source: SOVDOC 20-40%, discount US→TH 50%
  D2 % incremental refills — 30/50/70% [T3]
  D3 ER/IPD avoidance — 0.5/1.5/3.0% [T4]
  D4 Cost per ER event — 8K/15K/25K THB [T3]
       ⚠️ Cost avoidance, NOT hospital revenue
  D5 Nurse call reduction — 5/10/15% [T4]
  D6 Nurse cost/min — 3.3 THB [T1]
  D7 Avg refill visit revenue — 2,200 THB [T1]

🎯 CONFIDENCE TIER & PRIORITY SCORE INPUT (v1.1)
  Confidence: T3 (metadata only — not multiplied into Pure ROI)
  Strategic Fit: Cost ✓ Catch-up ✓ Value ✓ → 1.20x (used for Priority Score)

⚙️ EFFORT
  PM:        12/8/6 MD
  PD:        10/8/6 MD
  SWE BE:    30/22/16 MD (CRITICAL — Pharmacy integration)
  SWE FE:    18/14/10 MD
  SWE Notif: 12/8/6 MD
  QA:        10/7/5 MD
  App Spec:  8/5/3 MD
  Total:    100/72/52 MD

🚩 KEY ASSUMPTIONS TO VERIFY
  1. NCD VN = 25% of total VN (verify ICD-10 query)
  2. Pharmacy data integration feasibility (do spike Week 1-2)
  3. NCD elderly SPC adoption (caregiver proxy strategy?)

→ Approve / Adjust [field] / Reject
```

User: "Approve"

---

## Step 5: Build Workbook

```bash
python scripts/build_roi_workbook.py inputs.json /mnt/user-data/outputs/
```

Output: `MED-1.0.3_ROI.xlsx` (6 sheets, 156 formulas)

---

## Step 6: Run Validator (Stage A — always)

```bash
python scripts/validate_roi.py MED-1.0.3_ROI.xlsx
```

Output (v1.1 Pure ROI):
```json
{
  "red_flags": [
    {
      "rule": "RF-01",
      "message": "Y1 Best ROI 82.32x exceeds 20x cap"
    },
    {
      "rule": "RF-02",
      "message": "Y1 Base ROI 10.40x exceeds 10x — verify TAM logic + double-counting"
    }
  ],
  "warnings": [
    {
      "rule": "W-01",
      "message": "Y1 Base ROI 10.40x exceeds 5x"
    },
    {
      "rule": "W-04",
      "message": "Best:Worst ratio 65.7x indicates high uncertainty"
    }
  ],
  "passed_checks": ["formula_errors_zero", "tam_within_org_total", "confidence_tier_present", "strategic_fit_within_cap"],
  "trigger_review": true,
  "trigger_reason": "Triggered: 2 red flag(s)"
}
```

> **Note (v1.1):** Pure ROI numbers are higher than pre-v1.1 multiplier-adjusted ROI because Confidence + Strategic Fit no longer divide value down. RF-01/RF-02 firing more often is the honest signal — refine Worst/Base/Best ranges if ROI looks too aggressive (don't gloss over with multipliers).

---

## Step 7: Spawn Subagents (parallel, since trigger_review=true)

Main spawns 2 subagents in same turn:

**Subagent 1 (CFO):**
- Reads `agents/cfo_reviewer.md`
- Reviews workbook
- Saves to `MED-1.0.3_cfo_review.md`

**Subagent 2 (HoP):**
- Reads `agents/head_of_product_reviewer.md`
- Reviews workbook
- Saves to `MED-1.0.3_hop_review.md`

---

## Step 8: Synthesis + Present

```
✅ ROI Build Complete — MED-1.0.3 Refill Alert

📊 BOTTOM LINE (v1.1 Pure ROI)
  Y1 Base ROI:    10.40x  → 🟢 STRONG GO
  3-Yr Base ROI:  26.02x  → 🟢 STRONG GO
  Y1 Priority Score:  12.48x  (= Pure ROI × SF 1.20)  ← roadmap ranking only
  3-Yr Priority Score: 31.22x
  Build Effort: 72 MD (100/52)

📁 FILES
  - /mnt/user-data/outputs/MED-1.0.3_ROI.xlsx
  - /mnt/user-data/outputs/MED-1.0.3_summary.md
  - /mnt/user-data/outputs/MED-1.0.3_cfo_review.md
  - /mnt/user-data/outputs/MED-1.0.3_hop_review.md

🔍 REVIEW DECISION
  Triggered: Yes
  Reason: Triggered: 1 red flag(s) (RF-01: Y1 Best 53x exceeds 20x cap)

⚠️  VALIDATOR FLAGS (Stage A — v1.1 Pure ROI)
  🔴 RF-01: Y1 Best ROI 82.32x exceeds 20x cap
  🔴 RF-02: Y1 Base ROI 10.40x exceeds 10x — verify TAM + double-counting
  🟡 W-01: Y1 Base ROI 10.40x exceeds 5x
  🟡 W-04: Best:Worst ratio 65.7x (high uncertainty)
  
  ✅ Passed: formula_errors_zero, tam_within_org_total, confidence_tier_present, strategic_fit_within_cap

🔍 REVIEWER NOTES (Stage B)

  💼 Skeptical CFO:
    Q1: TAM 326K = NCD visits or unique patients?
        → If visits, double-counted at 6 cycles/yr → ROI may drop 50%
    Q2: ER cost avoidance 7.1M = patient/insurance saving, not Synphaet revenue
        → Recommend split: Hospital ROI vs System ROI sheets
    Q3: Refill conversion 35% — SOVDOC is US data, no TH NCD baseline
        → Pilot needed before claiming this rate to board

  🎯 Pragmatic Head of Product:
    P1: Pharmacy data integration risk = MEDIUM/HIGH but no spike done
        → Recommend 5-day spike before commit MD
    P2: Value Risk MEDIUM — ผู้ป่วย NCD ไม่ได้สัมภาษณ์
        → 5-10 NCD patient interviews before NOW commit
    P3: Pilot kill threshold "<15% conversion" — sample size?
        → Need 200+ patients × 3 months for statistical power

📊 RECOMMENDATION
  Numbers look strong but model has 3 issues to refine before CFO present:
  (1) TAM unique-vs-visits clarification, (2) Hospital vs System ROI split,
  (3) Pharmacy spike + NCD interview before NOW commit. Files ready for refinement.
  
  Decision is yours.
```

---

## Key Patterns This Example Shows

1. **Driver tree mandatory** — every value traces (Eff VN → D1 → D2 → D7 → revenue)
2. **3 scenarios always** — never single point
3. **Cost avoidance separate** — flagged explicitly
4. **Validator catches issues** — even when ROI looks good
5. **Reviewers add depth** — CFO + HoP catch different blind spots
6. **Advisor mode** — user retains decision authority
7. **Pure ROI defendable (v1.1)** — no Confidence × SF multipliers laundering the headline

---

## Anti-Patterns This Example Avoids

❌ Top-down "feature นี้น่าจะได้ 10M" — uses bottom-up driver chain
❌ Single ROI number — uses Worst/Base/Best
❌ US benchmark applied directly — applied 50% TH discount
❌ Cost avoidance counted as revenue — flagged + recommended split
❌ Best case 100x — capped at 20x with red flag
❌ Reviewer blocking output — advisor mode, user decides
❌ Confidence/SF multipliers inflating ROI — v1.1 drops both, Pure ROI = headline, Priority Score = ranking only
