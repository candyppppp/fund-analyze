from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from flask_cors import CORS

from models.fund import Fund

from models.user import user_manager, ADMIN_USERNAME

from utils.indicators import calculate_rsi, calculate_volatility

from utils.data_sources import data_source_manager

from utils.fund_recommender import get_recommended_funds as get_recommended_funds_engine

from middleware import performance_monitor, rate_limit

import time
import requests
import json
import re
import os
from datetime import datetime, timedelta
import logging

from db import supabase, supabase_admin

# 检查是否在 Vercel 环境中
is_vercel = os.environ.get('VERCEL') is not None


def _is_trading_time_bj():
    from datetime import timezone, timedelta
    bj = datetime.now(timezone(timedelta(hours=8)))
    day  = bj.weekday()   # 0=Mon .. 4=Fri
    mins = bj.hour * 60 + bj.minute
    return day < 5 and 570 <= mins < 900   # 9:30-15:00


def _is_nav_settled_bj():
    from datetime import timezone, timedelta
    bj = datetime.now(timezone(timedelta(hours=8)))
    day  = bj.weekday()
    mins = bj.hour * 60 + bj.minute
    if day >= 5:
        return True           # weekend
    return mins >= 1260 or mins < 570  # after 21:00 or before 9:30

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

# 获取应用根目录
base_dir = os.path.dirname(os.path.abspath(__file__))

# 显式配置Flask应用
app = Flask(__name__,
            static_folder=os.path.join(base_dir, 'static'),
            template_folder=os.path.join(base_dir, 'templates'))

_cors_origins = os.environ.get('CORS_ORIGINS', '').split(',')
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
                    data['name'] or f"基金{data['code']}",
                    data['code'],
                    data['prices'] or [],
                    data['dates'] or [],
                    data['returns'] or [],
                    data.get('volumes') or []
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
                logger.error(f"重建基金对象失败 id={data.get('id')} code={data.get('code')}: {e}")
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
    """更新 Supabase 中每只基金的技术指标（只更新，不新增不删除）

    只更新已存在的基金的技术指标字段，避免覆盖删除操作或影响新增基金。
    新增基金由 add_fund 负责，删除由 delete_fund 负责。
    """
    global funds, last_save_time

    now = time.time()
    if now - last_save_time < 60:
        logger.debug('save_funds 节流跳过')
        return
    last_save_time = now

    logger.info('更新基金技术指标到 Supabase')
    try:
        for fund in funds:
            # 只更新技术指标相关字段，不动 id/code/username
            update_data = {
                'rsi': fund.rsi,
                'volatility': fund.volatility,
                'macd': list(fund.macd) if fund.macd else [0, 0, 0],
                'kdj': list(fund.kdj) if fund.kdj else [0, 0, 0],
                'bollinger_bands': list(fund.bollinger_bands) if fund.bollinger_bands else [0, 0, 0],
                'atr': fund.atr,
                'volume_ratio': fund.volume_ratio,
                'predicted_return': fund.predicted_return,
                'prediction_confidence': fund.prediction_confidence,
                'previous_day_return': fund.previous_day_return,
                'prices': fund.prices,
                'dates': fund.dates,
                'returns': fund.returns,
                'nav_updated_at': getattr(fund, 'nav_updated_at', None),
                'has_realtime': getattr(fund, 'has_realtime', False),
                'gszzl': getattr(fund, 'gszzl', None),
                'gsz': getattr(fund, 'gsz', None),
                'gztime': getattr(fund, 'gztime', None),
                'est_source': getattr(fund, 'est_source', ''),
            }
            supabase_admin.table('funds').update(update_data).eq('id', fund.id).execute()
        logger.info(f'成功更新 {len(funds)} 只基金技术指标')
    except Exception as e:
        logger.error(f"更新基金数据失败: {e}")


# 初始化加载数据
try:
    load_funds()
except Exception as e:
    logger.error(f'初始化加载数据失败: {e}')
    funds = []

# 获取基金持仓数据
_holdings_cache = {}  # {code: (timestamp, holdings_data)}
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
    """从东方财富 JSON 接口获取股票名称（对境外服务器友好）"""
    try:
        # 判断市场
        if stock_code.startswith('6') or stock_code.startswith('688'):
            market = 1  # 沪市
        else:
            market = 0  # 深市

        url = (f"https://push2.eastmoney.com/api/qt/stock/get"
               f"?secid={market}.{stock_code}&fields=f58,f43,f169,f170")
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.eastmoney.com/"}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            name = data.get('f58', '')
            if name and name != '-':
                return name
    except Exception as e:
        logger.warning(f"获取股票名称失败 {stock_code}: {e}")
    return f'股票{stock_code}'


# 批量获取股票实时数据
def get_batch_stock_real_time_data(stock_codes):
    """批量获取股票实时数据，使用东方财富 JSON 接口（对境外服务器友好）"""
    results = {}
    if not stock_codes:
        return results

    batch_size = 20
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.eastmoney.com/"}

    for i in range(0, len(stock_codes), batch_size):
        batch = stock_codes[i:i + batch_size]
        try:
            # 东方财富市场号：沪市=1，深市=0
            secids = []
            for code in batch:
                market = 1 if (code.startswith('6') or code.startswith('688')) else 0
                secids.append(f"{market}.{code}")

            url = ("https://push2.eastmoney.com/api/qt/ulist.np/get"
                   f"?fltt=2&invt=2&fields=f12,f2,f4,f3"
                   f"&secids={','.join(secids)}")
            resp = requests.get(url, headers=headers, timeout=5)

            if resp.status_code == 200:
                items = resp.json().get('data', {}).get('diff', [])
                for item in items:
                    code = str(item.get('f12', ''))
                    price = item.get('f2', 0) or 0
                    change_amount = item.get('f4', 0) or 0
                    change_ratio = (item.get('f3', 0) or 0) / 100
                    results[code] = {
                        'current_price': price,
                        'change_amount': change_amount,
                        'change_ratio': change_ratio,
                    }
        except Exception as e:
            logger.debug(f"批量获取股票数据失败: {e}")

        # 补全未获取到的
        for code in batch:
            if code not in results:
                results[code] = {'current_price': 0, 'change_amount': 0, 'change_ratio': 0}

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


# 获取市场数据（大盘指数）
def get_market_data():
    """获取大盘指数实时数据，使用东方财富 JSON 接口
    包含：上证、深证、沪深300、上证50、创业板、科创50
    """
    try:
        # secids:
        #   1.000001 = 上证指数
        #   0.399001 = 深证成指
        #   1.000300 = 沪深300
        #   1.000016 = 上证50
        #   0.399006 = 创业板指
        #   1.000688 = 科创50
        url = ("https://push2.eastmoney.com/api/qt/ulist.np/get"
               "?fltt=2&invt=2&fields=f12,f14,f3,f4,f2"
               "&secids=1.000001,0.399001,1.000300,1.000016,0.399006,1.000688")
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.eastmoney.com/"}
        resp = requests.get(url, headers=headers, timeout=5)

        result = {'indices': {}, 'sectors': {}}
        name_map = {
            '000001': '上证指数',
            '399001': '深证成指',
            '000300': '沪深300',
            '000016': '上证50',
            '399006': '创业板指',
            '000688': '科创50',
        }

        if resp.status_code == 200:
            items = resp.json().get('data', {}).get('diff', [])
            for item in items:
                code = str(item.get('f12', ''))
                name = name_map.get(code, item.get('f14', code))
                price = item.get('f2', 0) or 0
                change_ratio = (item.get('f3', 0) or 0) / 100  # 东方财富是百分比×100
                change_amount = item.get('f4', 0) or 0
                result['indices'][name] = {
                    'code': code,
                    'current_price': price,
                    'change_amount': change_amount,
                    'change_ratio': change_ratio,
                }
        return result
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
        if not validate_csrf_token():
            return render_template('login.html', error='请求验证失败，请刷新页面重试')
        username = request.form.get('username')
        password = request.form.get('password')

        # 验证用户身份
        user = user_manager.authenticate(username, password)
        if user:
            # 设置会话
            session['username'] = user.username
            session['is_admin'] = (username == ADMIN_USERNAME)  # 管理员判断
            session.permanent = True  # 使会话持久化

            # 加载用户的基金数据
            load_funds(user.username)

            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='用户名或密码错误')

    return render_template('login.html')


# 移除注册路由，因为不需要用户自行注册

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

    if request.method == 'POST':
        if not validate_csrf_token():
            error = '请求验证失败，请刷新页面重试'
        else:
            action = request.form.get('action')

            if action == 'add':
                # 新增账户
                new_username = request.form.get('new_username')
                new_password = request.form.get('new_password')
                permissions = request.form.getlist('permissions')

                if new_username and new_password:
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
                if username and username != ADMIN_USERNAME:  # 不允许删除管理员账户
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

    return render_template('account_management.html',
                           users=users,
                           error=error,
                           success=success,
                           admin_username=ADMIN_USERNAME)



@app.route('/api/funds', methods=['GET'])
@performance_monitor
@rate_limit
def get_funds():
    try:
        if 'username' not in session:
            return jsonify({'error': '未登录'}), 401

        username = session['username']

        # basic_only 提前判断：只需 id/code/name，直接查 Supabase，不走完整 load_funds
        basic_only = request.args.get('basic', 'false').lower() == 'true'
        if basic_only:
            try:
                rows = supabase.table('funds').select('id,code,name').eq('username', username).execute()
                return jsonify([{'id': r['id'], 'code': r['code'], 'name': r['name']} for r in (rows.data or [])])
            except Exception as e:
                logger.error(f'basic 查询失败: {e}')
                return jsonify([])

        # -- Fast path: non-trading / settled -> return Supabase data directly
        # Avoids slow external API calls when market is closed.
        # After returning cached data, if data is stale (>24h), trigger a background
        # refresh to keep Supabase up-to-date even without a cron job.
        if _is_nav_settled_bj():
            try:
                rows = supabase.table('funds').select('*').eq('username', username).execute()
                if rows.data:
                    logger.info(f'nav settled, returning Supabase cache: {len(rows.data)} funds')

                    # Check staleness: trigger refresh if any fund's data is not from today (BJ time)
                    # Bug fix: previous logic used >24h which could miss same-day refreshes
                    # e.g. data updated at 15:00 yesterday, opened at 21:00 today = only 6h gap, no refresh
                    from datetime import timezone as _tz2
                    _bj_today = datetime.now(_tz2(timedelta(hours=8))).strftime('%Y-%m-%d')
                    _needs_refresh = False
                    for row in rows.data:
                        nav_ts = row.get('nav_updated_at')
                        if not nav_ts:
                            _needs_refresh = True
                            break
                        try:
                            # If nav_updated_at date < today (BJ), data is stale
                            if str(nav_ts)[:10] < _bj_today:
                                _needs_refresh = True
                                break
                        except Exception:
                            pass

                    if _needs_refresh:
                        logger.info('Supabase data stale (>24h), triggering background refresh')
                        import threading
                        def _bg_refresh():
                            try:
                                global funds
                                load_funds(username)
                                user_funds = [f for f in funds if getattr(f, 'username', None) == username]
                                if not user_funds:
                                    return
                                from concurrent.futures import ThreadPoolExecutor, as_completed as _ac
                                market_data = get_market_data()
                                from datetime import timezone as _tz_bg, timedelta as _td_bg
                                today = datetime.now(_tz_bg(_td_bg(hours=8))).strftime('%Y-%m-%d')
                                def _upd(fund):
                                    try:
                                        name, new_prices, new_dates, new_returns = get_fund_data(fund.code)
                                        if new_prices and new_dates:
                                            existing = set(fund.dates)
                                            merged_dates, merged_prices, merged_returns = list(fund.dates), list(fund.prices), list(fund.returns)
                                            for d, p, r in zip(new_dates, new_prices, new_returns):
                                                if d not in existing:
                                                    merged_dates.append(d); merged_prices.append(p); merged_returns.append(r); existing.add(d)
                                            if len(merged_dates) > len(fund.dates):
                                                combined = sorted(zip(merged_dates, merged_prices, merged_returns))
                                                fund.dates = [x[0] for x in combined]; fund.prices = [x[1] for x in combined]; fund.returns = [x[2] for x in combined]
                                        fund.update_prices(fund.prices, fund.dates, fund.returns, market_data=market_data)
                                        fund.nav_updated_at = today
                                        fund.prediction_confidence = fund.calculate_prediction_confidence()
                                    except Exception as _e:
                                        logger.warning(f'bg refresh {fund.code}: {_e}')
                                with ThreadPoolExecutor(max_workers=4) as ex:
                                    list(ex.map(_upd, user_funds))
                                # 节流保护：直接写而不走 save_funds 的60秒限制
                                for fund in user_funds:
                                    try:
                                        supabase_admin.table('funds').update({
                                            'prices': fund.prices, 'dates': fund.dates, 'returns': fund.returns,
                                            'rsi': fund.rsi, 'volatility': fund.volatility,
                                            'macd': list(fund.macd) if fund.macd else [0,0,0],
                                            'kdj': list(fund.kdj) if fund.kdj else [0,0,0],
                                            'bollinger_bands': list(fund.bollinger_bands) if fund.bollinger_bands else [0,0,0],
                                            'predicted_return': fund.predicted_return,
                                            'prediction_confidence': fund.prediction_confidence,
                                            'previous_day_return': fund.previous_day_return,
                                            'nav_updated_at': fund.nav_updated_at,
                                        }).eq('id', fund.id).execute()
                                    except Exception as _e:
                                        logger.warning(f'bg save {fund.code}: {_e}')
                                logger.info(f'bg refresh complete: {len(user_funds)} funds updated')
                            except Exception as _e:
                                logger.error(f'bg refresh failed: {_e}')
                        threading.Thread(target=_bg_refresh, daemon=True).start()

                    # 直接返回 Supabase 缓存数据，不做同步修正（防止拉净值超时导致空列表）
                    # 今日净值更新由后台异步刷新（_bg_refresh）负责，下次打开页面即可看到
                    return jsonify(rows.data)
            except Exception as _e:
                logger.warning(f'Supabase cache read failed, falling back: {_e}')

        # -- Full path: trading hours -> fetch external API, update Supabase
        global funds
        load_funds(username)
        user_funds = [f for f in funds if getattr(f, 'username', None) == username]

        logger.info(f'get funds user={username} count={len(user_funds)}')
        from datetime import timezone as _tz_gf, timedelta as _td_gf
        today = datetime.now(_tz_gf(_td_gf(hours=8))).strftime('%Y-%m-%d')
        updated_funds = []

        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed as _as_completed
            import copy

            market_data = get_market_data()

            def _update_one(fund):
                """单只基金并发更新 - 操作独立副本，避免多线程竞争修改共享对象"""
                try:
                    already_updated_today = (
                        fund.nav_updated_at is not None and
                        str(fund.nav_updated_at)[:10] == today
                    )
                    if already_updated_today:
                        rt = data_source_manager.get_fund_estimated_return(fund.code)
                    else:
                        name, new_prices, new_dates, new_returns = get_fund_data(fund.code)
                        rt = data_source_manager.get_fund_estimated_return(fund.code)
                        if new_prices and new_dates:
                            # 用本地变量合并，不直接 append 到 fund 对象（线程安全）
                            existing = set(fund.dates)
                            merged_dates = list(fund.dates)
                            merged_prices = list(fund.prices)
                            merged_returns = list(fund.returns)
                            for d, p, r in zip(new_dates, new_prices, new_returns):
                                if d not in existing:
                                    merged_dates.append(d)
                                    merged_prices.append(p)
                                    merged_returns.append(r)
                                    existing.add(d)
                            if len(merged_dates) > len(fund.dates):
                                combined = sorted(zip(merged_dates, merged_prices, merged_returns))
                                fund.dates   = [x[0] for x in combined]
                                fund.prices  = [x[1] for x in combined]
                                fund.returns = [x[2] for x in combined]
                        fund.update_prices(fund.prices, fund.dates, fund.returns,
                                           market_data=market_data)
                        fund.nav_updated_at = today

                    holdings = _holdings_cache.get(fund.code, (0, {}))[1] if fund.code in _holdings_cache else {}
                    if rt:
                        fund.predicted_return = fund.calculate_predicted_return(
                            stock_holdings=holdings, market_data=market_data,
                            real_time_estimated_return=rt)
                        fund.gszzl      = rt.get('gszzl')
                        fund.gsz        = rt.get('gsz')
                        fund.gztime     = rt.get('gztime')
                        fund.est_source = rt.get('source', '')
                        fund.has_realtime = True
                    else:
                        fund.predicted_return = fund.calculate_predicted_return(
                            stock_holdings=holdings, market_data=market_data)
                        fund.gszzl = fund.gsz = fund.gztime = None
                        fund.est_source = ''
                        fund.has_realtime = False
                    fund.prediction_confidence = fund.calculate_prediction_confidence()
                    return fund.to_dict()
                except Exception as e:
                    logger.error(f'更新基金 {fund.code} 失败: {e}')
                    return fund.to_dict()

            with ThreadPoolExecutor(max_workers=6) as executor:
                futures = {executor.submit(_update_one, fund): fund for fund in user_funds}
                for future in _as_completed(futures):
                    result = future.result()
                    if result:
                        updated_funds.append(result)

            save_funds(username)
            logger.info('基金数据更新完成')

        except Exception as e:
            logger.error(f'批量更新基金失败: {e}')
            updated_funds = [f.to_dict() for f in user_funds]

        if not updated_funds:
            updated_funds = [f.to_dict() for f in user_funds]

        return jsonify(updated_funds or [])

    except Exception as e:
        logger.error(f'获取基金列表失败: {e}')
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

        # 直接查 Supabase 检查是否已存在（不依赖内存，避免无状态漏判）
        try:
            existing = supabase.table('funds').select('id').eq('code', code).eq('username',
                                                                                session['username']).execute()
            if existing.data:
                logger.warning(f'基金已经存在: {code}')
                return jsonify({'error': '基金已经存在'}), 400
        except Exception as e:
            logger.error(f'检查基金存在失败: {e}')

        # 同步内存（确保后续操作不重复）
        if not funds:
            try:
                load_funds(session['username'])
            except Exception as e:
                logger.error(f'加载基金数据失败: {e}')

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
        # 直接 insert 新基金到 Supabase（不传 id，由数据库自增）
        fund_data = fund.to_dict()
        fund_data['username'] = session['username']
        fund_data.pop('id', None)  # 去掉 id，让 Supabase 自动生成
        resp = supabase_admin.table('funds').insert(fund_data).execute()
        # 用数据库生成的 id 更新内存对象
        if resp.data:
            fund.id = resp.data[0]['id']
            Fund.id_counter = fund.id + 1
        funds.append(fund)
        logger.info(f'基金添加成功: {code}，id={fund.id}，历史净值 {len(prices)} 条')
        return jsonify(fund.to_dict()), 201
    except Exception as e:
        logger.error(f'添加基金失败: {e}')
        return jsonify({'error': str(e)}), 400


# ── 买入记录 API（云端持久化）────────────────────────────────────────────────

@app.route('/api/buy_records', methods=['GET'])
@performance_monitor
@rate_limit
def get_buy_records():
    """获取当前用户所有买入记录"""
    try:
        if 'username' not in session:
            return jsonify({'error': '未登录'}), 401
        username = session['username']
        resp = supabase.table('buy_records').select('*').eq('username', username).execute()
        return jsonify(resp.data or [])
    except Exception as e:
        logger.error(f'获取买入记录失败: {e}')
        return jsonify([])


@app.route('/api/buy_records', methods=['POST'])
@performance_monitor
@rate_limit
def add_buy_record():
    """添加买入记录"""
    try:
        if 'username' not in session:
            return jsonify({'error': '未登录'}), 401
        data = request.get_json()
        if not data:
            return jsonify({'error': '缺少数据'}), 400
        record = {
            'username': session['username'],
            'fund_id': data.get('fund_id'),
            'fund_code': data.get('fund_code'),
            'fund_name': data.get('fund_name', ''),
            'nav': data.get('nav'),
            'shares': data.get('shares'),
            'amount': data.get('amount'),
            'date': data.get('date'),
            'note': data.get('note', ''),
        }
        resp = supabase_admin.table('buy_records').insert(record).execute()
        return jsonify(resp.data[0] if resp.data else record), 201
    except Exception as e:
        logger.error(f'添加买入记录失败: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/buy_records/<int:record_id>', methods=['DELETE'])
@performance_monitor
@rate_limit
def delete_buy_record(record_id):
    """删除买入记录"""
    try:
        if 'username' not in session:
            return jsonify({'error': '未登录'}), 401
        username = session['username']
        supabase_admin.table('buy_records').delete().eq('id', record_id).eq('username', username).execute()
        return jsonify({'message': 'deleted'})
    except Exception as e:
        logger.error(f'删除买入记录失败: {e}')
        return jsonify({'error': str(e)}), 500




@app.route('/api/blogger-signals', methods=['GET'])
@performance_monitor
@rate_limit
def get_blogger_signals():
    """获取博主信号列表，支持按日期查询"""
    try:
        if 'username' not in session:
            return jsonify({'error': '未登录'}), 401
        username = session['username']
        date = request.args.get('date', '')  # 不传则返回最近7天

        from datetime import timezone as _tz, timedelta as _td
        _bj_today = datetime.now(_tz(_td(hours=8))).strftime('%Y-%m-%d')

        days = int(request.args.get('days', 7))  # 支持 1D/3D/7D，默认7个交易日
        days = max(1, min(days, 30))

        query = supabase.table('blogger_signals').select('*').eq('username', username)
        if date:
            query = query.eq('date', date)
        else:
            # 按交易日计算：含今天往前共 N 个交易日
            from datetime import timezone as _tz7, timedelta as _td7
            _bj_dt = datetime.now(_tz7(_td7(hours=8))).date()
            _trading = []
            _cur = _bj_dt
            while len(_trading) < days:
                if _cur.weekday() < 5:
                    _trading.append(_cur)
                _cur -= _td7(days=1)
            _cutoff = _trading[-1].strftime('%Y-%m-%d')
            logger.info(f'blogger_signals: days={days}交易日, cutoff={_cutoff}')
            query = query.gte('date', _cutoff)

        resp = query.order('date', desc=True).limit(5000).execute()  # 突破 Supabase 默认 1000 条限制
        result = resp.data or []
        # 如果空，再查一次不带 username 过滤，看表里是否有数据
        if not result:
            all_resp = supabase.table('blogger_signals').select('id,username,date').limit(5).execute()
            logger.warning(f'blogger_signals 查询空: username={username!r}, days={days}, cutoff={_cutoff if not date else date!r}, count=0. 表里前5条: {all_resp.data}')
        else:
            logger.info(f'get_blogger_signals: username={username!r}, count={len(result)}')
        return jsonify(result)
    except Exception as e:
        logger.error(f'获取博主信号失败: {e}')
        return jsonify([])


@app.route('/api/blogger-signals', methods=['POST'])
@performance_monitor
@rate_limit
def upload_blogger_signals():
    """批量上传博主信号（前端解析 xlsx 后发送 JSON 数组）"""
    try:
        if 'username' not in session:
            return jsonify({'error': '未登录'}), 401
        username = session['username']

        data = request.get_json()
        if not data or not isinstance(data, list):
            return jsonify({'error': '数据格式错误，需要 JSON 数组'}), 400

        if len(data) > 500:
            return jsonify({'error': '单次上传不超过500条'}), 400

        # 校验并补充字段
        records = []
        for row in data:
            fund_code = str(row.get('fund_code', '')).strip()
            fund_name = str(row.get('fund_name', '')).strip()
            action    = str(row.get('action', '')).strip()
            date      = str(row.get('date', '')).strip()
            blogger   = str(row.get('blogger_name', '')).strip()

            # 必填字段校验
            if not all([fund_code, fund_name, action, date, blogger]):
                continue  # 跳过不完整的行

            # action 只接受合法值
            if action not in ('买入', '卖出', '定投', '清仓', '减仓'):
                continue

            records.append({
                'username':      username,
                'date':          date,
                'blogger_name':  blogger,
                'fund_code':     fund_code,
                'fund_name':     fund_name,
                'action':        action,
                'amount':        str(row.get('amount', '')).strip(),
                'topic':         str(row.get('topic', '')).strip(),
                'yearly_return': str(row.get('yearly_return', '')).strip(),
            })

        if not records:
            return jsonify({'error': '没有有效数据（请检查基金代码是否填写）'}), 400

        if not supabase_admin:
            return jsonify({'error': '服务端写入权限不足'}), 500

        # 前端已去重，但后端再做一次保险：按唯一键去重，相同 key 保留最后一条
        seen = {}
        for r in records:
            key = (r['date'], r['blogger_name'], r['fund_code'])
            seen[key] = r  # 同 key 后覆盖前
        unique_records = list(seen.values())

        # 逐条 upsert，避免批量提交时同批次内有重复 key 报错
        inserted = 0
        for r in unique_records:
            try:
                supabase_admin.table('blogger_signals').upsert(
                    r, on_conflict='username,date,blogger_name,fund_code'
                ).execute()
                inserted += 1
            except Exception as _ue:
                logger.warning(f'blogger_signals upsert 跳过: {_ue}')

        logger.info(f'blogger_signals: {username} 上传 {inserted}/{len(unique_records)} 条，日期={records[0]["date"] if records else "?"}')
        return jsonify({'success': True, 'inserted': inserted, 'total': len(data), 'unique': len(unique_records)})

    except Exception as e:
        logger.error(f'上传博主信号失败: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/funds/<int:fund_id>', methods=['DELETE'])
@performance_monitor
@rate_limit
def delete_fund(fund_id):
    try:
        if 'username' not in session:
            return jsonify({'error': '未登录'}), 401

        username = session['username']
        logger.info(f'删除基金: {fund_id}')

        # 先从 Supabase 删除，确保持久化
        supabase_admin.table('funds').delete().eq('id', fund_id).eq('username', username).execute()

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


@app.route('/api/investment-advice', methods=['GET'])
@performance_monitor
@rate_limit
def get_investment_advice():
    try:
        if 'username' not in session:
            return jsonify({'error': '未登录'}), 401

        username = session['username']
        force_refresh = request.args.get('refresh', '0') == '1'

        # ── 1. 非强制刷新时：优先读 Supabase 缓存 ──────────────────────────
        if not force_refresh:
            try:
                cache_row = supabase.table('advice_cache') \
                    .select('data,updated_at') \
                    .eq('username', username) \
                    .execute()
                if cache_row.data:
                    row = cache_row.data[0]
                    updated_at_str = row.get('updated_at', '')
                    cached_data = row.get('data')
                    if updated_at_str and cached_data:
                        from datetime import timezone
                        updated_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
                        age_minutes = (datetime.now(timezone.utc) - updated_at).total_seconds() / 60
                        has_real_data = (
                            cached_data.get('holdingsAdvice') or
                            cached_data.get('recommendedFunds')
                        )
                        # 缓存 TTL：交易时间15分钟，非交易时间60分钟
                        _advice_ttl = 15 if _is_trading_time_bj() else 60
                        if age_minutes < _advice_ttl and has_real_data:
                            logger.info(f'投资建议命中 Supabase 缓存（{age_minutes:.1f} 分钟前生成）')
                            cached_data['_cache_time'] = int(updated_at.timestamp() * 1000)
                            cached_data['_advice_updated_at'] = updated_at_str
                            return jsonify(cached_data)
                        else:
                            logger.info(f'Supabase 缓存已过期（{age_minutes:.1f} 分钟），重新生成')
            except Exception as _ce:
                logger.warning(f'读取 Supabase 投资建议缓存失败: {_ce}')

        logger.info('获取投资建议（重新生成）')

        # Vercel 无状态：确保内存有数据
        global funds
        if not funds:
            load_funds(username)

        # 并行拉所有基金实时估值，更新 predicted_return
        # 否则从 Supabase 加载的历史值可能全是0，导致全部判断为"持有"
        market_data = get_market_data()

        from concurrent.futures import ThreadPoolExecutor, as_completed

        def fetch_rt(fund):
            try:
                rt = data_source_manager.get_fund_estimated_return(fund.code)
                return fund, rt
            except Exception as e:
                logger.warning(f"获取 {fund.code} 实时估值失败: {e}")
                return fund, None

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {executor.submit(fetch_rt, fund): fund for fund in funds}
            for future in as_completed(futures):
                fund, rt = future.result()
                if rt and rt.get('gszzl') is not None:
                    try:
                        fund.predicted_return = fund.calculate_predicted_return(
                            real_time_estimated_return=rt
                        )
                    except Exception:
                        pass
                    fund.gszzl = rt.get('gszzl')
                    fund.gsz = rt.get('gsz')
                    fund.gztime = rt.get('gztime')
                    fund.est_source = rt.get('source', '')
                    fund.has_realtime = True
                else:
                    fund.has_realtime = False
                    fund.gszzl = None

        # 读取前端传来的投资偏好档位（small / medium / large）
        investment_level = request.args.get('level', 'small')
        if investment_level not in ('small', 'medium', 'large'):
            investment_level = 'small'

        # 读取当前用户持仓记录（用于区分"补仓"和"建仓"）
        try:
            holding_records = supabase.table('buy_records').select('fund_code,shares').eq('username', session['username']).execute()
            # 计算每只基金的净持仓份数
            _holding_map = {}
            for r in (holding_records.data or []):
                fc = r.get('fund_code', '')
                _holding_map[fc] = _holding_map.get(fc, 0) + (r.get('shares', 0) or 0)
        except Exception as _e:
            logger.warning(f'读取持仓记录失败: {_e}')
            _holding_map = {}

        # ── 查询7天内的博主信号，用于 blogger_hint 标注 ─────────────────────
        _blogger_map = {}  # fund_code -> {'buy': N, 'sell': N, 'bloggers': [...]}
        try:
            from datetime import timezone as _btz, timedelta as _btd
            _7d_ago = (datetime.now(_btz(_btd(hours=8))) - _btd(days=7)).strftime('%Y-%m-%d')
            _bsig = supabase.table('blogger_signals')                 .select('fund_code,action,blogger_name')                 .eq('username', username)                 .gte('date', _7d_ago)                 .execute()
            for _r in (_bsig.data or []):
                _fc = _r.get('fund_code', '')
                if not _fc:
                    continue
                if _fc not in _blogger_map:
                    _blogger_map[_fc] = {'buy': 0, 'sell': 0, 'bloggers': []}
                if _r.get('action') in ('买入', '定投'):
                    _blogger_map[_fc]['buy'] += 1
                elif _r.get('action') == '卖出':
                    _blogger_map[_fc]['sell'] += 1
                _bn = _r.get('blogger_name', '')
                if _bn and _bn not in _blogger_map[_fc]['bloggers']:
                    _blogger_map[_fc]['bloggers'].append(_bn)
        except Exception as _be:
            logger.warning(f'查询博主信号失败（不影响主流程）: {_be}')

        holdingsAdvice = []
        for fund in funds:
            pr = getattr(fund, 'predicted_return', 0)

            # 净值（供前端换算份额用）
            # 优先用 gsz（实时估算净值，交易时间有效）；否则用最新已结算净值 prices[-1]
            _prices = fund.prices or []
            nav = _prices[-1] if _prices else 0
            gsz = getattr(fund, 'gsz', None)   # 实时估算净值（如 4.8838）
            has_realtime = getattr(fund, 'has_realtime', False)
            # 交易时间有实时数据时用估算净值，否则用最新真实净值
            est_nav_add = round(float(gsz), 4) if has_realtime and gsz else nav

            # ── 多维度综合决策（替代单日涨跌判断）─────────────────────────────
            action, suggest_amount = _calc_action(fund, pr, market_data, investment_level, _blogger_map.get(fund.code))

            # ── 建仓逻辑：关注但无净持仓的基金，看多信号改为"建仓" ──────────
            net_holding = _holding_map.get(fund.code, 0)
            if net_holding <= 0 and action in ('补仓', '轻仓补入'):
                action = '建仓'   # 首次入场，改用建仓标签

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

            # 博主实盘提示
            _bm = _blogger_map.get(fund.code, {})
            _blogger_hint = ''
            if _bm:
                _parts = []
                if _bm['buy'] > 0:
                    _parts.append(f"{_bm['buy']}位博主买入")
                if _bm['sell'] > 0:
                    _parts.append(f"{_bm['sell']}位博主卖出")
                if _parts:
                    _blogger_hint = '、'.join(_parts) + '（近7天）'

            holdingsAdvice.append({
                'fundName': fund.name,
                'fundCode': fund.code,
                'action': action,
                'suggest_amount': suggest_amount,
                'est_nav_add': round(est_nav_add, 4) if est_nav_add else None,
                'reason': reason,
                'blogger_hint': _blogger_hint,
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

        # recommendedFunds moved to /api/recommended-funds (separate endpoint)
        # The recommender engine takes 60+ seconds, exceeding Vercel 10s timeout,
        # causing Supabase write to never execute. holdingsAdvice alone is fast.
        result = {'holdingsAdvice': holdingsAdvice, 'recommendedFunds': []}

        if holdingsAdvice:
            _write_ok = False
            if not supabase_admin:
                logger.error('advice_cache write skipped: supabase_admin is None (SUPABASE_SERVICE_ROLE_KEY missing?)')
            else:
                try:
                    from datetime import timezone as _tz
                    now_utc = datetime.now(_tz.utc).isoformat()
                    # 先尝试 update 已有行
                    upd = supabase_admin.table('advice_cache')                         .update({'data': result, 'updated_at': now_utc})                         .eq('username', username).execute()
                    if upd.data:
                        _write_ok = True
                        logger.info(f'advice_cache updated for {username}')
                    else:
                        # 没有已有行，insert
                        ins = supabase_admin.table('advice_cache')                             .insert({'username': username, 'data': result, 'updated_at': now_utc})                             .execute()
                        _write_ok = bool(ins.data)
                        logger.info(f'advice_cache inserted for {username}: {_write_ok}')
                    if _write_ok:
                        result['_cache_time'] = int(datetime.now(_tz.utc).timestamp() * 1000)
                        result['_advice_updated_at'] = now_utc
                except Exception as _se:
                    logger.error(f'advice_cache write FAILED: {_se}')

        return jsonify(result)
    except Exception as e:
        logger.error(f'获取投资建议失败: {e}')
        return jsonify({'holdingsAdvice': [], 'recommendedFunds': []})


@app.route('/api/recommended-funds', methods=['GET'])
@performance_monitor
@rate_limit
def get_recommended_funds_api():
    """Recommended funds endpoint - separate from investment advice to avoid Vercel timeout.
    Uses its own Supabase table (recommended_funds_cache) with 6h TTL.
    Returns up to 20 funds (10 stable + 10 balanced).
    """
    try:
        if 'username' not in session:
            return jsonify({'error': '未登录'}), 401

        username = session['username']
        force_refresh = request.args.get('refresh', '0') == '1'

        # ── 1. Try Supabase cache first (6h TTL) ──────────────────────────────
        if not force_refresh:
            try:
                rec_row = supabase.table('recommended_funds_cache')                     .select('data,updated_at')                     .eq('username', username)                     .execute()
                if rec_row.data:
                    row = rec_row.data[0]
                    updated_at_str = row.get('updated_at', '')
                    cached_data = row.get('data')
                    if updated_at_str and cached_data and cached_data.get('recommendedFunds'):
                        from datetime import timezone
                        updated_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
                        age_hours = (datetime.now(timezone.utc) - updated_at).total_seconds() / 3600
                        _rec_ttl = 1 if _is_trading_time_bj() else 3
                        if age_hours < _rec_ttl:
                            logger.info(f'recommended funds: Supabase cache hit ({age_hours:.1f}h old)')
                            cached_data['_rec_updated_at'] = updated_at_str
                            cached_data['_rec_cache_time'] = int(updated_at.timestamp() * 1000)
                            return jsonify(cached_data)
                        else:
                            logger.info(f'recommended funds: cache expired ({age_hours:.1f}h), refreshing')
            except Exception as _ce:
                logger.warning(f'recommended funds cache read failed: {_ce}')

        # ── 2. Generate fresh recommendations (20 funds: 10 stable + 10 balanced) ──
        logger.info('recommended funds: generating fresh recommendations')
        market_data = get_market_data()
        recommended = get_recommended_funds_engine(market_snapshot=market_data, top_per_tier=10)
        logger.info(f'recommended funds: got {len(recommended)} funds')

        # 追加博主信号（7天内买入的推荐基金标注博主动向）
        try:
            from datetime import timezone as _rtz, timedelta as _rtd
            _r7ago = (datetime.now(_rtz(_rtd(hours=8))) - _rtd(days=7)).strftime('%Y-%m-%d')
            _rbsig = supabase.table('blogger_signals')                 .select('fund_code,action,blogger_name')                 .eq('username', username)                 .gte('date', _r7ago)                 .execute()
            _rmap = {}
            for _rr in (_rbsig.data or []):
                _fc = _rr.get('fund_code', '')
                if not _fc: continue
                if _fc not in _rmap: _rmap[_fc] = {'buy': 0, 'sell': 0}
                if _rr.get('action') in ('买入', '定投'): _rmap[_fc]['buy'] += 1
                elif _rr.get('action') == '卖出': _rmap[_fc]['sell'] += 1
            # 给每条推荐基金加 blogger_hint
            for _rf in recommended:
                _bm2 = _rmap.get(_rf.get('code', ''), {})
                _hint_parts = []
                if _bm2.get('buy'): _hint_parts.append(f"{_bm2['buy']}位博主买入")
                if _bm2.get('sell'): _hint_parts.append(f"{_bm2['sell']}位博主卖出")
                _rf['blogger_hint'] = '、'.join(_hint_parts) + '（近7天）' if _hint_parts else ''
        except Exception as _rbe:
            logger.warning(f'推荐基金博主信号查询失败: {_rbe}')

        result = {'recommendedFunds': recommended}

        # ── 3. Write to recommended_funds_cache ───────────────────────────────
        if recommended:
            if not supabase_admin:
                logger.error('recommended_funds_cache write skipped: supabase_admin is None')
            else:
                try:
                    from datetime import timezone as _tz
                    now_utc = datetime.now(_tz.utc).isoformat()
                    upd = supabase_admin.table('recommended_funds_cache')                         .update({'data': result, 'updated_at': now_utc})                         .eq('username', username).execute()
                    if upd.data:
                        logger.info(f'recommended_funds_cache updated: {len(recommended)} funds')
                    else:
                        ins = supabase_admin.table('recommended_funds_cache')                             .insert({'username': username, 'data': result, 'updated_at': now_utc})                             .execute()
                        logger.info(f'recommended_funds_cache inserted: {bool(ins.data)}')
                    result['_rec_updated_at'] = now_utc
                    result['_rec_cache_time'] = int(datetime.now(_tz.utc).timestamp() * 1000)
                except Exception as _se:
                    logger.error(f'recommended_funds_cache write FAILED: {_se}')

        return jsonify(result)
    except Exception as e:
        logger.error(f'recommended funds failed: {e}')
        return jsonify({'recommendedFunds': []})


def _calc_action(fund, pr: float, market_data: dict, investment_level: str = 'small', blogger_signals: dict = None) -> tuple:
    # 技术面多维度综合决策引擎
    #
    # 设计原则：决策以技术指标为主，实时估值仅作辅助参考（权重与其他指标相同）
    # 需多项技术指标同向共识才触发操作，避免单一指标误判
    #
    # 评分结构（满分约 ±8）：
    #   技术主体：5日趋势、20日均线、MACD、RSI、KDJ-J、布林带 各±1（共±6）
    #   辅助参考：实时估值±1（与技术指标平权，仅作辅助）
    #   环境修正：大盘涨跌±1（门槛提高至2%）
    #
    # 决策阈值（需多项技术信号共识）：
    #   补仓 ≥+4，轻仓补入 ≥+3，持有 -2~+2，观望减持 ≤-3，减仓 ≤-4

    prices = getattr(fund, 'prices', []) or []
    rsi    = getattr(fund, 'rsi', 50) or 50
    macd   = getattr(fund, 'macd', [0, 0, 0]) or [0, 0, 0]
    kdj    = getattr(fund, 'kdj', [0, 0, 0]) or [0, 0, 0]
    bb     = getattr(fund, 'bollinger_bands', [0, 0, 0]) or [0, 0, 0]

    # ── 1. 5日净值趋势（近5日日均涨跌幅，平滑单日噪音）──────────────────────
    trend_5d = 0.0
    if len(prices) >= 6:
        daily_returns = [(prices[-i] / prices[-i-1] - 1) for i in range(1, 6)]
        trend_5d = sum(daily_returns) / len(daily_returns)

    # ── 2. 20日均线方向（中期趋势过滤）─────────────────────────────────────
    ma20_signal = 0
    if len(prices) >= 21:
        ma20 = sum(prices[-20:]) / 20
        if prices[-1] > ma20 * 1.002:    # 站上均线0.2%确认多头
            ma20_signal = 1
        elif prices[-1] < ma20 * 0.998:  # 跌破均线0.2%确认空头
            ma20_signal = -1

    # ── 3. 技术指标打分（每项 -1/0/+1）─────────────────────────────────────
    score = 0

    # 3a. 5日趋势（门槛0.1%，贴合基金日常波动；原0.3%门槛过高）
    if trend_5d > 0.001:
        score += 1
    elif trend_5d < -0.001:
        score -= 1

    # 3b. 20日均线方向
    score += ma20_signal

    # 3c. MACD（金叉+红柱 / 死叉+绿柱）
    ml, sl, hist = macd[0], macd[1], macd[2]
    if ml > sl and hist > 0:
        score += 1
    elif ml < sl and hist < 0:
        score -= 1

    # 3d. RSI（放宽至40/60；原35/65对基金过于极端，日常难触发）
    if rsi < 40:
        score += 1
    elif rsi > 60:
        score -= 1

    # 3e. KDJ-J（放宽至30/70；原20/80过于极端）
    j = kdj[2]
    if j < 30:
        score += 1
    elif j > 70:
        score -= 1

    # 3f. 布林带位置（放宽至30%/70%；原20%/80%区间太窄）
    if bb[0] != bb[2] and prices:
        bb_pct = (prices[-1] - bb[2]) / (bb[0] - bb[2])
        if bb_pct < 0.3:
            score += 1
        elif bb_pct > 0.7:
            score -= 1

    # ── 4. 实时估值辅助（权重与技术指标相同，不主导决策）──────────────────
    # 预估值有一定误差，门槛0.3%过滤日内微小噪音
    has_realtime = getattr(fund, 'has_realtime', False)
    if has_realtime and abs(pr) > 0.003:
        score += 1 if pr > 0 else -1

    # ── 5. 大盘环境修正（门槛提高至2%，避免小幅波动频繁触发）─────────────
    if market_data:
        indices = market_data.get('indices', {})
        if indices:
            avg_market = sum(v.get('change_ratio', 0) for v in indices.values()) / len(indices)
            if avg_market < -0.02:
                score -= 1
            elif avg_market > 0.02:
                score += 1

    # ── 6. 博主信号加权（辅助维度，上限 ±2 分，不单独触发操作建议）──────────
    # blogger_signals: {'buy': N, 'sell': N} 来自调用方预查询的7天数据
    if blogger_signals:
        _b_buy  = blogger_signals.get('buy', 0)
        _b_sell = blogger_signals.get('sell', 0)
        _b_score = 0
        if _b_buy >= 3:
            _b_score += 2   # 3位及以上博主买入，强信号
        elif _b_buy >= 1:
            _b_score += 1   # 1-2位博主买入，弱信号
        if _b_sell >= 3:
            _b_score -= 2
        elif _b_sell >= 1:
            _b_score -= 1
        score += max(-2, min(2, _b_score))  # 限制在 ±2 以内

    # ── 7. 决策输出 ──────────────────────────────────────────────────────────
    AMOUNT_TABLE = {
        'small':  [100, 200, 300, 500],
        'medium': [300, 500, 800, 1000],
        'large':  [800, 1000, 1200, 1500, 2000],
    }
    amounts = AMOUNT_TABLE.get(investment_level, AMOUNT_TABLE['small'])

    def pick_amount(sc, tbl):
        idx = max(0, sc - 4)
        return tbl[min(idx, len(tbl) - 1)]

    if score >= 4:
        action = '补仓'
        suggest_amount = pick_amount(score, amounts)
    elif score <= -4:
        action = '减仓'
        suggest_amount = 0
    elif score >= 3:
        action = '轻仓补入'
        suggest_amount = amounts[0]
    elif score <= -3:
        action = '观望减持'
        suggest_amount = 0
    else:
        action = '持有'
        suggest_amount = 0

    logger.debug(
        f"[决策] {getattr(fund, 'code', '?')} score={score} "
        f"trend5d={trend_5d:.4f} ma20={ma20_signal} rsi={rsi:.1f} "
        f"macd={'up' if ml>sl else 'dn'} kdj_j={j:.1f} bb={bb_pct if bb[0]!=bb[2] and prices else 'n/a'} → {action}"
    )
    return action, suggest_amount
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


# 服务端内存缓存（同一 Vercel 实例内有效，60秒）
_market_cache = {'data': None, 'ts': 0}
MARKET_CACHE_SEC = 60

@app.route('/api/market-data', methods=['GET'])
@performance_monitor
@rate_limit
def get_market_data_api():
    """获取市场数据，包括主要大盘指数和行业板块的实时数据"""
    try:
        import time as _time
        global _market_cache
        now_ts = _time.time()
        # 60秒内直接返回缓存，不重复调东方财富
        if _market_cache['data'] and now_ts - _market_cache['ts'] < MARKET_CACHE_SEC:
            logger.debug('market-data: 服务端内存缓存命中')
            return jsonify(_market_cache['data'])

        logger.info('获取市场数据')
        market_data = get_market_data()
        # 有数据才更新缓存（失败时保留旧缓存）
        if market_data and market_data.get('indices'):
            _market_cache = {'data': market_data, 'ts': now_ts}
        elif _market_cache['data']:
            return jsonify(_market_cache['data'])  # 失败时返回旧缓存
        return jsonify(market_data)
    except Exception as e:
        logger.error(f'获取市场数据失败: {e}')
        if _market_cache.get('data'):
            return jsonify(_market_cache['data'])
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
    port = int(os.environ.get('PORT', 8003))
    logger.debug(f'Starting Flask server on port {port}...')
    logger.debug(f'Server will run on http://localhost:{port}')
    app.run(debug=False, port=port, host='0.0.0.0')