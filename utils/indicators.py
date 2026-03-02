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

def calculate_macd(prices, fast_period=12, slow_period=26, signal_period=9):
    """计算MACD指标"""
    if len(prices) < slow_period:
        return 0, 0, 0
    
    # 计算EMA
    def ema(prices, period):
        ema_values = []
        multiplier = 2 / (period + 1)
        ema_values.append(prices[0])
        for i in range(1, len(prices)):
            ema_value = prices[i] * multiplier + ema_values[-1] * (1 - multiplier)
            ema_values.append(ema_value)
        return ema_values
    
    fast_ema = ema(prices, fast_period)
    slow_ema = ema(prices, slow_period)
    macd_line = [f - s for f, s in zip(fast_ema, slow_ema)]
    signal_line = ema(macd_line, signal_period)
    histogram = [m - s for m, s in zip(macd_line, signal_line)]
    
    return macd_line[-1], signal_line[-1], histogram[-1]

def calculate_kdj(prices, period=9):
    """计算KDJ指标"""
    if len(prices) < period:
        return 0, 0, 0
    
    # 计算RSV
    low_list = []
    high_list = []
    for i in range(len(prices) - period + 1):
        low_list.append(min(prices[i:i+period]))
        high_list.append(max(prices[i:i+period]))
    
    rsv = []
    for i in range(len(low_list)):
        if high_list[i] == low_list[i]:
            rsv.append(50)
        else:
            rsv.append((prices[i+period-1] - low_list[i]) / (high_list[i] - low_list[i]) * 100)
    
    # 计算K、D、J值
    k_values = []
    d_values = []
    j_values = []
    
    for i in range(len(rsv)):
        if i == 0:
            k = 50
            d = 50
        else:
            k = 2/3 * k_values[-1] + 1/3 * rsv[i]
            d = 2/3 * d_values[-1] + 1/3 * k
        j = 3 * k - 2 * d
        k_values.append(k)
        d_values.append(d)
        j_values.append(j)
    
    return k_values[-1], d_values[-1], j_values[-1]

def calculate_bollinger_bands(prices, period=20, num_std=2):
    """计算布林带"""
    if len(prices) < period:
        return 0, 0, 0
    
    ma = np.mean(prices[-period:])
    std = np.std(prices[-period:])
    upper_band = ma + num_std * std
    lower_band = ma - num_std * std
    
    return upper_band, ma, lower_band

def calculate_atr(prices, period=14):
    """计算平均真实波动范围(ATR)"""
    if len(prices) < period:
        return 0
    
    tr = []
    for i in range(1, len(prices)):
        high = prices[i]
        low = prices[i]
        prev_close = prices[i-1]
        tr_val = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr.append(tr_val)
    
    atr = np.mean(tr[-period:])
    return atr

def calculate_volume_analysis(volumes, period=20):
    """成交量分析"""
    if len(volumes) < period:
        return 0
    
    avg_volume = np.mean(volumes[-period:])
    current_volume = volumes[-1]
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
    
    return volume_ratio