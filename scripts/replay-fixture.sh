#!/usr/bin/env bash
# Replay a fixture PR through the PR Listener webhook endpoint.
# Usage: ./scripts/replay-fixture.sh [fixture_name] [listener_url]
#
# Defaults:
#   fixture_name = pr_payment_parser
#   listener_url = http://localhost:8000

set -euo pipefail

FIXTURE_NAME="${1:-pr_payment_parser}"
LISTENER_URL="${2:-http://localhost:8000}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
FIXTURE_PATH="$ROOT_DIR/packages/test-fixtures/fixtures/${FIXTURE_NAME}.json"

if [ ! -f "$FIXTURE_PATH" ]; then
    echo "ERROR: Fixture not found at $FIXTURE_PATH"
    exit 1
fi

echo "Replaying fixture: $FIXTURE_NAME"
echo "  File: $FIXTURE_PATH"
echo "  Target: $LISTENER_URL/v1/webhooks/github"
echo ""

DELIVERY_ID="replay-$(date +%s)"

curl -s -X POST \
    "${LISTENER_URL}/v1/webhooks/github" \
    -H "Content-Type: application/json" \
    -H "X-GitHub-Event: pull_request" \
    -H "X-GitHub-Delivery: ${DELIVERY_ID}" \
    -H "X-Hub-Signature-256: sha256=mock" \
    -d @"$FIXTURE_PATH" | python3 -m json.tool

echo ""
echo "Done. Delivery ID: $DELIVERY_ID"
