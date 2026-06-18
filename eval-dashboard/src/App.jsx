import { useState, useEffect } from 'react'
import MetricCard from './components/MetricCard'
import EvolutionChart from './components/EvolutionChart'
import LatencyStats from './components/LatencyStats'

const METRIC_DEFS = [
  {
    key: 'answer_correctness',
    label: 'Answer Correctness',
    description: 'LLM judge (8B) comparing generated answer to ground truth. 0–1 normalized.',
  },
  {
    key: 'answer_relevancy',
    label: 'Answer Relevancy',
    description: 'RAGAS: does the answer address the question? Penalizes off-topic responses.',
  },
  {
    key: 'context_recall',
    label: 'Context Recall',
    description: 'RAGAS: did retrieval surface all chunks needed to answer? Higher = less missing context.',
  },
  {
    key: 'precision_at_5',
    label: 'Precision@5',
    description: 'Retrieval: what fraction of top-5 chunks are relevant? Based on source + keyword match.',
  },
]

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <div className="w-16 h-16 rounded-2xl bg-indigo-50 flex items-center justify-center mb-4">
        <svg className="w-8 h-8 text-indigo-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5"
            d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      </div>
      <h2 className="text-lg font-semibold text-gray-700 mb-1">No eval runs yet</h2>
      <p className="text-sm text-gray-400 max-w-sm">
        Run the eval script to generate the first benchmark:
      </p>
      <pre className="mt-3 text-xs bg-gray-100 text-gray-600 px-4 py-3 rounded-xl font-mono">
        python scripts/run_eval_versioned.py --version v2.0 --tag "baseline" --n 50
      </pre>
    </div>
  )
}

export default function App() {
  const [indexData, setIndexData] = useState([])
  const [runs, setRuns] = useState([])
  const [selectedVersion, setSelectedVersion] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch('/data/index.json')
      .then(r => r.json())
      .then(async (idx) => {
        if (!idx.length) { setLoading(false); return }
        const loaded = await Promise.all(
          idx.map(entry => fetch(`/data/runs/${entry.file}`).then(r => r.json()))
        )
        setIndexData(idx)
        setRuns(loaded)
        setSelectedVersion(idx[idx.length - 1].version)
        setLoading(false)
      })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [])

  const currentIdx = indexData.findIndex(e => e.version === selectedVersion)
  const currentRun = runs[currentIdx] ?? null
  const prevRun = currentIdx > 0 ? runs[currentIdx - 1] : null

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-100 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                  d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <div>
              <h1 className="text-base font-semibold text-gray-900">Prism Eval Dashboard</h1>
              <p className="text-xs text-gray-400">Retrieval & answer quality metrics</p>
            </div>
          </div>

          {indexData.length > 0 && (
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-400">{indexData.length} run{indexData.length !== 1 ? 's' : ''}</span>
              <select
                value={selectedVersion ?? ''}
                onChange={e => setSelectedVersion(e.target.value)}
                className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                {indexData.map(e => (
                  <option key={e.version} value={e.version}>
                    {e.version} — {e.tag}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8 flex flex-col gap-6">
        {loading && (
          <div className="flex items-center justify-center py-24 text-gray-400 text-sm">Loading...</div>
        )}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-xl">
            Failed to load eval data: {error}
          </div>
        )}

        {!loading && !error && !runs.length && <EmptyState />}

        {currentRun && (
          <>
            {/* Run meta */}
            <div className="flex items-center gap-4 text-xs text-gray-400">
              <span className="bg-indigo-50 text-indigo-700 font-medium px-2.5 py-1 rounded-full">
                {currentRun.version}
              </span>
              <span>{currentRun.tag}</span>
              <span>·</span>
              <span>{currentRun.sample_count} samples</span>
              <span>·</span>
              <span>{new Date(currentRun.computed_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}</span>
              {currentRun.config && (
                <>
                  <span>·</span>
                  <span>HyDE: {currentRun.config.hyde_enabled ? 'on' : 'off'}</span>
                  <span>·</span>
                  <span>retrieve_k={currentRun.config.retrieve_k}</span>
                </>
              )}
            </div>

            {/* Metric cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {METRIC_DEFS.map(m => (
                <MetricCard
                  key={m.key}
                  label={m.label}
                  description={m.description}
                  value={currentRun.metrics?.[m.key]}
                  prevValue={prevRun?.metrics?.[m.key]}
                />
              ))}
            </div>

            {/* Evolution chart + latency */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <div className="lg:col-span-2">
                <EvolutionChart runs={runs} index={indexData} />
              </div>
              <LatencyStats metrics={currentRun.metrics} />
            </div>

          </>
        )}
      </main>
    </div>
  )
}
