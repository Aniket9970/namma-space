.PHONY: install-backend install-frontend dev-backend dev-frontend dev clean

# ── Backend ──────────────────────────────────────────────────────────────────
install-backend:
	@echo "Installing backend dependencies…"
	cd backend && python -m pip install -r requirements.txt

dev-backend:
	@echo "Starting FastAPI backend on :8000…"
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

# ── Frontend ─────────────────────────────────────────────────────────────────
install-frontend:
	@echo "Installing frontend dependencies…"
	cd frontend && npm install

dev-frontend:
	@echo "Starting Vite frontend on :5173…"
	cd frontend && npm run dev

# ── Both ─────────────────────────────────────────────────────────────────────
dev:
	@echo "Starting backend and frontend concurrently…"
	$(MAKE) dev-backend & $(MAKE) dev-frontend

# ── Clean ────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -type f -name "*.pyc" -delete 2>/dev/null; true
	rm -rf frontend/node_modules frontend/dist 2>/dev/null; true
	rm -f backend/namma_space.db 2>/dev/null; true
