"""DeepFace adapter: ArcFace + OpenCV detector, ONNX Runtime CPU. Imported lazily, after DEEPFACE_HOME is set."""
from __future__ import annotations

from importlib import metadata
from typing import Any, Protocol

from sentinel.utils.exceptions import BiometricError


class FaceEngine(Protocol):
    model_name: str
    detector_backend: str
    distance_metric: str

    def embed(self, frame: Any) -> list[float]: ...
    def threshold(self) -> tuple[float, str]: ...
    def version(self) -> str: ...


class DeepFaceEngine:
    def __init__(self, model_name: str = "ArcFace", detector_backend: str = "opencv",
                 distance_metric: str = "cosine") -> None:
        self.model_name, self.detector_backend, self.distance_metric = model_name, detector_backend, distance_metric

    def _deepface(self) -> Any:
        try:
            from deepface import DeepFace
        except ImportError as exc:
            raise BiometricError("DeepFace belum terpasang. Jalankan: python -m pip install -r requirements-biometric.txt") from exc
        return DeepFace

    def version(self) -> str:
        try:
            return metadata.version("deepface")
        except metadata.PackageNotFoundError:
            return "unknown"

    def embed(self, frame: Any) -> list[float]:
        df = self._deepface()
        try:
            results = df.represent(img_path=frame, model_name=self.model_name,
                                   detector_backend=self.detector_backend, enforce_detection=True, align=True)
        except ValueError as exc:
            raise BiometricError("Wajah tidak terdeteksi. Hadap kamera dengan pencahayaan cukup.") from exc
        except Exception as exc:  # model download/ONNX failures
            raise BiometricError(f"Gagal memproses wajah ({type(exc).__name__}). Pastikan model ArcFace sudah terunduh.") from exc
        if len(results) != 1:
            raise BiometricError(f"Harus tepat satu wajah di kamera; terdeteksi {len(results)}.")
        return [float(x) for x in results[0]["embedding"]]

    def threshold(self) -> tuple[float, str]:
        """Take the threshold from the installed DeepFace instead of guessing it."""
        errors = []
        try:
            from deepface.modules import verification
            value = float(verification.find_threshold(self.model_name, self.distance_metric))
            return value, f"deepface.modules.verification.find_threshold (deepface {self.version()})"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"find_threshold: {type(exc).__name__}")
        try:
            df = self._deepface()
            probe = [1.0] + [0.0] * 511
            res = df.verify(img1_path=probe, img2_path=probe, model_name=self.model_name,
                            distance_metric=self.distance_metric, detector_backend=self.detector_backend)
            return float(res["threshold"]), f"DeepFace.verify()['threshold'] (deepface {self.version()})"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"verify: {type(exc).__name__}")
        raise BiometricError("Threshold ArcFace tidak dapat dibaca dari DeepFace terpasang (" + "; ".join(errors) + ").")
