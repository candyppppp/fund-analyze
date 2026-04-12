# db.py
import os
import logging
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# 从环境变量读取
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY')
SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')

# 日志输出（不要输出完整密钥，只输出长度）
logger.info(f"🔧 配置检查:")
logger.info(f"   SUPABASE_URL 存在: {bool(SUPABASE_URL)}")
logger.info(f"   SUPABASE_URL 长度: {len(SUPABASE_URL) if SUPABASE_URL else 0}")
logger.info(f"   SUPABASE_URL 开头: {SUPABASE_URL[:20] if SUPABASE_URL else 'None'}..." if SUPABASE_URL else 'None')
logger.info(f"   SUPABASE_ANON_KEY 存在: {bool(SUPABASE_ANON_KEY)}")
logger.info(f"   SUPABASE_ANON_KEY 长度: {len(SUPABASE_ANON_KEY) if SUPABASE_ANON_KEY else 0}")

# 验证 URL 格式
if SUPABASE_URL:
    if not SUPABASE_URL.startswith('https://'):
        logger.warning(f"⚠️  URL 没有以 https:// 开头: {SUPABASE_URL}")
        if SUPABASE_URL.startswith('http://'):
            logger.warning("⚠️  HTTP 不安全，建议使用 HTTPS")
        else:
            # 尝试自动添加 https://
            if '.supabase.co' in SUPABASE_URL:
                SUPABASE_URL = f'https://{SUPABASE_URL}'
                logger.info(f"✅ 已自动修复 URL: {SUPABASE_URL}")

# 初始化客户端
try:
    if SUPABASE_URL and SUPABASE_ANON_KEY:
        # 验证 URL
        if not SUPABASE_URL.startswith('https://'):
            raise ValueError(f"URL 必须使用 HTTPS: {SUPABASE_URL}")
        if not SUPABASE_URL.endswith('.supabase.co'):
            logger.warning(f"⚠️  URL 不是标准的 Supabase 格式: {SUPABASE_URL}")

        supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        logger.info("✅ Supabase 客户端创建成功")
    else:
        logger.error("❌ 缺少 Supabase 配置")
        logger.error(f"   缺少 URL: {not SUPABASE_URL}")
        logger.error(f"   缺少 ANON_KEY: {not SUPABASE_ANON_KEY}")
        supabase = None

except Exception as e:
    logger.error(f"❌ Supabase 初始化失败: {e}")
    logger.error(f"   使用的 URL: {SUPABASE_URL[:50] if SUPABASE_URL else 'None'}...")
    supabase = None

# 初始化管理客户端
try:
    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        logger.info("✅ Supabase 管理客户端创建成功")
    else:
        logger.warning("⚠️  Supabase 管理客户端未创建（缺少服务密钥）")
        supabase_admin = None
except Exception as e:
    logger.error(f"❌ Supabase 管理客户端初始化失败: {e}")
    supabase_admin = None