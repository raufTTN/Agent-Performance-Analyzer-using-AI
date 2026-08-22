#!/usr/bin/env bash

# ==============================================================================
# Enterprise SRE & IT Operations Intelligence Platform - Docker Setup
# Fully Automated Bootstrapping & Deployment Tool
# ==============================================================================

set -e

# System Terminal Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}  🛡️  Enterprise SRE Platform - Automated Docker Deployment           ${NC}"
echo -e "${BLUE}======================================================================${NC}\n"

# 1. OS Detection
OS_TYPE=$(uname -s | tr '[:upper:]' '[:lower:]')
echo -e "${BLUE}🔍 Detected Operating System: ${OS_TYPE}${NC}"

# 2. Dependency Installation: Docker & Docker Compose
if ! command -v docker &> /dev/null || (! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null); then
    echo -e "${YELLOW}⚠️  Docker or Docker Compose is missing. Automating installation...${NC}"
    
    if [[ "$OS_TYPE" == "darwin" ]]; then
        # macOS Installation via Homebrew
        if ! command -v brew &> /dev/null; then
            echo -e "${RED}❌ Error: Homebrew is required on macOS to install Docker automatically.${NC}"
            echo -e "${YELLOW}Please install Homebrew from https://brew.sh/ and run this script again.${NC}"
            exit 1
        fi
        echo -e "${YELLOW}📦 Installing Docker Desktop via Homebrew...${NC}"
        brew install --cask docker
        echo -e "${GREEN}✓ Docker installed. Please open Docker Desktop from your Applications folder to finish setup.${NC}"
        echo -e "${YELLOW}⏳ Waiting for Docker daemon to start...${NC}"
        while ! docker info > /dev/null 2>&1; do
            sleep 3
            echo -n "."
        done
        echo ""
        
    elif [[ "$OS_TYPE" == "linux" ]]; then
        # Linux Installation via apt/get-docker.sh
        echo -e "${YELLOW}📦 Installing Docker and Docker Compose... (You may be prompted for your sudo password)${NC}"
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo sh get-docker.sh
        rm get-docker.sh
        
        # Add user to docker group to avoid needing sudo for docker commands in the future
        if [ "$EUID" -ne 0 ]; then
            echo -e "${YELLOW}🔧 Adding current user ($USER) to the docker group...${NC}"
            sudo usermod -aG docker $USER
            echo -e "${YELLOW}⚠️  Note: You might need to log out and log back in for docker group changes to fully take effect.${NC}"
        fi
        
        # Ensure Docker Compose plugin is also installed
        if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
            echo -e "${YELLOW}📦 Installing Docker Compose...${NC}"
            sudo apt-get update && sudo apt-get install -y docker-compose-plugin docker-compose
        fi
    else
        echo -e "${RED}❌ Error: Unsupported OS ($OS_TYPE) for automated Docker installation. Please install Docker manually.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ Docker and Docker Compose environments verified.${NC}"
fi

# Determine the correct docker commands (handling sudo if the user is not in the docker group yet)
if docker info &> /dev/null; then
    DOCKER_CMD="docker"
else
    DOCKER_CMD="sudo docker"
fi

if $DOCKER_CMD compose version &> /dev/null; then
    COMPOSE_CMD="$DOCKER_CMD compose"
else
    COMPOSE_CMD="$DOCKER_CMD-compose"
fi

# 3. Dependency Installation: Ollama
echo -e "\n${BLUE}🤖 Checking local Ollama LLM service daemon...${NC}"
if ! command -v ollama &> /dev/null; then
    echo -e "${YELLOW}⚠️  Ollama is missing. Automating installation via official script...${NC}"
    curl -fsSL https://ollama.com/install.sh | sh
    echo -e "${GREEN}✓ Ollama successfully installed.${NC}"
else
    echo -e "${GREEN}✓ Ollama daemon verified.${NC}"
fi

# Ensure Ollama daemon is running in the background if it isn't active
if ! pgrep -x "ollama" > /dev/null && ! curl -s http://localhost:11434/api/tags > /dev/null; then
    echo -e "${YELLOW}⚙️  Starting background Ollama service daemon...${NC}"
    ollama serve > /dev/null 2>&1 &
    sleep 3
fi

# 4. Model Provisioning
echo -e "\n${BLUE}🧠 Provisioning Local LLM Model (qwen2.5:3b)...${NC}"
if ! ollama list | grep -q "qwen2.5:3b"; then
    echo -e "${YELLOW}📥 Initiating background pull/run for qwen2.5:3b model...${NC}"
    # Execute ollama run in background to pull the model
    nohup ollama run qwen2.5:3b > /dev/null 2>&1 &
    echo -e "${GREEN}✓ Model pull initiated in the background.${NC}"
else
    echo -e "${GREEN}✓ Local model 'qwen2.5:3b' is already available.${NC}"
fi

# 5. Create Required Directories for Volumes
echo -e "\n${BLUE}📁 Verifying data and export directories...${NC}"
mkdir -p data reports exports

# 6. Build and Run Container
echo -e "\n${BLUE}🐳 Building and starting Docker container with multi-stage image...${NC}"
$COMPOSE_CMD up -d --build

echo -e "\n${BLUE}⏳ Waiting for Streamlit application to initialize...${NC}"
sleep 5

# 7. Success Verification & Output
if $DOCKER_CMD ps | grep -q "sre-platform"; then
    echo -e "\n${GREEN}======================================================================${NC}"
    echo -e "${GREEN}${BOLD}🚀 Success! The SRE Platform is now LIVE and running in Docker.${NC}"
    echo -e "${GREEN}======================================================================${NC}\n"
    echo -e "You can securely access the application at: ${BLUE}${BOLD}http://localhost:8501${NC}"
    echo -e "\nTo view realtime logs, run: ${YELLOW}$COMPOSE_CMD logs -f${NC}"
    echo -e "To stop the application gracefully, run: ${YELLOW}$COMPOSE_CMD down${NC}\n"
else
    echo -e "\n${RED}❌ Error: Container failed to start. Please check the logs via: $COMPOSE_CMD logs${NC}"
fi
