import { useState } from "react";
import { sendMessage } from "../api";
import MessageBubble from "./MessageBubble";

export default function ChatArea({ onEvalEntry, hasDocuments }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [webSearch, setWebSearch] = useState(false);

  async function handleSend(e) {
    e.preventDefault();
    if (!input.trim() || loading || !hasDocuments) return;

    const question = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: question, webSearch }]);
    setLoading(true);

    try {
      const data = await sendMessage(question, webSearch);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer,
          sources: data.sources,
          faithfulness: data.faithfulness,
        },
      ]);
      onEvalEntry({
        query: question,
        answer: data.answer,
        faithfulness_score: data.faithfulness.score,
        reason: data.faithfulness.reason,
      });
    } catch (err) {
      const detail = err.response?.data?.detail || err.message;
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Error: " + detail },
      ]);
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
            <svg
              className="w-16 h-16 text-indigo-200 mb-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1"
                d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
              />
            </svg>
            <p className="text-lg font-medium text-gray-500 mb-1">
              {hasDocuments
                ? "Ask a question about your documents"
                : "Upload documents to get started"}
            </p>
            <p className="text-sm text-gray-400">
              {hasDocuments
                ? "FinRAG will find answers and cite sources"
                : "Drop PDF, TXT, or CSV files in the sidebar"}
            </p>
          </div>
        )}
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-indigo-400 text-sm">
            <svg
              className="w-4 h-4 animate-spin"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
            <span>Thinking...</span>
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleSend} className="p-4 bg-white border-t border-gray-100">
        <div className="flex gap-3 max-w-4xl mx-auto">
          <button
            type="button"
            onClick={() => setWebSearch((v) => !v)}
            disabled={loading || !hasDocuments}
            title={webSearch ? "Web search ON — click to disable" : "Web search OFF — click to enable"}
            className={`shrink-0 p-3 rounded-xl border text-sm font-medium transition-colors shadow-sm ${
              webSearch
                ? "bg-emerald-50 border-emerald-300 text-emerald-700 hover:bg-emerald-100"
                : "bg-gray-50 border-gray-200 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            } disabled:opacity-40 disabled:cursor-not-allowed`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
            </svg>
          </button>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              hasDocuments
                ? webSearch
                  ? "Ask anything — searching docs + web..."
                  : "Ask about your documents..."
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
            Send
          </button>
        </div>
        {webSearch && hasDocuments && (
          <p className="text-center text-xs text-emerald-600 mt-2">
            Web search active — answers will include live web context
          </p>
        )}
      </form>
    </div>
  );
}
