export default function MetricCard({ label, value, prevValue, description, unit = '%' }) {
  const display = value != null ? (unit === '%' ? `${(value * 100).toFixed(1)}%` : `${value}`) : '—'

  let delta = null
  let deltaClass = 'text-gray-400'
  let deltaSign = ''
  if (value != null && prevValue != null) {
    const diff = unit === '%' ? (value - prevValue) * 100 : value - prevValue
    delta = diff.toFixed(unit === '%' ? 1 : 0)
    if (diff > 0) { deltaClass = 'text-emerald-600'; deltaSign = '+' }
    else if (diff < 0) { deltaClass = 'text-red-500'; deltaSign = '' }
    else { deltaClass = 'text-gray-400' }
  }

  const scoreColor = value == null ? 'text-gray-400'
    : value >= 0.8 ? 'text-emerald-600'
    : value >= 0.6 ? 'text-yellow-600'
    : 'text-red-500'

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 flex flex-col gap-1">
      <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">{label}</span>
      <div className="flex items-end gap-2 mt-1">
        <span className={`text-3xl font-bold tabular-nums ${scoreColor}`}>{display}</span>
        {delta != null && (
          <span className={`text-sm font-medium mb-1 ${deltaClass}`}>
            {deltaSign}{delta}{unit === '%' ? 'pp' : unit}
          </span>
        )}
      </div>
      <p className="text-xs text-gray-400 mt-1 leading-relaxed">{description}</p>
    </div>
  )
}
