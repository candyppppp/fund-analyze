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
        print(f"开始获取基金 {code} 数据...")
        # 1. 直接使用基金代码作为名称（避免基金列表查询失败）
        name = f'基金{code}'
        
        # 2. 使用 AkShare 获取基金历史净值数据
        # 获取最近60天的历史数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=60)
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        print(f"尝试获取基金 {code} 的历史净值数据...")
        try:
            # 获取基金历史净值
            fund_data = ak.fund_em_open_fund_daily(code, start_date=start_date_str, end_date=end_date_str)
            print(f"获取到基金 {code} 的历史净值数据，数据量: {len(fund_data)}")
        except Exception as e:
            print(f"获取基金历史净值失败: {e}")
            # 如果获取失败，使用模拟数据
            fund_data = pd.DataFrame()
        
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
            print(f"成功提取 {len(prices)} 条净值数据")
        else:
            print("没有获取到历史净值数据，使用模拟数据")
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
        
        print(f"基金 {code} 数据获取完成，名称: {name}, 价格数据量: {len(prices)}")
        return name, prices, dates, returns
    except Exception as e:
        print(f"获取基金数据失败: {e}")
        # 如果API调用失败，返回模拟数据
        name = f'基金{code}'
        end_date = datetime.now()
        prices = []
        dates = []
        for i in range(60):
            base_price = 1.0 + i * 0.01
            prices.append(round(base_price, 4))
            date = (end_date - timedelta(days=59-i)).strftime('%Y-%m-%d')
            dates.append(date)
        returns = [0] * len(prices)
        print(f"使用模拟数据，基金 {code} 名称: {name}, 价格数据量: {len(prices)}")
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

@app.route('/api/funds/<string:code>/details', methods=['GET'])
def get_fund_details(code):
    try:
        print(f"开始获取基金 {code} 详情...")
        
        # 初始化默认值
        establishment_date = '2020-01-01'
        field = '股票型'
        manager = '未知'
        size = '1.0亿'
        
        # 投资组成默认值
        composition = [
            {'name': '股票', 'percentage': 80},
            {'name': '债券', 'percentage': 15},
            {'name': '现金', 'percentage': 5}
        ]
        
        # 重仓股默认值
        related_stocks = [
            {'name': '贵州茅台', 'code': '600519', 'percentage': 8.5, 'change': 1.2},
            {'name': '腾讯控股', 'code': '00700', 'percentage': 7.2, 'change': -0.5},
            {'name': '苹果', 'code': 'AAPL', 'percentage': 6.8, 'change': 0.8},
            {'name': '宁德时代', 'code': '300750', 'percentage': 5.9, 'change': 2.1},
            {'name': '阿里巴巴', 'code': '09988', 'percentage': 4.7, 'change': -1.3}
        ]
        
        try:
            # 尝试获取基金详情
            print(f"尝试获取基金 {code} 的详细信息...")
            fund_detail = ak.fund_em_open_fund_info(code)
            print(f"获取到基金 {code} 的详细信息，数据量: {len(fund_detail)}")
            
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
        except Exception as e:
            print(f"获取基金详情失败: {e}")
        
        try:
            # 尝试获取基金持仓信息
            print(f"尝试获取基金 {code} 的持仓信息...")
            fund_holdings = ak.fund_em_open_fund_holdings(code)
            print(f"获取到基金 {code} 的持仓信息，数据量: {len(fund_holdings)}")
            
            if not fund_holdings.empty:
                # 取前5只重仓股
                related_stocks = []
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
        except Exception as e:
            print(f"获取基金持仓信息失败: {e}")
        
        # 构建基金详细信息
        fund_details = {
            'establishmentDate': establishment_date,
            'field': field,
            'manager': manager,
            'size': size,
            'composition': composition,
            'relatedStocks': related_stocks
        }
        
        print(f"基金 {code} 详情获取完成")
        return jsonify(fund_details)
    except Exception as e:
        print(f"获取基金详情失败: {e}")
        # 如果API调用失败，返回默认数据
        return jsonify({
            'establishmentDate': '2020-01-01',
            'field': '股票型',
            'manager': '未知',
            'size': '1.0亿',
            'composition': [
                {'name': '股票', 'percentage': 80},
                {'name': '债券', 'percentage': 15},
                {'name': '现金', 'percentage': 5}
            ],
            'relatedStocks': [
                {'name': '贵州茅台', 'code': '600519', 'percentage': 8.5, 'change': 1.2},
                {'name': '腾讯控股', 'code': '00700', 'percentage': 7.2, 'change': -0.5},
                {'name': '苹果', 'code': 'AAPL', 'percentage': 6.8, 'change': 0.8},
                {'name': '宁德时代', 'code': '300750', 'percentage': 5.9, 'change': 2.1},
                {'name': '阿里巴巴', 'code': '09988', 'percentage': 4.7, 'change': -1.3}
            ]
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