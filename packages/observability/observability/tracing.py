from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator


@dataclass
class TraceSpan:
    span_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    parent_id: str | None = None
    name: str = ""
    start_time: float = field(default_factory=time.monotonic)
    end_time: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    status: str = "OK"

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, **kwargs: Any) -> None:
        self.events.append({"name": name, "timestamp": time.monotonic(), **kwargs})

    def end(self) -> None:
        self.end_time = time.monotonic()

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0


_current_trace_id: str = ""


@contextmanager
def trace_context(
    name: str,
    trace_id: str | None = None,
    parent_id: str | None = None,
    **attributes: Any,
) -> Generator[TraceSpan, None, None]:
    global _current_trace_id

    if trace_id is None:
        trace_id = _current_trace_id or str(uuid.uuid4())
    _current_trace_id = trace_id

    span = TraceSpan(trace_id=trace_id, parent_id=parent_id, name=name)
    for k, v in attributes.items():
        span.set_attribute(k, v)

    try:
        yield span
        span.status = "OK"
    except Exception as e:
        span.status = "ERROR"
        span.add_event("exception", error=str(e))
        raise
    finally:
        span.end()
