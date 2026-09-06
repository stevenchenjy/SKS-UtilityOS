from dataclasses import dataclass
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
MAX_UPLOAD = 8 * 1024 * 1024


def default_data_dir(mode: str) -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path.home() / ".local" / "share"
    return base / "SKS-UtilityOS" / mode


@dataclass(frozen=True)
class Config:
    data_dir: Path
    mode: str = "demo"
    port: int = 8765

    def validate(self) -> None:
        if self.mode not in {"demo", "staff"}:
            raise ValueError("MODE_INVALID")
        if not 1024 <= self.port <= 65535:
            raise ValueError("PORT_INVALID")
        path = self.data_dir.resolve()
        if path == ROOT or ROOT in path.parents:
            raise ValueError("DATA_DIRECTORY_MUST_BE_OUTSIDE_SOURCE")
        if self.mode == "staff":
            blocked = {"desktop", "documents", "mobile documents", "icloud drive", "onedrive", "dropbox", "google drive", "googledrive"}
            if any(part.lower() in blocked or part.lower().startswith("onedrive -") for part in path.parts):
                raise ValueError("STAFF_DATA_DIRECTORY_MUST_BE_LOCAL_UNSYNCED")

    @property
    def origins(self) -> set[str]:
        return {f"http://127.0.0.1:{self.port}", f"http://localhost:{self.port}"}
