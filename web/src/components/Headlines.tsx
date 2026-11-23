import { SectionHeading } from './ui'

const HEADLINES: string[] = [
  'One run costs far more model requests than its visible tool calls, about twelve requests for a four tool call scan stage.',
  'A run can return success while doing nothing at all, so stages are judged by tool call counts and read backs, never by the absence of an error.',
  'The Groq free tier token per minute limit is spent in seconds by the SDK helper call bursts; a token bucket pacer in the relay fixed it.',
  'The memctl CLI could not run in the standard layout; filed as issue 805, maintainer confirmed, fix delivered as pull request 815.',
  'Typed outputs are fragile with small free models; an orchestrator side salvage extracts the first balanced JSON object.',
  'An ingested skill is invisible until admitted, and nothing in the product says so.',
]

export function Headlines() {
  return (
    <section id="headlines" className="mx-auto max-w-7xl scroll-mt-24 px-4 py-14 sm:px-6 lg:px-8">
      <SectionHeading
        eyebrow="Headline findings"
        title="What building on the SDK taught us, in six lines"
        lede="The short version first. Each line below is one of the findings this build is judged on, expanded with its reproduction in the findings section further down this page and in FINDINGS.md in the project repo."
      />
      <div className="mt-10 overflow-hidden rounded-card border border-line bg-night-850/90 shadow-card">
        {HEADLINES.map((line, i) => (
          <div
            key={i}
            className="flex items-baseline gap-4 border-b border-line px-5 py-4 last:border-0 sm:px-6"
          >
            <span className="w-10 shrink-0 font-mono text-[13px] font-semibold text-iris-400">
              {String(i + 1).padStart(2, '0')}
            </span>
            <p className="flex-1 text-dense leading-relaxed text-moon-200">{line}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
