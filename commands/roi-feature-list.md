---
description: List all PE roadmap features ranked by Priority Score with tier + quarter assignment
---

# /roi-feature-list

Show all features in the PE roadmap, ranked by Priority Score (= Pure ROI × Strategic Fit), with their tier (🟢/🟡/🟠/🔴), assigned quarter, and current status.

When triggered, run:

```bash
python3 .claude/skills/roi-portfolio/scripts/update_phase_plan.py .
```

Then read the latest `Per-Feature ROI/PE_Roadmap_Phase_Plan_*.md` and present a compact table:

```
📋 PE Roadmap — N features ranked by Priority Score

Rank  Code            Tier  Y1 ROI  3Y ROI  SF    Priority  Effort  Quarter  Status
────────────────────────────────────────────────────────────────────────────────────
1     APT-2.0         🟢    8.5x    18.4x   1.30  11.05     91 MD   Q1       In Progress
2     INS-1.0         🟢    6.2x    21.8x   1.30  8.06      67 MD   Q1       Discovery
...
```

Compact, scannable. If feature has `status: KILLED` or `DEFERRED_*` in inputs.json, group at bottom.

If user passes a filter argument like `/roi-feature-list q1` or `/roi-feature-list 🟢`, filter accordingly:
- `q1`/`q2`/`q3`/`q4` → only that quarter
- `🟢` / `strong` / `go` → only STRONG GO tier
- `🔴` / `kill` → only KILL candidates
- code prefix like `APT` → only matching codes

Direct, no preamble.
