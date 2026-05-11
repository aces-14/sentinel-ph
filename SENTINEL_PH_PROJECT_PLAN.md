# Sentinel PH — Project Planning Document

**Project Codename:** Sentinel PH
**Author:** Reynaldo Ace Pilpil
**Last Updated:** 11 May 2026
**Status:** Pre-build / Planning
**Repository:** _to be created — github.com/aces-14/sentinel-ph_
**Target v1 Demo Date:** As soon as possible

---

## 1. Project Overview

Sentinel PH is a multi-agent dengue intelligence platform for the Philippines. It ingests official surveillance reports, climate data, news, and search-trend signal; cleans and stores them in a unified database; runs a question-answering RAG layer over Philippine dengue research and DOH guidelines; orchestrates a multi-agent workflow that produces region-specific risk briefings; and surfaces everything through a public Streamlit dashboard with a map, trends, and an AI chat interface.

The project is deliberately framed as a *monitoring and risk-scoring* platform, not a *prediction* system. Outbreak prediction is genuinely hard and well-trodden academic territory; positioning the project as one would set us up to be judged against PhDs with vastly more data and compute. By framing the work as intelligence aggregation with risk scoring (and prediction as an honestly-bounded stretch feature), the same engineering effort produces a much more defensible deliverable.

The point of this project is not to outperform epidemiologists. It is to demonstrate, in one unified system, the full stack of skills an AI engineer is expected to ship in 2026: data engineering, RAG, multi-agent orchestration, classical ML, fine-tuning, deployment, and honest evaluation — applied to a problem that genuinely matters to millions of Filipinos.

---

## 2. Goals and Success Criteria

### Primary Goal
Ship a deployed, public-facing dengue intelligence platform that demonstrates production-grade AI engineering applied to a real Philippine public health problem.

### Secondary Goals
1. Produce a cleaned, open-sourced dataset of Philippine dengue surveillance data that other researchers and builders can use.
2. Publish a fine-tuned small language model on Hugging Face for Filipino health-text NER.
3. Generate two technical writeups documenting engineering decisions and what didn't work.
4. Establish one external advisory contact (epidemiologist or public health professional) before building.

### Definition of Done for v1
- Dashboard live on Hugging Face Spaces with a map of all 17 PH regions, weekly trend charts, and a working RAG chat interface.
- Risk model trained, evaluated with temporal cross-validation, and published with honest confidence intervals and an evaluation report.
- Cleaned dataset published on Hugging Face Datasets.
- Fine-tuned model published on Hugging Face Hub with a real model card.
- One blog post written and published.
- Code on GitHub with a README, a contributing guide, and reproducible setup instructions.

---

## 3. Scope and Limitations

### In Scope
- **Granularity:** Province-level (81 provinces) and Region-level (17 regions). Down to province but not city/barangay.
- **Time resolution:** Weekly aggregates (matching DOH publication cadence).
- **Time range:** 2016 to present (DOH digital surveillance reports begin around then).
- **Diseases covered:** Dengue only for v1. Architecture should allow extension to other notifiable diseases later.
- **Languages:** English primary, Tagalog secondary (for the fine-tuned NER model and select dashboard labels).
- **Output:** Public read-only dashboard; no user accounts, no write operations, no PII collection.

### Out of Scope (v1)
- Real-time daily case data (unavailable at granularity needed)
- Hospital admission / ICU data (private, not freely accessible)
- Mosquito surveillance data (sparse, not centrally available)
- Direct medical advice or diagnosis (legal/ethical reasons)
- Sub-province granularity (city, municipality, barangay)
- Native mobile app (web dashboard sufficient)
- Multi-disease support
- Personalized alerts or push notifications
- Authentication, user accounts, paid tiers

### Known Limitations (must be transparent about these)
- **Risk scores are not diagnoses or guarantees.** The dashboard must surface this prominently.
- **Data lag.** DOH reports run 1-2 weeks behind real conditions.
- **No causal claims.** The model identifies correlations, not causation, between weather/news signals and case counts.
- **Limited evaluation data.** Without held-out future data, evaluation must rely on temporal cross-validation, which is less reliable than true forward-looking validation.
- **Tagalog NLP is constrained** by the small amount of labeled health text available; the fine-tuned model will be a proof of concept, not a production-grade Filipino health NER system.
- **Free-tier compute** introduces latency. Inference on Hugging Face Spaces free CPU tier is slow — acceptable for a demo, not for production.
- **News and search-trend signals are noisy proxies.** They correlate weakly with actual case counts and will not always agree with surveillance data.

---

## 4. Tech Stack

| Category | Tool / Library | Purpose | Cost |
|---|---|---|---|
| **Language** | Python 3.11+ | Primary language for everything | Free |
| **Package manager** | uv (or poetry) | Modern, fast Python dependency mgmt | Free |
| **LLM framework** | LangChain | Document loaders, prompt templates, chains | Free |
| **Agent orchestration** | LangGraph | Multi-agent state machines | Free |
| **LLM inference** | Groq API | Fast Llama 3.3 70B inference | Free tier |
| **Embeddings** | sentence-transformers (BAAI/bge-small-en) | Vector embeddings, runs on CPU | Free |
| **Vector DB** | ChromaDB | Local persistent vector store | Free |
| **Classical ML** | scikit-learn, XGBoost | Risk scoring model | Free |
| **Time series baseline** | statsmodels | ARIMA baseline for comparison | Free |
| **Data processing** | pandas, polars | Tabular data wrangling | Free |
| **PDF parsing** | pdfplumber, pypdf | DOH PDF extraction | Free |
| **Web scraping** | requests, BeautifulSoup, playwright | DOH site, news sources | Free |
| **Weather API** | Open-Meteo | Free, no API key, daily historical data | Free |
| **Climate (optional upgrade)** | Copernicus ERA5 (CDS API) | Higher-fidelity reanalysis data | Free w/ registration |
| **News data** | GDELT 2.0 Doc API | Global news monitoring | Free |
| **Trends signal** | pytrends | Google Trends data | Free |
| **Geographic data** | OpenStreetMap (Geofabrik), PSA shapefiles | PH boundary polygons | Free |
| **Database** | SQLite (dev) → DuckDB or Postgres (if needed) | Storage for cleaned data | Free |
| **Job scheduling** | APScheduler | Periodic data refresh | Free |
| **Fine-tuning** | Unsloth on Google Colab | Free T4 GPU, memory-efficient | Free |
| **Base model for fine-tune** | Llama 3.2 1B or Phi-3 mini | Small enough for free GPU | Free |
| **Model hosting** | Hugging Face Hub | Public model + dataset hosting | Free |
| **Dashboard** | Streamlit | Fast Python-native dashboards | Free |
| **Map visualization** | Folium (Leaflet wrapper) | Choropleth maps | Free |
| **Charts** | Plotly | Interactive trend charts | Free |
| **Deployment** | Hugging Face Spaces (free CPU tier) | Public hosting | Free |
| **Version control** | Git + GitHub | Source control | Free |
| **CI (optional)** | GitHub Actions | Lint, test, format | Free |
| **Experiment tracking (optional)** | MLflow (local) or Weights & Biases free | ML experiment logging | Free |

### Why these specific choices

- **Open-Meteo over Copernicus initially:** No API key, no registration. Get the pipeline working first; switch to ERA5 later for higher-fidelity reanalysis.
- **Groq over OpenAI/Anthropic:** Free tier is generous, latency is excellent, Llama 3.3 70B is competitive for this workload. We can use Anthropic Claude or OpenAI GPT-4 sparingly for evaluation/ground-truth generation.
- **ChromaDB over Pinecone/Weaviate:** Local, free, persistent, no signup. Perfect for a solo dev project.
- **XGBoost over LSTM/Transformer for risk scoring:** Tabular data, modest size, well-published baselines for dengue forecasting, less prone to overfitting on small data, easier to interpret.
- **Llama 3.2 1B for fine-tuning:** Small enough to fit on free Colab T4, popular base model so the credential carries weight on the resume.
- **Streamlit over React/Next.js:** Solo dev, focus is the AI/ML work, deploy in minutes on HF Spaces.
- **uv over pip + venv:** Significantly faster, modern, plays well with Claude Code workflows.

---

## 5. Datasets — What and How to Get Them

| # | Dataset | Source | Format | Access Method | Refresh |
|---|---|---|---|---|---|
| 1 | DOH Weekly Disease Surveillance Reports | doh.gov.ph/health-statistics | PDF | Scrape index page → download PDFs → parse | Weekly |
| 2 | WHO WPRO Dengue Updates | who.int/westernpacific (WPRO surveillance) | HTML / PDF | HTTP fetch → parse | Weekly |
| 3 | Historical weather (daily, per province) | Open-Meteo Archive API | JSON | HTTP API call | Daily |
| 4 | Current weather conditions | Open-Meteo Forecast API | JSON | HTTP API call | Hourly |
| 5 | News mentions of dengue (PH) | GDELT 2.0 Doc API | JSON | HTTP API call | Daily |
| 6 | Google Trends — "dengue" + Filipino terms by region | pytrends library | DataFrame | Python library | Weekly |
| 7 | PH province / region boundaries | PSA + Geofabrik OpenStreetMap | Shapefile / GeoJSON | One-time download | Static |
| 8 | PH province population | Philippine Statistics Authority | CSV | One-time download | Annual |
| 9 | Dengue research papers (PH-specific) | PubMed, Google Scholar, arXiv | PDF | Manual + scripted download | One-time |
| 10 | DOH dengue guidelines / fact sheets | DOH website | PDF | One-time scrape | Quarterly |

### Notes on each dataset

**1. DOH Surveillance Reports (the central dataset)**
The most valuable but most painful to acquire. DOH publishes weekly Disease Surveillance Reports as PDFs at `doh.gov.ph/health-statistics`. The PDFs are not perfectly structured — table layouts shift between years, headers move, and some weeks are missing. Plan to spend most of Phase 1 building a robust extraction pipeline. Use pdfplumber for table extraction; fall back to pypdf for raw text where pdfplumber misses. Keep raw PDFs in `data/raw/doh/` and parsed structured output in `data/processed/cases.parquet`. Build a small validation suite that flags weeks where extraction looks suspect (e.g., unusually high or low case counts vs. neighbors).

**2. WHO WPRO Updates**
Cross-validation source. Use to sanity-check DOH parsing.

**3-4. Open-Meteo**
Best free weather API for this use case. Endpoint: `https://archive-api.open-meteo.com/v1/era5`. Pull daily temperature, precipitation, and humidity for a representative point in each province (use province centroid). Lag features (1-week, 2-week, 4-week, 8-week lags) are the standard inputs for dengue risk modeling because mosquito reproduction has a temperature- and rain-dependent lifecycle.

**5. GDELT**
Free global news database. Query the Doc 2.0 API for `dengue Philippines` plus province names. Useful for both signal (rising news = possible outbreak awareness) and qualitative briefings.

**6. Google Trends**
Use pytrends to pull search interest for `dengue`, `lagnat ng dengue`, `dengue symptoms` segmented by Philippine region. Trend signal often *leads* official surveillance by 1-2 weeks because people search before they get diagnosed.

**7-8. Geographic + Population**
Philippine Statistics Authority (psa.gov.ph) publishes shapefiles. Geofabrik also has clean OpenStreetMap PH extracts. Need both polygons (for the choropleth map) and population (to compute incidence rates per 100,000).

**9-10. Research papers + DOH guidelines**
Source documents for the RAG layer. Aim for 30-50 high-quality PDFs covering Philippine dengue epidemiology, DOH treatment protocols, and prevention guidance. Store in `data/raw/rag_corpus/`.

### Data licensing note
DOH bulletins are public-domain government records. Open-Meteo, Copernicus, and GDELT are open data. Pytrends scrapes Google's public-facing data (use responsibly — rate-limit). Cleaned derivative datasets published on Hugging Face should be released under CC-BY 4.0 with proper source attribution.

---

## 6. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA INGESTION LAYER                         │
│                                                                       │
│  DOH PDF Scraper  ──┐                                                │
│  Weather Agent    ──┤                                                │
│  News Agent       ──┼──► Cleaned Parquet/SQLite ──┐                  │
│  Trends Puller    ──┤                              │                  │
│  RAG Corpus Loader──┘                              │                  │
└────────────────────────────────────────────────────┼─────────────────┘
                                                     │
                  ┌──────────────────────────────────┼─────────────────┐
                  │                                  │                  │
                  ▼                                  ▼                  ▼
        ┌──────────────────┐         ┌────────────────────┐   ┌───────────────┐
        │   RAG LAYER      │         │ MULTI-AGENT SYSTEM │   │  RISK MODEL   │
        │  (LangChain +    │         │     (LangGraph)    │   │   (XGBoost)   │
        │   ChromaDB)      │         │                    │   │               │
        │                  │         │  • Extraction agt  │   │  inputs:      │
        │  Q&A over PH     │         │  • Correlation agt │   │  - case lags  │
        │  dengue research │         │  • Briefing agt    │   │  - weather    │
        │  + DOH guidelines│         │  • Evaluator agt   │   │  - news/trends│
        └──────────────────┘         └────────────────────┘   └───────────────┘
                  │                                  │                  │
                  └──────────────────┬───────────────┴──────────────────┘
                                     │
                                     ▼
                  ┌─────────────────────────────────────┐
                  │       STREAMLIT DASHBOARD           │
                  │   (Hugging Face Spaces, free tier)  │
                  │                                     │
                  │   • Map (Folium choropleth)         │
                  │   • Trend charts (Plotly)           │
                  │   • Chat interface (RAG)            │
                  │   • Weekly briefing (agent output)  │
                  │   • Risk score per province         │
                  └─────────────────────────────────────┘
```

---

## 7. Phase-by-Phase Build Plan

Each phase below includes: **Goal**, **Tools**, **Step-by-step actions**, **Deliverables**, and **Decision rationale** for tooling choices.

---

### Phase 0 — Setup (Days 1-3)

**Goal:** Empty repo to "everything wired and one trivial test passing."

**Tools used in this phase:**
- Local development environment (your laptop)
- GitHub (repo hosting)
- uv (Python package manager)
- VS Code or your editor of choice
- Claude Code (project scaffolding)
- Optional: GitHub Actions for CI later

**Where the work happens:** All local. No Colab, no cloud GPU. Just your laptop.

**Step-by-step:**
1. Create GitHub repo `sentinel-ph` (public). Initialize with MIT or Apache 2.0 license, README placeholder, .gitignore for Python.
2. Clone locally. Create a Python 3.11 environment with `uv venv`.
3. Define initial `pyproject.toml` with dependencies: `langchain`, `langgraph`, `langchain-community`, `langchain-groq`, `chromadb`, `sentence-transformers`, `pandas`, `polars`, `pdfplumber`, `pypdf`, `requests`, `beautifulsoup4`, `playwright`, `xgboost`, `scikit-learn`, `statsmodels`, `streamlit`, `folium`, `plotly`, `apscheduler`, `python-dotenv`, `pytest`, `ruff`.
4. Create directory skeleton:
   ```
   sentinel-ph/
   ├── data/
   │   ├── raw/           # untouched downloads
   │   ├── processed/     # cleaned parquet files
   │   └── rag_corpus/    # PDFs for RAG
   ├── src/
   │   ├── ingest/        # data ingestion modules
   │   ├── rag/           # vector store + chat
   │   ├── agents/        # LangGraph agents
   │   ├── model/         # risk scoring model
   │   ├── dashboard/     # Streamlit app
   │   └── utils/
   ├── notebooks/         # exploratory work
   ├── tests/
   ├── scripts/           # one-off scripts
   ├── .env.example
   ├── pyproject.toml
   ├── README.md
   └── PROJECT_PLAN.md    # this document
   ```
5. Get API keys: Groq (free tier — `console.groq.com`), Hugging Face token (`huggingface.co/settings/tokens`). Store in `.env` (gitignored). Document in `.env.example`.
6. Write a single `tests/test_smoke.py` that imports each module and verifies environment loads.
7. Commit and push.

**Deliverables for Phase 0:**
- Public GitHub repo with skeleton pushed
- Local environment working
- Smoke test passing
- API keys stored in `.env`

**Decision rationale:**
- *Why public repo from day 1?* The repo itself is the credential. Activity early matters.
- *Why uv?* Faster dependency resolution; integrates well with Claude Code.
- *Why this dir layout?* Mirrors how production AI projects are organized — separates ingestion, RAG, agents, model, dashboard cleanly so each can be tested in isolation.

---

### Phase 1 — Data Ingestion (Weeks 1-3)

**Goal:** End up with clean parquet files containing weekly dengue cases per province (2016-present), daily weather per province, news mentions, and search trends — all queryable from a single SQLite DB.

**Tools used in this phase:**
- All work happens **locally on your laptop** (no Colab, no cloud)
- pdfplumber + pypdf for PDF extraction
- BeautifulSoup + requests for the DOH website index
- playwright (only if DOH site uses heavy JavaScript)
- Open-Meteo Archive API for historical weather (HTTP only, no library)
- pytrends for Google Trends
- GDELT Doc API (HTTP only)
- pandas / polars for data wrangling
- SQLite for unified storage
- pytest for ingestion tests
- Claude Code for writing the parsers

**Step-by-step:**
1. **Build DOH PDF scraper:**
   - Crawl the DOH health-statistics index page; extract all PDF URLs.
   - Download each PDF to `data/raw/doh/YYYY-WW.pdf`.
   - Build a parser using pdfplumber that extracts the morbidity table per region/province.
   - Validate: row counts per region should match the totals printed in the report.
2. **Build weather puller:**
   - For each province, compute its centroid (use shapefile from Phase 1 step 5).
   - Hit Open-Meteo Archive API: `https://archive-api.open-meteo.com/v1/era5?latitude=X&longitude=Y&start_date=2016-01-01&end_date=...&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,relative_humidity_2m_mean`.
   - Store as `data/processed/weather_daily.parquet` with columns: `[province, date, t_max, t_min, precip, rh_mean]`.
3. **Build news puller (GDELT):**
   - Query: `dengue AND Philippines`, language English + Tagalog if available.
   - Store article metadata (URL, title, date, country, region tag) in `data/processed/news.parquet`.
4. **Build Google Trends puller:**
   - For each PH region, pull weekly trend index for queries: `dengue`, `dengue symptoms`, `lagnat ng dengue`, `bahay sa lamok`.
   - Store as `data/processed/trends_weekly.parquet`.
5. **Download geographic data:**
   - PSA shapefiles for province boundaries → convert to GeoJSON → store in `data/raw/geo/ph_provinces.geojson`.
   - Compute centroids; save lookup table in `data/processed/province_centroids.parquet`.
6. **Build unified SQLite database:**
   - Single SQLite file at `data/sentinel.db` with tables: `cases`, `weather`, `news`, `trends`, `provinces`.
   - Loader scripts in `src/ingest/load_db.py`.
7. **Write tests:**
   - For each ingestion module, write a small test that runs against a known-good week and asserts the parsed output matches a hand-coded expected DataFrame.
8. **Wire scheduling (optional for v1):**
   - APScheduler job that pulls latest DOH PDF + weather + news weekly.
   - For v1, manual triggering is fine. Automate later if time allows.

**Deliverables for Phase 1:**
- `data/sentinel.db` populated with at least 2020-2026 weekly case data + matched daily weather + news + trends
- Ingestion modules in `src/ingest/` with passing tests
- Notebook (`notebooks/01_eda.ipynb`) doing exploratory plots: cases over time per region, seasonality, weather correlations

**Decision rationale:**
- *Why parquet + SQLite, not just CSV?* Parquet is columnar, compressed, and fast for analytical queries. SQLite is a single-file DB that "just works" without setup. Postgres is overkill for v1.
- *Why Open-Meteo first instead of Copernicus?* Zero friction: no API key, no registration. Get the pipeline working first; swap to ERA5 in v2 if needed.
- *Why pdfplumber and not LLM extraction?* Reliability. LLMs hallucinate numbers. Use deterministic parsing for the ground-truth dataset. LLMs come in later for unstructured news, not for surveillance numbers.

---

### Phase 2 — RAG Layer (Weeks 4-6)

**Goal:** A working question-answering system that takes a question about dengue, retrieves grounded passages from PH dengue research and DOH guidelines, and produces a citation-backed answer using Groq + LangChain.

**Tools used in this phase:**
- All work happens **locally** (the chat interface runs on your laptop)
- LangChain (document loaders, prompt templates, retrieval chains)
- ChromaDB (local persistent vector store at `data/chroma/`)
- sentence-transformers `BAAI/bge-small-en-v1.5` for embeddings (CPU is fine)
- LangGraph (chat workflow with citation enforcement)
- Groq API (Llama 3.3 70B for the LLM)
- Claude Code for prompt iteration

**Step-by-step:**
1. **Assemble RAG corpus:**
   - Manually curate 30-50 PDFs: PH dengue epidemiology papers, DOH dengue clinical management guidelines, DOH dengue prevention fact sheets, WHO WPRO dengue technical guidance, key academic reviews on PH-specific dengue patterns.
   - Store in `data/rag_corpus/`.
2. **Build the indexer:**
   - LangChain `PyPDFLoader` for each PDF.
   - `RecursiveCharacterTextSplitter` with chunk size 800 tokens, overlap 100.
   - Embed with `BAAI/bge-small-en-v1.5`.
   - Persist to ChromaDB at `data/chroma/`.
3. **Build the retrieval chain:**
   - Top-k retrieval with k=5.
   - Optional: rerank with `BAAI/bge-reranker-base` for better precision.
4. **Build the LangGraph chat workflow with citation enforcement (extends your Labor Law RAG pattern):**
   - Node 1: Retrieve passages.
   - Node 2: Generate answer with explicit instruction to cite passage IDs.
   - Node 3: Validator — check that every factual claim in the answer maps to a retrieved passage. If not, route back to node 2 with a refinement prompt. Cap at 3 retries.
5. **Build a CLI chat for testing:**
   - `python -m src.rag.cli` opens an interactive chat in the terminal. Use this heavily during prompt iteration.
6. **Write evaluation set:**
   - 30-50 hand-written question-answer pairs covering: clinical (symptoms, severity), prevention, epidemiology, statistics. For each, label which corpus document(s) the answer should come from.
   - Run automated eval: retrieval recall, answer factual correctness (use Claude or GPT-4 as a judge for the LLM grading; document this honestly).

**Deliverables for Phase 2:**
- ChromaDB vector store at `data/chroma/`
- Working RAG chat module in `src/rag/`
- Evaluation set + eval report (retrieval recall %, answer accuracy %, hallucination rate %)
- 1 short writeup or notebook on prompt iterations and what worked

**Decision rationale:**
- *Why bge-small-en over OpenAI embeddings?* Free, local, no API costs, runs fast on CPU.
- *Why citation enforcement via a separate validator node?* Same reasoning as your Labor Law RAG: smooth-sounding hallucinations are worse than honest "I don't know." The validator is the guardrail.
- *Why 30-50 PDFs and not 500?* Quality over quantity for v1. A small, high-signal corpus retrieves better than a large noisy one.

---

### Phase 3 — Multi-Agent System + Risk Scoring (Weeks 7-9)

**Goal:** A LangGraph multi-agent workflow that produces a weekly per-region briefing combining recent case data, weather context, news summaries, and a risk score with confidence interval.

**Tools used in this phase:**
- Local development continues on your laptop
- LangGraph for orchestration
- Groq for LLM calls
- XGBoost for the risk model
- scikit-learn for preprocessing and temporal cross-validation
- statsmodels for an ARIMA baseline (to compare against)
- mlflow (local) for experiment tracking — optional but recommended
- matplotlib + plotly for evaluation plots
- Claude Code for writing agent nodes and the model training loop

**Step-by-step:**
1. **Train the XGBoost risk model:**
   - Target: log(cases per 100k next week) per province.
   - Features: case lags (1, 2, 4, 8 weeks back), rolling means, weather lags (temp + precip + humidity at 1, 2, 4, 8 weeks back), Google Trends current and lagged, news mention count, month-of-year, region, El Niño / La Niña phase if available.
   - Split: temporal cross-validation (train 2016-2022, validate 2023, test 2024-2025). Never random shuffle — that leaks future information.
   - Metrics: RMSE, MAE, calibration plot, feature importance.
   - Compare against: (a) naive seasonal baseline (last year same week), (b) ARIMA per province.
2. **Wrap the model in a Python class:**
   - `src/model/risk_scorer.py` exposes `predict(province, as_of_date) -> {score, ci_low, ci_high, top_features}`.
3. **Build the multi-agent workflow in LangGraph:**
   - **Ingestion Agent:** Pulls latest weekly DOH update, refreshes weather, refreshes news. Writes to DB.
   - **Extraction Agent:** Parses the latest DOH bulletin into structured cases. Validates against prior weeks; flags anomalies.
   - **Correlation Agent:** Joins recent cases with weather and news per province. Produces a structured "context object" per region.
   - **Risk Scoring Agent:** Calls the XGBoost model for each province. Attaches scores and confidence intervals to the context object.
   - **Briefing Agent:** Generates a per-region narrative briefing using the context object. Required to cite specific data points (e.g., "Cases up 12% week-over-week in Cebu; humidity has been above 80% for 14 consecutive days").
   - **Evaluator Agent:** Reviews the generated briefing for: (a) factual grounding against the context object, (b) appropriate uncertainty language, (c) absence of medical advice. If any check fails, routes back to the Briefing Agent with corrective feedback. Cap at 3 retries.
4. **End-to-end weekly run:**
   - Single command `python -m src.agents.weekly_run` triggers the full workflow and writes outputs to `data/processed/weekly_briefings/{date}/{region}.json`.

**Deliverables for Phase 3:**
- Trained XGBoost model + saved artifact in `models/`
- Evaluation report comparing risk model vs. baselines
- Multi-agent LangGraph workflow runnable end-to-end
- Sample weekly briefings for at least 4 historical weeks
- Notebook documenting model decisions, what features mattered, what didn't work

**Decision rationale:**
- *Why XGBoost and not a deep model?* Tabular data, modest sample size, well-documented baselines exist for dengue forecasting using similar feature sets. Less risk of overfitting; more interpretable.
- *Why temporal CV?* Random splits leak future information into training and inflate accuracy claims. Temporal splits are the honest way to validate a forecasting model.
- *Why the validator agent loop?* Same integrity philosophy as your existing projects. The agent should refuse its own bad outputs.

---

### Phase 4 — Fine-Tuning + Dashboard + Deployment (Weeks 10-12)

**Goal:** Ship the public dashboard, publish the fine-tuned NER model, and produce the open dataset.

**Tools used in this phase (split by sub-task):**

For **fine-tuning** (sub-phase 4a):
- **Google Colab (free T4 GPU)** — _this is the only place we go cloud, and only for fine-tuning_
- Unsloth library (most memory-efficient fine-tuning; fits Llama 3.2 1B comfortably on a free T4)
- Hugging Face Datasets for the training data
- Hugging Face Hub for uploading the final model
- The fine-tuning happens in a Colab notebook saved at `notebooks/04_finetune.ipynb`. After training, the model file is uploaded to HF Hub. Inference in the dashboard then *downloads from HF Hub* — we do not bundle weights in the repo.

For the **dashboard + deployment** (sub-phase 4b):
- Local development: Streamlit, Folium, Plotly
- Hugging Face Spaces (free CPU tier) for deployment
- The whole Streamlit app gets pushed to a separate `huggingface.co/spaces/aces-14/sentinel-ph` repo (a Space is itself a Git repo)
- Claude Code for assembling the dashboard layout

**Step-by-step:**

**Sub-phase 4a — Fine-tune the Filipino health-text NER model:**
1. Construct a small labeled dataset: ~500-1500 examples of Tagalog/English news snippets and social posts mentioning dengue, with span labels for entities like {SYMPTOM, LOCATION, SEVERITY_INDICATOR, DATE_REFERENCE}. Bootstrap initial labels by prompting Groq Llama 3.3 70B; manually correct a sample.
2. Open Google Colab; select T4 runtime.
3. Install Unsloth in the notebook.
4. Load Llama 3.2 1B base model.
5. Fine-tune with QLoRA on the labeled dataset. Track loss curves.
6. Evaluate on a held-out test split: precision, recall, F1 per entity type.
7. Push to Hugging Face Hub at `aces-14/sentinel-ph-ner-v1` with a model card documenting: training data size, eval metrics, intended use, limitations.
8. Save the notebook back to the GitHub repo.

**Sub-phase 4b — Build the dashboard:**
1. Streamlit app structure:
   - **Home tab:** PH map (Folium choropleth) colored by current risk score per province, last-updated timestamp, headline trend line
   - **Region detail tab:** Selectbox for province → trend chart (Plotly), recent cases table, weekly briefing text, risk score with confidence interval
   - **Chat tab:** Embedded RAG chat interface
   - **About / Methodology tab:** How risk scores are computed, data sources, limitations (very important — this is where transparency lives)
2. Dashboard reads from `data/sentinel.db` and the saved briefings JSONs. The agent workflow is run *offline* (locally or scheduled) and the dashboard just consumes the latest outputs. This keeps Spaces deployment fast and cheap.

**Sub-phase 4c — Deploy to Hugging Face Spaces:**
1. Create a Space (Streamlit SDK, free CPU tier).
2. Push the dashboard subdirectory (`src/dashboard/`) plus a copy of the latest data snapshots.
3. Configure secrets: `GROQ_API_KEY`, `HF_TOKEN`.
4. First deploy. Iterate on layout.
5. Once stable, write a deploy script that snapshots fresh data + briefings to the Space repo on a schedule.

**Sub-phase 4d — Open-source the dataset:**
1. Clean and version the parsed DOH cases dataset (province × week × cases).
2. Push to Hugging Face Datasets at `aces-14/ph-dengue-surveillance` with a dataset card documenting source, license (CC-BY 4.0), update cadence, and known limitations.

**Sub-phase 4e — Write the launch blog post:**
1. Title suggestion: *"What I learned trying to build a dengue intelligence platform for the Philippines"*
2. Cover: motivation, architecture, what worked, what didn't, what the model is and isn't, where you'd take it next. Be honest about failures — that's what reads as mature.
3. Publish on dev.to or Hashnode. Tag #ai #langchain #healthcare #philippines.

**Deliverables for Phase 4:**
- Live public dashboard at `huggingface.co/spaces/aces-14/sentinel-ph`
- Fine-tuned model live at `huggingface.co/aces-14/sentinel-ph-ner-v1`
- Open dataset at `huggingface.co/datasets/aces-14/ph-dengue-surveillance`
- Published blog post
- Updated GitHub repo with full README, setup instructions, contribution guide

**Decision rationale:**
- *Why Colab for fine-tuning, not local?* Most laptops can't fit even a 1B model in VRAM. Colab's free T4 has 16 GB — plenty for QLoRA on Llama 3.2 1B.
- *Why Unsloth?* Most memory-efficient open-source fine-tuning library. Fits where vanilla HuggingFace Transformers won't.
- *Why deploy on HF Spaces and not Render/Fly/etc?* Free CPU tier, integrates with HF Hub for model loading, AI community sees Space pages, single-platform story.
- *Why precompute briefings offline rather than generate live?* Cost (LLM calls) and latency. The dashboard becomes a fast viewer of recent outputs; the heavy work happens in the agent workflow that you trigger yourself or on a schedule.

---

## 8. Working with Claude Code

This document is designed to be read by Claude Code as a project spec. When you start a Claude Code session in this repo, point it at this file with something like:

> "Read PROJECT_PLAN.md. We are currently on Phase X step Y. Help me implement [specific step]."

### Recommended Claude Code workflow per phase

- **Phase 0:** Use Claude Code to scaffold the directory layout and `pyproject.toml` from this document.
- **Phase 1:** Use Claude Code to write the DOH PDF parser. Claude Code is excellent at iterative parsing where you feed it a sample PDF and refine extraction logic. Use it heavily for the ingestion modules and their tests.
- **Phase 2:** Use Claude Code to wire LangChain / LangGraph plumbing. Ask it to write the citation-validator node carefully; this is the most subtle piece.
- **Phase 3:** Use Claude Code to wire the agent graph and write the model training loop. For the model itself, drive the feature engineering and validation methodology yourself — that's where the engineering learning lives.
- **Phase 4:** Use Claude Code for the Streamlit layout, the HF Spaces deploy script, the model card draft, and the blog post draft. Always rewrite these in your own voice before publishing.

### Conventions for Claude Code to follow
- Python 3.11+, type hints required on public functions.
- Format with `ruff format`; lint with `ruff check`.
- Tests in `tests/`, one test file per source module.
- No new dependencies without updating `pyproject.toml`.
- No new top-level directories without updating this document.
- All API keys via `.env` and `python-dotenv`. Never hard-code keys.
- Commit messages: imperative mood, short summary line, optional body.
- Branch convention: `phaseN/short-description` for phase work.

---

## 9. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| DOH PDF format changes mid-project, breaking parser | Medium | High | Build parser to fail loudly, not silently. Alert on schema drift. Keep raw PDFs forever. |
| Risk model accuracy is mediocre | High | Medium | Frame as "risk scoring" not "prediction." Publish honest evaluation including baselines. Confidence intervals visible everywhere. |
| Free Groq tier rate-limits during heavy iteration | Medium | Low | Cache aggressively. Use smaller models (Llama 3.1 8B) for development; escalate to 70B for final outputs only. |
| HF Spaces free tier too slow | Medium | Medium | Precompute everything. Dashboard is a viewer, not a live LLM frontend. |
| Fine-tuning data is too small to produce a useful NER model | High | Low | Position the fine-tuned model as a proof of concept in the model card. The credential of having published a fine-tuned model is independent of its eval scores. |
| Scope creep | High | High | This document is the contract. Anything not listed is v2. Before adding something, ask: "Does this go in scope, or is it v2?" |
| Project takes longer than 12 weeks | High | Low | That's fine. 16 weeks of a strong shipped project beats 12 weeks of half-done work. Update the timeline; don't compromise the deliverable. |
| Burnout | Medium | High | Schedule a real day off after each phase. Don't skip. |

---

## 10. Appendix — References and Resources

### Key external resources
- DOH Health Statistics: `doh.gov.ph/health-statistics`
- WHO WPRO Dengue: `who.int/westernpacific/emergencies/surveillance/dengue`
- Open-Meteo: `open-meteo.com/en/docs/historical-weather-api`
- Copernicus CDS: `cds.climate.copernicus.eu`
- GDELT 2.0 Doc API: `blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/`
- pytrends: `github.com/GeneralMills/pytrends`
- Philippine Statistics Authority: `psa.gov.ph`
- LangChain docs: `python.langchain.com`
- LangGraph docs: `langchain-ai.github.io/langgraph`
- Unsloth: `github.com/unslothai/unsloth`
- Hugging Face Spaces docs: `huggingface.co/docs/hub/spaces`
- Streamlit docs: `docs.streamlit.io`

### Suggested reading before starting
1. At least two academic papers on Philippine dengue forecasting (search Google Scholar: `"dengue" "Philippines" forecasting weather`)
2. The Hugging Face Datasets card guide
3. The LangGraph quickstart and one example multi-agent tutorial
4. The Unsloth fine-tuning tutorial for Llama 3.2

### Outreach targets (Phase 0 — do this in week 1)
- One epidemiologist or public health researcher at UP Manila, RITM (Research Institute for Tropical Medicine), or a related institution
- Goal: 30-minute conversation. Bring this document. Ask: *"What would make this useful? What already exists? What's the most honest framing?"*

---

**End of Project Plan v1**
*This document will be revised as the project develops. All revisions tracked in Git.*
