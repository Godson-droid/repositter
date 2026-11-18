import { data, shortId } from '../lib/data'
import { Card, Chip, MicroLabel, SectionHeading } from './ui'

export function Memory() {
  const { memory, doctor, relay, meta } = data
  return (
    <section id="memory" className="border-t border-line bg-night-900/60">
      <div className="mx-auto max-w-7xl scroll-mt-24 px-4 py-16 sm:px-6 lg:px-8">
        <SectionHeading
          eyebrow="Memory registry"
          title="What the sitter remembers"
          lede="RepoSitter’s cross-run state lives in the SDK’s persistent memory — not in a session, not in a file the agent rereads by hand. This is the actual memory store dump from the shakedown run, queried on 15 Nov 2026."
        />

        <div className="mt-10 grid gap-6 lg:grid-cols-5">
          <div className="flex flex-col gap-4 lg:col-span-3">
            {memory.records.map((rec) => (
              <Card key={rec.id} className="p-6">
                <div className="flex flex-wrap items-center gap-2">
                  <Chip tone="iris">{rec.type}</Chip>
                  <Chip tone="moon">{rec.scope}</Chip>
                  <span className="ml-auto font-mono text-[11.5px] text-moon-500">
                    id {shortId(rec.id, 10)}
                  </span>
                </div>
                <p className="mt-4 font-mono text-[13px] leading-relaxed text-moon-100">{rec.key}</p>
                <p className="mt-2 text-dense leading-relaxed text-moon-300">{rec.content}</p>
                <p className="mt-4 border-t border-line pt-3 text-small leading-relaxed text-moon-500">
                  Written by run 00’s record stage. The probe scan then found this record in a fresh
                  session and skipped issue #759 — the round trip is the proof. One quirk: the SDK
                  silently slugified the requested key (
                  <span className="font-mono">triaged:openminion/openminion#759</span> became the
                  stored key above). That is finding F7.
                </p>
              </Card>
            ))}
            <p className="font-mono text-[11.5px] text-moon-500">
              store: {memory.store} · dump: runs/diagnostics/memory-records.txt
            </p>
          </div>

          <div className="flex flex-col gap-6 lg:col-span-2">
            <Card className="p-6">
              <div className="flex items-baseline justify-between">
                <MicroLabel>Diagnostics — openminion doctor</MicroLabel>
                <span className="tnum font-mono text-[12px] text-moon-400">
                  <span className="text-mint-400">{doctor.ok} OK</span> ·{' '}
                  <span className="text-amber-400">{doctor.warn} WARN</span>
                </span>
              </div>
              <div className="mt-4 space-y-3">
                {doctor.warns.map((w) => (
                  <div key={w.name} className="rounded-panel border border-line bg-night-900 px-4 py-3">
                    <p className="font-mono text-[12px] text-amber-300">{w.name}</p>
                    <p className="mt-1 text-small leading-relaxed text-moon-400">{w.detail}</p>
                  </div>
                ))}
              </div>
              <p className="mt-4 text-small leading-relaxed text-moon-500">
                All {doctor.total} checks are committed at runs/diagnostics/doctor.txt, warnings
                included. Doctor earned its keep during the build — see the diagnostics row in the
                building blocks.
              </p>
            </Card>

            <Card className="p-6">
              <MicroLabel>The relay — a counted budget</MicroLabel>
              <dl className="mt-4 grid grid-cols-3 gap-4">
                <div>
                  <dt className="text-[11px] font-semibold uppercase tracking-[0.14em] text-moon-500">
                    Requests
                  </dt>
                  <dd className="tnum mt-1 font-display text-[26px] font-semibold text-moon-100">
                    {relay.chatCompletions}
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] font-semibold uppercase tracking-[0.14em] text-moon-500">
                    Avg latency
                  </dt>
                  <dd className="tnum mt-1 font-display text-[26px] font-semibold text-moon-100">
                    {relay.avgSeconds}s
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] font-semibold uppercase tracking-[0.14em] text-moon-500">
                    Failures
                  </dt>
                  <dd className="tnum mt-1 font-display text-[26px] font-semibold text-moon-100">
                    {relay.allOk ? '0' : '—'}
                  </dd>
                </div>
              </dl>
              <p className="mt-4 text-small leading-relaxed text-moon-500">
                OpenMinion never sees a real API key: a loopback relay forwards each request to
                OpenRouter and attaches the credential at the boundary, logging every call (model{' '}
                <span className="font-mono text-moon-300">{meta.model}</span>, {relay.minSeconds}–
                {relay.maxSeconds}s per request). The log is the audit trail behind finding F8’s
                request economics.
              </p>
            </Card>
          </div>
        </div>
      </div>
    </section>
  )
}
