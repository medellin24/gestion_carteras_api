from __future__ import annotations

from pathlib import Path
import sys

_BASE_PATH = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def project_path(*parts: str) -> Path:
    """
    Returns an absolute path within the project or the PyInstaller bundle.
    """
    return _BASE_PATH.joinpath(*parts)


def asset_path(*parts: str) -> str:
    """
    Shortcut to get the absolute path to a file inside the assets folder.
    """
    return str(project_path(*parts))

