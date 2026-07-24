# System Implementation & Architecture Guide

Welcome to the internal engineering documentation for the **Enterprise SRE & IT Operations Intelligence Platform**. This document provides a deep dive into the monolithic architecture, data staging strategies, and AI integration mechanisms that power the platform.

---

## 1. System Architecture Overview

The platform operates on a **Monolithic Streamlit Architecture** (`app.py`), designed for rapid, secure, air-gapped deployment in enterprise environments. By relying on Streamlit, the application unifies the frontend rendering and backend logic within a single Python event loop. 

### Key Architectural Traits:
- **Stateless UI Rendering:** Streamlit's top-down execution model means the UI is re-rendered on state changes. We heavily utilize `st.session_state` to cache LLM responses, datasets, and complex ML computations to prevent unnecessary re-execution.
- **Air-Gapped First:** No external cloud services are required. Data stays on the local disk (SQLite), and LLM inference is routed to a local Ollama instance (`http://localhost:11434`), guaranteeing strict data compliance.
- **Dual-Theme Support & Glassmorphism:** The frontend injects native `st.html()` and CSS overrides to render dynamic, visually stunning components, bypassing Streamlit's default constraints.

---

## 2. Data Pipeline & Staging

Data ingestion is the critical first step before any analytics or LLM operations occur. The platform avoids relying on raw CSVs in memory and instead uses a resilient local SQLite staging gateway.

### `utils/loader.py` (LegacyDataStagingGateway)
The loader is responsible for sanitizing incoming datasets (`data/*.csv`).
- **Dynamic Field Parsing:** It safely strips malformed headers and gracefully coerces `Effort` and `Resolution Hours` to numerics. 
- **Time Delta Fallbacks:** If `Resolution Hours` is missing, it automatically calculates the time difference between `Created Time` and `Resolved Time`, adapting to various ISO and European timestamp formats.
- **Database Seeding:** It flushes the previous cache (`DELETE FROM tickets`) to ensure a clean state, inserting thousands of rows securely via parameterized batch inserts (`ON CONFLICT(ticket_id) DO UPDATE`).

### `utils/db_manager.py` (SQLite Architecture)
- **Schema Design:** The `tickets` table is flat and denormalized, ideal for read-heavy analytical queries. It natively tracks `company`, `ticket_type`, `category`, and `agent` attributes.
- **Lock Prevention:** The connection factory (`get_db_connection()`) is encapsulated within `with` contexts across the app to automatically commit transactions and release file locks, ensuring the UI thread never blocks indefinitely on the `.db` file.
- **Index Optimization:** B-Tree indexes (`idx_tickets_agent`, `idx_tickets_priority`, etc.) are pre-compiled during initialization to guarantee sub-millisecond query filtering when the user interacts with the dashboard.

---

## 3. Module Deep Dives (`analytics/`)

The `analytics/` package contains the core business logic, separated from the UI for testability and maintainability.

### 📊 `analytics/scoring.py` (SLA Compliance Engine & Leaderboard)
Calculates performance scores based on weighted metrics. 
- **Dynamic Weights:** It intelligently adjusts the weights (Speed vs. Volume) based on the context (e.g., `Service Requests` prioritize volume/effort, while `Incidents` prioritize strict SLA resolution speed).
- **Leaderboard Generation:** Aggregates effort minutes, breaches, and completion rates into a single, normalized `Performance_Score` out of 100 for each agent.

### 🔍 `analytics/ticket_explorer.py` (Deep Forensics)
Allows operators to drill down into a specific `ticket_id`.
- **Vector Search (Local):** It uses `LocalTicketVectorStore` to calculate semantic similarity distances natively. It surfaces historically similar solved cases so engineers don't have to reinvent the wheel.
- **Audit Execution:** Connects to `LocalTicketAnalyzer` to pass the ticket's raw description and resolution notes into the LLM, outputting structured diagnostics (Root Cause, Incident Summary).

### 🛡️ `analytics/noise_cluster.py` (Infrastructure Noise Clustering)
Focuses on systemic issues rather than individual tickets.
- **Frequency Analysis:** Aggregates subjects and companies to find high-volume "noise" (e.g., repeating VPN drops or password lockouts).
- **Security Playbooks:** Uses the LLM to analyze these clusters and automatically construct air-gapped security playbooks or engineering efficiency strategies.

---

## 4. AI Integration Strategy

The platform integrates AI deeply into its workflows without compromising data privacy.

- **Engine:** Ollama running locally.
- **Endpoint configuration:** Handled in `config.py` (`OLLAMA_API_URL = "http://localhost:11434/api/generate"`).
- **Prompt Engineering:** The prompts are strict and highly prescriptive, enforcing JSON schemas. `json.loads` safely parses the generative output.
- **Modules using AI:**
  - **Career Coaching Workshop:** Batches an agent's history and generates personalized feedback.
  - **Executive Review Compiler (`utils/insights.py`):** Passes the top 10 agents to the LLM to generate a 1-sentence strategic remark for each, blending quantitative data with qualitative AI analysis.
  - **Forensics & Noise:** As detailed above.

---

## 5. UI/UX Design System

The application breaks away from standard Streamlit aesthetics to provide a premium enterprise experience.

- **CSS Overrides:** Custom CSS is injected to hide default Streamlit branding (hamburger menu, footers).
- **Metric Cards & Layout:** Relies heavily on `st.columns` and `st.metric` for responsive KPI grids.
- **PDF Export Engine:** `utils/insights.py` compiles raw Python strings into robust HTML5, injecting custom `@page` styles, borders, and typography (`Inter` font) before converting it to a professional PDF layout using `xhtml2pdf`.

---

## 6. Future Scalability & Migration Considerations

As the dataset grows and the organization scales, the following architectural upgrades should be considered:

1. **Database Migration:** Migrate from SQLite to **PostgreSQL**. SQLite is perfect for local staging (up to a few GBs), but concurrent writes (if automated webhooks are added in the future) will require Postgres. `utils/db_manager.py` uses standard SQL, making this transition relatively straightforward via SQLAlchemy.
2. **Asynchronous LLM Calls:** Currently, LLM inference blocks the main Streamlit thread. Migrating to `asyncio` with `httpx` and utilizing Streamlit's newer asynchronous features will improve perceived performance.
3. **Embeddings Database:** The current "Semantic Search" uses native distance calculations. Integrating a dedicated vector database like **ChromaDB** or **Qdrant** will vastly improve performance when searching through tens of thousands of historical tickets.
4. **Caching Strategy:** Replace `st.cache_data` with a distributed Redis cache if the application is containerized and deployed across multiple replicas.
