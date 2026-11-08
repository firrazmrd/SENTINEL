"""SENTINEL entry point. Run with the project's virtual environment: python main.py"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler


def main() -> int:
    from config import Settings
    settings = Settings.from_env()
    settings.apply_environment()          # DEEPFACE_HOME must be set before DeepFace is imported
    settings.ensure_dirs()
    handler = RotatingFileHandler(settings.logs_dir / "sentinel.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])   # never log secrets, passwords, or plaintext
    from sentinel.ui.app import SentinelApp
    SentinelApp(settings).mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
