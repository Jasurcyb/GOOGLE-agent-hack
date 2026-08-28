from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from github_adapter import GitHubAppClient

logger = logging.getLogger("publisher.github")

COMMENT_MARKER = "<!-- regression-hunter:repo:pr -->"

RISK_LABELS = {
    "low": "regression-risk:low",
    "medium": "regression-risk:medium",
    "high": "regression-risk:high",
    "critical": "regression-risk:critical",
}


class GitHubPublisher:
    """Handles GitHub write-back: check run, labels, upserted comment."""

    def __init__(self, client: GitHubAppClient | None = None) -> None:
        self._client = client
        if self._client is None:
            app_id = os.environ.get("GITHUB_APP_ID")
            installation_id = os.environ.get("GITHUB_INSTALLATION_ID")
            private_key_path = os.environ.get("GITHUB_PRIVATE_KEY_PATH")
            if app_id and installation_id and private_key_path:
                self._client = GitHubAppClient(
                    app_id=app_id,
                    installation_id=installation_id,
                    private_key=Path(private_key_path).read_text(encoding="utf-8"),
                )

    async def publish(
        self,
        repo: str,
        pr_number: int,
        head_sha: str,
        assessment: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if self._client is None:
            logger.info("GitHubAppClient not configured — skipping GitHub write-back")
            return [{"target": "github", "status": "skipped"}]

        deliveries: list[dict[str, Any]] = []

        try:
            check = await self._create_check_run(repo, head_sha, assessment)
            deliveries.append({"target": "github_check", "status": "published", "id": check.get("id")})
        except Exception as e:
            logger.error("Failed to create check run: %s", e)
            deliveries.append({"target": "github_check", "status": "failed", "error": "internal_error"})

        try:
            labels = await self._apply_labels(repo, pr_number, assessment)
            deliveries.append({"target": "github_labels", "status": "published", "labels": labels})
        except Exception as e:
            logger.error("Failed to apply labels: %s", e)
            deliveries.append({"target": "github_labels", "status": "failed", "error": "internal_error"})

        try:
            comment = await self._upsert_comment(repo, pr_number, assessment)
            deliveries.append({"target": "github_comment", "status": "published", "id": comment.get("id")})
        except Exception as e:
            logger.error("Failed to upsert comment: %s", e)
            deliveries.append({"target": "github_comment", "status": "failed", "error": "internal_error"})

        return deliveries

    async def _create_check_run(
        self,
        repo: str,
        head_sha: str,
        assessment: dict[str, Any],
    ) -> dict[str, Any]:
        risk_level = assessment.get("risk_level", "low")
        confidence = assessment.get("confidence", 0)

        if confidence < 70:
            conclusion = "neutral"
        elif risk_level in ("high", "critical") and assessment.get("requires_human_review", True):
            conclusion = "failure"
        else:
            conclusion = "success"

        summary = self._build_check_summary(assessment)

        return await self._client.create_check_run(
            repo=repo,
            head_sha=head_sha,
            name="Regression Hunter / pre-deploy impact",
            status="completed",
            conclusion=conclusion,
            summary=summary,
        )

    def _build_check_summary(self, assessment: dict[str, Any]) -> str:
        score = assessment.get("risk_score", 0)
        level = assessment.get("risk_level", "low").upper()
        confidence = assessment.get("confidence", 0)
        assets = assessment.get("affected_assets", [])

        lines = [
            f"## Regression Hunter — Risk Assessment",
            "",
            f"| Metric | Value |",
            f"|---|---|",
            f"| Risk Score | {score}/100 |",
            f"| Risk Level | {level} |",
            f"| Confidence | {confidence}% |",
            f"| Regression Probability | {assessment.get('regression_probability', 0):.1%} |",
            f"| Requires Review | {'Yes' if assessment.get('requires_human_review') else 'No'} |",
            "",
        ]

        if assets:
            lines.append("### Top 3 Affected Assets")
            for a in assets[:3]:
                lines.append(f"- {a.get('urn', 'unknown')} — {a.get('impact', 'unknown')}")

        tests = assessment.get("recommended_tests", [])
        if tests:
            lines.append("\n### Recommended Tests")
            for t in tests[:5]:
                lines.append(f"- [{t.get('kind', 'test')}] {t.get('title', 'untitled')}")

        return "\n".join(lines)

    async def _apply_labels(
        self,
        repo: str,
        pr_number: int,
        assessment: dict[str, Any],
    ) -> list[str]:
        risk_level = assessment.get("risk_level", "low")
        labels: list[str] = []

        risk_label = RISK_LABELS.get(risk_level, RISK_LABELS["low"])
        labels.append(risk_label)

        if assessment.get("confidence", 100) < 70:
            labels.append("regression-needs-review")

        await self._client.add_labels(repo, pr_number, labels)
        return labels

    async def _upsert_comment(
        self,
        repo: str,
        pr_number: int,
        assessment: dict[str, Any],
    ) -> dict[str, Any]:
        body = self._build_comment_body(assessment)
        return await self._client.upsert_comment(
            repo=repo,
            pr_number=pr_number,
            marker="regression-hunter:repo:pr",
            body=body,
        )

    def _build_comment_body(self, assessment: dict[str, Any]) -> str:
        score = assessment.get("risk_score", 0)
        level = assessment.get("risk_level", "low").upper()
        confidence = assessment.get("confidence", 0)

        def _sanitize(val: Any) -> str:
            import html
            return html.escape(str(val))

        lines = [
            f"## Regression Hunter AI — Risk Assessment",
            "",
            f"**Score:** {score}/100 | **Level:** {level} | **Confidence:** {confidence}%",
            "",
        ]

        if assessment.get("requires_human_review"):
            lines.append("> Requires human review before merge.")
            lines.append("")

        assets = assessment.get("affected_assets", [])
        if assets:
            lines.append("### Highest-Impact Assets")
            for a in assets[:3]:
                urn = _sanitize(a.get("urn", "unknown"))
                impact = _sanitize(a.get("impact", "unknown"))
                distance = _sanitize(a.get("distance", "?"))
                refs = ", ".join(_sanitize(r) for r in a.get("evidence_refs", [])[:2])
                lines.append(f"- **{urn}** (distance: {distance})")
                lines.append(f"  Impact: {impact}")
                if refs:
                    lines.append(f"  Evidence: {refs}")

        tests = assessment.get("recommended_tests", [])
        if tests:
            lines.append("\n### Recommended Tests")
            for t in tests[:5]:
                kind = _sanitize(t.get("kind", "test"))
                title = _sanitize(t.get("title", "untitled"))
                target_path = _sanitize(t.get("target_path", "N/A"))
                t_body = _sanitize(t.get("body", ""))
                lines.append(f"- **[{kind}]** {title}")
                lines.append(f"  `Path: {target_path}`")
                if t_body:
                    lines.append(f"  {t_body}")

        if not assets and not tests:
            lines.append("No verified business impact detected for this change.")

        lines.extend(["", "---", f"*Powered by Regression Hunter AI*"])

        return "\n".join(lines)
