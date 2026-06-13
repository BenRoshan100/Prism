from unittest.mock import patch, MagicMock
import json
import pytest
from server.briefing import generate_briefing


def _mock_llm_response(summary: list, questions: list):
    payload = json.dumps({"summary": summary, "suggested_questions": questions})
    mock_response = MagicMock()
    mock_response.content = payload
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    return mock_llm


SAMPLE_TEXT = "This is a document about machine learning. " * 100


def test_generate_briefing_returns_required_keys():
    mock_llm = _mock_llm_response(
        ["Point 1", "Point 2", "Point 3", "Point 4", "Point 5"],
        ["Q1?", "Q2?", "Q3?"],
    )
    with patch("server.briefing._get_llm", return_value=mock_llm):
        result = generate_briefing("test.pdf", SAMPLE_TEXT)
    assert "doc_name" in result
    assert "summary" in result
    assert "suggested_questions" in result


def test_generate_briefing_limits_to_five_bullets():
    mock_llm = _mock_llm_response(
        ["P1", "P2", "P3", "P4", "P5", "P6", "P7"],
        ["Q1?", "Q2?", "Q3?"],
    )
    with patch("server.briefing._get_llm", return_value=mock_llm):
        result = generate_briefing("test.pdf", SAMPLE_TEXT)
    assert len(result["summary"]) <= 5


def test_generate_briefing_limits_to_three_questions():
    mock_llm = _mock_llm_response(
        ["P1", "P2", "P3", "P4", "P5"],
        ["Q1?", "Q2?", "Q3?", "Q4?"],
    )
    with patch("server.briefing._get_llm", return_value=mock_llm):
        result = generate_briefing("test.pdf", SAMPLE_TEXT)
    assert len(result["suggested_questions"]) <= 3


def test_generate_briefing_strips_markdown_fences():
    mock_response = MagicMock()
    mock_response.content = '```json\n{"summary": ["P1", "P2", "P3", "P4", "P5"], "suggested_questions": ["Q1?", "Q2?", "Q3?"]}\n```'
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    with patch("server.briefing._get_llm", return_value=mock_llm):
        result = generate_briefing("doc.pdf", SAMPLE_TEXT)
    assert len(result["summary"]) == 5


def test_generate_briefing_returns_empty_on_llm_failure():
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = Exception("LLM timeout")
    with patch("server.briefing._get_llm", return_value=mock_llm):
        result = generate_briefing("doc.pdf", SAMPLE_TEXT)
    assert result["summary"] == []
    assert result["suggested_questions"] == []
