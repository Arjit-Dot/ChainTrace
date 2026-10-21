import cytoscape from 'cytoscape'
import dagre from 'cytoscape-dagre'
import { Maximize2 } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { NODE_COLORS } from '../../lib/colors'
import { shortAddr } from '../../lib/format'

cytoscape.use(dagre)

// Same legend as the trace graph: complaints are victims (grey), shared scammer wallets orange, exchanges green.
export const NETWORK_TYPES = {
  complaint: { color: NODE_COLORS.victim, label: 'Complaint', shape: 'round-rectangle' },
  wallet: { color: NODE_COLORS.intermediary, label: 'Shared wallet', shape: 'ellipse' },
  exchange: { color: NODE_COLORS.exchange, label: 'Exchange', shape: 'round-rectangle' },
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
      'text-max-width': 140,
      'text-valign': 'bottom',
      'text-margin-y': 6,
      'border-width': 2,
      'border-color': '#0b0f17',
    },
  },
  { selector: 'node[type = "complaint"]', style: { width: 40, height: 26 } },
  { selector: 'node[type = "exchange"]', style: { width: 46, height: 30 } },
  { selector: 'node[type = "complaint"]:active, node.hover', style: { 'border-color': '#f8fafc', 'overlay-opacity': 0 } },
  {
    selector: 'edge',
    style: {
      width: 2,
      'line-color': '#475569',
      'target-arrow-color': '#475569',
      'target-arrow-shape': 'triangle',
      'arrow-scale': 0.8,
      'curve-style': 'bezier',
    },
  },
  { selector: 'edge.to-exchange', style: { 'line-color': '#22c55e', 'target-arrow-color': '#22c55e' } },
]

function toElements(network) {
  const types = Object.fromEntries(network.nodes.map((n) => [n.id, n.type]))
  return [
    ...network.nodes.map((n) => ({
      data: {
        id: n.id,
        type: n.type,
        color: NETWORK_TYPES[n.type].color,
        shape: NETWORK_TYPES[n.type].shape,
        label: n.type === 'complaint' ? `${n.id}\n${n.label}` : n.type === 'wallet' ? `${n.label}\n${shortAddr(n.id)}` : n.label,
      },
    })),
    ...network.edges.map((e, i) => ({
      data: { id: `e${i}`, source: e.source, target: e.target },
      classes: types[e.target] === 'exchange' ? 'to-exchange' : '',
    })),
  ]
}

// Complaints -> the wallets they share -> the exchange those wallets pay into. Click a complaint to open it.
export default function NetworkGraph({ network, onOpenCase }) {
  const box = useRef(null)
  const cyRef = useRef(null)
  const openRef = useRef(onOpenCase)
  useEffect(() => {
    openRef.current = onOpenCase
  })

  useEffect(() => {
    const cy = cytoscape({
      container: box.current,
      elements: toElements(network),
      style: STYLE,
      layout: { name: 'dagre', rankDir: 'LR', nodeSep: 40, rankSep: 170, padding: 30 },
      minZoom: 0.3,
      maxZoom: 2.5,
    })
    cy.on('tap', 'node[type = "complaint"]', (e) => openRef.current(e.target.id()))
    cy.on('mouseover', 'node[type = "complaint"]', (e) => {
      e.target.addClass('hover')
      box.current.style.cursor = 'pointer'
    })
    cy.on('mouseout', 'node', (e) => {
      e.target.removeClass('hover')
      box.current.style.cursor = ''
    })
    cyRef.current = cy
    return () => cy.destroy()
  }, [network])

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
