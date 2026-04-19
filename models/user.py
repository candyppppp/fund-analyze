"""
user.py — 用户模型与用户管理器

使用 db.supabase_admin（service role key）进行用户管理，
避免在本文件重复初始化 Supabase 客户端。
"""

import hashlib
import logging
import os
from datetime import datetime

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import supabase_admin as supabase

logger = logging.getLogger(__name__)

ADMIN_USERNAME = "candyp"


class User:
    def __init__(self, username: str, password: str,
                 id: str = None, permissions: list = None):
        self.id           = id or username
        self.username     = username
        self.password_hash = self._hash_password(password)
        self.created_at   = datetime.now().isoformat()
        self.permissions  = permissions or []

    def _hash_password(self, password: str) -> str:
        """使用 scrypt + 随机 salt 哈希密码，格式: scrypt$<hex_salt>$<hex_hash>"""
        salt = os.urandom(16)
        h = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
        return f"scrypt${salt.hex()}${h.hex()}"

    def check_password(self, password: str) -> bool:
        """验证密码，兼容旧版裸 SHA-256 哈希（自动迁移）"""
        stored = self.password_hash
        if stored.startswith('scrypt$'):
            # 新格式
            try:
                _, salt_hex, hash_hex = stored.split('$')
                salt = bytes.fromhex(salt_hex)
                expected = bytes.fromhex(hash_hex)
                actual = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
                return actual == expected
            except Exception:
                return False
        else:
            # 旧格式（裸 SHA-256）：验证通过后升级
            old_hash = hashlib.sha256(password.encode()).hexdigest()
            if stored == old_hash:
                # 验证通过，静默升级到 scrypt
                self.password_hash = self._hash_password(password)
                return True
            return False

    def to_dict(self) -> dict:
        return {
            "id":            self.id,
            "username":      self.username,
            "password_hash": self.password_hash,
            "created_at":    self.created_at,
            "permissions":   self.permissions,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        user = cls(data["username"], "dummy",
                   permissions=data.get("permissions", []))
        user.id            = data["id"]
        user.password_hash = data["password_hash"]
        user.created_at    = data.get("created_at", datetime.now().isoformat())
        return user


class UserManager:
    def __init__(self):
        self.users: dict = self._load_users()
        self._ensure_default_user()

    def _load_users(self) -> dict:
        try:
            resp = supabase.table("users").select("*").execute()
            return {u["id"]: User.from_dict(u) for u in resp.data}
        except Exception as e:
            logger.error(f"从 Supabase 加载用户失败: {e}")
            return {}

    def _upsert_user(self, user: "User") -> bool:
        try:
            supabase.table("users").upsert(user.to_dict()).execute()
            return True
        except Exception as e:
            logger.error(f"保存用户 {user.username} 失败: {e}")
            return False

    def _ensure_default_user(self):
        if ADMIN_USERNAME not in {u.username for u in self.users.values()}:
            perms = ["add_fund", "delete_fund", "buy_sell",
                     "view_advice", "manage_accounts"]
            admin = User(ADMIN_USERNAME, "123456", permissions=perms)
            self.users[admin.id] = admin
            self._upsert_user(admin)
            logger.info(f"创建默认管理员: {ADMIN_USERNAME}")

    def get_user(self, username: str):
        return next((u for u in self.users.values()
                     if u.username == username), None)

    def authenticate(self, username: str, password: str):
        user = self.get_user(username)
        if not (user and user.check_password(password)):
            return None
        # check_password 可能已把旧 SHA-256 哈希升级为 scrypt，持久化新哈希
        if user.password_hash.startswith('scrypt$'):
            try:
                self._upsert_user(user)
            except Exception as e:
                logger.warning(f'升级密码哈希持久化失败: {e}')
        return user

    def create_user(self, username: str, password: str,
                    permissions: list = None):
        if self.get_user(username):
            return None
        new = User(username, password, permissions=permissions)
        self.users[new.id] = new
        self._upsert_user(new)
        return new

    def update_user(self, user: "User") -> bool:
        if user.id not in self.users:
            return False
        self.users[user.id] = user
        return self._upsert_user(user)

    def delete_user(self, user_id: str) -> bool:
        if user_id not in self.users:
            return False
        try:
            supabase.table("users").delete().eq("id", user_id).execute()
            del self.users[user_id]
            return True
        except Exception as e:
            logger.error(f"删除用户 {user_id} 失败: {e}")
            return False


user_manager = UserManager()