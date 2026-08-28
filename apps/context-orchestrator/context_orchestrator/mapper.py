from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from contracts.models.enums import BindingType
from contracts.models.evidence import (
    DataHubImpact,
    EvidenceBundle,
    EvidenceIndexEntry,
    RedactionManifest,
)
from datahub_adapter.context_port import DataHubContextPort, DataHubEntity, ImpactNeighborhood


@dataclass
class AssetBinding:
    symbol_id: str
    datahub_urn: str
    binding_type: BindingType
    evidence: str
    confidence: float
    is_authoritative: bool


SQL_TABLE_RE = re.compile(
    r'\b(?:FROM|JOIN|INTO|UPDATE|DELETE\s+FROM)\s+([\w.]+)',
    re.IGNORECASE,
)
KAFKA_TOPIC_RE = re.compile(
    r'["\']([\w._-]+)["\']',
)
YAML_ASSET_RE = re.compile(
    r'datahub_urn:\s*["\']?([^"\'\n]+)["\']?',
    re.IGNORECASE,
)


class CodeToAssetMapper:
    """Maps code symbols to DataHub URNs using 4 levels of evidence."""

    def __init__(self, datahub_port: DataHubContextPort) -> None:
        self._port = datahub_port

    async def map_symbols_to_assets(
        self,
        symbols: list[dict],
        imports: list[str],
        source_content: dict[str, str] | None = None,
    ) -> list[AssetBinding]:
        bindings: list[AssetBinding] = []

        bindings.extend(self._level1_yaml_annotations(source_content or {}))
        bindings.extend(self._level2_pipeline_metadata(imports))
        bindings.extend(self._level3_ast_sql_refs(symbols, source_content or {}))

        discovered = await self._level4_semantic_search(symbols)
        bindings.extend(discovered)

        return bindings

    def _level1_yaml_annotations(self, source_content: dict[str, str]) -> list[AssetBinding]:
        """Level 1: datahub_assets.yaml or decorators linking symbols to URNs."""
        bindings: list[AssetBinding] = []

        for path, content in source_content.items():
            if "datahub_assets" in path or path.endswith(".yaml") or path.endswith(".yml"):
                for m in YAML_ASSET_RE.finditer(content):
                    urn = m.group(1).strip()
                    bindings.append(AssetBinding(
                        symbol_id="yaml:" + path,
                        datahub_urn=urn,
                        binding_type=BindingType.AUTHORITATIVE,
                        evidence=f"datahub_assets.yaml in {path}",
                        confidence=1.0,
                        is_authoritative=True,
                    ))

            for line in content.splitlines():
                if "@datahub_urn" in line or "datahub:asset:" in line:
                    m = re.search(r'["\']([^"\']+)["\']', line)
                    if m:
                        bindings.append(AssetBinding(
                            symbol_id="decorator:" + path,
                            datahub_urn=m.group(1),
                            binding_type=BindingType.AUTHORITATIVE,
                            evidence=f"decorator in {path}",
                            confidence=1.0,
                            is_authoritative=True,
                        ))

        return bindings

    def _level2_pipeline_metadata(self, imports: list[str]) -> list[AssetBinding]:
        """Level 2: OpenLineage, dbt manifest, Airflow metadata, Spark logs."""
        bindings: list[AssetBinding] = []

        for imp in imports:
            if "openlineage" in imp.lower():
                bindings.append(AssetBinding(
                    symbol_id="openlineage",
                    datahub_urn="",
                    binding_type=BindingType.AUTHORITATIVE,
                    evidence="OpenLineage integration detected",
                    confidence=0.95,
                    is_authoritative=True,
                ))
            if "dbt" in imp.lower() and "manifest" in imp.lower():
                bindings.append(AssetBinding(
                    symbol_id="dbt:manifest",
                    datahub_urn="",
                    binding_type=BindingType.AUTHORITATIVE,
                    evidence="dbt manifest.json reference",
                    confidence=0.95,
                    is_authoritative=True,
                ))

        return bindings

    def _level3_ast_sql_refs(
        self,
        symbols: list[dict],
        source_content: dict[str, str],
    ) -> list[AssetBinding]:
        """Level 3: AST-extracted SQL table/column references, Kafka topics."""
        bindings: list[AssetBinding] = []

        for sym in symbols:
            fqn = sym.get("fqn", "")
            file_path = sym.get("file_path", "")

            content = source_content.get(file_path, "")
            if not content:
                continue

            start = sym.get("start_line", 0)
            end = sym.get("end_line", 0)
            if start and end:
                lines = content.splitlines()
                body = "\n".join(lines[start-1:end])
            else:
                body = content

            for m in SQL_TABLE_RE.finditer(body):
                table = m.group(1)
                urn = f"urn:li:dataset:(urn:li:dataPlatform:snowflake,{table},PROD)"
                bindings.append(AssetBinding(
                    symbol_id=fqn,
                    datahub_urn=urn,
                    binding_type=BindingType.AUTHORITATIVE,
                    evidence=f"AST-extracted SQL reference: {m.group(0)}",
                    confidence=1.0,
                    is_authoritative=True,
                ))

            if "KafkaProducer" in body or "KafkaConsumer" in body:
                for m in KAFKA_TOPIC_RE.finditer(body):
                    topic = m.group(1)
                    if topic and not topic.startswith("urn:"):
                        urn = f"urn:li:dataset:(urn:li:dataPlatform:kafka,{topic},PROD)"
                        bindings.append(AssetBinding(
                            symbol_id=fqn,
                            datahub_urn=urn,
                            binding_type=BindingType.AUTHORITATIVE,
                            evidence=f"Kafka topic reference: {topic}",
                            confidence=0.9,
                            is_authoritative=True,
                        ))

        return bindings

    async def _level4_semantic_search(self, symbols: list[dict]) -> list[AssetBinding]:
        """Level 4: DataHub search/semantic search candidates — DISCOVERED, confidence < 1.0."""
        bindings: list[AssetBinding] = []

        for sym in symbols:
            name = sym.get("fqn", "").split(".")[-1]
            if not name or len(name) < 3:
                continue

            results = await self._port.search(name, limit=3)
            for entity in results:
                bindings.append(AssetBinding(
                    symbol_id=sym.get("fqn", ""),
                    datahub_urn=entity.urn,
                    binding_type=BindingType.DISCOVERED,
                    evidence=f"DataHub semantic search for '{name}'",
                    confidence=0.5,
                    is_authoritative=False,
                ))

        return bindings
