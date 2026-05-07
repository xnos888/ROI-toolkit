#!/usr/bin/env python3
"""
Sub-feature Decomposition.

Splits bundled features (e.g., "Appointment 2.0" with 3 sub-features) into
distinct mechanisms. Each mechanism has its own outcome + driver tree, preventing
double-counting in ROI.

Use case (from Kim's Top 15 ROI Plan):
  Feature: APT-2.0 Appointment 2.0
  Sub-features:
    - Self-service slot booking 24/7  → Lost demand capture
    - Reschedule/Cancel ออนไลน์         → Slot recovery
    - LINE OA 2-way confirm           → No-show reduction
  Primary Outcome stated: "O1 - No-show Reduction"

Problem: Bundling all 3 under ONE outcome → double-counting risk.

Solution: Decompose into N distinct mechanisms, validate outcome alignment,
flag misalignment for user review.

Usage:
    python decompose_subfeatures.py <inputs.json> [output.json]
"""

import json
import sys
from pathlib import Path
from datetime import datetime


# ============== MECHANISM TAXONOMY ==============

# Mechanism categories — each has distinct driver chain
MECHANISMS = {
    'no_show_reduction': {
        'description': 'Reduce no-show rate of existing bookings',
        'addresses_outcome': 'no-show reduction',
        'keywords_in_subfeature': [
            'reminder', 'confirm', 'แจ้งเตือน', 'ยืนยัน', 'sms', 'line oa',
            '2-way', 'two-way', 'notification',
        ],
        'driver_chain': 'Booked appointments × confirmation rate × show-up uplift × revenue/visit',
    },
    'lost_demand_capture': {
        'description': 'Capture demand that would not have booked otherwise (after-hours, friction)',
        'addresses_outcome': 'incremental bookings',
        'keywords_in_subfeature': [
            'self-service', 'online booking', '24/7', 'after-hours',
            'จองเอง', 'จองออนไลน์', 'self-booking',
        ],
        'driver_chain': 'Lost demand pool × capture rate × conversion × revenue/visit',
    },
    'slot_recovery': {
        'description': 'Recover empty slots from cancellations to fill with waiting list',
        'addresses_outcome': 'slot utilization',
        'keywords_in_subfeature': [
            'reschedule', 'cancel', 'ยกเลิก', 'เลื่อนนัด', 'waitlist',
        ],
        'driver_chain': 'Cancellations × recovery rate × waitlist conversion × revenue/visit',
    },
    'ops_cost_reduction': {
        'description': 'Reduce manual ops cost (call center, admin, paperwork)',
        'addresses_outcome': 'ops cost saving',
        'keywords_in_subfeature': [
            'call center', 'manual', 'paperwork', 'admin', 'reduce calls',
            'ลดงาน', 'อัตโนมัติ', 'automate',
        ],
        'driver_chain': 'Volume × time saved × cost/min',
    },
    'patient_experience': {
        'description': 'Improve patient experience (wait time, transparency, satisfaction)',
        'addresses_outcome': 'NPS / retention',
        'keywords_in_subfeature': [
            'wait time', 'transparency', 'visibility', 'experience',
            'รอ', 'ความพึงพอใจ', 'satisfaction',
        ],
        'driver_chain': 'Volume × experience uplift × retention × CLV',
    },
    'medication_adherence': {
        'description': 'Improve medication adherence / refill behavior',
        'addresses_outcome': 'refill conversion / continuity',
        'keywords_in_subfeature': [
            'refill', 'medication', 'reminder', 'adherence',
            'ยา', 'เตือนยา', 'NCD',
        ],
        'driver_chain': 'NCD patients × refill conversion × visits/yr × revenue',
    },
    'cost_avoidance_system': {
        'description': 'System-level cost avoidance (ER/IPD prevented) — NOT hospital revenue',
        'addresses_outcome': 'system cost avoidance',
        'keywords_in_subfeature': [
            'er prevention', 'admission avoidance', 'readmission',
            'ป้องกันการ admit', 'ลด ER',
        ],
        'driver_chain': 'At-risk patients × avoidance rate × event cost (NOT hospital revenue)',
    },
}


def classify_subfeature(subfeature_text: str) -> list:
    """
    Classify a sub-feature description into mechanism(s).

    A sub-feature may map to multiple mechanisms — flag this as concern.
    """
    text_lower = subfeature_text.lower()
    matches = []

    for mech_id, mech_def in MECHANISMS.items():
        for keyword in mech_def['keywords_in_subfeature']:
            if keyword.lower() in text_lower:
                matches.append(mech_id)
                break

    return list(set(matches))  # dedupe


def decompose(inputs: dict) -> dict:
    """
    Analyze sub-features and produce decomposition report.
    """
    feature = inputs['feature']
    feature_code = feature.get('code', '?')
    feature_name = feature.get('name', '')
    primary_outcome = inputs.get('primary_outcome', '')
    subfeatures = feature.get('sub_features', [])

    # Try alternate field names from Kim's roadmap CSV
    if not subfeatures:
        scope = feature.get('scope', '')
        # Heuristic: split scope by bullet markers, semicolons, or "+"
        if scope:
            for sep in ['\n', ';', '•', ',', '+']:
                if sep in scope:
                    subfeatures = [s.strip() for s in scope.split(sep) if s.strip()]
                    break
            if not subfeatures:
                subfeatures = [scope]

    if not subfeatures:
        return {
            'feature_code': feature_code,
            'status': 'no_subfeatures_found',
            'message': 'No sub-features detected. Treating as single-mechanism feature.',
            'mechanisms': [],
            'concerns': [],
        }

    # Classify each sub-feature
    classifications = []
    all_mechanisms_seen = set()
    for sf in subfeatures:
        mechs = classify_subfeature(sf)
        classifications.append({
            'subfeature': sf,
            'mechanisms': mechs,
            'mechanism_count': len(mechs),
        })
        all_mechanisms_seen.update(mechs)

    # Identify concerns
    concerns = []

    # Concern 1: Multiple distinct mechanisms bundled
    if len(all_mechanisms_seen) > 1:
        concerns.append({
            'type': 'multiple_mechanisms_bundled',
            'severity': 'high',
            'message': (
                f"Found {len(all_mechanisms_seen)} distinct mechanisms in one feature: "
                f"{', '.join(all_mechanisms_seen)}. "
                "Recommend split into separate features OR explicit multi-outcome model "
                "to prevent double-counting."
            ),
            'mechanisms': list(all_mechanisms_seen),
        })

    # Concern 2: Sub-feature with no mechanism match (unclassified)
    unclassified = [c for c in classifications if c['mechanism_count'] == 0]
    if unclassified:
        concerns.append({
            'type': 'unclassified_subfeatures',
            'severity': 'medium',
            'message': (
                f"{len(unclassified)} sub-feature(s) not matched to known mechanism. "
                "Manually classify or expand mechanism taxonomy."
            ),
            'subfeatures': [c['subfeature'] for c in unclassified],
        })

    # Concern 3: Primary outcome ≠ stated mechanism
    primary_outcome_lower = primary_outcome.lower()
    stated_outcome_keywords = {
        'no-show': 'no_show_reduction',
        'no show': 'no_show_reduction',
        'demand': 'lost_demand_capture',
        'lost': 'lost_demand_capture',
        'capture': 'lost_demand_capture',
        'utilization': 'slot_recovery',
        'recovery': 'slot_recovery',
        'cost': 'ops_cost_reduction',
        'experience': 'patient_experience',
        'wait': 'patient_experience',
        'refill': 'medication_adherence',
        'adherence': 'medication_adherence',
        'avoidance': 'cost_avoidance_system',
    }

    inferred_outcome_mech = None
    for kw, mech in stated_outcome_keywords.items():
        if kw in primary_outcome_lower:
            inferred_outcome_mech = mech
            break

    if inferred_outcome_mech and inferred_outcome_mech not in all_mechanisms_seen and all_mechanisms_seen:
        concerns.append({
            'type': 'outcome_mechanism_mismatch',
            'severity': 'high',
            'message': (
                f"Primary outcome ('{primary_outcome}') maps to '{inferred_outcome_mech}' "
                f"but sub-features address: {', '.join(all_mechanisms_seen)}. "
                "Outcome may not capture the actual value drivers."
            ),
            'stated_outcome': primary_outcome,
            'inferred_mechanism_from_outcome': inferred_outcome_mech,
            'subfeature_mechanisms': list(all_mechanisms_seen),
        })

    # Concern 4: Cost-avoidance bundled with revenue mechanisms (RF-04 preview)
    if 'cost_avoidance_system' in all_mechanisms_seen and len(all_mechanisms_seen) > 1:
        concerns.append({
            'type': 'cost_avoidance_with_revenue',
            'severity': 'high',
            'message': (
                "System cost avoidance bundled with revenue-generating mechanisms. "
                "Cost avoidance is NOT hospital revenue — must be separated in ROI sheet."
            ),
        })

    return {
        'feature_code': feature_code,
        'feature_name': feature_name,
        'status': 'decomposed',
        'subfeature_count': len(subfeatures),
        'unique_mechanisms': list(all_mechanisms_seen),
        'classifications': classifications,
        'concerns': concerns,
        'recommendation': _recommend(concerns, all_mechanisms_seen),
    }


def _recommend(concerns: list, mechanisms: set) -> str:
    """Generate user-facing recommendation."""
    if not concerns:
        return "Sub-features cleanly map to single mechanism. Proceed with normal ROI build."

    high_severity = [c for c in concerns if c.get('severity') == 'high']
    if high_severity:
        if any(c['type'] == 'multiple_mechanisms_bundled' for c in high_severity):
            return (
                "RECOMMENDED: Split feature into separate ROI builds, one per mechanism. "
                "OR explicitly model multi-outcome with distinct value components per mechanism."
            )
        if any(c['type'] == 'cost_avoidance_with_revenue' for c in high_severity):
            return (
                "RECOMMENDED: Build single ROI with explicit Hospital ROI vs System ROI separation. "
                "Cost avoidance must be in its own value component, not summed with revenue."
            )
        if any(c['type'] == 'outcome_mechanism_mismatch' for c in high_severity):
            return (
                "RECOMMENDED: Reconfirm primary outcome with user. Stated outcome may not "
                "align with what sub-features actually deliver."
            )

    return "Proceed with caution. Address concerns above in Stage 1 review."


def render_report_md(decomposition: dict) -> str:
    """Render decomposition as markdown for inline review."""
    lines = []
    code = decomposition.get('feature_code', '?')
    lines.append(f"# Sub-feature Decomposition — {code}")
    lines.append("")
    lines.append(f"**Feature:** {decomposition.get('feature_name', '')}")
    lines.append(f"**Status:** {decomposition['status']}")

    if decomposition['status'] == 'no_subfeatures_found':
        lines.append(f"_{decomposition.get('message', '')}_")
        return "\n".join(lines)

    lines.append(f"**Sub-features detected:** {decomposition['subfeature_count']}")
    lines.append(f"**Unique mechanisms:** {len(decomposition['unique_mechanisms'])}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Classifications
    lines.append("## Sub-feature → Mechanism Mapping")
    lines.append("")
    lines.append("| # | Sub-feature | Mechanism(s) |")
    lines.append("|---|-------------|--------------|")
    for i, c in enumerate(decomposition['classifications'], 1):
        sf = c['subfeature'][:60]
        mechs = ', '.join(c['mechanisms']) if c['mechanisms'] else '⚠️ unclassified'
        lines.append(f"| {i} | {sf} | {mechs} |")
    lines.append("")

    # Concerns
    if decomposition['concerns']:
        lines.append("---")
        lines.append("")
        lines.append("## ⚠️ Concerns")
        lines.append("")
        for c in decomposition['concerns']:
            severity_icon = '🔴' if c.get('severity') == 'high' else '🟡'
            lines.append(f"### {severity_icon} {c['type']}")
            lines.append(c['message'])
            lines.append("")
    else:
        lines.append("✅ No concerns identified.")
        lines.append("")

    # Recommendation
    lines.append("---")
    lines.append("")
    lines.append("## Recommendation")
    lines.append("")
    lines.append(decomposition['recommendation'])

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python decompose_subfeatures.py <inputs.json> [output.json] [output.md]")
        sys.exit(1)

    inputs_path = Path(sys.argv[1])
    output_json = sys.argv[2] if len(sys.argv) >= 3 else None
    output_md = sys.argv[3] if len(sys.argv) >= 4 else None

    with open(inputs_path) as f:
        inputs = json.load(f)

    result = decompose(inputs)

    if output_json:
        Path(output_json).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    if output_md:
        Path(output_md).write_text(render_report_md(result), encoding='utf-8')

    if not output_json and not output_md:
        print(render_report_md(result))
    else:
        print(json.dumps({
            "status": "success",
            "feature_code": result['feature_code'],
            "subfeatures": result.get('subfeature_count', 0),
            "mechanisms": len(result.get('unique_mechanisms', [])),
            "concerns": len(result.get('concerns', [])),
        }))


if __name__ == '__main__':
    main()
