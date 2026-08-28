from __future__ import annotations

import pytest

from impact_analyzer.analyzer import ImpactAnalyzer


class TestImpactAnalyzer:
    def test_empty_analysis(self):
        analyzer = ImpactAnalyzer()
        result = analyzer.analyze("run-1", changed_symbols=[])
        assert result.node_count == 0
        assert result.blast_radius_score == 0.0

    def test_simple_code_to_asset(self):
        analyzer = ImpactAnalyzer()
        result = analyzer.analyze(
            "run-1",
            changed_symbols=["src.parser.parse_amount"],
            datahub_bindings=[
                {
                    "symbol_id": "src.parser.parse_amount",
                    "datahub_urn": "urn:li:dataset:payment_events",
                    "entity_type": "DATASET",
                    "criticality": 1.0,
                }
            ],
        )
        assert result.node_count >= 2
        assert result.weighted_downstream_assets > 0

    def test_blast_radius_capped_at_20(self):
        analyzer = ImpactAnalyzer()

        bindings = [
            {
                "symbol_id": f"symbol_{i}",
                "datahub_urn": f"urn:li:dataset:asset_{i}",
                "entity_type": "DASHBOARD",
                "criticality": 0.5,
            }
            for i in range(100)
        ]

        result = analyzer.analyze(
            "run-1",
            changed_symbols=[f"symbol_{i}" for i in range(100)],
            datahub_bindings=bindings,
        )
        assert result.blast_radius_score <= 20.0

    def test_lineage_traversal(self):
        analyzer = ImpactAnalyzer()
        result = analyzer.analyze(
            "run-1",
            changed_symbols=["src.parser"],
            datahub_bindings=[
                {"symbol_id": "src.parser", "datahub_urn": "urn:li:dataset:a", "entity_type": "DATASET"},
            ],
            datahub_lineage=[
                {"from": "urn:li:dataset:a", "to": "urn:li:dataset:b"},
                {"from": "urn:li:dataset:b", "to": "urn:li:dashboard:c"},
            ],
        )
        assert result.node_count >= 3
        assert result.edge_count >= 2
