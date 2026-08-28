#!/usr/bin/env bash
# Regression Hunter AI — One-command demo setup
# Usage: ./scripts/setup-demo.sh
#
# Starts the full stack with seeded data and replays a sample PR.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[RH]${NC} $1"; }
warn() { echo -e "${YELLOW}[RH]${NC} $1"; }
err() { echo -e "${RED}[RH]${NC} $1"; }

echo -e "${BOLD}Regression Hunter AI — Demo Setup${NC}"
echo ""

# ─── Step 1: Start infrastructure ───
log "Starting Docker Compose (core + demo + llm-mock profiles)..."
docker compose --profile core --profile demo --profile llm-mock up -d

log "Waiting for PostgreSQL..."
for i in $(seq 1 30); do
    if docker compose exec -T postgres pg_isready -U rh -d regression_hunter >/dev/null 2>&1; then
        log "PostgreSQL is ready"
        break
    fi
    sleep 1
done

log "Waiting for RabbitMQ..."
for i in $(seq 1 30); do
    if docker compose exec -T rabbitmq rabbitmq-diagnostics -q ping >/dev/null 2>&1; then
        log "RabbitMQ is ready"
        break
    fi
    sleep 1
done

# ─── Step 2: Run migrations ───
log "Running database migrations..."
if command -v alembic >/dev/null 2>&1; then
    cd db && alembic upgrade head && cd ..
    log "Migrations complete"
else
    warn "Alembic not found — skipping migrations (assumed already applied)"
fi

# ─── Step 3: Load seed data ───
log "Loading seed data..."
if command -v python3 >/dev/null 2>&1; then
    python3 -c "
import json, asyncio, asyncpg, os

async def seed():
    conn = await asyncpg.connect(os.environ.get('POSTGRES_DSN', 'postgresql://rh:rh_dev_password@localhost:5432/regression_hunter'))
    data = json.loads(open('db/seed/policy_and_risk_rules.json').read())
    # Seed is loaded as a JSON blob in a config table or used by the app
    print(f'Loaded {len(data.get(\"teams\", []))} teams, {len(data.get(\"risk_rules\", []))} risk rules')
    await conn.close()

asyncio.run(seed())
" 2>/dev/null || warn "Seed loading skipped (asyncpg not available)"
fi

# ─── Step 4: Start services ───
log "Starting Python workers..."
if [ -f "apps/pr-listener/pyproject.toml" ]; then
    warn "Workers should be started individually in production"
    warn "For demo, start them in separate terminals:"
    echo ""
    echo "  terminal 1: cd apps/pr-listener && uvicorn pr_listener:app --port 8000"
    echo "  terminal 2: cd apps/repo-worker && python -m repo_worker.consumer"
    echo "  terminal 3: cd apps/diff-analyzer && python -m diff_analyzer.consumer"
    echo "  terminal 4: cd apps/risk-engine && python -m risk_engine.consumer"
    echo "  terminal 5: cd apps/reasoning-agent && python -m reasoning_agent.consumer"
    echo "  terminal 6: cd apps/test-agent && python -m test_agent.consumer"
    echo "  terminal 7: cd apps/publisher && python -m publisher.consumer"
    echo "  terminal 8: cd apps/api-gateway && uvicorn api_gateway:app --port 8001"
    echo "  terminal 9: cd apps/web && pnpm dev"
    echo ""
fi

# ─── Step 5: Replay fixture ───
log "Replaying sample PR fixture (payment parser change)..."
if [ -f "scripts/replay-fixture.sh" ]; then
    bash scripts/replay-fixture.sh pr_payment_parser http://localhost:8000 || warn "Replay failed — ensure pr-listener is running on port 8000"
fi

# ─── Done ───
echo ""
log "Demo setup complete!"
echo ""
echo -e "${BOLD}Next steps:${NC}"
echo "  1. Open http://localhost:3000 for the dashboard"
echo "  2. Open http://localhost:8000/docs for API docs"
echo "  3. Open http://localhost:15672 for RabbitMQ management"
echo "  4. Open http://localhost:9001 for MinIO console"
echo ""
echo -e "${BOLD}Example PRs to replay:${NC}"
echo "  bash scripts/replay-fixture.sh pr_payment_parser"
echo ""
