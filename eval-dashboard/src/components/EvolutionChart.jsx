import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts'

const METRICS = [
  { key: 'answer_correctness', label: 'Answer Correctness', color: '#6366f1' },
  { key: 'answer_relevancy',   label: 'Answer Relevancy',   color: '#10b981' },
  { key: 'context_recall',     label: 'Context Recall',     color: '#f59e0b' },
  { key: 'precision_at_5',     label: 'Precision@5',        color: '#ef4444' },
]

export default function EvolutionChart({ runs, index }) {
  if (!runs.length) return null

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
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis dataKey="version" tick={{ fontSize: 12 }} />
          <YAxis domain={[0, 100]} tickFormatter={fmt} tick={{ fontSize: 12 }} width={40} />
          <Tooltip formatter={(v) => `${v}%`} />
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
