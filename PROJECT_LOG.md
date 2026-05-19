# Sentinel PH — Project Log

This file tracks everything done across all phases: what was built, decisions made, and problems encountered.
All revisions are tracked in Git. High-level scope changes are also recorded in `SENTINEL_PH_PROJECT_PLAN.md`.

---

## Phase 0 — Setup

**Status:** DONE
**Completed:** 11 May 2026

### What was done
- Cloned `https://github.com/aces-14/sentinel-ph.git` into `D:\projects\sentinelPH`
- Installed `uv` (v0.11.13) and created a Python 3.11 virtual environment at `.venv`
- Seeded the venv with `pip` (required by VS Code Python Environments extension)
- Created full directory skeleton: `src/ingest`, `src/rag`, `src/agents`, `src/model`, `src/dashboard`, `src/utils`, `data/raw`, `data/processed`, `data/raw/rag_corpus`, `data/raw/geo`, `models`, `notebooks`, `tests`, `scripts`
- Wrote `pyproject.toml` with all Phase 1–4 dependencies
- Wrote `.env.example` documenting required API keys (Groq, HF token)
- Wrote `tests/test_smoke.py` — 2 tests, both passing
- Updated `.gitignore` with project-specific data and model file exclusions

### Problems encountered
- `uv venv` does not include `pip` by default → VS Code Python Environments panel showed an error trying to list packages with pip. Fixed by running `uv pip install pip` to seed the venv.
- First `uv sync` failed because `hatchling` couldn't find the package directory (project name `sentinel-ph` vs directory `src/`). Fixed by adding `[tool.hatch.build.targets.wheel] packages = ["src"]` to `pyproject.toml`.
- `scikit-learn` had a broken partial install after the first interrupted sync. Fixed by running `uv pip install --reinstall scikit-learn`.

---

## Phase 1 — Data Ingestion

**Status:** DONE
**Started:** 11 May 2026
**Completed:** 11 May 2026

---

### Step 1 — OpenDengue Case Data

**Status:** DONE

**What was done**
- Wrote `src/ingest/opendengue.py`
- Downloaded `Spatial_extract_V1_3.zip` from OpenDengue GitHub (52 MB) → cached at `data/raw/opendengue_spatial_v1_3.zip`
- Filtered to Philippines rows (9,897 of 2.8M global rows)
- Saved three resolution-specific parquet files:
  - `data/processed/cases_national_weekly.parquet` — 544 rows, 2012–2023 ← used for risk model + trend charts
  - `data/processed/cases_regional_annual.parquet` — 224 rows, 1999–2020 ← used for choropleth map
  - `data/processed/cases_provincial_monthly.parquet` — 9,060 rows, 1993–2010 ← historical EDA only
- All validated: 0 null cases, 0 null dates, 0 negative values
- Wrote 15 tests in `tests/test_ingest_opendengue.py` — all passing

**Problems encountered**
- The original plan assumed province-level weekly data from 2016 to present. After inspecting the actual data, this was wrong:
  - Province-level (Admin2) data only covers **1993–2010** at **monthly** resolution
  - Region-level (Admin1) data only covers **1999–2020** at **annual** resolution
  - Only national-level (Admin0) is weekly and recent (2012–2023)
- **Resolution:** Adjusted project scope to Option B — national weekly for the risk model/time series, regional annual for the map. Documented in project plan revision v1.3.

---

### Step 2 — Weather Data (Open-Meteo ERA5)

**Status:** DONE

**What was done**
- Wrote `src/ingest/weather.py`
- Confirmed all 20 unique region name variants in OpenDengue data and mapped each to a lat/lon centroid (deduplicated to 18 unique locations)
- Called Open-Meteo ERA5 Archive API for each location: `t_max`, `t_min`, `precip`, `rh_mean` daily from 2012-01-01 to 2023-12-31
- Saved `data/processed/weather_daily.parquet` — 78,894 rows, 0 nulls across all columns

**Problems encountered**
- Open-Meteo rate-limited requests (HTTP 429) after the first 6 regions. Initial 0.5s sleep between requests was too aggressive.
- **Resolution:** Added two fixes: (1) resume logic — re-runs skip regions already saved in the parquet file; (2) exponential backoff on 429 errors (10s → 20s → 40s, up to 5 retries). Re-ran and all 18 regions completed successfully.

---

### Step 3 — News Data (GDELT Doc 2.0)

**Status:** DONE (partial data — see problems)

**What was done**
- Wrote `src/ingest/news.py`
- Queried GDELT Doc 2.0 API for "dengue philippines", one request per quarter (48 quarters, 2012–2023)
- Saved `data/processed/news.parquet` — 3,051 articles after deduplication

**Problems encountered**
- GDELT Doc 2.0 API was highly unreliable: ~60% of requests failed with empty non-JSON responses, HTTP 429 rate limits, connection resets, or timeouts.
- Coverage before 2017 was nearly zero — the Doc 2.0 API has limited historical depth for pre-2017 queries.
- **Resolution:** Accepted partial data. Quarters that succeeded returned up to 250 articles each (API max). Data from 2017–2023 was more consistent. News signal is supplementary for the agents, not a hard requirement for the risk model.

---

### Step 4 — Google Trends

**Status:** DONE (partial data — see problems)

**What was done**
- Wrote `src/ingest/trends.py`
- Pulled weekly interest for 4 keywords ("dengue", "dengue symptoms", "dengue fever", "lagnat ng dengue") across 3 five-year chunks (2012–2016, 2017–2021, 2022–2023) for Philippines (geo="PH")
- Saved `data/processed/trends_weekly.parquet` — 1,777 rows across 4 keywords

**Problems encountered**
- Initial `TrendReq` call used `retries` and `backoff_factor` parameters which pytrends passes to `urllib3.Retry`. In urllib3 v2.0+, the `method_whitelist` argument was removed, causing a `TypeError` before any request was made.
- **Resolution:** Removed `retries` and `backoff_factor` from the `TrendReq` constructor and implemented retry logic manually in `_fetch_chunk`. Fixed on re-run.
- "lagnat ng dengue" (Tagalog term) returned no data for 2012–2021 chunks — likely too low a search volume for the pytrends API to return weekly resolution. Only the 2022–2023 chunk succeeded (106 rows). Accepted as-is.
- Google rate-limited aggressively (HTTP 429) throughout — the 30s/60s/90s backoff handled most cases but some chunks still failed after 3 retries.

---

### Step 5 — Geographic Data (GADM)

**Status:** DONE (with a note — see problems)

**What was done**
- Wrote `src/ingest/geo.py`
- Downloaded GADM 4.1 Philippines level-1 GeoJSON from `geodata.ucdavis.edu` → saved to `data/raw/geo/ph_regions.geojson`
- Computed centroids for all features → saved to `data/processed/region_centroids.parquet` (81 rows)

**Problems encountered**
- GADM level 1 for the Philippines returns **81 provinces**, not 17 administrative regions. In GADM's hierarchy, the Philippines treats provinces as the first sub-national division (unlike most countries where level 1 = top-level regions).
- **Impact:** The GeoJSON features do not align with the region names in the OpenDengue data. For the Phase 4 choropleth map, we will need to either: (a) aggregate province polygons to regions using a province→region lookup table, or (b) find a region-level GeoJSON from a different source (e.g., PSA official shapefiles or a community repo).
- **Resolution for now:** Kept the 81-province GeoJSON and centroids as useful raw data. The province→region mapping and choropleth rendering will be handled in Phase 4.

---

### Step 6 — SQLite Database

**Status:** DONE

**What was done**
- Wrote `src/ingest/database.py`
- Loaded all 7 processed parquet files into `data/sentinel.db`:
  - `cases_national_weekly` — 544 rows
  - `cases_regional_annual` — 224 rows
  - `cases_provincial_monthly` — 9,060 rows
  - `weather_daily` — 78,894 rows
  - `news` — 3,051 rows
  - `trends_weekly` — 1,777 rows
  - `region_centroids` — 81 rows
- Database size: 8.3 MB

**Problems encountered**
- None.

---

### Step 7 — Tests

**Status:** DONE

**What was done**
- `tests/test_ingest_opendengue.py` — 15 tests
- `tests/test_ingest_weather.py` — 8 tests
- `tests/test_ingest_news.py` — 5 tests
- `tests/test_ingest_geo.py` — 7 tests
- `tests/test_ingest_trends.py` — 6 tests
- `tests/test_ingest_database.py` — 6 tests
- **Total: 49/49 passing** (including the 2 smoke tests from Phase 0)

**Problems encountered**
- `test_temperature_range` initially asserted `t_max > 15°C`, which failed for the Cordillera Administrative Region (CAR) — a highland area where temperatures legitimately drop below 15°C. Corrected the lower bound to `5°C`.

---

## Phase 2 — RAG Layer

**Status:** DONE
**Started:** 12 May 2026
**Completed:** 12 May 2026

---

### Step 1 — RAG Corpus Selection

**Status:** DONE

**What was done**
- User selected 8 dengue-related PDF documents and placed them in `data/raw/rag_corpus/`
- PDFs confirmed to be text-extractable (not image-based scans):
  - `5_national-clinical-guideline-of-dengue-timor-leste_clean_final-12-dec-2022.pdf` — 93 pages
  - `9789241547871_eng.pdf` — 160 pages (WHO Dengue Guidelines for Diagnosis, Treatment, Prevention & Control)
  - `9789241549738-eng.pdf` — 92 pages (WHO Technical Handbook: Dengue Surveillance)
  - `abm-15-5-abm-2021-0027.pdf` — 10 pages (dengue epidemiology Philippines research)
  - `ajtmh.23-0250.pdf` — 9 pages (American Journal of Tropical Medicine and Hygiene)
  - `Dengue-20250109.pdf` — 12 pages (WHO WPRO Dengue Situation Update 714, Jan 2025)
  - `pntd.0007280.pdf` — 18 pages (dengue research trends in Philippines systematic review)
  - `tropmed-96-887.pdf` — 12 pages (American Journal of Tropical Medicine and Hygiene)

**Problems encountered**
- The DOH EDCS Disease Surveillance Reports were image-based scanned PDFs containing multiple diseases mixed together. Running OCR locally was not viable on available hardware.
- **Resolution:** Replaced with the 8 text-extractable PDFs above. Documented in project plan revision v1.2.

---

### Step 2 — Corpus Indexing (ChromaDB)

**Status:** DONE

**Tools used**
- `langchain-community` — `PyPDFLoader` for PDF text extraction
- `langchain-text-splitters` — `RecursiveCharacterTextSplitter` (chunk_size=800, overlap=100)
- `langchain-huggingface` — `HuggingFaceEmbeddings` with `BAAI/bge-small-en-v1.5`
- `sentence-transformers` — CPU inference backend for embeddings
- `langchain-chroma` — `Chroma.from_documents()` for persistence
- `chromadb` — local persistent vector store

**Files created/used**
- `src/rag/indexer.py` — main indexing module
  - `build_index(corpus_dir, chroma_dir, force)` — builds or loads ChromaDB vector store
  - Constants: `CORPUS_DIR`, `CHROMA_DIR`, `COLLECTION_NAME`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `EMBED_MODEL`
- `data/chroma/` — persisted ChromaDB index (excluded from git via `.gitignore`)
- Input: 8 PDFs in `data/raw/rag_corpus/`
- Output: 1,617 chunks from 406 total PDF pages

**Problems encountered**
- `from langchain.text_splitter import RecursiveCharacterTextSplitter` raised `ImportError` — in LangChain 0.3+, text splitters were moved to the separate `langchain-text-splitters` package.
- `from langchain.vectorstores import Chroma` also failed — ChromaDB integration was moved to `langchain-chroma` (separate package).
- `from langchain.embeddings import HuggingFaceEmbeddings` failed — HuggingFace embeddings moved to `langchain-huggingface` (separate package).
- **Resolution:** Installed `langchain-chroma==1.1.0` and `langchain-huggingface==1.2.2` via `uv pip install`, updated imports to `langchain_chroma`, `langchain_huggingface`, `langchain_text_splitters`, and added both packages to `pyproject.toml` dependencies.

---

### Step 3 — Retriever

**Status:** DONE

**Tools used**
- `langchain-chroma` — `Chroma` for loading persisted vector store
- `langchain-huggingface` — `HuggingFaceEmbeddings` (same model as indexer)
- `langchain-core` — `Document` type for typed retrieval results

**Files created/used**
- `src/rag/retriever.py`
  - `load_vectorstore(chroma_dir)` — loads existing ChromaDB index; raises `FileNotFoundError` if not built
  - `retrieve(question, vectorstore, k=5)` — `similarity_search` returning top-k `Document` objects
  - `format_passages(docs)` — formats documents as numbered `[1]..[5]` passage block with `(Source: filename, page N)` headers for use in LLM prompts
  - `TOP_K = 5`

**Problems encountered**
- None.

---

### Step 4 — LangGraph Chat Workflow

**Status:** DONE

**Tools used**
- `langgraph` — `StateGraph`, `END`, conditional edges
- `langchain-groq` — `ChatGroq` with `llama-3.3-70b-versatile`
- `langchain-core` — `HumanMessage`, `SystemMessage`
- `python-dotenv` — loads `GROQ_API_KEY` from `.env`

**Files created/used**
- `src/rag/chat.py`
  - `RAGState` — `TypedDict` with fields: `question`, `passages_text`, `valid_ids`, `answer`, `attempts`, `valid`, `feedback`
  - `node_retrieve` — calls `load_vectorstore()` and `retrieve()` to populate `passages_text` and `valid_ids`
  - `node_generate` — calls `ChatGroq` with system prompt enforcing citations; uses refinement prompt on retries
  - `node_validate` — calls `ChatGroq` to audit that every claim in the answer has a valid passage citation; returns `PASS` or `FAIL: <reason>`
  - `_should_retry` — routing function: returns `"end"` if `valid=True` or `attempts >= MAX_RETRIES (3)`, else `"generate"`
  - `build_graph()` — assembles the compiled `StateGraph` (retrieve → generate → validate, with conditional retry loop)
  - `ask(question)` — public API; returns `{"answer", "attempts", "valid"}`
  - Module-level `_graph` singleton to avoid rebuilding the graph on every call

**Graph topology**
```
retrieve → generate → validate
                ↑           |
                └── retry ──┘  (max 3 attempts, then accept)
```

**Problems encountered**
- None.

---

### Step 5 — CLI Chat Interface

**Status:** DONE

**Tools used**
- `src.rag.chat.ask` — the LangGraph workflow

**Files created/used**
- `src/rag/cli.py`
  - Interactive terminal loop: reads user input, calls `ask()`, prints answer with citation validity and attempt count
  - Usage: `python -m src.rag.cli`
  - Commands: `quit`/`exit` to leave; empty input is ignored

**Problems encountered**
- None.

---

### Step 6 — Evaluation Set

**Status:** DONE

**Tools used**
- `src.rag.chat.ask` — for full RAG pipeline evaluation
- `src.rag.retriever` — for retrieval-only recall measurement

**Files created/used**
- `src/rag/eval.py`
  - `EVAL_SET` — 30 curated dengue Q&A pairs, each with `gold_keywords` (expected in answer) and `retrieval_keywords` (expected in retrieved passages)
  - `run_eval(questions, delay_s)` — runs all questions through RAG pipeline, computes per-question scores
  - Metrics: retrieval recall (keyword overlap in passages), answer accuracy (keyword overlap in answer), citation rate (% of answers with at least one `[N]` citation)
  - `print_summary(results)` — aggregate metrics table
  - `save_results(results, path)` — saves full results as JSON
  - Usage: `python -m src.rag.eval` or `python -m src.rag.eval --questions 10 --save`

**Problems encountered**
- None.

---

### Step 7 — RAG Tests

**Status:** DONE

**Tools used**
- `pytest` — test runner
- `unittest.mock` — mock `ChatGroq`, `load_vectorstore`, `retrieve`, `format_passages` for unit tests

**Files created/used**
- `tests/test_rag_retriever.py` — 9 tests
  - Vectorstore load/fail, top-k retrieval, page content presence, source metadata, `format_passages` structure, empty-list edge case, dengue relevance check
- `tests/test_rag_chat.py` — 8 tests
  - Graph builds, `RAGState` fields, routing logic (valid/exhausted/retry), mocked end-to-end `ask()` happy path, mocked retry path, missing API key raises `EnvironmentError`
- **Total new tests: 17**
- **Total passing: 66/66** (all phases combined)

**Problems encountered**
- None.

---

### Step 8 — Live CLI Testing and Bug Fixes

**Status:** DONE

**What was done**
- Ran `python -m src.rag.cli` interactively and tested 6 dengue questions against the live Groq API.

**Test results**

| Question | Attempts | Valid | Notes |
|---|---|---|---|
| Dengue virus + four serotypes | 1 | ✓ | Ideal first-try result |
| Dengue transmission | 3 | ⚠ | Well-cited answer; validator over-strict (false positive) |
| Peak biting hours of Aedes | 2 | ✓ | Correct "passages do not contain" refusal — honest RAG behaviour |
| Incubation period | 3 | ✓ | Correct; verbose meta-commentary in answer (fixed) |
| "Breakbone fever" | 3 | ⚠ | Validator correctly caught speculative "likely given because…" (true positive) |
| Warning signs of severe dengue | 2 | ✓ | Clean, well-cited, ideal result |

**Problems encountered and solutions**

1. **Embedding model reloaded on every question** — `node_retrieve` called `load_vectorstore()` directly, which constructed a new `HuggingFaceEmbeddings` instance (and re-loaded 199 weight shards) on each invocation. Symptom: `Loading weights: 100%|…| 199/199` appeared before every answer.
   - **Fix:** Added a module-level `_vectorstore` singleton in `src/rag/chat.py` and a `_get_vectorstore()` helper. `node_retrieve` now calls `_get_vectorstore()` instead of `load_vectorstore()` directly. Weights load once per process on the first question; all subsequent questions are instant.

2. **"Not in passages" answer cited all five passages** — When retrieved chunks did not contain the answer, the model appended `[1][2][3][4][5]` to the "passages do not contain…" sentence. This was misleading (citing the absence of information).
   - **Fix:** Added to `SYSTEM_PROMPT`: *"If the passages do not contain enough information to answer, say so explicitly — do not cite passages in that case."*

3. **Verbose citation meta-commentary on retries** — After multiple failed validator attempts the model began appending a separate sentence explaining which passage supported which claim (e.g. *"It's worth noting that [3] supports X while [1] supports Y…"*). Redundant given inline citations already convey this.
   - **Fix:** Added to `SYSTEM_PROMPT`: *"Do NOT add a separate sentence explaining which passage supports which claim — let the inline citations speak for themselves."*

**Files changed**
- `src/rag/chat.py` — added `_vectorstore` singleton + `_get_vectorstore()`, updated `node_retrieve`, updated `SYSTEM_PROMPT`

**Tests after fixes: 66/66 still passing.**

---

## Phase 3 — Multi-Agent System + Risk Scoring

**Status:** In Progress
**Started:** 12 May 2026

---

### Step 1 — Feature Engineering

**Status:** DONE

**Tools used**
- `pandas` — data loading, merging, resampling, lag/rolling operations
- `numpy` — log1p transformation, NaN handling
- `src.model.features` — main feature builder

**Files created/used**
- `src/model/features.py`
  - `build_features()` → returns full feature DataFrame (535 rows × 27 cols) with no NaN
  - `get_feature_columns(df)` → returns ordered list of 25 input feature columns
  - `_load_cases()` — loads `cases_national_weekly.parquet`
  - `_load_weather_weekly(cases)` — aggregates 18-region daily weather to national weekly (mean t_max/t_min/rh, sum precip) aligned to case week boundaries via `merge_asof`
  - `_load_trends_weekly(cases)` — pivots trends by keyword (dengue, dengue symptoms, dengue fever), aligns to case weeks
  - `_load_news_weekly(cases)` — counts news articles per case week
  - Lag features: case lags at 1, 2, 4, 8 weeks; 4-week rolling mean of cases
  - Weather lags: each of 4 weather vars at lag 1 and 2 (current-week weather excluded — dengue reacts to past conditions)
  - Trend lags: each keyword at lag 1; current-week trends kept (search precedes diagnosis by ~1 week)
  - Calendar features: `epiweek`, `month`, `is_rainy_season` (June–November)
  - Target: `target_log_cases` = `log1p(cases of next week)` via `shift(-1)`
  - 9 rows dropped for NaN (8 lag initialisation rows at start + 1 missing target at end)

**Feature columns (25):** `year`, `epiweek`, `trend_dengue`, `trend_fever`, `trend_symptoms`, `news_count`, `cases_lag1`, `cases_lag2`, `cases_lag4`, `cases_lag8`, `cases_roll4`, `weather_t_max_lag1`, `weather_t_max_lag2`, `weather_t_min_lag1`, `weather_t_min_lag2`, `weather_precip_lag1`, `weather_precip_lag2`, `weather_rh_lag1`, `weather_rh_lag2`, `trend_dengue_lag1`, `trend_symptoms_lag1`, `trend_fever_lag1`, `news_count_lag1`, `month`, `is_rainy_season`

**Problems encountered**
- `pd.merge_asof` on cases (`datetime64[us]`) and trends (`datetime64[ms]`) raised `MergeError: incompatible merge keys`. Fixed by casting trends dates to `datetime64[us]` before the merge.
- `→` arrow character in a `print()` caused `UnicodeEncodeError` on Windows cp1252 terminal. Fixed by using `to` instead.

---

### Step 2 — Model Training

**Status:** DONE

**Tools used**
- `xgboost` — `XGBRegressor` with early stopping on validation set
- `scikit-learn` — `mean_squared_error`, `mean_absolute_error`
- `statsmodels` — `ARIMA(2,1,2)` rolling baseline
- `joblib` — model serialisation
- `src.model.features` — feature matrix builder

**Files created/used**
- `src/model/train.py`
  - `temporal_split(df)` → (train, val, test) by date — train ≤ 2020-12-31, val = 2021, test ≥ 2022-01-01
  - `train_xgboost(X_train, y_train, X_val, y_val)` — XGBRegressor with early stopping
  - `naive_seasonal_predict(train, eval_df)` — baseline: mean of same epiweek from training set
  - `arima_predict(train, eval_df)` — rolling one-step-ahead ARIMA(2,1,2) forecast
  - `compute_thresholds(train_preds)` — tertile thresholds (33rd/67th percentile) for LOW/MEDIUM/HIGH
  - `run_training(force)` → trains, evaluates all models, saves artifacts, returns metadata dict
  - `print_report(meta)` → prints comparison table and feature importance bar chart
- `models/xgb_dengue_risk.joblib` — saved XGBoost model
- `models/model_meta.json` — feature columns, thresholds, top features, all evaluation metrics

**Temporal split sizes:** train=390 weeks, val=49 weeks, test=96 weeks

**Results (test set — 2022–2023):**

| Model | RMSE (log) | MAE (log) | RMSE (cases) | MAE (cases) |
|---|---|---|---|---|
| **XGBoost** | **0.7024** | **0.4579** | **978.7** | **768.0** |
| Naive seasonal | 1.1820 | 0.8612 | 2580.7 | 1998.1 |
| ARIMA (2,1,2) | 1.0715 | 0.8618 | 2908.0 | 2002.8 |

XGBoost outperforms both baselines by ~40% on RMSE (log scale). Case-level RMSE of ~979 means predictions are typically within ~979 cases of the true value per week.

**Top features by importance:**
1. `cases_lag1` (0.2452) — strongest signal: recent case trajectory
2. `cases_roll4` (0.2279) — 4-week trend
3. `cases_lag2` (0.1381) — secondary lag
4. `weather_rh_lag2` (0.0312) — humidity 2 weeks prior
5. `weather_precip_lag2` (0.0304) — rainfall 2 weeks prior

**Risk thresholds (log scale):** LOW ≤ 7.56 | MEDIUM ≤ 8.27 | HIGH > 8.27

**Problems encountered**
- `model.best_iteration` raised `AttributeError` — in newer XGBoost, this attribute only exists when `early_stopping_rounds` is set. Fixed by moving `early_stopping_rounds=50` from `fit()` to the `XGBRegressor` constructor.
- `XGBModel.fit() got an unexpected keyword argument 'early_stopping_rounds'` — confirmed that in XGBoost 2.x, `early_stopping_rounds` belongs in the constructor, not `fit()`.
- ARIMA convergence warning on some windows ("Maximum Likelihood optimization failed to converge") — non-fatal; model still produces predictions. Accepted as expected behaviour for short windows.

---

### Step 3 — Risk Scorer Wrapper

**Status:** DONE

**Tools used**
- `joblib` — load saved XGBoost model
- `src.model.features` — build feature matrix for prediction

**Files created/used**
- `src/model/risk_scorer.py`
  - `RiskScorer` class with `load()`, `predict(as_of_date)`, `predict_range(start, end)`
  - `predict()` returns: `as_of_date`, `forecast_week` (7 days later), `predicted_cases` (back-transformed), `log_pred`, `risk_level` (LOW/MEDIUM/HIGH), `top_drivers` (top 5 features with values and importances)
  - Sample output for 2023-10-01: 3,675 estimated cases, MEDIUM risk

**Problems encountered**
- None.

---

### Step 4 — Model Tests

**Status:** DONE

**Files created/used**
- `tests/test_model_features.py` — 13 tests
  - No-NaN assertion, expected columns, target log-scaling, date range, no future leakage in lags, binary rainy season, epiweek range, non-negative news counts
- `tests/test_model_risk_scorer.py` — 15 tests
  - Load/fail, prediction key schema, risk level validity, case count positive, log pred range, 7-day forecast offset, string/date input, top drivers shape and keys, out-of-range error, predict_range list output
- **Total new tests: 28**
- **Total passing: 94/94** (all phases combined)

---

### Step 5 — Multi-Agent Briefing Workflow

**Status:** DONE

**Tools used**
- `langgraph` — `StateGraph`, conditional edges, 4-node graph
- `langchain-groq` — `ChatGroq` (llama-3.3-70b-versatile) for briefing generation and evaluation
- `sqlite3` / `pandas` — DB queries for case, weather, trends, news data
- `src.model.risk_scorer` — `RiskScorer.predict()` for risk level and top drivers

**Files created/used**
- `src/agents/briefing.py`
  - `AgentState` TypedDict: `as_of_date`, `context`, `risk`, `briefing`, `attempts`, `valid`, `feedback`
  - `_build_context(as_of_date)` — queries SQLite for last 8 weeks of cases (WoW %, YoY %, 4-week trend), national weekly weather averages, latest Google Trends index, 4-week news count; returns structured context dict
  - `node_build_context` → `node_score_risk` → `node_generate_briefing` → `node_evaluate_briefing`
  - Evaluator checks 3 criteria: DATA_GROUNDING (all numbers from context), UNCERTAINTY (hedged language), NO_MEDICAL (no treatment/diagnosis advice); returns `PASS` or `FAIL_<criterion>: <reason>`
  - Retry loop: up to `MAX_RETRIES=3` if evaluator fails
  - `run(as_of_date)` → `{briefing, context, risk, attempts, valid}`

**Graph topology**
```
build_context → score_risk → generate_briefing → evaluate_briefing
                                    ↑                      |
                                    └────── retry ──────────┘
```

**Live test output (2023-10-01):**
- 3,142 cases (WoW: -1.2%, YoY: -18.7%), falling 4-week trend
- MEDIUM risk, est. 3,675 cases next week
- Briefing generated with specific numbers, hedged language, no medical advice
- `WARN | attempts=3` — evaluator was over-strict (same pattern as RAG validator); final briefing is correct
- Output saved to `data/processed/weekly_briefings/2023-10-01/briefing.json`

**Problems encountered**
- None during implementation. Date filtering in SQL required using pandas `parse_dates` + in-Python filtering rather than SQL string comparison (dates stored as "YYYY-MM-DD HH:MM:SS" strings in SQLite — boundary cases can be tricky with plain string `<=` comparison).

---

### Step 6 — Weekly Run CLI

**Status:** DONE

**Files created/used**
- `src/agents/weekly_run.py`
  - `main()` — CLI entry point: `--date YYYY-MM-DD` (default: latest in DB), `--save` flag
  - `_latest_available_date()` — queries `MAX(week_start)` from SQLite
  - `save_output(result, out_dir)` — writes `data/processed/weekly_briefings/{date}/briefing.json` with `generated_at` timestamp
  - `print_result(result)` — summary header + full briefing text

**Usage:** `python -m src.agents.weekly_run --date 2023-10-01 --save`

**Problems encountered**
- None.

---

### Step 7 — Agent Tests

**Status:** DONE

**Files created/used**
- `tests/test_agents_briefing.py` — 15 tests
  - Context builder: expected keys, cases fields, trend direction validity, weather range check, rainy season flags (October = True, February = False), news count non-negative, raises on pre-data date
  - Routing: valid→end, exhausted→end, invalid+remaining→generate
  - Graph builds without error
  - Mocked end-to-end `run()`: correct keys returned on PASS, retry triggered on FAIL then resolved
  - `save_output`: JSON file created with correct content and `generated_at` field
- **Total new tests: 15**
- **Total passing: 109/109** (all phases combined)

**Problems encountered**
- None.

---

## Phase 4 — Fine-Tuning + Dashboard + Deployment

**Status:** In Progress (sub-phase 4b dashboard done; deployment files ready)
**Started:** 19 May 2026

---

### Step 1 — Streamlit Dashboard

**Status:** DONE

**Tools used**
- `streamlit` — 4-tab dashboard layout, `@st.cache_resource`, `@st.cache_data`, `st.session_state`
- `plotly.express` / `plotly.graph_objects` — line charts, bar charts, scatter_map
- `plotly.subplots.make_subplots` — weather subplot (temperature + rainfall)
- `src.model.risk_scorer` — RiskScorer loaded via `@st.cache_resource`
- `src.rag.chat` — LangGraph RAG graph loaded via `@st.cache_resource`
- `src.agents.briefing` — weekly run workflow triggered from Briefing tab

**Files created/used**
- `src/dashboard/app.py` — main Streamlit application
  - **Sidebar:** national risk badge (colored chip), latest week cases metric (WoW %), data/model attribution
  - **Tab 1 — Overview:** 4 KPI columns (WoW cases, YoY, 4-week trend direction, season), province scatter map (81 GADM points, open-street-map), "About" panel with model specs and top drivers
  - **Tab 2 — Trends:** year range filter, national weekly cases chart with rainy season shading (Jun–Nov vrect), 2-panel weather subplot (T max/min line + weekly rainfall bar), Google Trends "dengue" interest chart
  - **Tab 3 — Chat:** RAG chat with `st.chat_input`, `st.session_state.messages` history, per-message citation validity caption, clear button
  - **Tab 4 — Briefing:** date picker over available data range, "Generate Briefing" button triggers `run(as_of_date)`, auto-saves to `data/processed/weekly_briefings/`, loads existing JSON on re-visit, renders risk level chip + predicted cases + validator status + full briefing text + context JSON expander

**Map note:** Used `px.scatter_map` (Plotly 6.x) with `map_style="open-street-map"` — no API key required. Province dots show 81 GADM centroids without regional case join (data granularity mismatch; honest v1 behavior).

**Singleton pattern in dashboard:**
- `@st.cache_resource` for `RiskScorer` (loads joblib model) and LangGraph graph (builds and compiles once)
- `@st.cache_data` for all DataFrames (parquets cached across reruns)
- Groq API key bridged from `st.secrets → os.environ` at startup so `os.getenv("GROQ_API_KEY")` works in downstream modules on both local (`.env`) and Streamlit Community Cloud (Secrets dashboard)

**Tested locally:** `streamlit run src/dashboard/app.py` → server started cleanly, HTTP 200 on healthz endpoint, no runtime errors in startup logs.

**Problems encountered**
- `px.scatter_mapbox` deprecated in Plotly 6.x → replaced with `px.scatter_map` + `map_style` parameter.
- `st.secrets` raises `StreamlitSecretNotFoundError` locally when no `secrets.toml` exists — `"GROQ_API_KEY" in st.secrets` triggers a file parse. Fixed by wrapping in `try/except Exception: pass`.

---

### Step 3 — Dashboard Redesign (v2)

**Status:** DONE

**Trigger:** Full user review after first local test. Six issues raised:
1. Not user-friendly for normal people
2. Design not modern or visually appealing
3. Technical jargon visible to users
4. Tab navigation feels outdated
5. "Latest cases" from 2023 shown as current — misleading in 2026
6. Province dot map (81 points, no data) serves no purpose

**What changed in the redesign**

| Before | After |
|---|---|
| `st.tabs(["Overview","Trends","Chat","Briefing"])` | Sidebar radio navigation (4 pages) |
| "Latest Week Cases: 2,607 (+34.5% WoW)" | Removed — data is from 2023, framing as "current" is dishonest |
| "epiweek", "WoW", "YoY", "RMSE", "XGBoost" | Completely removed from all user-facing text |
| Province scatter map (81 dots, lat/lon only) | Regional bar chart: top 15 regions by total cases (actual information) |
| No data-age context anywhere | "Data period: 2012–2023" in sidebar + explicit notice on Report page |
| Tabs with no explanation | Every page opens with a blue intro box explaining what the user is looking at |
| Health disclaimer buried | Disclaimer in sidebar + on every page that touches health |

**New page structure**
- **Overview** — Hero banner, 4 historical stat cards (total cases, weekly avg, worst week, peak season), regional case bar chart (most affected regions), prevention tips with expandable cards
- **Explore the Data** — Year filter, weekly cases line chart with rainy season shading, weather subplot (temperature + rainfall), Google search interest chart; all with plain-language intro boxes
- **Ask About Dengue** — RAG chat with example questions, plain spinner text, "✓ verified" status in plain words
- **Situation Report** — Date picker with explicit "data is from 2012–2023" notice; generates historical briefings for any past week

**Design decisions**
- Custom CSS: red gradient hero, white shadow cards with red top border, blue intro boxes, amber data-age notices
- `inject_css()` called once at startup — no repeated injection
- Removed scorer from sidebar and overview (not meaningful without current data)
- Regional bar chart replaces map: shows `cases_regional_annual.parquet` aggregated by region — actual useful information

---

### Step 2 — Deployment Files

**Status:** DONE

**Files created/used**
- `requirements.txt` — pip-installable dependencies for Streamlit Community Cloud
  - `--extra-index-url https://download.pytorch.org/whl/cpu` + `torch` to get CPU-only PyTorch (~500 MB vs 2 GB full CUDA build); `sentence-transformers` requires torch for BAAI/bge-small-en-v1.5 inference
- `.streamlit/config.toml` — server settings (headless=true, port 8501), theme (red primary, white BG), usage stats disabled
- `.streamlit/secrets.toml.example` — template showing `GROQ_API_KEY = "gsk_..."` for user to paste into Streamlit Community Cloud Secrets dashboard

**gitignore updated**
- Removed blanket exclusion of `data/processed/*.parquet`, `data/chroma/`, `models/*.joblib`, `models/*.json`, `data/*.db` — these are now committed for deployment
- Total committed data: ~29 MB (parquets 600 KB + SQLite 8.2 MB + ChromaDB 20 MB + model 152 KB + meta 4 KB) — well within GitHub (100 MB/file) and Streamlit Community Cloud (1 GB) limits
- Added `.claude/` to gitignore (Claude Code session memory — not project code)
- Raw source files (PDFs, GeoJSON, shapefiles, zip downloads) remain gitignored

**Deployment target:** Streamlit Community Cloud (not HF Spaces — user's HF Spaces are at capacity). Free tier, 1 app, direct GitHub integration.

**Problems encountered**
- None.

---

### Step 4 — Dashboard v4 Redesign

**Status:** DONE

**Trigger:** User review of v3. Two issues raised:
1. FAB was invisible and non-intuitive — users would not know the main features exist
2. Modal dialogs (via `@st.dialog`) added friction — two-click access through a popover then a modal
3. Map with `carto-positron` (light tiles) clashed visually with the dark `#0F172A` UI

**What changed**

| Before (v3) | After (v4) |
|---|---|
| FAB (fixed circle, bottom-right) + `st.popover` → `@st.dialog` | 3 always-visible labeled nav buttons below the main view (no FAB, no popover, no modal) |
| Light `carto-positron` map tiles | Dark `carto-darkmatter` tiles — cohesive with dark UI |
| Simple opaque bubbles | Glow-ring trace (semi-transparent outer) + opaque inner bubble + region text labels |
| Hover labels unstyled | Custom `hoverlabel` (dark panel bg, white text) |
| Tips in `st.expander` blocks | 5 tip cards in 3+2 grid — all content visible at once |
| Chat accessible only through FAB → popover → dialog | Chat inline: suggestion pills on first load, `st.container(height=280)` for scrollable history, `st.chat_input` below |
| Report accessible only through FAB → popover → dialog | Report inline: date picker + generate button + auto-shows latest cached briefing as preview |
| `overflow: hidden` (no page scroll) | `overflow-x: hidden` — allows vertical scroll when feature panels open |

**Architecture change:** All `@st.dialog` decorators removed. Feature panels rendered as conditional `<div class="feature-panel">` containers controlled by `st.session_state.active_panel`. Nav buttons toggle the active panel (same button click closes it).

**Problems encountered**
- `use_container_width=True` deprecated in `st.plotly_chart` in Streamlit 1.40+ → replaced with `width="stretch"` call pattern removed; used `use_container_width=True` which is still valid for plotly_chart specifically (not all widgets). ✓
- `st.columns([1, 1, 0.02])` used for tips row 2 to approximate centering two cards in a 3-column grid — the third slot is near-zero width, leaving two wider cards. ✓

---

### Pending Steps

- **Sub-phase 4a — Fine-tuning** (stretch goal): Llama 3.2 1B on Filipino dengue health text, Google Colab T4, push to HF Hub at `aces-14/sentinel-ph-ner-v1`
- **Sub-phase 4c — Deploy**: User commits all new files → push to GitHub → connect repo to Streamlit Community Cloud → set entry point to `src/dashboard/app.py` → add `GROQ_API_KEY` in Secrets dashboard
- **Sub-phase 4d — Open-source dataset**: Push cleaned parquets to HF Datasets as `aces-14/ph-dengue-surveillance`
- **Sub-phase 4e — Blog post + LinkedIn**: Drafts prepared in `scripts/linkedin_post.md` and `scripts/blog_post.md`
