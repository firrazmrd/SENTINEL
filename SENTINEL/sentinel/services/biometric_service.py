"""1:1 face verification against the account that is logging in. No liveness detection."""
from __future__ import annotations

import math
import uuid
from typing import Callable

from sentinel.database.connection import Database
from sentinel.database.repositories import BiometricRepo, SettingsRepo
from sentinel.devices.camera import CameraSource, FrameStream
from sentinel.devices.face_engine import FaceEngine
from sentinel.security.biometric_crypto import BiometricCrypto
from sentinel.services.audit_service import AuditService
from sentinel.services.permission_service import Action, CurrentUser, PermissionService
from sentinel.utils.exceptions import BiometricError, DecryptionError, DeviceError, NotFoundError
from sentinel.utils.timeutil import now_iso

ENROLL_FRAMES = 3
VERIFY_ATTEMPTS = 3
# Stages reported while a login verifies a face (the login screen renders them as status labels).
CAMERA_INITIALIZING, CAMERA_ACTIVE, SCANNING, VERIFYING = "CAMERA_INITIALIZING", "CAMERA_ACTIVE", "SCANNING", "VERIFYING"
VERIFIED, FAILED, CAMERA_UNAVAILABLE = "VERIFIED", "FAILED", "CAMERA_UNAVAILABLE"


def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def cosine_distance(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise BiometricError("Dimensi embedding tidak sama; daftarkan ulang wajah.")
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return 1.0 - dot / (na * nb) if na and nb else 1.0


class BiometricService:
    def __init__(self, db: Database, repo: BiometricRepo, settings_repo: SettingsRepo, crypto: BiometricCrypto,
                 engine: FaceEngine, camera: CameraSource, perms: PermissionService, audit: AuditService,
                 users) -> None:
        self._db, self._repo, self._settings = db, repo, settings_repo
        self._crypto, self._engine, self._camera = crypto, engine, camera
        self._perms, self._audit, self._users = perms, audit, users

    def has_template(self, user_id: str) -> bool:
        return self._repo.get(user_id) is not None

    def my_template_info(self, actor: CurrentUser) -> dict | None:
        actor = self._perms.authorize(actor, Action.MANAGE_OWN_FACE)
        t = self._repo.get(actor.id)
        return None if t is None else {k: t[k] for k in ("model_name", "detector_backend", "embedding_dim",
                                                         "distance_metric", "threshold", "updated_at")}

    def open_preview(self, actor: CurrentUser) -> FrameStream:
        """Live camera session for the Settings enrollment dialog. The caller must close() it."""
        self._perms.authorize(actor, Action.MANAGE_OWN_FACE)
        return self._camera.open_stream()

    def enroll(self, actor: CurrentUser) -> None:
        actor = self._perms.authorize(actor, Action.MANAGE_OWN_FACE)
        self._store_template(actor, self._camera.capture_frames(ENROLL_FRAMES))

    def enroll_from_frames(self, actor: CurrentUser, frames: list) -> None:
        """Same pipeline as enroll(), but with frames the user captured from the live preview."""
        actor = self._perms.authorize(actor, Action.MANAGE_OWN_FACE)
        self._store_template(actor, frames)

    def _store_template(self, actor: CurrentUser, frames: list) -> None:
        if not frames:
            raise BiometricError("Tidak ada gambar dari kamera.")
        embeddings = [_normalize(self._engine.embed(f)) for f in frames]  # each frame must have exactly one face
        mean = _normalize([sum(col) / len(col) for col in zip(*embeddings)])
        threshold, source = self._engine.threshold()
        nonce, blob = self._crypto.encrypt(mean, actor.id)
        now = now_iso()
        with self._db.transaction():
            self._repo.upsert({
                "id": str(uuid.uuid4()), "user_id": actor.id, "encrypted_embedding": blob, "nonce": nonce,
                "model_name": self._engine.model_name, "detector_backend": self._engine.detector_backend,
                "embedding_dim": len(mean), "distance_metric": self._engine.distance_metric,
                "threshold": threshold, "deepface_version": self._engine.version(), "now": now})
            self._settings.set("face_threshold_source", source, now)
            self._audit.record("BIOMETRIC_ENROLLMENT", actor_id=actor.id, target_type="user", target_id=actor.id,
                               details={"model": self._engine.model_name, "dim": len(mean)})

    def delete_template(self, actor: CurrentUser, user_id: str | None = None) -> None:
        if user_id is None or user_id == actor.id:
            actor = self._perms.authorize(actor, Action.MANAGE_OWN_FACE)
            user_id = actor.id
        else:
            actor = self._perms.authorize(actor, Action.RESET_FACE)
        if self._users.get(user_id) is None:
            raise NotFoundError("Pengguna tidak ditemukan.")
        with self._db.transaction():
            self._repo.delete(user_id)
            # No template => the face requirement can never be met; switch it off so the account is not locked out.
            self._users.update(user_id, require_face=0)
            self._audit.record("BIOMETRIC_TEMPLATE_DELETED", actor_id=actor.id, target_type="user", target_id=user_id)

    def verify(self, user_id: str, on_stage: Callable[[str], None] | None = None,
               on_stream: Callable[[FrameStream], None] | None = None) -> float:
        """Raises BiometricError unless the live face matches the stored template. Returns the distance.
        The camera is opened only here, only for the duration of the check, and always released. Frames stay in
        local variables and are never written anywhere. `on_stage` receives the FACE_STAGES in order (worker
        thread); `on_stream` receives the live stream so a UI can show a preview (it is closed when we return)."""
        def emit(stage: str) -> None:
            if on_stage is not None:
                try:
                    on_stage(stage)
                except Exception:  # noqa: BLE001 - a UI callback must never break authentication
                    pass

        tpl = self._repo.get(user_id)
        if tpl is None:
            raise BiometricError("Akun ini mewajibkan verifikasi wajah tetapi belum memiliki template wajah. "
                                 "Hubungi Admin untuk mereset pengaturan wajah.")
        if (tpl["model_name"], tpl["detector_backend"], tpl["distance_metric"]) != (
                self._engine.model_name, self._engine.detector_backend, self._engine.distance_metric):
            raise BiometricError("Template wajah dibuat dengan konfigurasi lain; daftarkan ulang wajah.")
        try:
            stored = self._crypto.decrypt(tpl["nonce"], tpl["encrypted_embedding"], user_id)
        except DecryptionError as exc:
            raise BiometricError(str(exc)) from exc

        emit(CAMERA_INITIALIZING)
        try:
            stream = self._camera.open_stream()
        except DeviceError:
            emit(CAMERA_UNAVAILABLE)
            raise
        try:
            emit(CAMERA_ACTIVE)
            if on_stream is not None:
                on_stream(stream)
            emit(SCANNING)
            frames = stream.grab(VERIFY_ATTEMPTS, 0.5)
            emit(VERIFYING)
            dist = self._match(stored, tpl["threshold"], frames)
            emit(VERIFIED)
            return dist
        except DeviceError:
            emit(CAMERA_UNAVAILABLE)
            raise
        except BiometricError:
            emit(FAILED)
            raise
        finally:
            stream.close()

    def _match(self, stored: list[float], threshold: float, frames: list) -> float:
        last_err: BiometricError | None = None
        for frame in frames:
            try:
                live = self._engine.embed(frame)
            except BiometricError as exc:  # no face / several faces: try the next frame
                last_err = exc
                continue
            dist = cosine_distance(stored, live)
            if dist <= threshold:
                return dist
            raise BiometricError("Wajah tidak cocok dengan template akun ini.")
        raise last_err or BiometricError("Wajah tidak terdeteksi.")
