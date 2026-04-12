// 缓存管理模块

class CacheManager {
    constructor() {
        // 使用 localStorage 存储缓存
        this.storageKey = 'fundTrackerCache';
        this.cache = this.loadFromStorage();
    }

    // 从 localStorage 加载缓存
    loadFromStorage() {
        try {
            const cached = localStorage.getItem(this.storageKey);
            if (cached) {
                return JSON.parse(cached);
            }
        } catch (error) {
            console.error('加载缓存失败:', error);
        }
        return {};
    }

    // 保存缓存到 localStorage
    saveToStorage() {
        try {
            localStorage.setItem(this.storageKey, JSON.stringify(this.cache));
        } catch (error) {
            console.error('保存缓存失败:', error);
        }
    }

    // 获取缓存
    get(key) {
        const item = this.cache[key];
        if (!item) return null;

        const { data, timestamp, expiry } = item;
        
        // 检查是否过期
        if (Date.now() - timestamp > expiry) {
            delete this.cache[key];
            this.saveToStorage();
            return null;
        }

        return data;
    }

    // 设置缓存
    set(key, data, expiry = 5 * 60 * 1000) { // 默认5分钟
        this.cache[key] = {
            data,
            timestamp: Date.now(),
            expiry
        };
        this.saveToStorage();
    }

    // 删除缓存
    delete(key) {
        delete this.cache[key];
        this.saveToStorage();
    }

    // 清空所有缓存
    clear() {
        this.cache = {};
        this.saveToStorage();
    }

    // 获取缓存的剩余有效期（毫秒）
    getRemainingTime(key) {
        const item = this.cache[key];
        if (!item) return 0;

        const { timestamp, expiry } = item;
        const remaining = expiry - (Date.now() - timestamp);
        return remaining > 0 ? remaining : 0;
    }

    // 检查缓存是否存在且有效
    has(key) {
        return this.get(key) !== null;
    }
}

// 创建全局缓存管理器实例
const cacheManager = new CacheManager();

// 导出缓存管理器
export default cacheManager;
