from __future__ import annotations

from typing import Any, Protocol


class DataHubGraphPort(Protocol):
    """SDK/GraphQL adapter for deterministic bulk fetch and write workflows."""

    async def get_entities_batch(self, urns: list[str]) -> list[dict[str, Any]]: ...

    async def get_lineage_batch(
        self,
        urns: list[str],
        direction: str = "DOWNSTREAM",
        depth: int = 3,
    ) -> dict[str, list[dict]]: ...

    async def save_document(
        self,
        parent_urn: str,
        document_id: str,
        content: str,
        content_type: str = "text/markdown",
    ) -> str: ...

    async def create_custom_entity(
        self,
        entity_type: str,
        properties: dict[str, Any],
    ) -> str: ...

    async def attach_structured_properties(
        self,
        urn: str,
        properties: dict[str, Any],
    ) -> None: ...

    async def add_tag(self, urn: str, tag: str) -> None: ...

    async def remove_tag(self, urn: str, tag: str) -> None: ...

    async def create_assertion(
        self,
        dataset_urn: str,
        assertion_type: str,
        definition: dict[str, Any],
        status: str = "PROPOSED",
    ) -> str: ...
