#!/usr/bin/env python3
"""
Stage 1 Assumption Preview Generator.

Reads the same inputs.json that build_roi_workbook.py consumes,
produces a markdown preview for inline approval BEFORE building xlsx.

Usage:
    python preview_assumptions.py <inputs.json> [output.md]

If output.md not specified, prints to stdout.
"""

import json
import sys
from pathlib import Path


def fmt_pct(v):
    if isinstance(v, (int, float)):
        return f"{v*100:.0f}%"
    return str(v)


def fmt_int(v):
    if isinstance(v, (int, float)):
        return f"{v:,.0f}"
    return str(v)


def fmt_thb(v):
    if isinstance(v, (int, float)):
        return f"{v:,.0f} THB"
    return str(v)


def render_preview(inputs):
    f = inputs['feature']
    code = f['code']
    name = f['name']
    category = f.get('category', 'Unspecified')
    problem = f.get('problem', '')
    scope = f.get('scope', '')

    lines = []
    lines.append(f"# 📋 Stage 1/3: Assumption Preview — {code} {name}")
    lines.append("")
    lines.append(f"**Category:** {category}")
    if scope:
        lines.append(f"**Scope:** {scope}")
    lines.append(f"**Problem:** {problem}")
    lines.append("")

    # Hypothesis + Outcome
    if inputs.get('hypothesis'):
        lines.append(f"**Hypothesis:** {inputs['hypothesis']}")
    if inputs.get('primary_outcome'):
        lines.append(f"**Primary outcome:** {inputs['primary_outcome']}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # === TAM-SAM-SOM ===
    lines.append("## 📊 TAM-SAM-SOM (3 Scenarios)")
    lines.append("")
    tss = inputs['tam_sam_som']
    tam = tss['tam']
    lines.append(f"**TAM** — {tam['label']}")

    def show_value(v):
        """Render YAML value, including =ref: pointer."""
        if isinstance(v, str) and v.startswith('='):
            return v
        return fmt_int(v)

    lines.append(f"  - Worst: {show_value(tam['worst'])} | Base: {show_value(tam['base'])} | Best: {show_value(tam['best'])} ({tam.get('unit', 'VN/yr')})")
    if tam.get('source'):
        lines.append(f"  - *Source:* {tam['source']}")
    lines.append("")

    if tss.get('sam_filters'):
        lines.append("**SAM Filters:**")
        for filt in tss['sam_filters']:
            lines.append(f"  - {filt['label']}: W {fmt_pct(filt['worst'])} / B {fmt_pct(filt['base'])} / Best {fmt_pct(filt['best'])}")
            if filt.get('source'):
                lines.append(f"    *{filt['source']}*")
        lines.append("")

    lines.append("**SOM Adoption Ramp:**")
    for year in ['Y1', 'Y2', 'Y3']:
        som = tss[f'som_{year.lower()}']
        lines.append(f"  - {year}: W {fmt_pct(som['worst'])} / B {fmt_pct(som['base'])} / Best {fmt_pct(som['best'])}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # === Conversion Factors ===
    lines.append("## 🔧 Conversion Factors")
    lines.append("")
    lines.append("| ID | Driver | Worst | Base | Best | Tier | Source |")
    lines.append("|----|--------|-------|------|------|------|--------|")
    for cf in inputs['conversion_factors']:
        fmt_func = fmt_pct if cf.get('format') == 'pct' else (fmt_thb if cf.get('format') == 'currency' else show_value)
        w = fmt_func(cf['worst']) if not (isinstance(cf['worst'], str) and cf['worst'].startswith('=')) else cf['worst']
        b = fmt_func(cf['base']) if not (isinstance(cf['base'], str) and cf['base'].startswith('=')) else cf['base']
        bst = fmt_func(cf['best']) if not (isinstance(cf['best'], str) and cf['best'].startswith('=')) else cf['best']
        primary = '⭐ ' if cf.get('primary') else ''
        lines.append(f"| {cf['id']} | {primary}{cf['label']} | {w} | {b} | {bst} | {cf.get('tier', 'T3')} | {cf.get('source', '')[:60]} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # === Confidence Tier (metadata) + Strategic Fit (Priority Score input) ===
    lines.append("## 🎯 Confidence Tier & Priority Score Input")
    lines.append("")
    conf = inputs['confidence']
    sf = inputs['strategic_fit']
    lines.append(f"- **Confidence Tier:** {conf.get('tier', 'T3')} (metadata only — not multiplied into value)")
    if conf.get('reason'):
        lines.append(f"  - *{conf['reason']}*")
    lines.append(f"- **Strategic Fit:** {sf['multiplier']}x (Priority Score input — never multiplied into Pure ROI)")
    if sf.get('reason'):
        lines.append(f"  - *{sf['reason']}*")
    lines.append("")
    lines.append("---")
    lines.append("")

    # === Effort ===
    lines.append("## ⚙️ Build Effort (MD)")
    lines.append("")
    lines.append("| Role | Worst | Base | Best |")
    lines.append("|------|-------|------|------|")
    total_w = total_b = total_best = 0
    for item in inputs['effort']['breakdown']:
        lines.append(f"| {item['role']} | {item['worst']} | {item['base']} | {item['best']} |")
        total_w += item['worst']
        total_b += item['base']
        total_best += item['best']
    lines.append(f"| **TOTAL** | **{total_w}** | **{total_b}** | **{total_best}** |")
    lines.append("")
    md_cost = inputs['effort'].get('md_cost', 24000)
    lines.append(f"**Build Cost (MD × {md_cost:,} THB):** W {total_w * md_cost:,} / B {total_b * md_cost:,} / Best {total_best * md_cost:,}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # === Cagan 4 Risks ===
    if inputs.get('cagan_risks'):
        lines.append("## 🔬 Cagan's 4 Risks (Discovery Status)")
        lines.append("")
        for risk_name, status in inputs['cagan_risks'].items():
            lines.append(f"- **{risk_name}:** {status}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # === Top 3 Assumptions to Verify ===
    lines.append("## 🚩 Top 3 Assumptions to Verify")
    lines.append("")
    flagged = inputs.get('flagged_assumptions', [])[:3]
    if flagged:
        for i, a in enumerate(flagged, 1):
            lines.append(f"{i}. **{a['assumption']}** ({a.get('tier', 'T?')}) — {a.get('verification', '')}")
    else:
        lines.append("*No flagged assumptions defined — recommend adding before commit.*")
    lines.append("")
    lines.append("---")
    lines.append("")

    # === Approval prompt ===
    lines.append("## ✅ Action Required")
    lines.append("")
    lines.append("Choose:")
    lines.append("- **Approve** → proceed to build xlsx")
    lines.append("- **Adjust [field]** → modify specific section, re-preview")
    lines.append("- **Reject** → restart input collection")
    lines.append("")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python preview_assumptions.py <inputs.json> [output.md]")
        sys.exit(1)

    inputs_path = Path(sys.argv[1])
    if not inputs_path.exists():
        print(f"Error: {inputs_path} not found")
        sys.exit(1)

    with open(inputs_path) as f:
        inputs = json.load(f)

    preview = render_preview(inputs)

    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
        output_path.write_text(preview, encoding='utf-8')
        print(json.dumps({
            "status": "success",
            "output": str(output_path),
            "feature_code": inputs['feature']['code'],
        }))
    else:
        print(preview)


if __name__ == '__main__':
    main()
