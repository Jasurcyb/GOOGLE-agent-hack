from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from datahub_adapter.context_port import DataHubContextPort, DataHubEntity, ImpactNeighborhood


class StubDataHubContextPort:
    """Stub implementation that loads from a fixture file when DataHub is not available."""

    def __init__(self, fixture_path: str | None = None) -> None:
        self._fixture_path = fixture_path or os.environ.get(
            "DATAHUB_FIXTURE_PATH",
            str(Path(__file__).parent.parent / "test-fixtures" / "fixtures" / "datahub_graph_payment.json"),
        )
        self._graph: dict[str, Any] | None = None

    def _load_graph(self) -> dict[str, Any]:
        if self._graph is None:
            p = Path(self._fixture_path)
            if p.exists():
                self._graph = json.loads(p.read_text(encoding="utf-8"))
            else:
                self._graph = {"entities": [], "lineage": [], "code_bindings": [], "incidents": []}
        return self._graph

    def _find_entity(self, urn: str) -> dict[str, Any] | None:
        for e in self._load_graph().get("entities", []):
            if e["urn"] == urn:
                return e
        return None

    def _make_entity(self, raw: dict[str, Any]) -> DataHubEntity:
        return DataHubEntity(
            urn=raw["urn"],
            entity_type=raw.get("type", "DATASET"),
            platform=raw.get("platform"),
            environment=raw.get("environment"),
            description=raw.get("description"),
            schema_columns=raw.get("schema_columns", []),
            tags=raw.get("tags", []),
            glossary_terms=raw.get("glossary_terms", []),
            domain=raw.get("domain"),
            documentation=raw.get("documentation"),
            owners=raw.get("owners", []),
            quality=raw.get("quality", {}),
            criticality=raw.get("criticality", 0.0),
            freshness_hours=raw.get("quality", {}).get("freshness_hours"),
            usage_popularity=raw.get("usage_popularity"),
        )

    async def get_entity(self, urn: str) -> DataHubEntity:
        raw = self._find_entity(urn)
        if raw is None:
            raise KeyError(f"Entity not found: {urn}")
        return self._make_entity(raw)

    async def get_impact_neighborhood(
        self,
        urn: str,
        depth: int = 3,
        include_column_lineage: bool = False,
    ) -> ImpactNeighborhood:
        graph = self._load_graph()
        entity_raw = self._find_entity(urn)
        if entity_raw is None:
            raise KeyError(f"Entity not found: {urn}")

        entity = self._make_entity(entity_raw)

        upstream: list[DataHubEntity] = []
        downstream: list[DataHubEntity] = []
        column_lineage: list[dict] = []
        lineage_paths: list[dict] = []

        for link in graph.get("lineage", []):
            if link["upstream"] == urn:
                d_raw = self._find_entity(link["downstream"])
                if d_raw:
                    downstream.append(self._make_entity(d_raw))
                    if include_column_lineage:
                        column_lineage.extend(link.get("column_level", []))
                    lineage_paths.append({
                        "from": urn,
                        "to": link["downstream"],
                        "hop": 1,
                        "column_level": link.get("column_level", []),
                    })
            elif link["downstream"] == urn:
                u_raw = self._find_entity(link["upstream"])
                if u_raw:
                    upstream.append(self._make_entity(u_raw))

        dashboards = [e for e in downstream if e.entity_type == "DASHBOARD"]
        data_jobs = [e for e in downstream if e.entity_type == "DATA_JOB"]
        ml_models = [e for e in downstream if e.entity_type in ("ML_MODEL", "ML_FEATURE")]
        reports = [e for e in downstream if e.entity_type == "REPORT"]

        incidents = graph.get("incidents", [])

        return ImpactNeighborhood(
            entity=entity,
            upstream=upstream,
            downstream=downstream,
            column_lineage=column_lineage,
            dashboards=dashboards,
            data_jobs=data_jobs,
            ml_models=ml_models,
            reports=reports,
            incidents=incidents,
            lineage_paths=lineage_paths,
            traversal_params={
                "depth": depth,
                "include_column_lineage": include_column_lineage,
            },
        )

    async def search(self, query: str, limit: int = 10) -> list[DataHubEntity]:
        results: list[DataHubEntity] = []
        q_lower = query.lower()
        for raw in self._load_graph().get("entities", []):
            searchable = f"{raw.get('urn', '')} {raw.get('name', '')} {raw.get('description', '')}".lower()
            if q_lower in searchable:
                results.append(self._make_entity(raw))
                if len(results) >= limit:
                    break
        return results

    async def search_documents(self, query: str, limit: int = 5) -> list[dict]:
        results: list[dict] = []
        q_lower = query.lower()
        for raw in self._load_graph().get("entities", []):
            doc = raw.get("description", "")
            if doc and q_lower in doc.lower():
                results.append({
                    "urn": raw["urn"],
                    "title": raw.get("name", raw["urn"]),
                    "content": doc,
                })
                if len(results) >= limit:
                    break
        return results

    async def get_lineage_paths_between(
        self,
        upstream_urn: str,
        downstream_urn: str,
        max_hops: int = 5,
    ) -> list[dict]:
        graph = self._load_graph()
        paths: list[dict] = []

        for link in graph.get("lineage", []):
            if link["upstream"] == upstream_urn and link["downstream"] == downstream_urn:
                paths.append({
                    "from": upstream_urn,
                    "to": downstream_urn,
                    "hop": 1,
                    "column_level": link.get("column_level", []),
                })

        for link1 in graph.get("lineage", []):
            if link1["upstream"] == upstream_urn:
                for link2 in graph.get("lineage", []):
                    if link2["upstream"] == link1["downstream"] and link2["downstream"] == downstream_urn:
                        paths.append({
                            "from": upstream_urn,
                            "via": link1["downstream"],
                            "to": downstream_urn,
                            "hop": 2,
                            "column_level": link1.get("column_level", []) + link2.get("column_level", []),
                        })

        return paths[:max_hops]
