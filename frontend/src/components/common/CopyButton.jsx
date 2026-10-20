import { Check, Copy } from 'lucide-react'
import { useState } from 'react'

export default function CopyButton({ text, className = '' }) {
  const [done, setDone] = useState(false)
  const copy = async () => {
    await navigator.clipboard.writeText(text)
    setDone(true)
    setTimeout(() => setDone(false), 1200)
  }
  return (
    <button
      onClick={copy}
      title="Copy"
      className={`shrink-0 text-muted hover:text-ink ${className}`}
    >
      {done ? <Check className="size-3.5 text-emerald-400" /> : <Copy className="size-3.5" />}
    </button>
  )
}
