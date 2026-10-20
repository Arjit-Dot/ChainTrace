import { FileDown, FileWarning, Info } from 'lucide-react'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import Legend from '../components/Legend'
import NearestVaspCard from '../components/NearestVaspCard'
import NodePanel from '../components/NodePanel'
import PageHeader from '../components/PageHeader'
import RecommendationsPanel from '../components/RecommendationsPanel'
import { ErrorState, Loading } from '../components/Status'
import SummaryStrip from '../components/SummaryStrip'
import TraceGraph from '../components/TraceGraph'
import { useFetch } from '../hooks/useFetch'
import { getCase, reportUrl } from '../lib/api'
import { humanize, shortAddr } from '../lib/format'

const btn =
  'inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50'

function CaseBody({ trace }) {
  const [selected, setSelected] = useState(null)
  const node = selected && trace.graph.nodes.find((n) => n.id === selected)

  return (
    <>
      <PageHeader
        title={`Case ${trace.case_id}`}
        subtitle={`${trace.complaint_id} · ${humanize(trace.fraud_type)} · reported wallet ${shortAddr(trace.wallet, 8)}`}
      >
        {/* Freeze Notice modal is wired in B4 */}
        <button disabled title="Freeze notice arrives in B4" className={`${btn} border-emerald-500/50 text-emerald-300`}>
          <FileWarning className="size-4" /> Freeze Notice
        </button>
        <a href={reportUrl(trace.case_id)} className={`${btn} border-line text-ink hover:bg-panel-2`}>
          <FileDown className="size-4" /> Download Report
        </a>
      </PageHeader>

      <div className="space-y-6 p-6">
        <SummaryStrip trace={trace} />
        {trace.notes && (
          <p className="flex items-start gap-2 rounded-md border border-line bg-panel-2/60 px-3 py-2 text-xs text-muted">
            <Info className="mt-px size-3.5 shrink-0" /> {trace.notes}
          </p>
        )}

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
          <section className="flex flex-col self-start rounded-lg border border-line bg-panel">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2.5">
              <h2 className="text-sm font-semibold">Fund flow</h2>
              <Legend />
            </div>
            <div className="h-[520px]">
              <TraceGraph trace={trace} selected={selected} onSelect={setSelected} />
            </div>
            <p className="border-t border-line px-4 py-2 text-xs text-muted">
              Click a wallet for details. Green path = route to the Nearest VASP · dashed = bridge / mixer · amber ring =
              idle funds.
            </p>
          </section>

          <div className="space-y-6">
            {node ? (
              <NodePanel node={node} graph={trace.graph} onClose={() => setSelected(null)} />
            ) : (
              <NearestVaspCard
                vasp={trace.nearest_vasp}
                graph={trace.graph}
                onLocate={() => setSelected(trace.nearest_vasp.deposit_address)}
              />
            )}
          </div>
        </div>

        <RecommendationsPanel items={trace.recommendations} />
      </div>
    </>
  )
}

export default function CaseView() {
  const { id } = useParams()
  const { data, loading, error, reload } = useFetch(() => getCase(id), [id])

  if (loading) return <Loading label={`Loading ${id}…`} />
  if (error) return <ErrorState error={error} onRetry={reload} />
  return <CaseBody key={id} trace={data} />
}
