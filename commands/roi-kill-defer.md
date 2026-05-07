---
description: Propose KILL/DEFER candidates based on (Pure ROI < threshold) AND (Strategic Fit < threshold) AND capacity tightness — for end-of-batch decision support
---

# /roi-kill-defer

Use roi-portfolio Mode C to propose KILL/DEFER candidates per the project criterion (NOT just ROI alone — must also fail Strategic Fit + capacity tightness).

When triggered, run:

```bash
python3 .claude/skills/roi-portfolio/scripts/update_phase_plan.py --propose-kill-defer .
```

Parse the JSON `proposals` array and present:

```
🔪 KILL/DEFER Candidates — {today}

Criterion:
  KILL  = (Pure ROI < 1.0x) AND (Strategic Fit < 1.2)
  DEFER = (Pure ROI 1.0-1.5x) AND (Strategic Fit < 1.4)

═══════════════════════════════════════════════════════
Code         Action  Y1 ROI  SF    Effort  Rationale
─────────────────────────────────────────────────────────
DOC-SUG      🔴 KILL 0.01x   1.05  88 MD   No financial OR strategic case (SF<1.2)
PFE-2.0      🔴 KILL 0.52x   1.30  74 MD   ...
PFE-1.0      🟠 DEFER 1.20x  1.30  73 MD   Defer until ROI proven via pilot

TOTAL FREED CAPACITY (if all approved): X MD
═══════════════════════════════════════════════════════

⚠ NOT proposed (high SF — strategic case overrides low ROI):
  - PFE-1.0 (Y1 0.5x but SF 1.4) — keep, surface as strategic bet
  - ...
```

After presenting:
1. Ask Kim to approve which candidates to act on
2. For each approved feature → trigger `roi-adjust` with `feature.status: "KILLED"` or `"DEFERRED_Q3"`
3. After all status updates → trigger `roi-portfolio` Mode B (re-aggregate Pipeline_Summary)

This is decision support, not auto-execute. User retains final call (per CLAUDE.md "Reviewer = advisor, not gate" rule).

Direct, no preamble.
