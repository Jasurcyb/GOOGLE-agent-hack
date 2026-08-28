from __future__ import annotations

import json
import os
from typing import Any

from contracts.models.evidence import (
    DataHubImpact,
    EvidenceBundle,
    EvidenceIndexEntry,
    RedactionManifest,
)
from datahub_adapter.context_port import DataHubContextPort
from datahub_adapter.stub_context import StubDataHubContextPort
from datahub_adapter.live_context import MCPDataHubContextPort

from context_orchestrator.mapper import AssetBinding, CodeToAssetMapper

SECRET_PATTERNS = [
    "api_key",
    "secret",
    "password",
    "token",
    "private_key",
    "credential",
]

PII_PATTERNS = [
    "email",
    "phone",
    "ssn",
    "address",
    "user_id",
    "customer_id",
]


class ContextBuilder:
    """Builds a versioned, redacted EvidenceBundle with token budget."""

    def __init__(
        self,
        datahub_port: DataHubContextPort | None = None,
        token_ceiling: int = 80000,
        default_lineage_depth: int = 3,
    ) -> None:
        if datahub_port is not None:
            self._port = datahub_port
        elif os.environ.get("DATAHUB_MCP_URL"):
            self._port = MCPDataHubContextPort(
                os.environ["DATAHUB_MCP_URL"], os.environ.get("DATAHUB_TOKEN")
            )
        else:
            self._port = StubDataHubContextPort()
        self._mapper = CodeToAssetMapper(self._port)
        self._token_ceiling = token_ceiling
        self._default_depth = default_lineage_depth

    async def build(
        self,
        run_id: str,
        repo: str,
        head_sha: str,
        change_summary: dict,
        code_impact: dict,
        symbols: list[dict],
        imports: list[str],
        source_content: dict[str, str] | None = None,
        policy: dict | None = None,
    ) -> EvidenceBundle:
        source_content = source_content or {}

        bindings = await self._mapper.map_symbols_to_assets(
            symbols, imports, source_content,
        )

        authoritative = [b for b in bindings if b.is_authoritative and b.datahub_urn]
        discovered = [b for b in bindings if not b.is_authoritative]

        datahub_impact = await self._retrieve_impact_neighborhoods(authoritative)

        redaction = self._redact(source_content, datahub_impact)

        evidence_index: dict[str, EvidenceIndexEntry] = {}
        for i, b in enumerate(authoritative):
            ev_id = f"ev_{i+1:03d}"
            evidence_index[ev_id] = EvidenceIndexEntry(
                source="datahub",
                uri=b.datahub_urn,
                trust="AUTHORITATIVE",
            )

        for i, b in enumerate(discovered):
            ev_id = f"ev_disc_{i+1:03d}"
            evidence_index[ev_id] = EvidenceIndexEntry(
                source="datahub_search",
                uri=b.datahub_urn,
                trust="DISCOVERED",
            )

        bundle = EvidenceBundle(
            bundle_version="1.0",
            run={
                "id": run_id,
                "repo": repo,
                "head_sha": head_sha,
            },
            change_summary=change_summary,
            code_impact=code_impact,
            datahub_impact=datahub_impact,
            historical_signals={},
            risk_features=self._extract_risk_features(change_summary, code_impact, datahub_impact, bindings),
            policy=policy or {},
            evidence_index=evidence_index,
            redaction_manifest=redaction,
        )

        return self._enforce_token_budget(bundle)

    async def _retrieve_impact_neighborhoods(
        self,
        bindings: list[AssetBinding],
    ) -> DataHubImpact:
        assets: list[dict] = []
        lineage_paths: list[dict] = []
        owners: list[dict] = []
        quality: list[dict] = []

        seen_urns: set[str] = set()

        for binding in bindings:
            if binding.datahub_urn in seen_urns:
                continue
            seen_urns.add(binding.datahub_urn)

            try:
                neighborhood = await self._port.get_impact_neighborhood(
                    binding.datahub_urn,
                    depth=self._default_depth,
                )

                entity = neighborhood.entity
                assets.append({
                    "urn": entity.urn,
                    "type": entity.entity_type,
                    "platform": entity.platform,
                    "description": entity.description,
                    "tags": entity.tags,
                    "criticality": entity.criticality,
                    "owners": entity.owners,
                    "quality": entity.quality,
                    "freshness_hours": entity.freshness_hours,
                    "binding_trust": "AUTHORITATIVE",
                })

                owners.extend(entity.owners)
                if entity.quality:
                    quality.append({"urn": entity.urn, **entity.quality})

                lineage_paths.extend(neighborhood.lineage_paths)

                for d in neighborhood.downstream:
                    assets.append({
                        "urn": d.urn,
                        "type": d.entity_type,
                        "criticality": d.criticality,
                        "distance": 1,
                        "binding_trust": "AUTHORITATIVE",
                    })

            except KeyError:
                continue

        return DataHubImpact(
            assets=assets,
            lineage_paths=lineage_paths,
            owners=owners,
            quality=quality,
        )

    def _extract_risk_features(
        self,
        change_summary: dict,
        code_impact: dict,
        datahub_impact: DataHubImpact,
        bindings: list[AssetBinding],
    ) -> dict:
        features: dict[str, Any] = {}

        features["symbols_changed"] = len(change_summary.get("symbols", []))
        features["semantic_deltas"] = len(change_summary.get("semantic_deltas", []))
        features["entry_points"] = len(change_summary.get("entry_points", []))

        features["call_paths"] = len(code_impact.get("call_paths", []))
        features["unknown_resolution_count"] = code_impact.get("unknown_resolution_count", 0)

        features["authoritative_bindings"] = sum(1 for b in bindings if b.is_authoritative)
        features["discovered_bindings"] = sum(1 for b in bindings if not b.is_authoritative)
        features["downstream_assets"] = len(datahub_impact.assets)
        features["lineage_paths"] = len(datahub_impact.lineage_paths)
        features["max_criticality"] = max(
            (a.get("criticality", 0) for a in datahub_impact.assets),
            default=0.0,
        )

        tier0 = any(
            "tier0" in a.get("tags", []) or "regulated" in a.get("tags", [])
            for a in datahub_impact.assets
        )
        features["has_tier0_or_regulated"] = tier0

        features["has_payment"] = any(
            "payment" in a.get("urn", "").lower()
            for a in datahub_impact.assets
        )

        return features

    def _redact(
        self,
        source_content: dict[str, str],
        datahub_impact: DataHubImpact,
    ) -> RedactionManifest:
        secret_count = 0
        pii_count = 0
        restricted_removed = 0

        for content in source_content.values():
            lower = content.lower()
            for pattern in SECRET_PATTERNS:
                secret_count += lower.count(pattern)

        filtered_assets: list[dict] = []
        for asset in datahub_impact.assets:
            tags = asset.get("tags", [])
            if "restricted" in tags and "finance" in tags:
                restricted_removed += 1
                continue
            filtered_assets.append(asset)

        if restricted_removed:
            datahub_impact.assets = filtered_assets

        return RedactionManifest(
            secret_count=secret_count,
            restricted_assets_removed=restricted_removed,
            pii_fields_redacted=pii_count,
        )

    def _enforce_token_budget(self, bundle: EvidenceBundle) -> EvidenceBundle:
        estimated_tokens = len(json.dumps(bundle.model_dump(), default=str)) // 4

        if estimated_tokens <= self._token_ceiling:
            return bundle

        if len(bundle.datahub_impact.assets) > 20:
            bundle.datahub_impact.assets = sorted(
                bundle.datahub_impact.assets,
                key=lambda a: a.get("criticality", 0),
                reverse=True,
            )[:20]

        if len(bundle.datahub_impact.lineage_paths) > 50:
            bundle.datahub_impact.lineage_paths = bundle.datahub_impact.lineage_paths[:50]

        return bundle
