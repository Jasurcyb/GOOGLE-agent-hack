'use client'

interface RiskScoreCardProps {
  assessment: any
}

export default function RiskScoreCard({ assessment }: RiskScoreCardProps) {
  if (!assessment) {
    return (
      <div className="card">
        <h3 className="text-sm font-medium text-neutral-400 mb-2">Risk Score</h3>
        <p className="text-sm text-neutral-500">No assessment available</p>
      </div>
    )
  }

  const score = assessment.risk_score || 0
  const circumference = 2 * Math.PI * 45
  const offset = circumference - (score / 100) * circumference

  return (
    <div className="card flex items-center gap-4">
      <div className="relative w-28 h-28">
        <svg className="w-28 h-28 transform -rotate-90">
          <circle cx="56" cy="56" r="45" stroke="#262626" strokeWidth="8" fill="none" />
          <circle
            cx="56" cy="56" r="45"
            stroke={score >= 80 ? '#ef4444' : score >= 60 ? '#f97316' : score >= 30 ? '#f59e0b' : '#22c55e'}
            strokeWidth="8" fill="none"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-2xl font-bold">{score}</span>
        </div>
      </div>
      <div className="space-y-1">
        <h3 className="text-sm font-medium text-neutral-400">Risk Score</h3>
        <div className="text-sm space-y-0.5">
          <div className="text-neutral-500">Probability: {(assessment.regression_probability * 100).toFixed(0)}%</div>
          <div className="text-neutral-500">Severity: {(assessment.impact_severity * 100).toFixed(0)}%</div>
          <div className="text-neutral-500">Confidence: {assessment.confidence}%</div>
        </div>
      </div>
    </div>
  )
}
