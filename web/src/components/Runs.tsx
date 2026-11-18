import type { ReactNode } from 'react'
import { data, fmtDateTime, fmtDay, type ExtraRun } from '../lib/data'
import { Chip, MicroLabel, SectionHeading } from './ui'

type Tone = 'mint' | 'rose' | 'iris' | 'amber'

function TimelineItem({
  date,
  title,
  tone,
  chip,
  children,
  last = false,
}: {
  date: string
  title: string
  tone: Tone
  chip: ReactNode
  children: ReactNode
  last?: boolean
}) {
  const dot =
    tone === 'mint'
      ? 'bg-mint-400'
      : tone === 'rose'
        ? 'bg-rose-400'
        : tone === 'amber'
          ? 'bg-amber-400'
          : 'bg-iris-400'
  return (
    <li className="relative flex gap-5 pb-10 last:pb-0 sm:gap-7">
      {!last ? <span aria-hidden="true" className="absolute left-[5px] top-4 h-full w-px bg-night-600" /> : null}
      <span className={`relative z-10 mt-1.5 h-[11px] w-[11px] shrink-0 rounded-full ${dot} ring-4 ring-black`} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <span className="font-mono text-[12px] text-moon-500">{date}</span>
          <h3 className="font-display text-card font-semibold text-moon-100">{title}</h3>
          {chip}
        </div>
        <div className="mt-2.5 max-w-3xl text-dense leading-relaxed text-moon-300">{children}</div>
      </div>
    </li>
  )
}

function ExtraRunItem({ run }: { run: ExtraRun }) {
  const facts: string[] = []
  if (run.fetchedCount != null) facts.push(`fetched ${run.fetchedCount} items`)
  if (run.reportCount > 0) facts.push(`${run.reportCount} new typed report${run.reportCount === 1 ? '' : 's'}`)
  if (run.alreadyTriaged.length > 0) facts.push(`${run.alreadyTriaged.length} skipped from memory`)
  if (run.seconds != null) facts.push(`${run.seconds}s wall clock`)
  if (run.relayRequests != null) facts.push(`${run.relayRequests} model requests`)
  return (
    <TimelineItem
      date={fmtDateTime(run.startedAt)}
      title={`Run — ${run.runName}`}
      tone="mint"
      chip={<Chip tone="mint" dot>Complete</Chip>}
    >
      <p>
        Full pipeline against <span className="font-mono text-moon-100">{run.target}</span>
        {facts.length ? <> — {facts.join(' · ')}</> : null}.
      </p>
      {run.approvalHeld ? (
        <p className="mt-2">
          <Chip tone="amber">Approval held</Chip>{' '}
          <span className="text-moon-400">
            The proposed GitHub write was paused by the policy engine; the held artifact is in the
            run directory.
          </span>
        </p>
      ) : null}
      {run.approvalResumed ? (
        <p className="mt-2">
          <Chip tone="mint">Approval executed</Chip>{' '}
          <span className="text-moon-400">
            The held write was approved, executed, and verified by an API read-back.
          </span>
        </p>
      ) : null}
      <p className="mt-2 font-mono text-[11.5px] text-moon-500">runs/{run.dir}/</p>
    </TimelineItem>
  )
}

export function Runs() {
  const { failedRun, run00, probeScan, extraRuns, scheduledRuns } = data
  return (
    <section id="runs" className="border-t border-line bg-night-900/60">
      <div className="mx-auto max-w-7xl scroll-mt-24 px-4 py-16 sm:px-6 lg:px-8">
        <SectionHeading
          eyebrow="Runs timeline"
          title="What has actually run — and what is booked next"
          lede="Completed runs link to their committed artifacts. Scheduled runs are stated as scheduled, with the date the free-tier request budget makes possible and exactly what each one will prove."
        />
        <ol className="mt-12 max-w-4xl">
          {failedRun ? (
            <TimelineItem
              date={fmtDateTime(failedRun.startedAt)}
              title="First live attempt — failed, kept on purpose"
              tone="rose"
              chip={<Chip tone="rose">Failed · evidence for F3</Chip>}
            >
              <p>
                Every provider call returned HTTP 200, yet the agent died with{' '}
                <span className="font-mono text-[12.5px] text-rose-300">EMPTY_PROVIDER_RESPONSE</span>{' '}
                after {failedRun.relayRequests} requests in {failedRun.seconds}s. The cause was the
                relay forwarding chunked-streaming responses; the buffered relay fixed it. The
                failed run stays in the repo as evidence rather than being deleted.
              </p>
              <p className="mt-2 font-mono text-[11.5px] text-moon-500">runs/{failedRun.dir}/</p>
            </TimelineItem>
          ) : null}

          {run00 ? (
            <TimelineItem
              date={fmtDateTime(run00.startedAt)}
              title="Run 00 — shakedown, end to end"
              tone="mint"
              chip={<Chip tone="mint" dot>Complete</Chip>}
            >
              <p>
                The full pipeline against the real{' '}
                <span className="font-mono text-moon-100">{run00.target}</span> repo: scanned{' '}
                {run00.fetchedCount} open items, classified issue #759 through the delegated
                subagent, and wrote its memory record — {run00.seconds}s wall clock across the
                scan, classify and record stages.
              </p>
              <p className="mt-2 font-mono text-[11.5px] text-moon-500">runs/{run00.dir}/</p>
            </TimelineItem>
          ) : null}

          {probeScan ? (
            <TimelineItem
              date="15 Nov 2026"
              title="Probe scan — memory answers back"
              tone="iris"
              chip={<Chip tone="iris" dot>Complete</Chip>}
            >
              <p>
                A scan-only run in a fresh session fetched {probeScan.fetchedCount} items and
                correctly reported #{probeScan.alreadyTriaged.join(', #')} as already triaged from
                the shakedown run’s memory record, with {probeScan.newItems.length} new items
                waiting. Cross-run memory, proven before the full example runs were made.
              </p>
              <p className="mt-2 font-mono text-[11.5px] text-moon-500">runs/probe-scan/scan.json</p>
            </TimelineItem>
          ) : null}

          {extraRuns.map((run) => (
            <ExtraRunItem key={run.dir} run={run} />
          ))}

          {scheduledRuns.map((run, i) => (
            <TimelineItem
              key={run.id}
              date={fmtDay(run.date)}
              title={`${run.id.replace('run-', 'Run ')} — ${run.title}`}
              tone="amber"
              chip={<Chip tone="amber">Scheduled</Chip>}
              last={i === scheduledRuns.length - 1 && extraRuns.length === 0}
            >
              <p>
                Target <span className="font-mono text-moon-100">{run.target}</span>. {run.proves}
              </p>
              <p className="mt-2 font-mono text-[11.5px] text-moon-500">$ {run.command}</p>
            </TimelineItem>
          ))}
        </ol>
        <MicroLabel className="mt-10">
          Why scheduled? The free tier allows 50 model requests a day, and one run spends them
          fast — finding F8 has the arithmetic.
        </MicroLabel>
      </div>
    </section>
  )
}
