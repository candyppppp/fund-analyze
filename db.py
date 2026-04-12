import os
import logging
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# 1. 直接从环境变量读取
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY')
SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')

# 初始化客户端
supabase: Client = None
supabase_admin: Client = None

try:
    if SUPABASE_URL and SUPABASE_ANON_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    else:
        logger.warning("Supabase URL or Anon Key is missing in environment variables.")

    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    else:
        logger.warning("Supabase URL or Service Role Key is missing in environment variables.")

except Exception as e:
    logger.error(f"Supabase initialization failed: {e}")