"""
Phase 2 Step 2 — RAG Corpus Indexer

Loads all PDFs from data/raw/rag_corpus/, splits into chunks, embeds with
BAAI/bge-small-en-v1.5, and persists to a ChromaDB vector store.

Tools used:
  - LangChain PyPDFLoader       : PDF text extraction
  - RecursiveCharacterTextSplitter : chunk documents
  - sentence-transformers       : BAAI/bge-small-en-v1.5 embeddings (CPU)
  - ChromaDB                    : local persistent vector store

Run once to build the index; re-run with force=True to rebuild.
"""

from __future__ import annotations

import logging
from pathlib import Path

from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

CORPUS_DIR = Path("data/raw/rag_corpus")
CHROMA_DIR = Path("data/chroma")
COLLECTION_NAME = "sentinel_ph_rag"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
EMBED_MODEL = "BAAI/bge-small-en-v1.5"


def _load_pdfs(corpus_dir: Path) -> list:
    """Load all PDFs in corpus_dir and return a flat list of LangChain Documents."""
    pdfs = sorted(corpus_dir.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"No PDFs found in {corpus_dir}")

    all_docs = []
    for pdf_path in pdfs:
        logger.info("Loading %s …", pdf_path.name)
        loader = PyPDFLoader(str(pdf_path))
        docs = loader.load()
        # Attach source filename to metadata for citation
        for doc in docs:
            doc.metadata["source"] = pdf_path.name
        all_docs.extend(docs)
        logger.info("  → %d pages", len(docs))

    logger.info("Total pages loaded: %d from %d PDFs", len(all_docs), len(pdfs))
    return all_docs


def _split(docs: list) -> list:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    logger.info("Split into %d chunks (size=%d, overlap=%d)", len(chunks), CHUNK_SIZE, CHUNK_OVERLAP)
    return chunks


def build_index(
    corpus_dir: Path = CORPUS_DIR,
    chroma_dir: Path = CHROMA_DIR,
    force: bool = False,
) -> Chroma:
    """
    Build (or load) the ChromaDB vector store from the RAG corpus PDFs.

    Parameters
    ----------
    corpus_dir : Path   Directory containing corpus PDFs.
    chroma_dir : Path   Where ChromaDB persists its data.
    force      : bool   Rebuild index even if it already exists.

    Returns
    -------
    Chroma vectorstore ready for similarity search.
    """
    chroma_dir.mkdir(parents=True, exist_ok=True)

    embeddings = HuggingFaceEmbeddings(
        model_name=EMBED_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    # If index already exists and force=False, just load it
    existing = list(chroma_dir.iterdir()) if chroma_dir.exists() else []
    if existing and not force:
        logger.info("Loading existing ChromaDB index from %s …", chroma_dir)
        vectorstore = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=embeddings,
            persist_directory=str(chroma_dir),
        )
        count = vectorstore._collection.count()
        logger.info("Loaded %d chunks from existing index.", count)
        return vectorstore

    logger.info("Building new ChromaDB index …")
    docs = _load_pdfs(corpus_dir)
    chunks = _split(docs)

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=str(chroma_dir),
    )
    count = vectorstore._collection.count()
    logger.info("Index built: %d chunks persisted to %s", count, chroma_dir)
    return vectorstore


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    vs = build_index(force=True)
    print(f"\nVector store ready. Total chunks: {vs._collection.count()}")

    # Quick sanity check
    results = vs.similarity_search("dengue symptoms philippines", k=3)
    print("\nTop-3 results for 'dengue symptoms philippines':")
    for i, doc in enumerate(results, 1):
        print(f"  [{i}] {doc.metadata.get('source','?')} p{doc.metadata.get('page','?')}: "
              f"{doc.page_content[:120].replace(chr(10),' ')} …")
