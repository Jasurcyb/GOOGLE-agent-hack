'use client'

import { useState } from 'react'
import { approveRecommendation } from '@/lib/api'

interface RecommendedTestsProps {
  tests: any[]
}

export default function RecommendedTests({ tests }: RecommendedTestsProps) {
  const [approving, setApproving] = useState<string | null>(null)

  if (!tests || tests.length === 0) {
    return (
      <div className="card">
        <h3 className="text-sm font-medium text-neutral-400 mb-2">Recommended Tests</h3>
        <p className="text-sm text-neutral-500">No test recommendations.</p>
      </div>
    )
  }

  const handleApprove = async (recId: string) => {
    setApproving(recId)
    try {
      await approveRecommendation(recId, 'reviewer')
    } finally {
      setApproving(null)
    }
  }

  return (
    <div className="card">
      <h3 className="text-sm font-medium text-neutral-400 mb-4">Recommended Tests ({tests.length})</h3>
      <div className="space-y-3">
        {tests.map((test, i) => (
          <div key={i} className="p-4 bg-neutral-900/50 rounded-lg border border-neutral-800">
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="px-2 py-0.5 text-xs bg-blue-500/20 text-blue-400 rounded">
                    {test.kind}
                  </span>
                  <span className="text-xs text-neutral-500">Priority {test.priority}</span>
                  {test.approval_required && (
                    <span className="px-2 py-0.5 text-xs bg-yellow-500/20 text-yellow-400 rounded">
                      Approval required
                    </span>
                  )}
                </div>
                <div className="text-sm font-medium">{test.title}</div>
                <div className="text-xs text-neutral-500 mt-1 font-mono">{test.target_path}</div>
                <div className="text-xs text-neutral-400 mt-2">{test.body}</div>
                {test.assertions?.length > 0 && (
                  <div className="mt-2">
                    <div className="text-xs text-neutral-600 mb-1">Assertions:</div>
                    <ul className="text-xs text-neutral-400 list-disc list-inside space-y-0.5">
                      {test.assertions.map((a: string, j: number) => <li key={j}>{a}</li>)}
                    </ul>
                  </div>
                )}
              </div>
              {test.approval_required && test.id && (
                <button
                  onClick={() => handleApprove(test.id)}
                  disabled={approving === test.id}
                  className="flex-shrink-0 px-3 py-1.5 text-xs bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
                >
                  {approving === test.id ? '...' : 'Approve'}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
