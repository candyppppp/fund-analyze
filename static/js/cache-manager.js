// 缓存管理模块
//
// 设计原则：
//   - 所有数据都存内存（页面生命周期内有效，刷新后丢失）
//   - 体积较小的数据（< SIZE_THRESHOLD）才持久化到 localStorage
//   - fundsList 含完整 prices/dates，体积大，只存内存，避免 QuotaExceededError
//   - investmentAdvice、marketData 等体积小，可持久化，跨刷新复用

const SIZE_THRESHOLD = 50 * 1024; // 50KB：超过此大小只存内存

class CacheManager {
    constructor() {
        this.storageKey = 'fundTrackerCache';
        this.memCache = {};
        this._loadFromStorage();
    }

    _loadFromStorage() {
        try {
            const raw = localStorage.getItem(this.storageKey);
            if (raw) {
                const parsed = JSON.parse(raw);
                const now = Date.now();
                for (const [key, item] of Object.entries(parsed)) {
                    if (now - item.timestamp <= item.expiry) {
                        this.memCache[key] = item;
                    }
                }
            }
        } catch (e) {
            console.warn('[CacheManager] 加载 localStorage 失败，使用空缓存');
        }
    }

    _saveToStorage() {
        try {
            const toSave = {};
            for (const [key, item] of Object.entries(this.memCache)) {
                if (!item._memOnly) toSave[key] = item;
            }
            localStorage.setItem(this.storageKey, JSON.stringify(toSave));
        } catch (e) {
            if (e.name === 'QuotaExceededError' || e.code === 22) {
                console.warn('[CacheManager] localStorage 空间不足，清除旧缓存');
                try { localStorage.removeItem(this.storageKey); } catch (_) {}
            }
        }
    }

    get(key) {
        const item = this.memCache[key];
        if (!item) return null;
        if (Date.now() - item.timestamp > item.expiry) {
            delete this.memCache[key];
            this._saveToStorage();
            return null;
        }
        return item.data;
    }

    set(key, data, expiry = 5 * 60 * 1000) {
        let memOnly = false;
        try {
            if (JSON.stringify(data).length > SIZE_THRESHOLD) memOnly = true;
        } catch (_) { memOnly = true; }

        this.memCache[key] = { data, timestamp: Date.now(), expiry, _memOnly: memOnly };
        if (!memOnly) this._saveToStorage();
    }

    delete(key) {
        delete this.memCache[key];
        this._saveToStorage();
    }

    clear(prefix) {
        if (prefix) {
            for (const key of Object.keys(this.memCache)) {
                if (key.startsWith(prefix)) delete this.memCache[key];
            }
        } else {
            this.memCache = {};
        }
        this._saveToStorage();
    }

    getRemainingTime(key) {
        const item = this.memCache[key];
        if (!item) return 0;
        const remaining = item.expiry - (Date.now() - item.timestamp);
        return remaining > 0 ? remaining : 0;
    }

    has(key) { return this.get(key) !== null; }
}

const cacheManager = new CacheManager();
export default cacheManager;