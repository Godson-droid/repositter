import raw from '../data.json'

export interface TriageReport {
  item_number: number
  item_kind: string
  title: string
  category: string
  priority: string
  summary: string
  suggested_labels: string[]
  suggested_next_action: string
}

export interface ScanItem {
  number: number
  status: 'triaged' | 'in-memory' | 'awaiting'
  title: string | null
  kind: string | null
  category: string | null
  priority: string | null
}

export interface ScheduledRun {
  id: string
  dir: string
  date: string
  title: string
  target: string
  command: string
  proves: string
}

export interface ExtraRun {
  dir: string
  runName: string
  target: string
  model: string
  startedAt: string | null
  seconds: number | null
  fetchedCount: number | null
  newItems: number[]
  alreadyTriaged: number[]
  reportCount: number
  relayRequests: number | null
  approvalHeld: boolean
  approvalResumed: boolean
}

export interface FindingBlock {
  t: 'p' | 'li'
  text: string
}

export interface Finding {
  id: string
  title: string
  blocks: FindingBlock[]
}

export interface BuildingBlock {
  block: string
  usage: string
  result: string
  evidence: string
}

export interface MemoryRecord {
  id: string
  scope: string
  type: string
  key: string
  content: string
}

export interface DoctorWarn {
  status: string
  name: string
  detail: string
  remediation: string | null
}

export interface SiteData {
  meta: {
    target: string
    targetUrl: string
    scratch: string
    scratchUrl: string
    model: string
    sdk: string
    eventUrl: string
    deadline: string
  }
  stats: {
    itemsScanned: number
    itemsTriaged: number
    memoryRecords: number
    relayRequests: number
    dailyCap: number
    findingsCount: number
    blocksTested: number
  }
  featuredReport: TriageReport | null
  reports: TriageReport[]
  items: ScanItem[]
  latestScanSource: string | null
  run00: {
    dir: string
    runName: string
    target: string
    model: string
    startedAt: string
    seconds: number
    fetchedCount: number
    newItems: number[]
    alreadyTriaged: number[]
    scanRunId: string | null
    classifyRunIds: string[]
    recordRunId: string | null
    scanNotes: string
  } | null
  failedRun: {
    dir: string
    runName: string
    target: string
    startedAt: string
    seconds: number
    error: string
    relayRequests: number | null
  } | null
  probeScan: {
    fetchedCount: number
    newItems: number[]
    alreadyTriaged: number[]
    notes: string
  } | null
  extraRuns: ExtraRun[]
  scheduledRuns: ScheduledRun[]
  memory: { store: string | null; queried: string | null; records: MemoryRecord[] }
  doctor: { ok: number; warn: number; total: number; warns: DoctorWarn[] }
  relay: {
    totalEntries: number
    chatCompletions: number
    other: { method: string; path: string; status: number }[]
    allOk: boolean
    models: string[]
    avgSeconds: number | null
    minSeconds: number | null
    maxSeconds: number | null
  }
  findings: Finding[]
  buildingBlocks: BuildingBlock[]
  pendingNote: string
}

export const data = raw as unknown as SiteData

/** "2026-11-15T11:57:07Z" -> "15 Nov 2026 · 11:57 UTC" */
export function fmtDateTime(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  const hh = String(d.getUTCHours()).padStart(2, '0')
  const mm = String(d.getUTCMinutes()).padStart(2, '0')
  return `${d.getUTCDate()} ${months[d.getUTCMonth()]} ${d.getUTCFullYear()} · ${hh}:${mm} UTC`
}

/** "2026-11-16" -> "Mon 16 Nov 2026" */
export function fmtDay(iso: string): string {
  const d = new Date(`${iso}T12:00:00Z`)
  if (Number.isNaN(d.getTime())) return iso
  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  return `${days[d.getUTCDay()]} ${d.getUTCDate()} ${months[d.getUTCMonth()]} ${d.getUTCFullYear()}`
}

export function shortId(id: string | null, head = 8): string {
  if (!id) return ''
  return id.length > head + 4 ? `${id.slice(0, head)}…${id.slice(-4)}` : id
}
