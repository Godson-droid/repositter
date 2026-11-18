import { data, shortId, type ScanItem } from '../lib/data'
import { Card, Chip, ExtLink, MicroLabel, SectionHeading } from './ui'

function priorityTone(p: string): 'rose' | 'amber' | 'moon' {
  if (p.toLowerCase() === 'high') return 'rose'
  if (p.toLowerCase() === 'medium') return 'amber'
  return 'moon'
}

function statusChip(item: ScanItem) {
  if (item.status === 'triaged') return <Chip tone="mint" dot>Triaged</Chip>
  if (item.status === 'in-memory') return <Chip tone="iris">Already in memory</Chip>
  return <Chip tone="amber">Awaiting run</Chip>
}

export function Triage() {
  const { featuredReport, items, meta, run00, latestScanSource } = data
  if (!featuredReport) return null
  const r = featuredReport
  const issueUrl = `${meta.targetUrl}/issues/${r.item_number}`
  return (
    <section id="triage" className="mx-auto max-w-7xl scroll-mt-24 px-4 py-16 sm:px-6 lg:px-8">
      <SectionHeading
        eyebrow="Triage reports"
        title="One real verdict, exactly as the agent wrote it"
        lede="This is the typed TriageReport the classifier subagent returned during the shakedown run — Pydantic-validated, saved as a run artifact, and recorded in memory. Nothing on this page is a mock-up."
      />

      <div className="mt-10 grid gap-6 lg:grid-cols-5">
        {/* Featured report */}
        <Card className="p-6 sm:p-8 lg:col-span-3">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <MicroLabel>
                {meta.target} · {r.item_kind} #{r.item_number}
              </MicroLabel>
              <h3 className="mt-3 font-display text-card font-semibold leading-snug text-moon-100">
                <ExtLink href={issueUrl} className="text-moon-100 hover:text-iris-300">
                  {r.title}
                </ExtLink>
              </h3>
            </div>
            <div className="flex shrink-0 gap-2">
              <Chip tone="iris">{r.category}</Chip>
              <Chip tone={priorityTone(r.priority)}>{r.priority} priority</Chip>
            </div>
          </div>

          <p className="mt-5 text-[15px] leading-relaxed text-moon-300">{r.summary}</p>

          <div className="mt-6">
            <MicroLabel>Suggested labels</MicroLabel>
            <div className="mt-2.5 flex flex-wrap gap-2">
              {r.suggested_labels.map((l) => (
                <span
                  key={l}
                  className="rounded-full border border-line bg-night-800 px-3 py-1 font-mono text-[12px] text-moon-200"
                >
                  {l}
                </span>
              ))}
            </div>
            <p className="mt-3 text-small leading-relaxed text-moon-500">
              The classifier drifted outside the rubric’s label vocabulary here — that is finding
              F12, and exactly why reports stay drafts for a human until the approval gate.
            </p>
          </div>

          <div className="mt-6 rounded-panel border border-line bg-night-900 p-5">
            <MicroLabel className="text-iris-400">Suggested next action</MicroLabel>
            <p className="mt-2 text-dense leading-relaxed text-moon-200">{r.suggested_next_action}</p>
          </div>

          {run00 ? (
            <dl className="mt-6 grid grid-cols-1 gap-4 border-t border-line pt-5 font-mono text-[11.5px] text-moon-500 sm:grid-cols-3">
              <div>
                <dt className="uppercase tracking-[0.14em]">Scan run</dt>
                <dd className="mt-1 text-moon-300">{shortId(run00.scanRunId, 10)}</dd>
              </div>
              <div>
                <dt className="uppercase tracking-[0.14em]">Classify run</dt>
                <dd className="mt-1 text-moon-300">{shortId(run00.classifyRunIds[0] ?? null, 10)}</dd>
              </div>
              <div>
                <dt className="uppercase tracking-[0.14em]">Record run</dt>
                <dd className="mt-1 text-moon-300">{shortId(run00.recordRunId, 10)}</dd>
              </div>
            </dl>
          ) : null}
        </Card>

        {/* Scan ledger */}
        <Card className="flex flex-col p-6 sm:p-8 lg:col-span-2">
          <div className="flex items-baseline justify-between gap-3">
            <h3 className="font-display text-card font-semibold text-moon-100">Scan ledger</h3>
            <span className="font-mono text-[11px] text-moon-500">
              source: runs/{latestScanSource}
            </span>
          </div>
          <p className="mt-2 text-dense leading-relaxed text-moon-400">
            Every item the latest scan fetched, with the status the artifacts support. Items
            without a report have not been classified yet — the ledger says so rather than
            guessing.
          </p>
          <div className="mt-5 flex-1 overflow-hidden rounded-panel border border-line">
            <table className="w-full text-left text-dense">
              <thead>
                <tr className="border-b border-line bg-night-900 text-[11px] uppercase tracking-[0.14em] text-moon-500">
                  <th className="px-4 py-2.5 font-semibold">Item</th>
                  <th className="px-4 py-2.5 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.number} className="border-b border-line/60 last:border-0 hover:bg-night-800/60">
                    <td className="px-4 py-2.5">
                      <span className="font-mono text-[12.5px] text-moon-200">#{item.number}</span>
                      {item.title ? (
                        <span className="mt-0.5 block max-w-[30ch] truncate text-small text-moon-400">
                          {item.title}
                        </span>
                      ) : null}
                    </td>
                    <td className="px-4 py-2.5">{statusChip(item)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </section>
  )
}
