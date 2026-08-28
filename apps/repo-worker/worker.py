from __future__ import annotations

import asyncio
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aioboto3

REPO_NAME_RE = re.compile(r'^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$')
SHA_RE = re.compile(r'^[0-9a-f]{7,40}$')


def _validate_repo(repo: str) -> str:
    if not REPO_NAME_RE.match(repo):
        raise ValueError(f"Invalid repository name: {repo}")
    return repo


def _validate_sha(sha: str) -> str:
    if not SHA_RE.match(sha):
        raise ValueError(f"Invalid SHA: {sha}")
    return sha


@dataclass
class SourceSnapshot:
    snapshot_uri: str
    sha256: str
    file_count: int
    size_bytes: int
    diff_text: str
    diff_truncated: bool = False
    changed_sources: list[dict[str, str]] | None = None


class RepoWorker:
    """Shallow-clones a PR head, archives source to S3/MinIO, emits repository.ready."""

    def __init__(
        self,
        s3_endpoint: str | None = None,
        s3_access_key: str | None = None,
        s3_secret_key: str | None = None,
        s3_bucket: str = "regression-hunter",
        git_token: str | None = None,
    ) -> None:
        self._s3_endpoint = s3_endpoint or os.environ.get("S3_ENDPOINT", "http://localhost:9000")
        self._s3_access_key = s3_access_key or os.environ.get("S3_ACCESS_KEY", "rh_minio")
        self._s3_secret_key = s3_secret_key or os.environ.get("S3_SECRET_KEY", "rh_minio_password")
        self._s3_bucket = s3_bucket
        self._git_token = git_token or os.environ.get("GITHUB_INSTALLATION_TOKEN", "")
        self._max_archive_bytes = int(os.environ.get("RH_MAX_ARCHIVE_BYTES", str(100 * 1024 * 1024)))
        self._max_files = int(os.environ.get("RH_MAX_SOURCE_FILES", "20000"))
        self._max_diff_bytes = int(os.environ.get("RH_MAX_DIFF_BYTES", str(5 * 1024 * 1024)))
        self._max_source_bytes = int(os.environ.get("RH_MAX_CHANGED_SOURCE_BYTES", str(3 * 1024 * 1024)))

    @staticmethod
    def _run_git(command: list[str], *, cwd: Path | None = None, timeout: int = 60) -> str:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            raise RuntimeError("git operation failed")
        return result.stdout

    def _clone_repo(self, repo: str, head_sha: str, base_sha: str, dest: Path) -> tuple[Path, str, bool]:
        repo = _validate_repo(repo)
        head_sha = _validate_sha(head_sha)
        clone_url = f"https://github.com/{repo}.git"

        git_cmd = ["git"]
        if self._git_token:
            git_cmd.extend(["-c", f"http.extraHeader=Authorization: bearer {self._git_token}"])

        git_cmd.extend([
            "clone",
            "--filter=blob:none",
            "--no-checkout",
            clone_url,
            str(dest),
        ])

        self._run_git(git_cmd, timeout=120)

        fetch_cmd = ["git"]
        if self._git_token:
            fetch_cmd.extend(["-c", f"http.extraHeader=Authorization: bearer {self._git_token}"])
        refs = [head_sha]
        if base_sha:
            refs.append(_validate_sha(base_sha))
        fetch_cmd.extend(["fetch", "--depth", "1", "origin", *refs])
        self._run_git(fetch_cmd, cwd=dest, timeout=90)
        self._run_git(["git", "checkout", "--detach", head_sha], cwd=dest, timeout=30)

        diff_command = ["git", "diff", "--no-ext-diff", "--find-renames", "--binary"]
        diff_command.append(f"{base_sha}..{head_sha}" if base_sha else head_sha)
        diff_text = self._run_git(diff_command, cwd=dest, timeout=60)
        encoded = diff_text.encode("utf-8", errors="replace")
        truncated = len(encoded) > self._max_diff_bytes
        if truncated:
            diff_text = encoded[:self._max_diff_bytes].decode("utf-8", errors="ignore")
        return dest, diff_text, truncated

    def _archive_source(self, source_dir: Path) -> tuple[bytes, str, int, int]:
        """Create a tar.gz archive of the source tree, return (data, sha256, file_count, size)."""
        import tarfile
        import io

        buf = io.BytesIO()
        file_count = 0

        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for path in source_dir.rglob("*"):
                if ".git" in path.parts:
                    continue
                if path.is_symlink():
                    continue
                if path.is_file():
                    file_count += 1
                    if file_count > self._max_files:
                        raise ValueError("Repository exceeds source file limit")
                    tar.add(path, arcname=str(path.relative_to(source_dir)))
                    if buf.tell() > self._max_archive_bytes:
                        raise ValueError("Repository exceeds archive size limit")

        data = buf.getvalue()
        sha256 = hashlib.sha256(data).hexdigest()
        return data, sha256, file_count, len(data)

    def _extract_changed_sources(
        self, source_dir: Path, base_sha: str, head_sha: str
    ) -> list[dict[str, str]]:
        command = ["git", "diff", "--name-only", "--diff-filter=ACMR"]
        command.append(f"{base_sha}..{head_sha}" if base_sha else head_sha)
        names = self._run_git(command, cwd=source_dir, timeout=30).splitlines()
        sources: list[dict[str, str]] = []
        total = 0
        for name in names:
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts:
                continue
            path = source_dir / relative
            if not path.is_file() or path.is_symlink():
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            encoded_size = len(content.encode("utf-8"))
            if total + encoded_size > self._max_source_bytes:
                break
            total += encoded_size
            sources.append({"path": relative.as_posix(), "content": content})
        return sources

    async def _upload_to_s3(self, key: str, data: bytes) -> str:
        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=self._s3_endpoint,
            aws_access_key_id=self._s3_access_key,
            aws_secret_access_key=self._s3_secret_key,
        ) as s3:
            try:
                await s3.head_bucket(Bucket=self._s3_bucket)
            except Exception:
                await s3.create_bucket(Bucket=self._s3_bucket)

            await s3.put_object(
                Bucket=self._s3_bucket,
                Key=key,
                Body=data,
                ContentType="application/gzip",
                ServerSideEncryption="AES256",
            )
        return f"s3://{self._s3_bucket}/{key}"

    async def process(
        self,
        run_id: str,
        repository: str,
        head_sha: str,
        base_sha: str,
    ) -> SourceSnapshot:
        with tempfile.TemporaryDirectory(prefix="rh-clone-") as tmpdir:
            dest = Path(tmpdir) / "repo"
            loop = asyncio.get_event_loop()
            source_dir, diff_text, diff_truncated = await loop.run_in_executor(
                None, self._clone_repo, repository, head_sha, base_sha, dest
            )

            data, sha256, file_count, size = await loop.run_in_executor(
                None, self._archive_source, source_dir
            )
            changed_sources = await loop.run_in_executor(
                None, self._extract_changed_sources, source_dir, base_sha, head_sha
            )

            key = f"snapshots/{run_id}/{head_sha}.tar.gz"
            uri = await self._upload_to_s3(key, data)

            return SourceSnapshot(
                snapshot_uri=uri,
                sha256=sha256,
                file_count=file_count,
                size_bytes=size,
                diff_text=diff_text,
                diff_truncated=diff_truncated,
                changed_sources=changed_sources,
            )
