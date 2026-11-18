import { data } from '../lib/data'
import { Chip, ExtLink, LiveDot, LogoMark } from './ui'

export function Nav() {
  const { meta, scheduledRuns, stats } = data
  const statusText =
    scheduledRuns.length > 0
      ? `Shakedown complete · ${scheduledRuns.length} scheduled`
      : 'All example runs complete'
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-black/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-3 px-4 sm:gap-4 sm:px-6 lg:px-8">
        <a href="#top" className="flex items-center gap-3">
          <LogoMark />
          <span className="leading-none">
            <span className="block font-display text-[17px] font-semibold tracking-tight text-moon-100">
              RepoSitter
            </span>
            <span className="mt-1 hidden whitespace-nowrap text-[11px] font-medium text-moon-500 xl:block">
              GitHub triage agent · OpenMinion SDK
            </span>
          </span>
        </a>

        <span className="ml-2 hidden lg:inline-flex">
          <Chip tone="iris">Cortensor Hackathon #5</Chip>
        </span>

        <nav className="ml-auto flex items-center gap-4 text-[13px] font-medium text-moon-300 sm:gap-5">
          <a href="#triage" className="hidden whitespace-nowrap transition-colors hover:text-moon-100 lg:inline">
            Triage
          </a>
          <a href="#runs" className="hidden whitespace-nowrap transition-colors hover:text-moon-100 lg:inline">
            Runs
          </a>
          <a href="#gate" className="hidden whitespace-nowrap transition-colors hover:text-moon-100 lg:inline">
            Approval gate
          </a>
          <a href="#findings" className="hidden whitespace-nowrap transition-colors hover:text-moon-100 lg:inline">
            Findings
          </a>
          <span className="hidden h-4 w-px bg-night-600 lg:block" />
          <ExtLink href={meta.targetUrl} className="hidden text-moon-300 sm:inline-flex">
            Target repo
          </ExtLink>
          <ExtLink href={meta.scratchUrl} className="hidden text-moon-300 min-[1600px]:inline-flex">
            Scratch repo
          </ExtLink>
          <ExtLink href={meta.eventUrl} className="hidden text-moon-300 sm:inline-flex">
            DoraHacks
          </ExtLink>
        </nav>

        <span className="ml-1 hidden items-center gap-2 whitespace-nowrap rounded-full border border-line bg-night-850 py-1.5 pl-3 pr-3.5 min-[1400px]:inline-flex">
          <LiveDot />
          <span className="whitespace-nowrap text-[11.5px] font-semibold text-moon-200">
            {statusText}
            <span className="sr-only">· {stats.findingsCount} findings documented</span>
          </span>
        </span>
      </div>
    </header>
  )
}
