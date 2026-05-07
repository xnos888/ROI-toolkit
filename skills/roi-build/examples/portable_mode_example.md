# Portable Mode Walkthrough

When the user does NOT have `Hospital_Baseline_DB.xlsx` in their project, the skill switches to **portable mode** — collecting baseline values inline.

This walkthrough shows the flow for a user at a different hospital (not Synphaet) who wants to evaluate a Refill Alert feature.

---

## Step 1: Skill Detects No Baseline

Skill checks for baseline file in this order:
1. `/mnt/project/Hospital_Baseline_DB.xlsx` ❌ Not found
2. `/mnt/user-data/uploads/Hospital_Baseline_DB.xlsx` ❌ Not found

→ **Portable mode activated**

---

## Step 2: Skill Asks for Minimum Baseline (6 values)

```
ไม่พบ Hospital baseline file. ขอ baseline values 6 ตัว 
(ใช้ default ได้ถ้าไม่ทราบ):

1. Total VN/year ของรพ.?            [default: 1,000,000]
2. Avg revenue per OPD VN (THB)?     [default: 3,000]
3. Target patient cohort size/year?  (เช่น NCD VN/year — 25-30% ของ total)
4. Avg refill cycles per patient/yr? [default: 6]
5. Nurse call handling time (min)?   [default: 8]
6. Avg revenue per refill visit?     [default: 2,200]
```

User pastes:
```
1. 800,000
2. 3,500
3. 200,000 (NCD)
4. 6
5. 7
6. 2,500
```

---

## Step 3: Skill Builds `inputs.json` with User-Provided Baseline

Skill generates:

```yaml
baseline:
  - metric: "Total VN per year"
    value: 800000
    unit: "VN"
    source: "User input (portable mode)"
  - metric: "Avg Revenue per OPD VN"
    value: 3500
    unit: "THB"
    source: "User input (portable mode)"
  - metric: "NCD-related VN per year"
    value: 200000
    unit: "VN/yr"
    source: "User input (portable mode)"
  - metric: "Avg refill cycles per NCD/year"
    value: 6
    unit: "cycles/yr"
    source: "User input (portable mode)"
  - metric: "Nurse call handling time"
    value: 7
    unit: "min/call"
    source: "User input (portable mode)"
  - metric: "Avg Revenue per Refill OPD visit"
    value: 2500
    unit: "THB"
    source: "User input (portable mode)"
```

→ Rest of pipeline (TAM-SAM-SOM, CFs, build, validate, review) **identical** to project mode

---

## Step 4: Skill Adjusts Defaults If Needed

If user wants different MD cost (default 24,000 THB) or MA rate (default 30%), skill asks:

```
Custom defaults? (กด Enter ถ้าใช้ default)
- Blended MD cost (THB/MD): [24,000]
- MA rate (%/yr of build):  [30%]
```

---

## Step 5: Continue Normal Flow

From here on, behavior is **same as project mode**:

1. Stage 1 preview → user approves
2. `build_roi_workbook.py` builds 6-sheet xlsx
3. `validate_roi.py` runs sanity checks
4. If trigger: spawn 2 reviewer subagents
5. Synthesis + present

---

## Differences vs Project Mode

| Aspect | Project Mode | Portable Mode |
|--------|--------------|---------------|
| Baseline source | `Hospital_Baseline_DB.xlsx` | User paste |
| Baseline credibility | Tier T1 (internal data) | Tier T2-T3 (user-provided estimate) |
| Confidence multiplier | Default 0.5 | Default 0.4 (lower because baseline is less verified) |
| Source citation in Sheet 6 | DB path | "User input (portable mode)" |
| Cross-feature consistency | Same baseline → comparable across features | Each session independent |

---

## When Portable Mode Should Be Used

- ✅ User is at a hospital without project setup
- ✅ User wants quick estimate without DB
- ✅ User is evaluating feature for hypothetical hospital
- ✅ User is using skill outside Synphaet context

---

## When Portable Mode Should NOT Be Used

- ❌ User has Hospital_Baseline_DB.xlsx but skill missed detecting it (check `/mnt/project/` and `/mnt/user-data/uploads/`)
- ❌ User wants to compare multiple features (use project mode for consistency)
- ❌ User is presenting to executives (project mode has stronger source citations)

---

## Validator Behavior in Portable Mode

Validator rules apply identically except:

- **RF-03** (TAM > 1.5x org total) uses user-provided "Total VN/year" instead of fixed 1.3M
- **Source citation check (W-05)** — counts "User input (portable mode)" as valid source

---

## Example Output Difference

**Project mode:**
```
🔍 REVIEW DECISION
  Triggered: Yes
  Reason: Triggered: 1 red flag(s)
  
📊 BOTTOM LINE
  Y1 Base ROI: 6.76x  (using Synphaet baseline)
```

**Portable mode:**
```
🔍 REVIEW DECISION
  Triggered: Yes
  Reason: Triggered: 1 red flag(s)
  
📊 BOTTOM LINE
  Y1 Base ROI: 5.43x  (using user-provided baseline)
  
⚠️  PORTABLE MODE NOTE
  Baseline values from user input — not verified against HIS data.
  Recommend re-running with verified baseline before commit.
```
