// 更新策略管理器

class UpdateStrategyManager {
    constructor() {
        // 定时器引用
        this.fundListInterval = null;
        this.holdingsInterval = null;

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
            case 'fundList': {
                // 读取用户设置的频率（默认3分钟）
                const _flMins = parseInt((typeof getSettings === 'function' ? getSettings().updateFrequency : null) || '3');
                if (isTrading) return _flMins * 60 * 1000;
                else if (isPreMarket || isAfterMarket) return Math.max(_flMins, 10) * 60 * 1000;
                else return 30 * 60 * 1000;
            }

            case 'holdings': {
                // 持仓股票改为按需拉取，此处仅供展开状态下的刷新参考
                const _hMins = parseInt((typeof getSettings === 'function' ? getSettings().holdingsFrequency : null) || '1');
                if (isTrading) return _hMins * 60 * 1000;
                else if (isPreMarket || isAfterMarket) return 10 * 60 * 1000;
                else return 30 * 60 * 1000;
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
                // investment-advice.js 内部自管定时器，此处无需额外启动
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

    }
}

// 创建全局实例
const updateStrategyManager = new UpdateStrategyManager();

// 导出更新策略管理器
export default updateStrategyManager;