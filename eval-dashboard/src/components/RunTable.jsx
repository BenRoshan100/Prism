import { useState } from 'react'

function score(v) {
  if (v == null) return '—'
  return `${(v * 100).toFixed(0)}%`
}

function scoreColor(v) {
  if (v == null) return 'text-gray-300'
  if (v >= 0.8) return 'text-emerald-600'
  if (v >= 0.6) return 'text-yellow-600'
  return 'text-red-500'
}

function Row({ item, idx }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <tr
        className="hover:bg-gray-50 cursor-pointer border-t border-gray-100"
        onClick={() => setOpen(v => !v)}
      >
        <td className="px-4 py-2.5 text-xs text-gray-500 font-mono w-8">{idx + 1}</td>
        <td className="px-4 py-2.5 text-sm text-gray-700 max-w-xs">
          <span className="line-clamp-2">{item.query}</span>
        </td>
        <td className={`px-4 py-2.5 text-sm font-mono font-medium text-center ${scoreColor(item.answer_correctness)}`}>
          {score(item.answer_correctness)}
        </td>
        <td className={`px-4 py-2.5 text-sm font-mono font-medium text-center ${scoreColor(item.answer_relevancy)}`}>
          {score(item.answer_relevancy)}
        </td>
        <td className={`px-4 py-2.5 text-sm font-mono font-medium text-center ${scoreColor(item.context_recall)}`}>
          {score(item.context_recall)}
        </td>
        <td className={`px-4 py-2.5 text-sm font-mono font-medium text-center ${scoreColor(item.precision_at_5)}`}>
          {score(item.precision_at_5)}
        </td>
        <td className="px-4 py-2.5 text-xs text-gray-400 font-mono text-right">
          {item.latency_ms ? `${item.latency_ms}ms` : '—'}
        </td>
        <td className="px-4 py-2.5 text-gray-300 text-center">
          <span>{open ? '▲' : '▼'}</span>
        </td>
      </tr>
      {open && (
        <tr className="bg-gray-50 border-t border-gray-100">
          <td colSpan={8} className="px-6 py-4">
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div>
                <p className="font-semibold text-gray-500 mb-1">Generated answer</p>
                <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">{item.answer}</p>
              </div>
              <div>
                <p className="font-semibold text-gray-500 mb-1">Ground truth</p>
                <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">{item.ground_truth}</p>
              </div>
              {item.correctness_reason && (
                <div className="col-span-2">
                  <p className="font-semibold text-gray-500 mb-1">Correctness judge note</p>
                  <p className="text-gray-600 italic">{item.correctness_reason}</p>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

export default function RunTable({ perQuery }) {
  if (!perQuery?.length) return null
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-100">
        <h2 className="text-sm font-semibold text-gray-700">Per-Query Breakdown</h2>
        <p className="text-xs text-gray-400 mt-0.5">Click any row to see generated answer vs ground truth</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-gray-50">
              <th className="px-4 py-2.5 text-xs text-gray-400 font-medium">#</th>
              <th className="px-4 py-2.5 text-xs text-gray-400 font-medium">Query</th>
              <th className="px-4 py-2.5 text-xs text-gray-400 font-medium text-center">Correctness</th>
              <th className="px-4 py-2.5 text-xs text-gray-400 font-medium text-center">Relevancy</th>
              <th className="px-4 py-2.5 text-xs text-gray-400 font-medium text-center">Recall</th>
              <th className="px-4 py-2.5 text-xs text-gray-400 font-medium text-center">P@5</th>
              <th className="px-4 py-2.5 text-xs text-gray-400 font-medium text-right">Latency</th>
              <th className="px-4 py-2.5 text-xs text-gray-400 font-medium text-center"></th>
            </tr>
          </thead>
          <tbody>
            {perQuery.map((item, i) => <Row key={i} item={item} idx={i} />)}
          </tbody>
        </table>
      </div>
    </div>
  )
}
