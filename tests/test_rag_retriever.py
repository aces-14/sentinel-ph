"""Tests for the RAG retriever module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

CHROMA_DIR = Path("data/chroma")


class TestRetriever:
    @pytest.fixture(autouse=True)
    def check_index(self) -> None:
        if not CHROMA_DIR.exists() or not list(CHROMA_DIR.iterdir()):
            pytest.skip("ChromaDB index not built — run src.rag.indexer first")

    def test_load_vectorstore_returns_chroma(self) -> None:
        from src.rag.retriever import load_vectorstore
        from langchain_chroma import Chroma

        vs = load_vectorstore()
        assert isinstance(vs, Chroma)

    def test_load_vectorstore_raises_without_index(self) -> None:
        from src.rag.retriever import load_vectorstore

        with pytest.raises(FileNotFoundError):
            load_vectorstore(chroma_dir=Path("data/__nonexistent__"))

    def test_retrieve_returns_documents(self) -> None:
        from src.rag.retriever import load_vectorstore, retrieve
        from langchain_core.documents import Document

        vs = load_vectorstore()
        docs = retrieve("dengue symptoms fever", vs, k=3)
        assert len(docs) == 3
        assert all(isinstance(d, Document) for d in docs)

    def test_retrieve_top_k_respected(self) -> None:
        from src.rag.retriever import load_vectorstore, retrieve

        vs = load_vectorstore()
        for k in (1, 3, 5):
            docs = retrieve("dengue Philippines", vs, k=k)
            assert len(docs) == k

    def test_documents_have_page_content(self) -> None:
        from src.rag.retriever import load_vectorstore, retrieve

        vs = load_vectorstore()
        docs = retrieve("dengue vaccine", vs, k=2)
        for doc in docs:
            assert doc.page_content.strip(), "Document has empty page_content"

    def test_documents_have_source_metadata(self) -> None:
        from src.rag.retriever import load_vectorstore, retrieve

        vs = load_vectorstore()
        docs = retrieve("aedes mosquito", vs, k=3)
        for doc in docs:
            assert "source" in doc.metadata, "Missing 'source' in metadata"
            assert doc.metadata["source"].endswith(".pdf")

    def test_format_passages_structure(self) -> None:
        from src.rag.retriever import format_passages
        from langchain_core.documents import Document

        docs = [
            Document(
                page_content="Dengue is a viral illness.",
                metadata={"source": "test.pdf", "page": 1},
            ),
            Document(
                page_content="Aedes aegypti is the primary vector.",
                metadata={"source": "test.pdf", "page": 2},
            ),
        ]
        result = format_passages(docs)
        assert "[1]" in result
        assert "[2]" in result
        assert "Source: test.pdf" in result
        assert "Dengue is a viral illness." in result

    def test_format_passages_empty_list(self) -> None:
        from src.rag.retriever import format_passages

        result = format_passages([])
        assert result == ""

    def test_retrieve_relevance_dengue_query(self) -> None:
        """Passages retrieved for a dengue-specific query should mention dengue."""
        from src.rag.retriever import load_vectorstore, retrieve

        vs = load_vectorstore()
        docs = retrieve("dengue hemorrhagic fever classification", vs, k=5)
        combined = " ".join(d.page_content.lower() for d in docs)
        assert "dengue" in combined, "Top passages contain no mention of 'dengue'"
