"""
Phase 2 Step 3 — RAG Retriever

Thin wrapper around the ChromaDB vector store that exposes
similarity search for use by the LangGraph chat workflow.

Tools used:
  - langchain-chroma  : ChromaDB vector store
  - langchain-huggingface : BAAI/bge-small-en-v1.5 embeddings
"""

from __future__ import annotations

import logging
from pathlib import Path

from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_community.embeddings import HuggingFaceEmbeddings

from src.rag.indexer import CHROMA_DIR, COLLECTION_NAME, EMBED_MODEL

logger = logging.getLogger(__name__)

TOP_K = 5


def _get_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=EMBED_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def load_vectorstore(chroma_dir: Path = CHROMA_DIR) -> Chroma:
    """Load the persisted ChromaDB vector store. Raises if index not yet built."""
    if not chroma_dir.exists() or not list(chroma_dir.iterdir()):
        raise FileNotFoundError(
            f"ChromaDB index not found at {chroma_dir}. "
            "Run `python -m src.rag.indexer` first."
        )
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=_get_embeddings(),
        persist_directory=str(chroma_dir),
    )


def retrieve(question: str, vectorstore: Chroma, k: int = TOP_K) -> list[Document]:
    """
    Retrieve the top-k most relevant document chunks for a question.

    Returns a list of LangChain Document objects, each with:
      .page_content  : the chunk text
      .metadata      : {"source": filename, "page": page_number}
    """
    docs = vectorstore.similarity_search(question, k=k)
    logger.debug("Retrieved %d docs for: %r", len(docs), question)
    return docs


def format_passages(docs: list[Document]) -> str:
    """Format retrieved documents as a numbered passage block for prompts."""
    lines = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page", "?")
        lines.append(f"[{i}] (Source: {source}, page {page})")
        lines.append(doc.page_content.strip())
        lines.append("")
    return "\n".join(lines)
