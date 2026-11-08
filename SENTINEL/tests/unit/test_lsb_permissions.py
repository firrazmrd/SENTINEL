import pytest
from PIL import Image

from sentinel.security import stego_lsb
from sentinel.services.permission_service import Action as A
from sentinel.services.permission_service import PermissionService as P
from sentinel.utils.exceptions import ValidationError


@pytest.mark.parametrize("mode", ["RGB", "RGBA"])
def test_lsb_round_trip_and_minimal_change(mode):
    img = Image.effect_noise((40, 40), 80).convert(mode)
    payload = bytes(range(200))
    out = stego_lsb.embed(img, payload)
    assert stego_lsb.extract(out, len(payload)) == payload
    assert max(abs(a - b) for a, b in zip(img.tobytes(), out.tobytes())) <= 1
    if mode == "RGBA":
        assert img.getchannel("A").tobytes() == out.getchannel("A").tobytes()


def test_lsb_capacity():
    img = Image.new("RGB", (8, 8))
    assert stego_lsb.capacity_bytes(img) == 24
    with pytest.raises(ValidationError):
        stego_lsb.embed(img, b"x" * 25)


MATRIX = {  # SRS 4.2
    "ADMIN": {A.VIEW_ALL_CASES, A.CREATE_CASE, A.ASSIGN_ANALYST, A.VIEW_EVIDENCE_META, A.VERIFY_CIPHERTEXT,
              A.SEND_MESSAGE, A.READ_MESSAGE, A.USE_STEGO, A.MANAGE_USERS, A.MANAGE_USB, A.VIEW_AUDIT},
    "INVESTIGATOR": {A.CREATE_CASE, A.UPLOAD_EVIDENCE, A.VIEW_EVIDENCE_META, A.VERIFY_CIPHERTEXT,
                     A.SEND_MESSAGE, A.READ_MESSAGE, A.USE_STEGO},
    "FORENSIC_ANALYST": {A.VIEW_EVIDENCE_META, A.DECRYPT_EVIDENCE, A.VERIFY_PLAINTEXT, A.VERIFY_CIPHERTEXT,
                         A.SEND_MESSAGE, A.READ_MESSAGE, A.USE_STEGO},
    "AUDITOR": {A.VIEW_ALL_CASES, A.VIEW_EVIDENCE_META, A.VERIFY_CIPHERTEXT, A.VIEW_AUDIT},
}
DENIED = {
    "ADMIN": {A.DECRYPT_EVIDENCE, A.VERIFY_PLAINTEXT, A.UPLOAD_EVIDENCE},
    "INVESTIGATOR": {A.DECRYPT_EVIDENCE, A.ASSIGN_ANALYST, A.MANAGE_USERS, A.MANAGE_USB, A.VIEW_ALL_CASES},
    "FORENSIC_ANALYST": {A.CREATE_CASE, A.UPLOAD_EVIDENCE, A.ASSIGN_ANALYST, A.MANAGE_USERS, A.MANAGE_USB},
    "AUDITOR": {A.DECRYPT_EVIDENCE, A.VERIFY_PLAINTEXT, A.SEND_MESSAGE, A.READ_MESSAGE, A.USE_STEGO,
                A.CREATE_CASE, A.UPLOAD_EVIDENCE, A.MANAGE_USERS, A.MANAGE_USB},
}


@pytest.mark.parametrize("role", list(MATRIX))
def test_permission_matrix(role):
    for action in MATRIX[role]:
        assert P.role_allows(role, action), (role, action)
    for action in DENIED[role]:
        assert not P.role_allows(role, action), (role, action)
    assert all(P.role_allows(role, a) for a in (A.VERIFY_LEDGER, A.VIEW_OWN_CASES))
