#!/bin/bash

# MemeNem Backend Start Script for Render Free Tier
# Optimized with Gunicorn and UvicornWorker for better memory management

echo "Starting MemeNem Backend..."
echo "PORT: $PORT"
echo "RENDER: $RENDER"
echo "Python version: $(python --version)"

# Use Gunicorn with UvicornWorker for better process management
# - Single worker to minimize memory usage on free tier
# - 300s timeout for startup (Render allows up to 10 minutes)
# - Bind to 0.0.0.0:$PORT for Render compatibility
exec gunicorn \
    -w 1 \
    -k uvicorn.workers.UvicornWorker \
    main:app \
    --bind 0.0.0.0:$PORT \
    --timeout 300 \
    --keep-alive 2 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --preload \
    --log-level info \
    --access-logfile - \
    --error-logfile -