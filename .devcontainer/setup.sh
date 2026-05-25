#!/usr/bin/env bash
set -euo pipefail
echo "=== Installing system deps ==="
sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg fonts-dejavu-core

# universal:2 already has Python 3.11 and Node 20

echo "=== Installing uv ==="
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

echo "=== Backend deps ==="
cd /workspaces/mpt-editor/backend
uv venv .venv --python 3.11
uv pip install -e .

echo "=== Backend .env ==="
cat > .env <<ENV
GEMINI_API_KEY=AIzaSyDnx-o-p4SH6gqAfdRNLgFpKdHW6XXmwSY
PEXELS_API_KEY=IAvO66Mp5veM2xfDJbby6jjFb5uSwZz6VfY1KjWl23IyKanuFqehZKS7
STORAGE_DIR=/workspaces/mpt-editor/backend/data
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
CORS_ORIGINS=*
ENV

echo "=== Frontend deps ==="
cd /workspaces/mpt-editor/frontend
npm install --no-audit --no-fund

echo "=== Setup done. Run 'make dev' to start. ==="
