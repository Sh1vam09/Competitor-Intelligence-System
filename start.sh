#!/bin/bash
set -e

echo "Starting AI Competitor Intelligence Engine..."

# Start the FastAPI backend
uvicorn api.main:app --host 0.0.0.0 --port 8000 &

# Start the Streamlit frontend
streamlit run frontend/app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false &

# Wait for any process to exit
wait -n

# Exit with status of process that exited first
exit $?
