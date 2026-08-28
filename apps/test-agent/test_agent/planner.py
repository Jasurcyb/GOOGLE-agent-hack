from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MECHANISM_TEST_MATRIX: dict[str, dict[str, Any]] = {
    "contract_mismatch": {
        "min_test": "unit_test",
        "framework": "pytest",
        "escalate_when": "public_interface_or_serialization_change",
        "escalation_test": "integration_test",
    },
    "null_format_change": {
        "min_test": "unit_test",
        "framework": "pytest",
        "escalate_when": "downstream_consumer",
        "escalation_test": "contract_test",
    },
    "fan_out": {
        "min_test": "integration_test",
        "framework": "pytest",
        "escalate_when": "datajob_or_kafka_edge",
        "escalation_test": "containerized_integration_test",
    },
    "stale_feature": {
        "min_test": "feature_schema_test",
        "framework": "pytest",
        "escalate_when": "active_model_deployment_downstream",
        "escalation_test": "inference_regression_test",
    },
    "consumer_compatibility": {
        "min_test": "contract_test",
        "framework": "pytest",
        "escalate_when": "public_consumers_or_auth_flow",
        "escalation_test": "api_contract_test",
    },
    "sql_transformation": {
        "min_test": "dbt_schema_test",
        "framework": "dbt",
        "escalate_when": "column_level_lineage_or_quality_contract",
        "escalation_test": "great_expectations_expectation",
    },
    "pipeline_job": {
        "min_test": "containerized_integration_test",
        "framework": "pytest",
        "escalate_when": "datajob_airflow_kafka_edge",
        "escalation_test": "containerized_integration_test",
    },
    "ui_path": {
        "min_test": "playwright_smoke_test",
        "framework": "playwright",
        "escalate_when": "high_usage_dashboard_or_customer_flow",
        "escalation_test": "playwright_regression_test",
    },
    "ml_feature": {
        "min_test": "feature_schema_test",
        "framework": "pytest",
        "escalate_when": "active_model_deployment_downstream",
        "escalation_test": "drift_inference_test",
    },
    "pure_behavior": {
        "min_test": "unit_test",
        "framework": "pytest",
        "escalate_when": "public_interface_or_serialization_change",
        "escalation_test": "integration_test",
    },
}

DEFAULT_MECHANISM = {
    "min_test": "unit_test",
    "framework": "pytest",
    "escalate_when": "always",
    "escalation_test": "integration_test",
}


@dataclass
class TestPlan:
    kind: str
    framework: str
    title: str
    body: str
    target_path: str
    priority: int
    assertions: list[str]
    negative_case: str
    mock_boundaries: list[str]
    traceability_id: str
    setup: str = ""
    approval_required: bool = True


class TestPlanner:
    """Maps verified hypotheses to the narrowest runnable tests."""

    def plan_tests(
        self,
        hypotheses: list[dict],
        affected_assets: list[dict],
        language: str = "python",
    ) -> list[TestPlan]:
        plans: list[TestPlan] = []

        for i, hyp in enumerate(hypotheses):
            if hyp.get("verification_status") == "UNVERIFIED":
                continue

            mechanism = hyp.get("mechanism", "pure_behavior")
            matrix_entry = MECHANISM_TEST_MATRIX.get(mechanism, DEFAULT_MECHANISM)

            test_kind = matrix_entry["min_test"]
            framework = matrix_entry["framework"]

            impacted_urns = hyp.get("impacted_urns", [])
            evidence_refs = hyp.get("evidence_refs", [])
            test_ids = hyp.get("recommended_test_ids", [])

            title = self._make_title(mechanism, impacted_urns, i)
            target_path = self._make_target_path(test_ids, language)

            plan = TestPlan(
                kind=test_kind,
                framework=framework,
                title=title,
                body=self._make_body(mechanism, evidence_refs, impacted_urns),
                target_path=target_path,
                priority=i + 1,
                assertions=self._make_assertions(mechanism, evidence_refs),
                negative_case=self._make_negative_case(mechanism),
                mock_boundaries=self._make_mock_boundaries(impacted_urns),
                traceability_id=f"rec_{i+1:03d}",
                setup=self._make_setup(framework),
                approval_required=True,
            )
            plans.append(plan)

            if self._should_escalate(mechanism, affected_assets, matrix_entry):
                escalation = matrix_entry["escalation_test"]
                esc_framework = self._escalation_framework(escalation)
                plans.append(TestPlan(
                    kind=escalation,
                    framework=esc_framework,
                    title=f"[ESCALATION] {title}",
                    body=f"Escalation test for {mechanism}: {matrix_entry['escalate_when']}",
                    target_path=target_path,
                    priority=i + 1,
                    assertions=plan.assertions,
                    negative_case=plan.negative_case,
                    mock_boundaries=plan.mock_boundaries,
                    traceability_id=f"rec_{i+1:03d}_esc",
                    setup=plan.setup,
                    approval_required=True,
                ))

        return self._rank_plans(plans)

    def _make_title(self, mechanism: str, urns: list[str], idx: int) -> str:
        urn_part = urns[0].split(":")[-1] if urns else "affected asset"
        return f"Test {mechanism} for {urn_part}"

    def _make_target_path(self, test_ids: list[str], language: str) -> str:
        if test_ids:
            return f"tests/test_regression.py::{'::'.join(test_ids)}"
        ext = "py" if language == "python" else "ts"
        return f"tests/test_regression.{ext}"

    def _make_body(self, mechanism: str, refs: list[str], urns: list[str]) -> str:
        ref_str = ", ".join(refs[:3]) if refs else "no evidence refs"
        urn_str = urns[0] if urns else "unknown asset"
        return f"Verify that {mechanism} does not affect {urn_str}. Evidence: {ref_str}"

    def _make_assertions(self, mechanism: str, refs: list[str]) -> list[str]:
        base = ["result matches expected behavior"]
        if "contract" in mechanism:
            base.append("response schema matches contract")
        if "null" in mechanism:
            base.append("null values handled correctly")
        if "sql" in mechanism:
            base.append("column types match schema")
        if "fan_out" in mechanism:
            base.append("all downstream consumers receive correct data")
        return base

    def _make_negative_case(self, mechanism: str) -> str:
        cases = {
            "contract_mismatch": "invalid input should raise ValueError",
            "null_format_change": "null input should be handled gracefully",
            "fan_out": "missing downstream should not cause silent failure",
            "stale_feature": "feature schema mismatch should be detected",
            "consumer_compatibility": "incompatible consumer should get clear error",
            "sql_transformation": "NULL aggregation should produce expected result",
            "ml_feature": "drift detection should trigger on stale feature",
            "ui_path": "error state should display user-friendly message",
        }
        return cases.get(mechanism, "edge case input should be rejected")

    def _make_mock_boundaries(self, urns: list[str]) -> list[str]:
        return [f"mock {urn}" for urn in urns[:3]]

    def _make_setup(self, framework: str) -> str:
        setups = {
            "pytest": "@pytest.fixture",
            "dbt": "dbt run --models <model>",
            "playwright": "page = await browser.new_page()",
            "great_expectations": "expectation_suite = ExpectationSuite(...)",
        }
        return setups.get(framework, "")

    def _should_escalate(
        self,
        mechanism: str,
        affected_assets: list[dict],
        matrix_entry: dict,
    ) -> bool:
        escalate_when = matrix_entry.get("escalate_when", "")
        if escalate_when == "always":
            return True

        for asset in affected_assets:
            asset_type = asset.get("type", "").upper()
            tags = asset.get("tags", [])

            if "public" in escalate_when and asset_type in ("API", "SERVICE"):
                return True
            if "datajob" in escalate_when.lower() and asset_type == "DATA_JOB":
                return True
            if "kafka" in escalate_when.lower() and "kafka" in asset.get("urn", "").lower():
                return True
            if "model_deployment" in escalate_when.lower() and asset_type == "ML_MODEL":
                return True
            if "column_level" in escalate_when.lower() and asset.get("column_lineage"):
                return True
            if "dashboard" in escalate_when.lower() and asset_type == "DASHBOARD":
                return True
            if "quality_contract" in escalate_when.lower() and asset.get("quality"):
                return True

        return False

    def _escalation_framework(self, escalation_type: str) -> str:
        frameworks = {
            "integration_test": "pytest",
            "contract_test": "pytest",
            "api_contract_test": "pytest",
            "containerized_integration_test": "pytest",
            "great_expectations_expectation": "great_expectations",
            "playwright_regression_test": "playwright",
            "drift_inference_test": "pytest",
            "inference_regression_test": "pytest",
        }
        return frameworks.get(escalation_type, "pytest")

    def _rank_plans(self, plans: list[TestPlan]) -> list[TestPlan]:
        def sort_key(p: TestPlan) -> tuple:
            coverage_weight = {"unit_test": 3, "contract_test": 4, "integration_test": 5,
                               "dbt_schema_test": 4, "playwright_smoke_test": 3,
                               "containerized_integration_test": 6,
                               "feature_schema_test": 4, "great_expectations_expectation": 5}
            return (coverage_weight.get(p.kind, 3), -p.priority)

        return sorted(plans, key=sort_key, reverse=True)
