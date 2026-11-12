CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('ADMIN','INVESTIGATOR','FORENSIC_ANALYST','AUDITOR')),
    status TEXT NOT NULL CHECK (status IN ('ACTIVE','DISABLED')),
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT NULL,
    created_at TEXT NOT NULL,
    last_login_at TEXT NULL,
    require_face INTEGER NOT NULL DEFAULT 0 CHECK (require_face IN (0,1)),
    require_usb INTEGER NOT NULL DEFAULT 1 CHECK (require_usb IN (0,1)),
    recovery_code_hash TEXT NULL,
    recovery_code_created_at TEXT NULL
);

CREATE TABLE IF NOT EXISTS usb_devices (
    id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL,
    volume_identifier TEXT NOT NULL,
    label TEXT,
    status TEXT NOT NULL CHECK (status IN ('ACTIVE','REVOKED')),
    registered_at TEXT NOT NULL,
    last_seen_at TEXT NULL
);

CREATE TABLE IF NOT EXISTS biometric_templates (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE REFERENCES users(id),
    encrypted_embedding BLOB NOT NULL,
    nonce BLOB NOT NULL,
    model_name TEXT NOT NULL,
    detector_backend TEXT NOT NULL,
    embedding_dim INTEGER NOT NULL,
    distance_metric TEXT NOT NULL,
    threshold REAL NOT NULL,
    deepface_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    case_number TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL CHECK (status IN ('OPEN','IN_REVIEW','CLOSED')),
    created_by TEXT NOT NULL REFERENCES users(id),
    assigned_analyst_id TEXT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_items (
    id TEXT PRIMARY KEY,
    evidence_code TEXT NOT NULL UNIQUE,
    case_id TEXT NOT NULL REFERENCES cases(id),
    original_filename TEXT NOT NULL,
    mime_type TEXT,
    original_size INTEGER NOT NULL,
    encrypted_path TEXT NOT NULL,
    encryption_algorithm TEXT NOT NULL,
    original_sha256 TEXT NOT NULL,
    encrypted_sha256 TEXT NOT NULL,
    status TEXT NOT NULL,
    uploaded_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    analyst_note TEXT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    case_id TEXT NULL REFERENCES cases(id),
    sender_id TEXT NOT NULL REFERENCES users(id),
    receiver_id TEXT NOT NULL REFERENCES users(id),
    ciphertext BLOB NOT NULL,
    nonce BLOB NOT NULL,
    algorithm TEXT NOT NULL,
    created_at TEXT NOT NULL,
    read_at TEXT NULL
);

CREATE TABLE IF NOT EXISTS stego_artifacts (
    id TEXT PRIMARY KEY,
    case_id TEXT NULL REFERENCES cases(id),
    source_image_name TEXT NOT NULL,
    output_path TEXT NOT NULL,
    carrier_sha256 TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    actor_id TEXT NULL REFERENCES users(id),
    event_type TEXT NOT NULL,
    target_type TEXT NULL,
    target_id TEXT NULL,
    case_id TEXT NULL REFERENCES cases(id),
    details_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ledger_blocks (
    block_index INTEGER PRIMARY KEY,
    audit_log_id TEXT NOT NULL REFERENCES audit_logs(id),
    timestamp_utc TEXT NOT NULL,
    actor_id TEXT NULL,
    event_type TEXT NOT NULL,
    target_id TEXT NULL,
    payload_hash TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    block_hash TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS app_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_cases_number ON cases(case_number);
CREATE INDEX IF NOT EXISTS idx_evidence_code ON evidence_items(evidence_code);
CREATE INDEX IF NOT EXISTS idx_evidence_case ON evidence_items(case_id);
CREATE INDEX IF NOT EXISTS idx_msg_receiver ON messages(receiver_id, created_at);
CREATE INDEX IF NOT EXISTS idx_msg_sender ON messages(sender_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_logs(actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_case ON audit_logs(case_id);
