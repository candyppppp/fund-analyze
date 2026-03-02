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

/**
 * 计算MACD指标
 * @param {Array} prices - 价格数据数组
 * @param {number} fastPeriod - 快速周期，默认12
 * @param {number} slowPeriod - 慢速周期，默认26
 * @param {number} signalPeriod - 信号周期，默认9
 * @returns {Object} 包含MACD数据的对象
 */
export function calculateMACD(prices, fastPeriod = 12, slowPeriod = 26, signalPeriod = 9) {
    if (!prices || prices.length < 3) {
        return {
            macdLine: [],
            signalLine: [],
            histogram: []
        };
    }
    
    // 当数据点不足时，使用实际可用的数据点数量作为周期
    const actualFastPeriod = Math.min(fastPeriod, Math.floor(prices.length / 2));
    const actualSlowPeriod = Math.min(slowPeriod, prices.length - 1);
    const actualSignalPeriod = Math.min(signalPeriod, Math.floor(actualSlowPeriod / 2));
    
    // 计算EMA
    function ema(data, period) {
        const result = [];
        const multiplier = 2 / (period + 1);
        result.push(data[0]);
        for (let i = 1; i < data.length; i++) {
            const emaValue = data[i] * multiplier + result[i - 1] * (1 - multiplier);
            result.push(emaValue);
        }
        return result;
    }
    
    const fastEma = ema(prices, actualFastPeriod);
    const slowEma = ema(prices, actualSlowPeriod);
    const macdLine = [];
    
    for (let i = 0; i < prices.length; i++) {
        if (i < actualSlowPeriod - 1) {
            macdLine.push(null);
        } else {
            macdLine.push(parseFloat((fastEma[i] - slowEma[i]).toFixed(4)));
        }
    }
    
    // 计算信号线
    const signalLineData = macdLine.filter(val => val !== null);
    const signalLine = signalLineData.length >= actualSignalPeriod ? ema(signalLineData, actualSignalPeriod) : [];
    const paddedSignalLine = Array(actualSlowPeriod - 1).fill(null).concat(signalLine);
    
    // 计算柱状图
    const histogram = [];
    for (let i = 0; i < prices.length; i++) {
        if (i < actualSlowPeriod + actualSignalPeriod - 2 || !paddedSignalLine[i]) {
            histogram.push(null);
        } else {
            const histValue = macdLine[i] - paddedSignalLine[i];
            histogram.push(parseFloat(histValue.toFixed(4)));
        }
    }
    
    return {
        macdLine: macdLine,
        signalLine: paddedSignalLine,
        histogram: histogram
    };
}

/**
 * 计算KDJ指标
 * @param {Array} prices - 价格数据数组
 * @param {number} period - 周期，默认9
 * @returns {Object} 包含KDJ数据的对象
 */
export function calculateKDJ(prices, period = 9) {
    if (!prices || prices.length < 2) {
        return {
            k: [],
            d: [],
            j: []
        };
    }
    
    // 当数据点不足时，使用实际可用的数据点数量作为周期
    const actualPeriod = Math.min(period, prices.length);
    
    const k = [];
    const d = [];
    const j = [];
    
    for (let i = 0; i < prices.length; i++) {
        if (i < actualPeriod - 1) {
            k.push(null);
            d.push(null);
            j.push(null);
        } else {
            const slice = prices.slice(i - actualPeriod + 1, i + 1);
            const low = Math.min(...slice);
            const high = Math.max(...slice);
            const close = prices[i];
            // 避免除以零的情况
            const rsv = high === low ? 50 : (close - low) / (high - low) * 100;
            
            if (i === actualPeriod - 1) {
                k.push(50);
                d.push(50);
            } else {
                k.push(parseFloat(((2/3) * k[i - 1] + (1/3) * rsv).toFixed(2)));
                d.push(parseFloat(((2/3) * d[i - 1] + (1/3) * k[i]).toFixed(2)));
            }
            j.push(parseFloat((3 * k[i] - 2 * d[i]).toFixed(2)));
        }
    }
    
    return {
        k: k,
        d: d,
        j: j
    };
}

/**
 * 计算ATR指标
 * @param {Array} prices - 价格数据数组
 * @param {number} period - 周期，默认14
 * @returns {Array} ATR数据
 */
export function calculateATR(prices, period = 14) {
    if (!prices || prices.length < period) {
        return [];
    }
    
    const atr = [];
    
    for (let i = 0; i < prices.length; i++) {
        if (i < 1) {
            atr.push(null);
        } else {
            const tr = Math.max(
                prices[i] - prices[i - 1],
                Math.abs(prices[i] - prices[i - 1]),
                Math.abs(prices[i - 1] - prices[i - 1])
            );
            
            if (i < period) {
                atr.push(parseFloat(tr.toFixed(4)));
            } else {
                const prevAtr = atr[i - 1];
                const newAtr = (prevAtr * (period - 1) + tr) / period;
                atr.push(parseFloat(newAtr.toFixed(4)));
            }
        }
    }
    
    return atr;
}