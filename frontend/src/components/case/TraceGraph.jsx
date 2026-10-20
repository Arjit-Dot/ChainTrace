import cytoscape from 'cytoscape'
import dagre from 'cytoscape-dagre'
import { Maximize2 } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { nodeColor } from '../../lib/colors'
import { formatAmount, shortAddr } from '../../lib/format'

cytoscape.use(dagre)

const SHAPES = {
  victim: 'ellipse',
  scam_wallet: 'ellipse',
  intermediary: 'ellipse',
  bridge: 'diamond',
  mixer: 'hexagon',
  exchange: 'round-rectangle',
  unknown: 'ellipse',
}

const STYLE = [
  {
    selector: 'node',
    style: {
      'background-color': 'data(color)',
      shape: 'data(shape)',
      width: 34,
      height: 34,
      label: 'data(label)',
      color: '#cbd5e1',
      'font-size': 10,
      'text-wrap': 'wrap',
      'text-max-width': 120,
      'text-valign': 'bottom',
      'text-margin-y': 6,
      'border-width': 2,
      'border-color': '#0b0f17',
    },
  },
  { selector: 'node[type = "exchange"]', style: { width: 44, height: 30 } },
  { selector: 'node[?idle]', style: { 'border-width': 4, 'border-color': '#fbbf24', 'border-style': 'double' } },
  { selector: 'node.reported', style: { width: 42, height: 42, 'border-color': '#fca5a5', 'border-width': 3 } },
  {
    selector: 'edge',
    style: {
      width: 'data(width)',
      'line-color': '#475569',
      'target-arrow-color': '#475569',
      'target-arrow-shape': 'triangle',
      'arrow-scale': 0.8,
      'curve-style': 'bezier',
      label: 'data(label)',
      'font-size': 9,
      color: '#94a3b8',
      'text-background-color': '#0b0f17',
      'text-background-opacity': 0.85,
      'text-background-padding': 2,
      'text-rotation': 'autorotate',
    },
  },
  { selector: 'edge[edge_type = "bridge"], edge[edge_type = "mixer_in"]', style: { 'line-style': 'dashed' } },
  { selector: 'edge[edge_type = "bridge"]', style: { 'line-color': '#3b82f6', 'target-arrow-color': '#3b82f6' } },
  { selector: 'edge[edge_type = "mixer_in"]', style: { 'line-color': '#a855f7', 'target-arrow-color': '#a855f7' } },
  {
    selector: '.vasp-path',
    style: { 'line-color': '#22c55e', 'target-arrow-color': '#22c55e', 'z-index': 10, color: '#86efac' },
  },
  { selector: 'node.vasp-path', style: { 'border-color': '#22c55e', 'border-width': 4 } },
  { selector: 'node.picked', style: { 'border-color': '#f8fafc', 'border-width': 4, 'overlay-opacity': 0 } },
]

function toElements(graph, wallet) {
  const max = Math.max(...graph.edges.map((e) => e.amount), 1)
  const nodes = graph.nodes.map((n) => ({
    data: {
      id: n.id,
      type: n.type,
      color: nodeColor(n.type),
      shape: SHAPES[n.type] ?? 'ellipse',
      idle: n.idle_balance > 0,
      label: `${n.label ?? n.type}${n.chain !== 'tron' ? ` (${n.chain})` : ''}\n${shortAddr(n.id)}`,
    },
    classes: n.id === wallet ? 'reported' : '',
  }))
  const edges = graph.edges.map((e, i) => ({
    data: {
      id: `e${i}`,
      source: e.source,
      target: e.target,
      edge_type: e.edge_type,
      width: 1.5 + 6 * Math.sqrt(e.amount / max),
      label: formatAmount(e.amount),
    },
  }))
  return [...nodes, ...edges]
}

// Fund-flow graph: left-to-right by hop, colored by node type, edge width by amount,
// green path from the reported wallet to the Nearest VASP deposit address.
export default function TraceGraph({ trace, selected, onSelect }) {
  const box = useRef(null)
  const cyRef = useRef(null)
  const onSelectRef = useRef(onSelect)
  onSelectRef.current = onSelect

  useEffect(() => {
    const cy = cytoscape({
      container: box.current,
      elements: toElements(trace.graph, trace.wallet),
      style: STYLE,
      layout: { name: 'dagre', rankDir: 'LR', nodeSep: 55, rankSep: 150, padding: 30 },
      minZoom: 0.3,
      maxZoom: 2.5,
    })

    const deposit = trace.nearest_vasp?.deposit_address
    if (deposit) {
      const path = cy.elements().aStar({
        root: cy.getElementById(trace.wallet),
        goal: cy.getElementById(deposit),
        directed: true,
      })
      if (path.found) path.path.addClass('vasp-path')
    }

    cy.on('tap', 'node', (e) => onSelectRef.current(e.target.id()))
    cy.on('tap', (e) => e.target === cy && onSelectRef.current(null))
    cyRef.current = cy
    return () => cy.destroy()
  }, [trace])

  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.nodes().removeClass('picked')
    if (selected) cy.getElementById(selected).addClass('picked')
  }, [selected, trace])

  return (
    <div className="relative h-full w-full">
      <div ref={box} className="h-full w-full" />
      <button
        onClick={() => cyRef.current?.fit(undefined, 30)}
        title="Fit graph"
        className="absolute top-2 right-2 rounded-md border border-line bg-panel-2/80 p-1.5 text-muted hover:text-ink"
      >
        <Maximize2 className="size-4" />
      </button>
    </div>
  )
}
