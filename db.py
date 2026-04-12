import os
import logging
from urllib.parse import urlparse
from supabase import create_client, Client

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get('SUPABASE_URL', '').strip()  # 添加 strip() 去除空格
SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY', '').strip()
SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '').strip()

# 调试信息
logger.info(f"SUPABASE_URL: '{SUPABASE_URL}'")
logger.info(f"URL长度: {len(SUPABASE_URL)}")
logger.info(f"URL是否以https开头: {SUPABASE_URL.startswith('https://')}")

# 验证 URL 格式
if SUPABASE_URL:
    parsed = urlparse(SUPABASE_URL)
    logger.info(f"URL解析结果: scheme={parsed.scheme}, netloc={parsed.netloc}")

    # 确保 URL 格式正确
    if not SUPABASE_URL.startswith('https://'):
        # 尝试自动修复
        if '.supabase.co' in SUPABASE_URL and not SUPABASE_URL.startswith('http'):
            SUPABASE_URL = f'https://{SUPABASE_URL}'
            logger.info(f"自动修复 URL 为: {SUPABASE_URL}")
        else:
            logger.error(f"URL 格式不正确，必须以 https:// 开头: {SUPABASE_URL}")

# 打印前几个字符（隐藏敏感信息）
if SUPABASE_URL and len(SUPABASE_URL) > 20:
    logger.info(f"URL预览: {SUPABASE_URL[:20]}...")
if SUPABASE_ANON_KEY and len(SUPABASE_ANON_KEY) > 10:
    logger.info(f"Key预览: {SUPABASE_ANON_KEY[:10]}...")

try:
    if SUPABASE_URL and SUPABASE_ANON_KEY:
        # 验证 URL 基本格式
        if not SUPABASE_URL.startswith('https://'):
            raise ValueError(f"Invalid URL format. Must start with https://. Got: {SUPABASE_URL}")

        if not SUPABASE_URL.endswith('.supabase.co'):
            logger.warning(f"URL 可能不是标准的 Supabase URL: {SUPABASE_URL}")

        supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        logger.info("Supabase 客户端创建成功")
    else:
        logger.error("缺少必要的环境变量")
        logger.error(f"URL设置: {'是' if SUPABASE_URL else '否'}")
        logger.error(f"Key设置: {'是' if SUPABASE_ANON_KEY else '否'}")
        supabase = None

except Exception as e:
    logger.error(f"Supabase 初始化失败: {str(e)}")
    logger.error(f"URL: {SUPABASE_URL}")
    supabase = None