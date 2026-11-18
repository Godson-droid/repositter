import { data } from '../lib/data'
import { MicroLabel, SectionHeading } from './ui'

export function Blocks() {
  const { buildingBlocks } = data
  return (
    <section id="blocks" className="border-t border-line bg-night-900/60">
      <div className="mx-auto max-w-7xl scroll-mt-24 px-4 py-16 sm:px-6 lg:px-8">
        <SectionHeading
          eyebrow="Building blocks"
          title="The OpenMinion surface RepoSitter actually exercises"
          lede="Taken from the tested-blocks table in FINDINGS.md, with the evidence artifact for each claim. One honest omission: the task-family scheduler tools did not fit this workflow and were not forced — delegation is via subagent() instead."
        />
        <div className="mt-10 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {buildingBlocks.map((b) => (
            <article
              key={b.block}
              className="flex flex-col rounded-panel border border-line bg-night-850/90 p-5 shadow-card"
            >
              <h3 className="font-display text-[16px] font-semibold text-moon-100">{b.block}</h3>
              <p className="mt-2 flex-1 text-dense leading-relaxed text-moon-300">{b.usage}</p>
              <p className="mt-3 border-l-2 border-iris-500/60 pl-3 text-dense leading-relaxed text-moon-200">
                {b.result}
              </p>
              <p className="mt-4 border-t border-line pt-3 font-mono text-[11px] leading-relaxed text-moon-500">
                {b.evidence}
              </p>
            </article>
          ))}
        </div>
        <MicroLabel className="mt-8">
          SDK pinned at openminion 0.1.21 in requirements.txt — the docs still say 0.1.20 (part of
          finding F14).
        </MicroLabel>
      </div>
    </section>
  )
}
