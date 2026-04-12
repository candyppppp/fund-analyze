import os
import logging
from supabase import create_client, Client

logger = logging.getLogger(__name__)

SUPABASE_URL              = os.environ.get('SUPABASE_URL', '')
SUPABASE_ANON_KEY         = os.environ.get('SUPABASE_ANON_KEY', '')
SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY) if SUPABASE_URL and SUPABASE_ANON_KEY else None
except Exception as e:
    logger.error(f"Supabase 初始化失败: {e}, URL={SUPABASE_URL}")
    supabase = None

try:
    supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY) if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY else None
except Exception as e:
    logger.error(f"Supabase admin 初始化失败: {e}")
    supabase_admin = None