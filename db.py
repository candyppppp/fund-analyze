"""
db.py — 统一的 Supabase 客户端单例

所有模块统一从此处导入，避免重复初始化和 key 不一致。
启动时若关键环境变量缺失，直接退出阻止应用启动。
"""

import os
import sys
from supabase import create_client, Client

SUPABASE_URL             = os.environ.get('SUPABASE_URL', '')
SUPABASE_ANON_KEY        = os.environ.get('SUPABASE_ANON_KEY', '')
SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')

_missing = [k for k, v in {
    'SUPABASE_URL':              SUPABASE_URL,
    'SUPABASE_ANON_KEY':         SUPABASE_ANON_KEY,
    'SUPABASE_SERVICE_ROLE_KEY': SUPABASE_SERVICE_ROLE_KEY,
}.items() if not v]

if _missing:
    sys.exit(
        f"[启动失败] 缺少必要的环境变量: {', '.join(_missing)}\n"
        "请在 .env 或 Vercel 环境变量中配置后再启动。"
    )

# 普通 CRUD（受 RLS 约束）
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# 管理操作（绕过 RLS，用于用户管理等）
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)