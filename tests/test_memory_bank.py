import pytest
from observability.memory_bank import CloudMemoryBank


@pytest.mark.asyncio
async def test_memory_bank_save_and_retrieve(tmp_path):
    storage_file = str(tmp_path / "test_memory.json")
    bank = CloudMemoryBank(storage_file=storage_file)

    uri = await bank.save_session_memory(
        session_id="run-101",
        agent_type="reasoning_agent",
        context={"risk": "high", "pr": 42},
    )
    assert "run-101" in uri

    item = await bank.get_session_memory("run-101")
    assert item is not None
    assert item["context"]["risk"] == "high"

    results = await bank.search_relevant_past_regressions(["high"])
    assert len(results) >= 1
