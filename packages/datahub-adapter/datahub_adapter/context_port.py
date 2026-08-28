from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class DataHubEntity:
    urn: str
    entity_type: str
    platform: str | None = None
    environment: str | None = None
    description: str | None = None
    schema_columns: list[dict] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    glossary_terms: list[str] = field(default_factory=list)
    domain: str | None = None
    documentation: str | None = None
    owners: list[dict] = field(default_factory=list)
    quality: dict = field(default_factory=dict)
    criticality: float = 0.0
    freshness_hours: float | None = None
    usage_popularity: float | None = None
    aspect_version: int = 0
    aspect_timestamp: str | None = None


@dataclass
class ImpactNeighborhood:
    entity: DataHubEntity
    upstream: list[DataHubEntity] = field(default_factory=list)
    downstream: list[DataHubEntity] = field(default_factory=list)
    column_lineage: list[dict] = field(default_factory=list)
    dashboards: list[DataHubEntity] = field(default_factory=list)
    data_jobs: list[DataHubEntity] = field(default_factory=list)
    ml_models: list[DataHubEntity] = field(default_factory=list)
    reports: list[DataHubEntity] = field(default_factory=list)
    incidents: list[dict] = field(default_factory=list)
    lineage_paths: list[dict] = field(default_factory=list)
    traversal_params: dict = field(default_factory=dict)


class DataHubContextPort(Protocol):
    """Agent Context Kit integration for stable, curated retrieval."""

    async def get_entity(self, urn: str) -> DataHubEntity: ...

    async def get_impact_neighborhood(
        self,
        urn: str,
        depth: int = 3,
        include_column_lineage: bool = False,
    ) -> ImpactNeighborhood: ...

    async def search(self, query: str, limit: int = 10) -> list[DataHubEntity]: ...

    async def search_documents(self, query: str, limit: int = 5) -> list[dict]: ...

    async def get_lineage_paths_between(
        self,
        upstream_urn: str,
        downstream_urn: str,
        max_hops: int = 5,
    ) -> list[dict]: ...
