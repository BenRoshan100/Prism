import json
import os
import re

from server.utils import load_config, setup_logger

logger = setup_logger(__name__)

_SAMPLE_CHARS = 3000


def _get_llm():
    from langchain_groq import ChatGroq
    config = load_config()
    return ChatGroq(
        model=config["llm"]["model"],
        api_key=os.environ.get("GROQ_API_KEY", ""),
        temperature=0.3,
        max_tokens=600,
    )


def generate_briefing(doc_name: str, text_sample: str) -> dict:
    """Generate 5-bullet summary + 3 suggested questions for a document.

    Returns empty lists if LLM call fails — briefing is non-critical.
    """
    empty = {"doc_name": doc_name, "summary": [], "suggested_questions": []}
    try:
        llm = _get_llm()
        prompt = (
            f"Analyze this document excerpt and respond with valid JSON only.\n"
            f"Document: {doc_name}\n\n"
            f"Content:\n{text_sample[:_SAMPLE_CHARS]}\n\n"
            f'Return exactly: {{"summary": ["5 bullet strings"], "suggested_questions": ["3 question strings"]}}'
        )
        from langchain_core.messages import HumanMessage
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = response.content.strip()

        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        # Extract JSON object — handles LLM preamble text before the JSON
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON object in LLM response: {raw[:100]}")
        cleaned = re.sub(r",\s*([}\]])", r"\1", match.group())  # strip trailing commas
        data = json.loads(cleaned)
        return {
            "doc_name": doc_name,
            "summary": data.get("summary", [])[:5],
            "suggested_questions": data.get("suggested_questions", [])[:3],
        }
    except Exception as e:
        logger.warning("Briefing generation failed for %s: %s", doc_name, e)
        return empty
