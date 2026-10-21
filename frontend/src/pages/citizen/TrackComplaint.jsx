import { Search } from 'lucide-react'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'

// Stage 1 placeholder: the lookup form is here, the status view arrives with the tracker (stage 3).
export default function TrackComplaint() {
  const [params, setParams] = useSearchParams()
  const [id, setId] = useState(params.get('id') ?? '')
  const asked = params.get('id')

  return (
    <div className="mx-auto max-w-xl space-y-5">
      <h1 className="text-2xl font-bold tracking-tight">Track a complaint</h1>
      <p className="text-sm text-muted">Enter the complaint ID you received when you reported the fraud.</p>
      <form
        onSubmit={(e) => {
          e.preventDefault()
          setParams(id.trim() ? { id: id.trim() } : {})
        }}
        className="flex gap-2"
      >
        <input
          value={id}
          onChange={(e) => setId(e.target.value)}
          placeholder="e.g. NCRP-2026-1234"
          aria-label="Complaint ID"
          className="w-full rounded-md border border-line bg-bg px-3 py-2 font-mono text-sm focus:border-accent focus:outline-none"
        />
        <button type="submit" className="inline-flex items-center gap-1.5 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-bg hover:bg-accent/90">
          <Search className="size-4" /> Track
        </button>
      </form>
      {asked && <p className="rounded-md border border-line bg-panel-2/60 px-3 py-2 text-sm text-muted">Status tracking for {asked} is switched on in the next release of this demo.</p>}
    </div>
  )
}
