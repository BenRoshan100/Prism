import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts'

const METRICS = [
  { key: 'answer_correctness', label: 'Answer Correctness', color: '#6366f1' },
  { key: 'answer_relevancy',   label: 'Answer Relevancy',   color: '#10b981' },
  { key: 'context_recall',     label: 'Context Recall',     color: '#f59e0b' },
  { key: 'precision_at_5',     label: 'Precision@5',        color: '#ef4444' },
]

const MAJOR_NAMES = { 1: 'Violet', 2: 'Indigo', 3: 'Azure', 4: 'Amber', 5: 'Scarlet' }

function formatVersion(version) {
  const match = version.match(/^v(\d+)\.(\d+)/)
  if (!match) return version
  const [, major, minor] = match
  const name = MAJOR_NAMES[Number(major)] ?? `v${major}`
  return `${name} (v${major}.${minor})`
}

function VersionTick({ x, y, payload, dateMap }) {
  const ver = payload.value
  const rawDate = dateMap[ver]
  const shortDate = rawDate
    ? new Date(rawDate).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: '2-digit' })
    : ''
  return (
    <g transform={`translate(${x},${y})`}>
      <text x={0} y={0} dy={14} textAnchor="middle" fontSize={11} fill="#6b7280">
        {formatVersion(ver)}
      </text>
      <text x={0} y={0} dy={28} textAnchor="middle" fontSize={10} fill="#9ca3af">
        {shortDate}
      </text>
    </g>
  )
}

export default function EvolutionChart({ runs, index }) {
  if (!runs.length) return null

  const dateMap = Object.fromEntries(index.map(e => [e.version, e.date]))

  const data = runs.map((run, i) => ({
    version: index[i]?.version ?? `run${i + 1}`,
    ...Object.fromEntries(
      METRICS.map(m => [m.key, run.metrics?.[m.key] != null
        ? parseFloat((run.metrics[m.key] * 100).toFixed(1))
        : null
      ])
    ),
  }))

  const fmt = (v) => `${v}%`

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
      <h2 className="text-sm font-semibold text-gray-700 mb-4">Metric Evolution Across Versions</h2>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis
            dataKey="version"
            tick={<VersionTick dateMap={dateMap} />}
            height={48}
            interval={0}
          />
          <YAxis domain={[0, 100]} tickFormatter={fmt} tick={{ fontSize: 12 }} width={40} />
          <Tooltip
            formatter={(v) => `${v}%`}
            labelFormatter={(ver) => formatVersion(ver)}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {METRICS.map(m => (
            <Line
              key={m.key}
              type="monotone"
              dataKey={m.key}
              name={m.label}
              stroke={m.color}
              strokeWidth={2}
              dot={{ r: 4 }}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
