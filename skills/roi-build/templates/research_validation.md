# Research Validation — Audit Trail

> **Generated:** {timestamp}
> **Feature:** {feature_code} {feature_name}
> **Session:** {session_id}

## Summary

| Metric | Value |
|--------|-------|
| Total CFs researched | {total_cfs} |
| Cache hits (token savings) | {cache_hits} |
| Fresh searches executed | {fresh_searches} |
| Fallbacks (search yielded no usable result) | {fallbacks} |
| Sources found (avg per CF) | {avg_sources_per_cf} |
| Tier T2 sources | {t2_count} |
| Tier T3 sources | {t3_count} |
| Tier T4 sources | {t4_count} |

---

## Sub-feature Decomposition (Stage 2.5a)

{decomposition_summary}

**Concerns flagged:** {concerns_count}

{decomposition_concerns_list}

---

## Per-CF Research Detail

{per_cf_blocks}

<!-- Each per_cf_block follows this template:

### {cf_id} — {cf_label}

**Mechanism:** {mechanism}
**Final tier:** {final_tier}
**Final values:** Worst {final_worst} / Base {final_base} / Best {final_best}
**Discount applied:** {discount_applied}

#### Sources

| # | Tier | Title | URL | Extracted Range |
|---|------|-------|-----|------------------|
| 1 | {tier} | {title} | {url} | {range} |
| 2 | ... | ... | ... | ... |

{fallback_notice_if_used}

-->

---

## Verification of User-Provided "Industry Evidence"

If user provided "Industry Evidence" claims, this section verifies each:

{industry_evidence_verification}

<!-- Each verification block:

### Claim: "{user_claim}"

**Source verified:** {url_or_not_found}
**Original publication date:** {date}
**Sample size / population:** {scope}
**Methodology:** {method}
**Caveats:** {caveats}
**Adjusted value (TH context):** {adjusted}

-->

---

## Cache Statistics

CFs sharing mechanism (cached, not re-searched):

{cache_groups}

<!-- Example:

- Mechanism "no-show reduction reminder" used by:
  - APT-2.0 D1
  - APT-3.0 D1
  - APT-4.0 D1
  → Researched once, reused 3×

-->

---

## Research Limitations

This audit reflects searches at time of generation. Limitations:

1. **Web search snapshot** — results may differ on subsequent runs
2. **Snippet-based extraction** — full study reading not performed
3. **Tier classification heuristics** — URL/keyword patterns, not domain expertise
4. **TH discount methodology** — applied uniformly, not per-CF calibrated
5. **Cache lifetime = session** — does not persist across sessions

For C-Level presentation: cite this audit alongside ROI sheet. Reproduce by re-running skill with same inputs (results may vary 5-15% due to search variance).

---

## Reproducibility Snapshot

```yaml
session_id: {session_id}
inputs_hash: {inputs_hash}
research_timestamp: {timestamp}
cf_count: {total_cfs}
fallback_count: {fallbacks}
search_engine: web_search (Claude tool)
discount_methodology: TH_DISCOUNTS_v1
```

To reproduce this audit, run skill with identical `inputs.json`. Variance in search results is expected (5-15%) due to web index changes and snippet variation.
