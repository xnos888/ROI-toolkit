# Conversion Factor Library

> **Role in v1.0:** **FALLBACK ONLY**
> 
> Step 2.5 (mandatory research) does live web_search for every CF at build-time. This library is used **only when search fails** (Q2=C try-then-degrade strategy). Library values are forced T4 tier when used as fallback.
>
> **Why keep this library?**
> - Bootstrap reference for new CF mechanisms (taxonomy + structure)
> - Fallback when web_search rate-limited or yields no usable results
> - Documents discount methodology applied during research
>
> **Do NOT manually update this library to "fresh" values** — that's what Step 2.5 is for. This library should remain stable and conservative.

Library of researched CFs with sources, geographical/maturity discount logic, and confidence tiers.

## Tier System (v1.1: metadata only)

| Tier | Confidence | When to Use |
|------|-----------|-------------|
| T1 | High | Internal data (Tableau, HIS, post-launch reports) |
| T2 | Medium-High | 1 case study + 1 corroborating, similar population |
| T3 | Medium | Industry benchmark, different geography |
| T4 | Low | Single source / heavy proxy / expert estimate |

**Tier is metadata — confidence label only, never multiplied into value.** Pure ROI = Business Value / Cost. Uncertainty signals come from the Worst/Base/Best spread + W-02 validator rule (T4 + Pure ROI > 3x flagged).

---

## Discount Methodology

When applying US/Western benchmarks to Thai healthcare context:

| Factor | Typical Discount | Reason |
|--------|------------------|--------|
| Geographic (US → TH) | -30% | Healthcare maturity gap |
| Patient digital literacy | -20% | Adoption slower in TH |
| Implementation risk | -15% | First-time deployment |
| Integration complexity | -10% | HIS legacy systems |
| **Total typical** | **~50-60%** | Cumulative |

**Rule of thumb:** Take US benchmark median, apply 0.5x for Base scenario, 0.3x for Worst, 0.7x for Best.

---

## Library: Appointment & No-Show

### CF-APT-01: No-show reduction from reminders

| Source | Region | Range | Tier |
|--------|--------|-------|------|
| SOVDOC (2025) | US | 20-40% | T3 |
| Synphaet APT-1.0 (2026 post-launch) | TH internal | +5.96% show-up uplift | T1 |

**Recommendation for TH features:**
- Worst: 5% reduction
- Base: 10% reduction
- Best: 20% reduction

### CF-APT-02: Manual reminder call time

| Source | Range | Tier |
|--------|-------|------|
| Industry standard | 5-8 min/appt | T2 |

**Use:** 6 min (Base), 8 min (Worst), 5 min (Best)

---

## Library: Medication

### CF-MED-01: Refill alert → conversion rate

| Source | Region | Range | Tier |
|--------|--------|-------|------|
| Express Scripts (US, NCD adherence) | US | 30-50% | T3 |
| SOVDOC patient engagement | US | 20-40% (proxy) | T3 |

**TH discount applied:**
- Worst: 20%
- Base: 35%
- Best: 50%

### CF-MED-02: Incremental refill rate (vs would-have-refilled)

**No reliable source** — heavy judgment. Conservative estimates:
- Worst: 30%
- Base: 50%
- Best: 70%

Tier: T4 — flag as "verify via cohort comparison post-pilot"

### CF-MED-03: ER/IPD avoidance from adherence

| Source | Range | Tier |
|--------|-------|------|
| Multiple US adherence studies | 1-3% | T4 |

**⚠️ Warning:** Heavy proxy. Use:
- Worst: 0.5%
- Base: 1.5%
- Best: 3.0%

**Always tier T4** unless internal cohort data available.

### CF-MED-04: Avg cost per ER/IPD event avoided

| Component | TH Cost (THB) |
|-----------|---------------|
| ER visit | 3,000-5,000 |
| 1-day IPD admission | 30,000-50,000 |
| Mix (typical NCD) | 8,000-25,000 |

**⚠️ CRITICAL:** This is cost-avoidance for patient/insurance. NOT hospital revenue. Show separately.

### CF-MED-05: Nurse "ขาดยา" call reduction

**Estimate, T4:**
- Worst: 5%
- Base: 10%
- Best: 15%

Verify via call center log post-pilot.

---

## Library: Queue Management

### CF-QUE-01: Counter utilization improvement (load balancing)

| Source | Range | Tier |
|--------|-------|------|
| Operations research (general) | 10-20% | T3 |

**TH discount:**
- Worst: 5%
- Base: 12%
- Best: 18%

### CF-QUE-02: Wait time reduction from visibility

| Source | Range | Tier |
|--------|-------|------|
| Patient experience studies | 15-30% perceived | T3 |

---

## Library: Lab/Imaging Results

### CF-LAB-01: Result access driving follow-up visit

| Source | Range | Tier |
|--------|-------|------|
| Patient portal studies (US) | 10-25% | T3 |

**TH discount:**
- Worst: 5%
- Base: 12%
- Best: 20%

### CF-LAB-02: Result inquiry call reduction

| Source | Range | Tier |
|--------|-------|------|
| Industry estimate | 30-50% | T3 |

---

## Library: Payment

### CF-PAY-01: Self-payment adoption rate

| Source | Range | Tier |
|--------|-------|------|
| FinTech adoption (TH retail) | 30-60% | T2 |

### CF-PAY-02: Manual payment processing time

| Component | Time |
|-----------|------|
| Cashier transaction | 3-5 min |
| Reconciliation per day | 2-3 hours |

---

## Library: Communication / Bot

### CF-COM-01: FAQ chatbot deflection rate

| Source | Range | Tier |
|--------|-------|------|
| Customer service AI (general) | 30-60% | T3 |

**Healthcare-specific discount:**
- Worst: 15%
- Base: 30%
- Best: 50%

### CF-COM-02: Async chat → revisit avoidance

**Estimate, T4:**
- Worst: 5%
- Base: 15%
- Best: 25%

---

## Researching New CFs (now automated in v1.0)

In v1.0, research is **automated via `scripts/research_cf.py`** during Step 2.5. The skill handles:

1. **Web search** — 2 queries per CF (max), via `web_search` tool
2. **Source tier classification** — T1-T4 based on URL signals
3. **Numeric range extraction** — regex from snippets
4. **TH discount application** — geographic + maturity + execution
5. **Cache management** — same mechanism queried once per session

**Manual research is no longer the protocol** — skill enforces this automatically.

### When manual research still applies

- Adding a new mechanism category to `decompose_subfeatures.py` taxonomy
- Updating the static library with new fallback values (rare — every 6-12 months)
- Building a new feature category not covered by existing patterns

For these cases, follow the legacy protocol below as guidance:

**Legacy manual protocol:**

1. **Web search** 2-3 sources for the mechanism
   - Prefer: peer-reviewed studies, hospital case studies, government health stats
   - Acceptable: industry reports (Bain, Deloitte, McKinsey)
   - Avoid: vendor blog posts (biased)

2. **Extract:** numeric range, study population, geography

3. **Cite in update:**
   ```
   [Mechanism] — Worst/Base/Best — Source: [Author Year, Country, Population]
   ```

4. **Tag tier honestly:**
   - T2 = 1 case study + 1 corroborating, similar population
   - T3 = industry benchmark, different geography
   - T4 = single source / heavy proxy

5. **Apply discount logic** (geographic + maturity + execution)

**Anti-pattern:** Inventing CF range from "expert judgment" without citation.

---

## Strategic Fit (Priority Score Input — v1.1)

> **Used for roadmap ranking only. NEVER multiplied into Pure ROI.**

| Component | Range | Logic |
|-----------|-------|-------|
| Cost-saving alignment | 1.0-1.2x | Reduces ops cost vs strategic priority |
| Catch-up vs competitor | 1.0-1.3x | Bumrungrad, Samitivej have it, we don't |
| Patient retention/value | 1.0-1.2x | Increases CLV |

**Multiplicative application (for Priority Score):**
```
Strategic Fit = Cost × Catch-up × Value
Example: 1.0 × 1.2 × 1.0 = 1.20x

Priority Score = Pure ROI × Strategic Fit
   ↓
ใช้สำหรับ ranking features ใน roadmap meeting (rank > value claim)
```

**Cap at 1.5x** — if higher, validator W-03 flags for justification (Priority Score may be inflated).

---

## Pure ROI Methodology (v1.1)

```
Pure ROI = Business Value / Cost
   ↓
Headline number, defendable to board, no laundering

Priority Score = Pure ROI × Strategic Fit (1.0-1.5x)
   ↓
Roadmap sequencing only, separate column on Sheet 5

Confidence Tier (T1/T2/T3/T4)
   ↓
Metadata label only, never multiplied. Validator W-02 flags T4 + Pure ROI > 3x
```

**Example (MED-1.0, T3 + SF 1.30x):**
```
Total Value Y1 = 19.5M THB (sum of components, no multipliers)
Y1 Cost = 1.99M THB
Pure Y1 ROI = 19.5M / 1.99M = 9.78x
Priority Score Y1 = 9.78 × 1.30 = 12.71x
```

**Why dropped multipliers in v1.1:**
- Confidence multiplier duplicated Worst/Base/Best spread (Base × 0.5 = Worst-in-disguise)
- Strategic Fit double-counted drivers already in value tree (Component A retention, Component C cost saving)
- Both inflated/deflated headline ROI mechanically — analysis laundering board would reject
