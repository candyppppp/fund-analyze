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
    
    def calculate_predicted_return(self):
        # 基于最近价格趋势预测当天收益率
        if len(self.prices) < 2:
            return 0
        
        # 计算最近5天的平均涨幅
        recent_returns = []
        for i in range(1, min(5, len(self.prices))):
            return_rate = (self.prices[-i] - self.prices[-(i+1)]) / self.prices[-(i+1)]
            recent_returns.append(return_rate)
        
        avg_return = sum(recent_returns) / len(recent_returns)
        return avg_return
    
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