---
description: Quick PE roadmap portfolio overview — total features, tier distribution, capacity utilization, stale reviewers
---

# /roi-status

Print a one-screen overview of the entire PE roadmap portfolio.

When triggered, run the following command and present the JSON output as a structured summary:

```bash
python3 .claude/skills/roi-portfolio/scripts/update_phase_plan.py .
```

(Adjust path if plugin is installed in a different location — fall back to `${CLAUDE_PLUGIN_ROOT}/skills/roi-portfolio/scripts/update_phase_plan.py` if `.claude/skills/` doesn't have the file.)

Then format the output as:

```
📊 PE Roadmap Status — {today}

FEATURES: {n_features} total
  🟢 STRONG GO ({y1>=5x}):  {count}
  🟡 CONDITIONAL (1.5-5x):  {count}
  🟠 DEFER (1-1.5x):         {count}
  🔴 KILL (<1x):             {count}

CAPACITY (Q1-Q4):
  Q1: {used}/{cap} MD ({status emoji})
  Q2: {used}/{cap} MD ({status emoji})
  Q3: {used}/{cap} MD ({status emoji})
  Q4: {used}/{cap} MD ({status emoji})

OVERSUBSCRIPTION: {if any quarter > cap, show delta}

PHASE PLAN: {path to latest PE_Roadmap_Phase_Plan_*.md}
```

Also scan `Per-Feature ROI/review/` for `.stale` files — flag count if > 0:

```bash
ls Per-Feature\ ROI/review/*.stale 2>/dev/null | wc -l
```

If any stale reviewers found, append:
```
⚠ STALE REVIEWERS: {count} feature(s) need re-review (run roi-deep-review)
```

Keep output under 30 lines. Direct, no preamble.
