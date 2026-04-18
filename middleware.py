"""
middleware.py — Flask 中间件装饰器

包含：
  performance_monitor  记录接口执行耗时
  rate_limit           基于 IP 的滑动窗口限流（60次/分钟）
"""

import time
import logging
from functools import wraps
from flask import request, jsonify

logger = logging.getLogger(__name__)

RATE_LIMIT        = 120  # 每窗口最大请求数（提高上限，前端已降频，此处作兜底）
RATE_LIMIT_WINDOW = 60   # 时间窗口（秒）
_request_counts: dict = {}


def performance_monitor(func):
    """记录接口执行耗时"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        t0 = time.time()
        result = func(*args, **kwargs)
        logger.info(f"{func.__name__} 执行时间: {(time.time()-t0)*1000:.2f}ms")
        return result
    return wrapper


def rate_limit(func):
    """滑动窗口 IP 限流"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        ip  = request.remote_addr
        now = time.time()
        timestamps = [t for t in _request_counts.get(ip, []) if now - t < RATE_LIMIT_WINDOW]
        if len(timestamps) >= RATE_LIMIT:
            logger.warning(f"IP {ip} 请求过频 ({len(timestamps)}/{RATE_LIMIT})")
            return jsonify({'error': '请求过于频繁，请稍后再试'}), 429
        timestamps.append(now)
        if timestamps:
            _request_counts[ip] = timestamps
        else:
            # 清理空键，防止字典无限膨胀
            _request_counts.pop(ip, None)
        return func(*args, **kwargs)
    return wrapper