#!/bin/bash
set -e

pip install -r requirements.txt

if [ -f workflows.db ]; then
    echo "workflows.db found ($(du -h workflows.db | cut -f1))"
else
    echo "WARNING: workflows.db not found — RAG search will be unavailable"
fi
