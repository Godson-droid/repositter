import { data } from '../lib/data'
import { Card, Chip, MicroLabel, SectionHeading } from './ui'

const POLICY_ROWS: { tool: string; declared: string; policy: string; tone: 'mint' | 'amber' }[] = [
  {
    tool: 'memory.write',
    declared: 'WRITE_SAFE · idempotent = false',
    policy: 'auto-approved by action-policy rule',
    tone: 'mint',
  },
  {
    tool: 'fetch_open_items',
    declared: 'READ_ONLY · idempotent',
    policy: 'runs freely — public reads only',
    tone: 'mint',
  },
  {
    tool: 'propose_github_write',
    declared: 'dangerous = True',
    policy: 'require_confirm — the run pauses',
    tone: 'amber',
  },
]

const FLOW = [
  {
    step: 'The agent proposes',
    body: 'Stage four asks the operations agent to apply the top report’s first suggested label through propose_github_write.',
  },
  {
    step: 'Policy pauses the run',
    body: 'The tool is declared dangerous, so the default action policy holds the call. The run thread waits; an approval_held.json artifact records exactly what was about to happen.',
  },
  {
    step: 'A human decides',
    body: 'No approval, no write — the proposal dies with the run. With approval, the same thread resumes, the write executes, and an API read-back verifies the label actually landed.',
  },
]

export function Gate() {
  const { meta, pendingNote, scheduledRuns } = data
  const proofRun = scheduledRuns.find((r) => r.id === 'run-03')
  return (
    <section id="gate" className="mx-auto max-w-7xl scroll-mt-24 px-4 py-16 sm:px-6 lg:px-8">
      <SectionHeading
        eyebrow="The approval gate"
        title="Reads are free. Writes wait for a human."
        lede="RepoSitter’s strongest guarantee is structural, not a prompt instruction: the only tool that can change GitHub is declared dangerous in code, so the SDK’s policy engine — not the model’s good behaviour — decides whether a write happens."
      />

      <div className="mt-10 grid gap-6 lg:grid-cols-5">
        <Card className="p-6 sm:p-8 lg:col-span-3">
          <MicroLabel>Action policy, as configured</MicroLabel>
          <div className="mt-4 overflow-hidden rounded-panel border border-line">
            {POLICY_ROWS.map((row, i) => (
              <div
                key={row.tool}
                className={`flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-center sm:justify-between ${
                  i !== POLICY_ROWS.length - 1 ? 'border-b border-line' : ''
                } bg-night-900`}
              >
                <div>
                  <p className="font-mono text-[13px] text-moon-100">{row.tool}</p>
                  <p className="mt-0.5 font-mono text-[11.5px] text-moon-500">{row.declared}</p>
                </div>
                <Chip tone={row.tone}>{row.policy}</Chip>
              </div>
            ))}
          </div>
          <p className="mt-4 text-small leading-relaxed text-moon-500">
            Memory writes needing their own policy rule was a surprise — an autonomous agent that
            must ask permission to remember anything cannot finish a batch run. That discovery is
            finding F6; the rule format had to be read out of the SDK source.
          </p>

          <div className="mt-8 space-y-0">
            {FLOW.map((f, i) => (
              <div key={f.step} className="relative flex gap-4 pb-7 last:pb-0">
                {i !== FLOW.length - 1 ? (
                  <span aria-hidden="true" className="absolute left-[13px] top-8 h-full w-px bg-night-600" />
                ) : null}
                <span className="z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-amber-500/40 bg-amber-500/10 font-mono text-[11px] font-semibold text-amber-300">
                  {i + 1}
                </span>
                <div>
                  <h3 className="font-display text-[15.5px] font-semibold text-moon-100">{f.step}</h3>
                  <p className="mt-1 max-w-xl text-dense leading-relaxed text-moon-300">{f.body}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <div className="flex flex-col gap-6 lg:col-span-2">
          <Card className="border-amber-500/25 p-6 sm:p-8">
            <div className="flex items-center justify-between gap-3">
              <MicroLabel className="text-amber-400">The proof</MicroLabel>
              <Chip tone="amber">{proofRun ? `Scheduled · ${proofRun.date}` : 'Complete'}</Chip>
            </div>
            <h3 className="mt-3 font-display text-card font-semibold text-moon-100">
              Held, approved, executed — on a repo built for it
            </h3>
            <p className="mt-3 text-dense leading-relaxed text-moon-300">
              The gate proof runs against{' '}
              <span className="font-mono text-moon-100">{meta.scratch}</span>, a scratch repo seeded
              for exactly this: the write is proposed, held, approved, executed, and verified by
              read-back. It never touches a third-party repo.
            </p>
            {proofRun ? (
              <p className="mt-4 rounded-panel border border-line bg-night-900 px-4 py-3 font-mono text-[11.5px] leading-relaxed text-moon-400">
                $ {proofRun.command}
              </p>
            ) : null}
          </Card>

          <Card className="flex-1 p-6 sm:p-8">
            <MicroLabel>Stated plainly in FINDINGS.md</MicroLabel>
            <blockquote className="mt-3 text-dense leading-relaxed text-moon-300">
              “{pendingNote}”
            </blockquote>
            <p className="mt-4 text-small text-moon-500">
              The stage is implemented and the policy behaviour verified; the held and resumed
              artifact pair joins runs/ when the scheduled runs land.
            </p>
          </Card>
        </div>
      </div>
    </section>
  )
}
