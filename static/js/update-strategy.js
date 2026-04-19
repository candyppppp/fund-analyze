// 更新策略管理器

class UpdateStrategyManager {
    constructor() {
        // 定时器引用
        this.fundListInterval = null;
        this.holdingsInterval = null;
        this.investmentAdviceInterval = null;

        // 当前激活的标签
        this.activeTab = 'fund-prediction';
    }

    // 统一用北京时间判断，避免境外设备时区偏差
    _bjTime() {
        const now = new Date();
        const bj = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Shanghai' }));
        return { day: bj.getDay(), hour: bj.getHours(), minute: bj.getMinutes() };
    }

    // 判断是否为交易时间（北京时间 周一至周五 9:30-15:00）
    isTradingTime() {
        const { day, hour, minute } = this._bjTime();
        if (day < 1 || day > 5) return false;
        const mins = hour * 60 + minute;
        return (mins >= 570 && mins < 690) || (mins >= 780 && mins < 900);
    }

    // 判断是否为盘前时间（北京时间 9:00-9:30）
    isPreMarketTime() {
        const { day, hour, minute } = this._bjTime();
        return day >= 1 && day <= 5 && hour === 9 && minute < 30;
    }

    // 判断是否为盘后时间（北京时间 15:00-16:00）
    isAfterMarketTime() {
        const { day, hour } = this._bjTime();
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
                    return 3 * 60 * 1000; // 交易时间: 3分钟
                } else if (isPreMarket || isAfterMarket) {
                    return 10 * 60 * 1000; // 盘前盘后: 10分钟
                } else {
                    return 30 * 60 * 1000; // 非交易时间: 30分钟
                }

            case 'holdings':
                // 股票持仓更新频率（持仓数据变化慢，无需高频）
                if (isTrading) {
                    return 5 * 60 * 1000; // 交易时间: 5分钟
                } else if (isPreMarket || isAfterMarket) {
                    return 10 * 60 * 1000; // 盘前盘后: 10分钟
                } else {
                    return 30 * 60 * 1000; // 非交易时间: 30分钟
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
}

// 创建全局实例
const updateStrategyManager = new UpdateStrategyManager();

// 导出更新策略管理器
export default updateStrategyManager;