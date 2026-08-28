from __future__ import annotations

import json
from typing import Any

from datahub_adapter.context_port import DataHubContextPort, DataHubEntity, ImpactNeighborhood
from datahub_adapter.graph_port import DataHubGraphPort
from datahub_adapter.mcp_client import DataHubMCPClient, MCPToolSet


def _tool_json(result: dict[str, Any]) -> Any:
    """Normalize structured MCP responses; ignore unstructured prose."""
    if "structuredContent" in result:
        return result["structuredContent"]
    content = result.get("content", [])
    for item in content if isinstance(content, list) else []:
        raw_text = item.get("text") if isinstance(item, dict) else None
        if raw_text:
            try:
                return json.loads(raw_text)
            except json.JSONDecodeError:
                continue
    return result


def _entity(raw: dict[str, Any]) -> DataHubEntity:
    return DataHubEntity(
        urn=str(raw.get("urn", raw.get("entityUrn", ""))),
        entity_type=str(raw.get("type", raw.get("entityType", "DATASET"))).upper(),
        platform=raw.get("platform"),
        environment=raw.get("environment"),
        description=raw.get("description"),
        schema_columns=raw.get("schema", raw.get("schema_columns", [])) or [],
        tags=raw.get("tags", []) or [],
        glossary_terms=raw.get("glossaryTerms", raw.get("glossary_terms", [])) or [],
        domain=raw.get("domain"),
        documentation=raw.get("documentation"),
        owners=raw.get("owners", []) or [],
        quality=raw.get("quality", {}) or {},
        criticality=float(raw.get("criticality", 0.0) or 0.0),
        freshness_hours=raw.get("freshness_hours"),
        usage_popularity=raw.get("usage_popularity"),
        aspect_version=int(raw.get("aspectVersion", 0) or 0),
        aspect_timestamp=raw.get("aspectTimestamp"),
    )


class MCPDataHubContextPort(DataHubContextPort):
    """Context retrieval through the official DataHub MCP server."""

    def __init__(self, server_url: str, token: str | None = None) -> None:
        self._mcp = DataHubMCPClient(server_url=server_url, token=token)

    async def get_entity(self, urn: str) -> DataHubEntity:
        data = _tool_json(await self._mcp.call_tool("get_entities", {"urns": [urn]}))
        candidates = data.get("entities", data if isinstance(data, list) else [])
        if not candidates:
            raise KeyError(urn)
        return _entity(candidates[0])

    async def get_impact_neighborhood(self, urn: str, depth: int = 3, include_column_lineage: bool = False) -> ImpactNeighborhood:
        entity = await self.get_entity(urn)
        data = _tool_json(await self._mcp.call_tool("get_lineage", {
            "urn": urn, "direction": "DOWNSTREAM", "max_hops": depth,
            "include_column_lineage": include_column_lineage,
        }))
        paths = data.get("paths", data.get("lineage", [])) if isinstance(data, dict) else []
        downstream = [_entity(item) for item in data.get("entities", []) if isinstance(item, dict)] if isinstance(data, dict) else []
        return ImpactNeighborhood(
            entity=entity,
            downstream=downstream,
            dashboards=[item for item in downstream if item.entity_type == "DASHBOARD"],
            data_jobs=[item for item in downstream if item.entity_type in {"DATA_JOB", "DATAFLOW"}],
            ml_models=[item for item in downstream if item.entity_type in {"ML_MODEL", "ML_FEATURE"}],
            lineage_paths=paths if isinstance(paths, list) else [],
            traversal_params={"depth": depth, "include_column_lineage": include_column_lineage},
        )

    async def search(self, query: str, limit: int = 10) -> list[DataHubEntity]:
        data = _tool_json(await self._mcp.call_tool("search", {"query": query, "limit": limit}))
        items = data.get("entities", data.get("results", [])) if isinstance(data, dict) else data
        return [_entity(item) for item in items if isinstance(item, dict)][:limit]

    async def search_documents(self, query: str, limit: int = 5) -> list[dict]:
        data = _tool_json(await self._mcp.call_tool("search_documents", {"query": query, "limit": limit}))
        return data.get("documents", data.get("results", [])) if isinstance(data, dict) else []

    async def get_lineage_paths_between(self, upstream_urn: str, downstream_urn: str, max_hops: int = 5) -> list[dict]:
        data = _tool_json(await self._mcp.call_tool("get_lineage_paths_between", {
            "upstream_urn": upstream_urn, "downstream_urn": downstream_urn, "max_hops": max_hops,
        }))
        return data.get("paths", []) if isinstance(data, dict) else []


class MCPDataHubGraphPort(DataHubGraphPort):
    """Mutating port; the server must explicitly allow mutation tools."""

    def __init__(self, server_url: str, token: str | None = None) -> None:
        self._mcp = DataHubMCPClient(server_url, token, MCPToolSet(mutations_enabled=True))

    async def get_entities_batch(self, urns: list[str]) -> list[dict[str, Any]]:
        data = _tool_json(await self._mcp.call_tool("get_entities", {"urns": urns}))
        return data.get("entities", []) if isinstance(data, dict) else []

    async def get_lineage_batch(self, urns: list[str], direction: str = "DOWNSTREAM", depth: int = 3) -> dict[str, list[dict]]:
        return {urn: [_tool_json(await self._mcp.call_tool("get_lineage", {"urn": urn, "direction": direction, "max_hops": depth}))] for urn in urns}

    async def save_document(self, parent_urn: str, document_id: str, content: str, content_type: str = "text/markdown") -> str:
        data = _tool_json(await self._mcp.call_tool("save_document", {"parent_urn": parent_urn, "document_id": document_id, "content": content, "content_type": content_type}))
        return str(data.get("urn", document_id)) if isinstance(data, dict) else document_id

    async def create_custom_entity(self, entity_type: str, properties: dict[str, Any]) -> str:
        data = _tool_json(await self._mcp.call_tool("create_custom_entity", {"entity_type": entity_type, "properties": properties}))
        return str(data.get("urn", "")) if isinstance(data, dict) else ""

    async def attach_structured_properties(self, urn: str, properties: dict[str, Any]) -> None:
        await self._mcp.call_tool("set_structured_properties", {"urn": urn, "properties": properties})

    async def add_tag(self, urn: str, tag: str) -> None:
        await self._mcp.call_tool("add_tag", {"urn": urn, "tag": tag})

    async def remove_tag(self, urn: str, tag: str) -> None:
        await self._mcp.call_tool("remove_tag", {"urn": urn, "tag": tag})

    async def create_assertion(self, dataset_urn: str, assertion_type: str, definition: dict[str, Any], status: str = "PROPOSED") -> str:
        data = _tool_json(await self._mcp.call_tool("create_assertion", {"dataset_urn": dataset_urn, "assertion_type": assertion_type, "definition": definition, "status": status}))
        return str(data.get("urn", "")) if isinstance(data, dict) else ""
