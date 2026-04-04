from langchain_classic.memory import ConversationBufferWindowMemory

from server.utils import load_config, setup_logger

logger = setup_logger(__name__)


def create_memory(memory_key: str = "chat_history", max_token_limit: int = 2000) -> ConversationBufferWindowMemory:
    """
    Create LangChain ConversationBufferWindowMemory.
    memory_key = "chat_history"
    return_messages = True
    k = number of recent conversation turns to keep
    """
    config = load_config()
    max_token_limit = config.get("memory", {}).get("max_token_limit", max_token_limit)

    # Use window memory with k turns (approximate: ~200 tokens per turn)
    k_turns = max(1, max_token_limit // 200)

    memory = ConversationBufferWindowMemory(
        memory_key=memory_key,
        return_messages=True,
        output_key="answer",
        k=k_turns,
    )
    logger.info(f"Created conversation memory (k={k_turns} turns)")
    return memory


def get_memory_as_string(memory: ConversationBufferWindowMemory) -> str:
    """Return conversation history as formatted string for display in UI."""
    messages = memory.chat_memory.messages
    lines = []
    for msg in messages:
        role = "User" if msg.type == "human" else "Assistant"
        lines.append(f"{role}: {msg.content}")
    return "\n".join(lines)


def clear_memory(memory: ConversationBufferWindowMemory) -> None:
    """Clear all messages. Called on 'New Conversation' button."""
    memory.clear()
    logger.info("Conversation memory cleared")
