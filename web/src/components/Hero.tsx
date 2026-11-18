import { data } from '../lib/data'
import { Chip, MicroLabel } from './ui'

interface Stage {
  n: string
  name: string
  tool: string
  body: string
  gate?: boolean
}

const STAGES: Stage[] = [
  {
    n: '01',
    name: 'Scan',
    tool: 'skill.get · fetch_open_items · memory.search',
    body: 'Loads the triage rubric skill, fetches the repo’s open issues and PRs, and checks persistent memory for anything already triaged.',
  },
  {
    n: '02',
    name: 'Classify',
    tool: 'subagent() · typed TriageReport',
    body: 'Each new item goes to a bounded classifier subagent, which returns a Pydantic-validated report: category, priority, summary, labels, next action.',
  },
  {
    n: '03',
    name: 'Remember',
    tool: 'memory.write · fact records',
    body: 'One memory record per verdict, keyed to the item. The next run skips it — memory, not session context, carries state between runs.',
  },
  {
    n: '04',
    name: 'Propose',
    tool: 'propose_github_write · dangerous',
    body: 'Applying a label or posting a comment is a dangerous write. The policy engine pauses the run until a human approves on the same thread.',
    gate: true,
  },
]

function StageCard({ stage, last }: { stage: Stage; last: boolean }) {
  return (
    <div className="relative flex-1">
      <div
        className={`h-full rounded-panel border p-5 ${
          stage.gate
            ? 'border-amber-500/35 bg-amber-500/[0.05] shadow-[0_0_0_1px_rgba(245,158,11,0.12),0_12px_32px_-12px_rgba(0,0,0,0.8)]'
            : 'border-line bg-night-850/90 shadow-card'
        }`}
      >
        <div className="flex items-center justify-between">
          <span
            className={`font-mono text-[12px] font-medium ${stage.gate ? 'text-amber-400' : 'text-iris-400'}`}
          >
            {stage.n}
          </span>
          {stage.gate ? <Chip tone="amber">Approval gate</Chip> : null}
        </div>
        <h3 className="mt-3 font-display text-card font-semibold text-moon-100">{stage.name}</h3>
        <p className="mt-2 text-dense leading-relaxed text-moon-300">{stage.body}</p>
        <p className="mt-4 border-t border-line pt-3 font-mono text-[11px] leading-relaxed text-moon-500">
          {stage.tool}
        </p>
      </div>
      {!last ? (
        <span
          aria-hidden="true"
          className="absolute -right-3 top-1/2 z-10 hidden -translate-y-1/2 text-moon-500 lg:block"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M2 7h9M8 3.5 11.5 7 8 10.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
      ) : null}
    </div>
  )
}

export function Hero() {
  const { meta } = data
  return (
    <section id="top" className="relative overflow-hidden">
      {/* Ambient glow — the only gradient on the page */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 -top-40 h-[480px]"
        style={{
          background:
            'radial-gradient(560px 300px at 28% 0%, rgba(124,108,255,0.16), transparent 70%), radial-gradient(480px 260px at 78% 0%, rgba(52,211,153,0.06), transparent 70%)',
        }}
      />
      <div className="relative mx-auto max-w-7xl px-4 pb-14 pt-14 sm:px-6 sm:pt-20 lg:px-8">
        <div className="max-w-3xl animate-fade-up">
          <MicroLabel>
            <span className="text-iris-400">OpenMinion SDK</span>
            <span className="mx-2 text-night-600">/</span> Cortensor Hackathon #5
          </MicroLabel>
          <h1 className="mt-5 font-display text-display-lg font-semibold text-moon-100 sm:text-display-xl">
            The triage agent
            <br />
            that <span className="text-iris-400">remembers</span>.
          </h1>
          <p className="mt-6 max-w-2xl text-[17px] leading-relaxed text-moon-300">
            RepoSitter watches a GitHub repository so its maintainers don’t have to. It scans the
            open issues and pull requests, classifies the new ones with a delegated subagent,
            remembers every verdict in persistent memory — and never writes to GitHub without a
            human saying yes.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-2.5">
            <Chip tone="moon">
              Target <span className="font-mono text-moon-100">{meta.target}</span>
            </Chip>
            <Chip tone="moon">
              Model <span className="font-mono text-moon-100">{meta.model}</span>
            </Chip>
            <Chip tone="moon">
              SDK <span className="font-mono text-moon-100">{meta.sdk}</span>
            </Chip>
            <Chip tone="mint" dot>
              Free tier only · no paid fallback
            </Chip>
          </div>
        </div>

        <div className="mt-14">
          <MicroLabel className="mb-4">How a run works — four stages</MicroLabel>
          <div className="flex flex-col gap-4 lg:flex-row lg:gap-6">
            {STAGES.map((s, i) => (
              <StageCard key={s.n} stage={s} last={i === STAGES.length - 1} />
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
