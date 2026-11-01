# Namma Space: Code Repository & Setup Instructions
**Techfest IIT Bombay 2026–27 | Deliverable 4**

## 1. Quick Installation
```bash
# Clone and enter repo
cd namma_space/namma_space

# Install dependencies
pip install -r requirements.txt
pip install -r reconstruction/requirements.txt
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
```

## 2. Reconstruct Model (1 Command)
```bash
cd reconstruction
python run_pipeline.py --video "EX3.MOV" --clean
```

## 3. Run Web App
```bash
# Terminal 1: Backend
cd backend && python -m uvicorn main:app --host 127.0.0.1 --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev
```
Open `http://localhost:5173/` in your browser.
