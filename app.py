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
        if data.get('Data') and data['Data'].get('LSJZList'):
            name = data['Data']['FundBaseInfo'].get('基金名称', f'基金{code}')
        else:
            # 如果API调用失败，使用模拟数据
            fund_names = {
                '000001': '华夏成长混合',
                '000002': '华夏债券A',
                '000003': '华夏现金增利',
                '000004': '华夏精选混合',
                '020274': '富国中证细分化工产业主题ETF联接C'
            }
            name = fund_names.get(code, f'基金{code}')
        
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
        else:
            # 如果API调用失败，生成模拟数据
            base_price = random.uniform(1.0, 3.0)
            prices = []
            dates = []
            for i in range(60):
                change = random.uniform(-0.02, 0.02)
                base_price = base_price * (1 + change)
                prices.append(round(base_price, 4))
                date = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
                dates.append(date)
        
        # 3. 计算收益率数据
        returns = []
        for i in range(1, len(prices)):
            daily_return = (prices[i] - prices[i-1]) / prices[i-1]
            returns.append(round(daily_return * 100, 2))
        
        # 填充第一个收益率为0
        returns.insert(0, 0)
        
        return name, prices, dates, returns
    except Exception as e:
        # 如果API调用失败，使用模拟数据
        fund_names = {
            '000001': '华夏成长混合',
            '000002': '华夏债券A',
            '000003': '华夏现金增利',
            '000004': '华夏精选混合',
            '020274': '富国中证细分化工产业主题ETF联接C'
        }
        name = fund_names.get(code, f'基金{code}')
        
        # 生成模拟数据
        base_price = random.uniform(1.0, 3.0)
        prices = []
        dates = []
        returns = []
        end_date = datetime.now()
        for i in range(60):
            change = random.uniform(-0.02, 0.02)
            base_price = base_price * (1 + change)
            prices.append(round(base_price, 4))
            date = (end_date - timedelta(days=60-i)).strftime('%Y-%m-%d')
            dates.append(date)
            if i > 0:
                daily_return = (prices[i] - prices[i-1]) / prices[i-1]
                returns.append(round(daily_return * 100, 2))
            else:
                returns.append(0)
        
        return name, prices, dates, returns

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

if __name__ == '__main__':
    app.run(debug=True, port=8000)