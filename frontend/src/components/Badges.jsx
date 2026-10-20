import { RISK_CLASSES, SOURCE_CLASSES } from '../lib/colors'

const pill = 'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset'

export function RiskBadge({ risk, score }) {
  if (!risk) return null
  return (
    <span className={`${pill} ${RISK_CLASSES[risk] ?? RISK_CLASSES.Low}`}>
      {risk}
      {score != null && <span className="font-normal opacity-80">{score.toFixed(2)}</span>}
    </span>
  )
}

// Every result surface shows where its data came from: LIVE / CACHED / SIMULATED.
export function SourceBadge({ source }) {
  if (!source) return null
  return (
    <span className={`${pill} tracking-wider uppercase ${SOURCE_CLASSES[source] ?? SOURCE_CLASSES.simulated}`}>
      {source}
    </span>
  )
}
