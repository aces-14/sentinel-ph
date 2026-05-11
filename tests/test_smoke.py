"""Smoke tests — verify the environment loads and all top-level packages import."""

import importlib


REQUIRED_PACKAGES = [
    "langchain",
    "langgraph",
    "langchain_community",
    "langchain_groq",
    "chromadb",
    "sentence_transformers",
    "pandas",
    "polars",
    "pdfplumber",
    "pypdf",
    "requests",
    "bs4",
    "playwright",
    "xgboost",
    "sklearn",
    "statsmodels",
    "streamlit",
    "folium",
    "plotly",
    "apscheduler",
    "dotenv",
    "pytrends",
]


def test_packages_importable() -> None:
    failed: list[str] = []
    for pkg in REQUIRED_PACKAGES:
        try:
            importlib.import_module(pkg)
        except ImportError:
            failed.append(pkg)
    assert not failed, f"Failed to import: {failed}"


def test_src_packages_importable() -> None:
    src_packages = [
        "src",
        "src.ingest",
        "src.rag",
        "src.agents",
        "src.model",
        "src.dashboard",
        "src.utils",
    ]
    failed: list[str] = []
    for pkg in src_packages:
        try:
            importlib.import_module(pkg)
        except ImportError:
            failed.append(pkg)
    assert not failed, f"Failed to import src packages: {failed}"
