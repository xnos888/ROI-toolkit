# Driver Tree Patterns by Category

Per-category driver tree templates. Use these as starting points — adapt to specific feature.

## Why Driver Trees Matter

A driver tree decomposes outcome into **chain of cause-effect**:

```
ROI
├── Revenue Impact
│   ├── Driver A1 (volume-related)
│   └── Driver A2 (price-related)
└── Cost Impact
    ├── Driver B1 (ops savings)
    └── Driver B2 (cost avoidance)
```

Without driver tree, ROI is a guess. With driver tree:
- Every number traces to inputs
- Stakeholders can challenge specific drivers
- Leading indicators map to drivers (validation plan)
- Sensitivity analysis becomes possible

---

## Category 1: Appointment & Booking

**Use for:** APT-1.0, APT-2.0, online booking, slot management, reminders

```
Appointment Feature ROI
├── REVENUE: No-show reduction
│   ├── D1: Reminder coverage % (target 95%)
│   ├── D2: Reminder timing effectiveness (24h + 2h before)
│   ├── D3: Easy reschedule rate
│   └── D4: Recovered slot fill rate
│       → Outcome: Show-up rate ↑ → Revenue per OPD slot
│
└── OPS COST: Call center time saved
    ├── D5: Manual reminder calls eliminated (min/call × volume)
    └── D6: Reschedule handling automated %
        → Outcome: Nurse/admin time saved × hourly rate
```

**Key CFs to research:**
- Show-up rate uplift from reminder system (industry: 5-15%)
- Reminder ROI (SOVDOC: 20-40% no-show reduction)
- Manual call time per appointment (typical: 5-8 min)

---

## Category 2: Queue Management

**Use for:** QMC-1.0, QPH-1.0, QFJ-1.0, queue optimization

```
Queue Feature ROI
├── REVENUE: Capacity utilization ↑
│   ├── D1: Counter utilization rate (multi-counter sharing)
│   ├── D2: Patient throughput per hour
│   └── D3: Reduced abandonment rate
│       → Outcome: More patients served → revenue
│
├── PATIENT EXPERIENCE: Wait time ↓
│   ├── D4: Avg wait time reduction (min)
│   └── D5: Visibility/transparency uplift
│       → Outcome: Satisfaction ↑ → retention ↑
│
└── OPS COST: Less manual queue management
    ├── D6: Nurse/staff time managing queue
    └── D7: Complaint handling reduction
```

**Key CFs:**
- Counter utilization improvement from load balancing (5-15%)
- Wait time reduction from visibility (10-25%)
- Complaint rate reduction (industry: 30-50%)

---

## Category 3: Medication

**Use for:** MED-1.0 (Info, Reminder, Refill), MED-DLV

```
Medication Feature ROI
├── REVENUE: Refill / Repeat OPD visits
│   ├── D1: Alert → refill conversion rate
│   ├── D2: Incremental refills (would not happen w/o alert)
│   └── D3: Avg revenue per refill visit
│       → Outcome: Repeat OPD revenue ↑
│
├── COST AVOIDANCE: ER/IPD prevention (NOT hospital revenue!)
│   ├── D4: ER/IPD events avoided per alert
│   └── D5: Avg cost per ER/IPD event
│       → Outcome: System-level cost avoidance
│       ⚠️ Show separately, not in Hospital ROI
│
├── RETENTION: NCD patient continuity
│   ├── D6: Care continuity rate
│   └── D7: Patient lifetime value uplift
│
└── OPS COST: Nurse "ขาดยา" calls reduced
    ├── D8: Calls prevented per alert sent
    └── D9: Avg call handling time × cost/min
```

**⚠️ CRITICAL:** Cost avoidance (Driver D4-D5) is NOT hospital revenue. Always show separately as "System ROI" vs "Hospital ROI".

**Key CFs:**
- Refill conversion (industry: 30-50%, discount for TH context)
- Adherence-related ER avoidance (heavy proxy, T4)
- Nurse call reduction (estimate, T4)

---

## Category 4: Results & Records (Lab, Imaging)

**Use for:** LAB-*, IMG-1.0, LIC-1.0, lab result delivery

```
Lab/Imaging Feature ROI
├── REVENUE: Repeat visits / Test orders
│   ├── D1: Result access → follow-up visit rate
│   ├── D2: Comparison feature → repeat lab orders
│   └── D3: Avg revenue per follow-up
│
├── PATIENT EXPERIENCE: Time-to-result
│   ├── D4: Wait time for result reduction
│   └── D5: Self-service access vs nurse-mediated
│
└── OPS COST: Result distribution time saved
    ├── D6: Nurse calls reduced (result inquiry)
    └── D7: Admin time saved (paper handling)
```

**Key CFs:**
- Result access driving follow-up (10-20% lift)
- Reduced result inquiry calls (30-50%)

---

## Category 5: Payment & Finance

**Use for:** PAY-1.0, ERC-1.0, CHS-1.0

```
Payment Feature ROI
├── REVENUE: Faster collection
│   ├── D1: Payment completion rate
│   ├── D2: Days-to-collect reduction
│   └── D3: Recovery rate on unpaid
│
├── PATIENT EXPERIENCE: Friction ↓
│   ├── D4: Self-payment adoption rate
│   └── D5: Avg time saved per transaction
│
└── OPS COST: Cashier/admin time
    ├── D6: Manual payment processing eliminated
    └── D7: Reconciliation time saved
```

---

## Category 6: Communication & Care

**Use for:** DCH-1.0, AIB-1.0, MCT-1.0 (Cert), Doctor Chat, FAQ Bot

```
Communication Feature ROI
├── REVENUE: Reduced lost demand
│   ├── D1: Inquiry → conversion rate (FAQ → booking)
│   └── D2: Async chat → revisit avoidance
│
├── RETENTION: Engagement ↑
│   ├── D3: Patient activation rate
│   └── D4: Retention uplift
│
└── OPS COST: Call center load
    ├── D5: Inquiries deflected from human
    └── D6: After-hours handling
```

---

## Category 7: Visit Experience (Pre/During/Post)

**Use for:** VST-1.0, PCI-1.0, SQA-1.0

```
Visit Experience Feature ROI
├── PATIENT EXPERIENCE: Better consultation
│   ├── D1: Consultation time efficiency
│   └── D2: Question coverage / completeness
│
├── REVENUE: Reduced unnecessary revisits
│   ├── D3: Forgot-to-ask → revisit rate reduction
│   └── D4: Per-revisit revenue offset
│
└── OPS COST: Doctor/nurse time
    ├── D5: Doctor time per consult saved
    └── D6: Phone follow-up reduced
```

---

## Selecting the Right Tree

1. Match feature category to template above
2. Adapt — remove drivers that don't apply, add ones that do
3. **Validate driver independence** — no double-counting between drivers
4. **Identify cost avoidance vs revenue** — keep separate
5. **Pick top 3-5 drivers** — too many = over-engineering, too few = missing mechanism

---

## Anti-Patterns

❌ **Single driver tree without scenarios** — always Worst/Base/Best
❌ **Overlapping drivers** — e.g., "no-show ↓" AND "show-up ↑" (same thing)
❌ **Cost avoidance counted as revenue** — separate it
❌ **Driver without CF source** — every driver needs benchmark + citation
❌ **Driver that can't be measured** — leading indicator must exist
