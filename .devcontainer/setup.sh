#!/usr/bin/env bash
set -euo pipefail
echo "=== Installing system deps ==="
sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg fonts-dejavu-core

echo "=== Installing deno (for yt-dlp n-challenge solver) ==="
curl -fsSL https://deno.land/install.sh | sh
export PATH="$HOME/.deno/bin:$PATH"
echo 'export PATH="$HOME/.deno/bin:$PATH"' >> ~/.bashrc

echo "=== Installing uv ==="
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

echo "=== Backend deps ==="
cd /workspaces/mpt-editor/backend
uv venv .venv --python 3.11
uv pip install -e .

# Create an EMPTY .env. Keys are entered at runtime via the Settings UI (PUT /api/settings/keys).
echo "=== Backend .env (empty placeholders — keys entered via UI) ==="
cat > .env <<ENV
GEMINI_API_KEY=
PEXELS_API_KEY=
STORAGE_DIR=/workspaces/mpt-editor/backend/data
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
CORS_ORIGINS=*
ENV

echo "=== Frontend deps ==="
cd /workspaces/mpt-editor/frontend
npm install --no-audit --no-fund

echo
echo "Setup complete. Start with 'make dev' from repo root."
echo "Then open the forwarded :5173 URL — you will be asked to paste your Gemini + Pexels keys."
