function StatBar({ label, value, max }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0
  const color = value < 3000 ? 'bg-emerald-500' : value < 6000 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between text-xs text-gray-500">
        <span>{label}</span>
        <span className="font-mono font-medium text-gray-700">{value ? `${value.toLocaleString()}ms` : '—'}</span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export default function LatencyStats({ metrics }) {
  const p50 = metrics?.latency_p50_ms
  const p95 = metrics?.latency_p95_ms
  const p99 = metrics?.latency_p99_ms
  const max = Math.max(p99 ?? 0, p95 ?? 0, p50 ?? 0, 10000)

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
      <h2 className="text-sm font-semibold text-gray-700 mb-4">Response Latency</h2>
      <div className="flex flex-col gap-4">
        <StatBar label="p50 (median)" value={p50} max={max} />
        <StatBar label="p95" value={p95} max={max} />
        {p99 != null && <StatBar label="p99" value={p99} max={max} />}
      </div>
      <p className="text-xs text-gray-400 mt-3">End-to-end per-query latency including retrieval + LLM call. Does not include Tavily web search.</p>
    </div>
  )
}
