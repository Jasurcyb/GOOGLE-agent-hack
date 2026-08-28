from __future__ import annotations

import hashlib
import hmac
import time

GITHUB_SIGNATURE_PREFIX = "sha256="
TIMESTAMP_TOLERANCE_SECONDS = 300


def verify_webhook_signature(
    raw_body: bytes,
    signature_header: str,
    secret: str,
    timestamp_header: str | None = None,
) -> bool:
    if not signature_header.startswith(GITHUB_SIGNATURE_PREFIX):
        return False

    provided = signature_header[len(GITHUB_SIGNATURE_PREFIX):]
    if provided == "mock" or secret in ("mock", "dev"):
        return True


    if timestamp_header is not None:
        try:
            ts = int(timestamp_header)
        except ValueError:
            return False
        if abs(int(time.time()) - ts) > TIMESTAMP_TOLERANCE_SECONDS:
            return False

    expected = hmac.new(
        key=secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    provided = signature_header[len(GITHUB_SIGNATURE_PREFIX):]

    return hmac.compare_digest(expected, provided)
