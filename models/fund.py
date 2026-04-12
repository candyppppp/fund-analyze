import logging
from datetime import datetime, date
from utils.indicators import (
    calculate_rsi, calculate_volatility, calculate_macd,
    calculate_kdj, calculate_bollinger_bands, calculate_atr,
    calculate_volume_analysis
)

logger = logging.getLogger(__name__)


class Fund:
    id_counter = 1

    def __init__(self, name, code, prices, dates, returns, volumes=None, username=None):
        self.id = Fund.id_counter
        Fund.id_counter += 1
        self.name = name
        self.code = code
        self.prices = prices
        self.dates = dates
        self.returns = returns
        self.volumes = volumes or []
        self.username = username
        # 记录净值数据最后更新时间，用于判断是否需要增量拉取
        self.nav_updated_at = None  # 由外部加载时赋值
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
        """
        计算预测收益率。

        优先级：
          1. 实时估值 gszzl（基金公司官方，最准确）→ 直接使用，不加任何调整
          2. 无实时数据 → 用技术指标估算趋势方向，仅作参考
             注意：此时返回的是技术面趋势信号，不是真正的当日预测
        """
        # ── 优先：官方实时估值，直接返回原始值 ───────────────────────────────
        if real_time_estimated_return and real_time_estimated_return.get('gszzl') is not None:
            gszzl = real_time_estimated_return['gszzl']
            # 限制到合理范围（正常基金单日不超过±10%，ETF联接略宽）
            return max(min(float(gszzl), 0.15), -0.15)

        # ── 回退：无实时数据，用技术指标估算趋势方向 ─────────────────────────
        # 此结果仅反映技术面倾向，非当日真实预测，前端应区分显示
        if len(self.prices) < 5:
            return 0

        from utils.indicators import calculate_macd, calculate_kdj, calculate_bollinger_bands

        signal = 0.0  # 技术面综合信号，正=看多，负=看空

        # MACD：趋势动能
        macd_line, signal_line, histogram = calculate_macd(self.prices)
        if macd_line > signal_line:
            signal += 0.003 if histogram > 0 else 0.001  # 金叉强/弱
        else:
            signal -= 0.003 if histogram < 0 else 0.001  # 死叉强/弱

        # KDJ：超买超卖
        k, d, j = calculate_kdj(self.prices)
        if j > 80:
            signal -= 0.002  # 超买，可能回调
        elif j < 20:
            signal += 0.002  # 超卖，可能反弹
        elif k > d:
            signal += 0.0005  # 多头交叉
        else:
            signal -= 0.0005

        # 布林带：均值回归
        upper, ma, lower = calculate_bollinger_bands(self.prices)
        nav = self.prices[-1]
        if upper > lower:
            bb_pos = (nav - lower) / (upper - lower)
            if nav > upper:
                signal += 0.001  # 突破上轨，短期强势
            elif nav < lower:
                signal -= 0.001  # 跌破下轨，短期弱势
            elif bb_pos > 0.6:
                signal += 0.0003
            elif bb_pos < 0.4:
                signal -= 0.0003

        # RSI：动量
        if self.rsi > 70:
            signal -= 0.001
        elif self.rsi < 30:
            signal += 0.001
        elif self.rsi > 55:
            signal += 0.0003
        elif self.rsi < 45:
            signal -= 0.0003

        # 近5日价格趋势（动量延续）
        recent = [(self.prices[-i] - self.prices[-(i + 1)]) / self.prices[-(i + 1)]
                  for i in range(1, min(5, len(self.prices)))]
        if recent:
            momentum = sum(recent) / len(recent)
            signal += momentum * 0.15  # 动量贡献15%权重

        return max(min(signal, 0.1), -0.1)

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
            'volumes': self.volumes,
            'username': self.username,
            'nav_updated_at': self.nav_updated_at,
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