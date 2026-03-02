import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error

class MLModel:
    def __init__(self):
        self.model = LinearRegression()
        self.is_trained = False
    
    def train(self, X, y):
        """训练机器学习模型"""
        if len(X) < 10:
            # 数据不足，不训练模型
            return False
        
        # 划分训练集和测试集
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # 训练模型
        self.model.fit(X_train, y_train)
        
        # 评估模型
        y_pred = self.model.predict(X_test)
        mse = mean_squared_error(y_test, y_pred)
        print(f"模型训练完成，均方误差: {mse}")
        
        self.is_trained = True
        return True
    
    def predict(self, X):
        """使用模型进行预测"""
        if not self.is_trained:
            return None
        
        return self.model.predict([X])[0]
    
    def feature_extraction(self, fund, market_data, stock_holdings):
        """提取特征用于模型训练和预测"""
        features = []
        
        # 价格趋势特征
        if len(fund.prices) >= 5:
            # 最近5天的收益率
            recent_returns = []
            for i in range(1, 5):
                if i < len(fund.prices):
                    return_rate = (fund.prices[-i] - fund.prices[-(i+1)]) / fund.prices[-(i+1)]
                    recent_returns.append(return_rate)
                else:
                    recent_returns.append(0)
            features.extend(recent_returns)
        else:
            features.extend([0, 0, 0, 0])
        
        # 技术指标特征
        features.append(fund.rsi)
        features.append(fund.volatility)
        
        # MACD指标
        macd_line, signal_line, histogram = fund.macd
        features.append(macd_line)
        features.append(signal_line)
        features.append(histogram)
        
        # KDJ指标
        k, d, j = fund.kdj
        features.append(k)
        features.append(d)
        features.append(j)
        
        # 布林带
        upper_band, ma, lower_band = fund.bollinger_bands
        features.append(upper_band)
        features.append(ma)
        features.append(lower_band)
        
        # ATR指标
        features.append(fund.atr)
        
        # 市场环境特征
        if market_data:
            # 大盘指数平均涨跌幅
            indices = market_data.get('indices', {})
            index_changes = []
            for index_name, index_data in indices.items():
                index_changes.append(index_data.get('change_ratio', 0))
            if index_changes:
                avg_index_change = sum(index_changes) / len(index_changes)
                features.append(avg_index_change)
            else:
                features.append(0)
            
            # 行业板块平均涨跌幅
            sectors = market_data.get('sectors', {})
            sector_changes = []
            for sector_name, sector_data in sectors.items():
                sector_changes.append(sector_data.get('change_ratio', 0))
            if sector_changes:
                avg_sector_change = sum(sector_changes) / len(sector_changes)
                features.append(avg_sector_change)
            else:
                features.append(0)
        else:
            features.extend([0, 0])
        
        # 股票持仓特征
        if stock_holdings and stock_holdings.get('stocks'):
            # 持仓股票平均涨跌幅
            stock_changes = []
            for stock in stock_holdings['stocks']:
                stock_changes.append(stock.get('change_ratio', 0))
            if stock_changes:
                avg_stock_change = sum(stock_changes) / len(stock_changes)
                features.append(avg_stock_change)
            else:
                features.append(0)
            
            # 股票持仓集中度
            weights = [stock.get('weight', 0) for stock in stock_holdings['stocks']]
            if weights:
                concentration = max(weights) / sum(weights) if sum(weights) > 0 else 0
                features.append(concentration)
            else:
                features.append(0)
        else:
            features.extend([0, 0])
        
        return features
    
    def calculate_prediction_confidence(self, features):
        """计算预测置信度"""
        if not self.is_trained:
            return 0.5
        
        # 基于特征的完整性和模型的历史表现计算置信度
        confidence = 0.5
        
        # 特征完整性得分
        non_zero_features = sum(1 for f in features if f != 0)
        feature_completeness = non_zero_features / len(features)
        confidence += feature_completeness * 0.3
        
        # 模型训练状态
        confidence += 0.2
        
        return min(confidence, 0.95)
