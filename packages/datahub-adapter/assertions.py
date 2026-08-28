from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AssertionCandidate:
    """A proposed data-quality assertion that requires owner approval before enforcement."""
    dataset_urn: str
    assertion_type: str
    definition: dict[str, Any]
    status: str = "PROPOSED"
    title: str = ""
    description: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    requires_owner_approval: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_urn": self.dataset_urn,
            "assertion_type": self.assertion_type,
            "definition": self.definition,
            "status": self.status,
            "title": self.title,
            "description": self.description,
            "evidence_refs": self.evidence_refs,
            "requires_owner_approval": self.requires_owner_approval,
        }


ASSERTION_TEMPLATES: dict[str, dict[str, Any]] = {
    "NON_NULL": {
        "field": "column_name",
        "description": "Asserts that a column is never null",
        "template": {"operator": "IS_NOT_NULL", "column": "{column}"},
    },
    "ACCEPTED_RANGE": {
        "field": "column_name",
        "description": "Asserts that values fall within an accepted range",
        "template": {"operator": "BETWEEN", "column": "{column}", "min": "{min_val}", "max": "{max_val}"},
    },
    "SCHEMA_COMPATIBILITY": {
        "field": "schema_version",
        "description": "Asserts that schema changes are backward-compatible",
        "template": {"operator": "SCHEMA_MATCH", "expected_fields": "{expected_fields}"},
    },
    "FRESHNESS": {
        "field": "max_age_hours",
        "description": "Asserts that data is fresh within a threshold",
        "template": {"operator": "FRESHNESS_WITHIN", "max_age_hours": "{max_age_hours}"},
    },
    "UNIQUENESS": {
        "field": "column_name",
        "description": "Asserts that a column has unique values",
        "template": {"operator": "IS_UNIQUE", "column": "{column}"},
    },
    "REFERENTIAL_INTEGRITY": {
        "field": "foreign_key",
        "description": "Asserts referential integrity between datasets",
        "template": {"operator": "FK_EXISTS", "source_column": "{column}", "target_urn": "{target_urn}"},
    },
}


def create_assertion_candidates(
    affected_assets: list[dict],
    hypotheses: list[dict],
) -> list[AssertionCandidate]:
    """Generate assertion candidates from verified data contract hazards."""
    candidates: list[AssertionCandidate] = []

    for hyp in hypotheses:
        if hyp.get("verification_status") == "UNVERIFIED":
            continue

        mechanism = hyp.get("mechanism", "")
        impacted_urns = hyp.get("impacted_urns", [])
        evidence_refs = hyp.get("evidence_refs", [])

        for urn in impacted_urns:
            asset = next((a for a in affected_assets if a.get("urn") == urn), None)
            if asset is None:
                continue

            asset_type = asset.get("type", "").upper()

            if "null" in mechanism or "format" in mechanism:
                candidates.append(AssertionCandidate(
                    dataset_urn=urn,
                    assertion_type="NON_NULL",
                    definition={"operator": "IS_NOT_NULL", "column": "amount"},
                    title=f"Non-null assertion for {urn.split(':')[-1]}",
                    description="Asserts that critical columns are never null after transformation",
                    evidence_refs=evidence_refs,
                ))

            if "contract" in mechanism or "schema" in mechanism:
                candidates.append(AssertionCandidate(
                    dataset_urn=urn,
                    assertion_type="SCHEMA_COMPATIBILITY",
                    definition={"operator": "SCHEMA_MATCH", "expected_fields": asset.get("schema_columns", [])},
                    title=f"Schema compatibility for {urn.split(':')[-1]}",
                    description="Asserts that schema changes remain backward-compatible",
                    evidence_refs=evidence_refs,
                ))

            if "sql" in mechanism or "transformation" in mechanism:
                candidates.append(AssertionCandidate(
                    dataset_urn=urn,
                    assertion_type="ACCEPTED_RANGE",
                    definition={"operator": "BETWEEN", "column": "amount", "min": -1000000, "max": 1000000},
                    title=f"Accepted range for {urn.split(':')[-1]}",
                    description="Asserts that payment amounts fall within accepted business range",
                    evidence_refs=evidence_refs,
                ))

            if "freshness" in mechanism or "stale" in mechanism:
                candidates.append(AssertionCandidate(
                    dataset_urn=urn,
                    assertion_type="FRESHNESS",
                    definition={"operator": "FRESHNESS_WITHIN", "max_age_hours": 6},
                    title=f"Freshness assertion for {urn.split(':')[-1]}",
                    description="Asserts that data is refreshed within the expected SLA",
                    evidence_refs=evidence_refs,
                ))

    return candidates


def get_assertion_template(assertion_type: str) -> dict[str, Any] | None:
    return ASSERTION_TEMPLATES.get(assertion_type)
