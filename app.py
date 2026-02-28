from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from models.fund import Fund
from utils.indicators import calculate_rsi, calculate_volatility
import time
import requests
import json
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

funds = []

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
                
                # 提取持仓股票
                stock_codes_match = re.search(r'var stockCodesNew =\[(.*?)\];', data_str)
                if stock_codes_match:
                    stock_codes_str = stock_codes_match.group(1)
                    # 提取股票代码和名称
                    stock_codes = re.findall(r'"(.*?)"', stock_codes_str)
                    print(f"提取到 {len(stock_codes)} 只持仓股票")
                    
                    # 构建相关股票数据
                    for stock_code in stock_codes[:5]:  # 只取前5只股票
                        # 股票代码格式: 市场.代码 (1.600519)
                        stock_info = stock_code.split('.')
                        if len(stock_info) == 2:
                            market, code = stock_info
                            # 尝试从API响应中提取股票名称
                            # 注意：实际API响应中可能没有直接的股票名称映射
                            # 这里使用代码作为名称的一部分，使其更有意义
                            stock_name = f"股票 {code}"
                            # 暂时使用0作为占比和涨跌幅
                            # 实际应用中可以通过额外的API调用获取这些数据
                            fund_details['relatedStocks'].append({
                                'name': stock_name,
                                'code': code,
                                'percentage': 0,  # 暂时设为0，实际应该从API获取
                                'change': 0  # 暂时设为0，实际应该从API获取
                            })
                            print(f"添加股票: {stock_name} ({code})")
                else:
                    print("未提取到持仓股票")
                
                # 提取投资组成
                # 从API响应中提取真实的资产配置数据
                composition_match = re.search(r'var Data_assetAllocation = \{(.*?)\};', data_str, re.DOTALL)
                if composition_match:
                    composition_data = composition_match.group(1)
                    # 提取股票占比
                    stock_match = re.search(r'"股票占净比".*?"data":\[(.*?)\]', composition_data, re.DOTALL)
                    # 提取债券占比
                    bond_match = re.search(r'"债券占净比".*?"data":\[(.*?)\]', composition_data, re.DOTALL)
                    # 提取现金占比
                    cash_match = re.search(r'"现金占净比".*?"data":\[(.*?)\]', composition_data, re.DOTALL)
                    
                    if stock_match and bond_match and cash_match:
                        # 获取最新的占比数据（最后一个元素）
                        stock_data = stock_match.group(1).split(',')
                        bond_data = bond_match.group(1).split(',')
                        cash_data = cash_match.group(1).split(',')
                        
                        if stock_data and bond_data and cash_data:
                            stock_percentage = float(stock_data[-1].strip())
                            bond_percentage = float(bond_data[-1].strip())
                            cash_percentage = float(cash_data[-1].strip())
                            
                            fund_details['composition'] = [
                                {'name': '股票', 'percentage': stock_percentage},
                                {'name': '债券', 'percentage': bond_percentage},
                                {'name': '现金', 'percentage': cash_percentage}
                            ]
                            print(f"提取到投资组成数据: 股票 {stock_percentage}%, 债券 {bond_percentage}%, 现金 {cash_percentage}%")
                        else:
                            print("未提取到完整的投资组成数据")
                    else:
                        print("未提取到投资组成数据")
                else:
                    print("未提取到资产配置数据")
                    # 如果没有提取到数据，使用空数组
                    fund_details['composition'] = []
                
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

if __name__ == '__main__':
    print('Starting Flask server...')
    print('Server will run on http://localhost:8000')
    app.run(debug=True, port=8000, host='0.0.0.0')