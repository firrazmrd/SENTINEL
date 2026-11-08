"""Unduh sekali bobot ArcFace + cascade OpenCV ke DEEPFACE_HOME agar demo dapat berjalan offline.
Jalankan manual (butuh internet pertama kali):  python scripts/prefetch_models.py
Tidak memakai webcam dan tidak memakai foto pengguna: hanya gambar kosong sintetis.
"""
import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import Settings  # noqa: E402

settings = Settings.from_env()
settings.apply_environment()          # sebelum import deepface
settings.deepface_home.mkdir(parents=True, exist_ok=True)

import numpy as np  # noqa: E402
from deepface import DeepFace  # noqa: E402

blank = np.zeros((224, 224, 3), dtype=np.uint8)
DeepFace.represent(img_path=blank, model_name=settings.face_model, detector_backend=settings.face_detector,
                   enforce_detection=False)
wdir = settings.deepface_home / ".deepface" / "weights"
print(f"DEEPFACE_HOME = {os.environ['DEEPFACE_HOME']}")
for p in sorted(wdir.glob("*")):
    print(f"{p.name:45s} {p.stat().st_size // 1024:>8d} KB  sha256={hashlib.sha256(p.read_bytes()).hexdigest()}")
print("Catat SHA-256 di atas sebagai bukti bobot yang dipakai.")
