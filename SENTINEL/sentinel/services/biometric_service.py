"""1:1 face verification against the account that is logging in. No liveness detection."""
from __future__ import annotations

import math
import uuid

from sentinel.database.connection import Database
from sentinel.database.repositories import BiometricRepo, SettingsRepo
from sentinel.devices.camera import CameraSource
from sentinel.devices.face_engine import FaceEngine
from sentinel.security.biometric_crypto import BiometricCrypto
from sentinel.services.audit_service import AuditService
from sentinel.services.permission_service import Action, CurrentUser, PermissionService
from sentinel.utils.exceptions import BiometricError, DecryptionError, NotFoundError
from sentinel.utils.timeutil import now_iso

ENROLL_FRAMES = 3
VERIFY_ATTEMPTS = 3


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

    def enroll(self, actor: CurrentUser) -> None:
        actor = self._perms.authorize(actor, Action.MANAGE_OWN_FACE)
        frames = self._camera.capture_frames(ENROLL_FRAMES)
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
            self._audit.record("BIOMETRIC_TEMPLATE_DELETED", actor_id=actor.id, target_type="user", target_id=user_id)

    def verify(self, user_id: str) -> float:
        """Raises BiometricError unless the live face matches the stored template. Returns the distance."""
        tpl = self._repo.get(user_id)
        if tpl is None:
            raise BiometricError("Akun ini belum memiliki template wajah. Matikan switch Face Verification "
                                 "untuk login, lalu daftarkan wajah dari halaman Profile.")
        if (tpl["model_name"], tpl["detector_backend"], tpl["distance_metric"]) != (
                self._engine.model_name, self._engine.detector_backend, self._engine.distance_metric):
            raise BiometricError("Template wajah dibuat dengan konfigurasi lain; daftarkan ulang wajah.")
        try:
            stored = self._crypto.decrypt(tpl["nonce"], tpl["encrypted_embedding"], user_id)
        except DecryptionError as exc:
            raise BiometricError(str(exc)) from exc
        last_err: BiometricError | None = None
        for frame in self._camera.capture_frames(VERIFY_ATTEMPTS, interval=0.5):
            try:
                live = self._engine.embed(frame)
            except BiometricError as exc:  # no face / several faces: try the next frame
                last_err = exc
                continue
            dist = cosine_distance(stored, live)
            if dist <= tpl["threshold"]:
                return dist
            raise BiometricError("Wajah tidak cocok dengan template akun ini.")
        raise last_err or BiometricError("Wajah tidak terdeteksi.")
