/**
 * 技术分析模块
 * 用于计算各种技术分析指标
 */

/**
 * 计算移动平均线
 * @param {Array} data - 价格数据数组
 * @param {number} period - 周期
 * @returns {Array} 移动平均线数据
 */
export function calculateMA(data, period) {
    const result = [];
    for (let i = 0; i < data.length; i++) {
        if (i < period - 1) {
            result.push(null);
        } else {
            let sum = 0;
            for (let j = 0; j < period; j++) {
                sum += data[i - j];
            }
            result.push(sum / period);
        }
    }
    return result;
}

/**
 * 计算支撑位和阻力位
 * 使用多种方法计算，取平均值作为最终结果
 * @param {Array} prices - 价格数据数组
 * @returns {Object} 包含支撑位和阻力位的对象
 */
export function calculateSupportResistance(prices) {
    if (!prices || prices.length < 10) {
        // 数据不足，使用简化方法
        const latestPrice = prices[prices.length - 1] || 0;
        return {
            support: latestPrice * 0.9,
            resistance: latestPrice * 1.1
        };
    }
    
    // 方法1：基于近期高点和低点
    const recentPrices = prices.slice(-30); // 最近30个数据点
    const highest = Math.max(...recentPrices);
    const lowest = Math.min(...recentPrices);
    const range = highest - lowest;
    
    // 方法2：基于移动平均线
    const ma20 = calculateMA(prices, 20);
    const ma50 = calculateMA(prices, 50);
    const latestMA20 = ma20[ma20.length - 1] || 0;
    const latestMA50 = ma50[ma50.length - 1] || 0;
    
    // 方法3：基于百分比
    const latestPrice = prices[prices.length - 1];
    
    // 计算支撑位
    const support1 = lowest + range * 0.236; // 黄金分割
    const support2 = latestMA20 * 0.98;
    const support3 = latestPrice * 0.95;
    const support = (support1 + support2 + support3) / 3;
    
    // 计算阻力位
    const resistance1 = highest - range * 0.236; // 黄金分割
    const resistance2 = latestMA20 * 1.02;
    const resistance3 = latestPrice * 1.05;
    const resistance = (resistance1 + resistance2 + resistance3) / 3;
    
    return {
        support: parseFloat(support.toFixed(4)),
        resistance: parseFloat(resistance.toFixed(4))
    };
}

/**
 * 计算趋势线
 * @param {Array} prices - 价格数据数组
 * @param {Array} dates - 日期数据数组
 * @returns {Object} 包含趋势线参数的对象
 */
export function calculateTrendLine(prices, dates) {
    if (!prices || prices.length < 2) {
        return {
            slope: 0,
            intercept: 0,
            points: []
        };
    }
    
    const n = prices.length;
    let sumX = 0;
    let sumY = 0;
    let sumXY = 0;
    let sumX2 = 0;
    
    // 使用索引作为x值
    for (let i = 0; i < n; i++) {
        sumX += i;
        sumY += prices[i];
        sumXY += i * prices[i];
        sumX2 += i * i;
    }
    
    // 计算斜率和截距
    const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
    const intercept = (sumY - slope * sumX) / n;
    
    // 生成趋势线上的点
    const points = [];
    for (let i = 0; i < n; i++) {
        points.push(slope * i + intercept);
    }
    
    return {
        slope: parseFloat(slope.toFixed(6)),
        intercept: parseFloat(intercept.toFixed(4)),
        points: points
    };
}

/**
 * 计算布林带
 * @param {Array} prices - 价格数据数组
 * @param {number} period - 周期，默认20
 * @param {number} stdDev - 标准差倍数，默认2
 * @returns {Object} 包含布林带数据的对象
 */
export function calculateBollingerBands(prices, period = 20, stdDev = 2) {
    if (!prices || prices.length < period) {
        return {
            middle: [],
            upper: [],
            lower: []
        };
    }
    
    const middle = calculateMA(prices, period);
    const upper = [];
    const lower = [];
    
    for (let i = 0; i < prices.length; i++) {
        if (i < period - 1) {
            upper.push(null);
            lower.push(null);
        } else {
            // 计算标准差
            let sum = 0;
            for (let j = 0; j < period; j++) {
                sum += Math.pow(prices[i - j] - middle[i], 2);
            }
            const std = Math.sqrt(sum / period);
            
            upper.push(parseFloat((middle[i] + stdDev * std).toFixed(4)));
            lower.push(parseFloat((middle[i] - stdDev * std).toFixed(4)));
        }
    }
    
    return {
        middle: middle,
        upper: upper,
        lower: lower
    };
}