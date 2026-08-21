#!/bin/bash
set -e

pip install -r requirements.txt

# Download workflows.db from GitHub release (43MB, gitignored)
if [ ! -f workflows.db ]; then
    echo "Downloading workflows.db from GitHub release..."
    curl -L -o workflows.db https://github.com/laknanitish2110-sudo/ai-software-company/releases/download/v1.4.0/workflows.db
    echo "workflows.db downloaded ($(du -h workflows.db | cut -f1))"
else
    echo "workflows.db already exists, skipping download"
fi
