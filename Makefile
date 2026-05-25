.PHONY: dev backend frontend stop

dev:
	@bash scripts/dev.sh

backend:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

frontend:
	cd frontend && npm run dev -- --host 0.0.0.0

stop:
	-pkill -f "uvicorn app.main" || true
	-pkill -f "vite" || true
