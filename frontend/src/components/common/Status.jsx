import { AlertTriangle, Inbox, Loader2 } from 'lucide-react'

// Loading / error / empty states, so no page is ever blank.
export function Loading({ label = 'Loading…' }) {
  return (
    <div className="flex items-center gap-2 p-6 text-sm text-muted">
      <Loader2 className="size-4 animate-spin" /> {label}
    </div>
  )
}

export function ErrorState({ error, onRetry }) {
  return (
    <div className="m-6 flex items-start gap-3 rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
      <AlertTriangle className="mt-0.5 size-4 shrink-0" />
      <div className="flex-1">
        <p className="font-semibold">Something went wrong</p>
        <p className="opacity-80">{error?.message ?? String(error)}</p>
      </div>
      {onRetry && (
        <button onClick={onRetry} className="rounded border border-red-400/40 px-2 py-1 text-xs hover:bg-red-500/20">
          Retry
        </button>
      )}
    </div>
  )
}

export function Empty({ children = 'Nothing here yet.' }) {
  return (
    <div className="flex items-center gap-2 p-6 text-sm text-muted">
      <Inbox className="size-4" /> {children}
    </div>
  )
}
