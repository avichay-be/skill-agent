#!/bin/bash
# Azure App Service startup script for FastAPI application

# Option 1: Use uvicorn directly (simpler, good for moderate traffic)
python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level info

# Option 2: Use gunicorn with uvicorn workers (better for production, high traffic)
# Uncomment below and comment above if you want multiple workers
# python -m gunicorn app.main:app \
#     --workers 4 \
#     --worker-class uvicorn.workers.UvicornWorker \
#     --bind 0.0.0.0:8000 \
#     --timeout 120 \
#     --access-logfile - \
#     --error-logfile - \
#     --log-level info
