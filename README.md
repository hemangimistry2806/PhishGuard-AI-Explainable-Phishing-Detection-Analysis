# PhishGuard-AI: Explainable Phishing URL Detection & Analysis

PhishGuard-AI is an end-to-end cybersecurity system combining tree-based machine learning (XGBoost), explainable AI (SHAP TreeExplainer), large language model reasoning, Public Suffix List (PSL) domain extraction, persistent feedback telemetry, and a modern single-page slider interface.

---

## 1. System Architecture

```
                       ┌──────────────────────────────────────────────────────────┐
                       │           PhishGuard-AI Frontend (React + Vite)          │
                       │             Single-Page Slider (4 Navigable Slides)      │
                       └─────────────┬──────────────────────────────┬─────────────┘
                                     │                              │
                    Live URL Analysis│                              │Feedback & Analytics
                                     ▼                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                 FastAPI Backend (Port 8000)                             │
├──────────────────────────┬─────────────────────────────┬────────────────────────────────┤
│      URL Feature         │     Prediction & SHAP       │     Feedback Persistence       │
│       Extractor          │          Service            │           & Review             │
├──────────────────────────┼─────────────────────────────┼────────────────────────────────┤
│ • Public Suffix List     │ • XGBoost Classifier        │ • SQLite DB (phishguard.db)    │
│ • SSRF Protection        │ • 50 Ordered Features       │ • Privacy URL Redaction        │
│ • Heuristic HTML Parse   │ • SHAP TreeExplainer        │ • Disagreement Analytics       │
│ • Lexical Analysis       │ • LLM Narrative Reasoning   │ • Auditor Verification Workflow│
└──────────────────────────┴─────────────────────────────┴────────────────────────────────┘
```

---

## 2. Model Label Mapping & Inference Protocol

In accordance with the **PhiUSIIL Phishing URL Dataset** benchmark convention:
* **`0` = Phishing**
* **`1` = Legitimate**

The serialized XGBoost model (`ml/models/xgboost_model.pkl`) uses classes `[0, 1]`. Therefore, probability outputs are mapped consistently:
* `model.predict_proba(X)[0]`: **Phishing probability** (Class 0)
* `model.predict_proba(X)[1]`: **Legitimate probability** (Class 1)
* **Confidence**: Calculated strictly as the probability associated with the predicted class (`phishing_prob` if prediction=0, `legitimate_prob` if prediction=1).
* **SHAP Log-Odds Attribution**:
  * Positive values (`+Legitimate`): Features pushing the model toward Legitimate.
  * Negative values (`-Phishing`): Features pushing the model toward Phishing.

---

## 3. Live URL Feature Extraction & Approximations

Live URL extraction (`backend/services/url_feature_extractor.py`) accepts raw URL strings and computes the 50 features expected by the model:
1. **Registered Domain Extraction**: Uses the official **Public Suffix List** via `tldextract` to separate subdomains, registered domains, and multi-part ccSLDs (e.g., `google.com.kill-credential.net` correctly yields registered domain `kill-credential.net`).
2. **SSRF Protection**: Validates URL hostnames and DNS resolutions against loopback (`127.0.0.0/8`, `::1`), private subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local, and cloud metadata (`169.254.169.254`). Restricted requests are safely blocked before network invocation.
3. **Approximation Transparency (`URLSimilarityIndex`)**:
   * *Dataset Definition*: In the PhiUSIIL dataset, `URLSimilarityIndex` measured distance against the targeted brand's legitimate domain. 100% of legitimate training records have `URLSimilarityIndex = 100.0`, and this single feature represents **97.96% of XGBoost Gain Importance**.
   * *Live Inference*: Because the target brand being impersonated is unknown a priori during real-time inference, the live extractor identifies brand spoofing keywords (e.g. `paypal`, `google`) in subdomains or paths when the registered domain is unassociated. Otherwise, it calculates Jaccard character set consistency.
   * *Honest Disclosures*: The frontend and API explicitly disclose when feature values are approximated.

---

## 4. Empirical Model Evaluation & Ablation Experiments

The evaluation pipeline (`ml/evaluate_model.py`) produces reproducible findings stored in `backend/reports/model_evaluation_report.json`:

### 4.1 Dataset Integrity Audit
* **Dataset Shape**: 235,795 rows, 55 columns (5 metadata + 50 features)
* **Class Balance**: 134,850 Legitimate (57.19%) vs. 100,945 Phishing (42.81%)
* **Missing Values**: Exactly 0 across all columns
* **Exact Duplicate URLs**: 425 duplicate URLs
* **Normalized Duplicate URLs**: 3,386 duplicates (stripping scheme & trailing slash)
* **Unique Registered Domains**: 175,509 registered domains

### 4.2 Baseline & Controlled Ablation Results (Identical 80:20 Split)
| Experiment / Model Architecture | Features Used | Accuracy | Precision (Phishing) | Recall (Phishing) | Macro F1 | ROC-AUC |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Production XGBoost Baseline** | 50 Features | **100.00%** | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| **XGBoost (Ablated: Without URLSimilarityIndex)** | 49 Features | **99.998%** | 1.0000 | 0.99995 | 0.99998 | 0.99999 |
| **XGBoost (Lexical URL Features Only)** | 21 Features | **99.743%** | 0.9995 | 0.9945 | 0.9974 | 0.9989 |
| **Random Forest Comparison Baseline** | 50 Features | **99.998%** | 1.0000 | 0.99995 | 0.99998 | 1.0000 |
| **Logistic Regression (StandardScaler + L2)** | 50 Features | **99.987%** | 1.0000 | 0.9997 | 0.99987 | 0.99999 |

### 4.3 Domain-Disjoint Generalization Evaluation
* **Protocol**: GroupShuffleSplit by PSL registered domain (80:20 split).
* **Isolation**: Exactly **0 shared registered domains** between train and test sets.
* **Sample Count**: 191,679 train URLs (140,407 domains), 44,116 test URLs (35,102 domains).
* **Result**: Retrained XGBoost without `URLSimilarityIndex` achieves **99.975% Accuracy** (17,157 true phishing caught, only 11 false positives) on completely unseen registered domains, proving genuine out-of-domain predictive power.

---

## 5. Persistent Feedback Database & Review Workflow

Feedback is stored persistently in SQLite (`backend/phishguard.db`) via SQLAlchemy:
* **Schema (`feedback_records`)**:
  * `id` (int PK), `analysis_id` (str), `url` (sanitized string), `registered_domain` (str)
  * `model_prediction`, `user_verdict`, `is_agreement` (bool)
  * `phishing_probability`, `legitimate_probability`, `confidence`
  * `comment` (max 1000 chars), `verification_status` (`pending`, `verified`, `rejected`)
  * `reviewer_id`, `review_notes`, `reviewed_at`, `extracted_features` (JSON vector), `created_at`
* **Privacy Redaction Policy**: Query parameters containing credentials (`token`, `auth`, `key`, `password`, `session`) or values longer than 32 characters are automatically replaced with `[REDACTED]`.

### 5.1 Feedback Lifecycle & Why Retraining is NOT Automatic
```
Raw Prediction ──► Feedback Submission (Status: pending) ──► Disagreement Telemetry
                                                                     │
                                                           Human Security Audit
                                                                     │
                                                   ┌─────────────────┴─────────────────┐
                                                   ▼                                   ▼
                                           Status: rejected                   Status: verified
                                                                                       │
                                                                       Candidate Training Dataset
                                                                                       │
                                                                           Offline Evaluation
```
* **Production Model Protection**: User-submitted feedback is unverified telemetry and is **never** used to automatically retrain or overwrite `xgboost_model.pkl`.
* **Auditor Verification**: Only human reviewers with `X-Reviewer-Key` can transition records to `verified`.
* **Candidate Dataset Export**: `GET /feedback/candidate-dataset` exports confirmed ground-truth data formatted for offline model evaluation.

---

## 6. Frontend Redesign: Single-Page Slider

The frontend is implemented as a single-page slider with 4 horizontal sections:
* **Slide 1 — URL Analysis**: Priority URL input with paste/clear controls, live backend health status, analyze action, inline notifications, and 30 verified PhiUSIIL benchmark samples.
* **Slide 2 — Prediction & Explainability**: Risk verdict badge, confidence score, dual probability meters, warnings/disclosures, TreeExplainer SHAP attribution breakdown (top 5 with full 50-feature expander), AI reasoning narrative, and direct feedback submission pre-linked to the analysis ID.
* **Slide 3 — Model Evaluation & Reliability**: Live-verified empirical metrics from backend, domain-disjoint generalization report with zero domain overlap, 5-model controlled ablation comparison table, and feature importance audit.
* **Slide 4 — Feedback & Analytics**: Telemetry dashboard showing total submissions, user agreement rates, potential false positives, potential false negatives, review lifecycle counts, filterable SQLite submission logs, auditor review modal, and candidate dataset export.

### 6.1 Slider Navigation
* Clickable section indicators with progress bar
* Previous (`Prev`) and Next (`Next`) controls
* Keyboard shortcuts: Left/Right arrows (`←` / `→`) and number keys (`1`, `2`, `3`, `4`)
* State preservation: switching slides never clears analysis inputs or prediction state

---

## 7. How to Run the Project

### Prerequisites
* Python 3.9+ with dependencies in `backend/requirements.txt`
* Node.js 18+ and npm in `frontend/`

### 1. Start the Backend API Server
```powershell
# From project root
python -m uvicorn app:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```
* Interactive API docs: `http://127.0.0.1:8000/docs`
* Health Check: `http://127.0.0.1:8000/`

### 2. Start the Frontend Development Server
```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```
* Application URL: `http://127.0.0.1:5173/`

### 3. Run Test Suites
```powershell
# Run backend regression tests (52 tests)
pytest backend/tests -v

# Run production frontend build validation
cd frontend
npm run build
```

### 4. Re-run Model Evaluation & Ablation Pipeline
```powershell
python ml/evaluate_model.py
```
Outputs the complete report to `backend/reports/model_evaluation_report.json`.

---

## 8. Docker Deployment & Containerization

PhishGuard-AI includes complete, containerized support for reproducible local execution using Docker and Docker Compose.

### 8.1 Docker Architecture

```
                       ┌────────────────────────────────────────────────────────┐
                       │                     Host Browser                       │
                       │     http://localhost:5173  /  http://localhost:8000    │
                       └───────────────┬────────────────────────┬───────────────┘
                                       │ Port 5173              │ Port 8000
                                       ▼                        ▼
┌──────────────────────────────────────────────┐  ┌──────────────────────────────────────────────┐
│        Container: phishguard-frontend        │  │         Container: phishguard-backend        │
│                (nginx:alpine)                │  │              (python:3.10-slim)              │
├──────────────────────────────────────────────┤  ├──────────────────────────────────────────────┤
│ • Production static build (/dist)            │  │ • FastAPI Application (Uvicorn)             │
│ • SPA fallback routing (try_files)           │  │ • Trained XGBoost Model (50 features)       │
│ • Reverse proxy to backend:8000 for APIs     │  │ • SHAP TreeExplainer & Feature Extractor     │
│ • Healthcheck on /nginx-health               │  │ • Non-root execution (appuser:1000)          │
└──────────────────────┬───────────────────────┘  └──────────────────────┬───────────────────────┘
                       │ Internal Docker Network                         │
                       └─────────────────────────────────────────────────┤
                                                                         ▼
                                                  ┌──────────────────────────────────────────────┐
                                                  │       Named Volume: phishguard_db_data       │
                                                  │         Mounted at /app/data (SQLite)        │
                                                  │          Survives container restarts         │
                                                  └──────────────────────────────────────────────┘
```

### 8.2 Container Configuration & Ports

| Service | Container Name | Base Image | Host Port | Internal Port | Healthcheck |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Backend** | `phishguard-backend` | `python:3.10-slim` | `8000` | `8000` | `curl -f http://localhost:8000/health` |
| **Frontend** | `phishguard-frontend` | `node:20-alpine` (builder) + `nginx:alpine` | `5173` | `5173` | `wget -qO- http://localhost:5173/nginx-health` |

### 8.3 Quickstart with Docker Compose

1. **Configure Environment Variables**:
   ```bash
   cp .env.example .env
   ```
   *(Optional: Set `OPENROUTER_API_KEY` or `OPENAI_API_KEY` for LLM explanations; if omitted, rule-based reasoning operates automatically).*

2. **Validate Configuration**:
   ```bash
   docker compose config
   ```

3. **Build and Start Containers**:
   ```bash
   docker compose up --build
   ```
   *To run in detached background mode:*
   ```bash
   docker compose up -d --build
   ```

4. **Access Applications**:
   * **Frontend Application**: [http://localhost:5173](http://localhost:5173)
   * **Backend API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
   * **Backend Healthcheck**: [http://localhost:8000/health](http://localhost:8000/health)

5. **Stop Containers**:
   ```bash
   # Stop services while preserving SQLite data in phishguard_db_data volume
   docker compose down

   # Stop services and remove persistent volume (cold reset)
   docker compose down -v
   ```

### 8.4 Database Persistence & Security
* **SQLite Persistence**: User feedback and reviewer audits are stored in the `phishguard_db_data` named Docker volume mounted at `/app/data/phishguard.db`, surviving container restarts and recreations.
* **Non-Root Execution**: Backend runs under an unprivileged `appuser` (UID 1000).
* **Reverse Proxy Integration**: Frontend Nginx routes `/analyze/`, `/predict/`, `/explain/`, and `/feedback/` internally to `http://backend:8000`, eliminating cross-origin mismatches and avoiding client-side hardcoded localhost routing.
* **Build Context Hygiene**: Heavy datasets (`.csv`), local virtual environments, and secrets are strictly excluded via `.dockerignore`.
