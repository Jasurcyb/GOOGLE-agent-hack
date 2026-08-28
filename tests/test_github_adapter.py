from __future__ import annotations

import pytest

from github_adapter.webhook import verify_webhook_signature
from github_adapter.events import parse_webhook_event, WebhookEvent
from github_adapter.client import GitHubAppClient


class TestWebhookSignature:
    def test_valid_signature(self):
        import hmac
        import hashlib

        secret = "test-secret"
        body = b'{"action": "opened"}'
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        sig = f"sha256={expected}"

        assert verify_webhook_signature(body, sig, secret) is True

    def test_invalid_signature(self):
        assert verify_webhook_signature(b'{}', "sha256=invalid", "secret") is False

    def test_missing_prefix(self):
        assert verify_webhook_signature(b'{}', "invalid", "secret") is False


class TestWebhookParsing:
    def test_parse_pull_request(self):
        import json

        payload = json.dumps({
            "event_type": "pull_request",
            "action": "opened",
            "repository": {"full_name": "acme/payments"},
            "pull_request": {
                "number": 481,
                "head": {"sha": "abc123"},
                "base": {"sha": "fedcba"},
                "user": {"login": "dev-alice"},
            },
            "installation": {"id": 123456},
        }).encode()

        event = parse_webhook_event(payload)
        assert event is not None
        assert event.event_type == "pull_request"
        assert event.action == "opened"
        assert event.repository == "acme/payments"
        assert event.pr_number == 481
        assert event.head_sha == "abc123"
        assert event.author_login == "dev-alice"

    def test_parse_push(self):
        import json

        payload = json.dumps({
            "event_type": "push",
            "repository": {"full_name": "acme/payments"},
            "after": "newsha",
            "before": "oldsha",
            "sender": {"login": "dev-bob"},
            "installation": {"id": 123456},
        }).encode()

        event = parse_webhook_event(payload)
        assert event is not None
        assert event.event_type == "push"
        assert event.head_sha == "newsha"

    def test_parse_unknown_event(self):
        import json

        payload = json.dumps({"event_type": "issues"}).encode()
        event = parse_webhook_event(payload)
        assert event is None
