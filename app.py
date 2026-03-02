from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from models.fund import Fund
from utils.indicators import calculate_rsi, calculate_volatility
import time
import requests
import json
import re
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

funds = []

# 股票数据缓存
stock_cache = {}
stock_cache_expiry = 300  # 股票数据缓存时间（秒），增加到5分钟，减少API调用

# 基金持仓数据缓存
fund_holdings_cache = {}
fund_holdings_cache_expiry = 28800  # 基金持仓数据缓存时间（秒），8小时，减少API调用

# 市场数据缓存
market_data_cache = {}
market_data_cache_expiry = 120  # 市场数据缓存时间（秒），2分钟

# 获取基金持仓数据
def get_fund_holdings(code):
    """获取基金的持仓数据"""
    # 检查缓存
    cache_key = f"fund_holdings_{code}"
    current_time = time.time()
    
    if cache_key in fund_holdings_cache and current_time - fund_holdings_cache[cache_key]['timestamp'] < fund_holdings_cache_expiry:
        print(f"从缓存获取基金 {code} 持仓数据")
        return fund_holdings_cache[cache_key]['data']
    
    holdings = {
        'stocks': [],
        'stock_ratio': 0
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    # 优先从东方财富JS数据获取（响应速度快，数据结构清晰）
    try:
        print("尝试从东方财富JS数据获取基金持仓数据...")
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
                    print(f"成功解析 Data_holdStock，共 {len(data_hold_stock)} 只股票")
                    
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
                                    print(f"添加股票: {stock_name}, 代码: {clean_code}, 权重: {weight}%")
                        except Exception as e:
                            print(f"解析股票数据失败: {e}")
                except Exception as e:
                    print(f"解析 Data_holdStock 失败: {e}")
            
            # 如果 Data_holdStock 为空，尝试提取其他变量
            if not holdings['stocks']:
                # 尝试提取 Data_holdStockNew 变量
                data_hold_stock_new_match = re.search(r'var Data_holdStockNew = \[(.*?)\];', data_str, re.DOTALL)
                if data_hold_stock_new_match:
                    data_hold_stock_new_str = data_hold_stock_new_match.group(1)
                    try:
                        data_hold_stock_new = json.loads('[' + data_hold_stock_new_str + ']')
                        print(f"成功解析 Data_holdStockNew，共 {len(data_hold_stock_new)} 只股票")
                        
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
                                        print(f"添加股票: {stock_name}, 代码: {clean_code}, 权重: {weight}%")
                            except Exception as e:
                                print(f"解析股票数据失败: {e}")
                    except Exception as e:
                        print(f"解析 Data_holdStockNew 失败: {e}")
            
            # 如果仍然没有数据，尝试提取 stockCodes 和 stockNames 变量
            if not holdings['stocks']:
                # 尝试提取 stockCodes 变量
                stock_codes_match = re.search(r'var stockCodes\s*=\s*\[(.*?)\];', data_str)
                if stock_codes_match:
                    stock_codes_str = stock_codes_match.group(1)
                    try:
                        stock_codes = json.loads('[' + stock_codes_str + ']')
                        print(f"成功解析 stockCodes，共 {len(stock_codes)} 只股票")
                        
                        # 尝试提取 stockNames 变量
                        stock_names_match = re.search(r'var stockNames\s*=\s*\[(.*?)\];', data_str)
                        stock_names = []
                        if stock_names_match:
                            try:
                                stock_names_str = stock_names_match.group(1)
                                stock_names = json.loads('[' + stock_names_str + ']')
                                print(f"成功解析 stockNames，共 {len(stock_names)} 个股票名称")
                            except Exception as e:
                                print(f"解析 stockNames 失败: {e}")
                        
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
                            print(f"添加股票: {stock_name}, 代码: {clean_code}, 权重: {weight}%")
                    except Exception as e:
                        print(f"解析 stockCodes 失败: {e}")
            
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
                                    print(f"提取到股票占比: {holdings['stock_ratio']}%")
                                    break
                        except Exception as e:
                            print(f"解析资产配置JSON失败: {e}")
                except Exception as e:
                    print(f"提取资产配置数据失败: {e}")
            
            # 如果没有提取到资产配置数据，尝试从其他地方获取
            if holdings['stock_ratio'] == 0 and holdings['stocks']:
                # 计算股票总权重作为股票占比
                total_weight = sum(stock['weight'] for stock in holdings['stocks'])
                if total_weight > 0:
                    holdings['stock_ratio'] = min(total_weight, 100.0)
                    print(f"计算股票占比: {holdings['stock_ratio']}%")
    except Exception as e:
        print(f"从东方财富JS数据获取持仓数据失败: {e}")
    
    # 如果从JS数据获取失败，尝试从HTML页面获取
    if not holdings['stocks']:
        try:
            print("尝试从东方财富HTML页面获取基金持仓数据...")
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
                            print(f"添加股票: {stock_info['name']}, 代码: {stock_info['code']}, 权重: {stock_info['weight']}%")
                
                # 尝试提取资产配置数据
                asset_match = re.search(r'资产配置.*?<table.*?>(.*?)</table>', data_str, re.DOTALL)
                if asset_match:
                    asset_html = asset_match[1]
                    stock_ratio_match = re.search(r'股票.*?<td.*?>(\d+\.?\d*)%</td>', asset_html)
                    if stock_ratio_match:
                        holdings['stock_ratio'] = float(stock_ratio_match.group(1))
                        print(f"提取到股票占比: {holdings['stock_ratio']}%")
        except Exception as e:
            print(f"从HTML页面获取数据失败: {e}")
    
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
    
    # 存储到缓存
    fund_holdings_cache[cache_key] = {
        'timestamp': time.time(),
        'data': holdings
    }
    
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
                    print(f"从东方财富API获取股票名称: {stock_name}")
                    return stock_name
    except Exception as e:
        print(f"从东方财富API获取股票 {stock_code} 名称失败: {e}")
    
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
            # 新浪财经API返回格式: var hq_str_sh600519="贵州茅台,1785.00,1779.00,1781.00,1798.00,1765.00,1781.00,1782.00,14700,26284700,100,1781.00,200,1780.00,300,1779.00,500,1778.00,200,1777.00,100,1782.00,200,1783.00,300,1784.00,500,1785.00,200,1786.00,2025-12-12,15:00:03,00"
            name_match = re.search(r'"(.*?),', stock_data)
            if name_match:
                stock_name = name_match.group(1)
                if stock_name and stock_name != '' and stock_name != 'null':
                    print(f"从新浪财经API获取股票名称: {stock_name}")
                    return stock_name
    except Exception as e:
        print(f"从新浪财经API获取股票 {stock_code} 名称失败: {e}")
    
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
                    print(f"从百度股票API获取股票名称: {stock_name}")
                    return stock_name
    except Exception as e:
        print(f"从百度股票API获取股票 {stock_code} 名称失败: {e}")
    
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
                    print(f"从同花顺API获取股票名称: {stock_name}")
                    return stock_name
    except Exception as e:
        print(f"从同花顺API获取股票 {stock_code} 名称失败: {e}")
    
    # 如果所有数据源都失败，返回默认名称
    default_name = f'股票{stock_code}'
    print(f"使用默认股票名称: {default_name}")
    return default_name

# 批量获取股票实时数据
def get_batch_stock_real_time_data(stock_codes):
    """批量获取股票的实时数据，减少API调用次数"""
    results = {}
    cached_stocks = []
    uncached_stocks = []
    
    # 检查缓存
    current_time = time.time()
    for stock_code in stock_codes:
        cache_key = f"stock_{stock_code}"
        if cache_key in stock_cache and current_time - stock_cache[cache_key]['timestamp'] < stock_cache_expiry:
            results[stock_code] = stock_cache[cache_key]['data']
            cached_stocks.append(stock_code)
        else:
            uncached_stocks.append(stock_code)
    
    if cached_stocks:
        print(f"从缓存获取股票数据: {cached_stocks}")
    
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
                print(f"批量获取股票实时数据: {stock_url}")
                response = requests.get(stock_url, headers=headers, timeout=3)  # 减少超时时间
                
                if response.status_code == 200:
                    stock_data = response.text
                    print(f"批量获取股票数据成功，长度: {len(stock_data)}")
                    
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
                                            stock_cache[cache_key] = {
                                                'timestamp': time.time(),
                                                'data': stock_data
                                            }
                            except Exception as e:
                                print(f"解析股票数据失败: {e}")
                else:
                    print(f"股票实时数据API响应状态: {response.status_code}")
                    for stock_code in batch_codes:
                        results[stock_code] = {
                            'current_price': 0,
                            'change_amount': 0,
                            'change_ratio': 0
                        }
            except Exception as e:
                print(f"批量获取股票实时数据失败: {e}")
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
    current_time = time.time()
    
    if cache_key in stock_cache and current_time - stock_cache[cache_key]['timestamp'] < stock_cache_expiry:
        print(f"从缓存获取股票 {stock_code} 数据")
        return stock_cache[cache_key]['data']
    
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
    current_time = time.time()
    
    if cache_key in market_data_cache and current_time - market_data_cache[cache_key]['timestamp'] < market_data_cache_expiry:
        print("从缓存获取市场数据")
        return market_data_cache[cache_key]['data']
    
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
        print(f"获取市场数据: {market_url}")
        response = requests.get(market_url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            market_data = response.text
            print(f"市场数据获取成功，长度: {len(market_data)}")
            
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
            market_data_cache[cache_key] = {
                'timestamp': time.time(),
                'data': result
            }
            
            print(f"市场数据解析完成，指数: {len(result['indices'])}, 板块: {len(result['sectors'])}")
            return result
        else:
            print(f"市场数据API响应状态: {response.status_code}")
            return {'indices': {}, 'sectors': {}}
    except Exception as e:
        print(f"获取市场数据失败: {e}")
        return {'indices': {}, 'sectors': {}}

# 获取基金数据
def get_fund_data(code):
    try:
        print(f"开始获取基金 {code} 数据...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        # 初始化变量
        name = f'基金{code}'
        prices = []
        dates = []
        returns = []
        
        # 数据源1: 新浪财经API
        try:
            print("尝试使用新浪财经API获取基金基本信息和净值...")
            fund_url = f"http://fundgz.1234567.com.cn/js/{code}.js"
            response = requests.get(fund_url, headers=headers, timeout=5)
            response.encoding = 'utf-8'
            
            # 检查响应状态
            if response.status_code == 200:
                # 解析新浪财经的JS格式数据
                data_str = response.text.strip().replace('jsonpgz(', '').replace(');', '')
                data = json.loads(data_str)
                
                # 提取基金名称
                name = data.get('name', f'基金{code}')
                print(f"新浪财经API获取到基金名称: {name}")
                
                # 提取当前净值和日期
                if 'jzrq' in data and 'dwjz' in data:
                    date_str = data['jzrq']
                    nav = float(data['dwjz'])
                    # 先添加新浪财经的最新数据
                    prices.append(nav)
                    dates.append(date_str)
                    print(f"新浪财经API获取到最新净值数据: {date_str} - {nav}")
            else:
                print(f"新浪财经API响应状态错误: {response.status_code}")
        except Exception as e:
            print(f"新浪财经API失败: {e}")
            # 数据源2: 天天基金网API
            try:
                print("尝试使用天天基金网API获取基金基本信息...")
                fund_url = f"https://fund.eastmoney.com/{code}.html"
                response = requests.get(fund_url, headers=headers, timeout=5)
                response.encoding = 'utf-8'
                
                # 检查响应状态
                if response.status_code == 200:
                    # 简单解析HTML获取基金名称
                    import re
                    match = re.search(r'<title>(.*?)_基金净值_天天基金网</title>', response.text)
                    if match:
                        name = match.group(1)
                        print(f"天天基金网API获取到基金名称: {name}")
                    else:
                        print("天天基金网API未获取到基金名称")
                else:
                    print(f"天天基金网API响应状态错误: {response.status_code}")
            except Exception as e:
                print(f"天天基金网API失败: {e}")
        
        # 获取历史净值数据
        # 数据源1: 天天基金网API（优先使用，因为提供更完整的历史数据）
        try:
            print("尝试使用天天基金网API获取历史净值数据...")
            # 天天基金网净值API
            fund_data_url = f"https://fund.eastmoney.com/f10/F10DataApi.aspx?type=lsjz&code={code}&page=1&per=100"
            print(f"天天基金网API URL: {fund_data_url}")
            
            # 使用更完整的请求头
            tian_tian_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": f"https://fund.eastmoney.com/{code}.html",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Connection": "keep-alive"
            }
            
            response = requests.get(fund_data_url, headers=tian_tian_headers, timeout=10)
            
            print(f"天天基金网API响应状态: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    # 打印响应的前500个字符，以便调试
                    print(f"天天基金网API响应前500字符: {response.text[:500]}...")
                    
                    # 解析HTML数据
                    # 使用字符串操作提取content部分
                    try:
                        # 找到content的起始位置
                        content_start = response.text.find('content:"')
                        if content_start != -1:
                            content_start += len('content:"')
                            # 找到content的结束位置
                            content_end = response.text.find('"', content_start)
                            if content_end != -1:
                                content = response.text[content_start:content_end]
                                # 然后从content中提取表格
                                table_start = content.find('<table')
                                table_end = content.find('</table>', table_start)
                                if table_start != -1 and table_end != -1:
                                    table_html = content[table_start:table_end + len('</table>')]
                                    # 提取行数据
                                    row_start = table_html.find('<tr')
                                    rows = []
                                    while row_start != -1:
                                        row_end = table_html.find('</tr>', row_start)
                                        if row_end != -1:
                                            rows.append(table_html[row_start:row_end + len('</tr>')])
                                            row_start = table_html.find('<tr', row_end)
                                        else:
                                            break
                                    
                                    # 存储天天基金网的数据，以便后续处理
                                    tian_tian_prices = []
                                    tian_tian_dates = []
                                    
                                    for i, row in enumerate(rows):
                                        if i == 0:  # 跳过表头
                                            continue
                                        # 提取列数据
                                        col_start = row.find('<td')
                                        cols = []
                                        while col_start != -1:
                                            col_end = row.find('</td>', col_start)
                                            if col_end != -1:
                                                # 提取td标签内的内容
                                                col_content = row[col_start:col_end + len('</td>')]
                                                # 去除标签
                                                col_text = col_content.replace('<td', '').replace('</td>', '').replace('class="tor bold"', '').replace('class="tor bold red"', '').replace('class="red unbold"', '').strip()
                                                # 提取文本内容
                                                text_start = col_text.find('>')
                                                if text_start != -1:
                                                    col_text = col_text[text_start + 1:].strip()
                                                cols.append(col_text)
                                                col_start = row.find('<td', col_end)
                                            else:
                                                break
                                        
                                        if len(cols) >= 4:
                                            date_str = cols[0]
                                            nav_str = cols[1]
                                            try:
                                                nav = float(nav_str)
                                                tian_tian_prices.append(nav)
                                                tian_tian_dates.append(date_str)
                                                print(f"天天基金网API获取到净值数据: {date_str} - {nav}")
                                            except ValueError:
                                                print(f"解析净值数据失败: {nav_str}")
                                    
                                    # 反转数据，使其按时间正序排列
                                    tian_tian_prices.reverse()
                                    tian_tian_dates.reverse()
                                    
                                    # 添加到主数据列表
                                    prices.extend(tian_tian_prices)
                                    dates.extend(tian_tian_dates)
                                    
                                    if tian_tian_prices:
                                        print(f"天天基金网API成功提取 {len(tian_tian_prices)} 条净值数据")
                                    else:
                                        print("天天基金网API没有获取到净值数据")
                                else:
                                    print("天天基金网API没有找到净值表格")
                            else:
                                print("天天基金网API响应格式不正确：找不到content结束位置")
                        else:
                            print("天天基金网API响应格式不正确：找不到content起始位置")
                    except Exception as e:
                        print(f"解析天天基金网API响应失败: {e}")
                except Exception as e:
                    print(f"解析天天基金网API响应失败: {e}")
            else:
                print(f"天天基金网API响应状态错误: {response.status_code}")
        except Exception as e:
            print(f"天天基金网API失败: {e}")
            # 数据源2: 东方财富API
            try:
                print("尝试使用东方财富API获取历史净值数据...")
                # 东方财富API URL
                fund_data_url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
                print(f"东方财富API URL: {fund_data_url}")
                response = requests.get(fund_data_url, headers=headers, timeout=10)
                
                # 检查响应状态
                print(f"东方财富API响应状态: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        # 解析JS格式数据
                        data_str = response.text
                        # 提取净值数据
                        import re
                        net_value_match = re.search(r'var Data_netWorthTrend = \[(.*?)\];', data_str, re.DOTALL)
                        if net_value_match:
                            net_value_data = net_value_match.group(1)
                            # 转换为JSON格式
                            net_value_json = '[' + net_value_data + ']'
                            net_value_list = json.loads(net_value_json)
                            print(f"东方财富API获取到 {len(net_value_list)} 条净值数据")
                            
                            # 东方财富API返回的数据是按时间倒序排列的（最新的数据在前）
                            # 取最近365天的数据，确保有足够的历史数据供前端查询
                            recent_data = net_value_list[:365]  # 取前365条数据（最新的）
                            print(f"取最近 {len(recent_data)} 条数据")
                            
                            # 遍历数据，按时间正序添加
                            for item in reversed(recent_data):
                                try:
                                    nav = item['y']
                                    timestamp = item['x']
                                    # 添加调试信息，打印原始时间戳
                                    if len(prices) < 5:  # 只打印前5条数据的时间戳
                                        print(f"原始时间戳: {timestamp}, 转换后: {time.strftime('%Y-%m-%d', time.localtime(timestamp / 1000))}")
                                    date_str = time.strftime('%Y-%m-%d', time.localtime(timestamp / 1000))
                                    prices.append(nav)
                                    dates.append(date_str)
                                except (ValueError, KeyError) as e:
                                    print(f"解析东方财富净值数据失败: {e}")
                                    print(f"失败的数据项: {item}")
                            
                            if prices:
                                print(f"东方财富API成功提取 {len(prices)} 条净值数据")
                            else:
                                print("东方财富API没有获取到净值数据")
                        else:
                            print("东方财富API没有找到净值数据")
                    except Exception as e:
                        print(f"解析东方财富API响应失败: {e}")
                else:
                    print(f"东方财富API响应状态错误: {response.status_code}")
            except Exception as e:
                print(f"东方财富API失败: {e}")
                # 数据源3: 新浪财经API
                try:
                    print("尝试使用新浪财经API获取历史净值数据...")
                    # 新浪财经基金净值API
                    fund_data_url = f"http://fundgz.1234567.com.cn/js/{code}.js"
                    print(f"新浪财经API URL: {fund_data_url}")
                    response = requests.get(fund_data_url, headers=headers, timeout=10)
                    
                    print(f"新浪财经API响应状态: {response.status_code}")
                    
                    if response.status_code == 200:
                        try:
                            # 解析新浪财经的JS格式数据
                            data_str = response.text.strip().replace('jsonpgz(', '').replace(');', '')
                            data = json.loads(data_str)
                            print(f"新浪财经API响应数据: {data}")
                            
                            # 提取当前净值
                            if 'jzrq' in data and 'dwjz' in data:
                                date_str = data['jzrq']
                                nav = float(data['dwjz'])
                                prices.append(nav)
                                dates.append(date_str)
                                print(f"新浪财经API获取到净值数据: {date_str} - {nav}")
                            else:
                                print("新浪财经API没有净值数据")
                        except Exception as e:
                            print(f"解析新浪财经API响应失败: {e}")
                    else:
                        print(f"新浪财经API响应状态错误: {response.status_code}")
                except Exception as e:
                    print(f"新浪财经API失败: {e}")
        
        # 计算收益率数据
        if len(prices) > 1:
            returns = []
            for i in range(1, len(prices)):
                try:
                    daily_return = (prices[i] - prices[i-1]) / prices[i-1]
                    returns.append(daily_return)
                except (ZeroDivisionError, TypeError) as e:
                    print(f"计算收益率失败: {e}")
                    returns.append(0)
            # 填充第一个收益率为0
            returns.insert(0, 0)
        else:
            print("价格数据不足，无法计算收益率")
        
        # 添加调试信息，打印最近10条日期和净值数据
        print(f"基金 {code} 数据获取完成，名称: {name}, 价格数据量: {len(prices)}, 收益率数据量: {len(returns)}")
        
        # 打印最近10条数据（最新的）
        if len(prices) >= 10:
            print(f"最近10条数据（最新的）: {list(zip(dates[-10:], prices[-10:]))}")
        else:
            print(f"所有数据: {list(zip(dates, prices))}")
        
        # 检查是否包含2026-01-28的数据
        if '2026-01-28' in dates:
            index = dates.index('2026-01-28')
            print(f"找到2026-01-28的净值数据: {prices[index]}")
        else:
            print("未找到2026-01-28的净值数据")
            # 打印所有2026年的数据
            print("2026年的数据:")
            for i, date in enumerate(dates):
                if date.startswith('2026'):
                    print(f"日期: {date}, 净值: {prices[i]}")
            
        return name, prices, dates, returns
    except Exception as e:
        print(f"获取基金数据失败: {e}")
        # 如果API调用失败，返回空数据
        return f'基金{code}', [], [], []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/funds', methods=['GET'])
def get_funds():
    return jsonify([fund.to_dict() for fund in funds])

@app.route('/api/funds', methods=['POST'])
def add_fund():
    try:
        data = request.get_json()
        code = data['code']
        print(f"收到添加基金请求，基金代码: {code}")
        
        # 获取基金数据
        name, prices, dates, returns = get_fund_data(code)
        
        # 获取市场数据
        market_data = get_market_data()
        print(f"获取市场数据成功，指数: {len(market_data.get('indices', {}))}, 板块: {len(market_data.get('sectors', {}))}")
        
        # 获取基金持仓数据
        holdings = get_fund_holdings(code)
        print(f"获取基金持仓数据成功，股票数量: {len(holdings.get('stocks', []))}")
        
        # 检查数据是否有效
        if not prices:
            print(f"基金 {code} 没有获取到价格数据")
            # 仍然创建基金对象，但数据为空
        
        fund = Fund(name, code, prices, dates, returns)
        # 使用市场数据和持仓数据更新预测
        fund.predicted_return = fund.calculate_predicted_return(stock_holdings=holdings, market_data=market_data)
        fund.prediction_confidence = fund.calculate_prediction_confidence()
        funds.append(fund)
        print(f"基金 {code} 添加成功，ID: {fund.id}")
        return jsonify(fund.to_dict()), 201
    except Exception as e:
        print(f"添加基金失败: {e}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/funds/<int:fund_id>', methods=['DELETE'])
def delete_fund(fund_id):
    global funds
    funds = [fund for fund in funds if fund.id != fund_id]
    return jsonify({'message': 'Fund deleted'})

@app.route('/api/funds/<string:code>/details', methods=['GET'])
def get_fund_details(code):
    try:
        print(f"开始获取基金 {code} 详情...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        # 使用东方财富API获取基金详情
        fund_data_url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
        print(f"东方财富API URL: {fund_data_url}")
        response = requests.get(fund_data_url, headers=headers, timeout=10)
        
        print(f"东方财富API响应状态: {response.status_code}")
        
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
                        print("未提取到基金类型，使用默认值: 混合基金")
                if type_match:
                    fund_details['field'] = type_match.group(1)
                    print(f"提取到基金类型: {fund_details['field']}")
                else:
                    print("未提取到基金类型")
                
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
                            print(f"从规模变动数据中提取到成立时间: {fund_details['establishmentDate']}")
                if establish_match:
                    fund_details['establishmentDate'] = establish_match.group(1)
                    print(f"提取到成立时间: {fund_details['establishmentDate']}")
                else:
                    print("未提取到成立时间")
                
                # 清空composition和relatedStocks数组，因为我们不再使用这些数据
                fund_details['composition'] = []
                fund_details['relatedStocks'] = []
                
                print(f"基金 {code} 详情获取完成")
                print(f"获取到的详情数据: {fund_details}")
                return jsonify(fund_details)
            except Exception as e:
                print(f"解析东方财富API响应失败: {e}")
                # 打印部分响应内容，以便调试
                print(f"响应内容前500字符: {data_str[:500]}")
        else:
            print(f"东方财富API响应状态错误: {response.status_code}")
            # 打印响应内容，以便调试
            print(f"响应内容: {response.text}")
    except Exception as e:
        print(f"获取基金详情失败: {e}")
    
    # 如果API调用失败，返回空数据
    return jsonify({
        'establishmentDate': '',
        'field': '',
        'composition': [],
        'relatedStocks': []
    })

@app.route('/api/news', methods=['GET'])
def get_news():
    try:
        # 返回空数组，因为外部API调用可能被阻止
        # 在实际生产环境中，可以使用更稳定的新闻数据源
        return jsonify([])
    except Exception as e:
        print(f"获取新闻失败: {e}")
        # 如果API调用失败，返回空数组
        return jsonify([])

@app.route('/api/market-data', methods=['GET'])
def get_market_data_api():
    """获取市场数据，包括主要大盘指数和行业板块的实时数据"""
    try:
        market_data = get_market_data()
        return jsonify(market_data)
    except Exception as e:
        print(f"获取市场数据失败: {e}")
        return jsonify({'indices': {}, 'sectors': {}})

@app.route('/api/funds/<string:code>/nav', methods=['GET'])
def get_fund_nav(code):
    """获取基金在指定日期的净值"""
    try:
        # 验证基金代码格式
        if not re.match(r'^\d{6}$', code):
            return jsonify({'error': '无效的基金代码格式'}), 400
        
        # 获取日期参数
        date = request.args.get('date')
        if not date:
            return jsonify({'error': '缺少日期参数'}), 400
        
        # 验证日期格式
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
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
            return jsonify({'nav': nav})
        else:
            return jsonify({'nav': None, 'error': '未找到该日期的净值数据'})
    except Exception as e:
        print(f"获取基金净值失败: {e}")
        return jsonify({'nav': None, 'error': str(e)})

@app.route('/api/funds/<string:code>/holdings', methods=['GET'])
def get_fund_holdings_api(code):
    """获取基金的股票持仓数据"""
    try:
        # 验证基金代码格式
        if not re.match(r'^\d{6}$', code):
            return jsonify({'error': '无效的基金代码格式'}), 400
        
        # 获取基金持仓数据
        holdings = get_fund_holdings(code)
        if not holdings:
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
        
        # 尝试使用持仓数据更新基金的预测
        for fund in funds:
            if fund.code == code:
                fund.predicted_return = fund.calculate_predicted_return(stock_holdings=holdings_data, market_data=market_data)
                fund.prediction_confidence = fund.calculate_prediction_confidence()
                print(f"更新基金 {code} 的预测数据")
                break
        
        return jsonify(holdings_data)
    except Exception as e:
        print(f"获取基金持仓数据失败: {e}")
        return jsonify({'stocks': [], 'stock_ratio': 0, 'market_data': {'indices': {}, 'sectors': {}}})

if __name__ == '__main__':
    print('Starting Flask server...')
    print('Server will run on http://localhost:8888')
    app.run(debug=True, port=8888, host='0.0.0.0')