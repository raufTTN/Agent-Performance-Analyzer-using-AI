#!/usr/bin/env bash

# ==============================================================================
# Enterprise SRE & IT Operations Intelligence Platform - Setup & Launch Script
# Developed by Team Gamma (US SRE Pod)
# ==============================================================================

set -e

# System Terminal Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

MODEL_NAME="qwen2.5:3b"

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}  🛡️  Enterprise SRE & IT Operations Intelligence Platform Setup       ${NC}"
echo -e "${BLUE}  Developed by Team Gamma (US SRE Pod)                                ${NC}"
echo -e "${BLUE}======================================================================${NC}\n"

# 1. Check Python installation
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Error: python3 is not installed. Please install Python 3.9+ and retry.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python 3 environment verified: $(python3 --version)${NC}"

# 2. Check and prompt for wkhtmltopdf (Required for PDF Report Export)
if ! command -v wkhtmltopdf &> /dev/null; then
    echo -e "${YELLOW}⚠️  Warning: 'wkhtmltopdf' is not installed. PDF export capabilities require it.${NC}"
    echo -e "${YELLOW}👉 To fix on Debian/Ubuntu Linux run: sudo apt-get update && sudo apt-get install -y wkhtmltopdf${NC}\n"
else
    echo -e "${GREEN}✓ System PDF Rendering Engine (wkhtmltopdf) verified.${NC}"
fi

# 3. Create required runtime project directories
echo -e "${BLUE}📁 Verifying runtime project directory structure...${NC}"
mkdir -p data reports exports ai analytics utils

# 4. Virtual Environment Setup
VENV_DIR="venv"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}⚙️  Creating Python virtual environment in ./${VENV_DIR}...${NC}"
    python3 -m venv $VENV_DIR
fi

echo -e "${BLUE}🔄 Activating Python virtual environment...${NC}"
source $VENV_DIR/bin/activate

# 5. Install and Upgrade Python Packages
echo -e "${BLUE}📦 Upgrading pip and installing production dependencies...${NC}"
pip install --upgrade pip --quiet
pip install streamlit pandas plotly requests pdfkit --quiet

echo -e "${GREEN}✓ Python dependencies successfully installed.${NC}"

# 6. Verify Local Ollama Inference Subsystem
echo -e "\n${BLUE}🤖 Checking local Ollama LLM service daemon...${NC}"
if ! command -v ollama &> /dev/null; then
    echo -e "${RED}❌ Error: Ollama is not installed or not in system PATH.${NC}"
    echo -e "${YELLOW}👉 Install Ollama locally via: curl -fsSL https://ollama.com/install.sh | sh${NC}"
    exit 1
fi

# Ensure Ollama daemon is active
if ! pgrep -x "ollama" > /dev/null && ! curl -s http://localhost:11434/api/tags > /dev/null; then
    echo -e "${YELLOW}⚙️  Starting background Ollama service daemon...${NC}"
    ollama serve > /dev/null 2>&1 &
    sleep 3
fi

# Check and pull active model weights
echo -e "${BLUE}🧠 Verifying local LLM model weights (${MODEL_NAME})...${NC}"
if ! ollama list | grep -q "$MODEL_NAME"; then
    echo -e "${YELLOW}📥 Model '${MODEL_NAME}' not found locally. Downloading weights (this may take a minute)...${NC}"
    ollama pull $MODEL_NAME
else
    echo -e "${GREEN}✓ Local model '${MODEL_NAME}' is ready.${NC}"
fi

# Pre-warm model in memory
echo -e "${BLUE}🔥 Pre-warming local model memory allocation...${NC}"
curl -s -X POST http://localhost:11434/api/generate \
    -H "Content-Type: application/json" \
    -d "{\"model\": \"$MODEL_NAME\", \"prompt\": \"ping\", \"stream\": false}" > /dev/null || true

# 7. Launch Dashboard Interface
echo -e "\n${GREEN}======================================================================${NC}"
echo -e "${GREEN}🚀 All systems verified! Launching Streamlit Operations Dashboard...  ${NC}"
echo -e "${GREEN}======================================================================${NC}\n"

streamlit run app.py
