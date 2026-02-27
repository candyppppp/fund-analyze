from utils.indicators import calculate_rsi, calculate_volatility

class Fund:
    id_counter = 1
    
    def __init__(self, name, code, prices):
        self.id = Fund.id_counter
        Fund.id_counter += 1
        self.name = name
        self.code = code
        self.prices = prices
        self.rsi = calculate_rsi(prices)
        self.volatility = calculate_volatility(prices)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'rsi': self.rsi,
            'volatility': self.volatility,
            'prices': self.prices
        }
    
    def update_prices(self, new_prices):
        self.prices = new_prices
        self.rsi = calculate_rsi(new_prices)
        self.volatility = calculate_volatility(new_prices)