from __future__ import annotations

import re

from code_intelligence.analyzer_protocol import Entrypoint, ParseResult, Symbol


FASTAPI_ROUTE_RE = re.compile(
    r'@\w+\.\w+\(\s*["\']([^"\']+)["\'].*?\)\s*def\s+(\w+)',
    re.DOTALL,
)
FLASK_ROUTE_RE = re.compile(
    r'@\w+\.route\(\s*["\']([^"\']+)["\'].*?\)\s*def\s+(\w+)',
    re.DOTALL,
)
CELERY_TASK_RE = re.compile(r'@\w+\.task\b.*?\s+def\s+(\w+)', re.DOTALL)
CELERY_SHARED_TASK_RE = re.compile(r'@shared_task\b.*?\s+def\s+(\w+)', re.DOTALL)
AIRFLOW_DAG_RE = re.compile(r'DAG\s*\(\s*["\']([^"\']+)["\']', re.DOTALL)
KAFKA_PRODUCER_RE = re.compile(r'KafkaProducer\s*\(', re.DOTALL)
KAFKA_CONSUMER_RE = re.compile(r'KafkaConsumer\s*\(\s*["\']([^"\']+)["\']', re.DOTALL)


def detect_entrypoints(parse: ParseResult) -> list[Entrypoint]:
    """Detect operational entry points from parsed symbols and source."""
    entrypoints: list[Entrypoint] = []

    for sym in parse.symbols:
        if _is_fastapi_route(sym):
            route = _extract_route(sym, parse)
            entrypoints.append(Entrypoint(
                symbol_id=sym.id,
                framework="fastapi",
                route=route,
                method=_extract_http_method(sym),
                is_public=True,
            ))
        elif _is_flask_route(sym):
            route = _extract_route(sym, parse)
            entrypoints.append(Entrypoint(
                symbol_id=sym.id,
                framework="flask",
                route=route,
                is_public=True,
            ))
        elif _is_celery_task(sym):
            entrypoints.append(Entrypoint(
                symbol_id=sym.id,
                framework="celery",
                is_public=False,
            ))
        elif _is_airflow_dag(sym, parse):
            entrypoints.append(Entrypoint(
                symbol_id=sym.id,
                framework="airflow",
                is_public=False,
            ))
        elif _is_kafka_consumer(sym, parse):
            topic = _extract_kafka_topic(sym, parse)
            entrypoints.append(Entrypoint(
                symbol_id=sym.id,
                framework="kafka_consumer",
                route=topic,
                is_public=False,
            ))
        elif _is_kafka_producer(sym, parse):
            entrypoints.append(Entrypoint(
                symbol_id=sym.id,
                framework="kafka_producer",
                is_public=False,
            ))

    return entrypoints


def _is_fastapi_route(sym: Symbol) -> bool:
    return any(
        d in ("@app.get", "@app.post", "@app.put", "@app.delete",
              "@app.patch", "@router.get", "@router.post",
              "@router.put", "@router.delete", "@router.patch")
        for d in sym.decorators
    )


def _is_flask_route(sym: Symbol) -> bool:
    return any("@app.route" in d or "@bp.route" in d for d in sym.decorators)


def _is_celery_task(sym: Symbol) -> bool:
    return any(
        "@celery.task" in d or "@shared_task" in d or "@app.task" in d
        for d in sym.decorators
    )


def _is_airflow_dag(sym: Symbol, parse: ParseResult) -> bool:
    return any("DAG(" in d or "dag_id" in d for d in sym.decorators)


def _is_kafka_consumer(sym: Symbol, parse: ParseResult) -> bool:
    return any("KafkaConsumer" in d for d in sym.decorators) or \
        any("KafkaConsumer(" in imp for imp in parse.imports)


def _is_kafka_producer(sym: Symbol, parse: ParseResult) -> bool:
    return any("KafkaProducer" in d for d in sym.decorators) or \
        any("KafkaProducer(" in imp for imp in parse.imports)


def _extract_route(sym: Symbol, parse: ParseResult) -> str:
    for d in sym.decorators:
        match = re.search(r'["\']([^"\']+)["\']', d)
        if match:
            return match.group(1)
    return ""


def _extract_http_method(sym: Symbol) -> str:
    for d in sym.decorators:
        for method in ("get", "post", "put", "delete", "patch"):
            if f".{method}(" in d or f"@{method}(" in d:
                return method.upper()
    return "GET"


def _extract_kafka_topic(sym: Symbol, parse: ParseResult) -> str:
    for d in sym.decorators:
        match = re.search(r'["\']([^"\']+)["\']', d)
        if match:
            return match.group(1)
    return ""
