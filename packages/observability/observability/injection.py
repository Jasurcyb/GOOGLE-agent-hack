from __future__ import annotations

import re
from dataclasses import dataclass


INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r'ignore\s+(?:all\s+)?(?:previous|above)\s+instructions', re.IGNORECASE),
    re.compile(r'you\s+are\s+(?:now|actually)\s+a', re.IGNORECASE),
    re.compile(r'disregard\s+(?:all\s+)?(?:prior|previous)', re.IGNORECASE),
    re.compile(r'new\s+instructions?\s*:', re.IGNORECASE),
    re.compile(r'system\s*:\s*', re.IGNORECASE),
    re.compile(r'<\|system\|>', re.IGNORECASE),
    re.compile(r'<\|im_start\|>', re.IGNORECASE),
    re.compile(r'###\s*system\s*$', re.IGNORECASE | re.MULTILINE),
    re.compile(r'\[SYSTEM\]', re.IGNORECASE),
    re.compile(r'forget\s+(?:everything|all\s+rules)', re.IGNORECASE),
]

ALLOWED_TOOL_NAMES: set[str] = {
    "search", "search_documents", "get_lineage",
    "get_lineage_paths_between", "get_entities", "get_schema",
    "get_query_history",
}

DISALLOWED_IN_TOOL_OUTPUT: list[re.Pattern] = [
    re.compile(r'role\s*[:=]\s*["\']?system', re.IGNORECASE),
    re.compile(r'tool\s*[:=]\s*["\']?(?!search|get_)', re.IGNORECASE),
]


@dataclass
class InjectionCheckResult:
    is_safe: bool
    detected_patterns: list[str]
    sanitized_content: str


def check_prompt_injection(content: str) -> InjectionCheckResult:
    detected: list[str] = []

    for pattern in INJECTION_PATTERNS:
        for m in pattern.finditer(content):
            detected.append(m.group(0)[:80])

    is_safe = len(detected) == 0
    sanitized = content

    for pattern in INJECTION_PATTERNS:
        sanitized = pattern.sub("[FILTERED]", sanitized)

    return InjectionCheckResult(
        is_safe=is_safe,
        detected_patterns=detected,
        sanitized_content=sanitized,
    )


def is_tool_allowed(tool_name: str) -> bool:
    return tool_name in ALLOWED_TOOL_NAMES


def sanitize_tool_output(output: str) -> str:
    for pattern in DISALLOWED_IN_TOOL_OUTPUT:
        output = pattern.sub("[FILTERED]", output)
    return output


def classify_untrusted(content: str) -> str:
    """Mark content as untrusted data for LLM context."""
    return f"[UNTRUSTED_DATA_START]\n{content}\n[UNTRUSTED_DATA_END]"
