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

function FaithfulnessBadge({ faithfulness }) {
  if (!faithfulness || faithfulness.score < 0) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-gray-400 bg-gray-100 px-2.5 py-1 rounded-full">
        <span className="w-1.5 h-1.5 rounded-full bg-gray-400" />
        Eval failed
      </span>
    );
  }

  const { score, reason } = faithfulness;

  let dotColor, bgColor, textColor, label;
  if (score >= 4) {
    dotColor = "bg-green-500";
    bgColor = "bg-green-50";
    textColor = "text-green-700";
    label = "Faithful";
  } else if (score === 3) {
    dotColor = "bg-yellow-500";
    bgColor = "bg-yellow-50";
    textColor = "text-yellow-700";
    label = "Moderate";
  } else {
    dotColor = "bg-red-500";
    bgColor = "bg-red-50";
    textColor = "text-red-700";
    label = "Low";
  }

  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full ${bgColor} ${textColor}`}
        title={reason}
      >
        <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
        {label} ({score}/5)
      </span>
      <span className="group relative">
        <svg className="w-3.5 h-3.5 text-gray-400 cursor-help" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
        </svg>
        <span className="pointer-events-none absolute bottom-6 left-0 z-10 w-56 rounded-lg bg-gray-800 px-2.5 py-2 text-xs text-white opacity-0 group-hover:opacity-100 transition-opacity shadow-lg">
          LLM-as-judge score (1–5). Measures how grounded the answer is in the retrieved documents. 4–5 = faithful, 3 = partially supported, 1–2 = hallucination risk.
        </span>
      </span>
    </span>
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
          ) : (
            <CitedText
              text={message.content}
              onCitationClick={handleCitationClick}
            />
          )}
        </p>

        {!isUser && message.sources && (
          <WebSourcesList sources={message.sources} />
        )}

        {!isUser && message.faithfulness && (
          <div className="mt-3">
            <FaithfulnessBadge faithfulness={message.faithfulness} />
          </div>
        )}

        {!isUser && message.sources && (
          <SourceExpander sources={message.sources} />
        )}
      </div>
    </div>
  );
}
