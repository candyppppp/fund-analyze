document.addEventListener('DOMContentLoaded', function() {
    loadFunds();
    
    document.getElementById('add-fund-form').addEventListener('submit', function(e) {
        e.preventDefault();
        addFund();
    });
});

function loadFunds() {
    fetch('/api/funds')
        .then(response => response.json())
        .then(funds => {
            const container = document.getElementById('funds-container');
            container.innerHTML = '';
            
            if (funds.length === 0) {
                container.innerHTML = '<p>No funds in this group. Add one to track.</p>';
                return;
            }
            
            funds.forEach(fund => {
                const fundItem = document.createElement('div');
                fundItem.className = 'fund-item';
                
                let rsiClass = 'rsi-normal';
                let rsiMessage = '';
                if (fund.rsi > 70) {
                    rsiClass = 'rsi-hot';
                    rsiMessage = '🔥 RSI>70 (过热): 追高风险';
                } else if (fund.rsi < 30) {
                    rsiClass = 'rsi-cold';
                    rsiMessage = '❄️ RSI<30 (冰点): 反弹机会';
                }
                
                let volatilityClass = 'volatility-normal';
                let volatilityMessage = '';
                if (fund.volatility > 0.2) {
                    volatilityClass = 'volatility-high';
                    volatilityMessage = '🌪️ High Vol: 剧烈波动';
                }
                
                // 预测收益率样式
                let returnClass = 'return-positive';
                if (fund.predicted_return < 0) {
                    returnClass = 'return-negative';
                }
                
                // 生成唯一的图表ID
                const priceChartId = `price-chart-${fund.id}`;
                const returnChartId = `return-chart-${fund.id}`;
                
                fundItem.innerHTML = `
                    <h3>${fund.name} (${fund.code})</h3>
                    <div class="fund-metrics">
                        <div class="metric ${rsiClass}">
                            RSI: ${fund.rsi.toFixed(2)}<br>
                            ${rsiMessage}
                        </div>
                        <div class="metric ${volatilityClass}">
                            波动率: ${(fund.volatility * 100).toFixed(2)}%<br>
                            ${volatilityMessage}
                        </div>
                        <div class="metric ${returnClass}">
                            预测收益率: ${(fund.predicted_return * 100).toFixed(2)}%<br>
                            ${fund.predicted_return >= 0 ? '📈 上涨' : '📉 下跌'}
                        </div>
                    </div>
                    <div class="fund-charts">
                        <div class="chart-container">
                            <h4>净值趋势</h4>
                            <canvas id="${priceChartId}"></canvas>
                        </div>
                        <div class="chart-container">
                            <h4>收益率趋势</h4>
                            <canvas id="${returnChartId}"></canvas>
                        </div>
                    </div>
                    <button class="delete-btn" onclick="deleteFund(${fund.id})">删除</button>
                `;
                
                // 添加到容器后再绘制图表
                container.appendChild(fundItem);
                
                // 绘制净值趋势图
                const priceCtx = document.getElementById(priceChartId).getContext('2d');
                new Chart(priceCtx, {
                    type: 'line',
                    data: {
                        labels: fund.dates,
                        datasets: [{
                            label: '净值',
                            data: fund.prices,
                            borderColor: '#33b5e5',
                            backgroundColor: 'rgba(51, 181, 229, 0.1)',
                            borderWidth: 2,
                            tension: 0.3,
                            fill: true
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            x: {
                                display: true,
                                title: {
                                    display: true,
                                    text: '日期'
                                }
                            },
                            y: {
                                display: true,
                                title: {
                                    display: true,
                                    text: '净值'
                                }
                            }
                        }
                    }
                });
                
                // 绘制收益率趋势图
                const returnCtx = document.getElementById(returnChartId).getContext('2d');
                new Chart(returnCtx, {
                    type: 'bar',
                    data: {
                        labels: fund.dates,
                        datasets: [{
                            label: '日收益率(%)',
                            data: fund.returns,
                            backgroundColor: fund.returns.map(ret => ret >= 0 ? '#4CAF50' : '#ff4444'),
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            x: {
                                display: true,
                                title: {
                                    display: true,
                                    text: '日期'
                                }
                            },
                            y: {
                                display: true,
                                title: {
                                    display: true,
                                    text: '收益率(%)'
                                }
                            }
                        }
                    }
                });
            });
        });
}

function addFund() {
    const code = document.getElementById('fund-code').value;
    
    fetch('/api/funds', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ code })
    })
    .then(response => response.json())
    .then(() => {
        loadFunds();
        document.getElementById('add-fund-form').reset();
    });
}

function deleteFund(id) {
    fetch(`/api/funds/${id}`, {
        method: 'DELETE'
    })
    .then(() => {
        loadFunds();
    });
}