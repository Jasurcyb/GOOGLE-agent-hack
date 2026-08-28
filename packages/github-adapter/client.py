from __future__ import annotations

import time
from typing import Any

import httpx

GITHUB_API_BASE = "https://api.github.com"


class GitHubAppClient:
    def __init__(
        self,
        app_id: str,
        private_key: str,
        installation_id: str,
    ) -> None:
        self._app_id = app_id
        self._private_key = private_key
        self._installation_id = installation_id
        self._token: str | None = None
        self._token_expires: float = 0.0
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=GITHUB_API_BASE)
        return self._client

    async def _get_installation_token(self) -> str:
        if self._token and time.time() < self._token_expires - 60:
            return self._token

        client = await self._ensure_client()
        jwt = self._generate_app_jwt()
        resp = await client.post(
            f"/app/installations/{self._installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {jwt}",
                "Accept": "application/vnd.github+json",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["token"]
        self._token_expires = time.time() + 3600
        return self._token

    def _generate_app_jwt(self) -> str:
        import jwt as pyjwt

        now = int(time.time())
        payload = {"iat": now - 60, "exp": now + 600, "iss": self._app_id}
        return pyjwt.encode(payload, self._private_key, algorithm="RS256")

    async def _headers(self) -> dict[str, str]:
        token = await self._get_installation_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def create_check_run(
        self,
        repo: str,
        head_sha: str,
        name: str,
        status: str = "in_progress",
        conclusion: str | None = None,
        summary: str = "",
    ) -> dict[str, Any]:
        client = await self._ensure_client()
        body: dict[str, Any] = {
            "name": name,
            "head_sha": head_sha,
            "status": status,
            "output": {"title": name, "summary": summary},
        }
        if conclusion:
            body["conclusion"] = conclusion
        resp = await client.post(
            f"/repos/{repo}/check-runs",
            json=body,
            headers=await self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def upsert_comment(
        self,
        repo: str,
        pr_number: int,
        marker: str,
        body: str,
    ) -> dict[str, Any]:
        client = await self._ensure_client()
        headers = await self._headers()

        list_resp = await client.get(
            f"/repos/{repo}/issues/{pr_number}/comments",
            headers=headers,
        )
        list_resp.raise_for_status()
        comments = list_resp.json()

        marker_tag = f"<!-- {marker} -->"
        existing = None
        for c in comments:
            if marker_tag in c.get("body", ""):
                existing = c
                break

        full_body = f"{marker_tag}\n{body}"

        if existing:
            resp = await client.patch(
                f"/repos/{repo}/issues/comments/{existing['id']}",
                json={"body": full_body},
                headers=headers,
            )
        else:
            resp = await client.post(
                f"/repos/{repo}/issues/{pr_number}/comments",
                json={"body": full_body},
                headers=headers,
            )
        resp.raise_for_status()
        return resp.json()

    async def add_labels(
        self,
        repo: str,
        pr_number: int,
        labels: list[str],
    ) -> list[dict[str, Any]]:
        client = await self._ensure_client()
        resp = await client.post(
            f"/repos/{repo}/issues/{pr_number}/labels",
            json={"labels": labels},
            headers=await self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
