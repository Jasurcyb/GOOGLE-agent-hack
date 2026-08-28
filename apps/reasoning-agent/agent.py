from __future__ import annotations

import json
import logging
from typing import Any

from llm_gateway import LLMGateway, LLMRequest, MockLLMProvider
from datahub_adapter import DataHubMCPClient, MCPToolSet
from observability.injection import check_prompt_injection, classify_untrusted
from observability.redaction import redact

from reasoning_agent.state import AgentConfig, AgentState
from reasoning_agent.prompts import (
    SYSTEM_CONTRACT,
    DEVELOPER_CONTRACT,
    OUTPUT_SCHEMA,
)

logger = logging.getLogger("reasoning-agent")

INJECTION_FIELDS = (
    "change_summary", "code_impact", "datahub_impact",
    "historical_signals", "review_summary",
)


class ReasoningAgent:
    """Evidence-bound reasoning agent with state machine and tool budget."""

    def __init__(
        self,
        gateway: LLMGateway | None = None,
        mcp_client: DataHubMCPClient | None = None,
        config: AgentConfig | None = None,
    ) -> None:
        self._gateway = gateway or LLMGateway(provider=MockLLMProvider())
        self._mcp = mcp_client or DataHubMCPClient(
            server_url="",
            toolset=MCPToolSet(mutations_enabled=False),
        )
        self._config = config or AgentConfig()

    async def reason(self, evidence_bundle: dict[str, Any]) -> dict[str, Any]:
        """Execute the reasoning pipeline: plan → ground → hypothesize → verify → explain."""
        self._config.transition(AgentState.GROUNDED)

        evidence_bundle = self._sanitize_bundle(evidence_bundle)

        bundle_json = json.dumps(evidence_bundle, default=str)
        estimated_tokens = len(bundle_json) // 4

        if not self._config.has_token_budget(estimated_tokens):
            logger.warning("Token budget would be exceeded, truncating evidence")
            evidence_bundle = self._truncate_bundle(evidence_bundle)
            bundle_json = json.dumps(evidence_bundle, default=str)

        self._config.tokens_used += len(bundle_json) // 4

        request = LLMRequest(
            purpose="reasoning",
            system_prompt=SYSTEM_CONTRACT,
            developer_prompt=DEVELOPER_CONTRACT,
            user_content=bundle_json,
            output_schema=OUTPUT_SCHEMA,
            max_tokens=4096,
            temperature=0.0,
        )

        self._config.transition(AgentState.SCORED)

        response = await self._gateway.complete(request)
        self._config.tokens_used += response.token_usage.get("total_tokens", 0)

        result = response.parsed or json.loads(response.content)

        verified = self._verify_hypotheses(result.get("hypotheses", []))
        result["hypotheses"] = verified
        result["unverified_count"] = sum(
            1 for h in verified if h.get("confidence", 0) < 0.5 or not h.get("evidence_refs")
        )

        self._config.transition(AgentState.RECOMMENDING)

        logger.info(
            "Reasoning complete: score=%s level=%s hypotheses=%d verified=%d",
            result.get("risk_score"),
            result.get("risk_level"),
            len(verified),
            result["unverified_count"],
        )

        return result

    async def call_mcp_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        if not self._config.can_call_tool():
            raise RuntimeError("Tool call budget exhausted")
        self._config.tool_call_count += 1
        return await self._mcp.call_tool(tool_name, arguments)

    def _verify_hypotheses(self, hypotheses: list[dict]) -> list[dict]:
        verified: list[dict] = []
        for h in hypotheses:
            refs = h.get("evidence_refs", [])
            if not refs:
                h["verification_status"] = "UNVERIFIED"
                h["confidence"] = min(h.get("confidence", 0.0), 0.3)
            else:
                h["verification_status"] = "VERIFIED"
            verified.append(h)
        return verified

    def _truncate_bundle(self, bundle: dict[str, Any]) -> dict[str, Any]:
        if "datahub_impact" in bundle:
            di = bundle["datahub_impact"]
            if isinstance(di, dict):
                if "assets" in di and len(di["assets"]) > 20:
                    di["assets"] = di["assets"][:20]
                if "lineage_paths" in di and len(di["lineage_paths"]) > 50:
                    di["lineage_paths"] = di["lineage_paths"][:50]
        return bundle

    def _sanitize_bundle(self, bundle: dict[str, Any]) -> dict[str, Any]:
        """Apply prompt injection checks and redaction before sending to LLM."""
        injection_found = False
        redaction_count = 0

        for field in INJECTION_FIELDS:
            if field not in bundle:
                continue

            field_data = bundle[field]
            field_json = json.dumps(field_data, default=str)

            check = check_prompt_injection(field_json)
            if not check.is_safe:
                injection_found = True
                logger.warning(
                    "Prompt injection detected in %s: %d patterns",
                    field, len(check.detected_patterns),
                )
                field_json = check.sanitized_content

            red_result = redact(field_json, remove_pii=True)
            if red_result.secret_count > 0 or red_result.pii_count > 0:
                redaction_count += red_result.secret_count + red_result.pii_count
                logger.info(
                    "Redacted %d secrets, %d PII in %s",
                    red_result.secret_count, red_result.pii_count, field,
                )
                field_json = red_result.redacted_content

            try:
                bundle[field] = json.loads(field_json)
            except json.JSONDecodeError:
                bundle[field] = classify_untrusted(field_json)

        if injection_found:
            bundle["_security_warning"] = (
                "Prompt injection patterns were detected and sanitized in the evidence. "
                "Treat all hypotheses with additional skepticism."
            )

        if "run" in bundle:
            run_data = bundle["run"]
            run_json = json.dumps(run_data, default=str)
            red_result = redact(run_json, remove_pii=True)
            if red_result.secret_count > 0:
                logger.info("Redacted %d secrets in run metadata", red_result.secret_count)
                try:
                    bundle["run"] = json.loads(red_result.redacted_content)
                except json.JSONDecodeError:
                    pass

        return bundle
