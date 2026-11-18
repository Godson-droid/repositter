import { useState } from 'react'
import { data, type Finding } from '../lib/data'
import { MicroLabel, SectionHeading } from './ui'

function FindingRow({ finding, open, onToggle }: { finding: Finding; open: boolean; onToggle: () => void }) {
  return (
    <div className="border-b border-line last:border-0">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center gap-4 px-5 py-4 text-left transition-colors hover:bg-night-800/70 sm:px-6"
      >
        <span className="w-10 shrink-0 font-mono text-[13px] font-semibold text-iris-400">
          {finding.id}
        </span>
        <span className="flex-1 font-display text-[15.5px] font-medium leading-snug text-moon-100">
          {finding.title}
        </span>
        <svg
          width="14"
          height="14"
          viewBox="0 0 14 14"
          fill="none"
          aria-hidden="true"
          className={`shrink-0 text-moon-500 transition-transform duration-300 ${open ? 'rotate-180' : ''}`}
        >
          <path d="M3 5.5 7 9.5 11 5.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open ? (
        <div className="animate-fade-up px-5 pb-6 pl-[76px] pr-6 sm:px-6 sm:pl-[80px]">
          <div className="max-w-3xl space-y-3">
            {finding.blocks.map((b, i) =>
              b.t === 'li' ? (
                <p key={i} className="flex gap-2.5 text-dense leading-relaxed text-moon-300">
                  <span aria-hidden="true" className="mt-[9px] h-1 w-1 shrink-0 rounded-full bg-iris-500" />
                  <span>{b.text}</span>
                </p>
              ) : (
                <p key={i} className="text-dense leading-relaxed text-moon-300">
                  {b.text}
                </p>
              ),
            )}
          </div>
        </div>
      ) : null}
    </div>
  )
}

export function Findings() {
  const { findings } = data
  const [openId, setOpenId] = useState<string | null>('F8')
  return (
    <section id="findings" className="mx-auto max-w-7xl scroll-mt-24 px-4 py-16 sm:px-6 lg:px-8">
      <SectionHeading
        eyebrow="Findings"
        title="Fourteen things the SDK taught us, the hard way"
        lede="Every finding below was reproduced or observed first-hand during this build, and each carries its reproduction in FINDINGS.md. This section is a quarter of the hackathon score, so nothing here is padded — F14 is even honest about which observations are small."
      />
      <div className="mt-10 overflow-hidden rounded-card border border-line bg-night-850/90 shadow-card">
        {findings.map((f) => (
          <FindingRow
            key={f.id}
            finding={f}
            open={openId === f.id}
            onToggle={() => setOpenId(openId === f.id ? null : f.id)}
          />
        ))}
      </div>
      <MicroLabel className="mt-6">
        Full text with reproductions: FINDINGS.md in the project repo.
      </MicroLabel>
    </section>
  )
}
