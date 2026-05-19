"""
Phase 2 Step 4 — LangGraph RAG Chat Workflow

3-node graph:
  retrieve  → generate → validate
                  ↑           |
                  └── retry ──┘  (max MAX_RETRIES times, then accept)

Tools used:
  - langgraph   : StateGraph, conditional edges
  - langchain-groq : ChatGroq (llama-3.3-70b-versatile)
  - langchain-chroma : vectorstore loaded via retriever.load_vectorstore()
"""

from __future__ import annotations

import logging
import os
import re
from typing import Annotated

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from src.rag.retriever import format_passages, load_vectorstore, retrieve

load_dotenv()

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
MODEL_NAME = "llama-3.3-70b-versatile"

# ── Prompt templates ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are SentinelPH, a dengue intelligence assistant specialised in the Philippines.
Answer the user's question using ONLY the numbered passages provided.
For every factual claim, cite the passage number inline in square brackets, e.g. [1] or [2][3].
If the passages do not contain enough information to answer, say so explicitly — do not cite passages in that case.
Do NOT invent facts or cite passage numbers that were not provided.
Do NOT add a separate sentence explaining which passage supports which claim — let the inline citations speak for themselves.
"""

GENERATION_PROMPT = """\
PASSAGES:
{passages}

QUESTION: {question}

Write a concise, accurate answer with inline citations [1], [2], … referencing the passages above.
"""

REFINEMENT_PROMPT = """\
Your previous answer had the following issue:
{feedback}

PASSAGES:
{passages}

QUESTION: {question}

Rewrite the answer, ensuring every factual claim is supported by a cited passage number.
"""

VALIDATOR_PROMPT = """\
You are a strict citation auditor.

The assistant gave this answer:
<answer>
{answer}
</answer>

The valid passage numbers are: {valid_ids}

Task: Check that every factual claim in the answer is supported by at least one cited passage number in square brackets.
Respond with exactly one of:
  PASS   — all claims are cited
  FAIL: <short description of the first uncited claim>

Do NOT output anything else.
"""

# ── State ────────────────────────────────────────────────────────────────────

class RAGState(TypedDict):
    question: str
    passages_text: str
    valid_ids: list[int]
    answer: str
    attempts: int
    valid: bool
    feedback: str


# ── Helpers ──────────────────────────────────────────────────────────────────

_vectorstore = None  # cached after first load; embedding model loads once per process


def _get_vectorstore():
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = load_vectorstore()
    return _vectorstore


def _get_llm() -> ChatGroq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY not set in environment / .env file")
    return ChatGroq(model=MODEL_NAME, temperature=0, api_key=api_key)


# ── Node functions ────────────────────────────────────────────────────────────

def node_retrieve(state: RAGState) -> dict:
    """Load vectorstore and retrieve top-k passages for the question."""
    vs = _get_vectorstore()
    docs = retrieve(state["question"], vs)
    passages_text = format_passages(docs)
    valid_ids = list(range(1, len(docs) + 1))
    logger.debug("Retrieved %d passages", len(docs))
    return {
        "passages_text": passages_text,
        "valid_ids": valid_ids,
        "attempts": 0,
        "valid": False,
        "feedback": "",
        "answer": "",
    }


def node_generate(state: RAGState) -> dict:
    """Generate (or refine) an answer using the retrieved passages."""
    llm = _get_llm()

    if state["attempts"] == 0:
        user_content = GENERATION_PROMPT.format(
            passages=state["passages_text"],
            question=state["question"],
        )
    else:
        user_content = REFINEMENT_PROMPT.format(
            feedback=state["feedback"],
            passages=state["passages_text"],
            question=state["question"],
        )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]
    response = llm.invoke(messages)
    answer = response.content.strip()
    attempts = state["attempts"] + 1
    logger.debug("Generated answer (attempt %d)", attempts)
    return {"answer": answer, "attempts": attempts}


def node_validate(state: RAGState) -> dict:
    """Check that every factual claim in the answer cites a valid passage ID."""
    llm = _get_llm()
    valid_ids_str = ", ".join(str(i) for i in state["valid_ids"])

    messages = [
        HumanMessage(
            content=VALIDATOR_PROMPT.format(
                answer=state["answer"],
                valid_ids=valid_ids_str,
            )
        )
    ]
    response = llm.invoke(messages)
    verdict = response.content.strip()
    logger.debug("Validator verdict: %s", verdict)

    if verdict.upper().startswith("PASS"):
        return {"valid": True, "feedback": ""}

    # Extract feedback after "FAIL:"
    feedback = re.sub(r"^FAIL[:\s]*", "", verdict, flags=re.IGNORECASE).strip()
    return {"valid": False, "feedback": feedback}


# ── Routing ──────────────────────────────────────────────────────────────────

def _should_retry(state: RAGState) -> str:
    """Continue to END if valid or retries exhausted; else regenerate."""
    if state["valid"] or state["attempts"] >= MAX_RETRIES:
        return "end"
    return "generate"


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(RAGState)

    graph.add_node("retrieve", node_retrieve)
    graph.add_node("generate", node_generate)
    graph.add_node("validate", node_validate)

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "validate")
    graph.add_conditional_edges(
        "validate",
        _should_retry,
        {"end": END, "generate": "generate"},
    )

    return graph.compile()


# ── Public API ────────────────────────────────────────────────────────────────

_graph = None  # module-level singleton; compiled once per process


def ask(question: str) -> dict:
    """
    Run the RAG workflow for a single question.

    Returns
    -------
    dict with keys:
      "answer"   : str — the final answer with inline citations
      "attempts" : int — how many generation attempts were made
      "valid"    : bool — whether the validator passed
    """
    global _graph
    if _graph is None:
        _graph = build_graph()

    initial_state: RAGState = {
        "question": question,
        "passages_text": "",
        "valid_ids": [],
        "answer": "",
        "attempts": 0,
        "valid": False,
        "feedback": "",
    }

    final_state = _graph.invoke(initial_state)
    return {
        "answer": final_state["answer"],
        "attempts": final_state["attempts"],
        "valid": final_state["valid"],
    }
