"""Non-secret runtime configuration. Cryptographic keys never live here (see security/key_manager.py)."""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_dir

ALLOWED_EXTENSIONS = (
    ".pdf", ".png", ".jpg", ".jpeg", ".txt", ".docx", ".wav", ".mp3", ".mp4",
    ".zip", ".csv", ".json", ".log",
)


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    deepface_home: Path
    max_file_mb: int = 100
    camera_index: int = 0
    theme: str = "dark"
    usb_include_fixed: bool = False
    # Public demo key for the educational Vigenere layer. NOT a secret (SRS 7.2).
    vigenere_key: str = "SENTINELDEMO"
    usb_token_filename: str = ".sentinel-token"
    max_login_attempts: int = 5
    lockout_seconds: int = 30
    face_model: str = "ArcFace"
    face_detector: str = "opencv"
    face_metric: str = "cosine"

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(os.environ.get("SENTINEL_DATA_DIR") or user_data_dir("SENTINEL", appauthor=False))
        deepface = Path(os.environ.get("DEEPFACE_HOME") or (data_dir / "models"))
        return cls(
            data_dir=data_dir,
            deepface_home=deepface,
            max_file_mb=int(os.environ.get("SENTINEL_MAX_FILE_MB", "100")),
            camera_index=int(os.environ.get("SENTINEL_CAMERA_INDEX", "0")),
            theme=os.environ.get("SENTINEL_THEME", "dark"),
            usb_include_fixed=os.environ.get("SENTINEL_USB_INCLUDE_FIXED", "0") == "1",
        )

    def apply_environment(self) -> None:
        """Must run before DeepFace is imported."""
        os.environ["DEEPFACE_HOME"] = str(self.deepface_home)

    @property
    def max_file_bytes(self) -> int:
        return self.max_file_mb * 1024 * 1024

    @property
    def db_path(self) -> Path:
        return self.data_dir / "sentinel.db"

    @property
    def evidence_dir(self) -> Path:
        return self.data_dir / "evidence"

    @property
    def stego_dir(self) -> Path:
        return self.data_dir / "stego"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def keyring_service(self) -> str:
        """One keyring namespace per data directory so separate installs never collide."""
        digest = hashlib.sha256(str(self.data_dir.resolve()).lower().encode()).hexdigest()[:10]
        return f"SENTINEL-{digest}"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.evidence_dir, self.stego_dir, self.logs_dir, self.deepface_home):
            d.mkdir(parents=True, exist_ok=True)
