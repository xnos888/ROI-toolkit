# Escalation — {FEATURE_CODE} ({REASON})

**Generated:** {DATE}
**Workbook:** {WORKBOOK_PATH}
**Reason:** {REASON}  <!-- max_iters_reached | no_autofix_possible | rebuild_required | persistent_split -->
**Iterations consumed:** {N}/3

---

## Final state

| Metric | Worst | **Base** | Best |
|---|---|---|---|
| Y1 ROI | {y1_worst}x | **{y1_base}x** | {y1_best}x |
| 3-Yr ROI | {y3_worst}x | **{y3_base}x** | {y3_best}x |
| Build effort (MD) | {md_worst} | {md_base} | {md_best} |

**ROI movement across iters:**
{ROI_MOVEMENT_TABLE}

---

## Cumulative diff (inputs.v1 → inputs.v{N})

```diff
{UNIFIED_DIFF}
```

**Fixes applied successfully:** {n_applied}
**Fixes denied (forbidden field / not in whitelist):** {n_denied}

---

## Unresolved blocking issues

| ID | Reviewer | Severity | Category | Description | Why not auto-fixable |
|---|---|---|---|---|---|
{UNRESOLVED_TABLE}

---

## Three options for the user

### 1. 🟢 Override
Accept current ROI as-is and ship with documented unresolved issues. Sign-off required.

**When to choose:** strategic feature where remaining HIGH items are acceptable risk (e.g., discovery debt that can be addressed post-launch via cohort A/B), or business priority overrides methodological gap.

**Action:**
- Document override decision + sign-off in `_inputs/{FEATURE_CODE}_override.md`
- Re-run `generate_summary.py` with `--override` flag → final summary marks as ⚠️ OVERRIDDEN
- Proceed to commit with override visible in committee deck

### 2. 🟠 Defer
Park feature; create discovery tickets for each HIGH item; revisit once unblocked.

**When to choose:** discovery debt is real (e.g., 0 customer interviews on load-bearing CF) and addressing it pre-build will materially change the model.

**Action:**
- Create ticket per HIGH item (linked from this escalation file)
- Mark feature status as `Deferred — discovery sprint required`
- Set re-review trigger (e.g., "after Week 4 cohort study")

### 3. 🔵 Manual fix
User edits inputs.json directly + re-runs from Step 4 (build).

**When to choose:** reviewer's auto_fixable: false was wrong AND the fix is genuinely something the user can resolve via judgment (not new research) — e.g., correcting a strategic_fit rationale, swapping a primary CF for a more defendable one.

**Action:**
```bash
# 1. Edit inputs.json (latest version)
$EDITOR Per-Feature ROI/_inputs/{FEATURE_CODE}_inputs.v{N}.json

# 2. Rebuild
python .claude/skills/business-case-modeling/scripts/build_roi_workbook.py \
    Per-Feature\ ROI/_inputs/{FEATURE_CODE}_inputs.v{N}.json \
    Per-Feature\ ROI/

# 3. Restart loop from iter 1
python .claude/skills/business-case-modeling/scripts/review_loop.py \
    Per-Feature\ ROI/{FEATURE_CODE}_ROI.xlsx \
    Per-Feature\ ROI/_inputs/{FEATURE_CODE}_inputs.v{N}.json \
    --max-iters 3 --restart
```

---

## Iteration history

{ITER_HISTORY_SECTION}

---

## Files

- Workbook: `{WORKBOOK_PATH}`
- Latest inputs: `{INPUTS_PATH}`
- Iteration history: `{HISTORY_JSON_PATH}`
- Reviewer outputs: `review/{FEATURE_CODE}_iter_*_*.md`
