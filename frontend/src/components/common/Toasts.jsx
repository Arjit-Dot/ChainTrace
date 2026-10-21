import { X } from 'lucide-react'
import { useAlerts } from '../../hooks/useAlerts'
import { AlertLine, SEVERITY } from './AlertFeed'

// Live alerts pop up bottom-right in every open tab and fade after a few seconds.
export default function Toasts() {
  const { toasts, dismiss } = useAlerts()
  if (!toasts.length) return null
  return (
    <div className="pointer-events-none fixed right-5 bottom-5 z-50 flex w-96 flex-col gap-2" aria-live="polite">
      {toasts.map((a) => (
        <div
          key={a.id}
          role="status"
          className={`toast-in pointer-events-auto relative rounded-lg border border-l-4 border-line bg-panel px-4 py-3 pr-9 shadow-2xl ${(SEVERITY[a.severity] ?? SEVERITY.info).bar}`}
        >
          <AlertLine alert={a} onOpen={() => dismiss(a.id)} />
          <button onClick={() => dismiss(a.id)} title="Dismiss" className="absolute top-2.5 right-2.5 text-muted hover:text-ink">
            <X className="size-4" />
          </button>
        </div>
      ))}
    </div>
  )
}
