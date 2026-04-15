// 导入技术分析模块
import { calculateMA, calculateSupportResistance, calculateBollingerBands, calculateMACD, calculateKDJ, calculateATR } from './technical-analysis.js';
// 导入投资建议模块
import InvestmentAdvice from './investment-advice.js';
// 导入缓存管理器
import cacheManager from './cache-manager.js';
// 导入更新策略管理器
import updateStrategyManager from './update-strategy.js';

// 创建投资建议实例
const investmentAdvice = new InvestmentAdvice();
window.investmentAdvice = investmentAdvice; // 暴露到全局供 onclick 使用

// 缓存键
const CACHE_KEYS = {
    INVESTMENT_ADVICE: 'investmentAdvice',
    FUNDS_LIST: 'fundsList'
};

// 缓存有效期（毫秒）
const CACHE_EXPIRY = {
    INVESTMENT_ADVICE: 5 * 60 * 1000, // 5分钟
    FUNDS_LIST: 2 * 60 * 1000         // 2分钟
};

// 当前激活的标签
let activeTab = 'fund-prediction';
window.activeTab = activeTab; // 使activeTab在全局范围内可用

document.addEventListener('DOMContentLoaded', function() {
    // 预热云端买入记录缓存 + 迁移 localStorage 数据
    fetchAllBuyRecords().then(records => {
        if (records && records.length > 0) {
            window._cloudBuyRecords = records;
            // 云端数据加载完后重新渲染，确保持仓数据正确显示
            const cached = cacheManager.get(CACHE_KEYS.FUNDS_LIST);
            if (cached && cached.length) renderFunds(cached);
        }
    });
    setTimeout(() => migrateBuyRecordsToCloud(), 3000); // 等基金列表加载完再迁移

    // 排序固定为持仓优先，无需按钮事件

    // ── 定时闪烁（即使没数据更新也有视觉活跃感，每20秒随机闪一只卡片）──────
    setInterval(() => {
        const cards = document.querySelectorAll('.fund-item');
        if (!cards.length) return;
        const idx = Math.floor(Math.random() * cards.length);
        flashCard(cards[idx]);
    }, 20000);

    // 检查登录状态
    checkLoginStatus();

    loadFunds(); // 只加载基金列表，不加载基金预测

    // 启动定期更新
    startFundUpdateInterval();

    document.getElementById('add-fund-form').addEventListener('submit', function(e) {
        e.preventDefault();
        addFund();
    });

    // 设置按钮
    document.querySelector('.header-buttons button').addEventListener('click', function() {
        showSettings();
    });

    // 标签切换
    document.querySelectorAll('.tab').forEach((tab, index) => {
        tab.addEventListener('click', function() {
            // 如果点击的是当前激活的标签，直接返回
            if (this.classList.contains('active')) return;

            // 移除所有标签的活动状态
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            // 添加当前标签的活动状态
            this.classList.add('active');

            // 切换标签内容
            if (index === 0) {
                // 基金自选标签
                activeTab = 'fund-prediction';
                window.activeTab = activeTab;
                showLoadingState('正在加载基金自选列表...');
                loadFunds();
                updateStrategyManager.switchTab('fund-prediction');
            } else if (index === 1) {
                // 基金投资标签
                activeTab = 'investment-advice';
                window.activeTab = activeTab;
                showLoadingState('正在加载基金投资建议，请稍候...');
                investmentAdvice.loadInvestmentAdvice();
                updateStrategyManager.switchTab('investment-advice');
            }
        });
    });
});

// 检查登录状态
function checkLoginStatus() {
    // 从本地存储获取登录信息
    const loginInfo = localStorage.getItem('loginInfo');
    if (loginInfo) {
        try {
            const info = JSON.parse(loginInfo);
            const now = new Date().getTime();
            // 检查登录信息是否过期（7天）
            if (now - info.timestamp < 7 * 24 * 60 * 60 * 1000) {
                // 登录信息有效
                return true;
            } else {
                // 登录信息过期
                localStorage.removeItem('loginInfo');
                return false;
            }
        } catch (error) {
            console.error('解析登录信息失败:', error);
            localStorage.removeItem('loginInfo');
            return false;
        }
    }
    return false;
}

// 保存登录信息
function saveLoginInfo(username) {
    const loginInfo = {
        username: username,
        timestamp: new Date().getTime()
    };
    localStorage.setItem('loginInfo', JSON.stringify(loginInfo));
}

// 清除登录信息
function clearLoginInfo() {
    localStorage.removeItem('loginInfo');
}

// 显示加载状态
function showLoadingState(message = '加载中...') {
    const container = document.getElementById('funds-container');
    if (container) {
        container.innerHTML = `
            <div class="loading-container" style="
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                padding: 60px 20px;
                color: #666;
            ">
                <div class="loading-spinner" style="
                    width: 40px;
                    height: 40px;
                    border: 4px solid #f3f3f3;
                    border-top: 4px solid #007bff;
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                    margin-bottom: 20px;
                "></div>
                <p style="font-size: 16px; margin: 0;">${message}</p>
            </div>
            <style>
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            </style>
        `;
    }
}



// 通过代码添加基金
function addFundByCode(code) {
    // 防重复：和 addFund 共用同一个锁
    if (isAddingFund) {
        return;
    }
    isAddingFund = true;

    const isInvestmentTab = window.activeTab === 'investment-advice';

    if (!isInvestmentTab) {
        const container = document.getElementById('funds-container');
        if (container) {
            container.innerHTML = '<p style="text-align: center; color: #007bff; padding: 20px;">添加基金中...</p>';
        }
    } else {
        showSuccess(`正在添加 ${code}，请稍候...`);
    }

    fetch('/api/funds', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code })
    })
    .then(response => {
        if (response.status === 401) {
            window.location.href = '/login';
            return Promise.reject('未登录');
        }
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.error) {
            showError(data.error);
            if (!isInvestmentTab) loadFunds();
            return;
        }

        // 初始化持仓设置
        localStorage.setItem(`fundBuySettings_${data.id}`, JSON.stringify({
            date: new Date().toISOString().split('T')[0], shares: 0
        }));
        localStorage.setItem(`fundBuyRecords_${data.id}`, JSON.stringify([]));

        // 清除全部缓存（含 localStorage）
        cacheManager.clear('funds');
        cacheManager.clear('fundHoldings');
        try { localStorage.removeItem('funds'); } catch(e) {}

        if (isInvestmentTab) {
            showSuccess(`${code} 已加入自选`);
            // 后台预加载，切回基金自选 tab 时直接读最新数据
            fetch('/api/funds')
                .then(r => r.json())
                .then(funds => {
                    cacheManager.set(CACHE_KEYS.FUNDS_LIST, funds, CACHE_EXPIRY.FUNDS_LIST);
                    try { localStorage.setItem('funds', JSON.stringify(funds)); } catch(e) {}
                })
                .catch(() => {});
        } else {
            // 直接从 API 拉最新列表，跳过缓存，立刻渲染
            fetch('/api/funds')
                .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
                .then(funds => {
                    cacheManager.set(CACHE_KEYS.FUNDS_LIST, funds, CACHE_EXPIRY.FUNDS_LIST);
                    try { localStorage.setItem('funds', JSON.stringify(funds)); } catch(e) {}
                    return processFunds(funds);
                })
                .then(() => {
                    document.getElementById('add-fund-form') && document.getElementById('add-fund-form').reset();
                    showSuccess('基金添加成功');
                })
                .catch(err => {
                    console.error('刷新基金列表失败:', err);
                    showError('基金已添加，刷新列表失败，请手动刷新');
                });
        }
    })
    .catch(error => {
        console.error('添加基金失败:', error);
        if (error !== '未登录') {
            showError('添加基金失败，请稍后重试');
            if (!isInvestmentTab) loadFunds();
        }
    })
    .finally(() => {
        // 解锁
        isAddingFund = false;
    });
}

// 暴露到全局作用域
window.addFundByCode = addFundByCode;

// 标题动画效果
function animateTitle() {
    const fundPart = document.querySelector('.header h1 .fund-part');
    const trackerPart = document.querySelector('.header h1 .tracker-part');
    if (!fundPart || !trackerPart) return;

    let fundPulse = 1;
    let fundPulseDirection = 1;
    let trackerPosition = 0;
    let trackerDirection = 1;
    let shadowOpacity = 0.3;
    let shadowDirection = 1;

    setInterval(() => {
        // Fund 部分脉冲效果
        fundPulse += 0.01 * fundPulseDirection;
        if (fundPulse >= 1.1 || fundPulse <= 0.9) {
            fundPulseDirection *= -1;
        }
        fundPart.style.transform = `scale(${fundPulse})`;
        fundPart.style.textShadow = `0 0 10px rgba(0, 123, 255, ${shadowOpacity})`;

        // Tracker 部分滑动效果
        trackerPosition += 0.1 * trackerDirection;
        if (trackerPosition >= 5 || trackerPosition <= -5) {
            trackerDirection *= -1;
        }
        trackerPart.style.transform = `translateX(${trackerPosition}px)`;
        trackerPart.style.textShadow = `0 0 10px rgba(255, 255, 255, ${shadowOpacity})`;

        // 文字阴影透明度变化
        shadowOpacity += 0.01 * shadowDirection;
        if (shadowOpacity >= 0.8 || shadowOpacity <= 0.2) {
            shadowDirection *= -1;
        }

        // 添加呼吸效果 - 整体透明度变化
        const opacity = 0.8 + Math.sin(Date.now() / 1000) * 0.2;
        fundPart.style.opacity = opacity;
        trackerPart.style.opacity = opacity;
    }, 50);
}

// 缓存管理器已从 cache-manager.js 导入

// 基金数据自动更新定时器
let fundUpdateInterval = null;
let fundHoldingsUpdateIntervals = {}; // 每个基金的持仓更新定时器

// 获取市场数据（带缓存）
function getMarketData() {
    const cachedData = cacheManager.get('marketData');
    if (cachedData) {
        return Promise.resolve(cachedData);
    }

    // 缓存过期，从API获取新数据
    return fetch('/api/market-data')
        .then(response => response.json())
        .then(data => {
            // 更新缓存
            cacheManager.set('marketData', data);
            return data;
        })
        .catch(error => {
            console.error('获取市场数据失败:', error);
            // 如果获取失败，返回缓存数据（如果有）
            return cacheManager.get('marketData');
        });
}

// 处理基金数据的函数
function processFunds(funds) {
    return new Promise((resolve, reject) => {
        // 先获取市场数据
        getMarketData().then(marketData => {
            // 为每个基金添加市场数据
            funds.forEach(fund => {
                fund.market_data = marketData;
            });

            // 批量获取基金持仓数据，减少API请求
            const fundCodes = funds.map(fund => fund.code);
            const batchSize = 5; // 每批处理5个基金
            const batches = [];

            for (let i = 0; i < fundCodes.length; i += batchSize) {
                batches.push(fundCodes.slice(i, i + batchSize));
            }

            // 按批次处理，避免同时发起过多请求
            let processedFunds = funds;
            const processBatch = (batchIndex) => {
                if (batchIndex >= batches.length) {
                    return Promise.resolve(processedFunds);
                }

                const batch = batches[batchIndex];
                const batchPromises = batch.map(code => {
                    // 检查持仓数据缓存
                    const cachedHoldings = cacheManager.get('fundHoldings', code);
                    if (cachedHoldings) {
                        const fund = processedFunds.find(f => f.code === code);
                        if (fund) {
                            fund.stock_holdings = cachedHoldings;
                        }
                        return Promise.resolve(cachedHoldings);
                    }

                    // 缓存未命中，从API获取
                    return fetch(`/api/funds/${code}/holdings`)
                        .then(response => {
                            if (!response.ok) {
                                throw new Error(`HTTP error! status: ${response.status}`);
                            }
                            return response.json();
                        })
                        .then(holdings => {
                            // 找到对应的基金并添加持仓数据
                            const fund = processedFunds.find(f => f.code === code);
                            if (fund) {
                                fund.stock_holdings = holdings;
                            }
                            // 缓存持仓数据
                            cacheManager.set('fundHoldings', holdings, code);
                            return holdings;
                        })
                        .catch(error => {
                            console.error(`获取基金 ${code} 持仓数据失败:`, error);
                            return null;
                        });
                });

                return Promise.all(batchPromises).then(() => {
                    // 延迟300ms处理下一批，避免请求过于集中
                    return new Promise(resolve => setTimeout(() => {
                        resolve(processBatch(batchIndex + 1));
                    }, 300));
                });
            };

            processBatch(0).then(processedFunds => {
                // 渲染基金列表
                renderFunds(processedFunds);
                // 启动每个基金的持仓更新定时器
                startFundHoldingsUpdateIntervals(processedFunds);
                resolve(processedFunds);
            }).catch(reject);
        }).catch(reject);
    });
}

function loadFunds() {
    return new Promise((resolve, reject) => {
        // 显示加载状态
        showLoading('加载基金数据中...');

        // 检查本地存储
        let fundsData = null;
        try {
            const storedFunds = localStorage.getItem('funds');
            if (storedFunds) {
                fundsData = JSON.parse(storedFunds);
                // 先显示本地数据，提供即时反馈
                renderFunds(fundsData);
                hideLoading();
                // 启动每个基金的持仓更新定时器
                startFundHoldingsUpdateIntervals(fundsData);
            }
        } catch (error) {
            console.error('读取本地存储失败:', error);
        }

        // 检查缓存
        const cachedFunds = cacheManager.get(CACHE_KEYS.FUNDS_LIST);
        if (cachedFunds) {
            // 显示缓存数据
            renderFunds(cachedFunds);
            hideLoading();
            // 启动每个基金的持仓更新定时器
            startFundHoldingsUpdateIntervals(cachedFunds);
        }

        // 后台更新数据，即使网络不好也不影响显示
        updateFundsInBackground();

        // 确保至少返回本地存储的数据
        if (fundsData) {
            resolve(fundsData);
        } else if (cachedFunds) {
            resolve(cachedFunds);
        } else {
            // 从API获取最新数据
            fetch('/api/funds')
                .then(response => {
                    if (response.status === 401) {
                        // 未登录，重定向到登录页面
                        window.location.href = '/login';
                        return Promise.reject('未登录');
                    }
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(funds => {
                    // 更新缓存
                    cacheManager.set(CACHE_KEYS.FUNDS_LIST, funds, CACHE_EXPIRY.FUNDS_LIST);
                    // 保存到本地存储
                    try {
                        localStorage.setItem('funds', JSON.stringify(funds));
                    } catch (error) {
                        console.error('保存到本地存储失败:', error);
                        showWarning('本地存储空间不足，数据可能无法持久保存');
                    }

                    // 处理基金数据
                    return processFunds(funds);
                })
                .then(updatedFunds => {
                    resolve(updatedFunds);
                })
                .catch(error => {
                    console.error('获取基金数据失败:', error);
                    if (error !== '未登录') {
                        showError('获取基金数据失败，显示本地缓存数据');
                        // 如果API调用失败，返回本地存储的数据
                        if (fundsData) {
                            resolve(fundsData);
                        } else {
                            reject(error);
                        }
                    }
                })
                .finally(() => {
                    hideLoading();
                });
        }
    });
}

// 后台更新基金数据
function updateFundsInBackground() {
    // 获取当前缓存的基金数据
    const currentFunds = cacheManager.get(CACHE_KEYS.FUNDS_LIST);

    fetch('/api/funds')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(funds => {
            // 确保基金数据不为空
            if (funds && funds.length > 0) {
                // 更新缓存
                cacheManager.set(CACHE_KEYS.FUNDS_LIST, funds, CACHE_EXPIRY.FUNDS_LIST);
                // 保存到本地存储
                try {
                    localStorage.setItem('funds', JSON.stringify(funds));
                } catch (error) {
                    console.error('保存到本地存储失败:', error);
                }

                // 只有在当前显示的是基金预测标签时才重新渲染
                if (activeTab === 'fund-prediction') {
                    // 重新渲染以显示最新数据
                    renderFunds(funds);
                    // 重启持仓更新定时器
                    startFundHoldingsUpdateIntervals(funds);

                    // 为更新的基金添加闪烁效果
                    if (currentFunds) {
                        funds.forEach((updatedFund, index) => {
                            const currentFund = currentFunds.find(f => f.code === updatedFund.code);
                            if (currentFund) {
                                // 检查数据是否有变化
                                const hasChanged =
                                    updatedFund.predicted_return !== currentFund.predicted_return ||
                                    updatedFund.prediction_confidence !== currentFund.prediction_confidence ||
                                    updatedFund.real_time_estimated_return !== currentFund.real_time_estimated_return;

                                if (hasChanged) {
                                    // 为变化的基金添加闪烁效果，使用随机延迟，实现散状的不规则更新
                                    // 生成0-60秒的随机延迟，让基金在不同时间闪烁
                                    const randomDelay = Math.floor(Math.random() * 60000); // 0-60000ms 的随机延迟
                                    setTimeout(() => {
                                        const fundElement = document.getElementById(`fund-${updatedFund.id}`);
                                        if (fundElement) {
                                            flashCard(fundElement);
                                        }
                                    }, randomDelay);
                                }
                            }
                        });
                    }
                }
            } else {
            }
        })
        .catch(error => {
            console.error('后台更新基金数据失败:', error);
            // 网络错误时不更新数据，保持使用缓存
        });
}

// 为每个基金启动持仓更新定时器
function startFundHoldingsUpdateIntervals(funds) {
    // 清除现有的定时器
    for (const code in fundHoldingsUpdateIntervals) {
        clearInterval(fundHoldingsUpdateIntervals[code]);
    }
    fundHoldingsUpdateIntervals = {};

    // 为每个基金设置独立的更新定时器
    funds.forEach((fund, index) => {
        // 持仓股票价格5分钟更新一次（降低请求频率，避免429）
        const interval = 5 * 60 * 1000;

        // 随机延迟0-5分钟，错开各基金请求时间
        const randomDelay = Math.floor(Math.random() * 5 * 60 * 1000);

        // 先延迟一段时间，然后开始更新
        setTimeout(() => {
            fundHoldingsUpdateIntervals[fund.code] = setInterval(() => {
                // 检查是否为交易时间
                const now = new Date();
                const day = now.getDay();
                const hour = now.getHours();
                const isTradingTime = day >= 1 && day <= 5 && hour >= 9 && hour < 15;

                if (isTradingTime) {
                    // 只获取持仓数据，基金列表通过定期更新获取
                    fetch(`/api/funds/${fund.code}/holdings`)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }
                        return response.json();
                    })
                    .then(holdings => {
                        // 更新缓存
                        cacheManager.set('fundHoldings', holdings, fund.code);

                        // 更新基金对象
                        const fundsData = cacheManager.get('funds');
                        if (fundsData) {
                            const updatedFunds = fundsData.map(f => {
                                if (f.code === fund.code) {
                                    return {
                                        ...f,
                                        stock_holdings: holdings
                                    };
                                }
                                return f;
                            });
                            // 更新缓存
                            cacheManager.set(CACHE_KEYS.FUNDS_LIST, updatedFunds, CACHE_EXPIRY.FUNDS_LIST);
                            // 重新渲染
                            renderFunds(updatedFunds);

                            // 为更新的基金添加闪烁效果
                            const fundElement = document.getElementById(`fund-${fund.id}`);
                            if (fundElement) {
                                flashCard(fundElement);
                            }
                        }
                    })
                    .catch(error => {
                        console.error(`更新基金 ${fund.code} 数据失败:`, error);
                    });
                }
            }, interval);
        }, randomDelay);
    });
}

// 显示加载状态
function showLoading(message = '加载中...') {
    let loadingElement = document.getElementById('loading-indicator');
    if (!loadingElement) {
        loadingElement = document.createElement('div');
        loadingElement.id = 'loading-indicator';
        loadingElement.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background-color: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 15px 25px;
            border-radius: 5px;
            z-index: 10000;
            font-size: 14px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
        `;
        document.body.appendChild(loadingElement);
    }
    loadingElement.textContent = message;
    loadingElement.style.display = 'block';
}

// 隐藏加载状态
function hideLoading() {
    const loadingElement = document.getElementById('loading-indicator');
    if (loadingElement) {
        loadingElement.style.display = 'none';
    }
}

// 显示错误消息
function showError(message) {
    showNotification(message, 'error');
}

// 显示警告消息
function showWarning(message) {
    showNotification(message, 'warning');
}

// 显示成功消息
function showSuccess(message) {
    showNotification(message, 'success');
}

// 显示通知
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        border-radius: 4px;
        color: white;
        font-size: 14px;
        z-index: 10000;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
        animation: slideIn 0.3s ease-out;
    `;

    // 设置不同类型的样式
    switch (type) {
        case 'error':
            notification.style.backgroundColor = '#f44336';
            break;
        case 'warning':
            notification.style.backgroundColor = '#ff9800';
            break;
        case 'success':
            notification.style.backgroundColor = '#4caf50';
            break;
        default:
            notification.style.backgroundColor = '#2196f3';
    }

    notification.textContent = message;
    document.body.appendChild(notification);

    // 添加动画
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
    `;
    document.head.appendChild(style);

    // 3秒后自动消失
    setTimeout(() => {
        notification.style.animation = 'slideIn 0.3s ease-out reverse';
        setTimeout(() => {
            document.body.removeChild(notification);
            document.head.removeChild(style);
        }, 300);
    }, 3000);
}

// 定期更新基金数据
function startFundUpdateInterval() {
    // 清除现有的定时器
    if (fundUpdateInterval) {
        clearInterval(fundUpdateInterval);
    }

    // 根据交易时间设置不同的更新间隔
    function getUpdateInterval() {
        const now = new Date();
        const day = now.getDay();
        const hour = now.getHours();
        const isTradingTime = day >= 1 && day <= 5 && hour >= 9 && hour < 15;

        if (isTradingTime) {
            return 180000; // 交易时间每3分钟更新一次
        } else {
            return 1800000; // 非交易时间每30分钟更新一次
        }
    }

    // 初始设置更新间隔
    let interval = getUpdateInterval();

    fundUpdateInterval = setInterval(() => {
        loadFunds();

        // 重新计算更新间隔（如果时间发生变化）
        const newInterval = getUpdateInterval();
        if (newInterval !== interval) {
            clearInterval(fundUpdateInterval);
            interval = newInterval;
            fundUpdateInterval = setInterval(() => {
                loadFunds();
            }, interval);
        }
    }, interval);
}

function _sortFunds(funds) {
    // 持仓优先，持仓内按当日预估收益从高到低，未持仓按原顺序
    const hasBuy = f => {
        const s = getBuySettings(f.id);
        return s && s.shares > 0;
    };
    return [...funds].sort((a, b) => {
        const aHas = hasBuy(a), bHas = hasBuy(b);
        if (aHas && !bHas) return -1;
        if (!aHas && bHas) return 1;
        if (aHas && bHas) return (b.predicted_return || 0) - (a.predicted_return || 0);
        return 0;
    });
}

function renderFunds(funds) {
    // 建立 id→code 映射，供 investment-advice.js 止盈计算时查找买入记录
    window._fundIdCodeMap = {};
    funds.forEach(f => { if (f.id && f.code) window._fundIdCodeMap[String(f.id)] = f.code; });

    const container = document.getElementById('funds-container');
    container.innerHTML = '';

    // 更新 Group Count
    const groupCountElement = document.getElementById('group-count');
    if (groupCountElement) groupCountElement.textContent = funds.length;

    if (funds.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #888; padding: 20px;">No funds in this group. Add one to track.</p>';
        return;
    }

    // 应用排序
    const sortedFunds = _sortFunds(funds);
    sortedFunds.forEach(fund => {
        const fundItem = document.createElement('div');
        fundItem.className = 'fund-item';
        fundItem.id = `fund-${fund.id}`;
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
            // 公式：预估收益金额 = 上一个交易日的净值 * 预估收益率 * 份数
            // 确保使用正确的预测收益率
            const previousNetValue = fund.prices[fund.prices.length - 1];
            const predictedReturn = fund.predicted_return || 0;
            estimatedReturn = previousNetValue * predictedReturn * buySettings.shares;
        }

        // 计算预测准确性（与实际收益的对比）
        function calculatePredictionAccuracy(fund) {
            if (fund.returns && fund.returns.length > 1) {
                // 取最近的实际收益和预测收益进行对比
                const actualReturn = fund.returns[fund.returns.length - 1];
                const predictedReturn = fund.predicted_return || 0;
                const difference = Math.abs(actualReturn - predictedReturn);
                const accuracy = Math.max(0, 1 - difference / Math.max(Math.abs(actualReturn), 0.01)) * 100;
                return accuracy.toFixed(2);
            }
            return 'N/A';
        }

        // 获取预测置信度
        const confidence = fund.prediction_confidence || 0.5;

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

        // 计算上一个交易日的净值变化率
        let previousDayReturn = 0;
        if (fund.returns && fund.returns.length > 0) {
            let returnValue = fund.returns[fund.returns.length - 1];
            // 检查返回值是否已经是百分比形式（大于1或小于-1）
            if (Math.abs(returnValue) > 1) {
                // 如果是百分比形式，转换为小数
                previousDayReturn = returnValue / 100;
            } else {
                // 如果已经是小数形式，直接使用
                previousDayReturn = returnValue;
            }
        } else if (fund.prices && fund.prices.length >= 2) {
            previousDayReturn = (fund.prices[fund.prices.length - 1] - fund.prices[fund.prices.length - 2]) / fund.prices[fund.prices.length - 2];
        }

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
                    ${buySettings.shares <= 0 ? '<div class="fund-detail-box fund-no-holding"><span>暂未买入</span></div>' : ''}
                </div>
            </div>
            <div class="fund-performance">
                    <div class="fund-return-container">
                        <div class="fund-return ${previousDayReturn < 0 ? 'negative' : ''}">
                            ${previousDayReturn >= 0 ? '+' : ''}${(previousDayReturn * 100).toFixed(2)}%
                        </div>
                        <div class="fund-return-label">Previous Day</div>
                    </div>
                    <div class="fund-return-container">
                        <div class="fund-return ${fund.predicted_return < 0 ? 'negative' : ''}">
                            ${fund.predicted_return >= 0 ? '+' : ''}${(fund.predicted_return * 100).toFixed(2)}%
                        </div>
                        <div class="fund-return-label">Real-time Return</div>
                    </div>
                    <div class="fund-return-container">
                        <div class="fund-return" style="color: #4CAF50;">
                            ${(confidence * 100).toFixed(0)}%
                        </div>
                        <div class="fund-return-label">Confidence</div>
                    </div>
                    <div class="fund-return-container">
                        ${buySettings.shares > 0 ? `
                            <div class="fund-return ${estimatedReturn >= 0 ? '' : 'negative'}">
                                ${estimatedReturn >= 0 ? '+' : ''}${estimatedReturn.toFixed(2)}元
                            </div>
                        ` : `
                            <div class="fund-return" style="color:#555;">--</div>
                        `}
                        <div class="fund-return-label">Live Profit</div>
                    </div>
                </div>
        `;

        // 添加点击事件
        fundItem.addEventListener('click', function(e) {
            // 防止点击实时按钮时触发弹框
            if (!e.target.classList.contains('real-time-btn') && !e.target.closest('.real-time-btn')) {
                showFundDetails(fund);
            }
        });

        // 添加到容器
        container.appendChild(fundItem);
    });
}

// 防止重复提交的标志
let isAddingFund = false;

function addFund() {
    // 防止重复提交
    if (isAddingFund) {
        return;
    }

    const code = document.getElementById('fund-code').value;

    // 验证基金代码格式
    if (!/^\d{6}$/.test(code)) {
        showError('请输入有效的6位基金代码');
        return;
    }

    // 显示加载状态
    const addButton = document.querySelector('#add-fund-form button[type="submit"]');
    const originalText = addButton.textContent;
    addButton.textContent = '添加中...';
    addButton.disabled = true;
    isAddingFund = true;

    fetch('/api/funds', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ code })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        // 检查是否有错误
        if (data.error) {
            showError(data.error);
            return;
        }

        // 清除所有缓存（内存 + localStorage），确保下次渲染拿到最新数据
        cacheManager.clear('funds');
        cacheManager.clear('fundHoldings');
        try { localStorage.removeItem('funds'); } catch(e) {}

        // 直接从 API 拉最新列表（跳过缓存），拿到后立刻渲染
        return fetch('/api/funds')
            .then(r => {
                if (!r.ok) throw new Error(`HTTP ${r.status}`);
                return r.json();
            })
            .then(funds => {
                // 更新缓存和本地存储（供下次使用）
                cacheManager.set(CACHE_KEYS.FUNDS_LIST, funds, CACHE_EXPIRY.FUNDS_LIST);
                try { localStorage.setItem('funds', JSON.stringify(funds)); } catch(e) {}

                // 初始化新基金的持仓设置
                const defaultBuySettings = { date: new Date().toISOString().split('T')[0], shares: 0 };
                localStorage.setItem(`fundBuySettings_${data.id}`, JSON.stringify(defaultBuySettings));
                localStorage.setItem(`fundBuyRecords_${data.id}`, JSON.stringify([]));

                // 立即渲染，用户马上看到新基金
                return processFunds(funds);
            })
            .then(() => {
                document.getElementById('add-fund-form').reset();
                showSuccess('基金添加成功');
            });
    })
    .catch(error => {
        console.error('添加基金失败:', error);
        showError('添加基金失败，请稍后重试');
    })
    .finally(() => {
        // 恢复按钮状态
        setTimeout(() => {
            if (addButton) {
                addButton.textContent = originalText;
                addButton.disabled = false;
            }
            isAddingFund = false;
        }, 500); // 稍微延迟，确保用户能看到成功状态
    });
}

function deleteFund(id) {
    // 显示加载状态
    const deleteButton = event && event.target ? event.target : null;
    if (deleteButton) {
        deleteButton.textContent = '删除中...';
        deleteButton.disabled = true;
    }

    fetch(`/api/funds/${id}`, {
        method: 'DELETE'
    })
    .then(response => {
        if (response.status === 401) {
            // 未登录，重定向到登录页面
            window.location.href = '/login';
            return Promise.reject('未登录');
        }
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(() => {
        // 清除相关缓存
        cacheManager.clear('funds');
        cacheManager.clear('fundHoldings');

        // 重新加载基金数据
        loadFunds();

        // 重新加载设置页面中的基金管理数据
        const fundManagementContainer = document.querySelector('#fund-management');
        if (fundManagementContainer) {
            loadFundManagement(fundManagementContainer);
        }

        // 显示成功消息
        showSuccess('基金删除成功');
    })
    .catch(error => {
        console.error('删除基金失败:', error);
        if (error !== '未登录') {
            showError('删除基金失败，请稍后重试');
        }
    })
    .finally(() => {
        // 恢复按钮状态
        if (deleteButton) {
            deleteButton.textContent = '删除';
            deleteButton.disabled = false;
        }
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
    // 移动端：底部抽屉式弹出
    if (window.innerWidth <= 600) {
        modal.style.alignItems = 'flex-end';
    }

    // 弹框内容
    const modalContent = document.createElement('div');
    modalContent.className = 'modal-content';
    const isMobile = window.innerWidth <= 600;
    modalContent.style.cssText = isMobile ? `
        background-color: #121212;
        border-radius: 16px 16px 0 0;
        width: 100%;
        max-width: 100%;
        max-height: 92vh;
        overflow: hidden;
        box-shadow: 0 -4px 24px rgba(0, 0, 0, 0.7);
        border: 1px solid #2a2a2a;
        border-bottom: none;
        display: flex;
        flex-direction: column;
    ` : `
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
        <div style="background:#1a1a1a; border-bottom:1px solid #2a2a2a;">
            <div style="padding:14px 18px 0;">
                <div style="font-size:16px;font-weight:600;color:#fff;line-height:1.3;margin-bottom:3px;">${fund.name}</div>
                <div style="font-size:11px;color:#555;margin-bottom:14px;">${fund.code} &nbsp;·&nbsp; NAV ${fund.prices[fund.prices.length - 1]}</div>
            </div>
            <div style="display:flex; border-top:1px solid #2a2a2a;">
                <button class="tab-btn active" data-tab="details" style="flex:1;padding:10px 0;border:none;background:transparent;color:#4a9eff;cursor:pointer;font-size:13px;font-weight:600;border-bottom:2px solid #4a9eff;letter-spacing:.5px;">详情</button>
                <button class="tab-btn" data-tab="decision" style="flex:1;padding:10px 0;border:none;background:transparent;color:#666;cursor:pointer;font-size:13px;border-bottom:2px solid transparent;letter-spacing:.5px;">决策</button>
                <button class="tab-btn" data-tab="holding" style="flex:1;padding:10px 0;border:none;background:transparent;color:#666;cursor:pointer;font-size:13px;border-bottom:2px solid transparent;letter-spacing:.5px;">持仓</button>
            </div>
        </div>
        
        <!-- 标签内容 -->
        <div style="flex: 1; overflow-y: auto; padding: 0;">
            <!-- 详情标签 -->
            <div id="details-tab" class="tab-content" style="display: block;">
                <!-- 时间范围 -->
                <div style="display: flex; justify-content: flex-end; gap: 2px; padding: 10px 20px; background-color: #1e1e1e; border-bottom: 1px solid #333;">
                    <button class="time-btn active" data-days="7">7D</button>
                    <button class="time-btn" data-days="30">1M</button>
                    <button class="time-btn" data-days="90">3M</button>
                    <button class="time-btn" data-days="180">6M</button>
                    <button class="time-btn" data-days="365">1Y</button>
                    <button class="time-btn" data-days="0">ALL</button>
                </div>
                
                <!-- 趋势图 -->
                <div style="height: 350px; background-color: #000000; border-bottom: 1px solid #333; margin-bottom: 20px;">
                    <canvas id="${chartId}"></canvas>
                </div>
                
                <!-- 技术指标 -->
                <div style="height: 300px; background-color: #000000; border-bottom: 1px solid #333;">
                    <canvas id="${chartId}-tech"></canvas>
                </div>
                
                <!-- 持仓股票 -->
                <div style="padding: 10px 20px; border-bottom: 1px solid #333;">
                    <h3 style="color: #e0e0e0; margin-bottom: 10px; font-size: 14px; white-space: nowrap;">持仓股票</h3>
                    <div id="stock-holdings" style="background-color: #2a2a2a; border-radius: 4px; padding: 14px; border: 1px solid #333;">
                        <div style="font-size: 12px; color: #aaa;">加载中...</div>
                    </div>
                </div>
            </div>
            
            <!-- 决策标签 -->
            <div id="decision-tab" class="tab-content" style="display: none;">
                <!-- 基金风险评估 -->
                <div style="padding: 10px 20px;">
                    <h3 style="color: #e0e0e0; margin-bottom: 15px; font-size: 14px; ">基金风险评估</h3>
                    <div style="background-color: #2a2a2a; border-radius: 4px; padding: 18px; border: 1px solid #333;">
                        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px 24px; margin-bottom: 15px;" class="data-grid-3">
                            <div style="font-size:12px;line-height:1.6;"><span style="color:#666;font-size:11px;">当前净值</span><br><span style="color:#e0e0e0;font-weight:500;">${fund.prices && fund.prices.length > 0 ? fund.prices[fund.prices.length - 1] : '数据不足'}</span></div>
                            <div style="font-size:12px;line-height:1.6;"><span style="color:#666;font-size:11px;">RSI指标</span><br><span style="color:#e0e0e0;font-weight:500;">${fund.rsi ? fund.rsi.toFixed(2) + ' ' + getRSIMessage(fund.rsi) : '数据不足'}</span></div>
                            <div style="font-size:12px;line-height:1.6;"><span style="color:#666;font-size:11px;">波动率</span><br><span style="color:#e0e0e0;font-weight:500;">${fund.volatility ? (fund.volatility * 100).toFixed(2) + '%' : '数据不足'}</span></div>
                            <div style="font-size:12px;line-height:1.6;"><span style="color:#666;font-size:11px;">预测当日收益率</span><br><span class="return-value ${fund.predicted_return >= 0 ? 'positive' : 'negative'}">${fund.predicted_return ? (fund.predicted_return >= 0 ? '+' : '') + (fund.predicted_return * 100).toFixed(2) + '%' : '数据不足'}</span></div>
                            <div style="font-size:12px;line-height:1.6;"><span style="color:#666;font-size:11px;">预测置信度</span><br><span style="color:#e0e0e0;font-weight:500;">${fund.prediction_confidence ? (fund.prediction_confidence * 100).toFixed(0) + '%' : '数据不足'}</span></div>
                            <div style="font-size:12px;line-height:1.6;"><span style="color:#666;font-size:11px;">ATR指标</span><br><span style="color:#e0e0e0;font-weight:500;">${fund.atr ? fund.atr.toFixed(4) : '数据不足'}</span></div>
                        </div>
                        <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #333;">
                            <h4 style="color: #e0e0e0; margin: 0 0 12px 0; font-size: 13px; ">技术指标分析</h4>
                            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px 24px; font-size: 12px;" class="data-grid-3">
                                ${(() => {
                                    // 计算MACD信号
                                    let macdSignal = '数据不足';
                                    let macdSignalColor = '#aaa';
                                    
                                    if (fund.macd) {
                                        const [macdLine, signalLine, histogram] = fund.macd;
                                        if (macdLine > signalLine) {
                                            if (histogram > 0) {
                                                macdSignal = '金叉看多';
                                                macdSignalColor = '#4caf50';
                                            } else {
                                                macdSignal = '金叉初期';
                                                macdSignalColor = '#8bc34a';
                                            }
                                        } else {
                                            if (histogram < 0) {
                                                macdSignal = '死叉看空';
                                                macdSignalColor = '#ff4444';
                                            } else {
                                                macdSignal = '死叉初期';
                                                macdSignalColor = '#ff8a80';
                                            }
                                        }
                                    }
                                    
                                    return `<div style=""><strong>MACD信号:</strong> <span style="color: ${macdSignalColor};">${macdSignal}</span></div>`;
                                })()}
                                ${(() => {
                                    // 计算KDJ信号
                                    let kdjSignal = '数据不足';
                                    let kdjSignalColor = '#aaa';
                                    
                                    if (fund.kdj) {
                                        const [k, d, j] = fund.kdj;
                                        if (j > 80) {
                                            kdjSignal = '超买';
                                            kdjSignalColor = '#ff4444';
                                        } else if (j < 20) {
                                            kdjSignal = '超卖';
                                            kdjSignalColor = '#4caf50';
                                        } else if (j > 50) {
                                            kdjSignal = '多头';
                                            kdjSignalColor = '#8bc34a';
                                        } else {
                                            kdjSignal = '空头';
                                            kdjSignalColor = '#ff8a80';
                                        }
                                    }
                                    
                                    return `<div style=""><strong>KDJ信号:</strong> <span style="color: ${kdjSignalColor};">${kdjSignal}</span></div>`;
                                })()}
                                ${(() => {
                                    // 计算布林带信号
                                    let bollingerSignal = '数据不足';
                                    let bollingerSignalColor = '#aaa';
                                    
                                    if (fund.bollinger_bands && fund.prices && fund.prices.length > 0) {
                                        const [upperBand, ma, lowerBand] = fund.bollinger_bands;
                                        const currentPrice = fund.prices[fund.prices.length - 1];
                                        if (currentPrice > upperBand) {
                                            bollingerSignal = '突破上轨';
                                            bollingerSignalColor = '#4caf50';
                                        } else if (currentPrice < lowerBand) {
                                            bollingerSignal = '突破下轨';
                                            bollingerSignalColor = '#ff4444';
                                        } else if (currentPrice > ma) {
                                            bollingerSignal = '中轨之上';
                                            bollingerSignalColor = '#8bc34a';
                                        } else {
                                            bollingerSignal = '中轨之下';
                                            bollingerSignalColor = '#ff8a80';
                                        }
                                    }
                                    
                                    return `<div style=""><strong>布林带位置:</strong> <span style="color: ${bollingerSignalColor};">${bollingerSignal}</span></div>`;
                                })()}
                            </div>
                        </div>
                        <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #333;">
                            <h4 style="color: #e0e0e0; margin: 0 0 12px 0; font-size: 13px; ">风险评估</h4>
                            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px 24px; font-size: 12px;" class="data-grid-3">
                                <div style=""><strong>RSI风险:</strong> <span style="color: ${fund.rsi ? (fund.rsi > 70 ? '#ff4444' : fund.rsi < 30 ? '#4caf50' : '#ff9800') : '#aaa'}">${fund.rsi ? (fund.rsi > 70 ? '高' : fund.rsi < 30 ? '低' : '中') : '数据不足'}</span></div>
                                <div style=""><strong>波动率风险:</strong> <span style="color: ${fund.volatility ? (fund.volatility > 0.2 ? '#ff4444' : fund.volatility > 0.1 ? '#ff9800' : '#4caf50') : '#aaa'}">${fund.volatility ? (fund.volatility > 0.2 ? '高' : fund.volatility > 0.1 ? '中' : '低') : '数据不足'}</span></div>
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
                                    
                                    return `<div style=""><strong>趋势风险:</strong> <span style="color: ${trendRiskColor};">${trendRisk}</span></div>`;
                                })()}
                                <div style=""><strong>流动性风险:</strong> <span style="color: #ff9800;">中</span></div>
                                <div style=""><strong>市场风险:</strong> <span style="color: ${fund.volatility && fund.volatility > 0.15 ? '#ff9800' : '#4caf50'}">${fund.volatility && fund.volatility > 0.15 ? '中' : '低'}</span></div>
                                ${(() => {
                                    // 计算整体风险
                                    let overallRisk = '数据不足';
                                    let overallRiskColor = '#aaa';
                                    
                                    // 计算布林带数据
                                    const bollingerBands = calculateBollingerBands(fund.prices);
                                    const latestPrice = fund.prices && fund.prices.length > 0 ? fund.prices[fund.prices.length - 1] : 0;
                                    const latestUpperBand = bollingerBands.upper[bollingerBands.upper.length - 1];
                                    const latestLowerBand = bollingerBands.lower[bollingerBands.lower.length - 1];
                                    const latestMiddleBand = bollingerBands.middle[bollingerBands.middle.length - 1];
                                    
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
                                        
                                        // 布林带风险评分
                                        if (latestPrice && latestUpperBand && latestLowerBand) {
                                            if (latestPrice > latestUpperBand) riskScore += 2; // 突破上轨，风险增加
                                            else if (latestPrice < latestLowerBand) riskScore += 1; // 突破下轨，风险降低
                                        }
                                        
                                        // 综合判断
                                        if (riskScore >= 6) {
                                            overallRisk = '高';
                                            overallRiskColor = '#ff4444';
                                        } else if (riskScore >= 4) {
                                            overallRisk = '中';
                                            overallRiskColor = '#ff9800';
                                        } else {
                                            overallRisk = '低';
                                            overallRiskColor = '#4caf50';
                                        }
                                    }
                                    
                                    return `<div style=""><strong>整体风险:</strong> <span style="color: ${overallRiskColor};">${overallRisk}</span></div>`;
                                })()}
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- 智能决策 -->
                <div style="padding: 10px 20px;">
                    <h3 style="color: #e0e0e0; margin-bottom: 15px; font-size: 14px; ">智能决策</h3>
                    <div style="background-color: #2a2a2a; border-radius: 4px; padding: 18px; border: 1px solid #333;">
                        <div style="font-size: 12px; line-height: 1.8; color: #e0e0e0;">
                            ${(() => {
                                const pr  = fund.predicted_return || 0;
                                const rsi = fund.rsi || 50;
                                const bb  = calculateBollingerBands(fund.prices);
                                const nav = fund.prices && fund.prices.length ? fund.prices[fund.prices.length - 1] : 0;
                                const bbU = bb.upper && bb.upper.length ? bb.upper[bb.upper.length - 1] : 0;
                                const bbL = bb.lower && bb.lower.length ? bb.lower[bb.lower.length - 1] : 0;
                                const bbM = bb.middle && bb.middle.length ? bb.middle[bb.middle.length - 1] : 0;

                                // ── 主判断：以 predicted_return 为核心（与投资建议统一）──────────
                                // predicted_return 有实时估值时 = gszzl（最准），无时 = 技术面信号
                                let action = '持有';
                                let actionColor = '#ffc107';
                                let actionDetail = '';

                                if (pr > 0.02) {
                                    action = '补仓';
                                    actionColor = '#dc3545';
                                    actionDetail = '今日预估收益率 +' + (pr*100).toFixed(2) + '%，趋势向上，可适量加仓以扩大收益。';
                                } else if (pr < -0.02) {
                                    action = '减仓';
                                    actionColor = '#28a745';
                                    actionDetail = '今日预估收益率 ' + (pr*100).toFixed(2) + '%，趋势向下，建议控制仓位，等待企稳。';
                                } else if (pr > 0) {
                                    action = '持有';
                                    actionColor = '#ffc107';
                                    actionDetail = '今日预估收益率 +' + (pr*100).toFixed(2) + '%，涨幅温和，建议持有观察。';
                                } else {
                                    action = '观望';
                                    actionColor = '#ffc107';
                                    actionDetail = '今日预估收益率 ' + (pr*100).toFixed(2) + '%，短期承压，建议维持仓位等待信号。';
                                }

                                // ── 技术面风险提示（不改变主结论，仅作补充说明）─────────────────
                                const risks = [];
                                if (rsi > 70) risks.push('RSI=' + rsi.toFixed(1) + ' 处于超买区间，短期注意回调风险');
                                if (rsi < 30) risks.push('RSI=' + rsi.toFixed(1) + ' 处于超卖区间，存在反弹机会');
                                if (nav && bbU && nav > bbU) risks.push('净值突破布林带上轨（' + bbU.toFixed(4) + '），短线偏强但需警惕回踩');
                                if (nav && bbL && nav < bbL) risks.push('净值跌破布林带下轨（' + bbL.toFixed(4) + '），技术面超卖');

                                const riskTip = risks.length > 0
                                    ? '<p style="margin-top:10px;color:#aaa;">⚠ 风险提示：' + risks.join('；') + '。</p>'
                                    : '';

                                // ── 数据说明：告知用户本结论用的是实时还是历史数据 ───────────────
                                const dataTip = pr !== 0
                                    ? '<p style="margin-top:8px;color:#555;font-size:11px;">* 主结论基于今日实时预估净值，与投资建议页保持一致。技术指标为昨日收盘数据，仅供参考。</p>'
                                    : '<p style="margin-top:8px;color:#555;font-size:11px;">* 今日无实时估值（非交易时段），主结论基于技术指标历史信号，仅供参考。</p>';

                                return (
                                    '<p><strong>操作建议：</strong>' +
                                    '<span style="color:' + actionColor + ';font-weight:700;font-size:14px;margin:0 6px;">' + action + '</span> ' +
                                    actionDetail + '</p>' +
                                    riskTip +
                                    dataTip
                                );
                            })()}
                        </div>
                    </div>
                </div>
                
                <!-- 势头信号和智能操作建议 -->
                <div style="padding: 10px 20px;">
                    <h3 style="color: #e0e0e0; margin-bottom: 15px; font-size: 14px; ">势头信号</h3>
                    <div style="background-color: #2a2a2a; border-radius: 4px; padding: 18px; border: 1px solid #333;">
                        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;">
                            <div>
                                <div style="font-size: 13px; color: #e0e0e0; margin-bottom: 12px;"><strong>趋势方向</strong></div>
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
                                            <span style="margin-right: 6px; flex-shrink:0;">${trendIcon}</span> ${trendSignal}
                                        </div>
                                        <div style="font-size: 11px; color: #aaa; line-height: 1.4;">
                                            ${trendDesc}
                                        </div>
                                    `;
                                })()}
                            </div>
                            <div>
                                <div style="font-size: 13px; color: #e0e0e0; margin-bottom: 12px;"><strong>支撑位/阻力位</strong></div>
                                ${(() => {
                                    if (fund.prices && fund.prices.length > 0) {
                                        const minPrice = Math.min(...fund.prices);
                                        const maxPrice = Math.max(...fund.prices);
                                        const currentPrice = fund.prices[fund.prices.length - 1];
                                        const supportRate = ((currentPrice / minPrice - 1) * 100).toFixed(1);
                                        const resistanceRate = ((maxPrice / currentPrice - 1) * 100).toFixed(1);
                                        const supportColor = supportRate >= 0 ? '#ff4444' : '#4caf50';
                                        const resistanceColor = resistanceRate >= 0 ? '#4caf50' : '#ff4444';
                                        
                                        return `
                                            <div style="font-size: 11px; color: #e0e0e0; margin-bottom: 8px; ">
                                                支撑位: ${minPrice.toFixed(4)} <span style="color: ${supportColor};">(${supportRate >= 0 ? '+' : ''}${supportRate}%)</span>
                                            </div>
                                            <div style="font-size: 11px; color: #e0e0e0; ">
                                                阻力位: ${maxPrice.toFixed(4)} <span style="color: ${resistanceColor};">(-${resistanceRate}%)</span>
                                            </div>
                                        `;
                                    } else {
                                        return `
                                            <div style="font-size: 11px; color: #e0e0e0; margin-bottom: 8px; ">
                                                数据不足
                                            </div>
                                        `;
                                    }
                                })()}
                            </div>
                            <div>
                                <div style="font-size: 13px; color: #e0e0e0; margin-bottom: 12px;"><strong>智能操作建议</strong></div>
                                ${(() => {
                                    // 基于RSI、预测收益率和市场环境生成操作建议
                                    let advice = '';
                                    let adviceColor = '';
                                    let adviceDesc = '';
                                    
                                    // 计算市场环境影响
                                    let marketImpact = 0;
                                    let marketDesc = '';
                                    if (fund.market_data) {
                                        const indices = fund.market_data.indices || {};
                                        const indexChanges = Object.values(indices).map(index => index.change_ratio || 0);
                                        if (indexChanges.length > 0) {
                                            const avgIndexChange = indexChanges.reduce((sum, change) => sum + change, 0) / indexChanges.length;
                                            marketImpact = avgIndexChange;
                                            if (avgIndexChange > 0.01) {
                                                marketDesc = '大盘强势上涨，有利于基金表现';
                                            } else if (avgIndexChange < -0.01) {
                                                marketDesc = '大盘明显下跌，可能拖累基金表现';
                                            } else {
                                                marketDesc = '大盘震荡，对基金影响中性';
                                            }
                                        }
                                    }
                                    
                                    // 综合判断
                                    if (fund.rsi > 70) {
                                        advice = 'RSI过热, 建议止盈';
                                        adviceColor = '#ff4444';
                                        adviceDesc = 'RSI过高，建议止盈';
                                    } else if (fund.rsi < 30) {
                                        advice = 'RSI超卖, 建议买入';
                                        adviceColor = '#4caf50';
                                        adviceDesc = 'RSI过低，建议买入';
                                    } else if (fund.predicted_return > 0.01) {
                                        advice = '看涨信号, 建议持有';
                                        adviceColor = '#4caf50';
                                        adviceDesc = '预测上涨，建议持有';
                                    } else if (fund.predicted_return < -0.01) {
                                        advice = '看跌信号, 建议减仓';
                                        adviceColor = '#ff4444';
                                        adviceDesc = '预测下跌，建议减仓';
                                    } else {
                                        advice = '震荡行情, 建议观望';
                                        adviceColor = '#ff9800';
                                        adviceDesc = '建议观望';
                                    }
                                    
                                    // 结合市场环境调整建议
                                    if (marketImpact > 0.01 && fund.predicted_return < 0) {
                                        advice = '谨慎看跌, 建议观望';
                                        adviceColor = '#ff9800';
                                        adviceDesc = '大盘上涨，建议观望';
                                    } else if (marketImpact < -0.01 && fund.predicted_return > 0) {
                                        advice = '谨慎看涨, 建议轻仓';
                                        adviceColor = '#ff9800';
                                        adviceDesc = '大盘下跌，建议轻仓';
                                    }
                                    
                                    return `
                                        <div style="font-size: 12px; color: ${adviceColor}; display: flex; align-items: center; margin-bottom: 8px;">
                                            <span style="margin-right: 6px;">●</span> ${advice}
                                        </div>
                                        <div style="font-size: 11px; color: #aaa; line-height: 1.4;">
                                            ${marketDesc ? marketDesc : adviceDesc}
                                        </div>
                                    `;
                                })()}
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- 市场环境分析 -->
                <div style="padding: 10px 20px; margin-top: 10px;">
                    <h3 style="color: #e0e0e0; margin-bottom: 15px; font-size: 14px; ">市场环境分析</h3>
                    ${(() => {
                        if (fund.market_data) {
                            const indices = fund.market_data.indices || {};
                            const sectors = fund.market_data.sectors || {};
                            
                            if (Object.keys(indices).length > 0 || Object.keys(sectors).length > 0) {
                                return `
                                    <div style="background-color: #2a2a2a; border-radius: 4px; padding: 18px; border: 1px solid #333;">
                                        ${Object.keys(indices).length > 0 ? `
                                            <div style="margin-bottom: 15px;">
                                                <h4 style="color: #e0e0e0; margin: 0 0 10px 0; font-size: 13px;">大盘指数</h4>
                                                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; font-size: 11px;">
                                                    ${Object.entries(indices).map(([name, data]) => {
                                                        const changePercent = (data.change_ratio * 100).toFixed(2);
                                                        const changeColor = data.change_ratio >= 0 ? '#ff4444' : '#4caf50';
                                                        return `
                                                            <div style="">
                                                                <strong>${name}:</strong> ${data.current_price ? data.current_price.toFixed(2) : '0.00'} 
                                                                <span style="color: ${changeColor};">
                                                                    (${data.change_ratio >= 0 ? '+' : ''}${changePercent}%)
                                                                </span>
                                                            </div>
                                                        `;
                                                    }).join('')}
                                                </div>
                                            </div>
                                        ` : ''}
                                        ${Object.keys(sectors).length > 0 ? `
                                            <div>
                                                <h4 style="color: #e0e0e0; margin: 0 0 10px 0; font-size: 13px;">行业板块</h4>
                                                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; font-size: 11px;">
                                                    ${Object.entries(sectors).map(([name, data]) => {
                                                        const changePercent = (data.change_ratio * 100).toFixed(2);
                                                        const changeColor = data.change_ratio >= 0 ? '#ff4444' : '#4caf50';
                                                        return `
                                                            <div style="">
                                                                <strong>${name}:</strong> ${data.current_price ? data.current_price.toFixed(2) : '0.00'} 
                                                                <span style="color: ${changeColor};">
                                                                    (${data.change_ratio >= 0 ? '+' : ''}${changePercent}%)
                                                                </span>
                                                            </div>
                                                        `;
                                                    }).join('')}
                                                </div>
                                            </div>
                                        ` : ''}
                                    </div>
                                `;
                            }
                        }
                        return '<div style="color: #aaa; font-size: 12px;">市场数据获取中...</div>';
                    })()}
                </div>
            </div>
            
            <!-- 持仓标签 -->
            <div id="holding-tab" class="tab-content" style="display: none;">
                <!-- 我的持仓 -->
                <div style="padding: 10px 20px; border-bottom: 1px solid #333;">
                    <h3 style="color: #e0e0e0; margin-bottom: 10px; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">我的持仓 (持仓: <span id="total-shares">${buySettings.shares}</span>份，平均净值: <span id="avg-nav">0.0000</span>元)</h3>
                    <div style="background-color: #2a2a2a; border-radius: 4px; padding: 14px; border: 1px solid #333;">
                        <div id="buy-records-content" style="font-size: 12px;">
                            加载中...
                        </div>
                    </div>
                </div>
                
                <!-- 买卖操作 -->
                <div style="padding: 10px 20px;">
                    <h3 style="color: #e0e0e0; margin-bottom: 10px; font-size: 14px;">买卖操作</h3>
                    <div style="background-color: #2a2a2a; border-radius: 4px; padding: 14px; border: 1px solid #333;">
                        <div style="display: grid; grid-template-columns: minmax(0,1.4fr) minmax(0,1fr); gap: 10px; font-size: 12px;">
                            <div style="min-width: 0;">
                                <label style="display: block; margin-bottom: 6px; color: #888; font-size: 11px; letter-spacing:.4px;">操作日期</label>
                                <input type="date" id="buy-date" value="${new Date().toISOString().split('T')[0]}" style="width:100%;box-sizing:border-box;background-color:#333;color:#e0e0e0;border:1px solid #444;padding:10px 8px;border-radius:6px;font-size:13px;-webkit-appearance:none;appearance:none;">
                            </div>
                            <div style="min-width: 0;">
                                <label style="display: block; margin-bottom: 6px; color: #888; font-size: 11px; letter-spacing:.4px;">份数 <span style="color:#555;font-size:10px;">（负数卖出）</span></label>
                                <input type="number" id="buy-shares" value="0" inputmode="numeric" style="width:100%;box-sizing:border-box;background-color:#333;color:#e0e0e0;border:1px solid #444;padding:10px 8px;border-radius:6px;font-size:13px;">
                            </div>
                        </div>
                        <button id="save-buy-settings" style="margin-top: 16px; width:100%; background-color: #007bff; color: white; border: none; padding: 14px 0; border-radius: 8px; cursor: pointer; font-size: 15px; font-weight:600; letter-spacing:.3px;">确认</button>
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
            // 清除股票更新定时器
            clearStockUpdateInterval(fund.code);
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
                b.style.color = '#666';
                b.style.fontWeight = 'normal';
                b.style.borderBottom = '2px solid transparent';
            });
            this.style.color = '#4a9eff';
            this.style.fontWeight = '600';
            this.style.borderBottom = '2px solid #4a9eff';

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
            let buyOnlyShares = 0; // 仅累计买入份数，用于计算平均成本
            buyRecords.forEach((record, index) => {
                const isSell = record.shares < 0;
                const action = isSell ? '卖出' : '买入';
                const actionColor = isSell ? '#4caf50' : '#e0e0e0';
                const sharesAbs = Math.abs(record.shares);
                recordsHTML += `<p style="display:flex;align-items:center;padding:4px 0;border-bottom:1px solid #1e1e1e;gap:6px;">
                    <span style="color:${actionColor};font-size:11px;min-width:28px;">${action}</span>
                    <span style="color:#888;font-size:11px;">${record.date}</span>
                    <span style="color:#e0e0e0;">${sharesAbs}份</span>
                    <span style="color:#666;font-size:11px;">@${record.nav}元</span>
                    <span class="delete-record" data-index="${index}" style="cursor:pointer;color:#ff4444;margin-left:auto;opacity:0;transition:opacity 0.2s;font-size:11px;">✕</span>
                </p>`;
                totalShares += record.shares;
                if (!isSell) {
                    totalAmount += record.shares * record.nav; // 卖出不计入成本
                    buyOnlyShares += record.shares; // 仅买入份数累计
                }
            });
            buyRecordsContent.innerHTML = recordsHTML;
            totalSharesElement.textContent = totalShares;
            // 平均持仓成本 = 买入总金额 ÷ 买入总份数（不含卖出）
            const avgNav = buyOnlyShares > 0 ? totalAmount / buyOnlyShares : 0;
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

    // 删除买入记录（同步删云端）
    async function deleteBuyRecord(fundId, index) {
        const records = getBuyRecords(fundId);
        if (index < 0 || index >= records.length) return;
        const record = records[index];
        // 先删本地
        records.splice(index, 1);
        localStorage.setItem(`fundBuyRecords_${fundId}`, JSON.stringify(records));
        // 再删云端（用云端 id）
        if (record.id) {
            try {
                await fetch(`/api/buy_records/${record.id}`, { method: 'DELETE' });
                _buyRecordsCache = null;
                fetchAllBuyRecords(true).then(r => { if (r) window._cloudBuyRecords = r; });
            } catch(e) {
                console.warn('云端删除失败:', e);
            }
        }
        // 同步更新 settings
        const remaining = records.reduce((s, r) => s + r.shares, 0);
        localStorage.setItem(`fundBuySettings_${fundId}`, JSON.stringify({
            date: new Date().toISOString().split('T')[0],
            shares: Math.max(0, remaining)
        }));
    }



    // 初始加载买入记录
    loadBuyRecords();

    // 保存买入设置
    modal.querySelector('#save-buy-settings').addEventListener('click', function() {
        const buyDate = document.getElementById('buy-date').value;
        const buyShares = parseInt(document.getElementById('buy-shares').value) || 0;

        if (buyShares !== 0) {
            // 默认使用最新净值，下方会尝试从历史数据查找对应日期净值
            let buyNav = fund.prices[fund.prices.length - 1];

            // 尝试从历史数据中查找对应日期的净值
            if (fund.dates && fund.prices) {
                for (let i = 0; i < fund.dates.length; i++) {
                    if (fund.dates[i] === buyDate) {
                        buyNav = fund.prices[i];
                        break;
                    }
                }
            }

            // 保存买入记录的函数
            async function saveBuyRecordWithNav(nav) {
                const isSell = buyShares < 0;
                const buyRecord = {
                    date: buyDate,
                    shares: buyShares,          // 负数 = 卖出
                    nav: nav,
                    fund_id: String(fund.id),
                    fund_code: fund.code,
                    fund_name: fund.name,
                    amount: buyShares * nav,    // 负数 = 卖出金额
                    note: isSell ? '卖出' : '买入',
                };
                await saveBuyRecord(fund.id, buyRecord);

                // 重新计算累计持仓
                const allRecords = getBuyRecords(fund.id);
                const totalShares = allRecords.reduce((sum, r) => sum + r.shares, 0);

                // 更新持仓设置
                const buySettings = { date: buyDate, shares: Math.max(0, totalShares) };
                localStorage.setItem(`fundBuySettings_${fund.id}`, JSON.stringify(buySettings));

                // 刷新云端缓存
                fetchAllBuyRecords(true).then(records => {
                    if (records) window._cloudBuyRecords = records;
                });

                // 重新加载记录列表
                loadBuyRecords();

                // 清空表单
                document.getElementById('buy-date').value = new Date().toISOString().split('T')[0];
                document.getElementById('buy-shares').value = 0;

                const msg = isSell ? `卖出 ${Math.abs(sellShares)} 份已记录` : `买入 ${buyShares} 份已记录`;
                alert(msg);

                // 重新渲染基金列表（更新 Live Profit 和排序）
                loadFunds();
            }

            // 确保净值数据的一致性，无论线上还是本地环境
            // 当找不到对应日期的净值时，使用后端API获取该日期的净值
            if (buyNav === fund.prices[fund.prices.length - 1] && buyDate !== fund.dates[fund.dates.length - 1]) {
                // 尝试从后端API获取历史净值
                fetch(`/api/funds/${fund.code}/nav?date=${buyDate}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.nav) {
                            buyNav = data.nav;
                        } else if (data.error) {
                            console.warn(`获取历史净值失败: ${data.error}`);
                            // 不尝试使用其他API，保持后端数据一致性
                        }
                        saveBuyRecordWithNav(buyNav);
                    })
                    .catch(error => {
                        console.error('获取历史净值失败:', error);
                        // 不尝试使用其他API，保持后端数据一致性
                        saveBuyRecordWithNav(buyNav);
                    });
            } else {
                saveBuyRecordWithNav(buyNav);
            }
        } else {
            alert('请输入有效的买入份数');
        }
    });

    // 时间范围按钮
    const timeBtns = modal.querySelectorAll('.time-btn');

    // 初始化基金的时间周期
    if (!fundTimeRange[fund.code]) {
        fundTimeRange[fund.code] = 7; // 默认7天
    }

    // 更新按钮样式的函数
    function updateTimeBtnStyles() {
        timeBtns.forEach(btn => {
            const btnDays = parseInt(btn.getAttribute('data-days'));
            const isActive = btnDays === fundTimeRange[fund.code];

            if (isActive) {
                btn.classList.add('active');
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
                btn.classList.remove('active');
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
            const days = parseInt(this.getAttribute('data-days'));
            // 保存选择的时间周期
            fundTimeRange[fund.code] = days;
            // 更新按钮样式
            updateTimeBtnStyles();
            // 更新图表
            updateChart(fund, chartId, days);
        });
    });

    // 添加涨跌颜色样式
    const style = document.createElement('style');
    style.textContent = `
        .positive { color: #ff4444; }
        .negative { color: #4CAF50; }
        .bg-red { background-color: rgba(255, 68, 68, 0.2); }
        .bg-green { background-color: rgba(76, 175, 80, 0.2); }
        .border-red { border-color: #ff4444; background-color: rgba(255, 68, 68, 0.1); }
        .border-green { border-color: #4CAF50; background-color: rgba(76, 175, 80, 0.1); }
        .return-value { font-weight: bold; }
    `;
    modalContent.appendChild(style);

    // 初始化图表，使用保存的时间周期
    updateChart(fund, chartId, fundTimeRange[fund.code]);

    // 加载持仓股票数据
    loadStockHoldings(fund.code);
}

// 股票持仓数据缓存
const stockHoldingsCache = {};
let stockUpdateIntervals = {}; // 存储每个基金的更新定时器

// 存储每个基金的当前时间周期选择
const fundTimeRange = {};

// 根据交易时间获取缓存过期时间
function getStockHoldingsCacheExpiry() {
    const now = new Date();
    const hour = now.getHours();
    const minute = now.getMinutes();
    const dayOfWeek = now.getDay();

    // 周一到周五，9:30-11:30 和 13:00-15:00 为交易时间
    const isTradingTime = dayOfWeek >= 1 && dayOfWeek <= 5 &&
                        ((hour === 9 && minute >= 30) || (hour === 10) || (hour === 11 && minute < 30) ||
                        (hour === 13) || (hour === 14) || (hour === 15 && minute === 0));

    return isTradingTime ? 15 : 28800; // 交易时间15秒，非交易时间8小时
}

// 检查是否在开市时间内
function isTradingTime() {
    const now = new Date();
    const hour = now.getHours();
    const minute = now.getMinutes();
    const dayOfWeek = now.getDay();

    // 周一到周五，9:30-11:30 和 13:00-15:00
    if (dayOfWeek >= 1 && dayOfWeek <= 5) {
        if ((hour === 9 && minute >= 30) || (hour === 10) || (hour === 11 && minute < 30) ||
            (hour === 13) || (hour === 14) || (hour === 15 && minute === 0)) {
            return true;
        }
    }
    return false;
}

// 加载基金持仓股票数据
function loadStockHoldings(fundCode) {
    const stockHoldingsElement = document.getElementById('stock-holdings');

    // 检查缓存
    const cacheKey = `stock_holdings_${fundCode}`;
    const currentTime = Date.now() / 1000;
    const cacheExpiry = getStockHoldingsCacheExpiry();

    if (stockHoldingsCache[cacheKey] && (currentTime - stockHoldingsCache[cacheKey].timestamp) < cacheExpiry) {
        const cachedData = stockHoldingsCache[cacheKey].data;

        // 更新标题为"股票持仓 (X%)"
        const stockRatio = cachedData.stock_ratio ? cachedData.stock_ratio.toFixed(1) : 0;
        const titleElement = stockHoldingsElement.parentElement.querySelector('h3');
        if (titleElement) {
            titleElement.textContent = `股票持仓 (${stockRatio}%)`;
        }

        // 渲染数据
        renderStockHoldings(cachedData, stockHoldingsElement, false);

        // 设置自动更新
        setupStockUpdateInterval(fundCode);
        return;
    }

    // 显示加载中状态
    stockHoldingsElement.innerHTML = '<div style="font-size: 12px; color: #aaa; padding: 20px; text-align: center;">加载中...</div>';

    // 从API获取持仓股票数据
    fetch(`/api/funds/${fundCode}/holdings`)
        .then(response => response.json())
        .then(data => {

            // 存储到缓存
            stockHoldingsCache[cacheKey] = {
                timestamp: currentTime,
                data: data
            };

            // 更新标题为"股票持仓 (X%)"
            const stockRatio = data.stock_ratio ? data.stock_ratio.toFixed(1) : 0;
            const titleElement = stockHoldingsElement.parentElement.querySelector('h3');
            if (titleElement) {
                titleElement.textContent = `股票持仓 (${stockRatio}%)`;
            }

            // 渲染数据并添加弹跳效果
            renderStockHoldings(data, stockHoldingsElement, true);

            // 设置自动更新
            setupStockUpdateInterval(fundCode);
        })
        .catch(error => {
            console.error('获取持仓股票数据失败:', error);
            stockHoldingsElement.innerHTML = '<div style="font-size: 12px; color: #ff4444;">获取持仓股票数据失败</div>';
        });
}

// 设置股票数据自动更新
function setupStockUpdateInterval(fundCode) {
    // 清除之前的定时器
    if (stockUpdateIntervals[fundCode]) {
        clearInterval(stockUpdateIntervals[fundCode]);
    }

    // 清除之前的股票定时器
    if (typeof stockUpdateTimers !== 'undefined' && stockUpdateTimers[fundCode]) {
        stockUpdateTimers[fundCode].forEach(timer => clearInterval(timer));
        delete stockUpdateTimers[fundCode];
    }

    // 只有在交易时间才设置自动更新
    if (isTradingTime()) {
        // 交易时间10-25秒随机更新一次
        const interval = 60000; // 股票价格1分钟更新

        // 设置更新定时器
        stockUpdateIntervals[fundCode] = setInterval(() => {
            const stockHoldingsElement = document.getElementById('stock-holdings');
            if (stockHoldingsElement) {
                fetch(`/api/funds/${fundCode}/holdings`)
                    .then(response => response.json())
                    .then(data => {
                        // 存储到缓存
                        const cacheKey = `stock_holdings_${fundCode}`;
                        const currentTime = Date.now() / 1000;
                        stockHoldingsCache[cacheKey] = {
                            timestamp: currentTime,
                            data: data
                        };

                        // 渲染数据
                        renderStockHoldings(data, stockHoldingsElement, true);
                    })
                    .catch(error => {
                        console.error('自动更新持仓股票数据失败:', error);
                    });
            }

            // 检查是否仍在交易时间
            if (!isTradingTime()) {
                clearInterval(stockUpdateIntervals[fundCode]);
                delete stockUpdateIntervals[fundCode];
            }
        }, interval);
    } else {
    }
}

// 清除股票数据自动更新
function clearStockUpdateInterval(fundCode) {
    if (stockUpdateIntervals[fundCode]) {
        clearInterval(stockUpdateIntervals[fundCode]);
        delete stockUpdateIntervals[fundCode];
    }

    // 清除单个股票的更新定时器（兼容旧代码）
    if (typeof stockUpdateTimers !== 'undefined' && stockUpdateTimers[fundCode]) {
        stockUpdateTimers[fundCode].forEach(timer => clearInterval(timer));
        delete stockUpdateTimers[fundCode];
    }
}

// 添加CSS动画样式
const style = document.createElement('style');
style.textContent = `
    @keyframes flash-update {
        0% { background-color: rgba(255, 255, 255, 0.25); }
        100% { background-color: transparent; }
    }
    
    @keyframes pulse-border {
        0% { box-shadow: 0 0 0 0 rgba(255, 255, 255, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(255, 255, 255, 0); }
        100% { box-shadow: 0 0 0 0 rgba(255, 255, 255, 0); }
    }
    
    .flash-update {
        animation: flash-update 0.6s ease-out;
    }
    
    .pulse-border {
        animation: pulse-border 0.6s ease-out;
    }
`;
document.head.appendChild(style);

// 存储股票更新定时器 (不再使用，已简化更新逻辑)
// let stockUpdateTimers = {};

// 闪烁卡片动画
function flashCard(cardEl) {
    // 添加闪烁动画类
    cardEl.classList.add('flash-update');
    // 动画结束后移除类
    cardEl.addEventListener('animationend', () => {
        cardEl.classList.remove('flash-update');
    }, { once: true });
}

// 脉冲边框动画
function pulseCard(cardEl) {
    // 添加脉冲动画类
    cardEl.classList.add('pulse-border');
    // 动画结束后移除类
    cardEl.addEventListener('animationend', () => {
        cardEl.classList.remove('pulse-border');
    }, { once: true });
}

// 渲染股票持仓数据
function renderStockHoldings(data, element, addBounceEffect = false) {
    if (data.stocks && data.stocks.length > 0) {
        let holdingsHTML = '';

        // 按照权重排序
        data.stocks.sort((a, b) => b.weight - a.weight);

        // 显示全部股票
        const displayStocks = data.stocks;

        // 计算股票占比
        const stockRatio = data.stock_ratio ? data.stock_ratio.toFixed(1) : 0;

        // 添加股票网格
        holdingsHTML += '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px;">';

        // 批量处理股票数据，减少DOM操作
        const stockElements = displayStocks.map(stock => {
            const changeRatio = (stock.change_ratio * 100).toFixed(2);
            const isPositive = stock.change_ratio >= 0;
            const borderColor = isPositive ? '#ff4444' : '#4CAF50';
            const bgColor = isPositive ? 'rgba(255, 68, 68, 0.1)' : 'rgba(76, 175, 80, 0.1)';
            const textColor = isPositive ? '#ff4444' : '#4CAF50';

            return `
                <div class="stock-card" data-stock-code="${stock.code}" style="background-color: ${bgColor}; border: 1px solid ${borderColor}; border-radius: 4px; padding: 10px; transition: all 0.3s ease;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                        <div style="font-size: 12px; color: #e0e0e0; font-weight: bold;">${stock.name || stock.code}</div>
                        <div style="font-size: 10px; color: #aaa;">持仓: ${stock.weight.toFixed(2)}%</div>
                    </div>
                    <div style="font-size: 10px; color: #aaa; margin-bottom: 4px;">${stock.code}</div>
                    <div style="font-size: 12px; font-weight: bold; color: ${textColor};">
                        价格: ${stock.current_price.toFixed(2)}元  
                        涨幅: ${isPositive ? '+' : ''}${stock.change_amount.toFixed(2)}元  
                        ${isPositive ? '+' : ''}${changeRatio}%
                    </div>
                </div>
            `;
        }).join('');

        holdingsHTML += stockElements;
        holdingsHTML += '</div>';

        // 渲染HTML
        element.innerHTML = holdingsHTML;

        // 添加单个股票的闪烁动画效果
        if (addBounceEffect) {
            const stockCards = element.querySelectorAll('.stock-card');
            stockCards.forEach((card, index) => {
                // 为每个股票卡片设置不同的动画延迟
                setTimeout(() => {
                    // 随机选择闪烁或脉冲动画
                    if (Math.random() > 0.5) {
                        flashCard(card);
                    } else {
                        pulseCard(card);
                    }
                }, index * 100); // 每个卡片延迟100ms，形成交错效果
            });
        }
    } else {
        element.innerHTML = '<div style="font-size: 12px; color: #aaa; padding: 20px; text-align: center;">暂无持仓股票数据</div>';
    }
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

    // 优先从云端缓存计算持仓（支持多设备）
    if (window._cloudBuyRecords && window._cloudBuyRecords.length > 0) {
        const fundIdStr = String(fundId);
        const records = window._cloudBuyRecords.filter(r =>
            String(r.fund_id) === fundIdStr
        );
        if (records.length > 0) {
            const totalShares = records.reduce((sum, r) => sum + (r.shares || 0), 0);
            const lastRecord = records[records.length - 1];
            // 同步写入 localStorage 保持一致
            const settings = { date: lastRecord.date, shares: totalShares };
            localStorage.setItem(`fundBuySettings_${fundId}`, JSON.stringify(settings));
            return settings;
        }
    }

    // 降级：读 localStorage
    const savedSettings = localStorage.getItem(`fundBuySettings_${fundId}`);
    return savedSettings ? JSON.parse(savedSettings) : defaultSettings;
}

// 判断一个日期是否是交易日（简单实现，实际应用中可能需要更复杂的逻辑或API）
function isTradingDay(date) {
    const dayOfWeek = date.getDay();
    // 周末不是交易日
    if (dayOfWeek === 0 || dayOfWeek === 6) {
        return false;
    }

    // 这里可以添加节假日判断逻辑
    // 例如：检查是否是法定节假日

    return true;
}

// 获取上一个交易日的日期
function getPreviousTradingDay() {
    const today = new Date();
    let previousDay = new Date(today);

    // 向前查找，直到找到一个交易日
    do {
        previousDay.setDate(previousDay.getDate() - 1);
    } while (!isTradingDay(previousDay));

    return previousDay;
}

// ── 买入记录（云端 + localStorage 双写，保证兼容性）────────────────────────

// 内存缓存，避免重复请求
let _buyRecordsCache = null;
let _buyRecordsCacheTime = 0;
const _BUY_RECORDS_TTL = 60 * 1000; // 1分钟缓存

async function fetchAllBuyRecords(forceRefresh = false) {
    const now = Date.now();
    if (!forceRefresh && _buyRecordsCache && now - _buyRecordsCacheTime < _BUY_RECORDS_TTL) {
        return _buyRecordsCache;
    }
    try {
        const resp = await fetch('/api/buy_records');
        if (resp.ok) {
            const data = await resp.json();
            _buyRecordsCache = data;
            _buyRecordsCacheTime = now;
            return data;
        }
    } catch(e) {
        console.warn('获取云端买入记录失败，降级用 localStorage:', e);
    }
    return null;
}

function getBuyRecords(fundId) {
    // 优先从云端缓存读取（支持多设备）
    if (window._cloudBuyRecords && window._cloudBuyRecords.length > 0) {
        const records = window._cloudBuyRecords.filter(r => String(r.fund_id) === String(fundId));
        if (records.length > 0) {
            const localRecords = records.map(r => ({ date: r.date, shares: r.shares, nav: r.nav, id: r.id }));
            localStorage.setItem(`fundBuyRecords_${fundId}`, JSON.stringify(localRecords));
            return localRecords;
        }
    }
    const savedRecords = localStorage.getItem(`fundBuyRecords_${fundId}`);
    return savedRecords ? JSON.parse(savedRecords) : [];
}

async function saveBuyRecord(fundId, record) {
    // 1. 先写 localStorage（保证止盈计算立即可用）
    const records = getBuyRecords(fundId);
    records.push(record);
    localStorage.setItem(`fundBuyRecords_${fundId}`, JSON.stringify(records));

    // 2. 同步写云端
    try {
        await fetch('/api/buy_records', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(record)
        });
        _buyRecordsCache = null; // 清缓存
    } catch(e) {
        console.warn('云端买入记录保存失败，已保存到本地:', e);
    }
}

async function deleteBuyRecord(recordId, fundId) {
    // 1. 先删 localStorage
    if (fundId) {
        const records = getBuyRecords(fundId).filter((_, i) => i !== recordId);
        localStorage.setItem(`fundBuyRecords_${fundId}`, JSON.stringify(records));
    }
    // 2. 删云端（recordId 是云端 id）
    try {
        await fetch(`/api/buy_records/${recordId}`, { method: 'DELETE' });
        _buyRecordsCache = null;
    } catch(e) {
        console.warn('云端买入记录删除失败:', e);
    }
}

// 启动时把 localStorage 数据迁移到云端（只迁移一次）
async function migrateBuyRecordsToCloud(force = false) {
    return; // 迁移已完成，禁用自动迁移避免重复写入
    const migrated = localStorage.getItem('_buy_records_migrated_v2');
    if (migrated && !force) return;

    const allRecords = [];
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (!key || !key.startsWith('fundBuyRecords_')) continue;
        const fundId = key.replace('fundBuyRecords_', '');
        const records = JSON.parse(localStorage.getItem(key) || '[]');
        // 通过 _fundIdCodeMap 找到 fund_code
        const fundCode = window._fundIdCodeMap ? window._fundIdCodeMap[fundId] : null;
        // 通过缓存找 fund_name
        const cachedFunds = cacheManager.get(CACHE_KEYS.FUNDS_LIST) || [];
        const fundInfo = cachedFunds.find(f => String(f.id) === String(fundId));
        records.forEach(r => allRecords.push({
            ...r,
            fund_id: String(fundId),
            fund_code: r.fund_code || fundCode || '',
            fund_name: r.fund_name || (fundInfo ? fundInfo.name : ''),
            amount: r.amount || (r.nav && r.shares ? r.nav * r.shares : 0),
        }));
    }

    if (allRecords.length > 0) {
        let success = 0;
        for (const r of allRecords) {
            try {
                const resp = await fetch('/api/buy_records', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(r)
                });
                if (resp.ok) success++;
            } catch(e) {}
        }
        console.warn('迁移完成：' + allRecords.length + ' 条记录，成功 ' + success + ' 条');
        // 刷新云端缓存
        fetchAllBuyRecords(true).then(records => {
            if (records) window._cloudBuyRecords = records;
        });
    }
    localStorage.setItem('_buy_records_migrated_v2', '1');
}



function updateChart(fund, chartId, days) {
    // 计算需要显示的数据点数量
    const prices = fund.prices && fund.prices.length > 0 ? fund.prices : [];
    const dates = fund.dates && fund.dates.length > 0 ? fund.dates : [];

    let displayPrices = prices;
    let displayDates = dates;
    let startIndex = 0;

    if (days > 0) {
        startIndex = Math.max(0, prices.length - days);
        displayPrices = prices.slice(startIndex);
        displayDates = dates.slice(startIndex);
    }

    // 调试信息

    // 检查数据是否足够
    if (prices.length === 0) {
        // 没有数据，显示提示信息
        const ctx = document.getElementById(chartId).getContext('2d');
        if (window[`fundChart_${chartId}`]) {
            window[`fundChart_${chartId}`].destroy();
        }

        window[`fundChart_${chartId}`] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: []
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: '暂无历史数据',
                        color: '#e0e0e0',
                        font: {
                            size: 16
                        }
                    }
                },
                scales: {
                    x: {
                        display: false
                    },
                    y: {
                        display: false
                    }
                }
            }
        });
        return;
    }

    // 使用完整数据计算技术指标，确保有足够的数据点
    // 使用专业方法计算支撑位和阻力位
    const sr = calculateSupportResistance(prices);
    const supportLevel = sr.support;
    const resistanceLevel = sr.resistance;

    // 创建支撑位和压力位数据
    const supportData = Array(displayPrices.length).fill(supportLevel);
    const resistanceData = Array(displayPrices.length).fill(resistanceLevel);

    // 计算移动平均线（使用完整数据，然后截取需要显示的部分）
    const fullMA20 = calculateMA(prices, 20);
    const fullMA60 = calculateMA(prices, 60);
    const ma20 = fullMA20.slice(startIndex);
    const ma60 = fullMA60.slice(startIndex);

    // 计算布林带（使用完整数据，然后截取需要显示的部分）
    const fullBollingerBands = calculateBollingerBands(prices);
    const bollingerBands = {
        upper: fullBollingerBands.upper.slice(startIndex),
        middle: fullBollingerBands.middle.slice(startIndex),
        lower: fullBollingerBands.lower.slice(startIndex)
    };

    // 调试布林带数据

    // 计算MACD（使用完整数据，然后截取需要显示的部分）
    const fullMACD = calculateMACD(prices);
    const macd = {
        macdLine: fullMACD.macdLine.slice(startIndex),
        signalLine: fullMACD.signalLine.slice(startIndex),
        histogram: fullMACD.histogram.slice(startIndex)
    };

    // 计算KDJ（使用完整数据，然后截取需要显示的部分）
    const fullKDJ = calculateKDJ(prices);
    const kdj = {
        k: fullKDJ.k.slice(startIndex),
        d: fullKDJ.d.slice(startIndex),
        j: fullKDJ.j.slice(startIndex)
    };

    // 计算ATR
    const atr = calculateATR(prices);

    // 获取图表上下文
    const ctx = document.getElementById(chartId).getContext('2d');

    // 销毁现有图表
    if (window[`fundChart_${chartId}`]) {
        window[`fundChart_${chartId}`].destroy();
    }

    // 创建新图表
    window[`fundChart_${chartId}`] = new Chart(ctx, {
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
                    pointHoverRadius: 5,
                    pointBackgroundColor: '#33b5e5',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2
                },
                {
                    label: 'MA20',
                    data: ma20,
                    borderColor: '#ff9800',
                    borderWidth: 1.5,
                    tension: 0.3,
                    fill: false,
                    pointRadius: 0,
                    pointHoverRadius: 0
                },
                {
                    label: 'MA60',
                    data: ma60,
                    borderColor: '#9c27b0',
                    borderWidth: 1.5,
                    tension: 0.3,
                    fill: false,
                    pointRadius: 0,
                    pointHoverRadius: 0
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
                    borderColor: '#ff4444',
                    borderWidth: 1,
                    borderDash: [5, 5],
                    fill: false,
                    pointRadius: 0,
                    pointHoverRadius: 0
                },
                {
                    label: '布林带上轨',
                    data: bollingerBands.upper,
                    borderColor: '#4caf50',
                    borderWidth: 1,
                    borderDash: [3, 3],
                    fill: false,
                    pointRadius: 0,
                    pointHoverRadius: 0
                },
                {
                    label: '布林带中轨',
                    data: bollingerBands.middle,
                    borderColor: '#ff9800',
                    borderWidth: 1,
                    borderDash: [3, 3],
                    fill: false,
                    pointRadius: 0,
                    pointHoverRadius: 0
                },
                {
                    label: '布林带下轨',
                    data: bollingerBands.lower,
                    borderColor: '#f44336',
                    borderWidth: 1,
                    borderDash: [3, 3],
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
            backgroundColor: '#000000',
            scales: {
                x: {
                    position: 'bottom',
                    ticks: {
                        color: '#aaa',
                        font: {
                            size: 11
                        },
                        maxRotation: 0,
                        autoSkip: true,
                        maxTicksLimit: 8
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
                            return value.toFixed(4);
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
                    top: 20,
                    bottom: 30
                }
            }
        }
    });

    // 更新技术指标图表
    updateTechChart(fund, chartId, days);
}

function updateTechChart(fund, chartId, days) {
    // 计算需要显示的数据点数量
    const prices = fund.prices && fund.prices.length > 0 ? fund.prices : [];
    const dates = fund.dates && fund.dates.length > 0 ? fund.dates : [];

    let displayPrices = prices;
    let displayDates = dates;
    let startIndex = 0;

    if (days > 0) {
        startIndex = Math.max(0, prices.length - days);
        displayPrices = prices.slice(startIndex);
        displayDates = dates.slice(startIndex);
    }

    // 使用完整数据计算技术指标，确保有足够的数据点
    const fullMACD = calculateMACD(prices);
    const fullKDJ = calculateKDJ(prices);
    const atr = calculateATR(prices);

    // 截取需要显示的部分
    const macd = {
        macdLine: fullMACD.macdLine.slice(startIndex),
        signalLine: fullMACD.signalLine.slice(startIndex),
        histogram: fullMACD.histogram.slice(startIndex)
    };

    const kdj = {
        k: fullKDJ.k.slice(startIndex),
        d: fullKDJ.d.slice(startIndex),
        j: fullKDJ.j.slice(startIndex)
    };

    // 获取技术指标图表上下文
    const techChartId = `${chartId}-tech`;
    const ctx = document.getElementById(techChartId).getContext('2d');

    // 销毁现有图表
    if (window[`techChart_${chartId}`]) {
        window[`techChart_${chartId}`].destroy();
    }

    // 创建技术指标图表
    window[`techChart_${chartId}`] = new Chart(ctx, {
        type: 'line',
        data: {
            labels: displayDates,
            datasets: [
                {
                    label: 'MACD',
                    data: macd.macdLine,
                    borderColor: '#ff9800',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.3,
                    pointRadius: 0,
                    pointHoverRadius: 0
                },
                {
                    label: 'Signal',
                    data: macd.signalLine,
                    borderColor: '#f44336',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.3,
                    pointRadius: 0,
                    pointHoverRadius: 0
                },
                {
                    label: 'K',
                    data: kdj.k,
                    borderColor: '#33b5e5',
                    borderWidth: 1.5,
                    fill: false,
                    tension: 0.3,
                    pointRadius: 0,
                    pointHoverRadius: 0
                },
                {
                    label: 'D',
                    data: kdj.d,
                    borderColor: '#4caf50',
                    borderWidth: 1.5,
                    fill: false,
                    tension: 0.3,
                    pointRadius: 0,
                    pointHoverRadius: 0
                },
                {
                    label: 'J',
                    data: kdj.j,
                    borderColor: '#9c27b0',
                    borderWidth: 1.5,
                    fill: false,
                    tension: 0.3,
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
            backgroundColor: '#000000',
            scales: {
                x: {
                    position: 'bottom',
                    ticks: {
                        color: '#aaa',
                        font: {
                            size: 11
                        },
                        maxRotation: 0,
                        autoSkip: true,
                        maxTicksLimit: 8
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
                            return value.toFixed(3);
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
                    top: 20,
                    bottom: 30
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
    // 移动端：底部抽屉式弹出
    if (window.innerWidth <= 600) {
        modal.style.alignItems = 'flex-end';
    }

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
                <div style="margin-bottom: 8px;">
                    <label style="font-size: 11px; margin-right: 10px;">投资偏好:</label>
                    <select id="investment-level" style="background-color: #333; color: #e0e0e0; border: 1px solid #444; padding: 3px 6px; border-radius: 4px; font-size: 10px;">
                        <option value="small"  ${settings.investmentLevel === 'small'  ? 'selected' : ''}>小额（100 / 200 / 300 / 500 元）</option>
                        <option value="medium" ${settings.investmentLevel === 'medium' ? 'selected' : ''}>中额（300 / 500 / 800 / 1000 元）</option>
                        <option value="large"  ${settings.investmentLevel === 'large'  ? 'selected' : ''}>大额（800 / 1000 / 1200 / 1500 / 2000 元）</option>
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
        
        <div id="admin-section" style="margin-bottom: 16px; display: none;">
            <h3 style="color: #e0e0e0; margin-bottom: 8px; font-size: 12px;">账户管理</h3>
            <div style="background-color: #2a2a2a; border-radius: 4px; padding: 12px; border: 1px solid #333;">
                <button id="account-management" style="background-color: #007bff; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 11px; width: 100%;">管理账户</button>
            </div>
        </div>
        
        <div style="display: flex; justify-content: flex-end; gap: 8px;">
            <button id="clear-cache" style="background-color: #dc3545; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 11px;">清除缓存</button>
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
            investmentLevel: document.getElementById('investment-level').value,
            showDistance: document.getElementById('show-distance').checked,
            showRSI: document.getElementById('show-rsi').checked,
            showAlerts: document.getElementById('show-alerts').checked
        };

        localStorage.setItem('fundTrackerSettings', JSON.stringify(newSettings));
        alert('设置已保存');
        document.body.removeChild(modal);
        // 应用设置
        applySettings(newSettings);
        // 重新启动自动更新，应用新的更新频率
        startFundAutoUpdate();
    });

    // 检查是否为管理员
    fetch('/api/check-admin')
        .then(response => response.json())
        .then(data => {
            if (data.is_admin) {
                // 显示账户管理选项
                modal.querySelector('#admin-section').style.display = 'block';

                // 账户管理按钮点击事件
                modal.querySelector('#account-management').addEventListener('click', function() {
                    window.location.href = '/account-management';
                });
            }
        })
        .catch(error => {
            console.error('检查管理员权限失败:', error);
        });

    // 清除缓存按钮
    modal.querySelector('#clear-cache').addEventListener('click', function() {
        if (confirm('确定要清除所有缓存数据吗？这将删除所有基金数据和设置。')) {
            localStorage.clear();
            alert('缓存已清除');
            document.body.removeChild(modal);
            // 重新加载页面
            location.reload();
        }
    });
}

function getSettings() {
    const defaultSettings = {
        fontSize: 'medium',
        updateFrequency: '5',
        investmentLevel: 'small',
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
}

function loadFundManagement(container) {
    // 使用 basic=true 参数，只获取基金的基本信息，不需要更新数据
    fetch('/api/funds?basic=true')
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
                    }
                });
            });
        });
}

// 启动基金数据自动更新
function startFundAutoUpdate() {
    // 清除之前的定时器
    if (fundUpdateInterval) {
        clearInterval(fundUpdateInterval);
    }

    // 获取更新频率设置
    const settings = getSettings();
    const updateMinutes = parseInt(settings.updateFrequency) || 5;
    const updateIntervalMs = updateMinutes * 60 * 1000;

    // 设置新的定时器
    fundUpdateInterval = setInterval(() => {
        if (isTradingTime()) {
            loadFunds();
        }
    }, updateIntervalMs);
}

// 停止基金数据自动更新
function stopFundAutoUpdate() {
    if (fundUpdateInterval) {
        clearInterval(fundUpdateInterval);
        fundUpdateInterval = null;
    }
}

// 页面加载时应用设置并启动自动更新
window.addEventListener('load', function() {
    const settings = getSettings();
    applySettings(settings);
    startFundAutoUpdate();

    // 监听更新事件
    window.addEventListener('updateFundList', function() {
        if (typeof loadFunds === 'function') {
            loadFunds();
        }
    });

    window.addEventListener('updateHoldings', function() {
        if (typeof updateAllHoldings === 'function') {
            updateAllHoldings();
        }
    });

    window.addEventListener('updateInvestmentAdvice', function() {
        if (typeof investmentAdvice !== 'undefined' && investmentAdvice && typeof investmentAdvice.loadInvestmentAdvice === 'function') {
            investmentAdvice.loadInvestmentAdvice();
        }
    });
});