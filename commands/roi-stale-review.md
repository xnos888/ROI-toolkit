---
description: List features whose reviewer files are .stale (auto-marked after tier-shifting adjusts) — suggests re-running roi-deep-review
---

# /roi-stale-review

Find all features whose CFO + HoP reviewer files have been marked `.stale` (post-tier-shift after a roi-adjust). These features have ROI numbers that have moved beyond the verdict scope of their last review — re-review recommended before leadership presentation.

When triggered:

```bash
ls Per-Feature\ ROI/review/*.stale 2>/dev/null
```

Group results by feature code (extract from filename pattern `{CODE}_iter_{N}_{cfo,hop}.md.stale`).

Present:

```
⚠ Stale Reviewer Files — {today}

N features need re-review:

═══════════════════════════════════════════════════════
Feature      Last Reviewed  Stale Since  Reason
─────────────────────────────────────────────────────────
APT-2.0      iter_2 (2026-05-04)  2026-05-06   tier shifted 🟢→🟡 after effort adjust
MED-1.0      iter_3 (2026-05-05)  2026-05-06   tier shifted 🟡→🟠 after CF re-research
...

NEXT STEP for each:
  /roi-deep-review {CODE}
  (or batch: trigger roi-deep-review for all stale features in sequence)

ROLLBACK ALTERNATIVE (if recent adjust was a mistake):
  cp Per-Feature\ ROI/_inputs/{CODE}_inputs.v{N-1}.json Per-Feature\ ROI/_inputs/{CODE}_inputs.json
  → re-run roi-build steps 4-7 to rebuild
═══════════════════════════════════════════════════════
```

If no stale files: `✓ No stale reviews — all reviewer audits current.`

To detect "stale since" date, use file mtime of the `.stale` file.

Direct, no preamble.
