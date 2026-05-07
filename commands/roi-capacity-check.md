---
description: Quick Q1-Q4 capacity vs allocation check — flags oversubscription per quarter
---

# /roi-capacity-check

Show how much MD effort is allocated per quarter vs available capacity. Flag any quarter that's oversubscribed.

When triggered, run:

```bash
python3 .claude/skills/roi-portfolio/scripts/update_phase_plan.py .
```

Parse the JSON output `capacity_used` + `capacity_total` + `oversubscription` fields and present:

```
🗓 Capacity Check — {today}

Quarter   Used / Cap   Util %   Status
─────────────────────────────────────────
Q1        135 / 150    90%      🟡 TIGHT
Q2        142 / 150    95%      🟡 TIGHT
Q3        150 / 150    100%     🟡 TIGHT
Q4        148 / 150    99%      🟡 TIGHT
─────────────────────────────────────────
Total     575 / 600    96%      🟡 TIGHT

⚠ OVERSUBSCRIPTION:
  (none — all quarters within capacity)

OR if oversubscribed:
  Q1: +37 MD over (need to KILL/DEFER 37 MD worth of features)

OVERFLOW FEATURES (didn't fit any quarter):
  - CARE-1.0 (104 MD)
  - DOC-SUG (88 MD)
  - ...
```

Status thresholds:
- 🟢 OK: util < 80%
- 🟡 TIGHT: util 80-100%
- 🔴 OVER: util > 100% (oversubscribed)

If oversubscribed or overflow features exist → suggest `/roi-kill-defer` next.

Capacity defaults to 600 MD/yr (150/quarter) unless `Per-Feature ROI/_inputs/_capacity_config.json` overrides.

Direct, no preamble.
