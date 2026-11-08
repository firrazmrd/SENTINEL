"""Thin SQL layer. Only this module (and connection.py) contains SQL; UI never does."""
from __future__ import annotations

from typing import Any, Iterator

from sentinel.database.connection import Database

Row = dict[str, Any]


class _Repo:
    def __init__(self, db: Database) -> None:
        self.db = db


class UserRepo(_Repo):
    def get(self, user_id: str) -> Row | None:
        return self.db.one("SELECT * FROM users WHERE id=?", (user_id,))

    def get_by_username(self, username: str) -> Row | None:
        return self.db.one("SELECT * FROM users WHERE username=?", (username,))

    def list(self) -> list[Row]:
        return self.db.all("SELECT * FROM users ORDER BY created_at")

    def count(self) -> int:
        return self.db.scalar("SELECT count(*) FROM users")

    def count_active_admins(self) -> int:
        return self.db.scalar("SELECT count(*) FROM users WHERE role='ADMIN' AND status='ACTIVE'")

    def insert(self, row: Row) -> None:
        self.db.run(
            "INSERT INTO users(id,username,password_hash,full_name,role,status,failed_attempts,created_at) "
            "VALUES(:id,:username,:password_hash,:full_name,:role,:status,0,:created_at)", row)

    def update(self, user_id: str, **fields: Any) -> None:
        cols = ", ".join(f"{k}=:{k}" for k in fields)
        self.db.run(f"UPDATE users SET {cols} WHERE id=:_id", {**fields, "_id": user_id})

    def by_role(self, role: str, only_active: bool = True) -> list[Row]:
        sql = "SELECT * FROM users WHERE role=?" + (" AND status='ACTIVE'" if only_active else "")
        return self.db.all(sql + " ORDER BY full_name", (role,))


class UsbRepo(_Repo):
    def active(self) -> Row | None:
        return self.db.one("SELECT * FROM usb_devices WHERE status='ACTIVE' ORDER BY registered_at DESC LIMIT 1")

    def revoke_all(self) -> int:
        n = self.db.scalar("SELECT count(*) FROM usb_devices WHERE status='ACTIVE'")
        self.db.run("UPDATE usb_devices SET status='REVOKED' WHERE status='ACTIVE'")
        return n

    def insert(self, row: Row) -> None:
        self.db.run(
            "INSERT INTO usb_devices(id,token_hash,volume_identifier,label,status,registered_at) "
            "VALUES(:id,:token_hash,:volume_identifier,:label,'ACTIVE',:registered_at)", row)

    def touch(self, usb_id: str, when: str) -> None:
        self.db.run("UPDATE usb_devices SET last_seen_at=? WHERE id=?", (when, usb_id))


class BiometricRepo(_Repo):
    def get(self, user_id: str) -> Row | None:
        return self.db.one("SELECT * FROM biometric_templates WHERE user_id=?", (user_id,))

    def upsert(self, row: Row) -> None:
        self.db.run(
            "INSERT INTO biometric_templates(id,user_id,encrypted_embedding,nonce,model_name,detector_backend,"
            "embedding_dim,distance_metric,threshold,deepface_version,created_at,updated_at) "
            "VALUES(:id,:user_id,:encrypted_embedding,:nonce,:model_name,:detector_backend,:embedding_dim,"
            ":distance_metric,:threshold,:deepface_version,:now,:now) "
            "ON CONFLICT(user_id) DO UPDATE SET encrypted_embedding=excluded.encrypted_embedding,"
            "nonce=excluded.nonce,model_name=excluded.model_name,detector_backend=excluded.detector_backend,"
            "embedding_dim=excluded.embedding_dim,distance_metric=excluded.distance_metric,"
            "threshold=excluded.threshold,deepface_version=excluded.deepface_version,updated_at=excluded.updated_at",
            row)

    def delete(self, user_id: str) -> None:
        self.db.run("DELETE FROM biometric_templates WHERE user_id=?", (user_id,))


class CaseRepo(_Repo):
    _SELECT = (
        "SELECT c.*, u.full_name AS creator_name, a.full_name AS analyst_name FROM cases c "
        "JOIN users u ON u.id=c.created_by LEFT JOIN users a ON a.id=c.assigned_analyst_id ")

    def get(self, case_id: str) -> Row | None:
        return self.db.one(self._SELECT + "WHERE c.id=?", (case_id,))

    def list(self, scope: str, user_id: str, query: str = "") -> list[Row]:
        where, params = [], []
        if scope == "created":
            where.append("c.created_by=?"); params.append(user_id)
        elif scope == "assigned":
            where.append("c.assigned_analyst_id=?"); params.append(user_id)
        if query:
            where.append("(c.case_number LIKE ? OR c.title LIKE ?)"); params += [f"%{query}%"] * 2
        sql = self._SELECT + ("WHERE " + " AND ".join(where) + " " if where else "") + "ORDER BY c.created_at DESC"
        return self.db.all(sql, params)

    def count(self) -> int:
        return self.db.scalar("SELECT count(*) FROM cases")

    def insert(self, row: Row) -> None:
        self.db.run(
            "INSERT INTO cases(id,case_number,title,description,status,created_by,created_at,updated_at) "
            "VALUES(:id,:case_number,:title,:description,'OPEN',:created_by,:now,:now)", row)

    def update(self, case_id: str, **fields: Any) -> None:
        cols = ", ".join(f"{k}=:{k}" for k in fields)
        self.db.run(f"UPDATE cases SET {cols} WHERE id=:_id", {**fields, "_id": case_id})


class EvidenceRepo(_Repo):
    _SELECT = ("SELECT e.*, u.full_name AS uploader_name, c.case_number FROM evidence_items e "
               "JOIN users u ON u.id=e.uploaded_by JOIN cases c ON c.id=e.case_id ")

    def get(self, evidence_id: str) -> Row | None:
        return self.db.one(self._SELECT + "WHERE e.id=?", (evidence_id,))

    def list_for_case(self, case_id: str) -> list[Row]:
        return self.db.all(self._SELECT + "WHERE e.case_id=? ORDER BY e.created_at", (case_id,))

    def count_for_case(self, case_id: str) -> int:
        return self.db.scalar("SELECT count(*) FROM evidence_items WHERE case_id=?", (case_id,))

    def count_visible(self, scope: str, user_id: str) -> int:
        if scope == "created":
            return self.db.scalar("SELECT count(*) FROM evidence_items e JOIN cases c ON c.id=e.case_id "
                                  "WHERE c.created_by=?", (user_id,))
        if scope == "assigned":
            return self.db.scalar("SELECT count(*) FROM evidence_items e JOIN cases c ON c.id=e.case_id "
                                  "WHERE c.assigned_analyst_id=?", (user_id,))
        return self.db.scalar("SELECT count(*) FROM evidence_items")

    def insert(self, row: Row) -> None:
        self.db.run(
            "INSERT INTO evidence_items(id,evidence_code,case_id,original_filename,mime_type,original_size,"
            "encrypted_path,encryption_algorithm,original_sha256,encrypted_sha256,status,uploaded_by,created_at) "
            "VALUES(:id,:evidence_code,:case_id,:original_filename,:mime_type,:original_size,:encrypted_path,"
            ":encryption_algorithm,:original_sha256,:encrypted_sha256,'STORED',:uploaded_by,:created_at)", row)

    def set_status(self, evidence_id: str, status: str) -> None:
        self.db.run("UPDATE evidence_items SET status=? WHERE id=?", (status, evidence_id))

    def set_note(self, evidence_id: str, note: str) -> None:
        self.db.run("UPDATE evidence_items SET analyst_note=? WHERE id=?", (note, evidence_id))


class MessageRepo(_Repo):
    _SELECT = ("SELECT m.*, s.full_name AS sender_name, r.full_name AS receiver_name, c.case_number "
               "FROM messages m JOIN users s ON s.id=m.sender_id JOIN users r ON r.id=m.receiver_id "
               "LEFT JOIN cases c ON c.id=m.case_id ")

    def get(self, message_id: str) -> Row | None:
        return self.db.one(self._SELECT + "WHERE m.id=?", (message_id,))

    def insert(self, row: Row) -> None:
        self.db.run(
            "INSERT INTO messages(id,case_id,sender_id,receiver_id,ciphertext,nonce,algorithm,created_at) "
            "VALUES(:id,:case_id,:sender_id,:receiver_id,:ciphertext,:nonce,:algorithm,:created_at)", row)

    def inbox(self, user_id: str) -> list[Row]:
        return self.db.all(self._SELECT + "WHERE m.receiver_id=? ORDER BY m.created_at DESC", (user_id,))

    def sent(self, user_id: str) -> list[Row]:
        return self.db.all(self._SELECT + "WHERE m.sender_id=? ORDER BY m.created_at DESC", (user_id,))

    def mark_read(self, message_id: str, when: str) -> None:
        self.db.run("UPDATE messages SET read_at=? WHERE id=? AND read_at IS NULL", (when, message_id))

    def unread_count(self, user_id: str) -> int:
        return self.db.scalar("SELECT count(*) FROM messages WHERE receiver_id=? AND read_at IS NULL", (user_id,))


class StegoRepo(_Repo):
    def insert(self, row: Row) -> None:
        self.db.run(
            "INSERT INTO stego_artifacts(id,case_id,source_image_name,output_path,carrier_sha256,payload_sha256,"
            "created_by,created_at) VALUES(:id,:case_id,:source_image_name,:output_path,:carrier_sha256,"
            ":payload_sha256,:created_by,:created_at)", row)


class AuditRepo(_Repo):
    def insert(self, row: Row) -> None:
        self.db.run(
            "INSERT INTO audit_logs(id,actor_id,event_type,target_type,target_id,case_id,details_json,created_at) "
            "VALUES(:id,:actor_id,:event_type,:target_type,:target_id,:case_id,:details_json,:created_at)", row)

    def count(self) -> int:
        return self.db.scalar("SELECT count(*) FROM audit_logs")

    def search(self, *, restrict_user_id: str | None = None, restrict_case_scope: tuple[str, str] | None = None,
               event_type: str | None = None, actor_id: str | None = None, case_id: str | None = None,
               date_from: str | None = None, date_to: str | None = None, limit: int = 300) -> list[Row]:
        where, p = [], []
        if restrict_user_id:
            sub = ""
            if restrict_case_scope:
                col = "created_by" if restrict_case_scope[0] == "created" else "assigned_analyst_id"
                sub = f" OR a.case_id IN (SELECT id FROM cases WHERE {col}=?)"
            where.append(f"(a.actor_id=?{sub})")
            p.append(restrict_user_id)
            if restrict_case_scope:
                p.append(restrict_case_scope[1])
        if event_type:
            where.append("a.event_type=?"); p.append(event_type)
        if actor_id:
            where.append("a.actor_id=?"); p.append(actor_id)
        if case_id:
            where.append("a.case_id=?"); p.append(case_id)
        if date_from:
            where.append("a.created_at>=?"); p.append(date_from)
        if date_to:
            where.append("a.created_at<=?"); p.append(date_to)
        sql = ("SELECT a.*, u.username AS actor_username, c.case_number FROM audit_logs a "
               "LEFT JOIN users u ON u.id=a.actor_id LEFT JOIN cases c ON c.id=a.case_id "
               + ("WHERE " + " AND ".join(where) + " " if where else "")
               + "ORDER BY a.created_at DESC, a.rowid DESC LIMIT ?")
        return self.db.all(sql, [*p, limit])

    def event_types(self) -> list[str]:
        return [r["event_type"] for r in self.db.all("SELECT DISTINCT event_type FROM audit_logs ORDER BY 1")]


class LedgerRepo(_Repo):
    def last(self) -> Row | None:
        return self.db.one("SELECT * FROM ledger_blocks ORDER BY block_index DESC LIMIT 1")

    def insert(self, row: Row) -> None:
        self.db.run(
            "INSERT INTO ledger_blocks(block_index,audit_log_id,timestamp_utc,actor_id,event_type,target_id,"
            "payload_hash,previous_hash,block_hash) VALUES(:block_index,:audit_log_id,:timestamp_utc,:actor_id,"
            ":event_type,:target_id,:payload_hash,:previous_hash,:block_hash)", row)

    def count(self) -> int:
        return self.db.scalar("SELECT count(*) FROM ledger_blocks")

    def blocks_with_audit(self) -> Iterator[Row]:
        cur = self.db.conn().execute(
            "SELECT b.*, a.id AS a_id, a.actor_id AS a_actor_id, a.event_type AS a_event_type, "
            "a.target_type AS a_target_type, a.target_id AS a_target_id, a.case_id AS a_case_id, "
            "a.details_json AS a_details_json, a.created_at AS a_created_at "
            "FROM ledger_blocks b LEFT JOIN audit_logs a ON a.id=b.audit_log_id ORDER BY b.block_index")
        for r in cur:
            yield dict(r)

    def recent(self, limit: int = 200) -> list[Row]:
        return self.db.all("SELECT * FROM ledger_blocks ORDER BY block_index DESC LIMIT ?", (limit,))


class SettingsRepo(_Repo):
    def get(self, key: str) -> str | None:
        return self.db.scalar("SELECT setting_value FROM app_settings WHERE setting_key=?", (key,))

    def set(self, key: str, value: str, now: str) -> None:
        self.db.run(
            "INSERT INTO app_settings(setting_key,setting_value,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value,"
            "updated_at=excluded.updated_at", (key, value, now))
