import type { ReactNode } from 'react'

/** The RepoSitter mark: a watch ring with a settled point — the sitter's eye on the repo. */
export function LogoMark({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" className="shrink-0">
      <rect width="64" height="64" rx="14" fill="#0a0a0e" />
      <rect x="1" y="1" width="62" height="62" rx="13" fill="none" stroke="#2a2a35" strokeWidth="2" />
      <circle cx="32" cy="32" r="17" fill="none" stroke="#7c6cff" strokeWidth="4" />
      <circle cx="32" cy="32" r="6.5" fill="#7c6cff" />
      <circle cx="45" cy="19" r="3.5" fill="#34d399" />
    </svg>
  )
}

export function MicroLabel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <p className={`text-[11px] font-semibold uppercase tracking-[0.16em] text-moon-500 ${className}`}>
      {children}
    </p>
  )
}

export function SectionHeading({
  eyebrow,
  title,
  lede,
}: {
  eyebrow: string
  title: string
  lede?: string
}) {
  return (
    <div className="max-w-2xl">
      <MicroLabel className="text-iris-400">{eyebrow}</MicroLabel>
      <h2 className="mt-3 font-display text-h2 font-semibold text-moon-100">{title}</h2>
      {lede ? <p className="mt-3 text-[15px] leading-relaxed text-moon-300">{lede}</p> : null}
    </div>
  )
}

export function Card({
  children,
  className = '',
  id,
}: {
  children: ReactNode
  className?: string
  id?: string
}) {
  return (
    <div
      id={id}
      className={`rounded-card border border-line bg-night-850/90 shadow-card ${className}`}
    >
      {children}
    </div>
  )
}

type Tone = 'iris' | 'mint' | 'amber' | 'rose' | 'moon'

const toneClasses: Record<Tone, string> = {
  iris: 'border-iris-500/30 bg-iris-500/10 text-iris-300',
  mint: 'border-mint-500/30 bg-mint-500/10 text-mint-300',
  amber: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
  rose: 'border-rose-500/30 bg-rose-500/10 text-rose-300',
  moon: 'border-line bg-night-800 text-moon-300',
}

export function Chip({
  tone = 'moon',
  children,
  dot = false,
}: {
  tone?: Tone
  children: ReactNode
  dot?: boolean
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-1 text-[11px] font-semibold tracking-wide ${toneClasses[tone]}`}
    >
      {dot ? <span className="h-1.5 w-1.5 rounded-full bg-current" /> : null}
      {children}
    </span>
  )
}

export function LiveDot({ className = 'bg-mint-400' }: { className?: string }) {
  return (
    <span className="relative flex h-2 w-2">
      <span className={`absolute inline-flex h-full w-full animate-ping-soft rounded-full ${className}`} />
      <span className={`relative inline-flex h-2 w-2 rounded-full ${className}`} />
    </span>
  )
}

export function ExtLink({
  href,
  children,
  className = '',
}: {
  href: string
  children: ReactNode
  className?: string
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className={`inline-flex items-center gap-1 whitespace-nowrap transition-colors hover:text-iris-300 ${className}`}
    >
      {children}
      <svg width="11" height="11" viewBox="0 0 12 12" fill="none" aria-hidden="true" className="opacity-70">
        <path
          d="M3.5 2.5h6v6M9.5 2.5L2.5 9.5"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </a>
  )
}
