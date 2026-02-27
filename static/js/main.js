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
            
            // 更新组计数
            document.getElementById('group-count').textContent = funds.length;
            
            if (funds.length === 0) {
                container.innerHTML = '<p style="text-align: center; color: #888; padding: 20px;">No funds in this group. Add one to track.</p>';
                return;
            }
            
            funds.forEach(fund => {
                const fundItem = document.createElement('div');
                fundItem.className = 'fund-item';
                
                // 计算距高点
                const maxPrice = Math.max(...fund.prices);
                const currentPrice = fund.prices[fund.prices.length - 1];
                const distanceFromHigh = ((currentPrice - maxPrice) / maxPrice * 100).toFixed(2);
                
                // 生成唯一的图表ID
                const priceChartId = `price-chart-${fund.id}`;
                const returnChartId = `return-chart-${fund.id}`;
                
                fundItem.innerHTML = `
                    <div class="fund-info">
                        <div class="fund-name">${fund.name}</div>
                        <div class="fund-details">
                            <div class="fund-detail">
                                <span>${fund.code}</span>
                                <span style="color: #007bff;">场外</span>
                            </div>
                            <div class="fund-detail">
                                <span>距高点 ${distanceFromHigh}%</span>
                            </div>
                            <div class="fund-detail">
                                <span>RSI ${fund.rsi.toFixed(1)}</span>
                            </div>
                        </div>
                    </div>
                    <div class="fund-performance">
                        <div class="fund-return ${fund.predicted_return < 0 ? 'negative' : ''}">
                            ${fund.predicted_return >= 0 ? '+' : ''}${(fund.predicted_return * 100).toFixed(2)}%
                        </div>
                        <button class="real-time-btn">
                            <span>Real-time</span>
                            <span>🔄</span>
                        </button>
                        <button class="delete-btn" onclick="deleteFund(${fund.id})">删除</button>
                    </div>
                `;
                
                // 添加到容器
                container.appendChild(fundItem);
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