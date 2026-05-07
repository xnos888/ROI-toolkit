---
description: Run inline validator on every per-feature ROI workbook — sanity sweep before leadership review
---

# /roi-validate-all

Run `validate_roi.py` on every `{CODE}_ROI.xlsx` in `Per-Feature ROI/`. Aggregate red flags + warnings + formula integrity issues across the whole portfolio. Use as a pre-flight check before publishing master rollup or quarterly Phase Plan to leadership.

When triggered:

```bash
for f in "Per-Feature ROI"/*_ROI.xlsx; do
  [[ "$f" == *.bak* ]] && continue
  python3 .claude/skills/roi-build/scripts/validate_roi.py "$f"
done
```

Aggregate the JSON outputs and present:

```
🛡 Validator Sweep — {today}

N features validated:

═══════════════════════════════════════════════════════
RED FLAGS (require attention)
─────────────────────────────────────────────────────────
APT-2.0   RF-01  Y1 Best 28x exceeds 20x cap
MED-1.0   RF-04  Cost-avoidance 61% — recommend Hospital/System split
...

WARNINGS (advisory)
─────────────────────────────────────────────────────────
BIL-1.0   W-04   D7 source weak (T4)
...

FORMULA INTEGRITY (FI-01..FI-03)
─────────────────────────────────────────────────────────
✓ All N features passed formula integrity

PORTFOLIO HEALTH SUMMARY
─────────────────────────────────────────────────────────
  Clean (zero flags):         X features
  Warning-only:               Y features
  Red flag (blocking):        Z features
═══════════════════════════════════════════════════════

NEXT STEPS:
  - For each RF-04: consider roi-adjust + set is_system_value: true on the affected component
  - For each RF-01 (Best > 20x): add narrative caveat in summary.md
  - For each formula integrity issue: rebuild via roi-build (RF-06 auto-repair will run)
```

If features have hard errors (crashed validator):
```
⚠ X features failed validation entirely:
  - {CODE}: {stderr summary}
  Likely cause: workbook structure broken — rebuild via roi-build
```

Direct, no preamble. Useful before any portfolio publish or board prep.
