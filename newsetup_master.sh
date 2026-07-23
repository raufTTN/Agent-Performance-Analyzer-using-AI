#!/bin/bash

echo "======================================================================"
echo "🛡️ Starting SRE & IT Operations Intelligence Platform Deployment"
echo "======================================================================"

# 1. Check Python 3 Availability
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 could not be found. Please install Python 3.10+."
    exit 1
fi
echo "✅ Python 3 detected."

# 2. Create and Activate Virtual Environment
if [ ! -d "venv" ]; then
    echo "📦 Initializing clean Python virtual environment (venv)..."
    python3 -m venv venv
else
    echo "ℹ️ Existing venv directory detected."
fi

echo "🔄 Activating local environment architecture..."
source venv/bin/activate

# 3. Upgrade pip and install dependencies
echo "📥 Upgrading pip and installing required production Python packages..."
pip install --upgrade pip
pip install streamlit pandas plotly weasyprint pdfkit xhtml2pdf openpyxl requests

# 4. Verify directory structures
echo "📂 Validating filesystem folder layout structures..."
for dir in data reports analytics utils; do
    if [ ! -d "$dir" ]; then
        echo "Creating missing directory: $dir/"
        mkdir -p "$dir"
    fi
done

# 5. Fix permissions and run the app
echo "🔒 Applying execute permissions..."
chmod +x newsetup_master.sh

echo "======================================================================"
echo "🚀 Booting Up Enterprise Operations Control Panel Dashboard Interface..."
echo "======================================================================"
streamlit run app.py
