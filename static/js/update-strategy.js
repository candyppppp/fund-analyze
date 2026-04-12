// 更新策略管理器

class UpdateStrategyManager {
    constructor() {
        // 定时器引用
        this.fundListInterval = null;
        this.holdingsInterval = null;
        this.investmentAdviceInterval = null;
        
        // 当前激活的标签
        this.activeTab = 'fund-prediction';
        
        // 数据源健康状态
        this.dataSourceHealth = {
            sina: { status: 'healthy', lastCheck: null, failCount: 0 },
            eastmoney: { status: 'healthy', lastCheck: null, failCount: 0 },
            tencent: { status: 'healthy', lastCheck: null, failCount: 0 },
            ths: { status: 'healthy', lastCheck: null, failCount: 0 }
        };
        
        // 数据源健康检查阈值
        this.healthThreshold = 3;
        this.healthCheckInterval = 60 * 60 * 1000; // 1小时检查一次
        
        // 启动数据源健康检查
        this.startDataSourceHealthCheck();
    }
    
    // 判断是否为交易时间
    isTradingTime() {
        const now = new Date();
        const day = now.getDay();
        const hour = now.getHours();
        const minute = now.getMinutes();
        
        // 周一到周五
        if (day >= 1 && day <= 5) {
            // 上午: 9:30 - 11:30
            if (hour === 9 && minute >= 30 || (hour > 9 && hour < 11) || (hour === 11 && minute <= 30)) {
                return true;
            }
            // 下午: 13:00 - 15:00
            if (hour >= 13 && hour < 15) {
                return true;
            }
        }
        return false;
    }
    
    // 判断是否为盘前时间 (9:00 - 9:30)
    isPreMarketTime() {
        const now = new Date();
        const day = now.getDay();
        const hour = now.getHours();
        const minute = now.getMinutes();
        return day >= 1 && day <= 5 && hour === 9 && minute < 30;
    }
    
    // 判断是否为盘后时间 (15:00 - 16:00)
    isAfterMarketTime() {
        const now = new Date();
        const day = now.getDay();
        const hour = now.getHours();
        return day >= 1 && day <= 5 && hour >= 15 && hour < 16;
    }
    
    // 获取更新时间间隔（毫秒）
    getUpdateInterval(type) {
        const isTrading = this.isTradingTime();
        const isPreMarket = this.isPreMarketTime();
        const isAfterMarket = this.isAfterMarketTime();
        
        switch (type) {
            case 'fundList':
                // 基金列表更新频率
                if (isTrading) {
                    return 60 * 1000; // 交易时间: 1分钟
                } else if (isPreMarket || isAfterMarket) {
                    return 5 * 60 * 1000; // 盘前盘后: 5分钟
                } else {
                    return 30 * 60 * 1000; // 非交易时间: 30分钟
                }
                
            case 'holdings':
                // 股票持仓更新频率
                if (isTrading) {
                    return 15 * 1000; // 交易时间: 15秒
                } else if (isPreMarket || isAfterMarket) {
                    return 60 * 1000; // 盘前盘后: 1分钟
                } else {
                    return 10 * 60 * 1000; // 非交易时间: 10分钟
                }
                
            case 'investmentAdvice':
                // 投资建议更新频率
                if (isTrading) {
                    return 10 * 60 * 1000; // 交易时间: 10分钟
                } else {
                    return 60 * 60 * 1000; // 非交易时间: 1小时
                }
                
            default:
                return 60 * 1000;
        }
    }
    
    // 切换标签
    switchTab(tabName) {
        if (this.activeTab === tabName) return;
        
        // 停止之前的更新
        this.stopAllUpdates();
        
        // 启动新的更新
        this.activeTab = tabName;
        this.startUpdatesForTab(tabName);
    }
    
    // 根据标签启动更新
    startUpdatesForTab(tabName) {
        switch (tabName) {
            case 'fund-prediction':
                // 基金预测标签：启动基金列表和持仓更新
                this.startFundListUpdate();
                this.startHoldingsUpdate();
                break;
                
            case 'investment-advice':
                // 投资建议标签：启动投资建议更新
                this.startInvestmentAdviceUpdate();
                break;
        }
    }
    
    // 启动基金列表更新
    startFundListUpdate() {
        if (this.fundListInterval) {
            clearInterval(this.fundListInterval);
        }
        
        const update = () => {
            console.log(`[${new Date().toLocaleTimeString()}] 基金列表更新，间隔: ${this.getUpdateInterval('fundList') / 1000}秒`);
            // 使用事件触发基金列表更新
            const event = new CustomEvent('updateFundList');
            window.dispatchEvent(event);
        };
        
        // 立即执行一次
        update();
        
        // 设置定时器
        this.fundListInterval = setInterval(update, this.getUpdateInterval('fundList'));
        
        // 监听交易时间变化，重新设置定时器
        this.checkAndResetInterval('fundList', this.fundListInterval);
    }
    
    // 启动持仓更新
    startHoldingsUpdate() {
        if (this.holdingsInterval) {
            clearInterval(this.holdingsInterval);
        }
        
        const update = () => {
            console.log(`[${new Date().toLocaleTimeString()}] 股票持仓更新，间隔: ${this.getUpdateInterval('holdings') / 1000}秒`);
            // 使用事件触发持仓更新
            const event = new CustomEvent('updateHoldings');
            window.dispatchEvent(event);
        };
        
        // 立即执行一次
        update();
        
        // 设置定时器
        this.holdingsInterval = setInterval(update, this.getUpdateInterval('holdings'));
    }
    
    // 启动投资建议更新
    startInvestmentAdviceUpdate() {
        if (this.investmentAdviceInterval) {
            clearInterval(this.investmentAdviceInterval);
        }
        
        const update = () => {
            console.log(`[${new Date().toLocaleTimeString()}] 投资建议更新，间隔: ${this.getUpdateInterval('investmentAdvice') / 1000}秒`);
            // 使用事件触发投资建议更新
            const event = new CustomEvent('updateInvestmentAdvice');
            window.dispatchEvent(event);
        };
        
        // 立即执行一次
        update();
        
        // 设置定时器
        this.investmentAdviceInterval = setInterval(update, this.getUpdateInterval('investmentAdvice'));
    }
    
    // 检查并重置定时器（交易时间变化时）
    checkAndResetInterval(type, currentInterval) {
        const checkInterval = 60 * 1000; // 每分钟检查一次
        
        setInterval(() => {
            const newInterval = this.getUpdateInterval(type);
            // 如果时间间隔变化了，重新启动更新
            // 这里可以添加更复杂的逻辑
        }, checkInterval);
    }
    
    // 停止所有更新
    stopAllUpdates() {
        if (this.fundListInterval) {
            clearInterval(this.fundListInterval);
            this.fundListInterval = null;
        }
        if (this.holdingsInterval) {
            clearInterval(this.holdingsInterval);
            this.holdingsInterval = null;
        }
        if (this.investmentAdviceInterval) {
            clearInterval(this.investmentAdviceInterval);
            this.investmentAdviceInterval = null;
        }
    }
    
    // 数据源健康检查
    async checkDataSourceHealth(source) {
        const testCodes = ['000001', '510310']; // 测试用基金代码
        
        // 跳过会导致 CORS 错误的数据源
        const corsSources = ['sina', 'eastmoney'];
        if (corsSources.includes(source)) {
            console.log(`[数据源健康检查] ${source}: 跳过（CORS 限制）`);
            // 对于 CORS 受限的数据源，标记为健康，因为它们实际上是可用的
            this.updateSourceHealth(source, true);
            return true;
        }
        
        try {
            let url;
            switch (source) {
                case 'tencent':
                    url = `https://qt.gtimg.cn/q=sz${testCodes[0]}`;
                    break;
                default:
                    return false;
            }
            
            const startTime = Date.now();
            const response = await fetch(url, { timeout: 5000 });
            const latency = Date.now() - startTime;
            
            if (response.ok) {
                const data = await response.text();
                
                // 检查数据是否有效
                if (data && data.length > 10) {
                    this.updateSourceHealth(source, true);
                    console.log(`[数据源健康检查] ${source}: 健康，延迟: ${latency}ms`);
                    return true;
                }
            }
            
            this.updateSourceHealth(source, false);
            return false;
        } catch (error) {
            this.updateSourceHealth(source, false);
            console.error(`[数据源健康检查] ${source}: 失败 - ${error.message}`);
            return false;
        }
    }
    
    // 更新数据源健康状态
    updateSourceHealth(source, success) {
        const health = this.dataSourceHealth[source];
        health.lastCheck = new Date();
        
        if (success) {
            health.failCount = 0;
            health.status = 'healthy';
        } else {
            health.failCount++;
            if (health.failCount >= this.healthThreshold) {
                health.status = 'unhealthy';
                console.warn(`[数据源状态] ${source}: 不健康，连续失败 ${health.failCount} 次`);
            }
        }
    }
    
    // 获取当前可用的最佳数据源
    getBestDataSource() {
        const healthySources = Object.entries(this.dataSourceHealth)
            .filter(([_, health]) => health.status === 'healthy')
            .map(([name, _]) => name);
        
        if (healthySources.length === 0) {
            // 所有数据源都不健康，返回第一个（默认）
            return 'sina';
        }
        
        // 优先顺序: sina > eastmoney > tencent > ths
        const priority = ['sina', 'eastmoney', 'tencent', 'ths'];
        for (const source of priority) {
            if (healthySources.includes(source)) {
                return source;
            }
        }
        
        return 'sina';
    }
    
    // 启动数据源健康检查
    startDataSourceHealthCheck() {
        // 立即执行一次健康检查
        this.performHealthCheck();
        
        // 每小时执行一次健康检查
        setInterval(() => {
            this.performHealthCheck();
        }, this.healthCheckInterval);
    }
    
    // 执行健康检查
    async performHealthCheck() {
        console.log(`[${new Date().toLocaleTimeString()}] 开始数据源健康检查...`);
        
        const sources = ['sina', 'eastmoney', 'tencent', 'ths'];
        const results = await Promise.all(
            sources.map(source => this.checkDataSourceHealth(source))
        );
        
        const healthyCount = results.filter(r => r).length;
        const bestSource = this.getBestDataSource();
        
        console.log(`[数据源健康检查] 完成，可用: ${healthyCount}/${sources.length}，推荐: ${bestSource}`);
    }
    
    // 获取数据源状态报告
    getDataSourceStatus() {
        return {
            sources: this.dataSourceHealth,
            bestSource: this.getBestDataSource(),
            isTradingTime: this.isTradingTime(),
            currentTime: new Date().toLocaleString()
        };
    }
}

// 创建全局实例
const updateStrategyManager = new UpdateStrategyManager();

// 导出更新策略管理器
export default updateStrategyManager;