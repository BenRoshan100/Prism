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

  useEffect(() => {
    getDocuments(currentWorkspace).then((d) => setDocuments(d.documents || []));
    getWorkspaces().then((d) => setWorkspaces(d.workspaces || ["default"]));
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

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Maintenance banner — controlled by src/config.js */}
      {MAINTENANCE_MODE && (
        <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 flex items-center justify-center gap-2 text-xs text-amber-800">
          <svg className="w-3.5 h-3.5 shrink-0 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
          </svg>
          <span><strong>Under maintenance</strong> — {MAINTENANCE_MESSAGE}</span>
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
        />
        <ChatArea
          key={currentWorkspace}
          onEvalEntry={(entry) => setEvalLog((prev) => [...prev, entry])}
          hasDocuments={documents.length > 0}
          suggestedQuestion={suggestedQuestion}
          onSuggestedQuestionUsed={handleSuggestedQuestionUsed}
          currentWorkspace={currentWorkspace}
        />
      </main>
    </div>
  );
}

export default App;
