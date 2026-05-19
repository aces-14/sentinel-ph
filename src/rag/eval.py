"""
Phase 2 Step 6 — RAG Evaluation

Evaluates the RAG pipeline against a curated Q&A set.

Metrics:
  - Retrieval recall  : fraction of gold keywords found in retrieved passages
  - Answer accuracy   : fraction of expected keywords present in the answer
  - Citation rate     : fraction of answers that contain at least one [N] citation

Usage:
    python -m src.rag.eval
    python -m src.rag.eval --questions 10   # run first N questions only
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from dataclasses import dataclass, field

from src.rag.chat import ask
from src.rag.retriever import format_passages, load_vectorstore, retrieve

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Evaluation dataset ────────────────────────────────────────────────────────
# Each entry: question, gold_keywords (expected in answer), retrieval_keywords
# (expected in passages).  All keywords are lowercase; partial match is used.

EVAL_SET = [
    {
        "question": "What are the main clinical signs of dengue fever?",
        "gold_keywords": ["fever", "headache", "rash", "myalgia"],
        "retrieval_keywords": ["clinical", "symptoms", "fever"],
    },
    {
        "question": "What is dengue hemorrhagic fever and how is it classified?",
        "gold_keywords": ["hemorrhagic", "grade", "platelet", "plasma leakage"],
        "retrieval_keywords": ["hemorrhagic", "classification", "grade"],
    },
    {
        "question": "How is dengue transmitted and what is the primary vector?",
        "gold_keywords": ["aedes", "mosquito", "bite", "aegypti"],
        "retrieval_keywords": ["aedes", "vector", "transmission"],
    },
    {
        "question": "What laboratory tests confirm dengue infection?",
        "gold_keywords": ["ns1", "pcr", "igg", "igm", "serology"],
        "retrieval_keywords": ["laboratory", "diagnosis", "ns1"],
    },
    {
        "question": "What is the dengue incubation period?",
        "gold_keywords": ["days", "incubation"],
        "retrieval_keywords": ["incubation", "period"],
    },
    {
        "question": "How should dengue patients be managed at home?",
        "gold_keywords": ["hydration", "paracetamol", "rest", "fluid"],
        "retrieval_keywords": ["outpatient", "home", "management"],
    },
    {
        "question": "When should a dengue patient be hospitalised?",
        "gold_keywords": ["warning sign", "bleed", "hospital", "admission"],
        "retrieval_keywords": ["warning", "hospitalisation", "severe"],
    },
    {
        "question": "What are the warning signs of severe dengue?",
        "gold_keywords": ["abdominal pain", "persistent vomiting", "bleeding", "lethargy"],
        "retrieval_keywords": ["warning signs", "severe", "danger"],
    },
    {
        "question": "What fluids are recommended for dengue shock syndrome?",
        "gold_keywords": ["crystalloid", "iv fluid", "colloid", "shock"],
        "retrieval_keywords": ["shock", "fluid", "resuscitation"],
    },
    {
        "question": "What is dengue serotype and how many serotypes exist?",
        "gold_keywords": ["serotype", "denv", "four"],
        "retrieval_keywords": ["serotype", "denv"],
    },
    {
        "question": "What is the dengue burden in the Philippines?",
        "gold_keywords": ["philippines", "cases", "mortality"],
        "retrieval_keywords": ["philippines", "burden", "epidemiology"],
    },
    {
        "question": "What seasonal patterns characterise dengue in the Philippines?",
        "gold_keywords": ["rain", "season", "peak", "monsoon"],
        "retrieval_keywords": ["seasonal", "Philippines", "pattern"],
    },
    {
        "question": "How does rainfall affect dengue transmission?",
        "gold_keywords": ["rainfall", "breeding", "mosquito", "vector"],
        "retrieval_keywords": ["rainfall", "climate", "weather"],
    },
    {
        "question": "What is the role of temperature in dengue epidemiology?",
        "gold_keywords": ["temperature", "replication", "extrinsic incubation"],
        "retrieval_keywords": ["temperature", "climate", "incubation"],
    },
    {
        "question": "What personal protective measures prevent dengue?",
        "gold_keywords": ["repellent", "clothing", "mosquito net", "prevent"],
        "retrieval_keywords": ["prevention", "personal protection"],
    },
    {
        "question": "How can breeding sites for Aedes mosquitoes be eliminated?",
        "gold_keywords": ["stagnant water", "container", "larvae", "breeding"],
        "retrieval_keywords": ["breeding site", "vector control", "aedes"],
    },
    {
        "question": "What is fogging and is it effective against dengue?",
        "gold_keywords": ["fogging", "insecticide", "adult", "spray"],
        "retrieval_keywords": ["fogging", "insecticide", "vector control"],
    },
    {
        "question": "What dengue vaccines are available and for whom are they recommended?",
        "gold_keywords": ["dengvaxia", "vaccine", "seropositive", "age"],
        "retrieval_keywords": ["vaccine", "dengvaxia", "immunisation"],
    },
    {
        "question": "What is primary versus secondary dengue infection?",
        "gold_keywords": ["primary", "secondary", "antibody", "severe"],
        "retrieval_keywords": ["primary", "secondary", "infection", "immunity"],
    },
    {
        "question": "What is antibody-dependent enhancement in dengue?",
        "gold_keywords": ["antibody", "enhancement", "ade", "heterotypic"],
        "retrieval_keywords": ["antibody", "enhancement", "immune"],
    },
    {
        "question": "How is dengue surveillance conducted at the national level?",
        "gold_keywords": ["surveillance", "reporting", "sentinel", "weekly"],
        "retrieval_keywords": ["surveillance", "national", "monitoring"],
    },
    {
        "question": "What is the dengue case definition used by WHO?",
        "gold_keywords": ["case definition", "probable", "confirmed", "who"],
        "retrieval_keywords": ["case definition", "who", "classification"],
    },
    {
        "question": "What complications can arise from severe dengue?",
        "gold_keywords": ["organ impairment", "liver", "encephalitis", "myocarditis"],
        "retrieval_keywords": ["complications", "severe", "organ"],
    },
    {
        "question": "What is thrombocytopenia in the context of dengue?",
        "gold_keywords": ["platelet", "thrombocytopenia", "count", "below"],
        "retrieval_keywords": ["platelet", "thrombocytopenia"],
    },
    {
        "question": "How do children present differently with dengue compared to adults?",
        "gold_keywords": ["children", "paediatric", "febrile seizure"],
        "retrieval_keywords": ["children", "paediatric", "age"],
    },
    {
        "question": "What is the role of hematocrit in dengue management?",
        "gold_keywords": ["hematocrit", "haemoconcentration", "plasma leakage"],
        "retrieval_keywords": ["hematocrit", "plasma", "leakage"],
    },
    {
        "question": "What are integrated vector management strategies for dengue?",
        "gold_keywords": ["integrated", "biological", "environmental", "community"],
        "retrieval_keywords": ["integrated vector management", "ivm"],
    },
    {
        "question": "What is the dengue critical phase and when does it occur?",
        "gold_keywords": ["critical phase", "defervescence", "day", "leakage"],
        "retrieval_keywords": ["critical phase", "defervescence"],
    },
    {
        "question": "What is dengue rapid diagnostic testing?",
        "gold_keywords": ["rapid", "rdt", "ns1", "point of care"],
        "retrieval_keywords": ["rapid test", "diagnostic", "ns1"],
    },
    {
        "question": "How has dengue incidence changed in Southeast Asia over time?",
        "gold_keywords": ["increase", "trend", "southeast asia", "cases"],
        "retrieval_keywords": ["southeast asia", "trend", "epidemiology"],
    },
]


# ── Scoring helpers ───────────────────────────────────────────────────────────

def _keyword_recall(text: str, keywords: list[str]) -> float:
    """Fraction of keywords found (case-insensitive, partial match) in text."""
    if not keywords:
        return 1.0
    text_lower = text.lower()
    hits = sum(1 for kw in keywords if kw.lower() in text_lower)
    return hits / len(keywords)


def _has_citation(text: str) -> bool:
    return bool(re.search(r"\[\d+\]", text))


# ── Runner ────────────────────────────────────────────────────────────────────

@dataclass
class EvalResult:
    question: str
    answer: str
    attempts: int
    valid: bool
    retrieval_recall: float
    answer_accuracy: float
    has_citation: bool
    elapsed_s: float


def run_eval(questions: int | None = None, delay_s: float = 1.0) -> list[EvalResult]:
    """
    Run evaluation against the EVAL_SET.

    Parameters
    ----------
    questions : int | None   Limit to first N questions (None = all).
    delay_s   : float        Seconds to sleep between API calls.
    """
    vs = load_vectorstore()
    dataset = EVAL_SET[:questions] if questions else EVAL_SET
    results: list[EvalResult] = []

    for i, item in enumerate(dataset, 1):
        print(f"[{i}/{len(dataset)}] {item['question'][:70]}…")

        # Retrieval recall (without invoking LLM)
        docs = retrieve(item["question"], vs)
        passages_text = format_passages(docs)
        ret_recall = _keyword_recall(passages_text, item["retrieval_keywords"])

        # Full RAG answer
        t0 = time.perf_counter()
        try:
            result = ask(item["question"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error on Q%d: %s", i, exc)
            result = {"answer": "", "attempts": 0, "valid": False}
        elapsed = time.perf_counter() - t0

        ans_acc = _keyword_recall(result["answer"], item["gold_keywords"])
        cited = _has_citation(result["answer"])

        ev = EvalResult(
            question=item["question"],
            answer=result["answer"],
            attempts=result["attempts"],
            valid=result["valid"],
            retrieval_recall=ret_recall,
            answer_accuracy=ans_acc,
            has_citation=cited,
            elapsed_s=elapsed,
        )
        results.append(ev)

        print(
            f"  ret_recall={ret_recall:.2f}  ans_acc={ans_acc:.2f}"
            f"  cited={cited}  attempts={ev.attempts}  {elapsed:.1f}s"
        )

        if i < len(dataset):
            time.sleep(delay_s)

    return results


def print_summary(results: list[EvalResult]) -> None:
    n = len(results)
    avg_ret = sum(r.retrieval_recall for r in results) / n
    avg_ans = sum(r.answer_accuracy for r in results) / n
    pct_cited = sum(1 for r in results if r.has_citation) / n * 100
    avg_attempts = sum(r.attempts for r in results) / n
    avg_elapsed = sum(r.elapsed_s for r in results) / n

    print("\n" + "=" * 60)
    print(f"Evaluation summary  ({n} questions)")
    print("=" * 60)
    print(f"  Retrieval recall  (avg) : {avg_ret:.3f}")
    print(f"  Answer accuracy   (avg) : {avg_ans:.3f}")
    print(f"  Citation rate           : {pct_cited:.1f}%")
    print(f"  Avg generation attempts : {avg_attempts:.2f}")
    print(f"  Avg latency             : {avg_elapsed:.1f}s")
    print("=" * 60)


def save_results(results: list[EvalResult], path: str = "data/eval_results.json") -> None:
    import dataclasses
    with open(path, "w", encoding="utf-8") as fh:
        json.dump([dataclasses.asdict(r) for r in results], fh, indent=2)
    print(f"Results saved to {path}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate SentinelPH RAG pipeline")
    parser.add_argument("--questions", type=int, default=None, help="Limit to first N questions")
    parser.add_argument("--save", action="store_true", help="Save results to data/eval_results.json")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between API calls")
    args = parser.parse_args()

    results = run_eval(questions=args.questions, delay_s=args.delay)
    print_summary(results)
    if args.save:
        save_results(results)
