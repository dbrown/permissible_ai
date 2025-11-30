#!/bin/bash
# Quick Start: Secure Dataset Upload Demo

set -e

echo "================================================"
echo "  Secure Dataset Upload - Quick Start"
echo "================================================"
echo ""

# Check Python version
python3 --version || { echo "Error: Python 3 required"; exit 1; }

echo "[1/4] Installing TEE server dependencies..."
pip3 install flask cryptography pyjwt requests

echo ""
echo "[2/4] Starting TEE Server..."
cd "$(dirname "$0")/../workers"
python3 tee_server.py &
TEE_PID=$!
echo "TEE Server started (PID: $TEE_PID)"
sleep 3

echo ""
echo "[3/4] TEE Server running at http://localhost:8080"
echo ""
echo "Test attestation:"
curl -s http://localhost:8080/attestation | python3 -m json.tool | head -20
echo ""

echo ""
echo "[4/4] Starting Web Server..."
cd "$(dirname "$0")/../web_api"
export FLASK_APP=app.py
export TEE_SERVICE_ENDPOINT=http://localhost:8080
python3 app.py &
WEB_PID=$!
echo "Web Server started (PID: $WEB_PID)"
sleep 2

echo ""
echo "================================================"
echo "  ✓ Setup Complete!"
echo "================================================"
echo ""
echo "Web Interface: http://localhost:5000"
echo "TEE Endpoint:  http://localhost:8080"
echo ""
echo "Next Steps:"
echo "1. Navigate to http://localhost:5000"
echo "2. Log in and create/join a collaboration session"
echo "3. Click 'Upload Dataset'"
echo "4. Verify attestation (Step 1)"
echo "5. Select a file (Step 2)"
echo "6. Encrypt & Upload (Step 3)"
echo ""
echo "To stop servers:"
echo "  kill $TEE_PID $WEB_PID"
echo ""
