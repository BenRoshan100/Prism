import { useState } from "react";
import FileUpload from "./FileUpload";
import EvalPanel from "./EvalPanel";
import { deleteDocument } from "../api";

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
  onBriefing,
  briefing,
  onSuggestedQuestion,
}) {
  const [deletingDoc, setDeletingDoc] = useState(null);

  async function handleDelete(docName) {
    if (!window.confirm(`Remove "${docName}" from the index?`)) return;
    setDeletingDoc(docName);
    try {
      const result = await deleteDocument(docName);
      setDocuments(result.documents);
    } catch (e) {
      alert(`Delete failed: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setDeletingDoc(null);
    }
  }

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
          <FileUpload onUploadComplete={setDocuments} onBriefing={onBriefing} />
        </div>

        {/* Briefing card */}
        {briefing && (
          <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-3.5 space-y-2">
            <h3 className="text-xs font-semibold text-indigo-500 uppercase tracking-wider truncate">
              {briefing.doc_name.length > 30
                ? briefing.doc_name.slice(0, 30) + "…"
                : briefing.doc_name}
            </h3>
            <ul className="space-y-1">
              {briefing.summary.map((point, i) => (
                <li key={i} className="text-xs text-gray-600 flex gap-1.5">
                  <span className="text-indigo-400 shrink-0">•</span>
                  {point}
                </li>
              ))}
            </ul>
            {briefing.suggested_questions.length > 0 && (
              <div className="pt-1 space-y-1">
                <p className="text-xs text-indigo-400 font-medium">Try asking:</p>
                {briefing.suggested_questions.map((q, i) => (
                  <button
                    key={i}
                    onClick={() => onSuggestedQuestion(q)}
                    className="block w-full text-left text-xs bg-white border border-indigo-200 rounded-lg px-2.5 py-1.5 text-gray-700 hover:bg-indigo-50 hover:border-indigo-400 transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

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
                  <span className="text-gray-700 truncate flex-1 min-w-0">{doc.name}</span>
                  <span className="text-indigo-400 shrink-0 ml-2 text-xs font-medium">
                    {doc.chunk_count}
                  </span>
                  <button
                    onClick={() => handleDelete(doc.name)}
                    disabled={deletingDoc === doc.name}
                    title="Remove document"
                    className="ml-2 shrink-0 text-gray-300 hover:text-red-500 transition-colors disabled:opacity-40"
                  >
                    {deletingDoc === doc.name ? (
                      <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                      </svg>
                    ) : (
                      <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zm-1 6a1 1 0 112 0v5a1 1 0 11-2 0V8zm4 0a1 1 0 112 0v5a1 1 0 11-2 0V8z" clipRule="evenodd"/>
                      </svg>
                    )}
                  </button>
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

        {/* RAGAS Benchmark */}
        <EvalPanel />
      </div>
    </aside>
  );
}
