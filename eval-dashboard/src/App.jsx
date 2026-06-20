import { useState, useEffect } from 'react'
import MetricCard from './components/MetricCard'
import EvolutionChart from './components/EvolutionChart'
import LatencyStats from './components/LatencyStats'

const MAJOR_NAMES = { 1: 'Violet', 2: 'Indigo', 3: 'Azure', 4: 'Amber', 5: 'Scarlet' }

function formatVersion(version) {
  const match = version.match(/^v(\d+)\.(\d+)/)
  if (!match) return version
  const [, major, minor] = match
  const name = MAJOR_NAMES[Number(major)] ?? `v${major}`
  return `${name} (v${major}.${minor})`
}

const VERSION_NOTES = {
  'v1.0.0': [
    'Baseline: hybrid BM25 (0.3) + ChromaDB dense (0.7) → RRF → TinyBERT rerank top-10→5',
    '50 eval pairs across multi-hop, comparative, negative, numeric, and edge-case question types',
    'answer_correctness (LLM judge vs ground truth) adopted as primary metric — replaces circular faithfulness',
    'Separate eval-dashboard deployed; per-message faithfulness badge removed from UI',
  ],
  'v1.1.0': [
    'HyDE enabled: LLM generates a hypothetical answer, embeds it instead of the raw query',
    'Closes question→answer vector space gap — dense retrieval finds answer-shaped chunks',
    'BM25 + reranker still use original query',
    'Result: recall +3.5% but latency 3× (one extra Groq call per query) — not worth the trade',
  ],
  'v1.2.0': [
    'Multi-Query Retrieval: LLM generates 3 phrasings of each query at retrieval time',
    'Retrieves for each phrasing, deduplicates by best rank, RRF fuses wider candidate pool',
    'Reranker still scores against the original query',
    'Result: +0.7% recall, relevancy dropped — Phase 1 (query-side) exhausted; root cause is chunk quality',
  ],
  'v1.3.0': [
    'Contextual Retrieval: at ingest time, llama-3.1-8b-instant prepends 2-sentence context to each chunk',
    'Context situates the chunk within its source document before embedding — richer vector representation',
    'Result: recall +9.1pp (+18%), P@5 +6.6pp — biggest lift across all experiments',
    'Latency 2× — contextualized chunks are longer, so LLM processes more tokens per answer',
    'Production ingest untouched; eval-only via --contextual flag',
  ],
}

const METRIC_DEFS = [
  {
    key: 'answer_correctness',
    label: 'Answer Correctness',
    description: 'Are key facts in the generated answer correct vs the reference?',
    methodology: 'LLM-as-Judge: llama-3.1-8b scores each answer 1–5 against a human-written ground truth. Prompt checks for key facts present and correct. Score normalized to 0–1 (÷5). Independent of retrieved docs — judge only sees answer + reference.',
  },
  {
    key: 'answer_relevancy',
    label: 'Answer Relevancy',
    description: 'Does the answer actually address the question asked?',
    methodology: 'RAGAS metric. Generates N reverse questions from the answer using an LLM, embeds them, then measures cosine similarity to the original question embedding. High = answer stays on-topic. Low = vague, padded, or off-topic response. Does not require ground truth.',
  },
  {
    key: 'context_recall',
    label: 'Context Recall',
    description: 'Did retrieval surface all the chunks needed to answer correctly?',
    methodology: 'RAGAS metric. Breaks the ground truth reference into individual sentences. For each sentence, an LLM checks whether it can be attributed to the retrieved context. Score = attributed sentences ÷ total ground truth sentences. Requires ground truth.',
  },
  {
    key: 'precision_at_5',
    label: 'Precision@5',
    description: 'What fraction of the top-5 retrieved chunks were actually relevant?',
    methodology: 'Custom metric. For each of the 5 reranked chunks returned: checks if the source filename matches the expected document AND if relevant keywords from the eval pair appear in the chunk text. Score = matching chunks ÷ 5. No LLM call — deterministic.',
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
                    {formatVersion(e.version)}
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
                {formatVersion(currentRun.version)}
              </span>
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

            {/* Release notes */}
            {VERSION_NOTES[currentRun.version] && (
              <div className="bg-white border border-gray-100 rounded-2xl px-5 py-4">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
                  Release Notes — {formatVersion(currentRun.version)}
                </p>
                <ul className="space-y-1.5">
                  {VERSION_NOTES[currentRun.version].map((note, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                      <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-indigo-400 flex-shrink-0" />
                      {note}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Metric cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {METRIC_DEFS.map(m => (
                <MetricCard
                  key={m.key}
                  label={m.label}
                  description={m.description}
                  methodology={m.methodology}
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
