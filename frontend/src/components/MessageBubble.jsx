import SourceExpander from "./SourceExpander";

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
