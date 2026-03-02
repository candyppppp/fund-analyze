from utils.indicators import calculate_rsi, calculate_volatility

class Fund:
    id_counter = 1
    
    def __init__(self, name, code, prices, dates, returns):
        self.id = Fund.id_counter
        Fund.id_counter += 1
        self.name = name
        self.code = code
        self.prices = prices
        self.dates = dates
        self.returns = returns
        self.rsi = calculate_rsi(prices)
        self.volatility = calculate_volatility(prices)
        self.predicted_return = self.calculate_predicted_return()
    
    def calculate_predicted_return(self, stock_holdings=None):
        # 基于多种因素预测当天收益率
        if len(self.prices) < 2:
            return 0
        
        # 1. 基于最近价格趋势的预测
        recent_returns = []
        for i in range(1, min(5, len(self.prices))):
            return_rate = (self.prices[-i] - self.prices[-(i+1)]) / self.prices[-(i+1)]
            recent_returns.append(return_rate)
        
        avg_return = sum(recent_returns) / len(recent_returns)
        
        # 2. 基于股票持仓的预测
        stock_based_return = 0
        if stock_holdings and stock_holdings.get('stocks'):
            total_weight = sum(stock['weight'] for stock in stock_holdings['stocks'])
            if total_weight > 0:
                weighted_sum = sum(stock['weight'] * stock.get('change_ratio', 0) for stock in stock_holdings['stocks'])
                stock_based_return = weighted_sum / total_weight
        
        # 3. 基于技术指标的调整
        technical_adjustment = 0
        
        # 计算MA20
        if len(self.prices) >= 20:
            ma20 = sum(self.prices[-20:]) / 20
            current_price = self.prices[-1]
            # 价格在MA20之上，趋势向上
            if current_price > ma20:
                technical_adjustment += 0.001
            else:
                technical_adjustment -= 0.001
        
        # 计算压力位和支撑位
        if len(self.prices) >= 10:
            recent_prices = self.prices[-10:]
            resistance = max(recent_prices)
            support = min(recent_prices)
            current_price = self.prices[-1]
            
            # 接近压力位，可能回调
            if current_price > (resistance - (resistance - support) * 0.1):
                technical_adjustment -= 0.001
            # 接近支撑位，可能反弹
            elif current_price < (support + (resistance - support) * 0.1):
                technical_adjustment += 0.001
        
        # 4. 综合预测结果
        # 权重分配：价格趋势40%，股票持仓50%，技术指标10%
        final_prediction = avg_return * 0.4 + stock_based_return * 0.5 + technical_adjustment * 0.1
        
        # 限制预测范围，避免极端值
        final_prediction = max(min(final_prediction, 0.1), -0.1)
        
        return final_prediction
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'rsi': self.rsi,
            'volatility': self.volatility,
            'predicted_return': self.predicted_return,
            'prices': self.prices,
            'dates': self.dates,
            'returns': self.returns
        }
    
    def update_prices(self, new_prices, new_dates, new_returns):
        self.prices = new_prices
        self.dates = new_dates
        self.returns = new_returns
        self.rsi = calculate_rsi(new_prices)
        self.volatility = calculate_volatility(new_prices)
        self.predicted_return = self.calculate_predicted_return()