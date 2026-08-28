from __future__ import annotations

import re
from dataclasses import dataclass, field


SECRET_PATTERNS: list[re.Pattern] = [
    re.compile(r'(?:api[_-]?key|apikey)\s*[=:]\s*["\']?([\w\-]{20,})', re.IGNORECASE),
    re.compile(r'(?:secret|password|passwd)\s*[=:]\s*["\']?([^\s"\']+)', re.IGNORECASE),
    re.compile(r'(?:token|bearer)\s*[=:]\s*["\']?([\w\-\.]{20,})', re.IGNORECASE),
    re.compile(r'(?:private[_-]?key)\s*[=:]\s*["\']?-----BEGIN ([^-]+)', re.IGNORECASE),
    re.compile(r'AKIA[0-9A-Z]{16}'),
    re.compile(r'gh[pousr]_[A-Za-z0-9]{36}'),
    re.compile(r'sk-[A-Za-z0-9]{20,}'),
]

PII_PATTERNS: list[re.Pattern] = [
    re.compile(r'\b[\w._%+-]+@[\w.-]+\.[A-Za-z]{2,}\b'),
    re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),
    re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
    re.compile(r'\b(customer|user)[-_]?id\s*[=:]\s*["\']?(\d+)', re.IGNORECASE),
]

REDACTED = "[REDACTED]"


@dataclass
class RedactionResult:
    redacted_content: str
    secret_count: int = 0
    pii_count: int = 0
    secrets_found: list[str] = field(default_factory=list)
    pii_found: list[str] = field(default_factory=list)


def scan_secrets(content: str) -> list[str]:
    found: list[str] = []
    for pattern in SECRET_PATTERNS:
        for m in pattern.finditer(content):
            found.append(m.group(0)[:50])
    return found


def scan_pii(content: str) -> list[str]:
    found: list[str] = []
    for pattern in PII_PATTERNS:
        for m in pattern.finditer(content):
            found.append(m.group(0)[:50])
    return found


def redact(content: str, remove_pii: bool = True) -> RedactionResult:
    result = RedactionResult(redacted_content=content)

    for pattern in SECRET_PATTERNS:
        matches = list(pattern.finditer(content))
        for m in matches:
            result.secret_count += 1
            result.secrets_found.append(m.group(0)[:50])
        content = pattern.sub(REDACTED, content)

    if remove_pii:
        for pattern in PII_PATTERNS:
            matches = list(pattern.finditer(content))
            for m in matches:
                result.pii_count += 1
                result.pii_found.append(m.group(0)[:50])
            content = pattern.sub("[PII_REDACTED]", content)

    result.redacted_content = content
    return result


def redact_source_files(files: dict[str, str]) -> tuple[dict[str, str], RedactionResult]:
    total = RedactionResult(redacted_content="")
    redacted: dict[str, str] = {}

    for path, content in files.items():
        result = redact(content)
        redacted[path] = result.redacted_content
        total.secret_count += result.secret_count
        total.pii_count += result.pii_count
        total.secrets_found.extend(result.secrets_found)
        total.pii_found.extend(result.pii_found)

    return redacted, total


def redact_datahub_assets(assets: list[dict]) -> tuple[list[dict], int]:
    redacted: list[dict] = []
    removed = 0

    for asset in assets:
        tags = asset.get("tags", [])
        if "restricted" in tags:
            removed += 1
            continue

        desc = asset.get("description", "")
        if desc:
            r = redact(desc, remove_pii=True)
            asset["description"] = r.redacted_content

        redacted.append(asset)

    return redacted, removed
