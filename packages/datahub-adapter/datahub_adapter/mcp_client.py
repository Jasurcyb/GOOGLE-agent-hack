from __future__ import annotations

from typing import Any

import httpx

READ_ONLY_TOOLS = [
    "search",
    "search_documents",
    "get_lineage",
    "get_lineage_paths_between",
    "get_entities",
    "get_schema",
    "get_query_history",
]


class MCPToolSet:
    """Allow-listed DataHub MCP tool configuration."""

    def __init__(
        self,
        tools: list[str] | None = None,
        mutations_enabled: bool = False,
    ) -> None:
        self._allowed = set(tools) if tools else set(READ_ONLY_TOOLS)
        if mutations_enabled:
            self._allowed.update([
                "save_document",
                "create_custom_entity",
                "create_assertion",
                "add_tag",
                "remove_tag",
                "set_structured_properties",
            ])
        self._mutations_enabled = mutations_enabled

    @property
    def allowed_tools(self) -> set[str]:
        return self._allowed

    def is_allowed(self, tool_name: str) -> bool:
        return tool_name in self._allowed

    def is_mutation(self, tool_name: str) -> bool:
        mutation_tools = {
            "save_document",
            "create_custom_entity",
            "create_assertion",
            "add_tag",
            "remove_tag",
            "set_structured_properties",
        }
        return tool_name in mutation_tools


class DataHubMCPClient:
    """Thin MCP client for read-only DataHub discovery by the reasoning agent."""

    def __init__(
        self,
        server_url: str,
        token: str | None = None,
        toolset: MCPToolSet | None = None,
    ) -> None:
        if not server_url:
            raise ValueError("DATAHUB_MCP_URL must be configured for the live MCP client")
        self._server_url = server_url
        self._token = token
        self._toolset = toolset or MCPToolSet()
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(20.0, connect=5.0),
            headers={"Accept": "application/json, text/event-stream"},
        )

    @property
    def toolset(self) -> MCPToolSet:
        return self._toolset

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        if not self._toolset.is_allowed(tool_name):
            raise PermissionError(f"Tool '{tool_name}' is not in the allow-list")

        if self._toolset.is_mutation(tool_name) and not self._toolset._mutations_enabled:
            raise PermissionError(f"Mutations are disabled; tool '{tool_name}' requires mutation permission")

        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        response = await self._client.post(
            self._server_url,
            headers=headers,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tool_name, "arguments": arguments}},
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError("DataHub MCP returned a non-JSON response") from exc
        if payload.get("error"):
            raise RuntimeError("DataHub MCP tool call failed")
        result = payload.get("result", payload)
        if not isinstance(result, dict):
            raise RuntimeError("DataHub MCP returned an invalid tool response")
        return result

    async def close(self) -> None:
        await self._client.aclose()
