export default function MetricCard({ label, value, prevValue, description, methodology, unit = '%' }) {
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
      <div className="flex items-center gap-1.5">
        <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">{label}</span>
        {methodology && (
          <span className="group relative shrink-0">
            <svg className="w-3.5 h-3.5 text-gray-300 hover:text-indigo-400 cursor-help transition-colors" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
            <span className="pointer-events-none absolute bottom-6 left-0 z-20 w-72 rounded-xl bg-gray-900 px-3.5 py-3 text-xs text-gray-200 opacity-0 group-hover:opacity-100 transition-opacity shadow-xl leading-relaxed">
              <span className="block font-semibold text-white mb-1">How it's computed</span>
              {methodology}
            </span>
          </span>
        )}
      </div>
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
