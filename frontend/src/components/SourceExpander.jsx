import { useState } from "react";

export default function SourceExpander({ sources }) {
  const [open, setOpen] = useState(false);

  if (!sources || sources.length === 0) return null;

  return (
    <div className="mt-3">
      <button
        onClick={() => setOpen(!open)}
        className="text-xs text-indigo-500 hover:text-indigo-700 flex items-center gap-1.5 font-medium transition-colors"
      >
        <span>
          {open ? "Hide" : "Show"} sources ({sources.length})
        </span>
        <svg
          className={`w-3.5 h-3.5 transition-transform ${
            open ? "rotate-180" : ""
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {open && (
        <div className="mt-2.5 space-y-2">
          {sources.map((src, i) => {
            const isWeb = src.source_type === "web";
            return (
              <div
                key={i}
                className={`bg-white border-l-2 rounded-r-lg shadow-xs pl-3 pr-3 py-2.5 ${
                  isWeb ? "border-emerald-400" : "border-indigo-400"
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  {isWeb ? (
                    <a
                      href={src.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs font-semibold text-emerald-700 hover:underline truncate max-w-[200px]"
                      title={src.url}
                    >
                      {src.title || src.url}
                    </a>
                  ) : (
                    <span className="text-xs font-semibold text-indigo-700 truncate max-w-[200px]">
                      {src.source}
                    </span>
                  )}
                  <div className="flex gap-2 shrink-0 ml-2">
                    {isWeb && (
                      <span className="text-[10px] text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded font-medium">
                        web
                      </span>
                    )}
                    {src.page != null && (
                      <span className="text-[10px] text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">
                        Page {src.page + 1}
                      </span>
                    )}
                    {src.similarity_score != null && (
                      <span className="text-[10px] text-indigo-500 bg-indigo-50 px-1.5 py-0.5 rounded font-medium">
                        {src.similarity_score}
                      </span>
                    )}
                  </div>
                </div>
                <p className="text-xs text-gray-500 leading-relaxed">
                  {src.content.length > 200
                    ? src.content.slice(0, 200) + "..."
                    : src.content}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
