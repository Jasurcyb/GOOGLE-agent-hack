#!/usr/bin/env bash
# Start all Python worker services in background tmux panes
# Usage: ./scripts/start-workers.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR"

SERVICES=(
    "pr-listener:apps/pr-listener:uvicorn pr_listener:app --port 8000"
    "repo-worker:apps/repo-worker:python -m repo_worker.consumer"
    "diff-analyzer:apps/diff-analyzer:python -m diff_analyzer.consumer"
    "risk-engine:apps/risk-engine:python -m risk_engine.consumer"
    "reasoning-agent:apps/reasoning-agent:python -m reasoning_agent.consumer"
    "test-agent:apps/test-agent:python -m test_agent.consumer"
    "publisher:apps/publisher:python -m publisher.consumer"
    "api-gateway:apps/api-gateway:uvicorn api_gateway:app --port 8001"
)

echo "Starting ${#SERVICES[@]} worker services..."

for entry in "${SERVICES[@]}"; do
    IFS=':' read -r name dir cmd <<< "$entry"
    echo "  Starting $name..."
    cd "$ROOT_DIR/$dir"
    nohup $cmd > "/tmp/rh-$name.log" 2>&1 &
    echo "    PID: $! | Log: /tmp/rh-$name.log"
    cd "$ROOT_DIR"
    sleep 1
done

echo ""
echo "All services started. Check logs with: tail -f /tmp/rh-*.log"
echo "Stop all with: kill \$(jobs -p)"
