#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Namma Space — One-Click Mac Launcher
# Double-click this file in macOS Finder OR run './run_mac.command' in Terminal
# ─────────────────────────────────────────────────────────────────────────────

cd "$(dirname "$0")"

echo ""
echo "=========================================================="
echo "  Namma Space — Indoor Spatial Digital Twin Engine"
echo "  Launching on macOS..."
echo "=========================================================="
echo ""

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed or not in your PATH."
    echo "Please download and install Python from: https://www.python.org/"
    read -p "Press Enter to exit..."
    exit 1
fi

# Check Node / npm
if ! command -v npm &> /dev/null; then
    echo "[ERROR] Node.js / npm is not installed or not in your PATH."
    echo "Please download and install Node.js (LTS) from: https://nodejs.org/"
    read -p "Press Enter to exit..."
    exit 1
fi

echo "[1/4] Checking Python backend dependencies..."
python3 -m pip install -q -r backend/requirements.txt

echo "[2/4] Checking Frontend dependencies..."
if [ ! -d "frontend/node_modules" ]; then
    echo "First-time setup: Installing frontend dependencies (one-time only)..."
    (cd frontend && npm install)
fi

echo "[3/4] Starting FastAPI Backend on http://127.0.0.1:8000..."
(cd backend && python3 -m uvicorn main:app --host 127.0.0.1 --port 8000) &
BACKEND_PID=$!

sleep 2

echo "[4/4] Starting Vite Frontend on http://localhost:5173..."
(cd frontend && npm run dev) &
FRONTEND_PID=$!

sleep 2

# Open browser automatically on macOS
echo ""
echo "[OK] Opening Namma Space in your default browser..."
open "http://localhost:5173/"

echo ""
echo "=========================================================="
echo "  Namma Space is now running!"
echo "  Web Viewer:  http://localhost:5173/"
echo "  Backend API: http://127.0.0.1:8000/docs"
echo "  --------------------------------------------------------"
echo "  Controls: Click on canvas to lock mouse, WASD to walk,"
echo "            Shift to sprint, Space/C to elevate up/down."
echo "  (Press Ctrl+C in this terminal to shut down both servers)"
echo "=========================================================="
echo ""

# Handle graceful shutdown
cleanup() {
    echo ""
    echo "Shutting down servers..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT
wait
