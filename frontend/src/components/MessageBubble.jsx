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
    <span
      className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full ${bgColor} ${textColor}`}
      title={reason}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
      {label} ({score}/5)
    </span>
  );
}

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";

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
          {message.content}
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
