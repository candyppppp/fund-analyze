from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from models.fund import Fund
from utils.indicators import calculate_rsi, calculate_volatility
from utils.data_sources import data_source_manager
import time
import requests
import json
import re
from datetime import datetime, timedelta
import os
import logging

# 配置日志
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
CORS(app)

# 数据文件路径
DATA_FILE = 'funds_data.json'

# 加载基金数据
funds = []

# 定时保存间隔（秒）
SAVE_INTERVAL = 300  # 5分钟

# 上次保存时间
last_save_time = 0

def load_funds():
    """从文件加载基金数据"""
    global funds
    logger.info('开始加载基金数据')
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                fund_data = json.load(f)
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
                        funds.append(fund)
                    except Exception as e:
                        logger.error(f"重建基金对象失败: {e}")
                        continue
                # 更新ID计数器
                if funds:
                    Fund.id_counter = max(fund.id for fund in funds) + 1
                logger.info(f"成功加载 {len(funds)} 只基金")
        except Exception as e:
            logger.error(f"加载基金数据失败: {e}")
            funds = []
    else:
        logger.info("基金数据文件不存在，初始化空列表")
        funds = []


def save_funds():
    """保存基金数据到文件"""
    global funds, last_save_time
    logger.info('开始保存基金数据')
    try:
        # 创建临时文件
        temp_file = DATA_FILE + '.tmp'
        fund_data = [fund.to_dict() for fund in funds]
        # 确保目录存在
        os.makedirs(os.path.dirname(DATA_FILE) if os.path.dirname(DATA_FILE) else '.', exist_ok=True)
        
        # 先写入临时文件
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(fund_data, f, ensure_ascii=False, indent=2)
        
        # 原子操作替换文件
        os.replace(temp_file, DATA_FILE)
        
        last_save_time = time.time()
        logger.info(f"成功保存 {len(funds)} 只基金")
    except Exception as e:
        logger.error(f"保存基金数据失败: {e}")
        # 清理临时文件
        try:
            if os.path.exists(DATA_FILE + '.tmp'):
                os.remove(DATA_FILE + '.tmp')
        except:
            pass

# 定时保存任务
def scheduled_save():
    """定时保存基金数据"""
    while True:
        try:
            time.sleep(SAVE_INTERVAL)
            save_funds()
        except Exception as e:
            logger.error(f"定时保存任务失败: {e}")
            # 继续执行，不中断定时任务

# 定时更新基金数据任务
def scheduled_update_funds():
    """定时更新基金数据，每天0点更新前一天的真实数据"""
    while True:
        try:
            # 获取当前时间
            now = datetime.now()
            # 检查是否是0点
            if now.hour == 0 and now.minute == 0:
                logger.info('开始更新基金数据')
                # 更新所有基金数据
                for fund in funds:
                    try:
                        # 获取最新的基金数据
                        name, prices, dates, returns = get_fund_data(fund.code)
                        # 更新基金数据
                        fund.update_prices(prices, dates, returns)
                        logger.info(f'更新基金 {fund.code} 数据成功')
                    except Exception as e:
                        logger.error(f'更新基金 {fund.code} 数据失败: {e}')
                # 保存更新后的数据
                save_funds()
                logger.info('基金数据更新完成')
                # 避免重复执行，等待61秒
                time.sleep(61)
            else:
                # 每分钟检查一次
                time.sleep(60)
        except Exception as e:
            logger.error(f"定时更新任务失败: {e}")
            # 继续执行，不中断定时任务

# 初始化加载数据
try:
    load_funds()
except Exception as e:
    logger.error(f'初始化加载数据失败: {e}')
    funds = []

# 启动定时保存线程
try:
    import threading
    save_thread = threading.Thread(target=scheduled_save, daemon=True)
    save_thread.start()
    logger.info("定时保存线程已启动")
except Exception as e:
    logger.error(f'启动定时保存线程失败: {e}')

# 启动定时更新基金数据线程
try:
    update_thread = threading.Thread(target=scheduled_update_funds, daemon=True)
    update_thread.start()
    logger.info("定时更新基金数据线程已启动")
except Exception as e:
    logger.error(f'启动定时更新基金数据线程失败: {e}')

# 统一缓存管理类
class CacheManager:
    def __init__(self):
        # 基础缓存配置
        self.caches = {
            'stock': {'data': {}, 'expiry': 300, 'trading_expiry': 15},  # 股票数据：非交易时间5分钟，交易时间15秒
            'fund_holdings': {'data': {}, 'expiry': 28800, 'trading_expiry': 15},  # 基金持仓：非交易时间8小时，交易时间15秒
            'market_data': {'data': {}, 'expiry': 120, 'trading_expiry': 10},  # 市场数据：非交易时间2分钟，交易时间10秒
            'fund_data': {'data': {}, 'expiry': 60, 'trading_expiry': 30}  # 基金数据：非交易时间1分钟，交易时间30秒，确保能及时获取最新数据
        }
        self.hits = 0
        self.misses = 0
    
    def is_trading_time(self):
        """判断是否为交易时间"""
        now = datetime.now()
        is_trading_day = now.weekday() < 5  # 周一到周五
        hour = now.hour
        minute = now.minute
        # 9:30-11:30 和 13:00-15:00 为交易时间
        is_trading_hours = ((hour == 9 and minute >= 30) or (hour == 10) or (hour == 11 and minute < 30) or
                           (hour == 13) or (hour == 14) or (hour == 15 and minute == 0))
        return is_trading_day and is_trading_hours
    
    def get_expiry(self, cache_name):
        """根据交易时间获取缓存过期时间"""
        cache = self.caches.get(cache_name)
        if not cache:
            return 300  # 默认5分钟
        
        if self.is_trading_time():
            return cache.get('trading_expiry', cache['expiry'])
        else:
            return cache['expiry']
    
    def get(self, cache_name, key):
        """获取缓存数据"""
        cache = self.caches.get(cache_name)
        if not cache:
            self.misses += 1
            return None
        
        item = cache['data'].get(key)
        if not item:
            self.misses += 1
            return None
        
        # 检查缓存是否过期
        current_time = time.time()
        expiry = self.get_expiry(cache_name)
        if current_time - item['timestamp'] < expiry:
            self.hits += 1
            return item['data']
        else:
            # 缓存过期，删除
            del cache['data'][key]
            self.misses += 1
            return None
    
    def set(self, cache_name, key, data):
        """设置缓存数据"""
        cache = self.caches.get(cache_name)
        if not cache:
            return
        
        cache['data'][key] = {
            'timestamp': time.time(),
            'data': data
        }
        
        # 限制缓存大小，防止内存溢出
        max_items = 1000  # 每个缓存最多存储1000个项目
        if len(cache['data']) > max_items:
            # 删除最旧的项目
            sorted_items = sorted(cache['data'].items(), key=lambda x: x[1]['timestamp'])
            items_to_delete = len(cache['data']) - max_items
            for item_key, _ in sorted_items[:items_to_delete]:
                del cache['data'][item_key]
    
    def clear(self, cache_name=None):
        """清除缓存"""
        if cache_name:
            if cache_name in self.caches:
                self.caches[cache_name]['data'] = {}
                logger.info(f"清除缓存: {cache_name}")
        else:
            for cache_name in self.caches:
                self.caches[cache_name]['data'] = {}
            logger.info("清除所有缓存")
    
    def get_stats(self):
        """获取缓存统计信息"""
        stats = {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': self.hits / (self.hits + self.misses) * 100 if (self.hits + self.misses) > 0 else 0,
            'cache_sizes': {}
        }
        for cache_name, cache in self.caches.items():
            stats['cache_sizes'][cache_name] = len(cache['data'])
        return stats

# 创建缓存管理器实例
cache_manager = CacheManager()

# 获取基金持仓数据
def get_fund_holdings(code):
    """获取基金的持仓数据"""
    # 检查缓存
    cache_key = f"fund_holdings_{code}"
    cached_data = cache_manager.get('fund_holdings', cache_key)
    
    if cached_data:
        return cached_data
    
    holdings = {
        'stocks': [],
        'stock_ratio': 0
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    data_obtained = False
    
    # 优先从东方财富JS数据获取（响应速度快，数据结构清晰）
    try:
        fund_data_url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
        response = requests.get(fund_data_url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data_str = response.text
            
            # 尝试提取 Data_holdStock 变量（优先使用，包含真实持仓数据）
            data_hold_stock_match = re.search(r'var Data_holdStock = \[(.*?)\];', data_str, re.DOTALL)
            if data_hold_stock_match:
                data_hold_stock_str = data_hold_stock_match.group(1)
                try:
                    data_hold_stock = json.loads('[' + data_hold_stock_str + ']')
                    
                    for stock in data_hold_stock:  # 显示全部股票
                        try:
                            stock_code = stock.get('code', '')
                            stock_name = stock.get('name', '')
                            weight = stock.get('percent', 0) * 100  # 转换为百分比
                            
                            if stock_code and stock_name and weight > 0:
                                # 清理股票代码
                                clean_code = stock_code.split('.')[0]
                                if clean_code.isdigit() and len(clean_code) == 6:
                                    stock_info = {
                                        'code': clean_code,
                                        'name': stock_name,
                                        'weight': weight
                                    }
                                    holdings['stocks'].append(stock_info)
                        except Exception:
                            pass
                    if holdings['stocks']:
                        data_obtained = True
                except Exception:
                    pass
            
            # 如果 Data_holdStock 为空，尝试提取其他变量
            if not data_obtained:
                # 尝试提取 Data_holdStockNew 变量
                data_hold_stock_new_match = re.search(r'var Data_holdStockNew = \[(.*?)\];', data_str, re.DOTALL)
                if data_hold_stock_new_match:
                    data_hold_stock_new_str = data_hold_stock_new_match.group(1)
                    try:
                        data_hold_stock_new = json.loads('[' + data_hold_stock_new_str + ']')
                        
                        for stock in data_hold_stock_new:  # 显示全部股票
                            try:
                                stock_code = stock.get('code', '')
                                stock_name = stock.get('name', '')
                                weight = stock.get('percent', 0) * 100  # 转换为百分比
                                
                                if stock_code and stock_name and weight > 0:
                                    # 清理股票代码
                                    clean_code = stock_code.split('.')[0]
                                    if clean_code.isdigit() and len(clean_code) == 6:
                                        stock_info = {
                                            'code': clean_code,
                                            'name': stock_name,
                                            'weight': weight
                                        }
                                        holdings['stocks'].append(stock_info)
                            except Exception:
                                pass
                        if holdings['stocks']:
                            data_obtained = True
                    except Exception:
                        pass
            
            # 如果仍然没有数据，尝试提取 stockCodes 和 stockNames 变量
            if not data_obtained:
                # 尝试提取 stockCodes 变量
                stock_codes_match = re.search(r'var stockCodes\s*=\s*\[(.*?)\];', data_str)
                if stock_codes_match:
                    stock_codes_str = stock_codes_match.group(1)
                    try:
                        stock_codes = json.loads('[' + stock_codes_str + ']')
                        
                        # 尝试提取 stockNames 变量
                        stock_names_match = re.search(r'var stockNames\s*=\s*\[(.*?)\];', data_str)
                        stock_names = []
                        if stock_names_match:
                            try:
                                stock_names_str = stock_names_match.group(1)
                                stock_names = json.loads('[' + stock_names_str + ']')
                            except Exception:
                                pass
                        
                        # 为每只股票创建默认数据
                        for i, code in enumerate(stock_codes):  # 显示全部股票
                            # 移除可能的市场代码后缀（如.SH, .SZ）
                            clean_code = code.split('.')[0]
                            
                            # 处理特殊格式的股票代码，如6005191（可能是带市场标识的格式）
                            # 提取前6位数字作为股票代码
                            if len(clean_code) >= 6:
                                # 提取前6位数字
                                clean_code = ''.join(filter(str.isdigit, clean_code))[:6]
                            elif len(clean_code) < 6:
                                # 不足6位的代码可能是无效的，跳过
                                continue
                            
                            # 确保股票代码是有效的6位数字
                            if not clean_code.isdigit() or len(clean_code) != 6:
                                continue
                            
                            # 过滤掉非A股代码（只保留沪市6开头、深市0或3开头、科创板688开头的股票）
                            if not (clean_code.startswith('6') or clean_code.startswith('0') or clean_code.startswith('3')):
                                continue
                            
                            # 过滤掉可能的非股票代码（如基金代码等）
                            # 简单判断：只保留常见的A股代码范围
                            if clean_code.startswith('6'):
                                # 沪市股票：600000-699999
                                if not (600000 <= int(clean_code) <= 699999):
                                    continue
                            elif clean_code.startswith('0'):
                                # 深市主板：000001-001999
                                if not (1 <= int(clean_code) <= 1999):
                                    continue
                            elif clean_code.startswith('3'):
                                # 创业板：300000-300999
                                if not (300000 <= int(clean_code) <= 300999):
                                    continue
                            
                            # 生成默认权重
                            weight = 10.0 - i * 0.5  # 模拟权重递减
                            # 尝试获取股票名称
                            stock_name = f"股票{clean_code}"
                            if i < len(stock_names):
                                stock_name = stock_names[i]
                            
                            stock_info = {
                                'code': clean_code,
                                'name': stock_name,
                                'weight': weight
                            }
                            holdings['stocks'].append(stock_info)
                        if holdings['stocks']:
                            data_obtained = True
                    except Exception:
                        pass
            
            # 尝试提取资产配置数据
            asset_match = re.search(r'var Data_assetAllocation = \[(.*?)\];', data_str, re.DOTALL)
            if asset_match:
                try:
                    asset_data = asset_match.group(1)
                    # 尝试解析资产配置数据
                    if '{' in asset_data:
                        # 尝试解析为JSON
                        try:
                            asset_json = json.loads('[' + asset_data + ']')
                            for item in asset_json:
                                if item.get('assetType') == '股票' or item.get('name') == '股票':
                                    holdings['stock_ratio'] = float(item.get('ratio', 0)) * 100
                                    break
                        except Exception:
                            pass
                except Exception:
                    pass
            
            # 如果没有提取到资产配置数据，尝试从其他地方获取
            if holdings['stock_ratio'] == 0 and holdings['stocks']:
                # 计算股票总权重作为股票占比
                total_weight = sum(stock['weight'] for stock in holdings['stocks'])
                if total_weight > 0:
                    holdings['stock_ratio'] = min(total_weight, 100.0)
    except Exception as e:
        print(f"获取基金持仓数据失败: {e}")
    
    # 如果从JS数据获取失败，尝试从HTML页面获取
    if not data_obtained:
        try:
            fund_url = f"http://fund.eastmoney.com/{code}.html"
            response = requests.get(fund_url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data_str = response.text
                
                # 尝试提取股票持仓
                stock_matches = re.findall(r'class="fundStockList".*?<table.*?>(.*?)</table>', data_str, re.DOTALL)
                if stock_matches:
                    table_html = stock_matches[0]
                    row_matches = re.findall(r'<tr.*?>(.*?)</tr>', table_html, re.DOTALL)
                    for row in row_matches[1:]:  # 跳过表头，显示全部股票
                        name_match = re.search(r'<a.*?>(.*?)</a>', row)
                        code_match = re.search(r'\((\d{6})\)', row)
                        weight_match = re.search(r'<td.*?>(\d+\.?\d*)%</td>', row)
                        
                        if name_match and code_match and weight_match:
                            stock_info = {
                                'name': name_match.group(1),
                                'code': code_match.group(1),
                                'weight': float(weight_match.group(1))
                            }
                            holdings['stocks'].append(stock_info)
                    if holdings['stocks']:
                        data_obtained = True
                
                # 尝试提取资产配置数据
                asset_match = re.search(r'资产配置.*?<table.*?>(.*?)</table>', data_str, re.DOTALL)
                if asset_match:
                    asset_html = asset_match[1]
                    stock_ratio_match = re.search(r'股票.*?<td.*?>(\d+\.?\d*)%</td>', asset_html)
                    if stock_ratio_match:
                        holdings['stock_ratio'] = float(stock_ratio_match.group(1))
        except Exception as e:
            print(f"从HTML获取基金持仓数据失败: {e}")
    
    # 清理无效的股票代码并获取股票名称
    valid_stocks = []
    for stock in holdings['stocks']:
        code = stock['code']
        if code.isdigit() and len(code) == 6:
            # 只有在股票名称为空时才尝试获取
            if not stock.get('name') or stock['name'] == f"股票{code}":
                stock['name'] = get_stock_name(code)
            valid_stocks.append(stock)
    holdings['stocks'] = valid_stocks
    
    # 如果获取数据失败，尝试使用缓存中的旧数据
    if not data_obtained:
        # 尝试从缓存获取旧数据
        old_data = cache_manager.get('fund_holdings', cache_key)
        if old_data:
            return old_data
    
    # 存储到缓存
    cache_manager.set('fund_holdings', cache_key, holdings)
    
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
    except Exception:
        pass
    
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
    except Exception:
        pass
    
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
    except Exception:
        pass
    
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
    except Exception:
        pass
    
    # 如果所有数据源都失败，返回默认名称
    return f'股票{stock_code}'

# 批量获取股票实时数据
def get_batch_stock_real_time_data(stock_codes):
    """批量获取股票的实时数据，减少API调用次数"""
    results = {}
    cached_stocks = []
    uncached_stocks = []
    
    # 检查缓存
    for stock_code in stock_codes:
        cache_key = f"stock_{stock_code}"
        cached_data = cache_manager.get('stock', cache_key)
        if cached_data:
            results[stock_code] = cached_data
            cached_stocks.append(stock_code)
        else:
            uncached_stocks.append(stock_code)
    
    # 批量获取未缓存的股票数据
    if uncached_stocks:
        # 限制批量请求数量，避免API限制
        batch_size = 10
        for i in range(0, len(uncached_stocks), batch_size):
            batch_codes = uncached_stocks[i:i+batch_size]
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
                                            # 存储到缓存
                                            cache_key = f"stock_{stock_code}"
                                            cache_manager.set('stock', cache_key, stock_data)
                            except Exception as e:
                                print(f"解析股票数据失败: {e}")
                else:
                    for stock_code in batch_codes:
                        results[stock_code] = {
                            'current_price': 0,
                            'change_amount': 0,
                            'change_ratio': 0
                        }
            except Exception as e:
                print(f"获取批量股票数据失败: {e}")
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
    # 检查缓存
    cache_key = f"stock_{stock_code}"
    cached_data = cache_manager.get('stock', cache_key)
    if cached_data:
        return cached_data
    
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
    # 检查缓存
    cache_key = "market_data"
    cached_data = cache_manager.get('market_data', cache_key)
    if cached_data:
        return cached_data
    
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
                        print(f"解析市场数据失败: {e}")
            
            # 存储到缓存
            cache_manager.set('market_data', cache_key, result)
            
            return result
        else:
            return {'indices': {}, 'sectors': {}}
    except Exception as e:
        print(f"获取市场数据失败: {e}")
        return {'indices': {}, 'sectors': {}}

# 获取基金数据
def get_fund_data(code):
    # 检查缓存
    cache_key = f"fund_data_{code}"
    cached_data = cache_manager.get('fund_data', cache_key)
    if cached_data:
        logger.info(f"从缓存获取基金 {code} 数据")
        return cached_data['name'], cached_data['prices'], cached_data['dates'], cached_data['returns']
    
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
            if latest_nav_data['jzrq'] and latest_nav_data['dwjz']:
                date_str = latest_nav_data['jzrq']
                nav = latest_nav_data['dwjz']
                prices.append(nav)
                dates.append(date_str)
                logger.info(f"从新浪财经获取基金 {code} 数据: 日期={date_str}, 净值={nav}")
        
        # 从天天基金网API获取历史数据
        historical_data = data_source_manager.get_fund_historical_data(code)
        if historical_data:
            prices.extend(historical_data['prices'])
            dates.extend(historical_data['dates'])
            returns = historical_data['returns']
            logger.info(f"从天天基金网获取基金 {code} 历史数据，共 {len(historical_data['prices'])} 条记录")
        
        # 去重处理，避免重复数据
        unique_data = {}
        for date, price in zip(dates, prices):
            unique_data[date] = price
        
        # 确保新浪财经API返回的最新数据被保留
        if latest_nav_data and latest_nav_data['jzrq'] and latest_nav_data['dwjz']:
            date_str = latest_nav_data['jzrq']
            nav = latest_nav_data['dwjz']
            unique_data[date_str] = nav
            logger.info(f"确保新浪财经最新数据被保留: 日期={date_str}, 净值={nav}")
        
        # 按日期排序
        sorted_dates = sorted(unique_data.keys())
        sorted_prices = [unique_data[date] for date in sorted_dates]
        
        # 计算收益率数据
        if len(sorted_prices) > 1 and not returns:
            returns = []
            for i in range(1, len(sorted_prices)):
                try:
                    daily_return = (sorted_prices[i] - sorted_prices[i-1]) / sorted_prices[i-1]
                    returns.append(daily_return)
                except (ZeroDivisionError, TypeError):
                    returns.append(0)
            returns.insert(0, 0)
        
        # 存储到缓存
        fund_data = {
            'name': name,
            'prices': sorted_prices,
            'dates': sorted_dates,
            'returns': returns
        }
        cache_manager.set('fund_data', cache_key, fund_data)
        
        logger.info(f"获取基金 {code} 数据成功，共 {len(sorted_prices)} 条记录")
        return name, sorted_prices, sorted_dates, returns
    except Exception as e:
        logger.error(f"获取基金数据失败: {e}")
        # 如果API调用失败，返回空数据
        return f'基金{code}', [], [], []

@app.route('/')
def index():
    return render_template('index.html')

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
        logger.info('获取基金列表')
        
        # 立即返回当前基金数据，不等待更新完成
        # 这样可以快速响应前端请求
        current_funds = [fund.to_dict() for fund in funds]
        
        # 确保返回的数据不为空，即使网络不好
        if not current_funds:
            # 尝试从文件加载数据
            try:
                load_funds()
                current_funds = [fund.to_dict() for fund in funds]
                logger.info('从文件加载基金数据')
            except Exception as e:
                logger.error(f'加载基金数据失败: {e}')
        
        # 后台异步更新基金数据
        def update_funds_async():
            try:
                # 只获取一次市场数据，避免重复请求
                market_data = get_market_data()
                
                # 更新每个基金的最新数据
                for fund in funds:
                    try:
                        # 获取最新的基金数据
                        name, prices, dates, returns = get_fund_data(fund.code)
                        
                        # 获取实时预估收益率数据
                        real_time_estimated_return = data_source_manager.get_fund_estimated_return(fund.code)
                        
                        # 获取持仓数据
                        holdings = get_fund_holdings(fund.code)
                        
                        # 更新基金数据，包括实时预估收益率
                        fund.update_prices(prices, dates, returns, market_data=market_data)
                        
                        # 更新预测收益率，使用实时预估数据
                        fund.predicted_return = fund.calculate_predicted_return(
                            stock_holdings=holdings,
                            market_data=market_data,
                            real_time_estimated_return=real_time_estimated_return
                        )
                        fund.prediction_confidence = fund.calculate_prediction_confidence()
                        
                        logger.info(f'更新基金 {fund.code} 数据成功')
                    except Exception as e:
                        logger.error(f'更新基金 {fund.code} 数据失败: {e}')
                        # 继续处理下一个基金，不影响其他基金
                        continue
                # 保存更新后的数据
                save_funds()
                logger.info('后台更新基金数据完成')
            except Exception as e:
                logger.error(f'后台更新基金数据失败: {e}')
                # 后台更新失败不影响返回数据
        
        # 启动后台更新线程
        import threading
        update_thread = threading.Thread(target=update_funds_async, daemon=True)
        update_thread.start()
        
        # 立即返回当前数据，确保即使网络不好也能返回基金列表
        return jsonify(current_funds)
    except Exception as e:
        logger.error(f'获取基金列表失败: {e}')
        # 即使出现异常，也尝试返回已存储的基金数据
        try:
            current_funds = [fund.to_dict() for fund in funds]
            if current_funds:
                return jsonify(current_funds)
        except:
            pass
        # 最后才返回空数组
        return jsonify([]), 500

@app.route('/api/funds', methods=['POST'])
@performance_monitor
@rate_limit
def add_fund():
    try:
        data = request.get_json()
        if not data or 'code' not in data:
            logger.error('添加基金失败: 缺少基金代码')
            return jsonify({'error': '缺少基金代码'}), 400
        
        code = data['code']
        logger.info(f'添加基金: {code}')
        
        # 检查基金是否已经存在
        for existing_fund in funds:
            if existing_fund.code == code:
                logger.warning(f'基金已经存在: {code}')
                return jsonify({'error': '基金已经存在'}), 400
        
        # 额外的安全检查，确保不会重复添加
        logger.info(f'基金 {code} 不存在，准备添加')
        
        # 异步获取基金数据，提高响应速度
        import threading
        result = {}
        error = None
        
        def fetch_data():
            nonlocal result, error
            try:
                # 并行获取数据，提高性能
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                    # 提交并行任务
                    future_fund = executor.submit(get_fund_data, code)
                    future_market = executor.submit(get_market_data)
                    future_holdings = executor.submit(get_fund_holdings, code)
                    future_estimated_return = executor.submit(data_source_manager.get_fund_estimated_return, code)
                    
                    # 等待所有任务完成
                    name, prices, dates, returns = future_fund.result(timeout=8)
                    market_data = future_market.result(timeout=3)
                    holdings = future_holdings.result(timeout=8)
                    real_time_estimated_return = future_estimated_return.result(timeout=3)
                
                result = {
                    'name': name,
                    'prices': prices,
                    'dates': dates,
                    'returns': returns,
                    'holdings': holdings,
                    'market_data': market_data,
                    'real_time_estimated_return': real_time_estimated_return
                }
            except Exception as e:
                nonlocal error
                error = str(e)
                logger.error(f'获取基金数据失败: {e}')
        
        # 启动线程获取数据
        thread = threading.Thread(target=fetch_data)
        thread.start()
        thread.join(timeout=12)  # 设置12秒超时，给并行任务足够时间
        
        if error:
            return jsonify({'error': error}), 500
        
        if not result:
            return jsonify({'error': '获取基金数据超时'}), 504
        
        # 检查数据是否有效
        if not result['prices']:
            logger.warning(f'基金数据无效: {code}')
            # 仍然创建基金对象，但数据为空
            pass
        
        fund = Fund(result['name'], code, result['prices'], result['dates'], result['returns'])
        # 使用市场数据、持仓数据和实时预估收益率更新预测
        fund.predicted_return = fund.calculate_predicted_return(
            stock_holdings=result['holdings'], 
            market_data=result['market_data'],
            real_time_estimated_return=result['real_time_estimated_return']
        )
        fund.prediction_confidence = fund.calculate_prediction_confidence()
        funds.append(fund)
        # 保存数据到文件
        save_funds()
        logger.info(f'基金添加成功: {code}')
        return jsonify(fund.to_dict()), 201
    except Exception as e:
        logger.error(f'添加基金失败: {e}')
        return jsonify({'error': str(e)}), 400

@app.route('/api/funds/<int:fund_id>', methods=['DELETE'])
@performance_monitor
@rate_limit
def delete_fund(fund_id):
    try:
        logger.info(f'删除基金: {fund_id}')
        global funds
        original_length = len(funds)
        funds = [fund for fund in funds if fund.id != fund_id]
        if len(funds) == original_length:
            logger.warning(f'基金不存在: {fund_id}')
            return jsonify({'error': '基金不存在'}), 404
        # 保存数据到文件
        save_funds()
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
        
        # 检查缓存
        cache_key = f"fund_holdings_api_{code}"
        cached_data = cache_manager.get('fund_holdings', cache_key)
        if cached_data:
            logger.info(f'从缓存获取基金持仓API数据: {code}')
            return jsonify(cached_data)
        
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
        
        # 缓存响应数据
        cache_manager.set('fund_holdings', cache_key, holdings_data)
        
        logger.info(f'获取基金持仓数据成功: {code}')
        return jsonify(holdings_data)
    except Exception as e:
        logger.error(f'获取基金持仓数据失败: {e}')
        return jsonify({'stocks': [], 'stock_ratio': 0, 'market_data': {'indices': {}, 'sectors': {}}})

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8002))
    print(f'Starting Flask server on port {port}...')
    print(f'Server will run on http://localhost:{port}')
    app.run(debug=False, port=port, host='0.0.0.0')