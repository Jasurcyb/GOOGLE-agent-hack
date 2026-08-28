from __future__ import annotations

import json
import logging
import os
from typing import Any

from datahub_adapter.graph_port import DataHubGraphPort
from datahub_adapter.live_context import MCPDataHubGraphPort
from datahub_adapter.stub_graph import StubDataHubGraphPort

logger = logging.getLogger("publisher.datahub")


COMMIT_MARKER = "<!-- regression-hunter:repo:pr -->"


class DataHubPublisher:
    """Handles DataHub write-back: report document, assessment entity, properties, tags, assertions."""

    def __init__(self, graph_port: DataHubGraphPort | None = None) -> None:
        self._port = graph_port
        if self._port is None:
            if os.environ.get("DATAHUB_MCP_URL"):
                self._port = MCPDataHubGraphPort(
                    os.environ["DATAHUB_MCP_URL"], os.environ.get("DATAHUB_TOKEN")
                )
            else:
                self._port = StubDataHubGraphPort()

    async def publish(
        self,
        run_id: str,
        repo: str,
        pr_number: int,
        head_sha: str,
        assessment: dict[str, Any],
    ) -> list[dict[str, Any]]:
        deliveries: list[dict[str, Any]] = []
        report_urn: str | None = None
        assessment_urn: str | None = None

        try:
            report_urn = await self._save_report_document(run_id, repo, pr_number, head_sha, assessment)
            deliveries.append({"target": "datahub_report", "status": "published", "urn": report_urn})
        except Exception as e:
            logger.error("Failed to save report document: %s", e)
            deliveries.append({"target": "datahub_report", "status": "failed", "error": str(e)})

        try:
            assessment_urn = await self._create_assessment_entity(run_id, assessment, report_urn)
            deliveries.append({"target": "datahub_assessment", "status": "published", "urn": assessment_urn})
        except Exception as e:
            logger.error("Failed to create assessment entity: %s", e)
            deliveries.append({"target": "datahub_assessment", "status": "failed", "error": str(e)})

        try:
            await self._attach_structured_properties(assessment, assessment_urn)
            deliveries.append({"target": "datahub_properties", "status": "published"})
        except Exception as e:
            logger.error("Failed to attach properties: %s", e)
            deliveries.append({"target": "datahub_properties", "status": "failed", "error": str(e)})

        try:
            await self._add_at_risk_tags(assessment)
            deliveries.append({"target": "datahub_tags", "status": "published"})
        except Exception as e:
            logger.error("Failed to add tags: %s", e)
            deliveries.append({"target": "datahub_tags", "status": "failed", "error": str(e)})

        try:
            await self._create_assertion_candidates(assessment)
            deliveries.append({"target": "datahub_assertions", "status": "published"})
        except Exception as e:
            logger.error("Failed to create assertions: %s", e)
            deliveries.append({"target": "datahub_assertions", "status": "failed", "error": str(e)})

        return deliveries

    async def _save_report_document(
        self,
        run_id: str,
        repo: str,
        pr_number: int,
        head_sha: str,
        assessment: dict[str, Any],
    ) -> str:
        doc_id = f"Regression Hunter/{repo}/PR-{pr_number}/{head_sha[:8]}"
        content = self._build_report_markdown(run_id, repo, pr_number, head_sha, assessment)
        return await self._port.save_document(
            parent_urn=f"urn:li:container:{repo}",
            document_id=doc_id,
            content=content,
        )

    def _build_report_markdown(
        self,
        run_id: str,
        repo: str,
        pr_number: int,
        head_sha: str,
        assessment: dict[str, Any],
    ) -> str:
        lines = [
            f"# Regression Hunter Report — {repo}#{pr_number}",
            "",
            f"**Run ID:** {run_id}",
            f"**SHA:** {head_sha[:8]}",
            f"**Risk Score:** {assessment.get('risk_score', 0)}/100",
            f"**Risk Level:** {assessment.get('risk_level', 'unknown').upper()}",
            f"**Confidence:** {assessment.get('confidence', 0)}%",
            f"**Regression Probability:** {assessment.get('regression_probability', 0):.1%}",
            "",
            "## Affected Assets",
            "",
        ]

        for asset in assessment.get("affected_assets", [])[:10]:
            lines.append(f"- **{asset.get('urn', 'unknown')}** (distance: {asset.get('distance', '?')})")
            lines.append(f"  Impact: {asset.get('impact', 'unknown')}")

        lines.extend(["", "## Recommended Tests", ""])
        for test in assessment.get("recommended_tests", [])[:10]:
            lines.append(f"- [{test.get('kind', 'test')}] {test.get('title', 'untitled')}")
            lines.append(f"  Path: `{test.get('target_path', 'N/A')}`")

        lines.extend(["", "## Review Summary", "", assessment.get("review_summary", "N/A")])
        lines.extend(["", "## Business Impact", "", assessment.get("business_impact", "N/A")])
        lines.extend(["", "## Root Cause", "", assessment.get("root_cause", "N/A")])

        return "\n".join(lines)

    async def _create_assessment_entity(
        self,
        run_id: str,
        assessment: dict[str, Any],
        report_urn: str | None,
    ) -> str:
        properties = {
            "run_id": run_id,
            "risk_score": assessment.get("risk_score", 0),
            "risk_level": assessment.get("risk_level", "unknown"),
            "confidence": assessment.get("confidence", 0),
            "policy_version": assessment.get("model_version", "v1"),
        }
        if report_urn:
            properties["report_urn"] = report_urn
        return await self._port.create_custom_entity(
            entity_type="RegressionAssessment",
            properties=properties,
        )

    async def _attach_structured_properties(
        self,
        assessment: dict[str, Any],
        assessment_urn: str | None,
    ) -> None:
        for asset in assessment.get("affected_assets", []):
            urn = asset.get("urn", "")
            if urn and assessment_urn:
                await self._port.attach_structured_properties(urn, {
                    "regression_hunter.latest_risk_score": assessment.get("risk_score", 0),
                    "regression_hunter.latest_assessment_urn": assessment_urn,
                    "regression_hunter.open_recommendation_count": len(assessment.get("recommended_tests", [])),
                })

    async def _add_at_risk_tags(self, assessment: dict[str, Any]) -> None:
        risk_level = assessment.get("risk_level", "low")
        if risk_level in ("high", "critical"):
            for asset in assessment.get("affected_assets", []):
                urn = asset.get("urn", "")
                if urn and asset.get("binding_trust") == "AUTHORITATIVE":
                    await self._port.add_tag(urn, "RegressionHunter:AtRisk")

    async def _create_assertion_candidates(self, assessment: dict[str, Any]) -> None:
        for test in assessment.get("recommended_tests", []):
            if test.get("kind") in ("dbt_schema_test", "great_expectations_expectation"):
                target_urn = test.get("target_urn", "")
                if target_urn:
                    await self._port.create_assertion(
                        dataset_urn=target_urn,
                        assertion_type="SCHEMA_COMPATIBILITY",
                        definition={"test": test.get("title", ""), "assertions": test.get("assertions", [])},
                        status="PROPOSED",
                    )
