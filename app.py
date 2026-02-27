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
        
        # 1. 使用新浪财经API获取基金基本信息
        fund_url = f"http://fundgz.1234567.com.cn/js/{code}.js"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        # 获取基金基本信息
        response = requests.get(fund_url, headers=headers, timeout=5)
        response.encoding = 'utf-8'
        
        # 解析新浪财经的JS格式数据
        data_str = response.text.strip().replace('jsonpgz(', '').replace(');', '')
        data = json.loads(data_str)
        
        # 提取基金名称
        name = data.get('name', f'基金{code}')
        print(f"获取到基金名称: {name}")
        
        # 2. 使用新浪财经API获取历史净值数据
        # 注意：新浪财经API可能不提供完整的历史数据
        # 这里我们使用天天基金网API获取历史数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=60)
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        fund_data_url = f"https://fundapi.eastmoney.com/f10/lsjz?fundCode={code}&pageIndex=1&pageSize=100&startDate={start_date_str}&endDate={end_date_str}"
        response = requests.get(fund_data_url, headers=headers, timeout=5)
        data = response.json()
        
        # 提取净值和日期数据
        prices = []
        dates = []
        
        if data.get('Data') and data['Data'].get('LSJZList'):
            for item in data['Data']['LSJZList']:
                # 从新到旧排序，所以需要反转
                prices.append(float(item['NAV']))
                dates.append(item['FSRQ'])
            # 反转数据，使时间从早到晚
            prices.reverse()
            dates.reverse()
            print(f"成功提取 {len(prices)} 条净值数据")
        else:
            print("没有获取到历史净值数据")
        
        # 3. 计算收益率数据
        returns = []
        for i in range(1, len(prices)):
            daily_return = (prices[i] - prices[i-1]) / prices[i-1]
            returns.append(round(daily_return * 100, 2))
        
        # 填充第一个收益率为0
        if prices:
            returns.insert(0, 0)
        
        print(f"基金 {code} 数据获取完成，名称: {name}, 价格数据量: {len(prices)}")
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
    data = request.get_json()
    code = data['code']
    
    # 获取基金数据
    name, prices, dates, returns = get_fund_data(code)
    
    fund = Fund(name, code, prices, dates, returns)
    funds.append(fund)
    return jsonify(fund.to_dict()), 201

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