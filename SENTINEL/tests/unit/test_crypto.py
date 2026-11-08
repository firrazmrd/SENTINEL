import pytest

from sentinel.security.biometric_crypto import BiometricCrypto
from sentinel.security.file_crypto import FileCrypto
from sentinel.security.hashing import canonical_json, sha256_file, sha256_hex
from sentinel.security.message_crypto import MessageCrypto
from sentinel.security.password_hasher import PasswordHasher
from sentinel.security.vigenere import vigenere_decrypt, vigenere_encrypt
from sentinel.utils.exceptions import DecryptionError

K = bytes(range(32))


def test_argon2id():
    h = PasswordHasher()
    enc = h.hash("rahasia-123")
    assert enc.startswith("$argon2id$")
    assert h.verify(enc, "rahasia-123")
    assert not h.verify(enc, "salah")
    assert not h.verify("bukan-hash", "x")


@pytest.mark.parametrize("text", ["Hello, World!", "Pesan 123 — café ñ 日本語", "", "ABC xyz\n\t!?"])
def test_vigenere_round_trip(text):
    assert vigenere_decrypt(vigenere_encrypt(text, "SENTINELDEMO"), "SENTINELDEMO") == text


def test_vigenere_known_vector():
    assert vigenere_encrypt("ATTACKATDAWN", "LEMON") == "LXFOPVEFRNHR"
    assert vigenere_encrypt("a-b", "B") == "b-c"


def test_message_crypto_round_trip_and_binding():
    mc = MessageCrypto(K, "SENTINELDEMO")
    nonce, ct = mc.encrypt("halo dunia", "message", "id-1")
    assert b"halo" not in ct
    assert mc.decrypt(nonce, ct, "message", "id-1") == "halo dunia"
    with pytest.raises(DecryptionError):
        mc.decrypt(nonce, ct, "message", "id-2")          # wrong message id (AAD)
    with pytest.raises(DecryptionError):
        mc.decrypt(nonce, ct, "stego", "id-1")            # wrong context (AAD)
    with pytest.raises(DecryptionError):
        mc.decrypt(nonce[::-1], ct, "message", "id-1")    # wrong nonce
    with pytest.raises(DecryptionError):
        mc.decrypt(nonce, ct[:-1] + bytes([ct[-1] ^ 1]), "message", "id-1")  # tag flipped
    assert mc.encrypt("x", "message", "i")[0] != mc.encrypt("x", "message", "i")[0]  # fresh nonce


def test_message_crypto_wrong_key():
    nonce, ct = MessageCrypto(K, "ABC").encrypt("x", "message", "i")
    with pytest.raises(DecryptionError):
        MessageCrypto(bytes(32), "ABC").decrypt(nonce, ct, "message", "i")


def test_file_crypto():
    fc = FileCrypto(K)
    blob = fc.encrypt(b"isi bukti dummy", "ev-1")
    assert blob.startswith(b"SNTENC\x01") and b"dummy" not in blob
    assert fc.decrypt(blob, "ev-1") == b"isi bukti dummy"
    with pytest.raises(DecryptionError):
        fc.decrypt(blob, "ev-2")
    with pytest.raises(DecryptionError):
        fc.decrypt(blob[:-1] + bytes([blob[-1] ^ 1]), "ev-1")
    with pytest.raises(DecryptionError):
        fc.decrypt(b"XXXXXX" + blob[6:], "ev-1")
    assert fc.decrypt(fc.encrypt(b"", "e"), "e") == b""


def test_biometric_crypto():
    bc = BiometricCrypto(K)
    emb = [0.5, -1.25, 3.0]
    nonce, blob = bc.encrypt(emb, "u1")
    assert bc.decrypt(nonce, blob, "u1") == emb
    with pytest.raises(DecryptionError):
        bc.decrypt(nonce, blob, "u2")


def test_hashing(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"abc")
    assert sha256_file(p) == sha256_hex(b"abc") == sha256_file(p)
    assert canonical_json({"b": 1, "a": "é"}) == '{"a":"é","b":1}'.encode()
