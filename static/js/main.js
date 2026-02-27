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
                    </div>
                    <button class="delete-btn" onclick="deleteFund(${fund.id})">删除</button>
                `;
                
                container.appendChild(fundItem);
            });
        });
}

function addFund() {
    const name = document.getElementById('fund-name').value;
    const code = document.getElementById('fund-code').value;
    const pricesStr = document.getElementById('fund-prices').value;
    const prices = pricesStr.split(',').map(price => parseFloat(price.trim())).filter(price => !isNaN(price));
    
    fetch('/api/funds', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ name, code, prices })
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