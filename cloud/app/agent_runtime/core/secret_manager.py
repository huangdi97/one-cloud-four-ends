"""密钥管理器。基于加密的 SQLite 存储，可运行时更新无需重启。"""

import json
import logging
import os
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    _RED = "\033[91m"
    _BOLD = "\033[1m"
    _RESET = "\033[0m"
    print(
        f"{_RED}{_BOLD}"
        "╔══════════════════════════════════════════════════════════════╗\n"
        "║  ⚠️  CRITICAL: cryptography library not installed!         ║\n"
        "║  Secrets will be stored in PLAINTEXT!                      ║\n"
        "║  Install: pip install cryptography                         ║\n"
        "╚══════════════════════════════════════════════════════════════╝"
        f"{_RESET}"
    )
    logger.critical("cryptography not installed — secrets stored in plaintext")


def _get_storage_key() -> bytes:
    key_hex = os.environ.get("SECRET_STORAGE_KEY", "")
    if key_hex:
        return bytes.fromhex(key_hex)
    return os.urandom(32)


def _ensure_storage_key_in_production() -> None:
    env = os.environ.get("ENV", "development").lower()
    if env == "production":
        key_hex = os.environ.get("SECRET_STORAGE_KEY", "")
        if not key_hex:
            _RED = "\033[91m"
            _BOLD = "\033[1m"
            _RESET = "\033[0m"
            msg = (
                f"{_RED}{_BOLD}"
                "╔══════════════════════════════════════════════════════════════╗\n"
                "║  FATAL: SECRET_STORAGE_KEY not set in production mode!      ║\n"
                "║  Refusing to start — set SECRET_STORAGE_KEY env var.        ║\n"
                "╚══════════════════════════════════════════════════════════════╝"
                f"{_RESET}"
            )
            print(msg)
            raise SystemExit(1)


_ensure_storage_key_in_production()


class SecretManager:
    """密钥管理器。当前基于加密的 SQLite 存储，未来可对接 Vault/AWS Secrets Manager。"""

    def __init__(self, db_path: str = ""):
        """Initialize secret manager with encrypted SQLite storage."""
        self._storage_key = _get_storage_key()
        self._local_db = None
        self._external_db = None
        if db_path:
            self.db_path = db_path
        else:
            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            self.db_path = os.path.join(base, "data", "agent_secrets.db")
        self._ensure_table()

    def _get_connection(self) -> sqlite3.Connection:
        if self._external_db is not None:
            return self._external_db
        if self._local_db is None:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self._local_db = sqlite3.connect(self.db_path)
            self._local_db.row_factory = sqlite3.Row
        return self._local_db

    def set_db(self, db):
        """设置外部数据库连接。"""
        self._external_db = db

    def _ensure_table(self):
        conn = self._get_connection()
        conn.execute(
            "CREATE TABLE IF NOT EXISTS agent_secrets ("
            "key_name TEXT PRIMARY KEY, "
            "encrypted_value BLOB, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
            "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS agent_secrets_history ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "key_name TEXT NOT NULL, "
            "encrypted_value BLOB, "
            "rotated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        conn.commit()

    def _encrypt(self, plaintext: str) -> bytes:
        if HAS_CRYPTO:
            aesgcm = AESGCM(self._storage_key)
            nonce = os.urandom(12)
            ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
            return json.dumps({"nonce": nonce.hex(), "ct": ct.hex()}).encode("utf-8")
        return plaintext.encode("utf-8")

    def _decrypt(self, blob: bytes) -> str:
        if HAS_CRYPTO:
            try:
                data = json.loads(blob.decode("utf-8"))
                aesgcm = AESGCM(self._storage_key)
                return aesgcm.decrypt(bytes.fromhex(data["nonce"]), bytes.fromhex(data["ct"]), None).decode("utf-8")
            except (ValueError, KeyError):
                logger.warning("Secret manager解密异常，尝试直接解码", exc_info=True)
                return blob.decode("utf-8")
        return blob.decode("utf-8")

    def encrypt(self, plaintext: str) -> bytes:
        """Encrypt plaintext using AES-GCM or plaintext fallback."""
        return self._encrypt(plaintext)

    def decrypt(self, blob: bytes) -> str:
        """Decrypt a blob previously encrypted by encrypt()."""
        return self._decrypt(blob)

    def set(self, key_name: str, value: str):
        """设置并加密存储密钥。"""
        conn = self._get_connection()
        now = datetime.now().isoformat()
        encrypted = self._encrypt(value)
        existing = conn.execute("SELECT encrypted_value FROM agent_secrets WHERE key_name=?", (key_name,)).fetchone()
        if existing:
            conn.execute(
                "INSERT INTO agent_secrets_history (key_name, encrypted_value) VALUES (?, ?)",
                (key_name, existing["encrypted_value"] if isinstance(existing, sqlite3.Row) else existing[0]),
            )
        conn.execute(
            "INSERT OR REPLACE INTO agent_secrets (key_name, encrypted_value, updated_at) VALUES (?, ?, ?)",
            (key_name, encrypted, now),
        )
        conn.commit()
        logger.info("Secret %s updated", key_name)

    def get(self, key_name: str) -> str | None:
        """获取并解密密钥值。先从SQLite查，查不到时回退到 SECRET_{key_name} 环境变量。"""
        conn = self._get_connection()
        row = conn.execute("SELECT encrypted_value FROM agent_secrets WHERE key_name=?", (key_name,)).fetchone()
        if row:
            return self._decrypt(row["encrypted_value"])
        env_key = f"SECRET_{key_name.upper()}"
        env_val = os.environ.get(env_key)
        if env_val:
            return env_val
        return None

    def list_keys(self) -> list[str]:
        """列出所有密钥名称。"""
        conn = self._get_connection()
        rows = conn.execute("SELECT key_name FROM agent_secrets ORDER BY key_name").fetchall()
        return [r["key_name"] for r in rows]

    def rotate(self, key_name: str, new_value: str):
        """Rotate a secret to a new value."""
        self.set(key_name, new_value)

    def delete(self, key_name: str):
        """删除指定密钥。"""
        conn = self._get_connection()
        conn.execute("DELETE FROM agent_secrets WHERE key_name=?", (key_name,))
        conn.commit()

    def validate_config(self, expected_keys: list[str]) -> dict:
        """验证配置完整性，检查必填密钥是否存在。"""
        present = []
        missing = []
        warnings = []
        for key in expected_keys:
            val = self.get(key)
            if val is not None:
                present.append(key)
            else:
                missing.append(key)
        if not HAS_CRYPTO:
            warnings.append("Cryptography library not installed — secrets stored in plaintext")
        return {
            "missing": missing,
            "present": present,
            "warnings": warnings,
            "crypto_available": HAS_CRYPTO,
        }

    def export_keys(self) -> dict:
        """导出所有密钥名称和状态（不泄露值）。"""
        conn = self._get_connection()
        rows = conn.execute("SELECT key_name, created_at, updated_at FROM agent_secrets ORDER BY key_name").fetchall()
        result = {}
        for r in rows:
            env_key = f"SECRET_{r['key_name'].upper()}"
            result[r["key_name"]] = {
                "exists": True,
                "has_env_fallback": os.environ.get(env_key) is not None,
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
        return result
