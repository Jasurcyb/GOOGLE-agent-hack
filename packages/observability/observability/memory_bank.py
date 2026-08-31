from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger("observability.memory_bank")


class CloudMemoryBank:
    """Enterprise Memory Bank for persistent cross-session context and agent telemetry.
    Supports Google Cloud Firestore with zero-configuration in-memory/local JSON fallback.
    """

    def __init__(
        self,
        collection_name: str = "agent_memory_bank",
        storage_file: str | None = None,
    ) -> None:
        self.collection_name = collection_name
        self.storage_file = storage_file or "memory_bank_store.json"
        self._local_memory: dict[str, dict[str, Any]] = {}
        self._firestore_db: Any = None

        # Attempt Google Cloud Firestore client if environment configured
        if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or os.environ.get("FIRESTORE_EMULATOR_HOST"):
            try:
                from google.cloud import firestore
                self._firestore_db = firestore.AsyncClient()
                logger.info("Connected to Google Cloud Firestore for Memory Bank.")
            except Exception as e:
                logger.warning("Firestore client unavailable, using fallback storage: %s", e)
                self._firestore_db = None

        self._load_local()

    def _load_local(self) -> None:
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    self._local_memory = json.load(f)
            except Exception:
                self._local_memory = {}

    def _save_local(self) -> None:
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(self._local_memory, f, indent=2, default=str)
        except Exception as e:
            logger.warning("Could not persist local memory bank: %s", e)

    async def save_session_memory(
        self,
        session_id: str,
        agent_type: str,
        context: dict[str, Any],
        reasoning_trace: list[dict[str, Any]] | None = None,
    ) -> str:
        record = {
            "session_id": session_id,
            "agent_type": agent_type,
            "timestamp": time.time(),
            "context": context,
            "reasoning_trace": reasoning_trace or [],
        }

        if self._firestore_db is not None:
            try:
                doc_ref = self._firestore_db.collection(self.collection_name).document(session_id)
                await doc_ref.set(record)
                # Keep a local mirror so cross-session recall works even if a Firestore read hiccups
                self._local_memory[session_id] = record
                self._save_local()
                return f"firestore://{self.collection_name}/{session_id}"
            except Exception as e:
                logger.warning("Firestore write failed, saving locally: %s", e)

        self._local_memory[session_id] = record
        self._save_local()
        return f"local://memory_bank/{session_id}"

    async def get_session_memory(self, session_id: str) -> dict[str, Any] | None:
        if self._firestore_db is not None:
            try:
                doc_ref = self._firestore_db.collection(self.collection_name).document(session_id)
                doc = await doc_ref.get()
                if doc.exists:
                    return doc.to_dict()
            except Exception as e:
                logger.warning("Firestore read failed, checking local memory: %s", e)

        return self._local_memory.get(session_id)

    async def search_relevant_past_regressions(
        self,
        query_terms: list[str],
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []

        if self._firestore_db is not None:
            try:
                docs = self._firestore_db.collection(self.collection_name).limit(200).stream()
                async for doc in docs:
                    item = doc.to_dict()
                    if item:
                        records.append(item)
            except Exception as e:
                logger.warning("Firestore search failed, falling back to local memory: %s", e)

        for item in self._local_memory.values():
            if item not in records:
                records.append(item)

        results = []
        for item in records:
            content_str = json.dumps(item, default=str).lower()
            matches = sum(1 for term in query_terms if term.lower() in content_str)
            if matches > 0:
                results.append((matches, item))

        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:limit]]
