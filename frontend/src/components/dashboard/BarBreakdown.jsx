import { Bar, BarChart, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { CHART } from '../../lib/colors'
import { formatUSDT, humanize } from '../../lib/format'

const MAX_ROWS = 7 // the tail folds into "Other"
const ROW_PX = 30

const fmt = (metric) => (v) => (metric === 'amount' ? formatUSDT(v) : `${v} case${v === 1 ? '' : 's'}`)

function fold(items) {
  if (items.length <= MAX_ROWS) return items
  const head = items.slice(0, MAX_ROWS - 1)
  const tail = items.slice(MAX_ROWS - 1)
  return [
    ...head,
    {
      name: `Other (${tail.length})`,
      count: tail.reduce((s, x) => s + x.count, 0),
      amount: tail.reduce((s, x) => s + x.amount, 0),
    },
  ]
}

// Category label on one line (Recharts wraps long ticks on its own).
function Tick({ x, y, payload }) {
  return (
    <text x={x} y={y} dy={4} textAnchor="end" fill={CHART.muted} fontSize={12}>
      {payload.value}
    </text>
  )
}

function Tip({ active, payload }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="rounded-md border border-line bg-panel-2 px-3 py-2 text-xs shadow-xl">
      <p className="mb-1 text-muted">{d.label}</p>
      <p className="flex items-center gap-2">
        <span className="h-0.5 w-3 rounded" style={{ background: CHART.bar }} />
        <span className="font-semibold text-ink">{d.count} case{d.count === 1 ? '' : 's'}</span>
        <span className="text-muted">· {formatUSDT(d.amount)} lost</span>
      </p>
    </div>
  )
}

// One magnitude breakdown (single series): horizontal bars in one hue, value labelled at the bar end.
export default function BarBreakdown({ title, items, metric = 'count', humanizeNames = false }) {
  const rows = fold([...items].sort((a, b) => b[metric] - a[metric] || a.name.localeCompare(b.name))).map((x) => ({
    ...x,
    label: humanizeNames ? humanize(x.name) : x.name,
  }))
  return (
    <section className="rounded-lg border border-line bg-panel">
      <h2 className="border-b border-line px-4 py-2.5 text-sm font-semibold">{title}</h2>
      {rows.length === 0 ? (
        <p className="px-4 py-6 text-sm text-muted">No data yet.</p>
      ) : (
        <div className="px-2 py-3" style={{ height: rows.length * ROW_PX + 24 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 84, bottom: 0, left: 4 }} barCategoryGap={8}>
              <XAxis type="number" hide domain={[0, 'dataMax']} />
              <YAxis
                type="category"
                dataKey="label"
                width={150}
                tick={<Tick />}
                axisLine={{ stroke: CHART.line }}
                tickLine={false}
              />
              <Tooltip content={<Tip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} isAnimationActive={false} />
              <Bar
                dataKey={metric}
                fill={CHART.bar}
                radius={[0, 4, 4, 0]}
                maxBarSize={18}
                activeBar={{ fill: CHART.barHover }}
                isAnimationActive={false}
              >
                <LabelList dataKey={metric} position="right" formatter={fmt(metric)} fill={CHART.ink} fontSize={12} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  )
}
