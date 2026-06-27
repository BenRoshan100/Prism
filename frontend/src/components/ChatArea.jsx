import { useState, useEffect, useRef } from "react";
import { streamChat } from "../api";
import MessageBubble from "./MessageBubble";

export default function ChatArea({
  onEvalEntry,
  hasDocuments,
  suggestedQuestion,
  onSuggestedQuestionUsed,
  currentWorkspace = "default",
  filterDocs = [],
  onFilterClear,
}) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    if (suggestedQuestion) {
      setInput(suggestedQuestion);
      onSuggestedQuestionUsed?.();
    }
  }, [suggestedQuestion, onSuggestedQuestionUsed]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(e) {
    e.preventDefault();
    if (!input.trim() || loading || !hasDocuments) return;

    const question = input.trim();
    setInput("");
    const msgId = crypto.randomUUID();
    const tokenBuffer = [];

    setMessages((prev) => [
      ...prev,
      { role: "user", content: question },
      { id: msgId, role: "assistant", content: "", sources: [], loading: true },
    ]);
    setLoading(true);

    try {
      await streamChat(
        question,
        currentWorkspace,
        {
          onToken: (token) => {
            tokenBuffer.push(token);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === msgId ? { ...m, content: m.content + token } : m
              )
            );
          },
          onDone: (event) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === msgId
                  ? {
                      ...m,
                      sources: event.sources ?? [],
                      retrieval_method: event.retrieval_method,
                      loading: false,
                    }
                  : m
              )
            );
            onEvalEntry?.({ query: question, answer: tokenBuffer.join("") });
          },
          onError: (message) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === msgId
                  ? { ...m, content: `Error: ${message}`, loading: false }
                  : m
              )
            );
          },
        },
        filterDocs.length > 0 ? filterDocs : null
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex-1 flex flex-col bg-gray-50">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <svg className="w-16 h-16 text-indigo-200 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1"
                d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
              />
            </svg>
            <p className="text-lg font-medium text-gray-500 mb-1">
              {hasDocuments ? "Ask a question about your documents" : "Upload documents to get started"}
            </p>
            <p className="text-sm text-gray-400">
              {hasDocuments
                ? "Prism will find answers and cite sources"
                : "Drop PDF, TXT, CSV files or paste a URL in the sidebar"}
            </p>
          </div>
        )}
        {messages.map((msg, i) => (
          <MessageBubble key={msg.id ?? i} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Filter badge */}
      {filterDocs.length > 0 && (
        <div className="px-4 pt-2 max-w-4xl mx-auto w-full">
          <div className="flex items-center gap-2 text-xs text-indigo-600 bg-indigo-50 border border-indigo-200 rounded-lg px-3 py-1.5">
            <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2a1 1 0 01-.293.707L13 13.414V19a1 1 0 01-.553.894l-4 2A1 1 0 017 21v-7.586L3.293 6.707A1 1 0 013 6V4z" />
            </svg>
            <span className="truncate flex-1">
              Scoped to: {filterDocs.join(", ")}
            </span>
            <button
              type="button"
              onClick={onFilterClear}
              className="shrink-0 text-indigo-400 hover:text-indigo-600 transition-colors font-medium"
            >
              ×
            </button>
          </div>
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleSend} className="p-4 bg-white border-t border-gray-100">
        <div className="flex gap-3 max-w-4xl mx-auto">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              filterDocs.length > 0
                ? `Searching ${filterDocs.length} selected doc${filterDocs.length > 1 ? "s" : ""}...`
                : hasDocuments
                ? "Ask anything — searching docs + web..."
                : "Upload documents first to start chatting"
            }
            className="flex-1 px-4 py-3 border border-gray-200 rounded-xl text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-400 transition-shadow"
            disabled={loading || !hasDocuments}
          />
          <button
            type="submit"
            disabled={loading || !input.trim() || !hasDocuments}
            className="px-6 py-3 bg-indigo-600 text-white rounded-xl text-sm font-medium hover:bg-indigo-700 disabled:bg-indigo-200 disabled:cursor-not-allowed transition-colors shadow-sm"
          >
            {loading ? "..." : "Send"}
          </button>
        </div>
      </form>
    </div>
  );
}
