#!/usr/bin/env python3
"""
Conversion Factor Research Engine.

Web search 2-3 sources per CF, classify source quality (T1-T4),
extract numeric ranges, apply TH discount, output enriched CF.

Strategy (per Kim's design decisions):
- Q1=B: Research ALL CFs (not just primary)
- Q2=C: Try-then-degrade — search 2 attempts, fallback to library, force T4
- Q3=B: Cache per session — same mechanism queried once across batch

Usage (called from skill workflow, NOT standalone CLI):
    from research_cf import research_cf, CFResearchSession

    session = CFResearchSession()
    enriched_cf = session.research(cf_dict)
    session.save_audit_trail("research_validation.md")

NOTE: This script does NOT call web_search directly. It produces a
research PLAN (list of queries to run) that the orchestrating Claude
runs via the web_search tool, then feeds results back via .ingest_results().

This separation exists because:
1. web_search is a Claude tool, not a Python library
2. Skill orchestration happens at Claude turn level, not script level
3. Cache and tier classification logic stays in Python (testable)
"""

import json
import re
import sys
import hashlib
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional


# ============== TIER CLASSIFICATION ==============

# Source quality keywords (signal whether a search result is T1-T4)
TIER_T2_SIGNALS = [
    'pubmed', 'doi.org', 'nih.gov', 'who.int', 'cdc.gov',
    'thelancet', 'bmj.com', 'nejm.org', 'jamanetwork',
    'sciencedirect', 'springer', 'wiley.com',
    'peer-reviewed', 'randomized controlled trial', 'rct',
    'cochrane', 'systematic review', 'meta-analysis',
]

TIER_T3_SIGNALS = [
    'mckinsey.com', 'bain.com', 'deloitte.com', 'accenture.com',
    'gartner.com', 'forrester.com', 'kpmg.com',
    'case study', 'whitepaper', 'industry report',
    'healthcareitnews', 'modernhealthcare', 'fiercehealthcare',
    'beckers', 'kff.org', 'commonwealthfund',
    '.gov', 'ministry of public health', 'thaihealth',
]

TIER_T4_SIGNALS = [
    'press release', 'announces', 'launches',
    '.com/blog', 'medium.com', 'substack',
    'vendor', 'sales', 'marketing material',
]

# Vendor names — if source is from vendor and topic is their product, flag T4
KNOWN_VENDORS = [
    'epic.com', 'cerner.com', 'allscripts',
    'sovdoc', 'expressscripts',
    'salesforce.com', 'hubspot',
]


def classify_source_tier(url: str, snippet: str = "", title: str = "") -> str:
    """
    Classify a search result's tier based on URL + content signals.

    Returns: 'T2', 'T3', or 'T4'
    (T1 = internal data, never from web search)
    """
    combined = f"{url} {title} {snippet}".lower()

    # Vendor self-promotion → T4
    for vendor in KNOWN_VENDORS:
        if vendor in url.lower():
            return 'T4'

    # Peer-reviewed / academic → T2
    for signal in TIER_T2_SIGNALS:
        if signal in combined:
            return 'T2'

    # Industry report / consultancy → T3
    for signal in TIER_T3_SIGNALS:
        if signal in combined:
            return 'T3'

    # Press release / blog → T4
    for signal in TIER_T4_SIGNALS:
        if signal in combined:
            return 'T4'

    # Default: T3 (unclassified industry source)
    return 'T3'


def extract_numeric_range(text: str) -> Optional[tuple]:
    """
    Try to extract a numeric range or single value from search result text.

    Returns: (low, high) or (value, value) or None if no number found.
    Handles: "20-40%", "21.5%", "30 to 50 percent", "1 in 5"
    """
    if not text:
        return None

    # Pattern 1: X-Y% or X-Y percent
    m = re.search(r'(\d+\.?\d*)\s*[-–to]+\s*(\d+\.?\d*)\s*(%|percent)', text)
    if m:
        return (float(m.group(1)) / 100, float(m.group(2)) / 100)

    # Pattern 2: X% (single)
    m = re.search(r'(\d+\.?\d*)\s*(%|percent)', text)
    if m:
        v = float(m.group(1)) / 100
        return (v, v)

    # Pattern 3: X-Y (raw numbers, e.g., "21M fewer")
    m = re.search(r'(\d{1,3}(?:,\d{3})*\.?\d*)\s*[-–to]+\s*(\d{1,3}(?:,\d{3})*\.?\d*)', text)
    if m:
        try:
            return (float(m.group(1).replace(',', '')), float(m.group(2).replace(',', '')))
        except ValueError:
            pass

    return None


# ============== TH DISCOUNT METHODOLOGY ==============

TH_DISCOUNTS = {
    'geographic_us_to_th': 0.70,      # 30% reduction for healthcare maturity gap
    'patient_digital_literacy': 0.80,  # 20% reduction for adoption speed
    'implementation_risk': 0.85,       # 15% reduction first deployment
    'integration_complexity': 0.90,    # 10% reduction for HIS legacy
}


def apply_th_discount(value: float, source_geography: str = "us") -> dict:
    """
    Apply Thai healthcare discount to US/Western benchmarks.

    Returns dict with worst/base/best after discount.
    Cumulative: ~50% Base, 30% Worst, 70% Best of original.
    """
    if source_geography.lower() in ('th', 'thailand', 'thai'):
        # Already TH source — no geographic discount
        return {
            'worst': value * 0.70,
            'base': value * 1.0,
            'best': value * 1.20,
        }

    # US/Western source — apply full discount
    base_discount = (
        TH_DISCOUNTS['geographic_us_to_th']
        * TH_DISCOUNTS['patient_digital_literacy']
        * TH_DISCOUNTS['implementation_risk']
        * TH_DISCOUNTS['integration_complexity']
    )  # ~0.43

    return {
        'worst': value * base_discount * 0.6,  # ~26% of original
        'base': value * base_discount,          # ~43% of original
        'best': value * base_discount * 1.5,    # ~64% of original
    }


# ============== RESEARCH SESSION (with cache) ==============

@dataclass
class CFQuery:
    """A single CF research query plan."""
    cf_id: str
    cf_label: str
    mechanism: str       # short description for search query
    feature_code: str
    queries: list = field(default_factory=list)  # 2 search queries
    cache_key: str = ""

    def __post_init__(self):
        # Cache key based on mechanism (CF reused across features)
        normalized = re.sub(r'[^\w\s]', '', self.mechanism.lower()).strip()
        self.cache_key = hashlib.md5(normalized.encode()).hexdigest()[:12]


@dataclass
class CFResearchResult:
    """Result of researching a single CF."""
    cf_id: str
    cf_label: str
    mechanism: str
    sources: list = field(default_factory=list)  # list of dicts: url, title, snippet, tier
    extracted_ranges: list = field(default_factory=list)  # list of (low, high)
    final_tier: str = 'T4'
    final_worst: float = 0.0
    final_base: float = 0.0
    final_best: float = 0.0
    discount_applied: bool = False
    fallback_used: bool = False
    fallback_reason: str = ""
    notes: str = ""


class CFResearchSession:
    """
    Manages a research session across one or more features.

    Cache lifetime = session lifetime (Q3=B decision).
    Cache invalidates when session ends.
    """

    def __init__(self, library_path: Optional[str] = None):
        self.cache: dict = {}  # cache_key → CFResearchResult
        self.queries_planned: list = []  # for orchestrator to execute
        self.library_path = library_path
        self.library: dict = self._load_library() if library_path else {}
        self.audit_trail: list = []

    def _load_library(self) -> dict:
        """Load static CF library for fallback."""
        if not self.library_path or not Path(self.library_path).exists():
            return {}
        # Parse library markdown — extract CF IDs and ranges
        # (Simplified: in production would parse the markdown table format)
        return {}

    def plan_queries(self, cf: dict, feature_code: str) -> Optional[CFQuery]:
        """
        Build a query plan for one CF.

        Returns CFQuery if research needed, None if cache hit.
        """
        mechanism = cf.get('mechanism_short', cf['label'])

        query = CFQuery(
            cf_id=cf['id'],
            cf_label=cf['label'],
            mechanism=mechanism,
            feature_code=feature_code,
        )

        # Check cache
        if query.cache_key in self.cache:
            cached = self.cache[query.cache_key]
            self.audit_trail.append({
                'cf_id': cf['id'],
                'feature_code': feature_code,
                'cache_hit': True,
                'cache_source_cf': cached.cf_id,
                'reused_tier': cached.final_tier,
            })
            return None

        # Build 2 search queries (Q2=C: try-then-degrade, max 2 attempts)
        # Query 1: specific mechanism + healthcare context
        q1 = f"{mechanism} healthcare benchmark study"
        # Query 2: broader, with Thailand context
        q2 = f"{mechanism} hospital adoption rate"

        query.queries = [q1, q2]
        self.queries_planned.append(query)
        return query

    def ingest_results(
        self,
        cache_key: str,
        cf_id: str,
        cf_label: str,
        mechanism: str,
        search_results: list,
    ) -> CFResearchResult:
        """
        Process search results from orchestrator.

        search_results format:
            [{'url': str, 'title': str, 'snippet': str, 'query': str}, ...]
        """
        result = CFResearchResult(
            cf_id=cf_id,
            cf_label=cf_label,
            mechanism=mechanism,
        )

        # Classify each source
        for r in search_results:
            tier = classify_source_tier(
                r.get('url', ''),
                r.get('snippet', ''),
                r.get('title', ''),
            )
            range_data = extract_numeric_range(
                f"{r.get('title','')} {r.get('snippet','')}"
            )
            result.sources.append({
                'url': r.get('url', ''),
                'title': r.get('title', ''),
                'snippet': r.get('snippet', '')[:200],
                'query': r.get('query', ''),
                'tier': tier,
                'extracted_range': range_data,
            })
            if range_data:
                result.extracted_ranges.append(range_data)

        # Determine final tier (best tier among sources)
        tiers_found = [s['tier'] for s in result.sources]
        if 'T2' in tiers_found:
            result.final_tier = 'T2'
        elif 'T3' in tiers_found:
            result.final_tier = 'T3'
        else:
            result.final_tier = 'T4'

        # Aggregate ranges
        if result.extracted_ranges:
            all_lows = [r[0] for r in result.extracted_ranges]
            all_highs = [r[1] for r in result.extracted_ranges]
            avg_low = sum(all_lows) / len(all_lows)
            avg_high = sum(all_highs) / len(all_highs)
            avg_mid = (avg_low + avg_high) / 2

            # Apply TH discount (assume US sources unless clearly TH)
            is_th = any('thai' in s.get('url', '').lower() or 'thai' in s.get('title', '').lower()
                       for s in result.sources)
            geography = 'th' if is_th else 'us'

            discounted = apply_th_discount(avg_mid, geography)
            result.final_worst = max(avg_low * 0.6, discounted['worst'])
            result.final_base = discounted['base']
            result.final_best = min(avg_high * 1.2, discounted['best'])
            result.discount_applied = not is_th
        else:
            # No numeric ranges extracted → fallback needed
            result.fallback_used = True
            result.fallback_reason = "No numeric ranges extracted from search results"

        # Cache
        self.cache[cache_key] = result
        self.audit_trail.append({
            'cf_id': cf_id,
            'cache_hit': False,
            'sources_found': len(result.sources),
            'tier': result.final_tier,
            'fallback': result.fallback_used,
        })
        return result

    def fallback_to_library(self, cf: dict) -> CFResearchResult:
        """
        Q2=C strategy: when search fails, fall back to library + force T4.
        """
        result = CFResearchResult(
            cf_id=cf['id'],
            cf_label=cf['label'],
            mechanism=cf.get('mechanism_short', cf['label']),
            final_tier='T4',  # Force T4 — search didn't yield results
            final_worst=cf.get('worst_default', 0),
            final_base=cf.get('base_default', 0),
            final_best=cf.get('best_default', 0),
            fallback_used=True,
            fallback_reason="Search returned 0 sources or 0 numeric ranges. Using library defaults with forced T4 tier.",
        )
        self.audit_trail.append({
            'cf_id': cf['id'],
            'fallback': True,
            'forced_tier': 'T4',
        })
        return result

    def save_audit_trail(self, output_path: str) -> None:
        """Save research_validation.md with full audit trail."""
        lines = []
        lines.append("# Research Validation — Audit Trail")
        lines.append("")
        lines.append(f"**Generated:** {datetime.utcnow().isoformat()}Z")
        lines.append(f"**Total CFs researched:** {len(self.audit_trail)}")
        lines.append(f"**Cache hits (token savings):** {sum(1 for a in self.audit_trail if a.get('cache_hit'))}")
        lines.append(f"**Fallbacks (search failed):** {sum(1 for a in self.audit_trail if a.get('fallback'))}")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Per-CF Research Summary")
        lines.append("")

        for entry in self.audit_trail:
            cf_id = entry.get('cf_id', '?')
            lines.append(f"### {cf_id}")
            if entry.get('cache_hit'):
                lines.append(f"- **Cache hit** — reused result from {entry.get('cache_source_cf', 'earlier CF')}")
                lines.append(f"- Tier (cached): {entry.get('reused_tier', '?')}")
            elif entry.get('fallback'):
                lines.append(f"- **Fallback used** — search returned no usable results")
                lines.append(f"- Forced tier: T4")
            else:
                lines.append(f"- Sources found: {entry.get('sources_found', 0)}")
                lines.append(f"- Tier classified: {entry.get('tier', '?')}")
            lines.append("")

        # Sources detail
        lines.append("---")
        lines.append("")
        lines.append("## Source Citations")
        lines.append("")
        for cache_key, result in self.cache.items():
            lines.append(f"### {result.cf_id} — {result.cf_label}")
            lines.append(f"**Tier:** {result.final_tier}")
            lines.append(f"**Final values:** Worst {result.final_worst:.4f} / Base {result.final_base:.4f} / Best {result.final_best:.4f}")
            if result.fallback_used:
                lines.append(f"⚠️ **Fallback:** {result.fallback_reason}")
            lines.append("")
            for s in result.sources:
                lines.append(f"- [{s['tier']}] {s.get('title', 'untitled')}")
                lines.append(f"  - URL: {s.get('url', 'n/a')}")
                if s.get('extracted_range'):
                    low, high = s['extracted_range']
                    lines.append(f"  - Extracted range: {low:.2%} – {high:.2%}")
            lines.append("")

        Path(output_path).write_text("\n".join(lines), encoding='utf-8')


# ============== STANDALONE CLI (for testing) ==============

def main():
    """Test the research engine with a mock CF."""
    if len(sys.argv) < 2:
        print("Usage: python research_cf.py <inputs.json> [output_validation.md]")
        print("")
        print("This produces a query plan; actual web_search is run by orchestrator.")
        sys.exit(1)

    inputs_path = Path(sys.argv[1])
    output_path = sys.argv[2] if len(sys.argv) >= 3 else None

    with open(inputs_path) as f:
        inputs = json.load(f)

    session = CFResearchSession()

    print(json.dumps({
        "status": "plan_generated",
        "feature_code": inputs['feature']['code'],
        "queries_to_run": [
            {
                "cf_id": cf['id'],
                "cf_label": cf['label'],
                "queries": [
                    f"{cf.get('mechanism_short', cf['label'])} healthcare benchmark study",
                    f"{cf.get('mechanism_short', cf['label'])} hospital adoption rate",
                ],
            }
            for cf in inputs.get('conversion_factors', [])
        ],
    }, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
