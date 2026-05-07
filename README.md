# ROI-toolkit

> **v2.0** — 4-skill PE Roadmap ROI toolkit. Defendable per-feature business cases that survive CFO/board scrutiny, optimized to ~37% lower token cost vs the single-skill v1.

For Senestia/Synphaet hospital's Patient Engagement (PE) Roadmap workflow.

---

## What's inside

4 specialized skills covering the full per-feature lifecycle:

| Skill | When to use | Cost overhead |
|---|---|---|
| `roi-build` | New feature (no inputs.json yet). Full driver-tree workflow with web research, TAM-SAM-SOM funneling, Cagan 4-risk gates. | ~3-4K tokens + research |
| `roi-adjust` | Modify an existing feature's assumption (effort, TAM, CF, SF, scope) with mandatory cascade across xlsx + summary + master rollup + reviewer staleness. | LIGHT 3K / MEDIUM 5K / HEAVY 10K |
| `roi-deep-review` | CFO + Head of Product sub-agent audit loop (default max 2 iter). Catches cell-level bugs the validator architecturally misses. | ~30-50K per feature |
| `roi-portfolio` | Master rollup refresh + Phase Plan + KILL/DEFER decisions. Auto-chained from build/adjust. | ~3-5K |

## Why this plugin exists

The original `business-case-modeling` skill (v1.0) was a single 545-line skill that loaded ~13K tokens of overhead per trigger — even when most of the loaded context wasn't needed. v2.0 splits by lifecycle, applies progressive disclosure, and drops review-loop cost via shared boilerplate extraction + diff-based re-review on iter 2+.

**Empirical token savings (per 30-feature batch):**
- v1.0 baseline: ~700K-1M tokens
- v2.0 with all optimizations: ~250-400K tokens (**-60-65%**)

**Quality preserved:**
- CFO + HoP personas kept separate (data-driven decision: empirically only 10-25% overlap; merging would lose 7+ HIGH discovery_debt issues per batch)
- Anti-confirmation-bias whitelist preserved (forbidden auto-fix on TAM/CF/SF tuning)
- 71% bug-catch rate maintained (5/7 features in 2026-05-04 batch had cell-level bugs caught by reviewers)

## Install

### Claude Code (local marketplace)

```bash
# 1. Clone or extract this folder somewhere outside your project
# 2. Add as a local marketplace
claude /plugin marketplace add /path/to/ROI-toolkit

# 3. Install
claude /plugin install ROI-toolkit
```

### Claude Code (git marketplace)

```bash
# After publishing to GitHub:
claude /plugin marketplace add https://github.com/xnos888/ROI-toolkit

claude /plugin install ROI-toolkit
```

### Cowork

Same flow as Claude Code — Cowork supports the same plugin format.

## Project setup (required for skills to function)

These skills assume a project layout:

```
your-project/
├── CLAUDE.md                           ← project rules + load-bearing decisions
├── SKILL_ARCHITECTURE.md               ← (optional) workprocess overview
├── Hospital_Baseline_DB.xlsx           ← baseline metrics (VN, no-show rate, avg revenue)
├── PE North Star Metric.xlsx           ← North Star vectors (Acquisition, Queue, HCU, etc.)
├── marty-cagan-roadmap-thinking.md     ← (optional) Cagan reference
└── Per-Feature ROI/
    ├── _inputs/
    │   ├── {CODE}_inputs.json          ← per-feature input data (schema: see roi-build)
    │   ├── {CODE}_inputs.v{N}.json     ← versioned audit trail (created by roi-adjust)
    │   ├── {CODE}_decomposition.json
    │   ├── {CODE}_research_validation.md
    │   ├── _capacity_config.json       ← (optional) override default 600 MD annual capacity
    │   └── _archive/                   ← rotated old versions
    ├── {CODE}_ROI.xlsx                 ← 6-sheet workbook
    ├── {CODE}_summary.md               ← auto-generated narrative
    ├── Feature_ROI_Summary_*.xlsx      ← MASTER ROLLUP (data authority)
    ├── PE_Roadmap_Phase_Plan_*.md      ← current quarterly plan
    ├── Batch{N}_Master_Summary.md      ← per-batch narrative
    └── review/
        ├── {CODE}_iter_{N}_cfo.md      ← reviewer outputs
        ├── {CODE}_iter_{N}_hop.md
        ├── {CODE}_iter_history.json    ← append-only audit
        └── {CODE}_escalation.md        ← (if escalated)
```

## Python dependencies

```bash
pip install openpyxl formulas pyyaml
```

Plus **LibreOffice** (for `recalc.py` formula evaluation):

```bash
# macOS
brew install --cask libreoffice

# Linux
apt-get install libreoffice

# Cowork — verify with: which soffice
```

If LibreOffice is unavailable, `recalc.py` falls back to the `formulas` Python lib (slower but pure-Python).

## Usage (trigger phrases)

The skills auto-trigger on natural language. Examples:

| You type | Skill triggers |
|---|---|
| "ทำ ROI ให้ APT-3.0", "build ROI for medication delivery" | `roi-build` |
| "ปรับ effort APT-2.0 เป็น 25 MD", "เปลี่ยน TAM ของ Queue" | `roi-adjust` |
| "deep review APT-2.0", "ตรวจ ROI ของ MED-DLV-1.0" | `roi-deep-review` |
| "refresh master rollup", "ทำ Phase Plan", "decide KILL/DEFER batch 7" | `roi-portfolio` |

## Slash commands

| Command | What it does |
|---|---|
| `/roi-status` | Portfolio overview — features count, tier distribution, capacity, stale reviewers |
| `/roi-feature-list [filter]` | All features ranked by Priority Score with tier + quarter. Optional filter (`q1`, `🟢`, code prefix) |
| `/roi-capacity-check` | Q1-Q4 capacity vs allocation — flags oversubscription |
| `/roi-kill-defer` | Propose KILL/DEFER candidates per criterion (ROI + SF + capacity) |
| `/roi-stale-review` | List features whose reviewer files are `.stale` — recommend re-review |
| `/roi-validate-all` | Validator sweep on every workbook — sanity check before leadership publish |

## Decision framework

| Tier | Y1 Base ROI | Action |
|---|---|---|
| 🟢 STRONG GO | ≥ 5x | Q1-Q2 commit |
| 🟡 CONDITIONAL | 1.5x – 5x | Q3-Q4, watch validation gates |
| 🟠 DEFER | 1x – 1.5x | Out of annual plan unless strategic |
| 🔴 KILL | < 1x | Archive unless SF ≥ 1.4 |

## Critical project rules (load-bearing)

1. **Pure ROI ≠ Priority Score.** Strategic Fit (×1.0–1.5) feeds Priority Score for roadmap rank only. Headline ROI to leadership = Pure ROI
2. **Hospital ROI vs System ROI must be split** when cost-avoidance dominates (set `is_system_value: true` on the component)
3. **TH discount applied to US benchmarks** (~43% Base). Never use raw US numbers
4. **Cap Best case at 20x.** Higher = sanity-check fail (RF-01)
5. **Confidence Tier (T1-T4) is metadata only.** Does NOT multiply ROI
6. **Reviewer = advisor, not gate.** User retains decision authority
7. **Master rollup is mandatory.** Any feature change → must refresh `Feature_ROI_Summary.xlsx`
8. **Cascade rule.** Trace impact, present list, get approval, rebuild in dependency order. Never silent edit.

## Architecture overview

```
                       ┌──────────────────┐
                       │  User request    │
                       └────────┬─────────┘
                                │
        ┌───────────────┬───────┼────────────┬─────────────┐
        ↓               ↓       ↓            ↓             ↓
   "feature       "ปรับ X"  "deep review" "rollup"   "KILL/DEFER"
    ใหม่"
        ↓               ↓            ↓            ↓             ↓
   ┌────────┐      ┌─────────┐  ┌──────────┐ ┌────────────┐
   │ BUILD  │      │ ADJUST  │  │   DEEP   │ │ PORTFOLIO  │
   │        │      │         │  │  REVIEW  │ │            │
   └───┬────┘      └────┬────┘  └─────┬────┘ └─────┬──────┘
       │                │              │            │
       │ [opt suggest]  │ [if tier     │            │
       └─────chain──────┴──shift]──────┘            │
                        │                           │
       [auto-chain post-build/adjust]               │
                        └────────────────chain──────┘
```

## License

MIT — feel free to fork, adapt, or extend for your own hospital/healthcare PE roadmap workflows.

## Background

Built for Senestia/Synphaet hospital's PE roadmap. The methodology references:
- **Marty Cagan** — Outcome-driven, 4-risk discovery (Value/Usability/Feasibility/Viability)
- **Bottom-up driver tree** — every output traces to inputs via explicit cause-effect chain
- **3-point estimation (PERT)** — Worst/Base/Best, never single-point
- **Hospital baseline** — Senestia/Synphaet OPD 1.3M VN/yr, ~46% no-show post-APT-2.0
