const API_BASE = '/api/v1'

export async function fetchRun(runId: string) {
  const res = await fetch(`${API_BASE}/runs/${runId}`)
  if (!res.ok) throw new Error(`Failed to fetch run: ${res.status}`)
  return res.json()
}

export async function fetchRunGraph(runId: string, view: string = 'impact') {
  const res = await fetch(`${API_BASE}/runs/${runId}/graph?view=${view}`)
  if (!res.ok) throw new Error(`Failed to fetch graph: ${res.status}`)
  return res.json()
}

export async function fetchLatestPR(repo: string, number: number) {
  const res = await fetch(`${API_BASE}/pull-requests/${repo}/${number}/latest`)
  if (!res.ok) return null
  return res.json()
}

export async function approveRecommendation(recId: string, approver: string) {
  const res = await fetch(`${API_BASE}/recommendations/${recId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approver }),
  })
  return res.json()
}

export async function overrideRisk(runId: string, auditor: string, reason: string) {
  const res = await fetch(`${API_BASE}/runs/${runId}/override`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ auditor, reason }),
  })
  return res.json()
}

export function riskColorClass(level: string): string {
  const map: Record<string, string> = {
    low: 'risk-low',
    medium: 'risk-medium',
    high: 'risk-high',
    critical: 'risk-critical',
  }
  return map[level] || 'risk-low'
}

export function riskBgClass(level: string): string {
  const map: Record<string, string> = {
    low: 'bg-green-500/10 border-green-500/30',
    medium: 'bg-yellow-500/10 border-yellow-500/30',
    high: 'bg-orange-500/10 border-orange-500/30',
    critical: 'bg-red-500/10 border-red-500/30',
  }
  return map[level] || 'bg-gray-500/10 border-gray-500/30'
}
