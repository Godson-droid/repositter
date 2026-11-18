import { data } from '../lib/data'
import { MicroLabel } from './ui'

export function Stats() {
  const { stats, relay } = data
  const capPct = Math.min(100, Math.round((stats.relayRequests / stats.dailyCap) * 100))
  const cells = [
    {
      label: 'Items scanned',
      value: String(stats.itemsScanned),
      note: 'Open issues and PRs fetched from the target repo in the latest scan',
    },
    {
      label: 'Items triaged',
      value: String(stats.itemsTriaged),
      note: 'Typed reports saved as run artifacts, validated against the schema',
    },
    {
      label: 'Memory records',
      value: String(stats.memoryRecords),
      note: 'Persistent fact records the next run reads back to skip finished work',
    },
    {
      label: 'Findings documented',
      value: String(stats.findingsCount),
      note: 'Friction points and bugs, each with a reproduction — see F1 to F14 below',
    },
  ]
  return (
    <section className="border-y border-line bg-night-900">
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="grid grid-cols-2 gap-x-6 gap-y-10 lg:grid-cols-5">
          {cells.map((c) => (
            <div key={c.label}>
              <MicroLabel>{c.label}</MicroLabel>
              <p className="tnum mt-2 font-display text-display-lg font-semibold text-moon-100">
                {c.value}
              </p>
              <p className="mt-2 max-w-[26ch] text-small leading-relaxed text-moon-400">{c.note}</p>
            </div>
          ))}
          <div>
            <MicroLabel>Model requests logged</MicroLabel>
            <p className="tnum mt-2 font-display text-display-lg font-semibold text-moon-100">
              {stats.relayRequests}
              <span className="ml-1.5 text-[19px] font-medium text-moon-500">/ {stats.dailyCap} daily</span>
            </p>
            <div
              className="mt-3 h-1.5 w-full max-w-[180px] overflow-hidden rounded-full bg-night-700"
              role="img"
              aria-label={`${stats.relayRequests} of ${stats.dailyCap} free daily requests appear in the relay log`}
            >
              <div className="h-full rounded-full bg-iris-500" style={{ width: `${capPct}%` }} />
            </div>
            <p className="mt-2 max-w-[26ch] text-small leading-relaxed text-moon-400">
              Every forwarded call sits in the relay audit log — all HTTP 200, averaging{' '}
              {relay.avgSeconds}s. On a free tier, the budget is real (finding F8).
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}
