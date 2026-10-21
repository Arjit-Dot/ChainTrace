import { RISK_CLASSES, SOURCE_CLASSES, STAGES, URGENCY } from "../../lib/colors";

const pill =
  "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset";

export function RiskBadge({ risk, score }) {
  if (!risk) return null;
  return (
    <span className={`${pill} ${RISK_CLASSES[risk] ?? RISK_CLASSES.Low}`}>
      {risk}
      {score != null && (
        <span className="font-normal opacity-80">{score.toFixed(2)}</span>
      )}
    </span>
  );
}

// The reported wallet is not scored (a victim already named it), so it shows "Reported" instead of a risk.
export function ReportedBadge() {
  return (
    <span
      className={`${pill} bg-slate-500/15 text-slate-300 ring-slate-500/40`}
    >
      Reported
    </span>
  );
}

// Case urgency with the triggers that fired, so an officer can see why.
export function UrgencyBadge({ urgency, reasons = [] }) {
  const u = URGENCY[urgency];
  if (!u) return null;
  return (
    <span className={`${pill} ${u.classes}`} title={reasons.join("\n")}>
      {u.label}
    </span>
  );
}

export function StageBadge({ stage }) {
  const s = STAGES[stage]
  return s ? <span className={`${pill} ${s.classes}`}>{s.label}</span> : null
}

// Live monitoring: LIVE (checked recently), STALE (last check older than ~2 poll intervals), or OFF.
const MONITOR = {
  live: { text: "Live", dot: "bg-emerald-400", cls: "text-emerald-300" },
  stale: { text: "Stale", dot: "bg-amber-400", cls: "text-amber-300" },
  off: { text: "Monitoring off", dot: "bg-slate-500", cls: "text-slate-400" },
};

export function MonitorIndicator({ monitoring }) {
  const m = MONITOR[monitoring?.status];
  if (!m) return null;
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs font-medium ${m.cls}`}
    >
      <span
        className={`size-2 rounded-full ${m.dot} ${monitoring.status === "live" ? "animate-pulse" : ""}`}
      />
      {m.text}
    </span>
  );
}

// Every result surface shows where its data came from: LIVE / CACHED / SIMULATED.
export function SourceBadge({ source }) {
  if (!source) return null;
  return (
    <span
      className={`${pill} tracking-wider uppercase ${SOURCE_CLASSES[source] ?? SOURCE_CLASSES.simulated}`}
    >
      {source}
    </span>
  );
}
