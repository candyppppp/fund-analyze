"""
middleware.py — Flask 中间件装饰器

包含：
  performance_monitor  记录接口执行耗时
  rate_limit           基于 IP 的滑动窗口限流（120次/分钟）
"""

import time
import logging
from functools import wraps
from flask import request, jsonify

logger = logging.getLogger(__name__)

RATE_LIMIT        = 120  # 每窗口最大请求数
RATE_LIMIT_WINDOW = 60   # 时间窗口（秒）
_request_counts: dict = {}
_last_cleanup: float = 0
_CLEANUP_INTERVAL = 300  # 每5分钟清理一次过期 IP 条目


def _cleanup_expired():
    """清理超过窗口期的 IP 条目，防止字典无限膨胀"""
    global _last_cleanup
    now = time.time()
    if now - _last_cleanup < _CLEANUP_INTERVAL:
        return
    _last_cleanup = now
    expired = [ip for ip, ts in _request_counts.items()
               if not any(now - t < RATE_LIMIT_WINDOW for t in ts)]
    for ip in expired:
        del _request_counts[ip]
    if expired:
        logger.debug(f'[rate_limit] 清理 {len(expired)} 个过期 IP 条目')


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
        _cleanup_expired()  # 定期清理，防内存泄漏
        ip  = request.remote_addr
        now = time.time()
        timestamps = [t for t in _request_counts.get(ip, []) if now - t < RATE_LIMIT_WINDOW]
        if len(timestamps) >= RATE_LIMIT:
            logger.warning(f"IP {ip} 请求过频 ({len(timestamps)}/{RATE_LIMIT})")
            return jsonify({'error': '请求过于频繁，请稍后再试'}), 429
        timestamps.append(now)
        # timestamps 此时一定非空（刚追加了 now），直接更新
        _request_counts[ip] = timestamps
        return func(*args, **kwargs)
    return wrapper