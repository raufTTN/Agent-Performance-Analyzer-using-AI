# 🛡️ Enterprise SRE & IT Operations Intelligence Platform

Welcome to the Enterprise SRE & IT Operations Intelligence Platform. This powerful, localized AI-driven analytics dashboard is designed to ingest support workflows, calculate compliance metrics, and automatically uncover root-cause insights completely offline.

## 🌟 Core Features

- **LegacyDataStagingGateway ETL**: Safely handles dataset ingestion from local `.csv` files inside the `data/` directory. Automatically calculates missing timestamps, formats data securely, and seeds our high-speed local SQLite database safely, replacing previous staging loads dynamically.
- **Multi-Value Effort Filtering**: Empowers operators to clean the dashboard scope by selecting *multiple* minute-based effort values to exclude simultaneously using a resilient UI multiselect engine.
- **SLA Diagnostic Engine**: Deep calculation of resolution limits, automatically tracking how many tickets were successfully closed within targeted service level agreements versus breached cases.
- **Top 5 Noisy Infrastructure Alert Clusters**: Intelligently groups repetitive ticket subjects against their associated companies/contexts, surfacing the top 5 highest-frequency noise alerts.
- **Deep Forensics Explorer**: Look up specific Ticket IDs natively to view AI generative diagnostic summaries and visually parsed metadata, featuring beautiful, human-readable 12-hour formatted Ticket Closure Times (e.g., `19 Apr 2026, 12:45 PM`).
- **Automated Executive Review Compiler**: Generates robust, paginated reports complete with CSS grid styling, global KPIs, and LLM-powered strategic batch remarks for every agent, exportable simultaneously in rich **HTML** and **PDF** formats!

## ⚙️ Tech Stack Overview

- **Frontend/UI Engine**: [Streamlit](https://streamlit.io/)
- **Data Engineering**: [Pandas](https://pandas.pydata.org/), SQLite3
- **Visualization**: [Plotly](https://plotly.com/)
- **Local AI Inference**: [Ollama](https://ollama.com/) (Self-Hosted LLM API)
- **Document Export**: HTML5/CSS3, `xhtml2pdf`, `pdfkit`, `weasyprint`

## 📂 Project Directory Layout

```text
├── analytics/             # Core AI, SLAs, Forensics, Root-Cause & Scoring logic
├── utils/                 # Data loaders, database managers, and report HTML compilers
├── data/                  # Drop zone for target .csv dataset ingestion
├── reports/               # Output destination for generated HTML/PDF Executive Reviews
├── app.py                 # Main Streamlit dashboard application UI
├── config.py              # Centralized environment constants & model weights configuration
├── newsetup_master.sh     # One-click deployment environment bootstrapping script
└── anuragreadme.md        # Comprehensive documentation file
```

## 🚀 One-Click Installation & Startup

We have packaged a master bootstrapping script that will automatically detect Python, build an isolated virtual environment, fetch all necessary dependencies, construct missing directories, and boot the frontend engine!

1. Make sure you are in the project root directory.
2. Run the deployment script:
   ```bash
   chmod +x newsetup_master.sh
   ./newsetup_master.sh
   ```
3. The dashboard will automatically launch in your default web browser at `http://localhost:8501`.
