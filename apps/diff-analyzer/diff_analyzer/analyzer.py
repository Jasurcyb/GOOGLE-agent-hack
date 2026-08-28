from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class FileChangeType(StrEnum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass
class FileDelta:
    path: str
    change_type: FileChangeType
    added_lines: int = 0
    deleted_lines: int = 0
    old_path: str | None = None
    similarity_index: float = 0.0
    is_binary: bool = False
    language: str | None = None
    added_line_ranges: list[tuple[int, int]] = field(default_factory=list)
    deleted_line_ranges: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class DiffResult:
    run_id: str
    files: list[FileDelta]
    total_added: int
    total_deleted: int
    renames: int
    new_files: int
    deleted_files: int


def detect_language(path: str) -> str | None:
    ext_map = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".java": "java",
        ".go": "go",
        ".cs": "csharp",
        ".sql": "sql",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".xml": "xml",
    }
    ext = Path(path).suffix.lower()
    return ext_map.get(ext)


def parse_git_diff(diff_text: str) -> list[FileDelta]:
    """Parse a unified git diff into FileDelta records."""
    deltas: list[FileDelta] = []
    current: FileDelta | None = None
    current_added = 0
    current_deleted = 0

    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            if current is not None:
                current.added_lines = current_added
                current.deleted_lines = current_deleted
                deltas.append(current)
                current_added = 0
                current_deleted = 0

            parts = line.split()
            if len(parts) >= 4:
                a_path = parts[2].removeprefix("a/")
                b_path = parts[3].removeprefix("b/")
                current = FileDelta(
                    path=b_path,
                    change_type=FileChangeType.MODIFIED,
                    old_path=a_path if a_path != b_path else None,
                )
        elif line.startswith("new file"):
            if current:
                current.change_type = FileChangeType.ADDED
        elif line.startswith("deleted file"):
            if current:
                current.change_type = FileChangeType.DELETED
        elif line.startswith("rename from"):
            if current:
                current.old_path = line[len("rename from "):]
        elif line.startswith("rename to"):
            if current:
                current.change_type = FileChangeType.RENAMED
        elif line.startswith("similarity "):
            if current:
                pct = line.split("%")[0].split()[-1]
                current.similarity_index = float(pct) / 100.0
        elif line.startswith("Binary files"):
            if current:
                current.is_binary = True
        elif line.startswith("+++") or line.startswith("---"):
            continue
        elif line.startswith("+") and not line.startswith("+++"):
            current_added += 1
        elif line.startswith("-") and not line.startswith("---"):
            current_deleted += 1

    if current is not None:
        current.added_lines = current_added
        current.deleted_lines = current_deleted
        deltas.append(current)

    for d in deltas:
        d.language = detect_language(d.path)

    return deltas


def classify_delta(delta: FileDelta) -> dict:
    """Classify a file delta for semantic understanding."""
    return {
        "path": delta.path,
        "change_type": delta.change_type.value,
        "language": delta.language,
        "added": delta.added_lines,
        "deleted": delta.deleted_lines,
        "is_rename": delta.change_type == FileChangeType.RENAMED,
        "similarity": delta.similarity_index,
        "is_binary": delta.is_binary,
    }
