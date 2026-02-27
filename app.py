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
            end_date = datetime.now()
            start_date = end_date - timedelta(days=60)
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
            
            fund_data_url = f"https://fundapi.eastmoney.com/f10/lsjz?fundCode={code}&pageIndex=1&pageSize=100&startDate={start_date_str}&endDate={end_date_str}"
            print(f"东方财富API URL: {fund_data_url}")
            response = requests.get(fund_data_url, headers=headers, timeout=5)
            
            # 检查响应状态
            print(f"东方财富API响应状态: {response.status_code}")
            print(f"东方财富API响应内容: {response.text[:500]}...")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"东方财富API响应数据结构: {list(data.keys())}")
                    
                    if data.get('Data'):
                        print(f"Data字段存在: {list(data['Data'].keys())}")
                        if data['Data'].get('LSJZList'):
                            print(f"LSJZList长度: {len(data['Data']['LSJZList'])}")
                            if len(data['Data']['LSJZList']) > 0:
                                print(f"第一条数据: {data['Data']['LSJZList'][0]}")
                                
                                for item in data['Data']['LSJZList']:
                                    # 从新到旧排序，所以需要反转
                                    try:
                                        nav = float(item['NAV'])
                                        prices.append(nav)
                                        dates.append(item['FSRQ'])
                                    except (ValueError, KeyError) as e:
                                        print(f"解析历史数据失败: {e}")
                                        print(f"失败的数据项: {item}")
                                # 反转数据，使时间从早到晚
                                prices.reverse()
                                dates.reverse()
                                print(f"东方财富API成功提取 {len(prices)} 条净值数据")
                            else:
                                print("东方财富API LSJZList为空")
                        else:
                            print("东方财富API没有LSJZList字段")
                    else:
                        print("东方财富API没有Data字段")
                except json.JSONDecodeError as e:
                    print(f"解析东方财富API响应失败: {e}")
            else:
                print(f"东方财富API响应状态错误: {response.status_code}")
        except Exception as e:
            print(f"东方财富API失败: {e}")
            # 数据源2: 新浪财经历史数据API
            try:
                print("尝试使用新浪财经历史数据API获取历史净值数据...")
                # 新浪财经历史净值API
                fund_data_url = f"http://fundf10.eastmoney.com/F10DataApi.aspx?type=lsjz&code={code}&page=1&per=100"
                print(f"新浪财经历史数据API URL: {fund_data_url}")
                response = requests.get(fund_data_url, headers=headers, timeout=5)
                
                print(f"新浪财经历史数据API响应状态: {response.status_code}")
                print(f"新浪财经历史数据API响应内容: {response.text[:500]}...")
                
                if response.status_code == 200:
                    # 解析HTML内容获取历史净值数据
                    import re
                    # 查找净值数据表格
                    table_match = re.search(r'<table[^>]*id="tbLfjs"[^>]*>([\s\S]*?)</table>', response.text)
                    if table_match:
                        table_content = table_match.group(1)
                        # 查找表格行
                        rows = re.findall(r'<tr[^>]*>([\s\S]*?)</tr>', table_content)
                        print(f"找到 {len(rows)} 行数据")
                        
                        for row in rows[1:]:  # 跳过表头
                            # 查找日期和净值
                            cells = re.findall(r'<td[^>]*>([\s\S]*?)</td>', row)
                            if len(cells) >= 2:
                                try:
                                    date_str = cells[0].strip()
                                    nav_str = cells[1].strip()
                                    nav = float(nav_str)
                                    prices.append(nav)
                                    dates.append(date_str)
                                except (ValueError, IndexError) as e:
                                    print(f"解析新浪财经历史数据失败: {e}")
                        
                        if prices:
                            # 反转数据，使时间从早到晚
                            prices.reverse()
                            dates.reverse()
                            print(f"新浪财经历史数据API成功提取 {len(prices)} 条净值数据")
                        else:
                            print("新浪财经历史数据API没有获取到数据")
                    else:
                        print("新浪财经历史数据API没有找到数据表格")
                else:
                    print(f"新浪财经历史数据API响应状态错误: {response.status_code}")
            except Exception as e:
                print(f"新浪财经历史数据API失败: {e}")
        
        # 计算收益率数据
        if len(prices) > 1:
            returns = []
            for i in range(1, len(prices)):
                try:
                    daily_return = (prices[i] - prices[i-1]) / prices[i-1]
                    returns.append(round(daily_return * 100, 2))
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
        # 尝试从真实API获取基金详情
        # 这里可以添加实际的API调用代码
        # 由于API可能不稳定，暂时返回空数据
        
        # 构建空的基金详细信息
        fund_details = {
            'establishmentDate': '',
            'field': '',
            'manager': '',
            'size': '',
            'composition': [],
            'relatedStocks': []
        }
        
        print(f"基金 {code} 详情获取完成")
        return jsonify(fund_details)
    except Exception as e:
        print(f"获取基金详情失败: {e}")
        # 如果API调用失败，返回空数据
        return jsonify({
            'establishmentDate': '',
            'field': '',
            'manager': '',
            'size': '',
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