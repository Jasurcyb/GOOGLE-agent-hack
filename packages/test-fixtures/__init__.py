from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    path = FIXTURES_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Fixture '{name}' not found at {path}")
    return path.read_text(encoding="utf-8")


def list_fixtures() -> list[str]:
    return [f.stem for f in FIXTURES_DIR.glob("*.json")]


__all__ = ["FIXTURES_DIR", "load_fixture", "list_fixtures"]
