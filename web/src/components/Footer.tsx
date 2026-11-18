import { data } from '../lib/data'
import { ExtLink, LogoMark } from './ui'

export function Footer() {
  const { meta } = data
  return (
    <footer className="border-t border-line">
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-10 md:flex-row md:items-start md:justify-between">
          <div className="max-w-md">
            <div className="flex items-center gap-3">
              <LogoMark size={30} />
              <span className="font-display text-[16px] font-semibold text-moon-100">RepoSitter</span>
            </div>
            <p className="mt-4 text-dense leading-relaxed text-moon-400">
              Built by Godson for Cortensor Hackathon #5. Submission deadline {meta.deadline},
              Pacific Time.
            </p>
            <p className="mt-3 text-dense leading-relaxed text-moon-400">
              Every number on this page is generated from the committed run artifacts in{' '}
              <span className="font-mono text-moon-300">runs/</span> by{' '}
              <span className="font-mono text-moon-300">web/scripts/build-data.mjs</span> — when the
              scheduled runs land, the same script refreshes this site with no code changes.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-x-14 gap-y-8 text-dense">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-moon-500">
                Project
              </p>
              <ul className="mt-3 space-y-2.5 text-moon-300">
                <li>
                  <ExtLink href={meta.targetUrl}>Target: {meta.target}</ExtLink>
                </li>
                <li>
                  <ExtLink href={meta.scratchUrl}>Scratch: {meta.scratch}</ExtLink>
                </li>
                <li>
                  <ExtLink href={meta.eventUrl}>Cortensor Hackathon #5</ExtLink>
                </li>
              </ul>
            </div>
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-moon-500">
                Stack
              </p>
              <ul className="mt-3 space-y-2.5 text-moon-300">
                <li>{meta.sdk} (Python)</li>
                <li>
                  <span className="font-mono text-[12.5px]">{meta.model}</span> via OpenRouter
                </li>
                <li>React · Vite · Tailwind — this page</li>
              </ul>
            </div>
          </div>
        </div>
        <div className="mt-10 flex flex-col gap-2 border-t border-line pt-6 text-small text-moon-500 sm:flex-row sm:items-center sm:justify-between">
          <p>Reads are free. Writes wait for a human.</p>
          <p className="font-mono text-[11.5px]">
            dashboard data: runs/ artifacts · no mock data · no tracking
          </p>
        </div>
      </div>
    </footer>
  )
}
