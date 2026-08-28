'use client'

import { useEffect, useRef } from 'react'
import cytoscape from 'cytoscape'

interface ImpactGraphProps {
  nodes: any[]
  edges: any[]
}

const NODE_COLORS: Record<string, string> = {
  CODE_SYMBOL: '#3b82f6',
  DATASET: '#22c55e',
  DASHBOARD: '#a855f7',
  DATA_JOB: '#f59e0b',
  ML_MODEL: '#ec4899',
  ML_FEATURE: '#06b6d4',
  OWNER: '#6b7280',
  REPORT: '#8b5cf6',
}

export default function ImpactGraph({ nodes, edges }: ImpactGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const cyElements = [
      ...nodes.map((n: any) => ({
        data: {
          id: n.id || n.node_key,
          label: n.urn ? n.urn.split(':').pop() : n.id,
          kind: n.kind || n.node_kind,
          criticality: n.criticality || 0,
          distance: n.distance || 0,
        },
      })),
      ...edges.map((e: any) => ({
        data: {
          id: `${e.source || e.from_node}->${e.target || e.to_node}`,
          source: e.source || e.from_node,
          target: e.target || e.to_node,
          kind: e.kind || e.edge_kind,
        },
      })),
    ]

    cyRef.current = cytoscape({
      container: containerRef.current,
      elements: cyElements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': (ele: any) => NODE_COLORS[ele.data('kind')] || '#6b7280',
            'label': 'data(label)',
            'color': '#e5e5e5',
            'font-size': '10px',
            'width': (ele: any) => 30 + ele.data('criticality') * 20,
            'height': (ele: any) => 30 + ele.data('criticality') * 20,
            'text-valign': 'bottom',
            'text-margin-y': 4,
          },
        },
        {
          selector: 'edge',
          style: {
            'width': 2,
            'line-color': '#404040',
            'target-arrow-color': '#404040',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
          },
        },
      ],
      layout: {
        name: 'cose',
        animate: true,
        nodeRepulsion: 8000,
        idealEdgeLength: 100,
      },
    })

    return () => {
      cyRef.current?.destroy()
    }
  }, [nodes, edges])

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height: '400px', background: '#0a0a0a', borderRadius: '0.5rem' }}
    />
  )
}
