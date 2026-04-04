import { useState, useRef } from "react";
import { uploadFiles } from "../api";

export default function FileUpload({ onUploadComplete }) {
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

  async function handleFiles(files) {
    if (!files.length) return;
    setUploading(true);
    setError(null);
    try {
      const data = await uploadFiles(files);
      onUploadComplete(data.documents);
    } catch (err) {
      setError(err.response?.data?.detail || "Upload failed");
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
      <div
        onClick={() => fileInputRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        className={`border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition-all ${
          dragOver
            ? "border-indigo-500 bg-indigo-50"
            : "border-gray-200 hover:border-indigo-300 hover:bg-indigo-50/50"
        }`}
      >
        {uploading ? (
          <div className="flex flex-col items-center gap-2">
            <svg
              className="w-6 h-6 text-indigo-500 animate-spin"
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
            <p className="text-sm text-indigo-600 font-medium">
              Processing...
            </p>
          </div>
        ) : (
          <>
            <svg
              className="w-8 h-8 text-indigo-400 mx-auto mb-2"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.5"
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
              />
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
      {error && <p className="text-xs text-red-500 mt-2">{error}</p>}
    </div>
  );
}
