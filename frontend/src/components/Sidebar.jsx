import { useState } from "react";
import FileUpload from "./FileUpload";
import { deleteDocument } from "../api";

function NewWorkspaceInput({ onCreated }) {
  const [name, setName] = useState("");
  const [open, setOpen] = useState(false);

  function handleCreate(e) {
    e.preventDefault();
    const slug = name
      .trim()
      .toLowerCase()
      .replace(/\s+/g, "-")
      .replace(/[^a-z0-9-]/g, "");
    if (!slug) return;
    onCreated(slug);
    setName("");
    setOpen(false);
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="mt-2 w-full text-xs text-indigo-500 hover:text-indigo-700 text-left"
      >
        + New workspace
      </button>
    );
  }

  return (
    <form onSubmit={handleCreate} className="mt-2 flex gap-1">
      <input
        autoFocus
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="workspace-name"
        className="flex-1 text-xs border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500"
      />
      <button
        type="submit"
        className="text-xs bg-indigo-600 text-white rounded-lg px-2 py-1.5 hover:bg-indigo-700"
      >
        Create
      </button>
    </form>
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
  currentWorkspace,
  workspaces,
  onWorkspaceChange,
  onWorkspacesUpdate,
  filterDocs = [],
  onFilterChange,
  onFilterClear,
}) {
  const [deletingDoc, setDeletingDoc] = useState(null);

  async function handleDelete(docName) {
    if (!window.confirm(`Remove "${docName}" from the index?`)) return;
    setDeletingDoc(docName);
    try {
      const result = await deleteDocument(docName, currentWorkspace);
      setDocuments(result.documents);
    } catch (e) {
      alert(`Delete failed: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setDeletingDoc(null);
    }
  }

  return (
    <aside className="w-80 bg-white border-r border-gray-100 flex flex-col shrink-0 h-[calc(100vh-65px)] overflow-y-auto">
      <div className="p-4 space-y-4">
        {/* Workspace switcher */}
        <div className="bg-gray-50/80 rounded-xl p-3.5">
          <h3 className="text-xs font-semibold text-indigo-500 uppercase tracking-wider mb-2">
            Workspace
          </h3>
          <select
            value={currentWorkspace}
            onChange={(e) => onWorkspaceChange(e.target.value)}
            className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {workspaces.map((ws) => (
              <option key={ws} value={ws}>
                {ws}
              </option>
            ))}
          </select>
          <NewWorkspaceInput
            onCreated={(ws) => {
              onWorkspacesUpdate((prev) => [...new Set([...prev, ws])]);
              onWorkspaceChange(ws);
            }}
          />
        </div>

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
          <FileUpload onUploadComplete={setDocuments} onBriefing={onBriefing} currentWorkspace={currentWorkspace} />
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
              {(briefing.summary ?? []).map((point, i) => (
                <li key={i} className="text-xs text-gray-600 flex gap-1.5">
                  <span className="text-indigo-400 shrink-0">•</span>
                  {point}
                </li>
              ))}
            </ul>
            {(briefing.suggested_questions ?? []).length > 0 && (
              <div className="pt-1 space-y-1">
                <p className="text-xs text-indigo-400 font-medium">Try asking:</p>
                {(briefing.suggested_questions ?? []).map((q, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => onSuggestedQuestion(q)}
                    className="block w-full text-left text-xs bg-white border border-indigo-200 rounded-lg px-2.5 py-1.5 text-gray-700 hover:bg-indigo-50 hover:border-indigo-400 transition-colors focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:outline-none"
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
          <div className="flex items-center justify-between mb-2.5">
            <h3 className="text-xs font-semibold text-indigo-500 uppercase tracking-wider">
              Documents ({documents.length})
            </h3>
            {filterDocs.length > 0 && (
              <button
                type="button"
                onClick={onFilterClear}
                className="text-xs text-indigo-400 hover:text-indigo-600 transition-colors"
              >
                Clear filter
              </button>
            )}
          </div>
          {documents.length === 0 ? (
            <p className="text-sm text-gray-400">No documents yet</p>
          ) : (
            <ul className="space-y-1.5">
              {documents.map((doc, i) => {
                const isSelected = filterDocs.includes(doc.name);
                const isFiltering = filterDocs.length > 0;
                return (
                  <li
                    key={i}
                    className={`flex items-center justify-between text-sm bg-white rounded-lg px-3 py-2 shadow-xs transition-all cursor-pointer ${
                      isSelected
                        ? "ring-2 ring-indigo-500 bg-indigo-50"
                        : isFiltering
                        ? "opacity-50"
                        : "hover:ring-1 hover:ring-indigo-300"
                    }`}
                    onClick={() => onFilterChange(doc.name)}
                    title={isSelected ? "Click to remove filter" : "Click to filter to this doc"}
                  >
                    <span className={`truncate flex-1 min-w-0 ${isSelected ? "text-indigo-700 font-medium" : "text-gray-700"}`}>
                      {doc.name}
                    </span>
                    <span className="text-indigo-400 shrink-0 ml-2 text-xs font-medium">
                      {doc.chunk_count}
                    </span>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDelete(doc.name); }}
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
                );
              })}
            </ul>
          )}
        </div>

      </div>

      {/* Footer: version badge + eval link */}
      <div className="mt-auto p-4 border-t border-gray-100 flex items-center justify-between">
        <span className="text-xs text-gray-400 font-medium">
          <span className="bg-indigo-50 text-indigo-600 px-2 py-0.5 rounded-full font-semibold">Violet v1.3</span>
        </span>
        <a
          href="https://askprism-eval.vercel.app/"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-indigo-600 transition-colors group"
        >
          <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <span className="group-hover:underline">Eval →</span>
        </a>
      </div>
    </aside>
  );
}
