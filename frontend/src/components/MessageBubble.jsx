import SourceExpander from "./SourceExpander";

function WebSourcesList({ sources }) {
  const webSources = sources?.filter((s) => s.source_type === "web") ?? [];
  if (webSources.length === 0) return null;

  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {webSources.map((s, i) => (
        <a
          key={i}
          href={s.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-xs bg-emerald-50 border border-emerald-200 text-emerald-700 hover:bg-emerald-100 hover:border-emerald-300 px-2.5 py-1.5 rounded-lg transition-colors max-w-[220px]"
          title={s.url}
        >
          <svg className="w-3 h-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
          <span className="truncate">{s.title || new URL(s.url).hostname}</span>
        </a>
      ))}
    </div>
  );
}


function CitedText({ text, onCitationClick }) {
  if (!text) return null;
  const parts = text.split(/(\[\d+\])/g);
  return (
    <>
      {parts.map((part, i) => {
        const match = part.match(/^\[(\d+)\]$/);
        if (match) {
          const idx = parseInt(match[1], 10);
          return (
            <sup
              key={i}
              onClick={() => onCitationClick(idx)}
              className="ml-0.5 text-indigo-500 font-semibold cursor-pointer hover:text-indigo-700 text-xs select-none"
              title={`Jump to source [${idx}]`}
            >
              [{idx}]
            </sup>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";

  function handleCitationClick(idx) {
    const el = document.getElementById(`source-${idx}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-2xl rounded-2xl px-5 py-3.5 ${
          isUser
            ? "bg-indigo-600 text-white"
            : "bg-white text-gray-800 shadow-sm"
        }`}
      >
        <p className="text-sm whitespace-pre-wrap leading-relaxed">
          {isUser ? (
            message.content
          ) : message.loading && !message.content ? (
            <span className="inline-flex items-center gap-1 text-indigo-400">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce [animation-delay:-0.3s]" />
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce [animation-delay:-0.15s]" />
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" />
            </span>
          ) : (
            <>
              <CitedText text={message.content} onCitationClick={handleCitationClick} />
              {message.loading && (
                <span className="inline-block w-0.5 h-4 bg-indigo-400 animate-pulse ml-0.5 align-middle" />
              )}
            </>
          )}
        </p>

        {!isUser && !message.loading && message.sources && (
          <WebSourcesList sources={message.sources} />
        )}

        {!isUser && !message.loading && message.sources && (
          <SourceExpander sources={message.sources} />
        )}
      </div>
    </div>
  );
}
