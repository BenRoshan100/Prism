import { useState, useEffect, useCallback } from "react";
import { getDocuments, clearMemory, getWorkspaces } from "./api";
import Sidebar from "./components/Sidebar";
import ChatArea from "./components/ChatArea";
import { MAINTENANCE_MODE, MAINTENANCE_MESSAGE } from "./config";

function App() {
  const [documents, setDocuments] = useState([]);
  const [evalLog, setEvalLog] = useState([]);
  const [briefing, setBriefing] = useState(null);
  const [suggestedQuestion, setSuggestedQuestion] = useState("");
  const [currentWorkspace, setCurrentWorkspace] = useState("default");
  const [workspaces, setWorkspaces] = useState(["default"]);
  const [filterDocs, setFilterDocs] = useState([]);

  useEffect(() => {
    getDocuments(currentWorkspace).then((d) => setDocuments(d.documents || []));
    getWorkspaces().then((d) => setWorkspaces(d.workspaces || ["default"]));
  }, [currentWorkspace]);

  // Reset filter when workspace changes
  useEffect(() => {
    setFilterDocs([]);
  }, [currentWorkspace]);

  async function handleNewConversation() {
    await clearMemory();
    setEvalLog([]);
    setBriefing(null);
    setSuggestedQuestion("");
    window.location.reload();
  }

  async function handleWorkspaceChange(ws) {
    setCurrentWorkspace(ws);
    setBriefing(null);
    setSuggestedQuestion("");
    setEvalLog([]);
  }

  const handleSuggestedQuestionUsed = useCallback(() => setSuggestedQuestion(""), []);

  function handleFilterChange(docName) {
    setFilterDocs((prev) =>
      prev.includes(docName) ? prev.filter((d) => d !== docName) : [...prev, docName]
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Maintenance overlay — controlled by src/config.js */}
      {MAINTENANCE_MODE && (
        <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-gray-950/90 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl px-10 py-10 max-w-md w-full mx-4 flex flex-col items-center text-center gap-4">
            <svg className="w-14 h-14 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            </svg>
            <h2 className="text-2xl font-bold text-gray-900">Under Maintenance</h2>
            <p className="text-gray-500 text-sm leading-relaxed">{MAINTENANCE_MESSAGE}</p>
          </div>
        </div>
      )}

      <header className="bg-white px-6 py-4 shrink-0 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-1 h-8 bg-indigo-600 rounded-full" />
          <div>
            <h1 className="text-lg font-semibold text-gray-900 leading-tight">
              Prism
            </h1>
            <p className="text-xs text-gray-400">Document Intelligence</p>
          </div>
        </div>
      </header>

      <main className="flex-1 flex">
        <Sidebar
          documents={documents}
          setDocuments={setDocuments}
          onNewConversation={handleNewConversation}
          evalLog={evalLog}
          onBriefing={setBriefing}
          briefing={briefing}
          onSuggestedQuestion={setSuggestedQuestion}
          currentWorkspace={currentWorkspace}
          workspaces={workspaces}
          onWorkspaceChange={handleWorkspaceChange}
          onWorkspacesUpdate={setWorkspaces}
          filterDocs={filterDocs}
          onFilterChange={handleFilterChange}
          onFilterClear={() => setFilterDocs([])}
        />
        <ChatArea
          key={currentWorkspace}
          onEvalEntry={(entry) => setEvalLog((prev) => [...prev, entry])}
          hasDocuments={documents.length > 0}
          suggestedQuestion={suggestedQuestion}
          onSuggestedQuestionUsed={handleSuggestedQuestionUsed}
          currentWorkspace={currentWorkspace}
          filterDocs={filterDocs}
          onFilterClear={() => setFilterDocs([])}
        />
      </main>
    </div>
  );
}

export default App;
