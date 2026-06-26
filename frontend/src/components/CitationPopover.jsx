import { useEffect, useRef } from "react";

export default function CitationPopover({ source, anchorRect, onClose }) {
  const popoverRef = useRef(null);

  useEffect(() => {
    function handleMouseDown(e) {
      if (popoverRef.current && !popoverRef.current.contains(e.target)) {
        onClose();
      }
    }
    document.addEventListener("mousedown", handleMouseDown);
    return () => document.removeEventListener("mousedown", handleMouseDown);
  }, [onClose]);

  if (!source || !anchorRect) return null;

  const openAbove = anchorRect.top > window.innerHeight * 0.6;
  const left = Math.min(anchorRect.left, window.innerWidth - 336); // 320px + 16px buffer

  const style = {
    position: "fixed",
    left: `${Math.max(8, left)}px`,
    width: "320px",
    zIndex: 50,
    ...(openAbove
      ? { bottom: `${window.innerHeight - anchorRect.top + 8}px` }
      : { top: `${anchorRect.bottom + 8}px` }),
  };

  const isWeb = source.source_type === "web";
  const isPdf = !isWeb && typeof source.source === "string" &&
    source.source.toLowerCase().endsWith(".pdf");
  const pageNum = source.page != null ? source.page + 1 : null; // 0-indexed → 1-indexed
  const API_BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

  return (
    <div
      ref={popoverRef}
      style={style}
      className="bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100 bg-gray-50">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className={`text-[10px] font-semibold px-1.5 py-0.5 rounded shrink-0 ${
              isWeb
                ? "bg-emerald-100 text-emerald-700"
                : "bg-indigo-100 text-indigo-700"
            }`}
          >
            {isWeb ? "web" : isPdf ? "pdf" : "file"}
          </span>
          <span className="text-xs font-medium text-gray-700 truncate">
            {isWeb ? source.title || source.url : source.source}
          </span>
        </div>
        {pageNum != null && (
          <span className="text-[10px] text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded shrink-0 ml-2">
            Page {pageNum}
          </span>
        )}
      </div>

      {/* Body */}
      <div className="px-3 py-2.5 max-h-48 overflow-y-auto">
        <p className="text-xs text-gray-600 leading-relaxed">{source.content}</p>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between px-3 py-2 border-t border-gray-100 bg-gray-50">
        <div className="flex gap-2">
          {source.rerank_score != null && (
            <span className="text-[10px] text-indigo-500 bg-indigo-50 px-1.5 py-0.5 rounded font-medium">
              rerank: {Number(source.rerank_score).toFixed(2)}
            </span>
          )}
        </div>
        {isWeb && source.url && (
          <a
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[10px] text-emerald-600 hover:text-emerald-800 font-medium"
          >
            Open source →
          </a>
        )}
        {isPdf && pageNum != null && (
          <a
            href={`${API_BASE}/api/files/${encodeURIComponent(source.source)}#page=${pageNum}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[10px] text-indigo-600 hover:text-indigo-800 font-medium"
          >
            Open page {pageNum} →
          </a>
        )}
      </div>
    </div>
  );
}
