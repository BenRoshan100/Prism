import { useState, useEffect } from "react";
import { getDocuments, clearMemory } from "./api";
import Sidebar from "./components/Sidebar";
import ChatArea from "./components/ChatArea";

function App() {
  const [documents, setDocuments] = useState([]);
  const [evalLog, setEvalLog] = useState([]);
  const [briefing, setBriefing] = useState(null);
  const [suggestedQuestion, setSuggestedQuestion] = useState("");

  useEffect(() => {
    getDocuments().then((d) => setDocuments(d.documents || []));
  }, []);

  async function handleNewConversation() {
    await clearMemory();
    setEvalLog([]);
    setBriefing(null);
    setSuggestedQuestion("");
    window.location.reload();
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
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
        />
        <ChatArea
          onEvalEntry={(entry) => setEvalLog((prev) => [...prev, entry])}
          hasDocuments={documents.length > 0}
          suggestedQuestion={suggestedQuestion}
          onSuggestedQuestionUsed={() => setSuggestedQuestion("")}
        />
      </main>
    </div>
  );
}

export default App;
