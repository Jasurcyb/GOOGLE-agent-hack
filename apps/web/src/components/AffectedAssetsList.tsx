'use client'

interface AffectedAssetsListProps {
  assets: any[]
}

const TYPE_ICONS: Record<string, string> = {
  DATASET: 'DB',
  DASHBOARD: 'DW',
  DATA_JOB: 'JOB',
  ML_MODEL: 'ML',
  ML_FEATURE: 'FT',
  REPORT: 'RP',
}

export default function AffectedAssetsList({ assets }: AffectedAssetsListProps) {
  if (!assets || assets.length === 0) {
    return (
      <div className="card">
        <h3 className="text-sm font-medium text-neutral-400 mb-2">Affected Assets</h3>
        <p className="text-sm text-neutral-500">No verified business impact detected.</p>
      </div>
    )
  }

  return (
    <div className="card">
      <h3 className="text-sm font-medium text-neutral-400 mb-4">Affected Assets ({assets.length})</h3>
      <div className="space-y-2">
        {assets.map((asset, i) => (
          <div key={i} className="flex items-start gap-3 p-3 bg-neutral-900/50 rounded-lg">
            <div className="flex-shrink-0 w-10 h-10 flex items-center justify-center bg-neutral-800 rounded text-xs font-mono">
              {TYPE_ICONS[asset.type] || '??'}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-mono truncate">{asset.urn}</div>
              <div className="text-xs text-neutral-500 mt-0.5">{asset.impact}</div>
              <div className="flex gap-3 mt-1 text-xs text-neutral-600">
                <span>Distance: {asset.distance}</span>
                {asset.evidence_refs?.length > 0 && (
                  <span>Evidence: {asset.evidence_refs.length} refs</span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
