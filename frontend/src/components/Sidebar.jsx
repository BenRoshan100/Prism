import FileUpload from "./FileUpload";

function TrafficLight({ faithfulnessMean }) {
  let color, label;

  if (faithfulnessMean === null) {
    color = "bg-gray-300";
    label = "No data";
  } else {
    const fNorm = faithfulnessMean / 5;
    if (fNorm < 0.5) {
      color = "bg-red-500";
      label = "Poor";
    } else if (fNorm < 0.7) {
      color = "bg-yellow-500";
      label = "Moderate";
    } else {
      color = "bg-green-500";
      label = "Healthy";
    }
  }

  return (
    <div className="flex items-center gap-2">
      <div className={`w-3 h-3 rounded-full ${color} ring-2 ring-offset-1 ring-${color === "bg-gray-300" ? "gray-200" : color.replace("bg-", "")}/30`} />
      <span className="text-sm font-medium text-gray-700">{label}</span>
    </div>
  );
}

export default function Sidebar({
  documents,
  setDocuments,
  onNewConversation,
  evalLog,
}) {
  const faithfulnessScores = evalLog.filter((e) => e.faithfulness_score > 0);
  const faithfulnessMean =
    faithfulnessScores.length > 0
      ? faithfulnessScores.reduce((s, e) => s + e.faithfulness_score, 0) /
        faithfulnessScores.length
      : null;

  return (
    <aside className="w-80 bg-white border-r border-gray-100 flex flex-col shrink-0 h-[calc(100vh-65px)] overflow-y-auto">
      <div className="p-4 space-y-4">
        {/* New Conversation */}
        <button
          onClick={onNewConversation}
          className="w-full px-4 py-2.5 bg-indigo-600 text-white rounded-xl text-sm font-medium hover:bg-indigo-700 transition-colors shadow-sm"
        >
          New Conversation
        </button>

        {/* File Upload */}
        <div className="bg-gray-50/80 rounded-xl p-3.5">
          <h3 className="text-xs font-semibold text-indigo-500 uppercase tracking-wider mb-2.5">
            Upload Documents
          </h3>
          <FileUpload onUploadComplete={setDocuments} />
        </div>

        {/* Uploaded Documents */}
        <div className="bg-gray-50/80 rounded-xl p-3.5">
          <h3 className="text-xs font-semibold text-indigo-500 uppercase tracking-wider mb-2.5">
            Documents ({documents.length})
          </h3>
          {documents.length === 0 ? (
            <p className="text-sm text-gray-400">No documents yet</p>
          ) : (
            <ul className="space-y-1.5">
              {documents.map((doc, i) => (
                <li
                  key={i}
                  className="flex items-center justify-between text-sm bg-white rounded-lg px-3 py-2 shadow-xs"
                >
                  <span className="text-gray-700 truncate">{doc.name}</span>
                  <span className="text-indigo-400 shrink-0 ml-2 text-xs font-medium">
                    {doc.chunk_count}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Faithfulness Log */}
        <div className="bg-gray-50/80 rounded-xl p-3.5">
          <h3 className="text-xs font-semibold text-indigo-500 uppercase tracking-wider mb-2.5">
            Faithfulness ({evalLog.length} queries)
          </h3>
          {evalLog.length > 0 ? (
            <div className="flex gap-1.5 flex-wrap">
              {evalLog.slice(-10).map((e, i) => (
                <span
                  key={i}
                  title={e.reason}
                  className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-xs font-bold text-white shadow-sm ${
                    e.faithfulness_score >= 4
                      ? "bg-green-500"
                      : e.faithfulness_score === 3
                      ? "bg-yellow-500"
                      : e.faithfulness_score > 0
                      ? "bg-red-500"
                      : "bg-gray-300"
                  }`}
                >
                  {e.faithfulness_score > 0 ? e.faithfulness_score : "?"}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400">No queries yet</p>
          )}
        </div>

        {/* Retrieval Health */}
        <div className="bg-gray-50/80 rounded-xl p-3.5">
          <h3 className="text-xs font-semibold text-indigo-500 uppercase tracking-wider mb-2.5">
            Retrieval Health
          </h3>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-400">Mean Faithfulness</p>
              <p className="text-lg font-semibold text-gray-800">
                {faithfulnessMean !== null
                  ? `${faithfulnessMean.toFixed(1)}/5`
                  : "--"}
              </p>
            </div>
            <TrafficLight faithfulnessMean={faithfulnessMean} />
          </div>
        </div>
      </div>
    </aside>
  );
}
