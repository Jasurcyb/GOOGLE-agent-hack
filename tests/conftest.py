from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

for folder in ["packages", "apps"]:
    target_dir = ROOT_DIR / folder
    if target_dir.exists():
        for child in target_dir.iterdir():
            if child.is_dir() and str(child) not in sys.path:
                sys.path.insert(0, str(child))

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
