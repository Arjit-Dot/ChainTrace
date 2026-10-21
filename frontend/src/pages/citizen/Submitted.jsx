import { CheckCircle2 } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import CopyButton from '../../components/common/CopyButton'
import { R } from '../../lib/routes'

// Shown right after a complaint is filed. Only the complaint ID: nothing about how it will be handled.
export default function Submitted() {
  const { id } = useParams()
  return (
    <div className="mx-auto max-w-xl space-y-5 text-center">
      <CheckCircle2 className="mx-auto size-12 text-emerald-400" />
      <h1 className="text-2xl font-bold tracking-tight">Your complaint has been registered</h1>
      <p className="text-sm text-muted">Keep this complaint ID. You will need it to follow progress.</p>
      <div className="flex items-center justify-center gap-3 rounded-lg border border-line bg-panel px-5 py-4">
        <span className="font-mono text-xl font-semibold tracking-wide" data-testid="complaint-id">{id}</span>
        <CopyButton text={id} />
      </div>
      <div className="flex flex-wrap justify-center gap-3">
        <Link to={`${R.track}?id=${encodeURIComponent(id)}`} className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-bg hover:bg-accent/90">
          Track this complaint
        </Link>
        <Link to={R.gateway} className="rounded-md border border-line px-4 py-2 text-sm text-muted hover:text-ink">
          Back to home
        </Link>
      </div>
    </div>
  )
}
