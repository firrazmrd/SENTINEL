import pytest
from conftest import PASSWORD

from sentinel.utils.exceptions import BiometricError, PermissionDeniedError


def test_enroll_and_verify(env):
    u = env.make_user("INVESTIGATOR", "invest")
    env.camera.frames = ["alice"] * 3
    env.ctx.biometric.enroll(u)
    tpl = env.ctx.db.one("SELECT * FROM biometric_templates WHERE user_id=?", (u.id,))
    assert tpl["embedding_dim"] == 512 and tpl["model_name"] == "ArcFace" and tpl["threshold"] == 0.68
    assert len(tpl["encrypted_embedding"]) == 512 * 4 + 16          # AES-GCM: raw floats + tag, no plaintext
    env.camera.frames = ["alice+1", "alice+1", "alice+1"]            # same person, slight variation
    assert env.ctx.auth.login("invest", PASSWORD, True).id == u.id
    env.camera.frames = ["bob"] * 3                                  # someone else
    with pytest.raises(BiometricError):
        env.ctx.auth.login("invest", PASSWORD, True)


@pytest.mark.parametrize("frames", [["noface"] * 3, ["two"] * 3])
def test_no_face_or_multiple_faces_fail(env, frames):
    u = env.make_user("INVESTIGATOR", "invest")
    env.camera.frames = frames
    with pytest.raises(BiometricError):
        env.ctx.biometric.enroll(u)
    env.camera.frames = ["alice"] * 3
    env.ctx.biometric.enroll(u)
    env.camera.frames = frames
    with pytest.raises(BiometricError):
        env.ctx.auth.login("invest", PASSWORD, True)


def test_verification_is_one_to_one(env):
    a, b = env.make_user("INVESTIGATOR", "inv_a"), env.make_user("FORENSIC_ANALYST", "ana_b")
    env.camera.frames = ["alice"] * 3
    env.ctx.biometric.enroll(a)
    env.camera.frames = ["bob"] * 3
    env.ctx.biometric.enroll(b)
    env.camera.frames = ["alice"] * 3            # Alice's face must not log in as Bob
    with pytest.raises(BiometricError):
        env.ctx.auth.login("ana_b", PASSWORD, True)
    assert env.ctx.auth.login("inv_a", PASSWORD, True)


def test_template_delete_and_reset_rules(env):
    a, b = env.make_user("INVESTIGATOR", "inv_a"), env.make_user("AUDITOR", "aud_b")
    env.ctx.biometric.enroll(a)
    with pytest.raises(PermissionDeniedError):
        env.ctx.biometric.delete_template(b, a.id)       # only Admin may reset someone else's template
    env.ctx.biometric.delete_template(env.admin, a.id)
    assert not env.ctx.biometric.has_template(a.id)
