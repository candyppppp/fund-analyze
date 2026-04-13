from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from flask_cors import CORS

from models.fund import Fund

from models.user import user_manager

from utils.indicators import calculate_rsi, calculate_volatility

from utils.data_sources import data_source_manager

from utils.fund_recommender import get_recommended_funds as get_recommended_funds_engine

import time
import requests
import json
import re
from datetime import datetime, timedelta
import logging

from db import supabase, supabase_admin
import os

# 检查是否在 Vercel 环境中
is_vercel = os.environ.get('VERCEL') is not None

# 配置日志处理器
handlers = [logging.StreamHandler()]

# 只在本地环境中使用文件日志
if not is_vercel:
    handlers.append(logging.FileHandler('fund_analyze.log'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=handlers
)

logger = logging.getLogger(__name__)

import os

# 获取应用根目录
base_dir = os.path.dirname(os.path.abspath(__file__))

# 显式配置Flask应用
app = Flask(__name__,
            static_folder=os.path.join(base_dir, 'static'),
            template_folder=os.path.join(base_dir, 'templates'))
import os as _os
_cors_origins = _os.environ.get('CORS_ORIGINS', '').split(',')
_cors_origins = [o.strip() for o in _cors_origins if o.strip()] or ['*']

import secrets as _secrets

def generate_csrf_token():
    """生成并存储 CSRF token 到 session"""
    if '_csrf_token' not in session:
        session['_csrf_token'] = _secrets.token_hex(32)
    return session['_csrf_token']

def validate_csrf_token():
    """验证 POST 请求的 CSRF token"""
    token = request.form.get('_csrf_token') or request.headers.get('X-CSRF-Token')
    return token and token == session.get('_csrf_token')

app.jinja_env.globals['csrf_token'] = generate_csrf_token

CORS(app, supports_credentials=True, origins=_cors_origins)

# 添加密钥用于会话管理
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key-here')
app.config['PERMANENT_SESSION_LIFETIME'] = __import__('datetime').timedelta(hours=24)

# 数据文件路径
DATA_FILE = 'funds_data.json'
# 用户数据目录
USER_DATA_DIR = 'user_data'

# 确保用户数据目录存在
if not is_vercel:
    os.makedirs(USER_DATA_DIR, exist_ok=True)

# 加载基金数据
funds = []
last_save_time = 0


def get_user_data_file(username):
    """获取用户数据文件路径"""
    return os.path.join(USER_DATA_DIR, f"{username}_funds.json")


def load_funds(username=None):
    """从 Supabase 或本地文件加载基金数据"""
    global funds
    logger.info('开始加载基金数据')

    try:
        # 从 Supabase 加载基金数据
        if username:
            response = supabase.table('funds').select('*').eq('username', username).execute()
        else:
            response = supabase.table('funds').select('*').execute()

        fund_data = response.data
        funds = []

        for data in fund_data:
            # 重建Fund对象
            try:
                fund = Fund(
                    data['name'],
                    data['code'],
                    data['prices'],
                    data['dates'],
                    data['returns'],
                    data.get('volumes', [])
                )
                # 恢复其他属性
                fund.id = data['id']
                fund.rsi = data.get('rsi', 0)
                fund.volatility = data.get('volatility', 0)
                fund.macd = data.get('macd', [0, 0, 0])
                fund.kdj = data.get('kdj', [0, 0, 0])
                fund.bollinger_bands = data.get('bollinger_bands', [0, 0, 0])
                fund.atr = data.get('atr', 0)
                fund.volume_ratio = data.get('volume_ratio', 0)
                fund.predicted_return = data.get('predicted_return', 0)
                fund.prediction_confidence = data.get('prediction_confidence', 0.5)
                fund.previous_day_return = data.get('previous_day_return', 0)
                fund.username = data.get('username', username)
                fund.nav_updated_at = data.get('nav_updated_at', None)
                funds.append(fund)
            except Exception as e:
                logger.error(f"重建基金对象失败: {e}")
                continue

        # 更新ID计数器
        if funds:
            Fund.id_counter = max(fund.id for fund in funds) + 1
        logger.info(f"成功加载 {len(funds)} 只基金")
    except Exception as e:
        logger.error(f"从 Supabase 加载基金数据失败: {e}")
        # 从本地文件加载数据
        try:
            data_file = get_user_data_file(username or 'default')
            if os.path.exists(data_file):
                with open(data_file, 'r', encoding='utf-8') as f:
                    fund_data = json.load(f)
                funds = []
                for data in fund_data:
                    try:
                        fund = Fund(
                            data['name'],
                            data['code'],
                            data['prices'],
                            data['dates'],
                            data['returns'],
                            data.get('volumes', [])
                        )
                        # 恢复其他属性
                        fund.id = data['id']
                        fund.rsi = data.get('rsi', 0)
                        fund.volatility = data.get('volatility', 0)
                        fund.macd = data.get('macd', [0, 0, 0])
                        fund.kdj = data.get('kdj', [0, 0, 0])
                        fund.bollinger_bands = data.get('bollinger_bands', [0, 0, 0])
                        fund.atr = data.get('atr', 0)
                        fund.volume_ratio = data.get('volume_ratio', 0)
                        fund.predicted_return = data.get('predicted_return', 0)
                        fund.prediction_confidence = data.get('prediction_confidence', 0.5)
                        fund.previous_day_return = data.get('previous_day_return', 0)
                        fund.username = data.get('username', username)
                        fund.nav_updated_at = data.get('nav_updated_at', None)
                        funds.append(fund)
                    except Exception as e:
                        logger.error(f"从本地文件重建基金对象失败: {e}")
                        continue
                # 更新ID计数器
                if funds:
                    Fund.id_counter = max(fund.id for fund in funds) + 1
                logger.info(f"从本地文件成功加载 {len(funds)} 只基金")
            else:
                logger.warning(f"本地数据文件不存在: {data_file}")
                funds = []
        except Exception as e:
            logger.error(f"从本地文件加载基金数据失败: {e}")
            funds = []


def save_funds(username=None):
    """保存基金数据到 Supabase（upsert，60秒节流）"""
    global funds, last_save_time

    # 节流：60 秒内不重复写，避免每次 GET /api/funds 都触发写库
    now = time.time()
    if now - last_save_time < 60:
        logger.debug('save_funds 节流跳过（距上次写入 %.0f 秒）', now - last_save_time)
        return
    last_save_time = now

    logger.info('开始保存基金数据到 Supabase')
    try:
        rows = []
        for fund in funds:
            fund_data = fund.to_dict()
            fund_data['username'] = username or fund.username
            rows.append(fund_data)
        if rows:
            supabase.table('funds').upsert(rows).execute()
            logger.info(f'成功 upsert {len(rows)} 只基金')
        logger.info(f"成功保存 {len(funds)} 只基金到 Supabase")
    except Exception as e:
        logger.error(f"保存基金数据到 Supabase 失败: {e}")

    # Vercel 无持久文件系统，仅用 Supabase 持久化


# 初始化加载数据
try:
    load_funds()
except Exception as e:
    logger.error(f'初始化加载数据失败: {e}')
    funds = []


# 获取基金持仓数据
_holdings_cache = {}   # {code: (timestamp, holdings_data)}
_HOLDINGS_TTL = 7 * 24 * 3600  # 7天，持仓数据按季度更新

def get_fund_holdings(code):
    """获取基金的持仓数据

    东方财富 pingzhongdata 接口在 2025 年后移除了 Data_holdStock / Data_holdStockNew，
    现在改用 stockCodesNew（格式：市场号.股票代码，如 "0.002384"）和 stockCodes。
    权重数据已被接口移除，改为从 Data_fundSharesPositions 取最新总仓位，
    各股票按等权分配（总仓位 / 持仓数量）。
    """
    # 内存缓存：持仓按季度公告，7天内直接返回缓存
    _now = time.time()
    if code in _holdings_cache:
        _ts, _cached = _holdings_cache[code]
        if _now - _ts < _HOLDINGS_TTL:
            logger.debug(f'持仓缓存命中: {code}')
            return _cached

    holdings = {'stocks': [], 'stock_ratio': 0}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://fund.eastmoney.com/",
    }

    try:
        url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code != 200:
            logger.warning(f"持仓接口 {code}: HTTP {resp.status_code}")
            return holdings

        text = resp.text
        stock_codes = []

        # ── 优先：stockCodesNew，格式 "市场号.股票代码"，如 "0.002384" ──────────
        m = re.search(r'var stockCodesNew\s*=\s*\[(.*?)\];', text)
        if m:
            try:
                raw = json.loads('[' + m.group(1) + ']')
                for item in raw:
                    # 取小数点后的部分作为股票代码
                    parts = str(item).split('.')
                    if len(parts) == 2:
                        c = parts[1].zfill(6)  # 补齐6位
                        if len(c) == 6 and c.isdigit():
                            stock_codes.append(c)
                logger.info(f"持仓 {code}: stockCodesNew 解析到 {len(stock_codes)} 只股票")
            except Exception as e:
                logger.warning(f"持仓 {code}: stockCodesNew 解析失败 {e}")

        # ── 回退：stockCodes，格式 "0023840"（7位，去掉首位市场号）────────────
        if not stock_codes:
            m = re.search(r'var stockCodes\s*=\s*\[(.*?)\];', text)
            if m:
                try:
                    raw = json.loads('[' + m.group(1) + ']')
                    for item in raw:
                        s = str(item)
                        # 格式通常是7位："0023840" → 去掉第一位市场标识
                        if len(s) == 7:
                            c = s[1:]
                        elif len(s) == 6:
                            c = s
                        else:
                            c = re.sub(r'\D', '', s)[-6:]
                        if len(c) == 6 and c.isdigit():
                            stock_codes.append(c)
                    logger.info(f"持仓 {code}: stockCodes 解析到 {len(stock_codes)} 只股票")
                except Exception as e:
                    logger.warning(f"持仓 {code}: stockCodes 解析失败 {e}")

        if not stock_codes:
            logger.warning(f"持仓 {code}: 未找到任何股票代码")
            return holdings

        # ── 获取总仓位：从 Data_fundSharesPositions 取最新一条 ────────────────
        stock_ratio = 0.0
        m_pos = re.search(r'var Data_fundSharesPositions\s*=\s*\[(.*?)\];', text, re.DOTALL)
        if m_pos:
            try:
                positions = json.loads('[' + m_pos.group(1) + ']')
                if positions:
                    # 每项格式 [时间戳, 仓位百分比]，取最后一条
                    latest = positions[-1]
                    if isinstance(latest, list) and len(latest) >= 2:
                        stock_ratio = float(latest[1])
            except Exception as e:
                logger.warning(f"持仓 {code}: Data_fundSharesPositions 解析失败 {e}")

        # ── 回退总仓位：Data_assetAllocation ─────────────────────────────────
        if stock_ratio == 0:
            m_asset = re.search(r'var Data_assetAllocation\s*=\s*\[(.*?)\];', text, re.DOTALL)
            if m_asset:
                try:
                    for item in json.loads('[' + m_asset.group(1) + ']'):
                        if item.get('assetType') == '股票' or item.get('name') == '股票':
                            stock_ratio = float(item.get('ratio', 0)) * 100
                            break
                except Exception as _e:

                    logger.warning(f"caught exception: {_e}")

        # ── 等权分配：总仓位 / 持仓股票数 ────────────────────────────────────
        n = len(stock_codes)
        weight_each = round(stock_ratio / n, 2) if stock_ratio > 0 and n > 0 else 0.0

        for c in stock_codes:
            holdings['stocks'].append({
                'code': c,
                'name': get_stock_name(c),  # 通过新浪财经查名称
                'weight': weight_each,
            })

        holdings['stock_ratio'] = stock_ratio
        logger.info(f"持仓 {code}: 共 {n} 只股票，总仓位 {stock_ratio}%，等权 {weight_each}%/只")

    except Exception as e:
        logger.error(f"获取基金 {code} 持仓数据失败: {e}")

    _holdings_cache[code] = (time.time(), holdings)
    return holdings


# 获取股票名称
def get_stock_name(stock_code):
    """从多个数据源获取股票名称"""
    # 不再使用硬编码的股票列表，直接从API获取

    # 数据源1: 东方财富API (优先使用，更稳定)
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": "https://fund.eastmoney.com/"
        }

        # 为东方财富API添加市场前缀
        if stock_code.startswith('6'):
            full_code = f"sh{stock_code}"
        elif stock_code.startswith('0') or stock_code.startswith('3'):
            full_code = f"sz{stock_code}"
        elif stock_code.startswith('688'):
            full_code = f"sh{stock_code}"
        else:
            full_code = stock_code

        stock_url = f"https://emweb.securities.eastmoney.com/PC_HSF10/StockStructure/Index?type=web&code={full_code}"
        response = requests.get(stock_url, headers=headers, timeout=3)

        if response.status_code == 200:
            stock_data = response.text
            # 提取股票名称
            name_match = re.search(r'<title>(.*?)_股本结构', stock_data)
            if name_match:
                stock_name = name_match.group(1)
                if stock_name and stock_name != '' and '股本结构' not in stock_name:
                    return stock_name
    except Exception as _e:

        logger.warning(f"caught exception: {_e}")

    # 数据源2: 新浪财经API
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": "https://finance.sina.com.cn/"
        }

        # 对于沪市股票，需要添加sh前缀；深市股票添加sz前缀
        if stock_code.startswith('6'):
            full_code = f"sh{stock_code}"
        else:
            full_code = f"sz{stock_code}"

        stock_url = f"http://hq.sinajs.cn/list={full_code}"
        response = requests.get(stock_url, headers=headers, timeout=3)

        if response.status_code == 200:
            stock_data = response.text
            # 解析股票数据
            name_match = re.search(r'"(.*?),', stock_data)
            if name_match:
                stock_name = name_match.group(1)
                if stock_name and stock_name != '' and stock_name != 'null':
                    return stock_name
    except Exception as _e:

        logger.warning(f"caught exception: {_e}")

    # 数据源3: 百度股票API
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        stock_url = f"https://gupiao.baidu.com/stock/{stock_code}.html"
        response = requests.get(stock_url, headers=headers, timeout=3)

        if response.status_code == 200:
            stock_data = response.text
            # 提取股票名称
            name_match = re.search(r'<title>(.*?)_股票行情', stock_data)
            if name_match:
                stock_name = name_match.group(1)
                if stock_name and stock_name != '' and '股票行情' not in stock_name:
                    return stock_name
    except Exception as _e:

        logger.warning(f"caught exception: {_e}")

    # 数据源4: 同花顺API
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        stock_url = f"https://basic.10jqka.com.cn/{stock_code}/"
        response = requests.get(stock_url, headers=headers, timeout=3)

        if response.status_code == 200:
            stock_data = response.text
            # 提取股票名称
            name_match = re.search(r'<title>(.*?)_同花顺', stock_data)
            if name_match:
                stock_name = name_match.group(1)
                if stock_name and stock_name != '' and '同花顺' not in stock_name:
                    return stock_name
    except Exception as _e:

        logger.warning(f"caught exception: {_e}")

    # 如果所有数据源都失败，返回默认名称
    return f'股票{stock_code}'


# 批量获取股票实时数据
def get_batch_stock_real_time_data(stock_codes):
    """批量获取股票的实时数据，减少API调用次数"""
    results = {}

    # 批量获取股票数据
    if stock_codes:
        # 限制批量请求数量，避免API限制
        batch_size = 10
        for i in range(0, len(stock_codes), batch_size):
            batch_codes = stock_codes[i:i + batch_size]
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Referer": "https://finance.sina.com.cn/"
                }

                # 构建批量API URL
                full_codes = []
                for stock_code in batch_codes:
                    if stock_code.startswith('6'):
                        full_codes.append(f"sh{stock_code}")
                    else:
                        full_codes.append(f"sz{stock_code}")

                code_str = ",".join(full_codes)
                stock_url = f"http://hq.sinajs.cn/list={code_str}"
                response = requests.get(stock_url, headers=headers, timeout=3)  # 减少超时时间

                if response.status_code == 200:
                    stock_data = response.text

                    # 解析数据
                    lines = stock_data.strip().split('\n')
                    for line in lines:
                        if line:
                            try:
                                # 提取股票代码
                                code_part = line.split('=')[0]
                                stock_code = code_part.split('_')[-1].replace('sh', '').replace('sz', '')
                                if stock_code in batch_codes:
                                    # 解析股票数据
                                    data_part = line.split('=', 1)[1].strip('"')
                                    stock_info = data_part.split(',')
                                    if len(stock_info) > 3:
                                        # 计算涨跌幅
                                        current_price = float(stock_info[3])
                                        previous_close = float(stock_info[2])
                                        if previous_close > 0:
                                            change = (current_price - previous_close) / previous_close
                                            change_amount = current_price - previous_close
                                            stock_data = {
                                                'current_price': current_price,
                                                'change_amount': change_amount,
                                                'change_ratio': change
                                            }
                                            results[stock_code] = stock_data
                            except Exception as e:
                                logger.debug(f"解析股票数据失败: {e}")
                else:
                    for stock_code in batch_codes:
                        results[stock_code] = {
                            'current_price': 0,
                            'change_amount': 0,
                            'change_ratio': 0
                        }
            except Exception as e:
                logger.debug(f"获取批量股票数据失败: {e}")
                for stock_code in batch_codes:
                    results[stock_code] = {
                        'current_price': 0,
                        'change_amount': 0,
                        'change_ratio': 0
                    }

    return results


# 获取股票实时数据
def get_stock_real_time_data(stock_code):
    """获取股票的实时数据，包括当前价格、涨跌金额和涨跌比例"""
    # 调用批量获取函数
    results = get_batch_stock_real_time_data([stock_code])
    return results.get(stock_code, {
        'current_price': 0,
        'change_amount': 0,
        'change_ratio': 0
    })


# 获取市场数据（大盘指数和行业板块）
def get_market_data():
    """获取市场数据，包括主要大盘指数和行业板块的实时数据"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": "https://finance.sina.com.cn/"
        }

        # 主要大盘指数
        index_codes = {
            'sh000001': '上证指数',
            'sz399001': '深证成指',
            'sz399006': '创业板指',
            'sh000300': '沪深300'
        }

        # 主要行业板块
        sector_codes = {
            'sh000037': '医药制造',
            'sh000039': '食品饮料',
            'sh000043': '信息技术',
            'sh000063': '电子元件',
            'sh000048': '银行',
            'sh000046': '房地产',
            'sh000042': '电力',
            'sh000044': '通信设备',
            'sh000041': '航天航空',
            'sh000038': '纺织服装',
            'sh000040': '有色金属',
            'sh000045': '建筑材料',
            'sh000047': '交通运输',
            'sh000049': '煤炭',
            'sh000050': '石油',
            'sh000051': '钢铁',
            'sh000052': '化工',
            'sh000053': '机械',
            'sh000054': '汽车'
        }

        # 构建API URL
        all_codes = list(index_codes.keys()) + list(sector_codes.keys())
        code_str = ",".join(all_codes)
        market_url = f"http://hq.sinajs.cn/list={code_str}"
        response = requests.get(market_url, headers=headers, timeout=5)

        if response.status_code == 200:
            market_data = response.text

            # 解析数据
            lines = market_data.strip().split('\n')
            result = {
                'indices': {},
                'sectors': {}
            }

            for line in lines:
                if '=' in line:
                    try:
                        code_part, data_part = line.split('=', 1)
                        code = code_part.split('_')[-1]
                        data = data_part.strip('"').split(',')

                        if len(data) > 3:
                            current_price = float(data[3])
                            previous_close = float(data[2])
                            if previous_close > 0:
                                change = (current_price - previous_close) / previous_close
                                change_amount = current_price - previous_close

                                if code in index_codes:
                                    result['indices'][index_codes[code]] = {
                                        'code': code,
                                        'current_price': current_price,
                                        'change_amount': change_amount,
                                        'change_ratio': change
                                    }
                                elif code in sector_codes:
                                    result['sectors'][sector_codes[code]] = {
                                        'code': code,
                                        'current_price': current_price,
                                        'change_amount': change_amount,
                                        'change_ratio': change
                                    }
                    except Exception as e:
                        logger.debug(f"解析市场数据失败: {e}")

            return result
        else:
            return {'indices': {}, 'sectors': {}}
    except Exception as e:
        logger.debug(f"获取市场数据失败: {e}")
        return {'indices': {}, 'sectors': {}}


# 获取基金数据
def get_fund_data(code):
    try:
        # 初始化变量
        name = f'基金{code}'
        prices = []
        dates = []
        returns = []

        # 从新浪财经API获取最新净值
        latest_nav_data = data_source_manager.get_fund_latest_nav(code)
        if latest_nav_data:
            name = latest_nav_data['name']

        # 从数据源获取历史数据（包含最新净值）
        historical_data = data_source_manager.get_fund_historical_data(code)
        if historical_data:
            prices = historical_data['prices']
            dates = historical_data['dates']
            returns = historical_data['returns']
            logger.info(f"从 {historical_data['source']} 获取基金 {code} 历史数据，共 {len(prices)} 条记录")

        # 如果没有历史数据，使用新浪财经的最新净值
        if not prices and latest_nav_data and latest_nav_data['jzrq'] and latest_nav_data['dwjz']:
            date_str = latest_nav_data['jzrq']
            nav = latest_nav_data['dwjz']
            prices.append(nav)
            dates.append(date_str)
            returns.append(0)
            logger.info(f"从新浪财经获取基金 {code} 最新数据: 日期={date_str}, 净值={nav}")

        logger.info(f"获取基金 {code} 数据成功，共 {len(prices)} 条记录")
        return name, prices, dates, returns
    except Exception as e:
        logger.error(f"获取基金数据失败: {e}")
        # 如果所有尝试都失败，返回空数据
        return f'基金{code}', [], [], []


@app.route('/')
def index():
    # 检查用户是否已登录
    if 'username' not in session:
        return redirect(url_for('login'))
    # 加载用户的基金数据
    load_funds(session['username'])
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.method == 'POST' and not validate_csrf_token():
            return jsonify({'error': 'CSRF 验证失败'}), 403
        username = request.form.get('username')
        password = request.form.get('password')

        # 验证用户身份
        user = user_manager.authenticate(username, password)
        if user:
            # 设置会话
            session['username'] = user.username
            session['is_admin'] = (username == 'candyp')  # candyp 作为管理员
            session.permanent = True  # 使会话持久化

            # 加载用户的基金数据
            load_funds(user.username)

            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='用户名或密码错误')

    return render_template('login.html')


# 移除注册路由，因为不需要用户自行注册
# @app.route('/register', methods=['GET', 'POST'])
# def register():
#     if request.method == 'POST':
#         username = request.form.get('username')
#         password = request.form.get('password')
#
#         # 创建新用户
#         user = user_manager.create_user(username, password)
#         if user:
#             # 自动登录
#             session['username'] = user.username
#             session.permanent = True
#
#             # 初始化用户的基金数据
#             load_funds(user.username)
#
#             return redirect(url_for('index'))
#         else:
#             return render_template('register.html', error='用户名已存在')
#
#     return render_template('register.html')

@app.route('/logout')
def logout():
    # 清除会话
    session.clear()
    return redirect(url_for('login'))


@app.route('/api/check-admin', methods=['GET'])
def check_admin():
    # 检查用户是否为管理员
    is_admin = session.get('is_admin', False)
    return jsonify({'is_admin': is_admin})


@app.route('/account-management', methods=['GET', 'POST'])
def account_management():
    # 检查用户是否已登录且是管理员
    if 'username' not in session or session.get('is_admin') is not True:
        return redirect(url_for('login'))

    error = None
    success = None

    if request.method == 'POST' and not validate_csrf_token():
        return jsonify({'error': 'CSRF 验证失败'}), 403
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add':
            # 新增账户
            new_username = request.form.get('new_username')
            new_password = request.form.get('new_password')
            permissions = request.form.getlist('permissions')

            if new_username and new_password:
                # 创建新用户
                user = user_manager.create_user(new_username, new_password, permissions)
                if user:
                    success = '账户添加成功'
                else:
                    error = '用户名已存在'
            else:
                error = '请填写完整的账户信息'

        elif action == 'delete':
            # 删除账户
            username = request.form.get('username')
            if username and username != 'candyp':  # 不允许删除管理员账户
                # 找到用户并删除
                user_to_delete = None
                for user_id, user in user_manager.users.items():
                    if user.username == username:
                        user_to_delete = user_id
                        break

                if user_to_delete:
                    user_manager.delete_user(user_to_delete)
                    success = '账户删除成功'
                else:
                    error = '账户不存在'
            else:
                error = '无法删除管理员账户'

    # 获取所有用户
    users = list(user_manager.users.values())

    return render_template('account_management.html', users=users, error=error, success=success)


# 性能监控装饰器
import time
from functools import wraps


def performance_monitor(func):
    """性能监控装饰器"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = (end_time - start_time) * 1000
        logger.info(f"{func.__name__} 执行时间: {execution_time:.2f}ms")
        return result

    return wrapper


# 请求限流
from flask import request, jsonify

# 简单的内存限流实现
request_counts = {}
RATE_LIMIT = 60  # 每分钟最大请求数
RATE_LIMIT_WINDOW = 60  # 时间窗口（秒）


def rate_limit(func):
    """请求限流装饰器"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        ip = request.remote_addr
        now = time.time()

        # 清理过期的请求记录
        if ip in request_counts:
            # 过滤出时间窗口内的请求
            request_counts[ip] = [t for t in request_counts[ip] if now - t < RATE_LIMIT_WINDOW]
            # 检查是否超过限流
            if len(request_counts[ip]) >= RATE_LIMIT:
                logger.warning(f"IP {ip} 请求过于频繁")
                return jsonify({'error': '请求过于频繁，请稍后再试'}), 429
        else:
            request_counts[ip] = []

        # 记录本次请求
        request_counts[ip].append(now)
        return func(*args, **kwargs)

    return wrapper


@app.route('/api/funds', methods=['GET'])
@performance_monitor
@rate_limit
def get_funds():
    try:
        if 'username' not in session:
            return jsonify({'error': '未登录'}), 401

        basic_only = request.args.get('basic', 'false').lower() == 'true'

        if basic_only:
            basic_funds = [{'id': f.id, 'code': f.code, 'name': f.name} for f in funds]
            return jsonify(basic_funds)

        logger.info('获取基金列表')
        today = datetime.now().strftime('%Y-%m-%d')
        updated_funds = []

        try:
            market_data = get_market_data()

            for fund in funds:
                try:
                    # ── 判断是否需要更新历史净值 ──────────────────────────────
                    # nav_updated_at 记录上次拉取历史数据的日期
                    # 如果今天已经更新过，直接用缓存；否则做增量更新
                    already_updated_today = (
                            fund.nav_updated_at is not None and
                            str(fund.nav_updated_at)[:10] == today
                    )

                    if already_updated_today:
                        # ── 缓存命中：只拉实时预估收益率，不重新拉历史 ──────
                        logger.info(f'基金 {fund.code} 今日已更新历史净值，跳过重拉')
                        real_time_estimated_return = data_source_manager.get_fund_estimated_return(fund.code)
                    else:
                        # ── 缓存未命中：增量拉取今日新净值，追加到历史数据 ──
                        logger.info(f'基金 {fund.code} 开始增量更新净值')
                        name, new_prices, new_dates, new_returns = get_fund_data(fund.code)
                        real_time_estimated_return = data_source_manager.get_fund_estimated_return(fund.code)

                        if new_prices and new_dates:
                            # 只追加缓存中没有的新日期，不替换历史数据
                            existing_dates = set(fund.dates)
                            appended = 0
                            for d, p, r in zip(new_dates, new_prices, new_returns):
                                if d not in existing_dates:
                                    fund.dates.append(d)
                                    fund.prices.append(p)
                                    fund.returns.append(r)
                                    existing_dates.add(d)
                                    appended += 1

                            # 重新按日期排序（保证顺序正确）
                            if appended > 0:
                                combined = sorted(zip(fund.dates, fund.prices, fund.returns))
                                fund.dates = [x[0] for x in combined]
                                fund.prices = [x[1] for x in combined]
                                fund.returns = [x[2] for x in combined]
                                logger.info(f'基金 {fund.code}: 追加 {appended} 条新净值，'
                                            f'共 {len(fund.prices)} 条')
                            else:
                                logger.info(f'基金 {fund.code}: 无新净值（已是最新）')

                        # 更新技术指标
                        fund.update_prices(fund.prices, fund.dates, fund.returns,
                                           market_data=market_data)
                        # 标记今日已更新
                        fund.nav_updated_at = today

                    # ── 实时预估收益率 + 预测（每次都更新，不缓存） ──────────
                    holdings = get_fund_holdings(fund.code)
                    if real_time_estimated_return:
                        fund.predicted_return = fund.calculate_predicted_return(
                            stock_holdings=holdings,
                            market_data=market_data,
                            real_time_estimated_return=real_time_estimated_return,
                        )
                        # 缓存原始估值字段，投资建议接口直接读，避免重复请求
                        fund.gszzl = real_time_estimated_return.get('gszzl')
                        fund.gsz = real_time_estimated_return.get('gsz')
                        fund.gztime = real_time_estimated_return.get('gztime')
                        fund.est_source = real_time_estimated_return.get('source', '')
                        fund.has_realtime = True
                    else:
                        fund.predicted_return = fund.calculate_predicted_return(
                            stock_holdings=holdings, market_data=market_data,
                        )
                        fund.gszzl = None
                        fund.gsz = None
                        fund.gztime = None
                        fund.est_source = ''
                        fund.has_realtime = False
                    fund.prediction_confidence = fund.calculate_prediction_confidence()
                    updated_funds.append(fund.to_dict())

                except Exception as e:
                    logger.error(f'更新基金 {fund.code} 失败: {e}')
                    updated_funds.append(fund.to_dict())

            save_funds(session['username'])
            logger.info('基金数据更新完成')

        except Exception as e:
            logger.error(f'批量更新基金失败: {e}')
            updated_funds = [f.to_dict() for f in funds]

        if not updated_funds:
            try:
                load_funds(session['username'])
                updated_funds = [f.to_dict() for f in funds]
            except Exception as e:
                logger.error(f'加载基金数据失败: {e}')

        return jsonify(updated_funds or [])

    except Exception as e:
        logger.error(f'获取基金列表失败: {e}')
        try:
            current_funds = [f.to_dict() for f in funds]
            if current_funds:
                return jsonify(current_funds)
        except Exception as _e:

            logger.warning(f"caught exception: {_e}")
        return jsonify([]), 500


@app.route('/api/funds', methods=['POST'])
@performance_monitor
@rate_limit
def add_fund():
    try:
        # 检查用户是否已登录
        if 'username' not in session:
            return jsonify({'error': '未登录'}), 401

        data = request.get_json()
        if not data or 'code' not in data:
            logger.error('添加基金失败: 缺少基金代码')
            return jsonify({'error': '缺少基金代码'}), 400

        code = data['code']
        logger.info(f'添加基金: {code}')

        # 确保funds列表不为空
        if not funds:
            try:
                load_funds(session['username'])
            except Exception as e:
                logger.error(f'加载基金数据失败: {e}')

        # 检查基金是否已经存在
        for existing_fund in funds:
            if existing_fund.code == code:
                logger.warning(f'基金已经存在: {code}')
                return jsonify({'error': '基金已经存在'}), 400

        logger.info(f'基金 {code} 不存在，准备添加')

        # 四路数据并发拉取，总超时 20 秒
        import threading
        results = {'nav': None, 'market': None, 'holdings': None, 'rt': None}
        errors = []

        def _fetch_nav():
            try:
                results['nav'] = get_fund_data(code)
            except Exception as e:
                errors.append(f'历史净值: {e}')

        def _fetch_market():
            try:
                results['market'] = get_market_data()
            except Exception as e:
                errors.append(f'市场数据: {e}')

        def _fetch_holdings():
            try:
                results['holdings'] = get_fund_holdings(code)
            except Exception as e:
                errors.append(f'持仓数据: {e}')

        def _fetch_rt():
            try:
                results['rt'] = data_source_manager.get_fund_estimated_return(code)
            except Exception as e:
                errors.append(f'预估收益率: {e}')

        threads = [
            threading.Thread(target=_fetch_nav, daemon=True),
            threading.Thread(target=_fetch_market, daemon=True),
            threading.Thread(target=_fetch_holdings, daemon=True),
            threading.Thread(target=_fetch_rt, daemon=True),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20)

        # 历史净值是最关键的，拿不到才报错
        if results['nav'] is None:
            msg = '；'.join(errors) if errors else '获取基金数据超时，请稍后重试'
            logger.error(f'添加基金 {code} 失败: {msg}')
            return jsonify({'error': msg}), 504

        name, prices, dates, returns = results['nav']
        market_data = results['market'] or {'indices': {}, 'sectors': {}}
        holdings = results['holdings'] or {}
        rt = results['rt']

        if errors:
            logger.warning(f'添加基金 {code} 部分数据获取失败: {errors}')

        fund = Fund(name, code, prices, dates, returns)
        fund.predicted_return = fund.calculate_predicted_return(
            stock_holdings=holdings,
            market_data=market_data,
            real_time_estimated_return=rt,
        )
        if rt:
            fund.gszzl = rt.get('gszzl')
            fund.gsz = rt.get('gsz')
            fund.gztime = rt.get('gztime')
            fund.est_source = rt.get('source', '')
            fund.has_realtime = True
        else:
            fund.gszzl = fund.gsz = fund.gztime = None
            fund.est_source = ''
            fund.has_realtime = False
        fund.prediction_confidence = fund.calculate_prediction_confidence()
        funds.append(fund)
        save_funds(session['username'])
        logger.info(f'基金添加成功: {code}，历史净值 {len(prices)} 条')
        return jsonify(fund.to_dict()), 201
    except Exception as e:
        logger.error(f'添加基金失败: {e}')
        return jsonify({'error': str(e)}), 400


@app.route('/api/funds/<int:fund_id>', methods=['DELETE'])
@performance_monitor
@rate_limit
def delete_fund(fund_id):
    try:
        if 'username' not in session:
            return jsonify({'error': '未登录'}), 401

        username = session['username']
        logger.info(f'删除基金: {fund_id}')

        # 直接从 Supabase 删除
        result = supabase.table('funds').delete().eq('id', fund_id).eq('username', username).execute()

        # 同步删内存
        global funds
        funds = [f for f in funds if f.id != fund_id]

        logger.info(f'基金删除成功: {fund_id}')
        return jsonify({'message': 'Fund deleted'})
    except Exception as e:
        logger.error(f'删除基金失败: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/funds/<string:code>/details', methods=['GET'])
@performance_monitor
@rate_limit
def get_fund_details(code):
    try:
        logger.info(f'获取基金详情: {code}')
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        # 使用东方财富API获取基金详情
        fund_data_url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
        response = requests.get(fund_data_url, headers=headers, timeout=3)  # 减少超时时间

        if response.status_code == 200:
            try:
                # 解析JS格式数据
                data_str = response.text
                import re

                # 提取基金基本信息
                fund_details = {
                    'establishmentDate': '',
                    'field': '',
                    'composition': [],
                    'relatedStocks': []
                }

                # 提取基金类型（所属领域）
                # 尝试从不同的变量中提取基金类型
                type_match = re.search(r'var fundType = "(.*?)";', data_str)
                if not type_match:
                    # 尝试其他可能的变量名
                    type_match = re.search(r'var syl_fundType = "(.*?)";', data_str)
                if not type_match:
                    # 尝试从基金经理信息中提取
                    manager_match = re.search(r'var Data_currentFundManager = \[(.*?)\];', data_str, re.DOTALL)
                    if manager_match:
                        fund_details['field'] = "混合基金"  # 默认类型
                if type_match:
                    fund_details['field'] = type_match.group(1)

                # 提取基金成立时间
                # 尝试从不同的变量中提取成立时间
                establish_match = re.search(r'var establishDate = "(.*?)";', data_str)
                if not establish_match:
                    # 尝试其他可能的变量名
                    establish_match = re.search(r'var syl_establishDate = "(.*?)";', data_str)
                if not establish_match:
                    # 尝试从规模变动数据中提取
                    scale_match = re.search(r'var Data_fluctuationScale = \{"categories":\[(.*?)\]', data_str)
                    if scale_match:
                        # 使用最早的日期作为成立时间的近似
                        dates_str = scale_match.group(1)
                        dates = re.findall(r'"(.*?)"', dates_str)
                        if dates:
                            fund_details['establishmentDate'] = dates[0]
                if establish_match:
                    fund_details['establishmentDate'] = establish_match.group(1)

                # 清空composition和relatedStocks数组，因为我们不再使用这些数据
                fund_details['composition'] = []
                fund_details['relatedStocks'] = []

                logger.info(f'获取基金详情成功: {code}')
                return jsonify(fund_details)
            except Exception as e:
                logger.error(f'解析基金详情失败: {e}')
                pass
    except Exception as e:
        logger.error(f'获取基金详情失败: {e}')
        pass

    # 如果API调用失败，返回空数据
    return jsonify({
        'establishmentDate': '',
        'field': '',
        'composition': [],
        'relatedStocks': []
    })


@app.route('/api/news', methods=['GET'])
@performance_monitor
@rate_limit
def get_news():
    try:
        logger.info('获取实时快讯')
        # 返回空数组，因为外部API调用可能被阻止
        # 在实际生产环境中，可以使用更稳定的新闻数据源
        return jsonify([])
    except Exception as e:
        logger.error(f'获取实时快讯失败: {e}')
        # 如果API调用失败，返回空数组
        return jsonify([])


@app.route('/api/prediction', methods=['GET'])
@performance_monitor
@rate_limit
def get_prediction():
    try:
        # 检查用户是否已登录
        if 'username' not in session:
            return jsonify({'error': '未登录'}), 401

        logger.info('获取基金预测数据')

        # 基于当前基金数据生成预测
        predictions = []
        for fund in funds:
            prediction = {
                'name': fund.name,
                'code': fund.code,
                'predicted_return': fund.predicted_return,
                'prediction_confidence': fund.prediction_confidence,
                'prediction_time': datetime.now().isoformat(),
                'prediction_reason': '基于历史数据和技术指标分析'
            }
            predictions.append(prediction)

        return jsonify(predictions)
    except Exception as e:
        logger.error(f'获取基金预测数据失败: {e}')
        # 如果API调用失败，返回空数组
        return jsonify([])


@app.route('/api/investment-advice', methods=['GET'])
@performance_monitor
@rate_limit
def get_investment_advice():
    try:
        if 'username' not in session:
            return jsonify({'error': '未登录'}), 401

        logger.info('获取投资建议')
        market_data = get_market_data()

        holdingsAdvice = []
        for fund in funds:
            pr = getattr(fund, 'predicted_return', 0)

            # 预估净值（供前端换算份额用）
            gszzl = getattr(fund, 'gszzl', None)
            _prices = fund.prices or []
            nav = _prices[-1] if _prices else 0
            est_nav_add = round(nav * (1 + gszzl), 4) if gszzl is not None and nav else nav

            if pr > 0.02:
                action = '补仓'
                # 金额梯度（最高500元）
                if pr > 0.05:
                    suggest_amount = 500
                elif pr > 0.035:
                    suggest_amount = 300
                elif pr > 0.025:
                    suggest_amount = 200
                else:
                    suggest_amount = 100
            elif pr < -0.02:
                action = '减仓'
                suggest_amount = 0
            else:
                action = '持有'
                suggest_amount = 0

            reason = generate_holding_reason(fund, action, market_data)

            prices = fund.prices or []
            dates = fund.dates or []
            kdj = list(getattr(fund, 'kdj', [0, 0, 0]))
            bb = list(getattr(fund, 'bollinger_bands', [0, 0, 0]))
            macd = list(getattr(fund, 'macd', [0, 0, 0]))

            # 近1/2/4周净值变化率
            def chg(n):
                if len(prices) > n:
                    return round((prices[-1] / prices[-1 - n] - 1) * 100, 2)
                return None

            # 直接读 get_funds 已缓存的 gszzl，不再重复请求
            has_realtime = getattr(fund, 'has_realtime', False)
            gszzl = getattr(fund, 'gszzl', None)
            gztime = getattr(fund, 'gztime', None)
            est_source = getattr(fund, 'est_source', '')
            est_nav = None
            est_return = None
            if has_realtime and gszzl is not None:
                est_return = round(gszzl * 100, 2)
                if prices:
                    est_nav = round(prices[-1] * (1 + gszzl), 4)
            elif prices and pr:
                est_return = round(pr * 100, 2)
                est_nav = round(prices[-1] * (1 + pr), 4)

            holdingsAdvice.append({
                'fundName': fund.name,
                'fundCode': fund.code,
                'action': action,
                'suggest_amount': suggest_amount,
                'est_nav_add': round(est_nav_add, 4) if est_nav_add else None,
                'reason': reason,
                'indicators': {
                    # 行1
                    'nav': round(prices[-1], 4) if prices else None,
                    'est_nav': est_nav,
                    'est_return': est_return,
                    'chg_1w': chg(5),  # 近1周（5交易日）
                    'chg_2w': chg(10),  # 近2周
                    'chg_4w': chg(20),  # 近4周
                    # 行2
                    'rsi': round(getattr(fund, 'rsi', 50), 1),
                    'kdj_k': round(kdj[0], 1) if kdj else None,
                    'kdj_d': round(kdj[1], 1) if kdj else None,
                    'kdj_j': round(kdj[2], 1) if kdj else None,
                    'bb_pos': round((prices[-1] - bb[2]) / (bb[0] - bb[2]) * 100, 1)
                    if bb and bb[0] != bb[2] and prices else None,
                    'volatility': round(getattr(fund, 'volatility', 0) * 100, 2),
                    # 附加（原因文字用）
                    'macd': macd,
                    'bollinger_bands': bb,
                    'previous_day_return': round(getattr(fund, 'previous_day_return', 0), 2),
                    'prediction_confidence': round(getattr(fund, 'prediction_confidence', 0.5) * 100, 0),
                    'nav_date': dates[-1] if dates else '',
                    'has_realtime': getattr(fund, 'has_realtime', False),
                    'gztime': getattr(fund, 'gztime', None),
                    'est_source': getattr(fund, 'est_source', ''),
                }
            })

        try:
            recommendedFunds = get_recommended_funds_engine(market_snapshot=market_data, top_per_tier=5)
            logger.info(f'推荐引擎返回 {len(recommendedFunds)} 只基金')
        except Exception as e:
            logger.error(f'推荐引擎异常: {e}')
            recommendedFunds = []

        return jsonify({'holdingsAdvice': holdingsAdvice, 'recommendedFunds': recommendedFunds})
    except Exception as e:
        logger.error(f'获取投资建议失败: {e}')
        return jsonify({'holdingsAdvice': [], 'recommendedFunds': []})


def generate_holding_reason(fund, action: str, market_data: dict) -> str:
    """
    基于基金实际指标数据生成结构化分析原因。
    涵盖：净值趋势、近期变化率、RSI、KDJ、布林带、MACD、波动率、市场环境。
    """
    parts = []
    prices = getattr(fund, 'prices', [])
    dates = getattr(fund, 'dates', [])
    pr = getattr(fund, 'predicted_return', 0)

    # ── 1. 最新净值 & 近期变化率 ─────────────────────────────────────────────
    if prices and dates:
        nav = prices[-1]
        prev = getattr(fund, 'previous_day_return', 0)
        sign = '+' if prev >= 0 else ''
        parts.append(f"最新净值 {nav:.4f}（{dates[-1]}），前一日{sign}{prev:.2f}%")

    def chg_str(n, label):
        if len(prices) > n:
            r = (prices[-1] / prices[-1 - n] - 1) * 100
            s = '+' if r >= 0 else ''
            return f"{label}{s}{r:.2f}%"
        return None

    trend_parts = [x for x in [chg_str(5, '近1周'), chg_str(10, '近2周'), chg_str(20, '近4周')] if x]
    if trend_parts:
        parts.append('、'.join(trend_parts))

    # ── 2. RSI ───────────────────────────────────────────────────────────────
    rsi = getattr(fund, 'rsi', 50)
    if rsi < 30:
        parts.append(f"RSI={rsi:.1f}，深度超卖，技术面存在较强反弹动能，历史上此区间往往为阶段性低点")
    elif rsi < 45:
        parts.append(f"RSI={rsi:.1f}，弱势区间，短期仍承压，建议等待企稳信号")
    elif rsi > 70:
        parts.append(f"RSI={rsi:.1f}，超买区间，短线存在回调风险，建议谨慎追高")
    elif rsi > 55:
        parts.append(f"RSI={rsi:.1f}，技术面偏强，上行动能尚存，趋势仍在延续")
    else:
        parts.append(f"RSI={rsi:.1f}，指标中性，多空分歧，方向待明确")

    # ── 3. KDJ ───────────────────────────────────────────────────────────────
    kdj = getattr(fund, 'kdj', None)
    if kdj and len(kdj) == 3:
        k, d, j = kdj[0], kdj[1], kdj[2]
        if j < 20:
            parts.append(f"KDJ（K={k:.1f} D={d:.1f} J={j:.1f}）：J值超卖，短期底部信号较强")
        elif j > 80:
            parts.append(f"KDJ（K={k:.1f} D={d:.1f} J={j:.1f}）：J值超买，短线或有回落压力")
        elif k > d:
            parts.append(f"KDJ（K={k:.1f} D={d:.1f} J={j:.1f}）：K线上穿D线，形成多头交叉信号")
        elif k < d:
            parts.append(f"KDJ（K={k:.1f} D={d:.1f} J={j:.1f}）：K线下穿D线，形成空头交叉信号")
        else:
            parts.append(f"KDJ（K={k:.1f} D={d:.1f} J={j:.1f}）：三线趋于粘合，突破方向待确认")

    # ── 4. 布林带 ────────────────────────────────────────────────────────────
    bb = getattr(fund, 'bollinger_bands', None)
    if bb and len(bb) == 3 and prices:
        upper, mid, lower = bb[0], bb[1], bb[2]
        nav = prices[-1]
        if upper > lower:
            pct = (nav - lower) / (upper - lower) * 100
            if nav > upper:
                parts.append(f"布林带：净值突破上轨（上轨{upper:.4f}），强势信号，但短期注意超买回踩")
            elif nav < lower:
                parts.append(f"布林带：净值跌破下轨（下轨{lower:.4f}），超卖特征明显，可关注反弹时机")
            elif pct > 70:
                parts.append(f"布林带位置{pct:.0f}%，运行于上轨附近（上轨{upper:.4f} 中轨{mid:.4f}），多头占优")
            elif pct < 30:
                parts.append(f"布林带位置{pct:.0f}%，运行于下轨附近（下轨{lower:.4f} 中轨{mid:.4f}），具备支撑")
            else:
                parts.append(f"布林带位置{pct:.0f}%，中轨{mid:.4f}附近震荡，等待方向选择")

    # ── 5. MACD ──────────────────────────────────────────────────────────────
    macd = getattr(fund, 'macd', None)
    if macd and len(macd) == 3:
        ml, sl, hist = macd[0], macd[1], macd[2]
        if ml > sl and hist > 0:
            parts.append(f"MACD金叉（DIF={ml:.4f} DEA={sl:.4f} 柱={hist:.4f}），红柱扩张，上涨动能持续增强")
        elif ml > sl and hist <= 0:
            parts.append(f"MACD多头（DIF={ml:.4f} > DEA={sl:.4f}），红柱收缩中，上攻动能有所减弱")
        elif ml < sl and hist < 0:
            parts.append(f"MACD死叉（DIF={ml:.4f} DEA={sl:.4f} 柱={hist:.4f}），绿柱扩张，下行压力持续增大")
        else:
            parts.append(f"MACD空头（DIF={ml:.4f} < DEA={sl:.4f}），绿柱收缩，跌势或趋于缓和")

    # ── 6. 波动率 ────────────────────────────────────────────────────────────
    vol = getattr(fund, 'volatility', 0) * 100
    if vol < 3:
        parts.append(f"年化波动率{vol:.1f}%，基金走势平稳，适合稳健持有")
    elif vol < 8:
        parts.append(f"年化波动率{vol:.1f}%，波动适中，风险收益比较为均衡")
    elif vol < 15:
        parts.append(f"年化波动率{vol:.1f}%，波动偏高，建议控制单笔仓位")
    else:
        parts.append(f"年化波动率{vol:.1f}%，波动显著偏高，需严格控制风险敞口")

    # ── 7. 大盘环境 ──────────────────────────────────────────────────────────
    if market_data:
        indices = market_data.get('indices', {})
        if indices:
            changes = [v.get('change_ratio', 0) * 100 for v in indices.values()]
            avg = sum(changes) / len(changes)
            names = '、'.join(
                f"{n}{'↑' if v.get('change_ratio', 0) >= 0 else '↓'}{abs(v.get('change_ratio', 0) * 100):.2f}%"
                for n, v in list(indices.items())[:3]
            )
            if avg > 0.5:
                parts.append(f"当前大盘偏强（{names}），整体风险偏好上升，有助于基金净值修复")
            elif avg < -0.5:
                parts.append(f"当前大盘偏弱（{names}），市场情绪谨慎，短期压制基金表现")
            else:
                parts.append(f"大盘震荡（{names}），整体方向仍不明朗，需密切跟踪")

    # ── 8. 综合结论 ──────────────────────────────────────────────────────────
    conf = getattr(fund, 'prediction_confidence', 0.5)
    conf_desc = '高' if conf >= 0.7 else ('中' if conf >= 0.5 else '低')
    pr_pct = pr * 100
    sign = '+' if pr_pct >= 0 else ''
    parts.append(
        f"综合以上技术指标与市场环境，模型预测今日收益率{sign}{pr_pct:.2f}%"
        f"（置信度{conf_desc} {conf * 100:.0f}%），综合判断建议{action}"
    )

    return '；'.join(parts) + '。'


def get_detailed_analysis(fund):
    """尝试调用本地ollama获取详细的基金分析"""
    try:
        import requests
        import json

        # 构建请求数据
        prompt = f"请对基金 {fund.name} ({fund.code}) 进行详细分析，包括：1. 基金表现分析 2. 风险评估 3. 投资建议 4. 未来展望。基于以下数据：预测收益率 {fund.predicted_return:.4f}，预测置信度 {fund.prediction_confidence:.2f}，RSI {fund.rsi:.2f}，波动率 {fund.volatility:.4f}。请提供专业、科学、准确的分析，不要使用任何引导性短语，直接给出分析内容。"

        # 调用本地ollama API
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': 'llama3',
                'prompt': prompt,
                'max_tokens': 500,
                'temperature': 0.7
            },
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            return data.get('response', '').strip()
        else:
            logger.warning('调用ollama API失败，使用默认分析')
            return None
    except Exception as e:
        logger.warning(f'调用ollama失败: {e}，使用默认分析')
        return None


@app.route('/api/market-data', methods=['GET'])
@performance_monitor
@rate_limit
def get_market_data_api():
    """获取市场数据，包括主要大盘指数和行业板块的实时数据"""
    try:
        logger.info('获取市场数据')
        market_data = get_market_data()
        return jsonify(market_data)
    except Exception as e:
        logger.error(f'获取市场数据失败: {e}')
        return jsonify({'indices': {}, 'sectors': {}})


@app.route('/api/funds/<string:code>/nav', methods=['GET'])
@performance_monitor
@rate_limit
def get_fund_nav(code):
    """获取基金在指定日期的净值"""
    try:
        logger.info(f'获取基金净值: {code}')
        # 验证基金代码格式
        if not re.match(r'^\d{6}$', code):
            logger.warning(f'无效的基金代码格式: {code}')
            return jsonify({'error': '无效的基金代码格式'}), 400

        # 获取日期参数
        date = request.args.get('date')
        if not date:
            logger.warning('缺少日期参数')
            return jsonify({'error': '缺少日期参数'}), 400

        # 验证日期格式
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            logger.warning(f'无效的日期格式: {date}')
            return jsonify({'error': '无效的日期格式，应为YYYY-MM-DD'}), 400

        # 获取基金数据
        name, prices, dates, returns = get_fund_data(code)

        # 查找指定日期的净值
        nav = None
        for i, fund_date in enumerate(dates):
            if fund_date == date:
                nav = prices[i]
                break

        if nav:
            logger.info(f'获取基金净值成功: {code}, {date}, {nav}')
            return jsonify({'nav': nav})
        else:
            logger.warning(f'未找到该日期的净值数据: {code}, {date}')
            return jsonify({'nav': None, 'error': '未找到该日期的净值数据'})
    except Exception as e:
        logger.error(f'获取基金净值失败: {e}')
        return jsonify({'nav': None, 'error': str(e)})


@app.route('/api/funds/<string:code>/holdings', methods=['GET'])
@performance_monitor
@rate_limit
def get_fund_holdings_api(code):
    """获取基金的股票持仓数据"""
    try:
        logger.info(f'获取基金持仓数据: {code}')
        # 验证基金代码格式
        if not re.match(r'^\d{6}$', code):
            logger.warning(f'无效的基金代码格式: {code}')
            return jsonify({'error': '无效的基金代码格式'}), 400

        # 获取基金持仓数据
        holdings = get_fund_holdings(code)
        if not holdings:
            logger.warning(f'未获取到基金持仓数据: {code}')
            return jsonify({'stocks': [], 'stock_ratio': 0, 'market_data': {'indices': {}, 'sectors': {}}})

        # 批量获取股票实时数据
        stocks_with_data = []
        stock_codes = [stock['code'] for stock in holdings.get('stocks', [])]
        if stock_codes:
            stock_data_map = get_batch_stock_real_time_data(stock_codes)
            for stock in holdings.get('stocks', []):
                stock_data = stock_data_map.get(stock['code'], {
                    'current_price': 0,
                    'change_amount': 0,
                    'change_ratio': 0
                })
                stock_info = {
                    'code': stock['code'],
                    'name': stock.get('name', f'股票{stock["code"]}'),
                    'weight': stock['weight'],
                    'current_price': stock_data.get('current_price', 0),
                    'change_amount': stock_data.get('change_amount', 0),
                    'change_ratio': stock_data.get('change_ratio', 0)
                }
                stocks_with_data.append(stock_info)
        else:
            stocks_with_data = []

        # 获取市场数据
        market_data = get_market_data()

        # 构建完整的持仓数据
        holdings_data = {
            'stocks': stocks_with_data,
            'stock_ratio': holdings.get('stock_ratio', 0),
            'market_data': market_data
        }

        # 不再使用持仓数据更新基金的预测，避免数据波动
        # 基金预测数据由get_funds接口统一更新

        logger.info(f'获取基金持仓数据成功: {code}')
        return jsonify(holdings_data)
    except Exception as e:
        logger.error(f'获取基金持仓数据失败: {e}')
        return jsonify({'stocks': [], 'stock_ratio': 0, 'market_data': {'indices': {}, 'sectors': {}}})


if __name__ == '__main__':
    import os

    port = int(os.environ.get('PORT', 8003))
    logger.debug(f'Starting Flask server on port {port}...')
    logger.debug(f'Server will run on http://localhost:{port}')
    app.run(debug=False, port=port, host='0.0.0.0')