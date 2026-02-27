from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from models.fund import Fund
from utils.indicators import calculate_rsi, calculate_volatility
import random
import time
import requests
import json
import pandas as pd
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

funds = []

# 获取基金数据
def get_fund_data(code):
    try:
        # 1. 获取基金基本信息
        fund_info_url = f"https://fundapi.eastmoney.com/f10/lsjz?fundCode={code}&pageIndex=1&pageSize=1"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(fund_info_url, headers=headers)
        data = response.json()
        
        # 提取基金名称
        name = data.get('Data', {}).get('FundBaseInfo', {}).get('基金名称', f'基金{code}')
        
        # 2. 获取近3个月的净值数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        fund_data_url = f"https://fundapi.eastmoney.com/f10/lsjz?fundCode={code}&pageIndex=1&pageSize=100&startDate={start_date_str}&endDate={end_date_str}"
        response = requests.get(fund_data_url, headers=headers)
        data = response.json()
        
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
        
        # 3. 计算收益率数据
        returns = []
        for i in range(1, len(prices)):
            daily_return = (prices[i] - prices[i-1]) / prices[i-1]
            returns.append(round(daily_return * 100, 2))
        
        # 填充第一个收益率为0
        if prices:
            returns.insert(0, 0)
        
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
        # 使用天天基金网API获取基金详细信息
        fund_info_url = f"https://fundapi.eastmoney.com/f10/lsjz?fundCode={code}&pageIndex=1&pageSize=1"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(fund_info_url, headers=headers)
        data = response.json()
        
        # 提取基金基本信息
        fund_base_info = data.get('Data', {}).get('FundBaseInfo', {})
        
        # 尝试获取基金持仓信息
        holdings_url = f"https://fundapi.eastmoney.com/f10/ccmx?fundCode={code}"
        holdings_response = requests.get(holdings_url, headers=headers)
        holdings_data = holdings_response.json()
        
        # 提取投资组成
        composition = []
        holdings_info = holdings_data.get('Data', {}).get('CWZCTT', {})
        if holdings_info:
            if '股票占比' in holdings_info:
                composition.append({'name': '股票', 'percentage': float(holdings_info['股票占比'].replace('%', ''))})
            if '债券占比' in holdings_info:
                composition.append({'name': '债券', 'percentage': float(holdings_info['债券占比'].replace('%', ''))})
            if '现金占比' in holdings_info:
                composition.append({'name': '现金', 'percentage': float(holdings_info['现金占比'].replace('%', ''))})
        
        # 尝试获取基金重仓股
        related_stocks = []
        stock_holdings = holdings_data.get('Data', {}).get('ZCGDT', [])
        if stock_holdings:
            for stock in stock_holdings[:5]:  # 取前5只重仓股
                stock_name = stock.get('Gdmc', '')
                stock_code = stock.get('Gdcode', '')
                percentage = float(stock.get('Zczbl', '0').replace('%', ''))
                # 这里简化处理，实际应该从股票API获取涨跌
                change = round(random.uniform(-2, 2), 2)
                related_stocks.append({
                    'name': stock_name,
                    'code': stock_code,
                    'percentage': percentage,
                    'change': change
                })
        
        # 构建基金详细信息
        fund_details = {
            'establishmentDate': fund_base_info.get('成立日期', ''),
            'field': fund_base_info.get('基金类型', ''),
            'manager': fund_base_info.get('基金经理', ''),
            'size': fund_base_info.get('基金规模', ''),
            'composition': composition,
            'relatedStocks': related_stocks
        }
        
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
        # 使用东方财富网API获取实时财经新闻
        news_url = "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=10&np=1&fltt=2&invt=2&fields=f12,f14,f2,f3,f10,f13&secid=0.000001&ut=bd1d9ddb04089700cf9c27f6f7426281&wbp2u=|0|0|0|web"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(news_url, headers=headers)
        data = response.json()
        
        # 提取新闻数据
        news_list = []
        if data.get('data') and data['data'].get('diff'):
            for item in data['data']['diff'][:4]:  # 取前4条新闻
                # 模拟时间，实际应该从API获取
                hour = random.randint(9, 15)
                minute = random.randint(0, 59)
                time_str = f"{hour:02d}:{minute:02d}"
                
                news_list.append({
                    'time': time_str,
                    'content': item.get('f14', '').strip()
                })
        
        # 如果没有获取到新闻，返回空数组
        return jsonify(news_list)
    except Exception as e:
        print(f"获取新闻失败: {e}")
        # 如果API调用失败，返回空数组
        return jsonify([])

if __name__ == '__main__':
    print('Starting Flask server...')
    print('Server will run on http://localhost:8000')
    app.run(debug=True, port=8000, host='0.0.0.0')