'use client'

import { useState } from 'react'
import { fetchRun, fetchRunGraph, riskColorClass, riskBgClass } from '@/lib/api'
import ImpactGraph from '@/components/ImpactGraph'
import RiskScoreCard from '@/components/RiskScoreCard'
import AffectedAssetsList from '@/components/AffectedAssetsList'
import RecommendedTests from '@/components/RecommendedTests'

export default function Dashboard() {
  const [runId, setRunId] = useState('')
  const [loading, setLoading] = useState(false)
  const [run, setRun] = useState<any>(null)
  const [graph, setGraph] = useState<any>(null)

  const handleFetch = async () => {
    if (!runId) return
    setLoading(true)
    try {
      const data = await fetchRun(runId)
      setRun(data)
      const g = await fetchRunGraph(runId)
      setGraph(g)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen p-6">
      <header className="mb-8">
        <h1 className="text-2xl font-bold">Regression Hunter AI</h1>
        <p className="text-sm text-neutral-500">Risk assessment & impact graph</p>
      </header>

      <div className="flex gap-2 mb-6">
        <input
          type="text"
          value={runId}
          onChange={(e) => setRunId(e.target.value)}
          placeholder="Enter Run ID..."
          className="flex-1 px-4 py-2 bg-neutral-900 border border-neutral-700 rounded-lg text-sm focus:outline-none focus:border-blue-500"
        />
        <button
          onClick={handleFetch}
          disabled={loading || !runId}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Loading...' : 'Load'}
        </button>
      </div>

      {run && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <RiskScoreCard assessment={run.risk_assessment} />
            <div className="card">
              <h3 className="text-sm font-medium text-neutral-400 mb-2">Run Info</h3>
              <dl className="space-y-1 text-sm">
                <div><dt className="inline text-neutral-500">Repository:</dt> <dd className="inline">{run.repository}</dd></div>
                <div><dt className="inline text-neutral-500">PR:</dt> <dd className="inline">#{run.pr_number}</dd></div>
                <div><dt className="inline text-neutral-500">SHA:</dt> <dd className="inline font-mono">{run.head_sha?.slice(0, 8)}</dd></div>
                <div><dt className="inline text-neutral-500">Status:</dt> <dd className="inline">{run.status}</dd></div>
              </dl>
            </div>
            <div className={`card border ${run.risk_assessment ? riskBgClass(run.risk_assessment.risk_level) : ''}`}>
              <h3 className="text-sm font-medium text-neutral-400 mb-2">Risk Level</h3>
              {run.risk_assessment ? (
                <div className="space-y-2">
                  <div className={`text-3xl font-bold ${riskColorClass(run.risk_assessment.risk_level)}`}>
                    {run.risk_assessment.risk_level.toUpperCase()}
                  </div>
                  <div className="text-sm text-neutral-500">
                    Score: {run.risk_assessment.risk_score}/100 | Confidence: {run.risk_assessment.confidence}%
                  </div>
                  {run.risk_assessment.requires_review && (
                    <div className="text-xs text-orange-400">Requires human review</div>
                  )}
                </div>
              ) : (
                <p className="text-sm text-neutral-500">No assessment yet</p>
              )}
            </div>
          </div>

          {graph && (
            <div className="card">
              <h3 className="text-sm font-medium text-neutral-400 mb-4">Impact Graph</h3>
              <ImpactGraph nodes={graph.nodes} edges={graph.edges} />
            </div>
          )}

          {run.risk_assessment?.affected_assets && (
            <AffectedAssetsList assets={run.risk_assessment.affected_assets} />
          )}

          {run.risk_assessment?.recommended_tests && (
            <RecommendedTests tests={run.risk_assessment.recommended_tests} />
          )}
        </div>
      )}

      {!run && !loading && (
        <div className="card text-center text-neutral-500">
          Enter a Run ID to view the regression analysis report.
        </div>
      )}
    </div>
  )
}
