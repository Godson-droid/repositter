# RepoSitter — Design System & Handoff Notes

RepoSitter is the public dashboard for a GitHub issue/PR triage agent built on the
OpenMinion SDK (Cortensor Hackathon #5). The design goal matches the product's
promise: a calm, exact, evidence-first surface that feels like a shipped
maintainer tool, not a hackathon page — and that never shows a number it cannot
source from a committed run artifact.

**Brand line:** *The triage agent that remembers.*
The mark is a watch ring with a settled point — the sitter's eye on the repo —
drawn in the accent with one mint point for "recorded". It is the only place
iris and mint appear together at full strength.

---

## OLED-first color tokens

Defined in `tailwind.config.js`; never hard-code hex values in components.
The page background is **true black** (`#000000`) so OLED pixels switch off;
surfaces rise from black in small steps, with hairline borders instead of
grey washes. No gradients on surfaces — the only gradient is the hero's
ambient glow.

| Token | Value | Usage |
| --- | --- | --- |
| `night-950` | `#000000` | Page background — true black |
| `night-900` | `#050507` | Sunken sections, inset panels |
| `night-850` | `#0a0a0e` | Card surface |
| `night-800` | `#101016` | Raised elements, label pills |
| `night-700` | `#17171f` | Hover states, progress track |
| `night-600` | `#23232e` | Strong borders, timeline rule |
| `line` | `rgba(240,240,255,.08)` | Default 1px border everywhere |
| `iris-500` | `#7c6cff` | **Primary accent** — RepoSitter's own identity: links, stage numbers, memory states, the request bar |
| `iris-300 / 400` | `#b3a8ff / #9787ff` | Accent text on black |
| `amber-400` | `#fbbf24` | **Held / pending / scheduled** — the approval gate and everything waiting on a human or a date |
| `rose-400 / 500` | `#fb7185 / #f43f5e` | Danger and failure only: the failed run, high priority |
| `mint-400` | `#34d399` | **Verified / complete** — triaged items, executed approvals, live status |
| `moon-100` | `#f4f4f8` | Primary text |
| `moon-300 / 400` | `#c3c3cf / #9a9aa8` | Secondary text |
| `moon-500` | `#63636f` | Captions, micro-labels, mono metadata |

Rules: the accent is rationed — one strong iris moment per view (the hero
word, stage numerals, the ledger's memory state). Amber always means
"something is waiting" and is the gate's colour end to end; the gate stage
card in the pipeline and the gate section share it deliberately. Rose never
decorates. Mint never appears without a completed fact behind it.

## Typography

| Role | Face | Notes |
| --- | --- | --- |
| Display / headings / wordmark | **Sora** 500–700 | Tight tracking (`-0.025em` to `-0.03em`); sizes 56 / 40 / 30 / 19 |
| UI / body | **Inter** 400–700 | 15px body, 13.5px dense data, 12.5px small |
| Data / IDs / commands | **JetBrains Mono** 400–500 | Run IDs, record keys, CLI commands, ledger numbers |
| Numbers | Sora or Inter + `.tnum` | Tabular figures mandatory for every stat so columns never jitter |

Micro-labels are 11px uppercase at `0.16em` tracking — the system's main
structural rhythm; every section, card group and stat is introduced by one.

## Spacing & shape

- 4px base grid; sections are `py-16` bands, cards `gap-6` apart.
- Page container: `max-w-7xl` with 16/24/32px gutters.
- Radii: cards `20px` (`rounded-card`), inner panels `16px` (`rounded-panel`),
  pills full.
- Cards: `night-850` at 90% over a hairline `line` border, `shadow-card`
  (inset top highlight + deep soft drop). On true black, the inset highlight
  does the work a drop shadow does on grey themes.

## Component inventory

| Component | File | Notes |
| --- | --- | --- |
| `Nav` | `components/Nav.tsx` | Sticky, blurred black; wordmark, hackathon badge, section anchors, external repo links, live status pill. Links shed progressively by breakpoint (subtitle ≥xl, badge ≥lg, scratch link ≥1600px, status pill ≥1400px) so the bar never wraps |
| `LogoMark`, `Chip`, `MicroLabel`, `SectionHeading`, `Card`, `LiveDot`, `ExtLink` | `components/ui.tsx` | Shared primitives — extend here, not inline. `Chip` tones map 1:1 to the semantic rules above |
| `Hero` | `components/Hero.tsx` | Brand line + the four-stage pipeline as a flow; the Propose card is amber-tinted with an "Approval gate" chip so the gate reads as a stage, not a footnote |
| `Stats` | `components/Stats.tsx` | Five baked numbers from `data.json`; the request stat carries a thin iris bar against the 50/day free cap |
| `Triage` | `components/Triage.tsx` | The real typed report for issue #759 as a rich card (category/priority chips, label pills, next-action panel, stage run IDs in mono) beside the 25-item scan ledger with honest status chips |
| `Runs` | `components/Runs.tsx` | Vertical timeline: failed attempt (rose), shakedown + probe (mint/iris), completed runs folded in from artifacts, then scheduled runs (amber) with dates, commands, and what each proves |
| `Gate` | `components/Gate.tsx` | The action-policy table as configured, the three-step hold/approve/execute flow, the scratch-repo proof card, and FINDINGS.md's own "Pending" paragraph quoted verbatim |
| `Memory` | `components/Memory.tsx` | The memory-store dump rendered as registry cards, the `openminion doctor` summary (22 OK / 4 WARN, warnings shown), and the relay budget card |
| `Findings` | `components/Findings.tsx` | All 14 findings as an accordion (F8 open by default — the request-economics finding), bodies parsed from FINDINGS.md at build time |
| `Blocks` | `components/Blocks.tsx` | The 11 tested building blocks from the FINDINGS.md table, each with its evidence artifact path |
| `Footer` | `components/Footer.tsx` | Builder credit, deadline, stack, and the data-provenance note |

## Data & truthfulness

There is no mock data and no runtime fetching. `scripts/build-data.mjs`
(plain Node, zero dependencies) reads the real artifacts from the project
root — `runs/*/summary.json`, `runs/*/reports/*.json`, the scan JSONs,
`runs/diagnostics/` (memory dump, doctor output), `runs/relay.log`,
`FINDINGS.md`, `repositter.toml`, `requirements.txt` — and emits
`src/data.json`. `npm run build` runs it before `tsc`/`vite`, so a stale
`data.json` cannot ship.

Refresh contract for the scheduled runs (16–17 Nov): when
`runs/run-01-openminion/`, `runs/run-02-openminion/` and
`runs/run-03-scratch/` appear, re-running the script folds them into the
timeline as completed runs (with held/resumed approval states), updates
the scan ledger from the newest main-target scan, marks newly reported
items as triaged, and empties the scheduled list — no code changes. Runs
against the scratch repo are timeline-only: their issue numbers live in a
different repo's namespace and never enter the main ledger (this is
enforced in the script and was verified against simulated artifacts).
Absolute machine paths in the doctor output are sanitized before baking.

Status vocabulary, used consistently: **Triaged** (a typed report artifact
exists), **Already in memory** (a scan lists the item as triaged but no
report artifact is in this repo), **Awaiting run** (fetched, not yet
classified), **Scheduled** (a future run, with its date), **Failed**
(kept as evidence). Nothing is ever rendered as done that an artifact
does not say is done.

## Responsive behavior

Single column below `lg` throughout: pipeline stages stack with the gate
card last, the triage grid stacks report over ledger, stats go two-up,
the gate and memory grids stack. The nav sheds elements by breakpoint
(see inventory) before it ever wraps. Type drops from 56px display to
40px on small screens; the scan ledger table keeps two columns at 390px.

## Screenshots

In `docs/screenshots/`, taken from the production build (base
`/repositter/`; rendered via a relative-base copy for local capture):

- `desktop.png` — 1440×900 top viewport
- `full-page.png` — 1440 × full height
- `mobile-top.png` — 390×844 top viewport · `mobile.png` — 390 × full height
- `triage.png`, `gate.png`, `findings.png` — 1440×900 section details
