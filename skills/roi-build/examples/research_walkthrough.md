# Research Walkthrough — APT-2.0 Appointment 2.0

End-to-end example showing Step 2.5 research mechanism. Uses APT-2.0 from Kim's Top 15 ROI Plan as input.

---

## Step 1: User Trigger

User: "ทำ ROI ให้ APT-2.0 — Appointment 2.0 ตาม Top 15 Plan"

Skill loads:
- `/mnt/project/Hospital_Baseline_DB.xlsx` ✅
- 3 reference files

---

## Step 2: Collect Inputs

User provides (from Top 15 Plan):
- **Code:** APT-2.0
- **Name:** Appointment 2.0 (Online Booking + LINE OA 2-way)
- **Sub-features:**
  - Self-service slot booking 24/7
  - Reschedule/Cancel ออนไลน์
  - LINE OA 2-way confirm
- **Primary Outcome:** O1 - No-show Reduction
- **Industry Evidence (user-provided):** "Epic 21M fewer no-shows, 21.5% reduction. WakeMed +21% outpatient revenue."
- **Effort:** 80/60/45 MD

---

## Step 2.5: Research & Verify (NEW — MANDATORY)

### Stage 2.5a: Decompose Sub-features

```bash
python scripts/decompose_subfeatures.py inputs.json decomp.json decomp.md
```

**Output:**

```
🔴 multiple_mechanisms_bundled
Found 3 distinct mechanisms in one feature:
  - lost_demand_capture (Self-service booking 24/7)
  - slot_recovery (Reschedule/Cancel)
  - no_show_reduction (LINE OA 2-way confirm)

🔴 outcome_mechanism_mismatch
Stated outcome: "O1 - No-show Reduction"
Inferred from outcome: no_show_reduction
But sub-features address: lost_demand_capture, slot_recovery, no_show_reduction
→ Outcome may not capture actual value drivers

RECOMMENDED: Split into separate features OR multi-outcome model
```

**User decision required:**
- A) Split APT-2.0 into 3 separate ROI builds
- B) Build single ROI with 3 explicit value components
- C) Override and proceed (accept double-counting risk)

User picks **B** — single ROI with 3 value components (matches roadmap structure).

### Stage 2.5b: Plan Research Queries

For each CF, generate 2 search queries:

```
D1 (Lost demand capture rate):
  Q1: "online appointment booking after-hours adoption rate healthcare benchmark study"
  Q2: "self-service booking hospital adoption rate"

D2 (Slot recovery rate):
  Q1: "appointment cancellation slot recovery healthcare benchmark study"
  Q2: "reschedule online hospital adoption rate"

D3 (No-show reduction from 2-way confirm):
  Q1: "LINE 2-way confirmation no-show reduction healthcare benchmark study"
  Q2: "two-way SMS appointment reminder hospital adoption rate"

D4 (Avg revenue per OPD visit):
  → SKIP — T1 internal data from baseline

(Plus verification queries for user's industry claims)
Q-V1: "Epic 21M no-show reduction case study verification"
Q-V2: "WakeMed online scheduling outpatient revenue 21%"
```

**Cache check:** No CFs cached yet (first feature in batch).

### Stage 2.5c: Execute Web Searches

Orchestrating Claude runs `web_search` for each query. Captures top 3-5 results per query.

Example results for D3:

```json
[
  {
    "url": "https://pubmed.ncbi.nlm.nih.gov/12345",
    "title": "Two-way SMS appointment reminders RCT in Asian healthcare",
    "snippet": "...intervention reduced no-show by 25% (95% CI 18-32%)..."
  },
  {
    "url": "https://www.healthcareitnews.com/...",
    "title": "Hospital adopts 2-way messaging — 18% no-show reduction",
    "snippet": "...case study showed 18% reduction over 6 months..."
  },
  {
    "url": "https://example-vendor.com/blog/...",
    "title": "Our 2-way SMS reduces no-shows by 40%",
    "snippet": "...vendor claims 40% reduction in pilot..."
  }
]
```

### Stage 2.5d: Ingest Results

Skill processes each result:

| Source | Tier (auto-classified) | Range Extracted |
|--------|------------------------|-----------------|
| pubmed.ncbi.nlm.nih.gov | T2 (peer-reviewed) | 18-32% |
| healthcareitnews.com | T3 (industry case study) | 18% |
| example-vendor.com/blog | T4 (vendor blog) | 40% |

**Tier decision:** T2 (best tier among sources)
**Aggregate ranges:** Average of T2 + T3 = 18-25% (vendor T4 excluded)

**TH discount applied** (US sources):
- US Base: 22% (mid of 18-25%)
- TH Worst: 22% × 0.43 × 0.6 = **5.7%**
- TH Base: 22% × 0.43 = **9.5%**
- TH Best: 22% × 0.43 × 1.5 = **14.2%**

### Stage 2.5e: Verify User's Industry Claims

```
CLAIM 1: "Epic 21M fewer no-shows"
  Source verified: Epic Press Release 2023 [T3]
  Caveat found: "21M cumulative across 600+ Epic customers, 5 years"
  Per-customer per-year: 21M ÷ 600 ÷ 5 = ~7,000/year
  Conclusion: Headline number misleading. Adjusted: 7K reduction/yr/hospital scale.

CLAIM 2: "WakeMed +21% outpatient revenue"
  Source verified: WakeMed Internal Report 2022 [T3]
  Caveat found: "Includes new clinic openings + marketing campaign"
  Pure online booking attribution: 5-8% (best estimate from study text)
  Conclusion: Original 21% includes confounders. Adjusted: 5-8%.
```

### Stage 2.5f: Save Audit Trail

Output: `APT-2.0_research_validation.md`

Contains:
- Per-CF research summary
- All sources with URLs + tier classifications
- User claim verification (Epic and WakeMed)
- Cache statistics (0 hits — first feature)
- Reproducibility snapshot

---

## Step 3: Stage 1 Preview (with researched values)

Now CFs reflect research, not user-provided guesses:

```
🔧 CONVERSION FACTORS (research-validated)

D1 (Lost demand capture rate)
  Worst 8% / Base 15% / Best 25% [T3]
  Source: McKinsey Healthcare Digital Adoption 2024 + 2 corroborating
  TH discount applied (US source)

D2 (Slot recovery rate)
  Worst 20% / Base 35% / Best 50% [T3]
  Source: Beckers Hospital Review case studies

D3 (No-show reduction from 2-way confirm)
  Worst 5.7% / Base 9.5% / Best 14.2% [T2]  ← upgraded from initial estimate
  Source: PubMed RCT (Asian healthcare context, T2 strong)
  
D4 (Avg revenue per OPD visit)
  3,000 THB [T1 — internal]

⚠️  USER CLAIM CORRECTIONS (from verification):
- Epic "21M fewer no-shows" → adjusted to ~7K/hospital/year
- WakeMed "21%" → adjusted to 5-8% pure attribution
```

User reviews → Approves.

---

## Step 4-8: Same as Standard Pipeline

- Step 4: Build xlsx (now references researched CFs)
- Step 5: Validator runs (W-11 checks research quality, passes)
- Step 6: Trigger decision based on validator + research findings
- Step 7: Reviewers (CFO + HoP) — CFO will reference research_validation.md
- Step 8: Summary auto-generated, **includes research summary section**

---

## Final Output Files

```
/mnt/user-data/outputs/
├── APT-2.0_ROI.xlsx                    ← 6 sheets, research-backed CFs
├── APT-2.0_summary.md                  ← bottom line + decision tier
├── APT-2.0_research_validation.md      ← AUDIT TRAIL (NEW)
├── APT-2.0_decomposition.md            ← sub-feature analysis (NEW)
├── APT-2.0_cfo_review.md               ← if triggered
└── APT-2.0_hop_review.md               ← if triggered
```

---

## Key Difference vs v0.9

| Aspect | v0.9 (no research) | v1.0 (with research) |
|--------|--------------------|--------------------|
| CF source | Static library | Live web_search per CF |
| Tier | Static label | Auto-classified T1-T4 |
| User industry claims | Trusted as-is | Verified, often adjusted |
| TH discount | Library has it baked in | Applied dynamically per source |
| Audit trail | No | research_validation.md mandatory |
| Build time | ~30 sec | ~2-3 min (incl. searches) |
| Defendable to C-Level | Marginal | Strong |
| Token cost | 5K | 30-50K (3-5× more) |

---

## When Research Pays Off

✅ **Worth it:**
- Top 15 ROI Plan — 3 batches, multiple features, present to C-Level
- Industry evidence in input is unverified/from vendor pitch
- Feature is high-stakes (>$1M decision)
- TH-specific context (US benchmarks need adjustment)

❌ **Maybe overkill:**
- Quick estimation for personal exploration
- Internal team brainstorming (not for board)
- Feature with strong existing internal data (T1)
- Already presented to C-Level once (have audit trail from prior)

For Kim's Top 15 ROI Plan workflow — **research is mandatory** because each batch presented to C-Level demands defensibility.

---

## Cache Behavior in Batch (5 features)

```
Batch 1: APT-2.0 (5 CFs researched, 0 cache hits)
         → Cache populated with: lost_demand_capture, slot_recovery, no_show_reduction, ...

Batch 2: APT-3.0 (3 CFs)
         → 2 cache hits (no_show_reduction reused from APT-2.0)
         → 1 fresh search

Batch 3: MED-1.0.3 (7 CFs)
         → 0 cache hits (different mechanism category)
         → 7 fresh searches

Total: 12 fresh searches across 3 features (vs 15 without cache)
       Token savings: ~20% in this small batch
       
For 15-feature batch: token savings expected 50-70%
(Common CFs like no-show, refill, queue wait time appear repeatedly)
```
