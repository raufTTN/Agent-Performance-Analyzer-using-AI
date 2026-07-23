import os
from pathlib import Path

# Base Path Configurations
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"

# Ensure visual tracking subdirectories exist securely
DATA_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

# Air-Gapped Local Storage Database Mappings
DB_PATH = str(DATA_DIR / "analyzer.db")
CSV_PATH = str(DATA_DIR / "tickets.csv")

# Local AI Engine Controls via Ollama
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:3b"
LLM_TIMEOUT = 180            
MAX_TEXT_WINDOW = 1500       

# Precise Target Operational SLA Metrics Mappings (in Hours)
SLA_TARGETS = {
    "urgent": 4.0,   # P0
    "high": 8.0,     # P1
    "medium": 16.0,  # P2
    "low": 24.0      # P3
}

# Configurable Leaderboard Performance Matrix Tuning Weights
SCORING_WEIGHTS = {
    "sla_compliance": 0.40,  # SLA Compliance carries the highest priority
    "resolution_speed": 0.30,  # Shorter Resolution Hours increases score
    "volume_impact": 0.20,  # Total count volume handled
    "effort_efficiency": 0.10,  # Shorter effort minutes per ticket handled
}
