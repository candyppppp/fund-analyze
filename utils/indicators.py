import numpy as np

def calculate_rsi(prices, period=14):
    if len(prices) < period:
        return 0
    
    deltas = np.diff(prices)
    gains = deltas[deltas > 0]
    losses = -deltas[deltas < 0]
    
    if len(gains) == 0:
        return 0
    if len(losses) == 0:
        return 100
    
    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)
    
    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_volatility(prices, period=20):
    if len(prices) < period:
        return 0
    
    returns = np.diff(prices) / prices[:-1]
    volatility = np.std(returns) * np.sqrt(252)  # 年化波动率
    return volatility