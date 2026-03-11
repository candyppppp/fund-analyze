import logging
from utils.indicators import (
    calculate_rsi, calculate_volatility, calculate_macd, 
    calculate_kdj, calculate_bollinger_bands, calculate_atr,
    calculate_volume_analysis
)

logger = logging.getLogger(__name__)

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
        # 计算前一天收益率（基于最新净值）
        self.previous_day_return = 0
        if len(prices) >= 2:
            # 用最新净值除以倒数第二个净值，减去1，再乘以100%（转换为百分比）
            self.previous_day_return = ((prices[-1] / prices[-2]) - 1) * 100
        # 计算预测收益率
        self.predicted_return = self.calculate_predicted_return()
        # 计算预测置信度
        self.prediction_confidence = self.calculate_prediction_confidence()
    
    def calculate_predicted_return(self, stock_holdings=None, market_data=None, real_time_estimated_return=None):
        # 优先使用实时预估收益率数据
        if real_time_estimated_return and 'gszzl' in real_time_estimated_return:
            # 使用数据源提供的实时预估收益率
            real_time_return = real_time_estimated_return['gszzl']
            
            # 只进行轻微的市场环境调整，避免过度调整导致数据波动
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
                        # 大盘对基金的影响因子，使用较小的调整系数
                        market_adjustment = avg_index_change * 0.1
            
            # 综合调整后的预测
            final_prediction = real_time_return + market_adjustment
            
            # 限制预测范围，避免极端值
            final_prediction = max(min(final_prediction, 0.1), -0.1)
            
            return final_prediction
        
        # 如果没有实时预估数据，使用传统计算方法
        if len(self.prices) < 2:
            return 0
        
        # 基于最近价格趋势的预测
        recent_returns = []
        for i in range(1, min(5, len(self.prices))):
            return_rate = (self.prices[-i] - self.prices[-(i+1)]) / self.prices[-(i+1)]
            recent_returns.append(return_rate)
        
        avg_return = sum(recent_returns) / len(recent_returns)
        
        # 基于股票持仓的预测
        stock_based_return = 0
        if stock_holdings and stock_holdings.get('stocks'):
            total_weight = sum(stock['weight'] for stock in stock_holdings['stocks'])
            if total_weight > 0:
                # 将股票权重从百分比转换为小数形式
                weighted_sum = sum((stock['weight'] / 100) * stock.get('change_ratio', 0) for stock in stock_holdings['stocks'])
                stock_based_return = weighted_sum
        
        # 基于高级技术指标的调整
        technical_adjustment = 0
        
        # 重新计算技术指标，确保使用最新数据
        from utils.indicators import calculate_macd, calculate_kdj, calculate_bollinger_bands, calculate_atr
        
        # MACD指标
        macd_line, signal_line, histogram = calculate_macd(self.prices)
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
        k, d, j = calculate_kdj(self.prices)
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
        upper_band, ma, lower_band = calculate_bollinger_bands(self.prices)
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
        atr = calculate_atr(self.prices)
        if atr > 0.02:
            # 高波动率，可能加剧价格波动
            if avg_return > 0:
                technical_adjustment += 0.0008
            else:
                technical_adjustment -= 0.0008
        
        # 基于市场环境的调整
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
        
        # 基于趋势线的调整
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
        
        # 综合预测结果
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
            'previous_day_return': self.previous_day_return,
            'prices': self.prices,
            'dates': self.dates,
            'returns': self.returns,
            'volumes': self.volumes
        }
    
    def update_prices(self, new_prices, new_dates, new_returns, new_volumes=None, market_data=None):
        # 保存旧的价格数据，用于补充新数据
        old_prices = self.prices.copy()
        old_dates = self.dates.copy()
        old_returns = self.returns.copy()
        old_previous_day_return = self.previous_day_return
        
        # 确保新数据至少包含一些数据点
        if not new_prices:
            # 如果没有新数据，保持旧数据
            logger.warning(f"基金 {self.code} 没有获取到新的价格数据，使用旧数据")
            return
        
        # 合并新数据和旧数据，确保数据连续性
        if len(new_prices) < len(old_prices):
            # 如果新数据比旧数据少，使用旧数据补充
            # 保留新数据中的最新部分，并用旧数据补充历史部分
            combined_prices = old_prices[:-len(new_prices)] + new_prices
            combined_dates = old_dates[:-len(new_dates)] + new_dates
            combined_returns = old_returns[:-len(new_returns)] + new_returns
        else:
            # 使用新数据
            combined_prices = new_prices
            combined_dates = new_dates
            combined_returns = new_returns
        
        self.prices = combined_prices
        self.dates = combined_dates
        self.returns = combined_returns
        self.volumes = new_volumes or self.volumes
        
        # 更新技术指标，确保使用足够的数据点
        if len(combined_prices) >= 2:
            self.rsi = calculate_rsi(combined_prices)
            self.volatility = calculate_volatility(combined_prices)
            self.macd = calculate_macd(combined_prices)
            self.kdj = calculate_kdj(combined_prices)
            self.bollinger_bands = calculate_bollinger_bands(combined_prices)
            self.atr = calculate_atr(combined_prices)
        # 即使数据不足，也确保技术指标有默认值
        else:
            self.rsi = 50  # 默认RSI值
            self.volatility = 0.05  # 默认波动率
            self.macd = (0, 0, 0)  # 默认MACD值
            self.kdj = (50, 50, 50)  # 默认KDJ值
            self.bollinger_bands = (combined_prices[-1] * 1.1, combined_prices[-1], combined_prices[-1] * 0.9)  # 默认布林带
            self.atr = 0.01  # 默认ATR值
        
        self.volume_ratio = calculate_volume_analysis(self.volumes)
        
        # 计算前一天收益率（基于最新净值）
        self.previous_day_return = 0
        if len(combined_prices) >= 2:
            # 用最新净值除以倒数第二个净值，减去1，再乘以100%（转换为百分比）
            self.previous_day_return = ((combined_prices[-1] / combined_prices[-2]) - 1) * 100
        elif len(combined_prices) == 1 and len(old_prices) >= 1:
            # 如果新数据只有一个点，使用旧数据的最后一个点作为前一天的数据
            # 这样即使只有最新的净值，也能计算收益率
            self.previous_day_return = ((combined_prices[-1] / old_prices[-1]) - 1) * 100
        elif len(combined_prices) == 1 and len(old_prices) == 0:
            # 如果是新基金，没有历史数据，保持之前的收益率
            self.previous_day_return = old_previous_day_return
        
        # 更新预测
        self.predicted_return = self.calculate_predicted_return(market_data=market_data)
        self.prediction_confidence = self.calculate_prediction_confidence()