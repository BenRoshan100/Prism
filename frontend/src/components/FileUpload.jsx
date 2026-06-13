import { useState, useRef } from "react";
import { uploadFiles, uploadUrl } from "../api";

export default function FileUpload({ onUploadComplete, onBriefing }) {
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState("file"); // "file" | "url"
  const [urlInput, setUrlInput] = useState("");
  const fileInputRef = useRef(null);

  async function handleFiles(files) {
    if (!files.length) return;
    setUploading(true);
    setError(null);
    try {
      const data = await uploadFiles(files);
      onUploadComplete(data.documents);
      if (data.briefing && onBriefing) onBriefing(data.briefing);
    } catch (err) {
      setError(err.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleUrlSubmit(e) {
    e.preventDefault();
    const url = urlInput.trim();
    if (!url) return;
    setUploading(true);
    setError(null);
    try {
      const data = await uploadUrl(url);
      onUploadComplete(data.documents);
      if (data.briefing && onBriefing) onBriefing(data.briefing);
      setUrlInput("");
    } catch (err) {
      setError(err.response?.data?.detail || "URL ingestion failed");
    } finally {
      setUploading(false);
    }
  }

  function handleDrop(e) {
    e.preventDefault();
    setDragOver(false);
    handleFiles(Array.from(e.dataTransfer.files));
  }

  return (
    <div>
      {/* Tab switcher */}
      <div className="flex gap-1 mb-3">
        <button
          onClick={() => setTab("file")}
          className={`flex-1 text-xs py-1.5 rounded-lg font-medium transition-colors ${
            tab === "file"
              ? "bg-indigo-600 text-white"
              : "bg-gray-100 text-gray-500 hover:bg-gray-200"
          }`}
        >
          File
        </button>
        <button
          onClick={() => setTab("url")}
          className={`flex-1 text-xs py-1.5 rounded-lg font-medium transition-colors ${
            tab === "url"
              ? "bg-indigo-600 text-white"
              : "bg-gray-100 text-gray-500 hover:bg-gray-200"
          }`}
        >
          URL
        </button>
      </div>

      {tab === "file" ? (
        <>
          <div
            onClick={() => fileInputRef.current?.click()}
            onDrop={handleDrop}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            className={`border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition-all ${
              dragOver
                ? "border-indigo-500 bg-indigo-50"
                : "border-gray-200 hover:border-indigo-300 hover:bg-indigo-50/50"
            }`}
          >
            {uploading ? (
              <div className="flex flex-col items-center gap-2">
                <svg className="w-6 h-6 text-indigo-500 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                <p className="text-sm text-indigo-600 font-medium">Processing...</p>
              </div>
            ) : (
              <>
                <svg className="w-8 h-8 text-indigo-400 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5"
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                <p className="text-sm text-gray-600">Drop files here</p>
                <p className="text-xs text-gray-400 mt-1">PDF, TXT, or CSV</p>
              </>
            )}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.txt,.csv"
            className="hidden"
            onChange={(e) => handleFiles(Array.from(e.target.files))}
          />
        </>
      ) : (
        <form onSubmit={handleUrlSubmit} className="space-y-2">
          <input
            type="url"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            placeholder="https://example.com/article"
            className="w-full px-3 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            disabled={uploading}
          />
          <button
            type="submit"
            disabled={uploading || !urlInput.trim()}
            className="w-full py-2 bg-indigo-600 text-white rounded-xl text-sm font-medium hover:bg-indigo-700 disabled:bg-indigo-200 disabled:cursor-not-allowed transition-colors"
          >
            {uploading ? "Ingesting..." : "Ingest URL"}
          </button>
        </form>
      )}

      {error && <p className="text-xs text-red-500 mt-2">{error}</p>}
    </div>
  );
}
