import json

from langchain_groq import ChatGroq

from server.utils import load_config, setup_logger

logger = setup_logger(__name__)

FAITHFULNESS_PROMPT = """
You are an evaluation judge. Given a context and an answer, score how faithful
the answer is to the context on a scale of 1-5.

1 = Answer contradicts or ignores the context entirely
2 = Answer uses context minimally, adds significant unsupported claims
3 = Answer mostly uses context with minor unsupported additions
4 = Answer is well-grounded in context with trivial additions only
5 = Answer is entirely and accurately derived from the context

Context:
{context}

Answer:
{answer}

Respond ONLY with valid JSON: {{"score": <int>, "reason": "<one sentence>"}}
"""


def score_faithfulness(answer: str, source_chunks: list[dict]) -> dict:
    """
    Call LLM with FAITHFULNESS_PROMPT.
    Parse JSON response.
    Return dict with score, reason, raw_response.
    Handle JSON parse errors gracefully — return score: -1 on failure.
    """
    config = load_config()
    llm_config = config.get("llm", {})

    context = "\n\n".join(chunk.get("content", "") for chunk in source_chunks)

    prompt = FAITHFULNESS_PROMPT.format(context=context, answer=answer)

    try:
        llm = ChatGroq(
            model=llm_config["model"],
            api_key=_get_api_key(),
            temperature=0.0,
            max_tokens=200,
        )

        response = llm.invoke(prompt)
        raw = response.content.strip()

        parsed = json.loads(raw)
        return {
            "score": parsed.get("score", -1),
            "reason": parsed.get("reason", ""),
            "raw_response": raw,
        }
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse faithfulness JSON: {raw}")
        return {"score": -1, "reason": "JSON parse error", "raw_response": raw}
    except Exception as e:
        logger.error(f"Faithfulness scoring failed: {e}")
        return {"score": -1, "reason": str(e), "raw_response": ""}


def _get_api_key() -> str:
    """Load Groq API key from environment."""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    return os.getenv("GROQ_API_KEY", "")
