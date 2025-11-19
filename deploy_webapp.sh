#!/bin/bash
# Super Gnosis Web App Deployment Script
# Production-ready deployment with process management

set -e

echo "============================================================"
echo "🚀 Super Gnosis Web App Deployment"
echo "============================================================"
echo ""

# Check if port 8000 is already in use
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Port 8000 is already in use. Stopping existing service..."
    kill $(lsof -Pi :8000 -sTCP:LISTEN -t) 2>/dev/null || true
    sleep 2
fi

# Create necessary directories
mkdir -p logs
mkdir -p data

# Check for .env file
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Creating from template..."
    cp .env.example .env 2>/dev/null || echo "Please configure .env file with your API keys"
fi

# Install dependencies if needed
echo "📦 Checking dependencies..."
pip install -q -r requirements.txt 2>/dev/null || {
    echo "Installing minimal dependencies..."
    pip install -q fastapi uvicorn python-dotenv pydantic
}

# Start the web app
echo ""
echo "🌐 Starting Super Gnosis Web App..."
echo "   Dashboard: http://localhost:8000"
echo "   Health: http://localhost:8000/health"
echo ""

# Run with proper logging
exec python webapp.py