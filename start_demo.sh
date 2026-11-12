#!/usr/bin/env bash
# Start everything for the demo: Docker, the database, the API and the UI.
# Usage: ./start_demo.sh     (stop with Ctrl+C)
set -e
cd "$(dirname "$0")"

if ! docker info >/dev/null 2>&1; then
  echo "Starting Docker Desktop..."
  open -a Docker
  until docker info >/dev/null 2>&1; do sleep 2; done
fi

docker start sales-db >/dev/null
until docker exec sales-db pg_isready -q; do sleep 1; done
echo "Database ready."

export HF_HUB_OFFLINE=1   # the embedding model is already downloaded
source .venv/bin/activate

uvicorn api:app --port 8000 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null' EXIT
until curl -s localhost:8000/health >/dev/null; do sleep 1; done
echo "API ready: http://localhost:8000/docs"

streamlit run app.py --server.port 8501
