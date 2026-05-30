import { useState } from "react";
import { runRagasEval } from "../api";

const METRICS = [
  {
    key: "faithfulness",
    label: "Faithfulness",
    info: "Are claims in the answer supported by the retrieved documents? High = answer stays grounded in sources, doesn't hallucinate.",
  },
  {
    key: "answer_relevancy",
    label: "Answer Relevancy",
    info: "Does the answer actually address the question? High = on-topic, concise. Low = vague or off-topic response.",
  },
  {
    key: "context_precision",
    label: "Context Precision",
    info: "Were the retrieved chunks useful? High = retrieved docs were relevant to the question. Requires labeled ground truth — N/A without it.",
  },
  {
    key: "context_recall",
    label: "Context Recall",
    info: "Did retrieval find all the relevant chunks? High = nothing important was missed. Requires labeled ground truth — N/A without it.",
  },
];

function ScoreBar({ value }) {
  if (value === null || value === undefined) {
    return <span className="text-xs text-gray-400">N/A</span>;
  }
  const pct = Math.round(value * 100);
  const color =
    pct >= 70 ? "bg-green-500" : pct >= 50 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-200 rounded-full h-1.5">
        <div className={`${color} h-1.5 rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-semibold text-gray-700 w-8 text-right">
        {pct}%
      </span>
    </div>
  );
}

export default function EvalPanel({ evalLogLength }) {
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [nPairs, setNPairs] = useState(10);

  async function handleRun() {
    setLoading(true);
    setError(null);
    try {
      const data = await runRagasEval(nPairs);
      setResults(data);
    } catch (e) {
      setError(e?.response?.data?.detail || "RAGAS eval failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-gray-50/80 rounded-xl p-3.5">
      <h3 className="text-xs font-semibold text-indigo-500 uppercase tracking-wider mb-2.5">
        RAGAS Eval
      </h3>

      <div className="flex items-center gap-2 mb-3">
        <label className="text-xs text-gray-500 shrink-0">Last</label>
        <input
          type="number"
          min={1}
          max={50}
          value={nPairs}
          onChange={(e) => setNPairs(Number(e.target.value))}
          className="w-14 text-xs border border-gray-200 rounded-lg px-2 py-1 text-center focus:outline-none focus:ring-1 focus:ring-indigo-400"
        />
        <label className="text-xs text-gray-500 shrink-0">queries</label>
        <button
          onClick={handleRun}
          disabled={loading || evalLogLength === 0}
          className="ml-auto text-xs px-3 py-1.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors font-medium"
        >
          {loading ? "Running…" : "Run"}
        </button>
      </div>

      {evalLogLength === 0 && (
        <p className="text-xs text-gray-400">Ask questions first to populate eval data.</p>
      )}

      {error && (
        <p className="text-xs text-red-500 bg-red-50 rounded-lg px-2 py-1.5">{error}</p>
      )}

      {results?.error && (
        <p className="text-xs text-amber-600 bg-amber-50 rounded-lg px-2 py-1.5">{results.error}</p>
      )}

      {results && (
        <div className="space-y-2">
          {METRICS.map(({ key, label, info }) => (
            <div key={key}>
              <div className="flex items-center gap-1 mb-0.5">
                <span className="text-xs text-gray-500">{label}</span>
                <span className="group relative">
                  <svg className="w-3 h-3 text-gray-400 cursor-help" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                  </svg>
                  <span className="pointer-events-none absolute bottom-5 left-0 z-10 w-52 rounded-lg bg-gray-800 px-2.5 py-2 text-xs text-white opacity-0 group-hover:opacity-100 transition-opacity shadow-lg">
                    {info}
                  </span>
                </span>
              </div>
              <ScoreBar value={results[key]} />
            </div>
          ))}
          {results.sample_count !== undefined && (
            <p className="text-xs text-gray-400 pt-1">
              Evaluated {results.sample_count} pair{results.sample_count !== 1 ? "s" : ""}
            </p>
          )}
          {results.note && (
            <p className="text-xs text-gray-400 italic">{results.note}</p>
          )}
        </div>
      )}
    </div>
  );
}
