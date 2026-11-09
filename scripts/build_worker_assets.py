"""Copy Flask templates and static files into the Worker asset bundle."""

from __future__ import annotations

from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "worker_assets"


def main() -> None:
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    shutil.copytree(ROOT / "pages", DESTINATION / "pages")
    shutil.copytree(ROOT / "static", DESTINATION / "static")
    print(f"Built Worker assets in {DESTINATION}")


if __name__ == "__main__":
    main()
