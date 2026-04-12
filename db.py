"""
db.py — 统一的 Supabase 客户端单例
"""
import os
from supabase import create_client, Client

SUPABASE_URL              = os.environ.get('SUPABASE_URL', '')
SUPABASE_ANON_KEY         = os.environ.get('SUPABASE_ANON_KEY', '')
SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')

# 延迟初始化：环境变量为空时返回 None，避免启动崩溃
supabase: Client = (
    create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    if SUPABASE_URL and SUPABASE_ANON_KEY else None
)

supabase_admin: Client = (
    create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY else None
)