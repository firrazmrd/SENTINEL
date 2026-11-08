#!/usr/bin/env python
r"""SENTINEL v1.2 - smoke test minimum (hanya data dummy).

Jalankan dari dalam .venv:
    python scripts\smoke_sentinel.py core        # python, gui, sqlcipher, crypto, vigenere, lsb, argon2, keyring
    python scripts\smoke_sentinel.py hardware    # camera, deepface (dijalankan SENGAJA oleh pengguna)
    python scripts\smoke_sentinel.py sqlcipher   # satu tes saja

Skrip ini tidak menyimpan gambar/frame kamera ke disk, tidak mengirim data ke mana pun,
dan hanya memakai entri keyring + folder temp yang dihapus kembali.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import platform
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from importlib import metadata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

RESULTS: list[tuple[str, bool, str]] = []


def ver(pkg: str) -> str:
    try:
        return metadata.version(pkg)
    except metadata.PackageNotFoundError:
        return "TIDAK TERPASANG"


# ----------------------------------------------------------------------------- python / gui
def t_python(_a) -> str:
    assert sys.implementation.name == "cpython", "bukan CPython"
    assert sys.version_info[:2] == (3, 13), f"butuh 3.13.x, ditemukan {sys.version}"
    assert sys.maxsize > 2**32, "bukan Python 64-bit"
    assert sys.prefix != sys.base_prefix, "TIDAK berada di virtual environment"
    pip = subprocess.run([sys.executable, "-m", "pip", "--version"],
                         capture_output=True, text=True).stdout.strip()
    return f"{sys.version.split()[0]} | {platform.platform()} | exe={sys.executable} | {pip}"


def t_gui(_a) -> str:
    import customtkinter as ctk
    root = ctk.CTk()
    root.title("SENTINEL smoke")
    root.update()
    root.destroy()
    return f"customtkinter {ver('customtkinter')}"


# ----------------------------------------------------------------------------- sqlcipher
def t_sqlcipher(_a) -> str:
    import sqlite3

    from sqlcipher3 import dbapi2 as sqlcipher  # cara import yang diuji

    tmp = Path(tempfile.mkdtemp(prefix="sentinel_sqlc_"))
    try:
        db = tmp / "t.db"
        key = secrets.token_hex(32)  # 256-bit acak -> pakai raw key x'..'
        marker = "SENTINEL_MARKER_" + secrets.token_hex(8)

        con = sqlcipher.connect(str(db))
        con.execute(f"PRAGMA key = \"x'{key}'\"")  # harus statement pertama
        cv = con.execute("PRAGMA cipher_version").fetchone()
        assert cv and cv[0], "PRAGMA cipher_version kosong -> binding ini BUKAN SQLCipher"
        con.execute("CREATE TABLE t(v TEXT)")
        con.execute("INSERT INTO t VALUES (?)", (marker,))
        con.commit()
        con.close()

        raw = db.read_bytes()
        assert not raw.startswith(b"SQLite format 3\x00"), "header SQLite plaintext terdeteksi"
        assert marker.encode() not in raw, "isi tabel terbaca dalam file"

        try:  # 1) stdlib sqlite3 harus gagal
            sqlite3.connect(str(db)).execute("SELECT count(*) FROM sqlite_master").fetchall()
            raise AssertionError("sqlite3 standar bisa membuka DB -> tidak terenkripsi")
        except sqlite3.DatabaseError:
            pass

        wrong = sqlcipher.connect(str(db))  # 2) key salah harus gagal
        wrong.execute(f"PRAGMA key = \"x'{secrets.token_hex(32)}'\"")
        try:
            wrong.execute("SELECT count(*) FROM sqlite_master").fetchall()
            raise AssertionError("key salah tetap bisa membuka DB")
        except sqlcipher.DatabaseError:
            pass
        finally:
            wrong.close()

        ok = sqlcipher.connect(str(db))  # 3) key benar harus berhasil
        ok.execute(f"PRAGMA key = \"x'{key}'\"")
        got = ok.execute("SELECT v FROM t").fetchone()[0]
        ok.close()
        assert got == marker
        return f"sqlcipher3 {ver('sqlcipher3')} | cipher_version={cv[0]} | file terenkripsi, key salah ditolak"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ----------------------------------------------------------------------------- crypto (v1.2 design)
def t_crypto(_a) -> str:
    from sentinel.security.biometric_crypto import BiometricCrypto
    from sentinel.security.file_crypto import FileCrypto
    from sentinel.security.message_crypto import MessageCrypto
    from sentinel.utils.exceptions import DecryptionError

    def must_fail(fn, label):
        try:
            fn()
        except DecryptionError:
            return
        raise AssertionError(f"{label}: seharusnya DecryptionError")

    key = secrets.token_bytes(32)
    mc = MessageCrypto(key, "SENTINELDEMO")            # Vigenere -> AES-256-GCM
    nonce, ct = mc.encrypt("pesan dummy", "message", "id-1")
    assert mc.decrypt(nonce, ct, "message", "id-1") == "pesan dummy"
    must_fail(lambda: mc.decrypt(nonce, ct, "message", "id-2"), "AAD message id salah")
    must_fail(lambda: mc.decrypt(nonce, ct[:-1] + bytes([ct[-1] ^ 1]), "message", "id-1"), "tag diubah")

    fc = FileCrypto(key)                                # ChaCha20-Poly1305 one-shot
    blob = fc.encrypt(b"isi bukti dummy", "EV-1")
    assert fc.decrypt(blob, "EV-1") == b"isi bukti dummy"
    must_fail(lambda: fc.decrypt(blob, "EV-2"), "AAD evidence id salah")
    must_fail(lambda: fc.decrypt(blob[:-1] + bytes([blob[-1] ^ 1]), "EV-1"), "ciphertext diubah")

    bc = BiometricCrypto(key)
    n, b = bc.encrypt([0.25, -1.5, 2.0], "user-1")
    assert bc.decrypt(n, b, "user-1") == [0.25, -1.5, 2.0]
    must_fail(lambda: bc.decrypt(n, b, "user-2"), "AAD user id salah")
    return f"cryptography {ver('cryptography')} | AES-256-GCM, ChaCha20-Poly1305 one-shot, template wajah (tamper ditolak)"


def t_vigenere(_a) -> str:
    from sentinel.security.vigenere import vigenere_decrypt, vigenere_encrypt
    assert vigenere_encrypt("ATTACKATDAWN", "LEMON") == "LXFOPVEFRNHR"     # vektor klasik
    for text in ("Hello, World!", "Pesan 123 — café", ""):
        assert vigenere_decrypt(vigenere_encrypt(text, "SENTINELDEMO"), "SENTINELDEMO") == text
    return "Vigenere round trip + vektor uji klasik"


def t_lsb(_a) -> str:
    from PIL import Image

    from sentinel.security import stego_lsb
    img = Image.effect_noise((64, 64), 60).convert("RGB")
    payload = secrets.token_bytes(300)
    out = stego_lsb.embed(img, payload)
    assert stego_lsb.extract(out, len(payload)) == payload
    assert max(abs(a - b) for a, b in zip(img.tobytes(), out.tobytes())) <= 1
    return f"LSB PNG round trip (kapasitas {stego_lsb.capacity_bytes(img)} byte; perubahan piksel <= 1)"


# ----------------------------------------------------------------------------- argon2
def t_argon2(_a) -> str:
    import argon2
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError

    ph, pw = PasswordHasher(), "Dummy-Passw0rd-Only!"
    t0 = time.perf_counter()
    h = ph.hash(pw)
    t_hash = time.perf_counter() - t0
    assert h.startswith("$argon2id$"), "bukan Argon2id"
    t0 = time.perf_counter()
    assert ph.verify(h, pw)
    t_ver = time.perf_counter() - t0
    try:
        ph.verify(h, pw + "x")
        raise AssertionError("password salah diterima")
    except VerifyMismatchError:
        pass
    p = argon2.extract_parameters(h)
    return (f"argon2-cffi {ver('argon2-cffi')} | t={p.time_cost} m={p.memory_cost}KiB p={p.parallelism} "
            f"| hash {t_hash*1000:.0f} ms, verify {t_ver*1000:.0f} ms (target UI ~250-500 ms)")


# ----------------------------------------------------------------------------- keyring
def t_keyring(_a) -> str:
    import keyring
    kr = keyring.get_keyring()
    mod = type(kr).__module__
    assert "fail" not in mod and "null" not in mod, f"tidak ada backend keyring yang berfungsi: {type(kr)}"
    svc, user, val = "SENTINEL-smoke-test", "dummy", secrets.token_hex(32)
    keyring.set_password(svc, user, val)
    try:
        assert keyring.get_password(svc, user) == val
    finally:
        try:
            keyring.delete_password(svc, user)
        except Exception:
            pass
    assert keyring.get_password(svc, user) is None
    return f"keyring {ver('keyring')} | backend={type(kr).__module__}.{type(kr).__name__}"


# ----------------------------------------------------------------------------- camera / deepface
def _open_camera(cv2, index: int):
    for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY):
        cap = cv2.VideoCapture(index, backend)
        if cap.isOpened():
            return cap, backend
        cap.release()
    return None, None


def _grab_frames(index: int, count: int):
    import cv2
    cap, backend = _open_camera(cv2, index)
    assert cap is not None, f"kamera index {index} tidak bisa dibuka (cek privasi kamera Windows)"
    frames = []
    try:
        for _ in range(10):  # warm-up auto-exposure
            cap.read()
        for _ in range(count):
            ok, f = cap.read()
            assert ok and f is not None, "gagal membaca frame"
            frames.append(f)
            time.sleep(0.5)
    finally:
        cap.release()
    return frames, backend


def t_camera(a) -> str:
    import cv2
    names = sorted({(d.metadata["Name"] or "") for d in metadata.distributions()
                    if (d.metadata["Name"] or "").lower().startswith("opencv")})
    assert len(names) == 1, f"lebih dari satu distribusi OpenCV terpasang: {names}"
    frames, backend = _grab_frames(a.camera_index, 1)
    f = frames[0]
    assert f.mean() > 5, "frame hampir hitam (kamera tertutup / privasi?)"
    haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = haar.detectMultiScale(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), 1.1, 5)
    return f"{names[0]} {cv2.__version__} | backend={backend} | frame={f.shape} | wajah Haar={len(faces)} (frame tidak disimpan)"


def t_deepface(a) -> str:
    home = os.environ.get("DEEPFACE_HOME")
    assert home, "DEEPFACE_HOME harus diset SEBELUM skrip dijalankan"
    import numpy as np
    import onnxruntime as ort
    from deepface import DeepFace

    heavy = [m for m in ("tensorflow", "keras", "torch") if importlib.util.find_spec(m)]
    if a.image:
        import cv2
        img = cv2.imread(a.image)
        assert img is not None, "gagal membaca --image"
        frames = [img, img]
    else:
        frames, _ = _grab_frames(a.camera_index, 2)

    embs = []
    t0 = time.perf_counter()
    for f in frames:
        r = DeepFace.represent(img_path=f, model_name="ArcFace", detector_backend="opencv",
                               enforce_detection=True, align=True)
        assert len(r) == 1, f"harus tepat 1 wajah, terdeteksi {len(r)}"
        embs.append(np.asarray(r[0]["embedding"], dtype=np.float32))
    dt = time.perf_counter() - t0
    x, y = embs
    cos_dist = 1.0 - float(x @ y / (np.linalg.norm(x) * np.linalg.norm(y)))

    from sentinel.devices.face_engine import DeepFaceEngine
    thr, thr_src = DeepFaceEngine().threshold()
    wdir = Path(home) / ".deepface" / "weights"
    files = sorted(f"{p.name}={p.stat().st_size // 1024}KB" for p in wdir.glob("*")) if wdir.exists() else []
    assert files, f"tidak ada bobot di {wdir} (first run butuh internet untuk mengunduh)"
    stray = Path.home() / ".deepface"
    notes = []
    if stray.exists():
        notes.append(f"PERINGATAN: {stray} ada (cache lama di drive C:)")
    if heavy:
        notes.append(f"PERINGATAN: framework berat terpasang: {heavy}")
    return (f"deepface {ver('deepface')} | onnxruntime {ort.__version__} providers={ort.get_available_providers()} "
            f"| threshold={thr} ({thr_src}) | embedding dim={x.shape[0]} | cosine distance(frame1,frame2)={cos_dist:.3f} | 2 inferensi {dt:.1f}s "
            f"| weights di {wdir}: {files} " + " ".join(notes))


TESTS = {"python": t_python, "gui": t_gui, "sqlcipher": t_sqlcipher, "crypto": t_crypto, "vigenere": t_vigenere,
         "lsb": t_lsb, "argon2": t_argon2, "keyring": t_keyring, "camera": t_camera, "deepface": t_deepface}
GROUPS = {"core": ["python", "gui", "sqlcipher", "crypto", "vigenere", "lsb", "argon2", "keyring"],
          "hardware": ["camera", "deepface"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=[*TESTS, *GROUPS])
    ap.add_argument("--camera-index", type=int, default=0)
    ap.add_argument("--image", help="gambar milik sendiri (opsional) sebagai pengganti webcam untuk tes deepface")
    a = ap.parse_args()
    for name in GROUPS.get(a.what, [a.what]):
        t0 = time.perf_counter()
        try:
            note = TESTS[name](a)
            RESULTS.append((name, True, f"{note} [{time.perf_counter() - t0:.1f}s]"))
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            RESULTS.append((name, False, f"{type(exc).__name__}: {exc}"))
    print("\n=== HASIL ===")
    for name, ok, note in RESULTS:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {note}")
    return 0 if all(ok for _, ok, _ in RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
