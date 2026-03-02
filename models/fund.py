from utils.indicators import (
    calculate_rsi, calculate_volatility, calculate_macd, 
    calculate_kdj, calculate_bollinger_bands, calculate_atr,
    calculate_volume_analysis
)

class Fund:
    id_counter = 1
    
    def __init__(self, name, code, prices, dates, returns, volumes=None):
        self.id = Fund.id_counter
        Fund.id_counter += 1
        self.name = name
        self.code = code
        self.prices = prices
        self.dates = dates
        self.returns = returns
        self.volumes = volumes or []
        # 计算技术指标
        self.rsi = calculate_rsi(prices)
        self.volatility = calculate_volatility(prices)
        self.macd = calculate_macd(prices)
        self.kdj = calculate_kdj(prices)
        self.bollinger_bands = calculate_bollinger_bands(prices)
        self.atr = calculate_atr(prices)
        self.volume_ratio = calculate_volume_analysis(self.volumes)
        # 计算预测收益率
        self.predicted_return = self.calculate_predicted_return()
        # 计算预测置信度
        self.prediction_confidence = self.calculate_prediction_confidence()
    
    def calculate_predicted_return(self, stock_holdings=None, market_data=None):
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
        
        # 3. 基于高级技术指标的调整
        technical_adjustment = 0
        
        # MACD指标
        macd_line, signal_line, histogram = self.macd
        if macd_line > signal_line:
            if histogram > 0:
                # 金叉且柱状图为正，强烈看多
                technical_adjustment += 0.002
            else:
                # 金叉但柱状图为负，轻微看多
                technical_adjustment += 0.001
        else:
            if histogram < 0:
                # 死叉且柱状图为负，强烈看空
                technical_adjustment -= 0.002
            else:
                # 死叉但柱状图为正，轻微看空
                technical_adjustment -= 0.001
        
        # KDJ指标
        k, d, j = self.kdj
        if j > 80:
            # 超买，可能回调
            technical_adjustment -= 0.0015
        elif j < 20:
            # 超卖，可能反弹
            technical_adjustment += 0.0015
        elif j > 50:
            # 多头区域
            technical_adjustment += 0.0005
        else:
            # 空头区域
            technical_adjustment -= 0.0005
        
        # 布林带
        upper_band, ma, lower_band = self.bollinger_bands
        current_price = self.prices[-1]
        if current_price > upper_band:
            # 突破上轨，可能继续上涨
            technical_adjustment += 0.0012
        elif current_price < lower_band:
            # 突破下轨，可能继续下跌
            technical_adjustment -= 0.0012
        elif current_price > ma:
            # 价格在中轨之上，多头趋势
            technical_adjustment += 0.0005
        else:
            # 价格在中轨之下，空头趋势
            technical_adjustment -= 0.0005
        
        # RSI指标
        if self.rsi > 70:
            # 超买，可能回调
            technical_adjustment -= 0.0012
        elif self.rsi < 30:
            # 超卖，可能反弹
            technical_adjustment += 0.0012
        elif self.rsi > 50:
            # 多头区域
            technical_adjustment += 0.0003
        else:
            # 空头区域
            technical_adjustment -= 0.0003
        
        # ATR指标（波动率）
        if self.atr > 0.02:
            # 高波动率，可能加剧价格波动
            if avg_return > 0:
                technical_adjustment += 0.0008
            else:
                technical_adjustment -= 0.0008
        
        # 成交量分析
        if self.volume_ratio > 1.5:
            # 成交量放大，趋势可能加强
            if avg_return > 0:
                technical_adjustment += 0.0008
            else:
                technical_adjustment -= 0.0008
        elif self.volume_ratio < 0.5:
            # 成交量缩小，趋势可能反转
            if avg_return > 0:
                technical_adjustment -= 0.0005
            else:
                technical_adjustment += 0.0005
        
        # 4. 基于市场环境的调整
        market_adjustment = 0
        if market_data:
            # 大盘指数影响
            indices = market_data.get('indices', {})
            if indices:
                # 计算大盘平均涨跌幅
                index_changes = []
                for index_name, index_data in indices.items():
                    index_changes.append(index_data.get('change_ratio', 0))
                if index_changes:
                    avg_index_change = sum(index_changes) / len(index_changes)
                    # 大盘对基金的影响因子
                    market_adjustment += avg_index_change * 0.008
            
            # 行业板块影响（如果基金有行业倾向）
            sectors = market_data.get('sectors', {})
            if sectors:
                # 计算板块平均涨跌幅
                sector_changes = []
                for sector_name, sector_data in sectors.items():
                    sector_changes.append(sector_data.get('change_ratio', 0))
                if sector_changes:
                    avg_sector_change = sum(sector_changes) / len(sector_changes)
                    # 板块对基金的影响因子
                    market_adjustment += avg_sector_change * 0.005
        
        # 5. 基于趋势线的调整
        # 计算最近的趋势斜率
        if len(self.prices) >= 10:
            recent_prices = self.prices[-10:]
            x = list(range(len(recent_prices)))
            # 简单线性回归计算趋势斜率
            n = len(x)
            sum_x = sum(x)
            sum_y = sum(recent_prices)
            sum_xy = sum(x[i] * recent_prices[i] for i in range(n))
            sum_x2 = sum(x[i] ** 2 for i in range(n))
            
            if n * sum_x2 - sum_x ** 2 != 0:
                slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
                # 趋势斜率对预测的影响
                if slope > 0:
                    technical_adjustment += 0.0008
                else:
                    technical_adjustment -= 0.0008
        
        # 6. 综合预测结果
        # 权重分配：价格趋势20%，股票持仓50%，技术指标20%，市场环境10%
        final_prediction = avg_return * 0.2 + stock_based_return * 0.5 + technical_adjustment * 0.2 + market_adjustment * 0.1
        
        # 限制预测范围，避免极端值
        final_prediction = max(min(final_prediction, 0.1), -0.1)
        
        return final_prediction
    
    def calculate_prediction_confidence(self):
        """计算预测置信度"""
        confidence = 0.5  # 基础置信度
        
        # 基于数据质量的置信度调整
        if len(self.prices) >= 60:
            confidence += 0.2
        elif len(self.prices) >= 30:
            confidence += 0.1
        
        # 基于技术指标一致性的置信度调整
        indicators = []
        
        # MACD信号
        macd_line, signal_line, histogram = self.macd
        if macd_line > signal_line:
            indicators.append(1)
        else:
            indicators.append(-1)
        
        # KDJ信号
        k, d, j = self.kdj
        if j > 50:
            indicators.append(1)
        else:
            indicators.append(-1)
        
        # 布林带信号
        upper_band, ma, lower_band = self.bollinger_bands
        current_price = self.prices[-1]
        if current_price > ma:
            indicators.append(1)
        else:
            indicators.append(-1)
        
        # 计算指标一致性
        if len(indicators) > 1:
            positive_count = sum(1 for i in indicators if i > 0)
            negative_count = sum(1 for i in indicators if i < 0)
            if positive_count == len(indicators) or negative_count == len(indicators):
                confidence += 0.2
            elif positive_count >= len(indicators) * 0.6 or negative_count >= len(indicators) * 0.6:
                confidence += 0.1
        
        # 基于波动率的置信度调整
        if self.volatility < 0.1:
            confidence += 0.1
        elif self.volatility > 0.3:
            confidence -= 0.1
        
        # 限制置信度范围
        confidence = max(min(confidence, 0.95), 0.05)
        
        return confidence
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'rsi': self.rsi,
            'volatility': self.volatility,
            'macd': self.macd,
            'kdj': self.kdj,
            'bollinger_bands': self.bollinger_bands,
            'atr': self.atr,
            'volume_ratio': self.volume_ratio,
            'predicted_return': self.predicted_return,
            'prediction_confidence': self.prediction_confidence,
            'prices': self.prices,
            'dates': self.dates,
            'returns': self.returns,
            'volumes': self.volumes
        }
    
    def update_prices(self, new_prices, new_dates, new_returns, new_volumes=None, market_data=None):
        self.prices = new_prices
        self.dates = new_dates
        self.returns = new_returns
        self.volumes = new_volumes or self.volumes
        # 更新技术指标
        self.rsi = calculate_rsi(new_prices)
        self.volatility = calculate_volatility(new_prices)
        self.macd = calculate_macd(new_prices)
        self.kdj = calculate_kdj(new_prices)
        self.bollinger_bands = calculate_bollinger_bands(new_prices)
        self.atr = calculate_atr(new_prices)
        self.volume_ratio = calculate_volume_analysis(self.volumes)
        # 更新预测
        self.predicted_return = self.calculate_predicted_return(market_data=market_data)
        self.prediction_confidence = self.calculate_prediction_confidence()