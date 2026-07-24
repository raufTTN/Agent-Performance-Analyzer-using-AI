<div align="center">
  <h1>🛡️ Enterprise SRE & IT Operations Intelligence Platform</h1>
  <p><strong>Offline-First, AI-Powered SRE Dashboard for High-Security Environments</strong></p>
  
  ![Python Version](https://img.shields.io/badge/Python-3.9%2B-blue?style=for-the-badge&logo=python)
  ![Streamlit](https://img.shields.io/badge/Streamlit-1.30%2B-FF4B4B?style=for-the-badge&logo=streamlit)
  ![SQLite](https://img.shields.io/badge/SQLite-Local-003B57?style=for-the-badge&logo=sqlite)
  ![Ollama](https://img.shields.io/badge/AI-Ollama_Local-white?style=for-the-badge&logo=ollama)
  ![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)
</div>

<br>

## 📖 Executive Summary

The **Enterprise SRE & IT Operations Intelligence Platform** is a secure, monolithic data analytics dashboard built to ingest raw IT support workflows, rigorously calculate compliance metrics, and automatically uncover root-cause insights. 

Designed for strict, air-gapped enterprise environments, this platform operates **100% offline**. By leveraging a localized SQLite staging gateway and an embedded LLM (Ollama), it guarantees that highly sensitive infrastructure logs, security incidents, and user data never leave your internal network.

---

## 🌟 Core Features

- **🧠 AI Forensic Auditor (`analytics/ticket_explorer.py`)**
  Instantly surface historically similar solved tickets using semantic proximity, and generate LLM-powered root-cause summaries natively. Stop reinventing the wheel on recurring issues.

- **🛡️ Infrastructure Noise Clustering (`analytics/noise_cluster.py`)**
  Intelligently groups repetitive ticket subjects against associated companies and contexts, surfacing the top 5 highest-frequency noise alerts to help build security playbooks.

- **⏱️ SLA Compliance Engine (`analytics/scoring.py`)**
  Deep calculation of resolution limits, automatically tracking breached cases vs. SLA successes. Weights agent performance dynamically based on the work type (Volume/SRs vs. Speed/Incidents).

- **📊 Executive Review Compiler (`utils/insights.py`)**
  Generates robust, paginated reports complete with CSS grid styling, global KPIs, and LLM-powered strategic batch remarks for every agent. Exportable seamlessly into premium **HTML** and **PDF** formats.

- **⚡ Multi-Value Effort Filtering & Fast Staging**
  Clean dashboard scope instantly by filtering multiple effort values. Backed by `LegacyDataStagingGateway`, which safely handles dataset ingestion, formatting, and high-speed SQLite seeding.

---

## ⚙️ Tech Stack Overview

| Category | Technology | Purpose |
| :--- | :--- | :--- |
| **Frontend/UI Engine** | `Streamlit` | Reactive, stateless UI rendering with Dual-Theme Glassmorphism. |
| **Data Engineering** | `Pandas`, `SQLite3` | ETL pipelines, sanitization, and localized fast-read database storage. |
| **Visualization** | `Plotly` | Interactive KPI grids and charting. |
| **Local AI Inference** | `Ollama` | Self-hosted LLM API endpoint for air-gapped forensic diagnostics. |
| **Document Export** | `xhtml2pdf`, HTML5/CSS3 | Enterprise SLA reporting engine. |

---

## 📂 Directory Structure

```text
.
├── analytics/             # Core AI, SLAs, Forensics, Root-Cause & Scoring logic
│   ├── noise_cluster.py
│   ├── scoring.py
│   └── ticket_explorer.py
├── utils/                 # ETL loaders, database managers, and HTML compilers
│   ├── db_manager.py
│   ├── insights.py
│   └── loader.py
├── data/                  # Drop zone for target .csv dataset ingestion
├── reports/               # Output destination for generated HTML/PDF Executive Reviews
├── app.py                 # Main Streamlit dashboard application UI
├── config.py              # Centralized environment constants & model weights configuration
├── newsetup_master.sh     # One-click deployment environment bootstrapping script
├── IMPLEMENTATION.md      # Detailed Architecture and Engineering documentation
└── README.md              # Project documentation
```

---

## 🚀 Getting Started (Installation Guide)

We have packaged a master bootstrapping script that will automatically detect Python, build an isolated virtual environment, fetch all necessary dependencies, construct missing directories, and boot the frontend engine!

### 1. Execute the Bootstrapper
Ensure you are in the project root directory, then run:
```bash
chmod +x newsetup_master.sh
./newsetup_master.sh
```

### 2. Manual Virtual Environment Setup (Optional)
If you prefer to set up the environment manually:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt   # (Install pandas, streamlit, plotly, requests, xhtml2pdf)
```

### 3. Launch the Application
Start the Streamlit monolithic app:
```bash
streamlit run app.py
```
The dashboard will automatically launch in your default web browser at `http://localhost:8501`.

---

## 💡 Usage Guide

1. **Ingest CSV Data:** 
   Place your raw ticket export (e.g., `tickets.csv`) inside the `data/` folder. The application's `LegacyDataStagingGateway` will automatically parse it, fix missing timestamps, and securely load it into the local `analyzer.db` SQLite database when you click "Ingest Data".
2. **Apply Global Filters:**
   Use the sidebar to isolate specific companies, timeframes, or ticket types.
3. **Analyze Effort:**
   Use the "Effort" multi-select filter to exclude specific minute ranges to remove noise or anomalous ticket data from your analytics.
4. **Generate SLA Reports:**
   Scroll to the "Automated Operations Executive Review Compiler" section, click to generate, and download the resulting enterprise PDF for stakeholder distribution.

---
*Maintained by the Enterprise SRE Engineering Team.*
