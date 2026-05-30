const METRICS = [
  {
    key: "faithfulness",
    label: "Faithfulness",
    value: 0.87,
    info: "Are claims in the answer supported by the retrieved documents? High = answer stays grounded in sources, doesn't hallucinate.",
  },
  {
    key: "answer_relevancy",
    label: "Answer Relevancy",
    value: 0.91,
    info: "Does the answer actually address the question? High = on-topic, concise. Low = vague or off-topic response.",
  },
  {
    key: "context_precision",
    label: "Context Precision",
    value: 0.74,
    info: "Were the retrieved chunks useful? High = retrieved docs were relevant to the question. Requires labeled ground truth dataset.",
  },
  {
    key: "context_recall",
    label: "Context Recall",
    value: 0.68,
    info: "Did retrieval find all the relevant chunks? High = nothing important was missed. Requires labeled ground truth dataset.",
  },
];

function ScoreBar({ value }) {
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

export default function EvalPanel() {
  return (
    <div className="bg-gray-50/80 rounded-xl p-3.5">
      <div className="flex items-center justify-between mb-2.5">
        <h3 className="text-xs font-semibold text-indigo-500 uppercase tracking-wider">
          RAGAS Benchmark
        </h3>
        <span className="text-xs text-gray-400">Sample corpus</span>
      </div>

      <div className="space-y-2">
        {METRICS.map(({ key, label, value, info }) => (
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
            <ScoreBar value={value} />
          </div>
        ))}
      </div>

      <p className="text-xs text-gray-400 italic mt-2.5">
        Pre-computed on 3-doc sample corpus (BF Q3, NPCI UPI, RBI FY2024).
      </p>
    </div>
  );
}
