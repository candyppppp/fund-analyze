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
import akshare as ak

app = Flask(__name__)
CORS(app)

funds = []

# 获取基金数据
def get_fund_data(code):
    try:
        # 1. 使用 AkShare 获取基金基本信息
        # 获取基金列表，查找基金名称
        fund_list = ak.fund_em_open_fund_name()
        fund_info = fund_list[fund_list['基金代码'] == code]
        
        if not fund_info.empty:
            name = fund_info.iloc[0]['基金名称']
        else:
            name = f'基金{code}'
        
        # 2. 使用 AkShare 获取基金历史净值数据
        # 获取最近60天的历史数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=60)
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        # 获取基金历史净值
        fund_data = ak.fund_em_open_fund_daily(code, start_date=start_date_str, end_date=end_date_str)
        
        # 提取净值和日期数据
        prices = []
        dates = []
        
        if not fund_data.empty:
            # 按日期排序，从早到晚
            fund_data = fund_data.sort_values('净值日期')
            
            # 提取数据
            for index, row in fund_data.iterrows():
                prices.append(float(row['单位净值']))
                dates.append(row['净值日期'].strftime('%Y-%m-%d'))
        
        # 3. 如果没有获取到数据，生成模拟数据
        if not prices:
            # 生成最近60天的模拟数据
            base_price = 1.0
            for i in range(60):
                # 随机生成价格变化
                change = random.uniform(-0.02, 0.02)
                base_price = base_price * (1 + change)
                prices.append(round(base_price, 4))
                # 生成日期
                date = (end_date - timedelta(days=59-i)).strftime('%Y-%m-%d')
                dates.append(date)
        
        # 4. 计算收益率数据
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
        # 使用 AkShare 获取基金详细信息
        # 1. 获取基金基本信息
        fund_list = ak.fund_em_open_fund_name()
        fund_info = fund_list[fund_list['基金代码'] == code]
        
        # 2. 获取基金详情
        fund_detail = ak.fund_em_open_fund_info(code)
        
        # 3. 获取基金持仓信息
        try:
            fund_holdings = ak.fund_em_open_fund_holdings(code)
        except:
            fund_holdings = pd.DataFrame()
        
        # 4. 构建基金详细信息
        establishment_date = ''
        field = ''
        manager = ''
        size = ''
        
        if not fund_detail.empty:
            # 提取基金基本信息
            for index, row in fund_detail.iterrows():
                if row['item'] == '成立日期':
                    establishment_date = row['value']
                elif row['item'] == '基金类型':
                    field = row['value']
                elif row['item'] == '基金经理':
                    manager = row['value']
                elif row['item'] == '基金规模':
                    size = row['value']
        
        # 5. 提取投资组成
        composition = []
        # 注意：AkShare 可能没有直接提供投资组成的API，这里使用默认值
        # 在实际生产环境中，可以通过其他方式获取投资组成
        composition = [
            {'name': '股票', 'percentage': 80},
            {'name': '债券', 'percentage': 15},
            {'name': '现金', 'percentage': 5}
        ]
        
        # 6. 提取重仓股
        related_stocks = []
        if not fund_holdings.empty:
            # 取前5只重仓股
            top_holdings = fund_holdings.head(5)
            for index, row in top_holdings.iterrows():
                stock_name = row.get('股票名称', '')
                stock_code = row.get('股票代码', '')
                percentage = float(row.get('占净值比例', '0').replace('%', ''))
                # 模拟涨跌数据
                change = round(random.uniform(-2, 2), 2)
                related_stocks.append({
                    'name': stock_name,
                    'code': stock_code,
                    'percentage': percentage,
                    'change': change
                })
        
        # 构建基金详细信息
        fund_details = {
            'establishmentDate': establishment_date,
            'field': field,
            'manager': manager,
            'size': size,
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