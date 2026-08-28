from __future__ import annotations

from enum import StrEnum
from dataclasses import dataclass, field


class AgentState(StrEnum):
    COLLECTING = "collecting"
    GROUNDED = "grounded"
    SCORED = "scored"
    RECOMMENDING = "recommending"
    PUBLISHED = "published"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass
class AgentConfig:
    max_tool_calls: int = 12
    max_lineage_expansions: int = 3
    token_ceiling: int = 80000
    wall_clock_budget_seconds: int = 300

    tool_call_count: int = 0
    lineage_expansions: int = 0
    tokens_used: int = 0
    state: AgentState = AgentState.COLLECTING

    def can_call_tool(self) -> bool:
        return self.tool_call_count < self.max_tool_calls

    def can_expand_lineage(self) -> bool:
        return self.lineage_expansions < self.max_lineage_expansions

    def has_token_budget(self, estimated: int = 0) -> bool:
        return self.tokens_used + estimated < self.token_ceiling

    def transition(self, new_state: AgentState) -> None:
        valid = {
            AgentState.COLLECTING: {AgentState.GROUNDED, AgentState.FAILED},
            AgentState.GROUNDED: {AgentState.SCORED, AgentState.PARTIAL, AgentState.FAILED},
            AgentState.SCORED: {AgentState.RECOMMENDING, AgentState.PARTIAL, AgentState.FAILED},
            AgentState.RECOMMENDING: {AgentState.PUBLISHED, AgentState.PARTIAL, AgentState.FAILED},
        }
        if new_state not in valid.get(self.state, set()):
            raise ValueError(f"Invalid transition: {self.state} -> {new_state}")
        self.state = new_state
