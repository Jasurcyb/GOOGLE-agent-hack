from __future__ import annotations

import logging
import uuid
from typing import Any

from datahub_adapter.graph_port import DataHubGraphPort

logger = logging.getLogger("datahub_adapter.stub_graph")


class StubDataHubGraphPort(DataHubGraphPort):
    """InMemory / Stub DataHub graph port for write-back operations and test execution."""

    def __init__(self) -> None:
        self.documents: dict[str, dict[str, Any]] = {}
        self.custom_entities: dict[str, dict[str, Any]] = {}
        self.structured_properties: dict[str, dict[str, Any]] = {}
        self.tags: dict[str, set[str]] = {}
        self.assertions: dict[str, dict[str, Any]] = {}

    async def get_entities_batch(self, urns: list[str]) -> list[dict[str, Any]]:
        results = []
        for urn in urns:
            if urn in self.custom_entities:
                results.append(self.custom_entities[urn])
            else:
                results.append({"urn": urn, "type": "DATASET"})
        return results

    async def get_lineage_batch(
        self,
        urns: list[str],
        direction: str = "DOWNSTREAM",
        depth: int = 3,
    ) -> dict[str, list[dict]]:
        return {urn: [] for urn in urns}

    async def save_document(
        self,
        parent_urn: str,
        document_id: str,
        content: str,
        content_type: str = "text/markdown",
    ) -> str:
        doc_urn = f"urn:li:document:{uuid.uuid4().hex[:12]}"
        self.documents[doc_urn] = {
            "parent_urn": parent_urn,
            "document_id": document_id,
            "content": content,
            "content_type": content_type,
        }
        logger.info("StubDataHubGraphPort saved document %s for parent %s", doc_urn, parent_urn)
        return doc_urn

    async def create_custom_entity(
        self,
        entity_type: str,
        properties: dict[str, Any],
    ) -> str:
        entity_urn = f"urn:li:{entity_type.lower()}:{uuid.uuid4().hex[:12]}"
        self.custom_entities[entity_urn] = {
            "urn": entity_urn,
            "type": entity_type,
            "properties": properties,
        }
        logger.info("StubDataHubGraphPort created custom entity %s (%s)", entity_urn, entity_type)
        return entity_urn

    async def attach_structured_properties(
        self,
        urn: str,
        properties: dict[str, Any],
    ) -> None:
        if urn not in self.structured_properties:
            self.structured_properties[urn] = {}
        self.structured_properties[urn].update(properties)
        logger.info("StubDataHubGraphPort attached structured properties to %s", urn)

    async def add_tag(self, urn: str, tag: str) -> None:
        if urn not in self.tags:
            self.tags[urn] = set()
        self.tags[urn].add(tag)
        logger.info("StubDataHubGraphPort added tag %s to %s", tag, urn)

    async def remove_tag(self, urn: str, tag: str) -> None:
        if urn in self.tags:
            self.tags[urn].discard(tag)

    async def create_assertion(
        self,
        dataset_urn: str,
        assertion_type: str,
        definition: dict[str, Any],
        status: str = "PROPOSED",
    ) -> str:
        assertion_urn = f"urn:li:assertion:{uuid.uuid4().hex[:12]}"
        self.assertions[assertion_urn] = {
            "dataset_urn": dataset_urn,
            "assertion_type": assertion_type,
            "definition": definition,
            "status": status,
        }
        logger.info("StubDataHubGraphPort created assertion %s for dataset %s", assertion_urn, dataset_urn)
        return assertion_urn
