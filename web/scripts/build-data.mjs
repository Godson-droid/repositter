#!/usr/bin/env node
/**
 * build-data.mjs — RepoSitter dashboard data pipeline.
 *
 * Reads the REAL run artifacts from the project root (../../) and emits
 * src/data.json. Every number on the site comes from these files:
 *
 *   repositter.toml                          target repo + pinned model
 *   requirements.txt                         SDK version pin
 *   FINDINGS.md                              building-blocks table, F1..F14, pending note
 *   runs/run-00-shakedown/summary.json       shakedown run + stage run IDs
 *   runs/run-00-shakedown/reports/*.json     typed triage reports
 *   runs/probe-scan/scan.json                latest full scan (25 items)
 *   runs/run-01-failed-chunked-relay/        the failed run kept as evidence
 *   runs/diagnostics/memory-records.txt      persistent memory dump
 *   runs/diagnostics/doctor.txt              `openminion doctor` output
 *   runs/relay.log                           every forwarded model request (JSONL)
 *
 * Runs 01, 02 and 03 land on 16/17 Nov 2026 (free-tier resets). When their
 * artifact directories appear (runs/run-01-openminion, runs/run-02-openminion,
 * runs/run-03-scratch), re-running this script folds them in as completed
 * runs and drops them from the scheduled list — no code changes needed.
 *
 * Usage: node scripts/build-data.mjs   (also runs as part of `npm run build`)
 */
import { existsSync, readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const webDir = join(dirname(fileURLToPath(import.meta.url)), '..')
const root = join(webDir, '..')
const runsDir = join(root, 'runs')

const readText = (p) => (existsSync(p) ? readFileSync(p, 'utf8') : null)
const readJSON = (p) => {
  const t = readText(p)
  if (!t) return null
  try {
    return JSON.parse(t)
  } catch {
    return null
  }
}
const stripMd = (s) => s.replace(/\*\*/g, '').replace(/`/g, '').trim()

/* ---------------------------------- config --------------------------------- */

const toml = readText(join(root, 'repositter.toml')) || ''
const targetOwner = (toml.match(/\[target\][\s\S]*?owner\s*=\s*"([^"]+)"/) || [])[1] || 'openminion'
const targetRepo = (toml.match(/\[target\][\s\S]*?repo\s*=\s*"([^"]+)"/) || [])[1] || 'openminion'
const model = (toml.match(/primary\s*=\s*"([^"]+)"/) || [])[1] || 'cohere/north-mini-code:free'
const requirements = readText(join(root, 'requirements.txt')) || ''
const sdkPin = (requirements.match(/openminion==([0-9.]+)/) || [])[1] || '0.1.21'

const SCRATCH = 'Godson-droid/repositter-scratch'

/* --------------------------------- FINDINGS -------------------------------- */

const findingsMd = readText(join(root, 'FINDINGS.md')) || ''

// Building blocks table
const buildingBlocks = []
{
  const section = findingsMd.split('## Building blocks tested')[1]?.split('\n## ')[0] || ''
  const rows = section
    .split('\n')
    .filter((l) => l.trim().startsWith('|'))
    .slice(2) // header + separator
  for (const row of rows) {
    const cells = row.split('|').slice(1, -1).map((c) => stripMd(c))
    if (cells.length >= 4) {
      buildingBlocks.push({ block: cells[0], usage: cells[1], result: cells[2], evidence: cells[3] })
    }
  }
}

// Findings F1..F14 -> { id, title, blocks: [{t:'p'|'li', text}] }
function mdBlocks(body) {
  const blocks = []
  for (const raw of body.split('\n')) {
    const line = raw.trim()
    if (!line) continue
    if (line.startsWith('- ')) {
      blocks.push({ t: 'li', text: stripMd(line.slice(2)) })
    } else if (/^\d+\.\s/.test(line)) {
      blocks.push({ t: 'li', text: stripMd(line.replace(/^\d+\.\s/, '')) })
    } else if (blocks.length) {
      blocks[blocks.length - 1].text += ' ' + stripMd(line)
    } else {
      blocks.push({ t: 'p', text: stripMd(line) })
    }
  }
  return blocks
}

const findings = []
{
  const section = findingsMd.split('\n## Findings')[1]?.split('\n## Pending')[0] || ''
  const parts = section.split(/\n### (F\d+)\.\s+/)
  // parts: [prelude, id, title+body, id, title+body, ...]
  for (let i = 1; i < parts.length; i += 2) {
    const id = parts[i]
    const chunk = parts[i + 1] || ''
    const nl = chunk.indexOf('\n')
    const title = stripMd(nl === -1 ? chunk : chunk.slice(0, nl))
    const body = nl === -1 ? '' : chunk.slice(nl + 1)
    findings.push({ id, title, blocks: mdBlocks(body) })
  }
  findings.sort((a, b) => parseInt(a.id.slice(1)) - parseInt(b.id.slice(1)))
}

const pendingNote = (() => {
  const section = findingsMd.split('## Pending at the time of writing')[1] || ''
  const blocks = mdBlocks(section)
  return blocks.length ? blocks.map((b) => b.text).join(' ') : ''
})()

/* ------------------------------ run artifacts ------------------------------ */

function reportsIn(dir) {
  const reportsDir = join(dir, 'reports')
  if (!existsSync(reportsDir)) return []
  return readdirSync(reportsDir)
    .filter((f) => f.endsWith('.json'))
    .sort()
    .map((f) => readJSON(join(reportsDir, f)))
    .filter(Boolean)
}

const run00Dir = join(runsDir, 'run-00-shakedown')
const run00Summary = readJSON(join(run00Dir, 'summary.json'))
const run00Scan = readJSON(join(run00Dir, 'scan.json'))
const run00Reports = reportsIn(run00Dir)
const run00 = run00Summary
  ? {
      dir: 'run-00-shakedown',
      runName: run00Summary.run_name,
      target: run00Summary.target,
      model: run00Summary.model,
      startedAt: run00Summary.started_at,
      seconds: run00Summary.seconds,
      fetchedCount: run00Summary.fetched_count,
      newItems: run00Summary.new_item_numbers || [],
      alreadyTriaged: run00Summary.already_triaged_numbers || [],
      scanRunId: run00Summary.stages?.scan?.run_id || null,
      classifyRunIds: (run00Summary.stages?.classify || []).map((c) => c.run_id),
      recordRunId: run00Summary.stages?.record?.run_id || null,
      scanNotes: run00Scan?.notes || '',
    }
  : null

const failedDir = join(runsDir, 'run-01-failed-chunked-relay')
const failedSummary = readJSON(join(failedDir, 'summary.json'))
const failedRun = failedSummary
  ? {
      dir: 'run-01-failed-chunked-relay',
      runName: failedSummary.run_name,
      target: failedSummary.target,
      startedAt: failedSummary.started_at,
      seconds: failedSummary.seconds,
      error: failedSummary.stages?.scan?.error || 'ProviderError: EMPTY_PROVIDER_RESPONSE',
      relayRequests: failedSummary.relay_requests_delta ?? failedSummary.stages?.scan?.relay_requests ?? null,
    }
  : null

const probeScanRaw = readJSON(join(runsDir, 'probe-scan', 'scan.json'))
const probeScan = probeScanRaw
  ? {
      fetchedCount: probeScanRaw.fetched_count,
      newItems: probeScanRaw.new_item_numbers || [],
      alreadyTriaged: probeScanRaw.already_triaged_numbers || [],
      notes: probeScanRaw.notes || '',
    }
  : null

// Future / generic completed runs: any runs/<dir> with summary.json that is
// not one of the hand-modelled artifacts above.
const HANDLED = new Set(['run-00-shakedown', 'run-01-failed-chunked-relay', 'probe-scan', 'diagnostics'])
const extraRuns = []
if (existsSync(runsDir)) {
  for (const dir of readdirSync(runsDir).sort()) {
    if (HANDLED.has(dir)) continue
    const dirPath = join(runsDir, dir)
    const summary = readJSON(join(dirPath, 'summary.json'))
    if (!summary) continue
    extraRuns.push({
      dir,
      runName: summary.run_name || dir,
      target: summary.target || `${targetOwner}/${targetRepo}`,
      model: summary.model || model,
      startedAt: summary.started_at || null,
      seconds: summary.seconds ?? null,
      fetchedCount: summary.fetched_count ?? null,
      newItems: summary.new_item_numbers || [],
      alreadyTriaged: summary.already_triaged_numbers || [],
      reportCount: reportsIn(dirPath).length || (summary.reports || []).length,
      relayRequests: summary.relay_requests_delta ?? null,
      approvalHeld: existsSync(join(dirPath, 'approval_held.json')),
      approvalResumed: existsSync(join(dirPath, 'approval_resumed.json')),
      scan: readJSON(join(dirPath, 'scan.json')),
    })
  }
  extraRuns.sort((a, b) => String(a.startedAt).localeCompare(String(b.startedAt)))
}

// All typed reports for the MAIN target repo, keyed by item number (file
// artifacts win over summaries). Runs against other repos (the scratch-repo
// gate proof) appear in the timeline but never enter the main ledger —
// their issue numbers live in a different repo's namespace.
const MAIN_TARGET = `${targetOwner}/${targetRepo}`
const mainRuns = extraRuns.filter((r) => r.target === MAIN_TARGET)
const reportsByNumber = {}
for (const r of run00Reports) reportsByNumber[r.item_number] = r
for (const run of mainRuns) {
  for (const r of reportsIn(join(runsDir, run.dir))) reportsByNumber[r.item_number] = r
}
if (run00Summary?.reports) {
  for (const r of run00Summary.reports) {
    if (!reportsByNumber[r.item_number]) reportsByNumber[r.item_number] = r
  }
}
for (const run of mainRuns) {
  const s = readJSON(join(runsDir, run.dir, 'summary.json'))
  for (const r of s?.reports || []) {
    if (!reportsByNumber[r.item_number]) reportsByNumber[r.item_number] = r
  }
}

/* ------------------------------ scanned items ------------------------------ */

// Scan snapshots in chronological order; the latest defines the item universe.
const snapshots = []
if (run00Scan) {
  snapshots.push({
    source: 'run-00-shakedown',
    fetched: run00Scan.fetched_count,
    newItems: run00Scan.new_item_numbers || [],
    already: run00Scan.already_triaged_numbers || [],
  })
}
if (probeScan) {
  snapshots.push({ source: 'probe-scan', fetched: probeScan.fetchedCount, newItems: probeScan.newItems, already: probeScan.alreadyTriaged })
}
for (const run of mainRuns) {
  if (run.scan) {
    snapshots.push({
      source: run.dir,
      fetched: run.scan.fetched_count ?? run.fetchedCount,
      newItems: run.scan.new_item_numbers || run.newItems,
      already: run.scan.already_triaged_numbers || run.alreadyTriaged,
    })
  } else if (run.fetchedCount != null) {
    snapshots.push({ source: run.dir, fetched: run.fetchedCount, newItems: run.newItems, already: run.alreadyTriaged })
  }
}
const latestScan = snapshots[snapshots.length - 1] || { fetched: 0, newItems: [], already: [] }
const everInMemory = new Set(snapshots.flatMap((s) => s.already))
const universe = [...new Set([...latestScan.already, ...latestScan.newItems])]
const items = universe
  .map((n) => {
    const report = reportsByNumber[n]
    return {
      number: n,
      status: report ? 'triaged' : everInMemory.has(n) ? 'in-memory' : 'awaiting',
      title: report?.title || null,
      kind: report?.item_kind || null,
      category: report?.category || null,
      priority: report?.priority || null,
    }
  })
  .sort((a, b) => b.number - a.number)

/* ------------------------------ memory records ----------------------------- */

const memoryDump = (() => {
  const text = readText(join(runsDir, 'diagnostics', 'memory-records.txt')) || ''
  const lines = text.split('\n').filter((l) => l.trim())
  const header = lines.find((l) => l.startsWith('Memory store:')) || ''
  const store = (header.match(/Memory store:\s*(\S+)/) || [])[1] || null
  const queried = (header.match(/queried\s+([0-9-]+)\)/) || [])[1] || null
  const records = lines
    .filter((l) => l.includes('|'))
    .map((l) => {
      const parts = l.split('|')
      return {
        id: parts[0]?.trim(),
        scope: parts[1]?.trim(),
        type: parts[2]?.trim(),
        key: parts[3]?.trim(),
        content: (parts.slice(4).join('|').trim() || '').replace(/^"|"$/g, ''),
      }
    })
    .filter((r) => r.id)
  return { store, queried, records }
})()

/* --------------------------------- doctor ---------------------------------- */

const doctor = (() => {
  const text = readText(join(runsDir, 'diagnostics', 'doctor.txt')) || ''
  const sanitize = (s) =>
    s.replaceAll('/home/hatch/workspace/cortensor/repositter/', '').replaceAll('/home/hatch/', '~/')
  const checks = []
  for (const raw of text.split('\n')) {
    const m = raw.match(/^\[(OK|WARN)\]\s+([^:]+):\s*(.*)$/)
    if (m) {
      checks.push({ status: m[1], name: m[2].trim(), detail: sanitize(m[3].trim()), remediation: null })
    } else if (/^\s+remediation:/.test(raw) && checks.length) {
      checks[checks.length - 1].remediation = sanitize(raw.replace(/^\s+remediation:\s*/, '').trim())
    }
  }
  return {
    ok: checks.filter((c) => c.status === 'OK').length,
    warn: checks.filter((c) => c.status === 'WARN').length,
    total: checks.length,
    warns: checks.filter((c) => c.status === 'WARN'),
    checks,
  }
})()

/* ---------------------------------- relay ---------------------------------- */

const relay = (() => {
  const text = readText(join(runsDir, 'relay.log')) || ''
  const entries = text
    .split('\n')
    .filter((l) => l.trim())
    .map((l) => {
      try {
        return JSON.parse(l)
      } catch {
        return null
      }
    })
    .filter(Boolean)
  const chat = entries.filter((e) => e.path === '/v1/chat/completions')
  const secs = chat.map((e) => e.seconds).filter((n) => typeof n === 'number')
  return {
    totalEntries: entries.length,
    chatCompletions: chat.length,
    other: entries
      .filter((e) => e.path !== '/v1/chat/completions')
      .map((e) => ({ method: e.method, path: e.path, status: e.status })),
    allOk: entries.every((e) => e.status === 200),
    models: [...new Set(chat.map((e) => e.model))],
    avgSeconds: secs.length ? Math.round((secs.reduce((a, b) => a + b, 0) / secs.length) * 100) / 100 : null,
    minSeconds: secs.length ? Math.min(...secs) : null,
    maxSeconds: secs.length ? Math.max(...secs) : null,
  }
})()

/* ----------------------------- scheduled runs ------------------------------ */

const SCHEDULED = [
  {
    id: 'run-01',
    dir: 'run-01-openminion',
    date: '2026-11-16',
    title: 'Fresh triage, gate held',
    target: 'openminion/openminion',
    command: 'run.py --run-name run-01-openminion --max-items 2',
    proves:
      'Two fresh items triaged end to end, and the propose stage leaves its GitHub write held at the approval gate: an approval_held.json artifact, and nothing written anywhere.',
  },
  {
    id: 'run-02',
    dir: 'run-02-openminion',
    date: '2026-11-16',
    title: 'Memory skip proof',
    target: 'openminion/openminion',
    command: 'run.py --run-name run-02-openminion',
    proves:
      'A second full run over the same repository reports every item as already triaged from persistent memory. No reclassification, no wasted model requests.',
  },
  {
    id: 'run-03',
    dir: 'run-03-scratch',
    date: '2026-11-17',
    title: 'Approval gate, executed',
    target: SCRATCH,
    command: 'run.py --target Godson-droid/repositter-scratch --run-name run-03-scratch --max-items 1 --approve-write',
    proves:
      'The same gate, this time approved. The run resumes on its own thread, the label lands on a scratch repo issue, and an API read-back verifies it. This repository publishes the same day.',
  },
]
const completedDirs = new Set(extraRuns.map((r) => r.dir))
const scheduledRuns = SCHEDULED.filter((s) => !completedDirs.has(s.dir))

/* ---------------------------------- emit ----------------------------------- */

const data = {
  meta: {
    target: `${targetOwner}/${targetRepo}`,
    targetUrl: `https://github.com/${targetOwner}/${targetRepo}`,
    scratch: SCRATCH,
    scratchUrl: `https://github.com/${SCRATCH}`,
    model,
    sdk: `openminion ${sdkPin}`,
    eventUrl: 'https://dorahacks.io/hackathon/2418/detail',
    deadline: '18 Dec 2026',
  },
  stats: {
    itemsScanned: latestScan.fetched ?? 0,
    itemsTriaged: Object.keys(reportsByNumber).length,
    memoryRecords: memoryDump.records.length,
    relayRequests: relay.chatCompletions,
    dailyCap: 50,
    findingsCount: findings.length,
    blocksTested: buildingBlocks.length,
  },
  featuredReport: reportsByNumber[759] || Object.values(reportsByNumber)[0] || null,
  reports: Object.values(reportsByNumber).sort((a, b) => b.item_number - a.item_number),
  items,
  latestScanSource: latestScan.source || null,
  run00,
  failedRun,
  probeScan,
  extraRuns,
  scheduledRuns,
  memory: memoryDump,
  doctor: { ok: doctor.ok, warn: doctor.warn, total: doctor.total, warns: doctor.warns },
  relay,
  findings,
  buildingBlocks,
  pendingNote,
}

writeFileSync(join(webDir, 'src', 'data.json'), JSON.stringify(data, null, 2) + '\n')
console.log(
  `data.json written: ${items.length} items, ${Object.keys(reportsByNumber).length} reports, ` +
    `${findings.length} findings, ${buildingBlocks.length} blocks, ${relay.chatCompletions} relay requests, ` +
    `${extraRuns.length} extra runs folded in, ${scheduledRuns.length} runs still scheduled.`,
)
