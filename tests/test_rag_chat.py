"""Tests for the LangGraph RAG chat workflow."""

from unittest.mock import MagicMock, patch

import pytest


class TestChatWorkflow:
    def test_graph_builds_without_error(self) -> None:
        from src.rag.chat import build_graph

        graph = build_graph()
        assert graph is not None

    def test_rag_state_fields(self) -> None:
        from src.rag.chat import RAGState

        state: RAGState = {
            "question": "What is dengue?",
            "passages_text": "",
            "valid_ids": [],
            "answer": "",
            "attempts": 0,
            "valid": False,
            "feedback": "",
        }
        assert state["question"] == "What is dengue?"
        assert state["attempts"] == 0

    def test_should_retry_when_valid(self) -> None:
        from src.rag.chat import _should_retry, RAGState

        state: RAGState = {
            "question": "q",
            "passages_text": "",
            "valid_ids": [1, 2],
            "answer": "answer [1]",
            "attempts": 1,
            "valid": True,
            "feedback": "",
        }
        assert _should_retry(state) == "end"

    def test_should_retry_when_retries_exhausted(self) -> None:
        from src.rag.chat import _should_retry, MAX_RETRIES, RAGState

        state: RAGState = {
            "question": "q",
            "passages_text": "",
            "valid_ids": [1],
            "answer": "no citation",
            "attempts": MAX_RETRIES,
            "valid": False,
            "feedback": "uncited claim",
        }
        assert _should_retry(state) == "end"

    def test_should_retry_when_invalid_and_retries_remain(self) -> None:
        from src.rag.chat import _should_retry, RAGState

        state: RAGState = {
            "question": "q",
            "passages_text": "",
            "valid_ids": [1],
            "answer": "no citation",
            "attempts": 1,
            "valid": False,
            "feedback": "missing citation",
        }
        assert _should_retry(state) == "generate"

    @patch("src.rag.chat.load_vectorstore")
    @patch("src.rag.chat.retrieve")
    @patch("src.rag.chat.format_passages")
    @patch("src.rag.chat._get_llm")
    def test_ask_returns_expected_keys(
        self,
        mock_get_llm: MagicMock,
        mock_format: MagicMock,
        mock_retrieve: MagicMock,
        mock_load_vs: MagicMock,
    ) -> None:
        from langchain_core.documents import Document
        from src.rag.chat import ask

        # Mock vectorstore + retrieval
        mock_load_vs.return_value = MagicMock()
        mock_retrieve.return_value = [
            Document(page_content="Dengue is viral.", metadata={"source": "a.pdf", "page": 1})
        ]
        mock_format.return_value = "[1] (Source: a.pdf, page 1)\nDengue is viral.\n"

        # Mock LLM: generate returns cited answer; validator returns PASS
        llm_mock = MagicMock()
        generate_response = MagicMock()
        generate_response.content = "Dengue is a viral disease [1]."
        validate_response = MagicMock()
        validate_response.content = "PASS"
        llm_mock.invoke.side_effect = [generate_response, validate_response]
        mock_get_llm.return_value = llm_mock

        # Reset module-level singleton so mock is used
        import src.rag.chat as chat_mod
        chat_mod._graph = None

        result = ask("What is dengue?")

        assert "answer" in result
        assert "attempts" in result
        assert "valid" in result
        assert result["valid"] is True
        assert result["attempts"] == 1

    @patch("src.rag.chat.load_vectorstore")
    @patch("src.rag.chat.retrieve")
    @patch("src.rag.chat.format_passages")
    @patch("src.rag.chat._get_llm")
    def test_ask_retries_on_invalid(
        self,
        mock_get_llm: MagicMock,
        mock_format: MagicMock,
        mock_retrieve: MagicMock,
        mock_load_vs: MagicMock,
    ) -> None:
        from langchain_core.documents import Document
        from src.rag.chat import ask

        mock_load_vs.return_value = MagicMock()
        mock_retrieve.return_value = [
            Document(page_content="Dengue is viral.", metadata={"source": "a.pdf", "page": 1})
        ]
        mock_format.return_value = "[1] (Source: a.pdf, page 1)\nDengue is viral.\n"

        llm_mock = MagicMock()
        # Attempt 1: uncited answer → FAIL → retry
        # Attempt 2: cited answer → PASS
        gen_resp1 = MagicMock(); gen_resp1.content = "Dengue is viral."
        val_resp1 = MagicMock(); val_resp1.content = "FAIL: no citation"
        gen_resp2 = MagicMock(); gen_resp2.content = "Dengue is viral [1]."
        val_resp2 = MagicMock(); val_resp2.content = "PASS"
        llm_mock.invoke.side_effect = [gen_resp1, val_resp1, gen_resp2, val_resp2]
        mock_get_llm.return_value = llm_mock

        import src.rag.chat as chat_mod
        chat_mod._graph = None

        result = ask("What is dengue?")

        assert result["attempts"] == 2
        assert result["valid"] is True

    def test_get_llm_raises_without_api_key(self) -> None:
        import os
        from src.rag.chat import _get_llm

        original = os.environ.pop("GROQ_API_KEY", None)
        try:
            with pytest.raises(EnvironmentError, match="GROQ_API_KEY"):
                _get_llm()
        finally:
            if original is not None:
                os.environ["GROQ_API_KEY"] = original
