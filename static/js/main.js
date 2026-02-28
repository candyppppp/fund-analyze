document.addEventListener('DOMContentLoaded', function() {
    loadFunds();
    loadRealTimeNews();
    
    document.getElementById('add-fund-form').addEventListener('submit', function(e) {
        e.preventDefault();
        addFund();
    });
    
    // 清除缓存按钮
    document.querySelector('.header-buttons button:first-child').addEventListener('click', function() {
        localStorage.clear();
        alert('缓存已清除');
    });
    
    // 设置按钮
    document.querySelector('.header-buttons button:last-child').addEventListener('click', function() {
        showSettings();
    });
    
    // 实时快讯标签
    document.querySelector('.tab').addEventListener('click', function() {
        loadRealTimeNews();
    });
});

function loadRealTimeNews() {
    // 从后端API获取真实的实时快讯数据
    fetch('/api/news')
        .then(response => response.json())
        .then(news => {
            console.log('加载实时快讯:', news);
            // 这里可以添加显示快讯的逻辑
        })
        .catch(error => {
            console.error('获取实时快讯失败:', error);
            // 如果API调用失败，不显示任何数据
            console.log('获取实时快讯失败，不显示数据');
        });
}

function loadFunds() {
    // 从本地存储加载基金数据
    const savedFunds = localStorage.getItem('funds');
    if (savedFunds) {
        const funds = JSON.parse(savedFunds);
        renderFunds(funds);
    } else {
        // 如果本地存储没有数据，从API获取
        fetch('/api/funds')
            .then(response => response.json())
            .then(funds => {
                // 保存到本地存储
                localStorage.setItem('funds', JSON.stringify(funds));
                renderFunds(funds);
            });
    }
}

function renderFunds(funds) {
    const container = document.getElementById('funds-container');
    container.innerHTML = '';
    
    // 更新组计数
    document.getElementById('group-count').textContent = funds.length;
    
    if (funds.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #888; padding: 20px;">No funds in this group. Add one to track.</p>';
        return;
    }
    
    funds.forEach(fund => {
        const fundItem = document.createElement('div');
        fundItem.className = 'fund-item';
        fundItem.style.cursor = 'pointer';
        
        // 计算距高点
        const maxPrice = Math.max(...fund.prices);
        const currentPrice = fund.prices[fund.prices.length - 1];
        const distanceFromHigh = ((currentPrice - maxPrice) / maxPrice * 100).toFixed(2);
        
        // 生成唯一的图表ID
        const priceChartId = `price-chart-${fund.id}`;
        const returnChartId = `return-chart-${fund.id}`;
        
        // 获取买入设置
        const buySettings = getBuySettings(fund.id);
        // 计算预估今日收益
        let estimatedReturn = 0;
        if (buySettings.shares > 0) {
            estimatedReturn = fund.predicted_return * fund.prices[fund.prices.length - 1] * buySettings.shares;
        }
        
        // 获取RSI状态和emoji
        function getRSIStatus(rsi) {
            if (rsi > 70) {
                return { status: '过热', emoji: '🔥' };
            } else if (rsi < 30) {
                return { status: '过冷', emoji: '❄️' };
            } else if (rsi > 60 || rsi < 40) {
                return { status: '波动', emoji: '🌪️' };
            } else {
                return { status: '正常', emoji: '📊' };
            }
        }
        
        const rsiStatus = getRSIStatus(fund.rsi);
        
        fundItem.innerHTML = `
            <div class="fund-info">
                <div class="fund-name">${fund.name}</div>
                <div class="fund-details">
                    <div class="fund-detail">
                        <span class="fund-code">${fund.code}</span>
                        <span class="fund-type-tag">场外</span>
                    </div>
                    <div class="fund-detail-box">
                        <span>距高点 ${distanceFromHigh}%</span>
                    </div>
                    <div class="fund-detail-box">
                        <span>RSI ${fund.rsi.toFixed(1)}</span>
                        <span class="rsi-emoji">${rsiStatus.emoji}</span>
                    </div>
                </div>
            </div>
            <div class="fund-performance">
                <div class="fund-return-container">
                    <div class="fund-return ${fund.predicted_return < 0 ? 'negative' : ''}">
                        ${fund.predicted_return >= 0 ? '+' : ''}${(fund.predicted_return * 100).toFixed(2)}%
                    </div>
                    <div class="fund-return-label">Real-time Return</div>
                </div>
                ${buySettings.shares > 0 ? `
                    <div class="fund-return-container">
                        <div class="fund-return ${estimatedReturn >= 0 ? '' : 'negative'}">
                            ${estimatedReturn >= 0 ? '+' : ''}${estimatedReturn.toFixed(2)}元
                        </div>
                        <div class="fund-return-label">Live Profit/Loss</div>
                    </div>
                ` : ''}
                <div class="fund-actions">
                    <button class="real-time-btn">
                        <span>Real-time</span>
                        <span>🔄</span>
                    </button>
                    <button class="delete-btn" onclick="deleteFund(${fund.id})">删除</button>
                </div>
            </div>
        `;
        
        // 添加点击事件
        fundItem.addEventListener('click', function(e) {
            // 防止点击删除按钮时触发弹框
            if (!e.target.classList.contains('delete-btn') && !e.target.closest('.delete-btn')) {
                showFundDetails(fund);
            }
        });
        
        // 添加到容器
        container.appendChild(fundItem);
    });
}

function addFund() {
    const code = document.getElementById('fund-code').value;
    console.log('开始添加基金:', code);
    
    fetch('/api/funds', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ code })
    })
    .then(response => {
        console.log('添加基金API响应状态:', response.status);
        return response.json();
    })
    .then(data => {
        console.log('添加基金API返回数据:', data);
        // 重新从API获取所有基金数据并保存到本地存储
        fetch('/api/funds')
            .then(response => {
                console.log('获取基金列表API响应状态:', response.status);
                return response.json();
            })
            .then(funds => {
                console.log('获取到的基金列表:', funds);
                localStorage.setItem('funds', JSON.stringify(funds));
                renderFunds(funds);
                document.getElementById('add-fund-form').reset();
            })
            .catch(error => {
                console.error('获取基金列表失败:', error);
            });
    })
    .catch(error => {
        console.error('添加基金失败:', error);
    });
}

function deleteFund(id) {
    fetch(`/api/funds/${id}`, {
        method: 'DELETE'
    })
    .then(() => {
        // 重新从API获取所有基金数据并保存到本地存储
        fetch('/api/funds')
            .then(response => response.json())
            .then(funds => {
                localStorage.setItem('funds', JSON.stringify(funds));
                renderFunds(funds);
            });
    });
}

function showFundDetails(fund) {
    // 获取买入设置
    const buySettings = getBuySettings(fund.id);
    
    // 创建弹框
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0, 0, 0, 0.8);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 1000;
    `;
    
    // 弹框内容
    const modalContent = document.createElement('div');
    modalContent.className = 'modal-content';
    modalContent.style.cssText = `
        background-color: #121212;
        border-radius: 6px;
        width: 90%;
        max-width: 900px;
        max-height: 90vh;
        overflow: hidden;
        box-shadow: 0 5px 20px rgba(0, 0, 0, 0.6);
        border: 1px solid #333;
        display: flex;
        flex-direction: column;
    `;
    
    // 生成唯一的图表ID
    const chartId = `detail-chart-${fund.id}`;
    
    // 弹框HTML
    modalContent.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 15px 20px; border-bottom: 1px solid #333;">
            <div style="display: flex; flex-direction: column;">
                <h2 style="color: white; margin: 0; font-size: 16px;">${fund.name}</h2>
                <div style="font-size: 12px; color: #aaa; margin-top: 2px;">${fund.code} NAV: ${fund.prices[fund.prices.length - 1]}</div>
            </div>
            <div style="display: flex; align-items: center; gap: 10px;">
                <div style="display: flex; background-color: #1e1e1e; border-radius: 4px; overflow: hidden;">
                    <button class="tab-btn active" data-tab="details" style="padding: 6px 12px; border: none; background: transparent; color: #007bff; cursor: pointer; font-size: 12px; font-weight: bold;">详情</button>
                    <button class="tab-btn" data-tab="decision" style="padding: 6px 12px; border: none; background: transparent; color: #e0e0e0; cursor: pointer; font-size: 12px;">决策</button>
                    <button class="tab-btn" data-tab="holding" style="padding: 6px 12px; border: none; background: transparent; color: #e0e0e0; cursor: pointer; font-size: 12px;">持仓</button>
                </div>
            </div>
        </div>
        
        <!-- 标签内容 -->
        <div style="flex: 1; overflow-y: auto; padding: 0;">
            <!-- 详情标签 -->
            <div id="details-tab" class="tab-content" style="display: block;">
                <!-- 时间范围 -->
                <div style="display: flex; justify-content: flex-end; gap: 2px; padding: 10px 20px; background-color: #1e1e1e; border-bottom: 1px solid #333;">
                    <button class="time-btn" data-days="7">7D</button>
                    <button class="time-btn" data-days="30">1M</button>
                    <button class="time-btn active" data-days="90">3M</button>
                    <button class="time-btn" data-days="180">6M</button>
                    <button class="time-btn" data-days="365">1Y</button>
                    <button class="time-btn" data-days="0">ALL</button>
                </div>
                
                <!-- 趋势图 -->
                <div style="height: 350px; background-color: #1e1e1e; border-bottom: 1px solid #333;">
                    <canvas id="${chartId}"></canvas>
                </div>
            </div>
            
            <!-- 决策标签 -->
            <div id="decision-tab" class="tab-content" style="display: none;">
                <!-- 趋势信号和智能操作建议 -->
                <div style="background-color: #1e1e1e; padding: 20px 20px; border-bottom: 1px solid #333;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 15px;">
                        <div style="flex: 1;">
                            <div style="font-size: 14px; color: #e0e0e0; margin-bottom: 10px;"><strong>趋势信号</strong></div>
                            ${(() => {
                                // 计算趋势信号
                                let trendSignal = '';
                                let trendColor = '';
                                let trendDesc = '';
                                let priceChange = 0;
                                let trendIcon = '●';
                                
                                if (fund.prices && fund.prices.length >= 2) {
                                    const recentPrice = fund.prices[fund.prices.length - 1];
                                    const previousPrice = fund.prices[fund.prices.length - 2];
                                    priceChange = recentPrice - previousPrice;
                                    
                                    if (priceChange > 0) {
                                        trendSignal = '多头排列 (金叉向上)';
                                        trendColor = '#4caf50';
                                        trendDesc = '短期均线位于长期均线上方，价格呈上升趋势，市场情绪积极。';
                                        trendIcon = '✓';
                                    } else if (priceChange < 0) {
                                        trendSignal = '空头排列 (死叉向下)';
                                        trendColor = '#ff4444';
                                        trendDesc = '短期均线位于长期均线下方，价格呈下降趋势，市场情绪消极。';
                                        trendIcon = '✗';
                                    } else {
                                        trendSignal = '震荡整理';
                                        trendColor = '#ff9800';
                                        trendDesc = '价格在一定范围内波动，市场情绪中性。';
                                        trendIcon = '●';
                                    }
                                } else {
                                    trendSignal = '数据不足';
                                    trendColor = '#aaa';
                                    trendDesc = '价格数据不足，无法判断趋势。';
                                    trendIcon = '●';
                                }
                                
                                return `
                                    <div style="font-size: 12px; color: ${trendColor}; display: flex; align-items: center; margin-bottom: 8px;">
                                        <span style="margin-right: 8px;">${trendIcon}</span> ${trendSignal}
                                    </div>
                                    <div style="font-size: 11px; color: #aaa; line-height: 1.4;">
                                        ${trendDesc}
                                    </div>
                                `;
                            })()}
                        </div>
                        <div style="flex: 1; text-align: center;">
                            <div style="font-size: 14px; color: #e0e0e0; margin-bottom: 10px;"><strong>支撑位 (Low 60d)</strong></div>
                            <div style="font-size: 12px; color: #e0e0e0; margin-bottom: 8px;">
                                ${fund.prices && fund.prices.length > 0 ? (Math.min(...fund.prices)).toFixed(4) : '数据不足'}
                            </div>
                            <div style="font-size: 11px; color: #4caf50;">
                                ${fund.prices && fund.prices.length > 0 ? `支撑率 +${((fund.prices[fund.prices.length - 1] / Math.min(...fund.prices) - 1) * 100).toFixed(1)}%` : '-'}
                            </div>
                        </div>
                        <div style="flex: 1; text-align: right;">
                            <div style="font-size: 14px; color: #e0e0e0; margin-bottom: 10px;"><strong>智能操作建议</strong></div>
                            ${(() => {
                                // 基于RSI和预测收益率生成操作建议
                                let advice = '';
                                let adviceColor = '';
                                let adviceDesc = '';
                                
                                if (fund.rsi > 70) {
                                    advice = 'RSI过热, 建议止盈';
                                    adviceColor = '#ff4444';
                                    adviceDesc = 'RSI指标过高，当前基金处于超买状态，建议及时止盈。';
                                } else if (fund.rsi < 30) {
                                    advice = 'RSI超卖, 建议买入';
                                    adviceColor = '#4caf50';
                                    adviceDesc = 'RSI指标过低，当前基金处于超卖状态，可能存在反弹机会。';
                                } else if (fund.predicted_return > 0.01) {
                                    advice = '看涨信号, 建议持有';
                                    adviceColor = '#4caf50';
                                    adviceDesc = '预测收益率为正，短期可能有上涨空间。';
                                } else if (fund.predicted_return < -0.01) {
                                    advice = '看跌信号, 建议减仓';
                                    adviceColor = '#ff4444';
                                    adviceDesc = '预测收益率为负，短期可能面临调整。';
                                } else {
                                    advice = '震荡行情, 建议观望';
                                    adviceColor = '#ff9800';
                                    adviceDesc = '市场处于震荡状态，建议保持观望。';
                                }
                                
                                return `
                                    <div style="font-size: 12px; color: ${adviceColor}; display: flex; align-items: center; justify-content: flex-end; margin-bottom: 8px;">
                                        <span style="margin-right: 8px;">●</span> ${advice}
                                    </div>
                                    <div style="font-size: 11px; color: #aaa; line-height: 1.3; text-align: right;">
                                        ${adviceDesc}
                                    </div>
                                `;
                            })()}
                        </div>
                    </div>
                </div>
                
                <!-- 基金风险评估 -->
                <div style="background-color: #1e1e1e; padding: 20px 20px; border-bottom: 1px solid #333;">
                    <h3 style="color: #e0e0e0; margin-bottom: 15px; font-size: 14px;">基金风险评估</h3>
                    <div style="background-color: #2a2a2a; border-radius: 4px; padding: 18px; border: 1px solid #333;">
                        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 10px;">
                            <div style="font-size: 12px;"><strong>当前净值:</strong> <span style="color: #e0e0e0;">${fund.prices && fund.prices.length > 0 ? fund.prices[fund.prices.length - 1] : '数据不足'}</span></div>
                            <div style="font-size: 12px;"><strong>RSI指标:</strong> <span style="color: #e0e0e0;">${fund.rsi ? fund.rsi.toFixed(2) + ' ' + getRSIMessage(fund.rsi) : '数据不足'}</span></div>
                            <div style="font-size: 12px;"><strong>波动率:</strong> <span style="color: #e0e0e0;">${fund.volatility ? (fund.volatility * 100).toFixed(2) + '%' : '数据不足'}</span></div>
                            <div style="font-size: 12px;"><strong>预测当日收益率:</strong> <span class="return-value ${fund.predicted_return >= 0 ? 'positive' : 'negative'}">${fund.predicted_return ? (fund.predicted_return >= 0 ? '+' : '') + (fund.predicted_return * 100).toFixed(2) + '%' : '数据不足'}</span></div>
                        </div>
                        <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #333;">
                            <h4 style="color: #e0e0e0; margin-bottom: 10px; font-size: 13px;">风险评估</h4>
                            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; font-size: 12px;">
                                <div><strong>RSI风险:</strong> <span style="color: ${fund.rsi ? (fund.rsi > 70 ? '#ff4444' : fund.rsi < 30 ? '#4caf50' : '#ff9800') : '#aaa'}">${fund.rsi ? (fund.rsi > 70 ? '高' : fund.rsi < 30 ? '低' : '中') : '数据不足'}</span></div>
                                <div><strong>波动率风险:</strong> <span style="color: ${fund.volatility ? (fund.volatility > 0.2 ? '#ff4444' : fund.volatility > 0.1 ? '#ff9800' : '#4caf50') : '#aaa'}">${fund.volatility ? (fund.volatility > 0.2 ? '高' : fund.volatility > 0.1 ? '中' : '低') : '数据不足'}</span></div>
                                ${(() => {
                                    // 计算趋势风险
                                    let trendRisk = '数据不足';
                                    let trendRiskColor = '#aaa';
                                    
                                    if (fund.prices && fund.prices.length >= 5) {
                                        const recentPrices = fund.prices.slice(-5);
                                        const priceChange = recentPrices[4] - recentPrices[0];
                                        const priceChangePercent = priceChange / recentPrices[0] * 100;
                                        
                                        if (Math.abs(priceChangePercent) > 5) {
                                            trendRisk = '高';
                                            trendRiskColor = '#ff4444';
                                        } else if (Math.abs(priceChangePercent) > 2) {
                                            trendRisk = '中';
                                            trendRiskColor = '#ff9800';
                                        } else {
                                            trendRisk = '低';
                                            trendRiskColor = '#4caf50';
                                        }
                                    }
                                    
                                    return `<div><strong>趋势风险:</strong> <span style="color: ${trendRiskColor};">${trendRisk}</span></div>`;
                                })()}
                                <div><strong>流动性风险:</strong> <span style="color: #ff9800;">中</span></div>
                                <div><strong>市场风险:</strong> <span style="color: ${fund.volatility && fund.volatility > 0.15 ? '#ff9800' : '#4caf50'}">${fund.volatility && fund.volatility > 0.15 ? '中' : '低'}</span></div>
                                ${(() => {
                                    // 计算整体风险
                                    let overallRisk = '数据不足';
                                    let overallRiskColor = '#aaa';
                                    
                                    if (fund.rsi && fund.volatility) {
                                        let riskScore = 0;
                                        
                                        // RSI风险评分
                                        if (fund.rsi > 70) riskScore += 3;
                                        else if (fund.rsi < 30) riskScore += 1;
                                        else riskScore += 2;
                                        
                                        // 波动率风险评分
                                        if (fund.volatility > 0.2) riskScore += 3;
                                        else if (fund.volatility > 0.1) riskScore += 2;
                                        else riskScore += 1;
                                        
                                        // 综合判断
                                        if (riskScore >= 5) {
                                            overallRisk = '高';
                                            overallRiskColor = '#ff4444';
                                        } else if (riskScore >= 3) {
                                            overallRisk = '中';
                                            overallRiskColor = '#ff9800';
                                        } else {
                                            overallRisk = '低';
                                            overallRiskColor = '#4caf50';
                                        }
                                    }
                                    
                                    return `<div><strong>整体风险:</strong> <span style="color: ${overallRiskColor};">${overallRisk}</span></div>`;
                                })()}
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- 智能决策 -->
                <div style="background-color: #1e1e1e; padding: 20px 20px;">
                    <h3 style="color: #e0e0e0; margin-bottom: 15px; font-size: 14px;">智能决策</h3>
                    <div style="background-color: #2a2a2a; border-radius: 4px; padding: 18px; border: 1px solid #333;">
                        <div style="font-size: 12px; line-height: 1.5; color: #e0e0e0;">
                            ${(() => {
                                // 基于多种指标生成智能决策
                                let decisionText = '';
                                
                                if (!fund.rsi || !fund.volatility || !fund.predicted_return) {
                                    return '<p>数据不足，无法提供智能决策建议。</p>';
                                }
                                
                                if (fund.rsi > 70) {
                                    decisionText = '<p>RSI指标过高，当前基金处于超买状态，建议及时止盈，避免追高风险。</p>';
                                    decisionText += '<p style="margin-top: 10px;">可考虑将部分资金转移至低风险资产，等待回调后再重新入场。</p>';
                                } else if (fund.rsi < 30) {
                                    decisionText = '<p>RSI指标过低，当前基金处于超卖状态，可能存在反弹机会，建议适当买入。</p>';
                                    decisionText += '<p style="margin-top: 10px;">可采取分批建仓策略，降低入场风险。</p>';
                                } else if (fund.predicted_return > 0.01 && fund.volatility < 0.15) {
                                    decisionText = '<p>预测收益率为正，波动率较低，建议继续持有。</p>';
                                    decisionText += '<p style="margin-top: 10px;">可考虑适当加仓，扩大收益。</p>';
                                } else if (fund.predicted_return < -0.01) {
                                    decisionText = '<p>预测收益率为负，短期可能面临调整，建议适当减仓。</p>';
                                    decisionText += '<p style="margin-top: 10px;">可将部分资金暂时转出，等待市场企稳后再重新布局。</p>';
                                } else {
                                    decisionText = '<p>市场处于震荡状态，建议保持观望，等待明确信号。</p>';
                                    decisionText += '<p style="margin-top: 10px;">可维持当前仓位，密切关注市场变化。</p>';
                                }
                                
                                return decisionText;
                            })()}
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- 持仓标签 -->
            <div id="holding-tab" class="tab-content" style="display: none;">
                <!-- 我的持仓 -->
                <div style="background-color: #1e1e1e; padding: 15px 20px; border-bottom: 1px solid #333;">
                    <h3 style="color: #e0e0e0; margin-bottom: 10px; font-size: 14px;">我的持仓 (持仓: <span id="total-shares">${buySettings.shares}</span>份，平均净值: <span id="avg-nav">0.0000</span>元)</h3>
                    <div style="background-color: #2a2a2a; border-radius: 4px; padding: 14px; border: 1px solid #333;">
                        <div id="buy-records-content" style="font-size: 12px;">
                            加载中...
                        </div>
                    </div>
                </div>
                
                <!-- 买入设置 -->
                <div style="background-color: #1e1e1e; padding: 15px 20px;">
                    <h3 style="color: #e0e0e0; margin-bottom: 10px; font-size: 14px;">买入设置</h3>
                    <div style="background-color: #2a2a2a; border-radius: 4px; padding: 14px; border: 1px solid #333;">
                        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; font-size: 12px;">
                            <div>
                                <label style="display: block; margin-bottom: 5px;">买入日期:</label>
                                <input type="date" id="buy-date" value="${new Date().toISOString().split('T')[0]}" style="background-color: #333; color: #e0e0e0; border: 1px solid #444; padding: 5px; border-radius: 4px; font-size: 12px;">
                            </div>
                            <div>
                                <label style="display: block; margin-bottom: 5px;">买入份数:</label>
                                <input type="number" id="buy-shares" value="0" style="background-color: #333; color: #e0e0e0; border: 1px solid #444; padding: 5px; border-radius: 4px; font-size: 12px;">
                            </div>
                        </div>
                        <button id="save-buy-settings" style="margin-top: 10px; background-color: #007bff; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px;">保存设置</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // 添加到页面
    modal.appendChild(modalContent);
    document.body.appendChild(modal);
    
    // 点击空白区域关闭弹窗
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            document.body.removeChild(modal);
        }
    });
    
    // 阻止内容区域的点击事件冒泡
    modalContent.addEventListener('click', function(e) {
        e.stopPropagation();
    });
    
    // 标签切换功能
    const tabBtns = modal.querySelectorAll('.tab-btn');
    const tabContents = modal.querySelectorAll('.tab-content');
    
    tabBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const tabId = this.getAttribute('data-tab');
            
            // 更新标签按钮样式
            tabBtns.forEach(b => {
                b.style.color = '#e0e0e0';
                b.style.fontWeight = 'normal';
            });
            this.style.color = '#007bff';
            this.style.fontWeight = 'bold';
            
            // 隐藏所有内容
            tabContents.forEach(content => {
                content.style.display = 'none';
            });
            
            // 显示选中的内容
            document.getElementById(`${tabId}-tab`).style.display = 'block';
        });
    });
    
    // 加载买入记录
    function loadBuyRecords() {
        const buyRecords = getBuyRecords(fund.id);
        // 按日期从旧到新排序
        buyRecords.sort((a, b) => new Date(a.date) - new Date(b.date));
        const buyRecordsContent = modal.querySelector('#buy-records-content');
        const totalSharesElement = modal.querySelector('#total-shares');
        const avgNavElement = modal.querySelector('#avg-nav');
        
        if (buyRecords.length > 0) {
            let recordsHTML = '';
            let totalShares = 0;
            let totalAmount = 0;
            buyRecords.forEach((record, index) => {
                recordsHTML += `<p style="display: flex; align-items: center;">• ${record.date} ${record.shares}份 净值${record.nav}元<span class="delete-record" data-index="${index}" style="cursor: pointer; color: #ff4444; margin-left: 10px; opacity: 0; transition: opacity 0.2s;">x</span></p>`;
                totalShares += record.shares;
                totalAmount += record.shares * record.nav;
            });
            buyRecordsContent.innerHTML = recordsHTML;
            totalSharesElement.textContent = totalShares;
            const avgNav = totalAmount / totalShares;
            avgNavElement.textContent = avgNav.toFixed(4);
            
            // 添加hover效果
            document.querySelectorAll('#buy-records-content p').forEach((p, index) => {
                p.addEventListener('mouseenter', function() {
                    this.querySelector('.delete-record').style.opacity = '1';
                });
                p.addEventListener('mouseleave', function() {
                    this.querySelector('.delete-record').style.opacity = '0';
                });
            });
            
            // 添加删除事件监听
            document.querySelectorAll('.delete-record').forEach(btn => {
                btn.addEventListener('click', function() {
                    const index = parseInt(this.getAttribute('data-index'));
                    deleteBuyRecord(fund.id, index);
                    loadBuyRecords();
                    // 更新总持仓设置
                    const updatedRecords = getBuyRecords(fund.id);
                    const updatedTotalShares = updatedRecords.reduce((total, record) => total + record.shares, 0);
                    const buySettings = {
                        date: new Date().toISOString().split('T')[0],
                        shares: updatedTotalShares
                    };
                    localStorage.setItem(`fundBuySettings_${fund.id}`, JSON.stringify(buySettings));
                    // 重新加载页面以更新预估收益
                    loadFunds();
                });
            });
        } else {
            buyRecordsContent.textContent = '暂无持仓记录';
            totalSharesElement.textContent = '0';
            avgNavElement.textContent = '0.0000';
        }
    }
    
    // 删除买入记录
    function deleteBuyRecord(fundId, index) {
        const records = getBuyRecords(fundId);
        if (index >= 0 && index < records.length) {
            records.splice(index, 1);
            localStorage.setItem(`fundBuyRecords_${fundId}`, JSON.stringify(records));
        }
    }
    
    // 初始加载买入记录
    loadBuyRecords();
    
    // 保存买入设置
    modal.querySelector('#save-buy-settings').addEventListener('click', function() {
        const buyDate = document.getElementById('buy-date').value;
        const buyShares = parseInt(document.getElementById('buy-shares').value) || 0;
        
        if (buyShares > 0) {
            // 尝试获取购买当天的净值
            let buyNav = fund.prices[fund.prices.length - 1]; // 默认使用当前净值
            
            // 尝试从历史数据中查找对应日期的净值
            if (fund.dates && fund.prices) {
                for (let i = 0; i < fund.dates.length; i++) {
                    if (fund.dates[i] === buyDate) {
                        buyNav = fund.prices[i];
                        break;
                    }
                }
            }
            
            // 保存买入记录
            const buyRecord = {
                date: buyDate,
                shares: buyShares,
                nav: buyNav
            };
            saveBuyRecord(fund.id, buyRecord);
            
            // 计算总持仓
            const buyRecords = getBuyRecords(fund.id);
            const totalShares = buyRecords.reduce((total, record) => total + record.shares, 0);
            
            // 保存总持仓
            const buySettings = {
                date: buyDate,
                shares: totalShares
            };
            localStorage.setItem(`fundBuySettings_${fund.id}`, JSON.stringify(buySettings));
            
            // 重新加载买入记录
            loadBuyRecords();
            
            // 初始化表单
            document.getElementById('buy-date').value = new Date().toISOString().split('T')[0];
            document.getElementById('buy-shares').value = 0;
            
            alert('买入设置已保存');
            // 重新加载页面以更新预估收益
            loadFunds();
        } else {
            alert('请输入有效的买入份数');
        }
    });
    
    // 时间范围按钮
    const timeBtns = modal.querySelectorAll('.time-btn');
    
    // 更新按钮样式的函数
    function updateTimeBtnStyles() {
        timeBtns.forEach(btn => {
            if (btn.classList.contains('active')) {
                btn.style.cssText = `
                    background-color: #007bff;
                    color: white;
                    border: 1px solid #333;
                    padding: 4px 8px;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 12px;
                `;
            } else {
                btn.style.cssText = `
                    background-color: #2a2a2a;
                    color: #e0e0e0;
                    border: 1px solid #333;
                    padding: 4px 8px;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 12px;
                `;
            }
        });
    }
    
    // 初始化按钮样式
    updateTimeBtnStyles();
    
    // 添加点击事件
    timeBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            // 移除所有按钮的active类
            timeBtns.forEach(b => b.classList.remove('active'));
            // 添加当前按钮的active类
            this.classList.add('active');
            // 更新按钮样式
            updateTimeBtnStyles();
            // 更新图表
            const days = parseInt(this.getAttribute('data-days'));
            updateChart(fund, chartId, days);
        });
    });
    
    // 添加涨跌颜色样式
    const style = document.createElement('style');
    style.textContent = `
        .positive { color: #ff4444; }
        .negative { color: #4CAF50; }
        .return-value { font-weight: bold; }
    `;
    modalContent.appendChild(style);
    
    // 初始化图表
    updateChart(fund, chartId, 7);
}

function getFundDetails(code) {
    // 从后端API获取真实的基金详细信息
    return fetch(`/api/funds/${code}/details`)
        .then(response => response.json())
        .catch(error => {
            console.error('获取基金详情失败:', error);
            // 如果API调用失败，返回空对象
            return {
                establishmentDate: '',
                field: '',
                manager: '',
                size: '',
                composition: [],
                relatedStocks: []
            };
        });
}

function getBuySettings(fundId) {
    const defaultSettings = {
        date: new Date().toISOString().split('T')[0],
        shares: 0
    };
    
    const savedSettings = localStorage.getItem(`fundBuySettings_${fundId}`);
    return savedSettings ? JSON.parse(savedSettings) : defaultSettings;
}

function getBuyRecords(fundId) {
    const savedRecords = localStorage.getItem(`fundBuyRecords_${fundId}`);
    return savedRecords ? JSON.parse(savedRecords) : [];
}

function saveBuyRecord(fundId, record) {
    const records = getBuyRecords(fundId);
    records.push(record);
    localStorage.setItem(`fundBuyRecords_${fundId}`, JSON.stringify(records));
}

function updateChart(fund, chartId, days) {
    // 计算需要显示的数据点数量
    const prices = fund.prices && fund.prices.length > 0 ? fund.prices : [];
    const dates = fund.dates && fund.dates.length > 0 ? fund.dates : [];
    let displayPrices, displayDates;
    
    if (days === 0) {
        // 显示所有数据
        displayPrices = prices;
        displayDates = dates;
    } else {
        const dataPoints = Math.min(days, prices.length);
        const startIndex = Math.max(0, prices.length - dataPoints);
        displayPrices = prices.slice(startIndex);
        displayDates = dates.slice(startIndex);
    }
    
    // 计算支撑位和压力位
    const latestPrice = prices[prices.length - 1] || 0;
    const supportLevel = latestPrice * 0.9;
    const resistanceLevel = latestPrice * 1.1;
    
    // 创建支撑位和压力位数据
    const supportData = Array(displayPrices.length).fill(supportLevel);
    const resistanceData = Array(displayPrices.length).fill(resistanceLevel);
    
    // 获取图表上下文
    const ctx = document.getElementById(chartId).getContext('2d');
    
    // 销毁现有图表
    if (window.fundChart) {
        window.fundChart.destroy();
    }
    
    // 创建新图表
    window.fundChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: displayDates,
            datasets: [
                {
                    label: '净值',
                    data: displayPrices,
                    borderColor: '#33b5e5',
                    backgroundColor: 'rgba(51, 181, 229, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true,
                    pointRadius: 3,
                    pointHoverRadius: 5
                },
                {
                    label: '支撑位',
                    data: supportData,
                    borderColor: '#4caf50',
                    borderWidth: 1,
                    borderDash: [5, 5],
                    fill: false,
                    pointRadius: 0,
                    pointHoverRadius: 0
                },
                {
                    label: '压力位',
                    data: resistanceData,
                    borderColor: '#ff9800',
                    borderWidth: 1,
                    borderDash: [5, 5],
                    fill: false,
                    pointRadius: 0,
                    pointHoverRadius: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#ffffff',
                    bodyColor: '#e0e0e0',
                    borderColor: '#333',
                    borderWidth: 1,
                    padding: 10,
                    displayColors: false,
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            if (context.parsed.y !== null) {
                                label += context.parsed.y.toFixed(4);
                            }
                            return label;
                        }
                    }
                }
            },
            scales: {
                x: {
                    position: 'bottom',
                    ticks: {
                        color: '#aaa',
                        font: {
                            size: 11
                        },
                        maxRotation: 0
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)',
                        drawBorder: false
                    }
                },
                y: {
                    position: 'left',
                    ticks: {
                        color: '#aaa',
                        font: {
                            size: 11
                        },
                        callback: function(value) {
                            return value.toFixed(2);
                        }
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)',
                        drawBorder: false
                    }
                }
            },
            interaction: {
                intersect: false,
                mode: 'index'
            },
            animation: {
                duration: 1000,
                easing: 'easeInOutQuart'
            },
            layout: {
                padding: {
                    left: 10,
                    right: 10,
                    top: 10,
                    bottom: 10
                }
            }
        }
    });
}

function getRSIMessage(rsi) {
    if (rsi > 70) {
        return '(过热: 追高风险)';
    } else if (rsi < 30) {
        return '(冰点: 反弹机会)';
    } else {
        return '(正常)';
    }
}

function getInvestmentAdvice(fund) {
    let advice = '';
    
    if (fund.rsi > 70) {
        advice += 'RSI指标过高，当前基金处于超买状态，建议谨慎追高，可考虑减仓或观望。';
    } else if (fund.rsi < 30) {
        advice += 'RSI指标过低，当前基金处于超卖状态，可能存在反弹机会，可考虑适当加仓。';
    } else {
        advice += 'RSI指标处于正常范围，基金走势相对稳定。';
    }
    
    if (fund.volatility > 0.2) {
        advice += ' 波动率较高，风险较大，建议控制仓位。';
    } else {
        advice += ' 波动率较低，风险相对较小。';
    }
    
    if (fund.predicted_return > 0) {
        advice += ' 预测收益率为正，短期可能有上涨空间。';
    } else {
        advice += ' 预测收益率为负，短期可能面临调整。';
    }
    
    return advice;
}

function showSettings() {
    // 获取当前设置
    const settings = getSettings();
    
    // 创建弹框
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0, 0, 0, 0.8);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 1000;
    `;
    
    // 弹框内容
    const modalContent = document.createElement('div');
    modalContent.className = 'modal-content';
    modalContent.style.cssText = `
        background-color: #1e1e1e;
        padding: 16px;
        border-radius: 6px;
        width: 90%;
        max-width: 600px;
        max-height: 90vh;
        overflow-y: auto;
        box-shadow: 0 5px 20px rgba(0, 0, 0, 0.6);
        border: 1px solid #333;
    `;
    
    // 弹框HTML
    modalContent.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <h2 style="color: white; margin: 0; font-size: 14px;">设置</h2>
            <button class="close-btn" style="background-color: #2a2a2a; color: #e0e0e0; border: 1px solid #333; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 10px;">关闭</button>
        </div>
        
        <div style="margin-bottom: 16px;">
            <h3 style="color: #e0e0e0; margin-bottom: 8px; font-size: 12px;">显示设置</h3>
            <div style="background-color: #2a2a2a; border-radius: 4px; padding: 12px; border: 1px solid #333;">
                <div style="margin-bottom: 8px;">
                    <label style="font-size: 11px; margin-right: 10px;">字体大小:</label>
                    <select id="font-size" style="background-color: #333; color: #e0e0e0; border: 1px solid #444; padding: 3px 6px; border-radius: 4px; font-size: 10px;">
                        <option value="small" ${settings.fontSize === 'small' ? 'selected' : ''}>小</option>
                        <option value="medium" ${settings.fontSize === 'medium' ? 'selected' : ''}>中</option>
                        <option value="large" ${settings.fontSize === 'large' ? 'selected' : ''}>大</option>
                    </select>
                </div>
                <div style="margin-bottom: 8px;">
                    <label style="font-size: 11px; margin-right: 10px;">更新频率:</label>
                    <select id="update-frequency" style="background-color: #333; color: #e0e0e0; border: 1px solid #444; padding: 3px 6px; border-radius: 4px; font-size: 10px;">
                        <option value="1" ${settings.updateFrequency === '1' ? 'selected' : ''}>1分钟</option>
                        <option value="5" ${settings.updateFrequency === '5' ? 'selected' : ''}>5分钟</option>
                        <option value="15" ${settings.updateFrequency === '15' ? 'selected' : ''}>15分钟</option>
                        <option value="30" ${settings.updateFrequency === '30' ? 'selected' : ''}>30分钟</option>
                        <option value="60" ${settings.updateFrequency === '60' ? 'selected' : ''}>1小时</option>
                    </select>
                </div>
                <div style="margin-bottom: 4px;">
                    <input type="checkbox" id="show-distance" ${settings.showDistance ? 'checked' : ''} style="margin-right: 8px;">
                    <label for="show-distance" style="font-size: 11px;">显示距高点</label>
                </div>
                <div style="margin-bottom: 4px;">
                    <input type="checkbox" id="show-rsi" ${settings.showRSI ? 'checked' : ''} style="margin-right: 8px;">
                    <label for="show-rsi" style="font-size: 11px;">显示RSI</label>
                </div>
                <div style="margin-bottom: 4px;">
                    <input type="checkbox" id="show-alerts" ${settings.showAlerts ? 'checked' : ''} style="margin-right: 8px;">
                    <label for="show-alerts" style="font-size: 11px;">显示风险提示</label>
                </div>
            </div>
        </div>
        
        <div style="margin-bottom: 16px;">
            <h3 style="color: #e0e0e0; margin-bottom: 8px; font-size: 12px;">基金管理</h3>
            <div style="background-color: #2a2a2a; border-radius: 4px; padding: 12px; border: 1px solid #333;">
                <div id="fund-management" style="max-height: 200px; overflow-y: auto;">
                    <!-- 基金列表将通过JavaScript动态添加 -->
                </div>
            </div>
        </div>
        
        <div style="display: flex; justify-content: flex-end; gap: 8px;">
            <button id="save-settings" style="background-color: #007bff; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 11px;">保存设置</button>
        </div>
    `;
    
    // 添加到页面
    modal.appendChild(modalContent);
    document.body.appendChild(modal);
    
    // 关闭按钮
    modal.querySelector('.close-btn').addEventListener('click', function() {
        document.body.removeChild(modal);
    });
    
    // 加载基金列表
    loadFundManagement(modal.querySelector('#fund-management'));
    
    // 保存设置按钮
    modal.querySelector('#save-settings').addEventListener('click', function() {
        const newSettings = {
            fontSize: document.getElementById('font-size').value,
            updateFrequency: document.getElementById('update-frequency').value,
            showDistance: document.getElementById('show-distance').checked,
            showRSI: document.getElementById('show-rsi').checked,
            showAlerts: document.getElementById('show-alerts').checked
        };
        
        localStorage.setItem('fundTrackerSettings', JSON.stringify(newSettings));
        alert('设置已保存');
        document.body.removeChild(modal);
        // 应用设置
        applySettings(newSettings);
    });
}

function getSettings() {
    const defaultSettings = {
        fontSize: 'medium',
        updateFrequency: '5',
        showDistance: true,
        showRSI: true,
        showAlerts: true
    };
    
    const savedSettings = localStorage.getItem('fundTrackerSettings');
    return savedSettings ? JSON.parse(savedSettings) : defaultSettings;
}

function applySettings(settings) {
    // 应用字体大小
    document.body.style.fontSize = settings.fontSize === 'small' ? '13px' : settings.fontSize === 'large' ? '15px' : '14px';
    
    // 应用其他设置（这里可以添加更多设置的应用逻辑）
    console.log('应用设置:', settings);
}

function loadFundManagement(container) {
    fetch('/api/funds')
        .then(response => response.json())
        .then(funds => {
            container.innerHTML = '';
            
            if (funds.length === 0) {
                container.innerHTML = '<p style="text-align: center; color: #888; font-size: 11px; margin: 10px 0;">暂无基金</p>';
                return;
            }
            
            funds.forEach(fund => {
                const fundItem = document.createElement('div');
                fundItem.style.cssText = `
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 6px;
                    border-bottom: 1px solid #333;
                `;
                
                fundItem.innerHTML = `
                    <div>
                        <div style="font-size: 11px; font-weight: bold; color: white;">${fund.name}</div>
                        <div style="font-size: 10px; color: #aaa;">${fund.code}</div>
                    </div>
                    <button class="delete-fund-btn" data-id="${fund.id}" style="background-color: #dc3545; color: white; border: none; padding: 3px 6px; border-radius: 4px; cursor: pointer; font-size: 10px;">删除</button>
                `;
                
                container.appendChild(fundItem);
            });
            
            // 添加删除基金事件
            container.querySelectorAll('.delete-fund-btn').forEach(btn => {
                btn.addEventListener('click', function() {
                    const fundId = parseInt(this.getAttribute('data-id'));
                    if (confirm('确定要删除该基金吗？')) {
                        deleteFund(fundId);
                        // 重新加载基金列表
                        loadFundManagement(container);
                    }
                });
            });
        });
}

// 页面加载时应用设置
window.addEventListener('load', function() {
    const settings = getSettings();
    applySettings(settings);
});