#!/bin/bash

# ==============================================================================
# 🛡️ Enterprise SRE & IT Operations Intelligence Platform - Deployment Script
# ==============================================================================

set -e # Exit immediately if any command exits with a non-zero status

echo "======================================================================"
echo "🛡️ Starting SRE & IT Operations Intelligence Platform Deployment Pipeline"
echo "======================================================================"

# Step 1: Check Python installation environment
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is required but not found on this system."
    exit 1
fi

# Step 2: Establish isolated Python Virtual Environment
echo "📦 Initializing clean Python virtual environment (venv)..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Virtual environment created successfully."
else
    echo "ℹ️ Existing venv directory detected. Skipping creation layer."
fi

# Step 3: Activate virtual environment context
echo "🔄 Activating local environment architecture..."
source venv/bin/activate

# Step 4: Upgrade pipeline installer and deploy dependency definitions
echo "📥 Installing required production Python packages..."
pip install --upgrade pip
pip install streamlit pandas plotly requests

# Step 5: Verify localized application directory safety checks
echo "📂 Validating filesystem folder layout structures..."
mkdir -p data reports analytics utils ai

# Step 6: Verify Ollama runtime environment configurations
echo "🧠 Checking local AI inference layer configuration..."
if command -v ollama &> /dev/null; then
    echo "ℹ️ Local Ollama binary detected. Ensuring target model engine weights exist..."
    # Asynchronously pull the hyper-fast 3B parameter model in the background
    ollama pull qwen2.5:3b &
else
    echo "⚠️ Warning: Ollama backend binary not found globally."
    echo "Please ensure an active Ollama daemon is listening on port 11434 if using AI modules."
fi

# Step 7: Fire up the live interactive framework portal
echo "======================================================================"
echo "🚀 Booting Up Enterprise Operations Control Panel Dashboard Interface..."
echo "======================================================================"
python3 -m streamlit run app.py --server.port 8501