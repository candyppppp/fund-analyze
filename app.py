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
stock_cache_expiry = 30  # 股票数据缓存时间（秒）

# 基金持仓数据缓存
fund_holdings_cache = {}
fund_holdings_cache_expiry = 86400  # 基金持仓数据缓存时间（秒），1天

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

# 获取股票实时数据
def get_stock_real_time_data(stock_code):
    """获取股票的实时数据，包括当前价格、涨跌金额和涨跌比例"""
    # 检查缓存
    cache_key = f"stock_{stock_code}"
    current_time = time.time()
    
    if cache_key in stock_cache and current_time - stock_cache[cache_key]['timestamp'] < stock_cache_expiry:
        print(f"从缓存获取股票 {stock_code} 数据")
        return stock_cache[cache_key]['data']
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": "https://finance.sina.com.cn/"
        }
        
        # 使用新浪财经API获取股票实时数据
        # 对于沪市股票，需要添加sh前缀；深市股票添加sz前缀
        if stock_code.startswith('6'):
            full_code = f"sh{stock_code}"
        else:
            full_code = f"sz{stock_code}"
        
        stock_url = f"http://hq.sinajs.cn/list={full_code}"
        print(f"获取股票 {stock_code} 实时数据: {stock_url}")
        response = requests.get(stock_url, headers=headers, timeout=3)
        
        if response.status_code == 200:
            stock_data = response.text
            print(f"股票 {stock_code} 实时数据: {stock_data[:100]}...")
            # 解析股票数据
            stock_info = stock_data.split(',')
            if len(stock_info) > 3:
                # 计算涨跌幅
                try:
                    current_price = float(stock_info[3])
                    previous_close = float(stock_info[2])
                    if previous_close > 0:
                        change = (current_price - previous_close) / previous_close
                        change_amount = current_price - previous_close
                        # 存储到缓存
                        stock_cache[cache_key] = {
                            'timestamp': time.time(),
                            'data': {
                                'current_price': current_price,
                                'change_amount': change_amount,
                                'change_ratio': change
                            }
                        }
                        return {
                            'current_price': current_price,
                            'change_amount': change_amount,
                            'change_ratio': change
                        }
                except (ValueError, IndexError) as e:
                    print(f"解析股票 {stock_code} 实时数据失败: {e}")
            return {
                'current_price': 0,
                'change_amount': 0,
                'change_ratio': 0
            }
        else:
            print(f"股票 {stock_code} 实时数据API响应状态: {response.status_code}")
            return {
                'current_price': 0,
                'change_amount': 0,
                'change_ratio': 0
            }
    except Exception as e:
        print(f"获取股票 {stock_code} 实时数据失败: {e}")
        return {
            'current_price': 0,
            'change_amount': 0,
            'change_ratio': 0
        }

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
            print("尝试使用新浪财经API获取基金基本信息...")
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
        # 数据源1: 东方财富API
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
                        
                        # 只取最近60天的数据
                        recent_data = net_value_list[-60:]
                        print(f"取最近 {len(recent_data)} 条数据")
                        
                        for item in recent_data:
                            try:
                                nav = item['y']
                                date_str = time.strftime('%Y-%m-%d', time.localtime(item['x'] / 1000))
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
            # 数据源2: 新浪财经API
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
        
        print(f"基金 {code} 数据获取完成，名称: {name}, 价格数据量: {len(prices)}, 收益率数据量: {len(returns)}")
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
        
        # 检查数据是否有效
        if not prices:
            print(f"基金 {code} 没有获取到价格数据")
            # 仍然创建基金对象，但数据为空
        
        fund = Fund(name, code, prices, dates, returns)
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
            return jsonify({'stocks': [], 'stock_ratio': 0})
        
        # 获取股票实时数据
        stocks_with_data = []
        for stock in holdings.get('stocks', []):
            stock_data = get_stock_real_time_data(stock['code'])
            stock_info = {
                'code': stock['code'],
                'name': stock.get('name', f'股票{stock["code"]}'),
                'weight': stock['weight'],
                'current_price': stock_data.get('current_price', 0),
                'change_amount': stock_data.get('change_amount', 0),
                'change_ratio': stock_data.get('change_ratio', 0)
            }
            stocks_with_data.append(stock_info)
        
        # 按照权重排序
        stocks_with_data.sort(key=lambda x: x['weight'], reverse=True)
        
        return jsonify({
            'stocks': stocks_with_data,
            'stock_ratio': holdings.get('stock_ratio', 0)
        })
    except Exception as e:
        print(f"获取基金持仓数据失败: {e}")
        return jsonify({'stocks': [], 'stock_ratio': 0})

if __name__ == '__main__':
    print('Starting Flask server...')
    print('Server will run on http://localhost:8888')
    app.run(debug=True, port=8888, host='0.0.0.0')