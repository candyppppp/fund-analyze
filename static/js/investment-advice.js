import cacheManager from './cache-manager.js';

const ADVICE_TTL = 65 * 60 * 1000; // 65分钟，与后端 Supabase 缓存 60 分钟对齐

class InvestmentAdvice {
    constructor() {
        this.cacheKey = 'investmentAdvice';
        this._timer = null;
        this._startAutoRefresh();
    }

    // 判断是否交易时间（周一至周五 9:30-15:00，北京时间）
    _isTradingTime() {
        // 用 Asia/Shanghai 时区判断，避免用户设备时区影响
        const now = new Date();
        const bjStr = now.toLocaleString('en-US', { timeZone: 'Asia/Shanghai' });
        const bj = new Date(bjStr);
        const day = bj.getDay();
        const mins = bj.getHours() * 60 + bj.getMinutes();
        return day >= 1 && day <= 5 && mins >= 570 && mins < 900; // 9:30-15:00
    }

    // 启动定时刷新（用 setTimeout 链式调用，避免 setInterval 嵌套导致定时器泄漏）
    _startAutoRefresh() {
        if (this._timer) clearTimeout(this._timer);
        const schedule = () => {
            const interval = this._isTradingTime() ? 10 * 60 * 1000 : 60 * 60 * 1000;
            this._timer = setTimeout(() => {
                this._forceRefresh().finally(() => schedule()); // 请求完成后再安排下一次
            }, interval);
        };
        schedule();
    }

    // 强制刷新（绕过缓存，传 ?refresh=1），返回 Promise，带防并发锁
    _forceRefresh() {
        if (this._refreshing) return Promise.resolve(); // 防并发
        this._refreshing = true;
        const _lvl = (() => { try { return JSON.parse(localStorage.getItem('fundTrackerSettings') || '{}').investmentLevel || 'small'; } catch(e) { return 'small'; } })();
        return fetch('/api/investment-advice?refresh=1&level=' + _lvl)
            .then(r => r.ok ? r.json() : null)
            .then(a => {
                if (!a) return;
                const hasData = (a.holdingsAdvice && a.holdingsAdvice.length > 0) ||
                                (a.recommendedFunds && a.recommendedFunds.length > 0);
                if (hasData) {
                    if (!a._cache_time) a._cache_time = Date.now();
                    cacheManager.set(this.cacheKey, a, ADVICE_TTL);
                    if (window.activeTab === 'investment-advice') this.displayAdvice(a);
                }
            })
            .catch(() => {})
            .finally(() => {
                this._refreshing = false;
                // 恢复手动刷新按钮
                const btn = document.getElementById('ia-manual-refresh-btn');
                if (btn) { btn.textContent = '手动刷新数据'; btn.disabled = false; }
            });
    }

    loadInvestmentAdvice() {
        const _lvl = (() => { try { return JSON.parse(localStorage.getItem('fundTrackerSettings') || '{}').investmentLevel || 'small'; } catch(e) { return 'small'; } })();

        // 有缓存且有实质数据 → 立即展示，缓存剩余不足一半才后台刷新（不浪费请求）
        const cached = cacheManager.get(this.cacheKey);
        const cacheHasData = cached &&
            ((cached.holdingsAdvice && cached.holdingsAdvice.length > 0) ||
             (cached.recommendedFunds && cached.recommendedFunds.length > 0));

        if (cacheHasData) {
            if (window.activeTab === 'investment-advice') this.displayAdvice(cached);
            // 缓存剩余时间不足一半时才触发后台刷新，避免每次点击都发请求
            const remaining = cacheManager.getRemainingTime(this.cacheKey);
            const halfTTL = ADVICE_TTL / 2;
            if (remaining < halfTTL) this.updateInBackground();
            return;
        }

        // 无缓存：正常加载
        if (window.activeTab === 'investment-advice') this.showLoadingState();
        fetch('/api/investment-advice?level=' + _lvl)
            .then(r => { if (r.status === 401) { window.location.href='/login'; return Promise.reject('401'); } return r.json(); })
            .then(a => {
                const hasData = (a.holdingsAdvice && a.holdingsAdvice.length > 0) ||
                                (a.recommendedFunds && a.recommendedFunds.length > 0);
                if (hasData) {
                    // 优先使用后端返回的缓存时间（Supabase 缓存命中时），否则用当前时间
                    if (!a._cache_time) a._cache_time = Date.now();
                    cacheManager.set(this.cacheKey, a, ADVICE_TTL);
                }
                if (window.activeTab === 'investment-advice') this.displayAdvice(a);
            })
            .catch(e => { if (e !== '401' && window.activeTab === 'investment-advice') this.displayDefaultAdvice(); });
    }

    updateInBackground() {
        this._forceRefresh();
    }

    showLoadingState() {
        const c = document.getElementById('funds-container');
        if (!c) return;
        c.innerHTML = `<div style="display:flex;flex-direction:column;align-items:center;padding:80px 20px;color:#555;">
            <div style="width:32px;height:32px;border:3px solid #1e1e1e;border-top:3px solid #007bff;border-radius:50%;animation:ia-spin 1s linear infinite;margin-bottom:16px;"></div>
            <p style="margin:0;font-size:14px;color:#666;">正在分析基金数据，请稍候...</p>
            <p style="margin:8px 0 0;font-size:12px;color:#444;">预计需要 10–30 秒</p>
        </div><style>@keyframes ia-spin{to{transform:rotate(360deg)}}</style>`;
    }

    displayAdvice(advice) {
        const c = document.getElementById('funds-container');
        if (!c) return;

        const actionable  = (advice.holdingsAdvice || []).filter(i => !['持有'].includes(i.action));
        // 推荐基金去重：同一 code 可能因多次评分被重复推荐，保留第一次出现
        const _seenCodes = new Set();
        const recommended = (advice.recommendedFunds || []).filter(item => {
            if (!item.code || _seenCodes.has(item.code)) return false;
            _seenCodes.add(item.code);
            return true;
        });
        const now = new Date().toLocaleString('zh-CN',{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'});

        // 计算止盈建议（读 localStorage 持仓成本，纯前端计算）
        const takeProfitCards = this._calcTakeProfit(advice.holdingsAdvice || []);

        c.innerHTML = `
<style>
.ia{width:100%;box-sizing:border-box;padding:20px 0;}
.ia-sec{margin-bottom:32px;}
.ia-sec-hd{
    font-size:13px;font-weight:600;color:#999;
    margin-bottom:20px;padding-bottom:10px;
    border-bottom:1px solid #1a1a1a;
    display:flex;align-items:center;gap:8px;
    letter-spacing:.8px;text-transform:uppercase;
}
.ia-sec-hd .bar{width:3px;height:14px;border-radius:2px;flex-shrink:0;}
.ia-empty{
    color:#3a3a3a;padding:36px;text-align:center;
    background:#0d0d0d;border-radius:10px;
    border:1px dashed #1e1e1e;font-size:13px;
}

/* 卡片 */
.ia-card{
    background:#141414;
    border:1px solid #908e8e;
    border-radius:12px;
    padding:24px;
    margin-bottom:16px;
    transition:border-color .2s,box-shadow .2s;
}
.ia-card:hover{border-color:#908e8e;box-shadow:0 6px 24px rgba(0,0,0,.5);}

/* 标题行：基金名（代码）  徽章 */
.ia-card-hd{
    display:flex;justify-content:space-between;
    align-items:center;margin-bottom:20px;
}
.ia-fund-title{font-size:17px;font-weight:700;color:#e8e8e8;line-height:1.3;}
.ia-fund-title .code{color:#d6d1d1;font-weight:400;}
.ia-nav-date{font-size:11px;color:#939191;margin-top:5px;}

.ia-badge{padding:5px 16px;border-radius:20px;font-size:13px;font-weight:700;white-space:nowrap;letter-spacing:.3px;}
.ia-buy {background:rgba(220,53,69,.12);color:#dc3545;border:1px solid rgba(220,53,69,.3);}
.ia-sell{background:rgba(40,167,69,.12);color:#28a745;border:1px solid rgba(40,167,69,.3);}
.ia-new {background:rgba(0,123,255,.12);color:#007bff;border:1px solid rgba(0,123,255,.3);}

/* 指标格：两行6列 */
.ia-grid{
    display:grid;
    grid-template-columns:repeat(6,1fr);
    gap:10px;
    margin-bottom:20px;
}
.ia-cell{
    background:#0e0e0e;
    border:1px solid #7d7a7a;
    border-radius:8px;
    padding:13px 15px;
}
.ia-cell-lbl{font-size:11px;color:#444;margin-bottom:7px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.ia-cell-val{font-size:15px;font-weight:600;}

.pos {color:#dc3545;}
.neg {color:#28a745;}
.warn{color:#ffc107;}
.neu {color:#aaa;}

/* 分析依据 */
.ia-reason-box{
    background:#0c0c0c;
    border-left:3px solid #007bff;
    border-radius:0 6px 6px 0;
    padding:16px 18px;
    margin-bottom:16px;
}
.ia-reason-lbl{font-size:12px;color:#858484;letter-spacing:.8px;text-transform:uppercase;margin-bottom:10px;}
.ia-reason-txt{font-size:13px;line-height:1.95;color:#888;}

.ia-foot{display:flex;justify-content:space-between;font-size:12px;color:#7b7878;}

/* 推荐卡 */
.ia-rec-card{
    background:#141414;border:1px solid #908e8e;
    border-radius:12px;padding:22px 24px;
    margin-bottom:14px;transition:border-color .2s;
}
.ia-rec-card:hover{border-color:#908e8e;}
.ia-rec-hd{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;}
.ia-rec-name{font-size:15px;font-weight:600;color:#e0e0e0;}
.ia-rec-code{font-size:12px;color:#444;margin-top:4px;}
.ia-risk{font-size:11px;padding:3px 10px;border-radius:10px;}
.ia-add-btn{
    padding:6px 16px;
    background:rgba(0,123,255,.1);color:#007bff;
    border:1px solid rgba(0,123,255,.25);
    border-radius:6px;font-size:12px;cursor:pointer;transition:all .2s;
}
.ia-add-btn:hover{background:rgba(0,123,255,.2);}

@keyframes ia-up{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.ia-card,.ia-rec-card{animation:ia-up .3s ease both;}

@media(max-width:700px){
    .ia-grid{grid-template-columns:repeat(3,1fr);}
    .ia-fund-title{font-size:14px;}
}
</style>

<div class="ia">
  <!-- 投资建议 -->
  <div class="ia-sec">
    <div class="ia-sec-hd"><div class="bar" style="background:#007bff;"></div>投资建议</div>
    ${takeProfitCards.length > 0 ? takeProfitCards.join('') : ''}
    ${actionable.length > 0
        ? actionable.map((item, i) => this._card(item, takeProfitCards.length + i, now)).join('')
        : (takeProfitCards.length === 0 ? '<div class="ia-empty">当前无需操作，所有持仓均处于持有区间</div>' : '')}
  </div>

  <!-- 市场推荐 -->
  <div class="ia-sec">
    <div class="ia-sec-hd"><div class="bar" style="background:#17a2b8;"></div>推荐关注</div>
    ${recommended.length > 0
        ? recommended.map((item, i) => this._recCard(item, i)).join('')
        : '<div class="ia-empty">推荐引擎正在分析市场，请稍后刷新</div>'}
  </div>

  <div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0 16px;">
    <span style="font-size:11px;color:#3a3a3a;">
      最后更新时间 ${(() => {
        const ts = advice._cache_time;
        if (!ts) return '--';
        try {
          return new Date(ts).toLocaleString('zh-CN', {
            timeZone: 'Asia/Shanghai',
            year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit', second: '2-digit',
            hour12: false
          }).replace(/\//g, '-');
        } catch(e) { return '--'; }
      })()}
    </span>
    <button id="ia-manual-refresh-btn"
      onclick="window.investmentAdvice._forceRefresh();this.textContent='刷新中...';this.disabled=true;"
      style="font-size:12px;color:#555;background:transparent;border:1px solid #2a2a2a;border-radius:6px;padding:6px 16px;cursor:pointer;">
      手动刷新数据
    </button>
  </div>
</div>`;

        setTimeout(() => {
            document.querySelectorAll('.ia-add-btn').forEach(btn => {
                // once:true 确保每个按钮只绑定一次，防止重复渲染时重复绑定
                btn.addEventListener('click', () => {
                    btn.disabled = true;
                    btn.textContent = '添加中...';
                    window.addFundByCode(btn.dataset.code);
                }, { once: true });
            });
        }, 0);
    }

    _v(v, decimals, suffix='') {
        if (v === null || v === undefined) return '—';
        const n = Number(v);
        if (isNaN(n)) return '—';
        return decimals !== undefined ? n.toFixed(decimals) + suffix : String(v);
    }

    _pct(v) {
        // 带正负号的百分比
        if (v === null || v === undefined) return { txt:'—', cls:'neu' };
        const n = Number(v);
        if (isNaN(n)) return { txt:'—', cls:'neu' };
        const txt = (n>=0?'+':'') + n.toFixed(2) + '%';
        // 正值红色（A股涨红跌绿习惯）
        const cls = n > 0 ? 'pos' : n < 0 ? 'neg' : 'neu';
        return { txt, cls };
    }

    _card(item, index, now) {
        const d = item.indicators || {};
        const action = item.action;
        // badge 样式：建仓=蓝色，补仓/轻仓补入=红色，减仓/观望减持=绿色
        const badgeCls = (action === '建仓')          ? 'ia-new'
                       : (action === '补仓' || action === '轻仓补入') ? 'ia-buy'
                       : 'ia-sell';
        // 金额制展示：建议金额 / 预估净值 = 参考份额
        let badgeTxt = action;
        const isAddAction = action === '补仓' || action === '建仓' || action === '轻仓补入';
        if (isAddAction && item.suggest_amount > 0) {
            const estNav = item.est_nav_add || d.est_nav || d.nav || 0;
            const approxShares = estNav > 0 ? Math.floor(item.suggest_amount / estNav) : 0;
            badgeTxt = action + ' · ' + item.suggest_amount + '元'
                + (approxShares > 0 ? '（约' + approxShares + '份）' : '');
        }

        const macd = d.macd || [0,0,0];
        const macdUp = macd[0] > macd[1];
        const macdStr = macdUp ? (macd[2]>0 ? '金叉 ↑' : '多头') : (macd[2]<0 ? '死叉 ↓' : '空头');
        const macdCls = macdUp ? 'pos' : 'neg';

        const rsi = d.rsi ?? 50;
        const rsiCls = rsi < 35 ? 'neg' : rsi > 65 ? 'pos' : 'neu';   // 超卖(低)=机会=红，超买(高)=风险=绿

        const jv = d.kdj_j ?? 50;
        const jCls = jv > 80 ? 'pos' : jv < 20 ? 'neg' : 'neu';

        const bp = d.bb_pos;
        const bpCls = bp !== null && bp !== undefined ? (bp > 70 ? 'pos' : bp < 30 ? 'neg' : 'neu') : 'neu';

        const vol = d.volatility ?? 0;
        const volCls = vol > 15 ? 'pos' : vol > 8 ? 'warn' : 'neg';

        const p1w = this._pct(d.chg_1w);
        const p2w = this._pct(d.chg_2w);
        const p4w = this._pct(d.chg_4w);
        const pe  = this._pct(d.est_return);

        const cells = [
            // 行一
            { lbl:'最新净值',   val: this._v(d.nav, 4),    cls:'neu' },
            { lbl: d.has_realtime ? '预估净值 · 实时' : '预估净值 · 估算',
              val: this._v(d.est_nav, 4), cls:'neu' },
            { lbl: d.has_realtime
                    ? '预估收益率 · 实时'
                    : '预估收益率 · 估算',
              val: pe.txt, cls: pe.cls },
            { lbl:'近1周涨跌',  val: p1w.txt,               cls: p1w.cls },
            { lbl:'近2周涨跌',  val: p2w.txt,               cls: p2w.cls },
            { lbl:'近4周涨跌',  val: p4w.txt,               cls: p4w.cls },
            // 行二
            { lbl:'RSI(14)',    val: this._v(rsi, 1),                                      cls: rsiCls },
            { lbl:'KDJ-K',     val: this._v(d.kdj_k, 1),                                  cls: 'neu'  },
            { lbl:'KDJ-D',     val: this._v(d.kdj_d, 1),                                  cls: 'neu'  },
            { lbl:'KDJ-J',     val: this._v(jv, 1),                                       cls: jCls   },
            { lbl:'布林带位置', val: bp !== null && bp !== undefined ? this._v(bp,0)+'%' : '—', cls: bpCls },
            { lbl:'年化波动率', val: this._v(vol, 1) + '%',                                cls: volCls },
        ];

        return `
<div class="ia-card" style="animation-delay:${index*0.07}s">

  <!-- 标题行 -->
  <div class="ia-card-hd">
    <div>
      <div class="ia-fund-title">
        ${item.fundName}
        <span class="code">( ${item.fundCode} )</span>
      </div>
      ${d.nav_date ? `<div class="ia-nav-date">净值日期 ${d.nav_date}</div>` : ''}
    </div>
    <span class="ia-badge ${badgeCls}">${badgeTxt}</span>
  </div>

  <!-- 指标格 -->
  <div class="ia-grid">
    ${cells.map(cell => `
      <div class="ia-cell">
        <div class="ia-cell-lbl">${cell.lbl}</div>
        <div class="ia-cell-val ${cell.cls}">${cell.val}</div>
      </div>`).join('')}
  </div>

  <!-- 分析依据 -->
  <div class="ia-reason-box">
    <div class="ia-reason-lbl">分析依据</div>
    <div class="ia-reason-txt">${item.reason}</div>
  </div>

  <!-- 底部 -->
  <div class="ia-foot">
    <span>数据更新：${now}</span>
    <span>置信度 ${d.prediction_confidence ?? 50}%</span>
  </div>

</div>`;
    }

    _calcTakeProfit(holdingsAdvice) {
        /**
         * 综合止盈判断 — 不依赖固定阈值，而是多维度打分决策
         *
         * 考量维度：
         *  1. 累计收益率（浮盈）
         *  2. 近期趋势是否反转（近5/10日净值变化）
         *  3. RSI 是否超买
         *  4. 布林带是否突破上轨
         *  5. MACD 是否死叉
         *  6. 波动率是否骤升（止盈时机往往在波动放大前）
         *
         * 每项指标给出"止盈压力分"，综合评分决定是否提示及力度。
         * 避免：仅凭收益率阈值或仅凭技术面单独判断。
         */
        const cards = [];
        const now = new Date().toLocaleString('zh-CN',{
            year:'numeric',month:'2-digit',day:'2-digit',
            hour:'2-digit',minute:'2-digit',second:'2-digit'
        });

        holdingsAdvice.forEach((item, i) => {
            try {
                const records = this._getBuyRecordsByCode(item.fundCode);
                if (!records || records.length === 0) return;

                // 净持仓 = 买入份数总和 + 卖出份数总和（卖出为负数）
                let totalShares = 0;
                let buyShares = 0, buyCost = 0;
                records.forEach(r => {
                    totalShares += r.shares;
                    if (r.shares > 0) { // 只用买入记录计算成本
                        buyShares += r.shares;
                        buyCost   += r.shares * r.nav;
                    }
                });
                if (totalShares <= 0 || buyCost <= 0 || buyShares <= 0) return; // 已全部卖出则跳过

                const avgCost = buyCost / buyShares; // 平均买入成本
                const d         = item.indicators || {};
                const currentNav = (d.has_realtime && d.est_nav) ? d.est_nav : (d.nav || 0);
                if (!currentNav || !avgCost) return;

                const gainPct    = (currentNav - avgCost) / avgCost * 100;
                const totalValue  = totalShares * currentNav;
                const totalProfit = totalValue - buyCost;

                // ── 综合止盈打分 ─────────────────────────────────────────
                // 每项最高贡献若干分，总分 >= 40 提示，>= 70 强烈提示
                let score = 0;
                const signals = [];  // 记录触发的信号，用于分析依据文字

                // 1. 累计收益率
                if (gainPct >= 5) {
                    const gainScore = Math.min(40, Math.floor(gainPct / 20 * 40));
                    score += gainScore;
                    signals.push({ label: '基金收益', desc: `浮盈 +${gainPct.toFixed(2)}%，已形成较好的安全垫`, weight: gainScore });
                }

                // 2. MACD
                const macd = d.macd || [0, 0, 0];
                const macdLine = macd[0], signalLine = macd[1], histogram = macd[2];
                if (macdLine < signalLine && histogram < 0) {
                    score += 15;
                    signals.push({ label: 'MACD', desc: `DIF=${macdLine.toFixed(4)} 下穿 DEA=${signalLine.toFixed(4)}，动能转弱`, weight: 15 });
                } else if (macdLine < signalLine) {
                    score += 8;
                    signals.push({ label: 'MACD', desc: `DIF=${macdLine.toFixed(4)} 位于 DEA=${signalLine.toFixed(4)} 下方，上行动能收敛`, weight: 8 });
                }

                // 3. RSI
                const rsi = d.rsi || 50;
                if (rsi > 75) {
                    score += 15;
                    signals.push({ label: 'RSI', desc: `RSI ${rsi.toFixed(1)}，严重超买，回调风险显著`, weight: 15 });
                } else if (rsi > 65) {
                    score += 8;
                    signals.push({ label: 'RSI', desc: `RSI ${rsi.toFixed(1)}，处于偏热区间，注意短线压力`, weight: 8 });
                }

                // 4. 布林带
                const bb = d.bollinger_bands || [0, 0, 0];
                const bbU = bb[0], bbM = bb[1], bbL = bb[2];
                if (currentNav && bbU && currentNav > bbU) {
                    score += 15;
                    signals.push({ label: '布林带', desc: `净值 ${currentNav.toFixed(4)} 超过上轨 ${bbU.toFixed(4)}，短期偏强但易回踩`, weight: 15 });
                } else if (d.bb_pos && d.bb_pos > 80) {
                    score += 8;
                    signals.push({ label: '布林带', desc: `布林带位置 ${d.bb_pos.toFixed(0)}%，净值运行于上方区域，回调风险上升`, weight: 8 });
                }

                // 5. 波动率
                const vol = d.volatility || 0;
                if (vol > 20) {
                    score += 10;
                    signals.push({ label: '波动率', desc: `年化波动率（${vol.toFixed(1)}%）偏高，市场不确定性上升，止盈可锁定收益`, weight: 10 });
                } else if (vol > 12) {
                    score += 5;
                    signals.push({ label: '波动率', desc: `年化波动率（${vol.toFixed(1)}%）中等偏高，宜保持警惕`, weight: 5 });
                }

                // 6. KDJ
                const kdjJ = d.kdj_j;
                if (kdjJ !== null && kdjJ !== undefined && kdjJ > 85) {
                    score += 5;
                    signals.push({ label: 'KDJ', desc: `J值（${kdjJ.toFixed(1)}）严重超买，短线回调概率较高`, weight: 5 });
                }

                // ── 判断是否触发止盈 ─────────────────────────────────────
                // 总分 >= 40 且浮盈 >= 3% → 提示止盈（避免微利触发）
                // 总分 >= 70 且浮盈 >= 5% → 强烈止盈
                if (score < 40 || gainPct < 3) return;

                const isStrong    = score >= 70 && gainPct >= 5;
                const badgeColor  = isStrong ? '#dc3545' : '#ffc107';
                const badgeBg     = isStrong ? 'rgba(220,53,69,.12)' : 'rgba(255,193,7,.1)';
                const badgeBorder = isStrong ? 'rgba(220,53,69,.3)'  : 'rgba(255,193,7,.25)';

                // 生成建议文字
                const signalDesc = signals.map(s => s.label).join('、');
                let adviceText = '';
                if (isStrong) {
                    adviceText = `综合评分 ${score} 分（满分100），多项指标同时触发（${signalDesc}），止盈压力较强。`
                        + `建议考虑卖出 50%~100% 仓位，锁定 +${gainPct.toFixed(2)}% 收益（约 +${totalProfit.toFixed(2)} 元）。`
                        + '剩余仓位可设置跟踪止盈，如净值回落超过 3% 则继续清仓。';
                } else {
                    adviceText = `综合评分 ${score} 分，触发止盈信号（${signalDesc}）。`
                        + `当前浮盈 +${gainPct.toFixed(2)}%（+${totalProfit.toFixed(2)} 元），`
                        + '建议考虑部分止盈（30%~50% 仓位），保留剩余仓位继续观察。'
                        + '若后续技术面继续走弱，可进一步减仓。';
                }

                // 各维度信号列表
                const signalRows = signals.map(s =>
                    '<div style="display:grid;grid-template-columns:72px 1fr 44px;align-items:center;padding:6px 0;border-bottom:1px solid #1a1a1a;gap:8px;">' +
                    '<span style="color:#888;font-size:12px;white-space:nowrap;">' + s.label + '</span>' +
                    '<span style="color:#aaa;font-size:12px;text-align:left;">' + s.desc + '</span>' +
                    '<span style="color:' + badgeColor + ';font-weight:600;font-size:12px;text-align:right;">+' + s.weight + '分</span>' +
                    '</div>'
                ).join('');

                cards.push(
                    '<div class="ia-card" style="animation-delay:' + (i * 0.06) + 's;border-left:3px solid ' + badgeColor + ';">' +
                    '<div class="ia-card-hd">' +
                    '<div>' +
                    '<div class="ia-fund-title">' + item.fundName + ' <span class="code">( ' + item.fundCode + ' )</span></div>' +
                    '<div class="ia-nav-date">持仓 ' + totalShares.toFixed(2) + ' 份 · 均价 ' + avgCost.toFixed(4) + ' 元 · 评分 ' + score + '/100</div>' +
                    '</div>' +
                    '<span class="ia-badge" style="background:' + badgeBg + ';color:' + badgeColor + ';border:1px solid ' + badgeBorder + ';">' +
                    (isStrong ? '⚡ 强烈止盈' : '止盈提醒') + '</span>' +
                    '</div>' +

                    '<div class="ia-grid" style="grid-template-columns:repeat(4,1fr);margin-bottom:14px;">' +
                    '<div class="ia-cell"><div class="ia-cell-lbl">持仓均价</div><div class="ia-cell-val neu">' + avgCost.toFixed(4) + '</div></div>' +
                    '<div class="ia-cell"><div class="ia-cell-lbl">' + (d.has_realtime ? '预估净值' : '最新净值') + '</div><div class="ia-cell-val neu">' + currentNav.toFixed(4) + '</div></div>' +
                    '<div class="ia-cell"><div class="ia-cell-lbl">累计收益率</div><div class="ia-cell-val pos">+' + gainPct.toFixed(2) + '%</div></div>' +
                    '<div class="ia-cell"><div class="ia-cell-lbl">浮动盈亏</div><div class="ia-cell-val pos">+' + totalProfit.toFixed(2) + '元</div></div>' +
                    '</div>' +

                    '<div style="background:#0c0c0c;border-radius:6px;padding:12px 14px;margin-bottom:14px;">' +
                    '<div style="font-size:10px;color:#858484;letter-spacing:.8px;text-transform:uppercase;margin-bottom:10px;">触发信号明细</div>' +
                    signalRows +
                    '</div>' +

                    '<div class="ia-reason-box">' +
                    '<div class="ia-reason-lbl">止盈建议</div>' +
                    '<div class="ia-reason-txt">' + adviceText + '</div>' +
                    '</div>' +

                    '<div class="ia-foot"><span>数据更新：' + now + '</span><span>综合评分 ' + score + '/100</span></div>' +
                    '</div>'
                );
            } catch(e) {
                console.warn('止盈计算失败:', item.fundCode, e);
            }
        });
        return cards;
    }

    _getBuyRecordsByCode(fundCode) {
        // 优先读云端缓存（fetchAllBuyRecords 已在页面加载时预热）
        try {
            if (window._cloudBuyRecords) {
                return window._cloudBuyRecords.filter(r =>
                    r.fund_code === fundCode || String(r.fund_id) === String(
                        window._fundIdCodeMap ? Object.keys(window._fundIdCodeMap).find(
                            k => window._fundIdCodeMap[k] === fundCode
                        ) : null
                    )
                );
            }
        } catch(e) {}

        // 降级：读 localStorage
        try {
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (!key || !key.startsWith('fundBuyRecords_')) continue;
                const records = JSON.parse(localStorage.getItem(key) || '[]');
                if (!records || records.length === 0) continue;
                const fundId = key.replace('fundBuyRecords_', '');
                if (window._fundIdCodeMap && window._fundIdCodeMap[fundId] === fundCode) {
                    return records;
                }
            }
        } catch(e) {}
        return [];
    }

    _recCard(item, index) {
        const score  = item.score || 0;
        const riskC  = item.riskLevel === '稳健型' ? '#17a2b8' : '#ffc107';
        // 评分进度条宽度（满分100，最大60px）
        const barW = Math.min(Math.max(score, 0), 100) * 0.6;
        return `
<div class="ia-rec-card" style="animation-delay:${index*0.06}s">
  <!-- 标题行：基金名（代码）  风险标签 -->
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;">
    <div>
      <div style="font-size:15px;font-weight:700;color:#f6f4f4;line-height:1.3;">
        ${item.name}
        <span style="color:#d6d1d1;font-weight:400;font-size:13px;">( ${item.code} )</span>
      </div>
    </div>
    <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px;flex-shrink:0;margin-left:12px;">
      <span style="font-size:11px;padding:3px 10px;border-radius:10px;
        background:${riskC}18;color:${riskC};border:1px solid ${riskC}30;white-space:nowrap;">
        ${item.riskLevel||'均衡型'}
      </span>
      ${score > 0 ? `
      <div style="display:flex;align-items:center;gap:6px;">
        <span style="font-size:10px;color:#444;">评分</span>
        <div style="height:3px;width:${barW}px;background:#007bff;border-radius:2px;"></div>
        <span style="font-size:11px;color:#888;">${score.toFixed(0)}</span>
      </div>` : ''}
    </div>
  </div>

  <!-- 推荐理由 -->
  <div class="ia-reason-box" style="margin-bottom:14px;">
    <div class="ia-reason-lbl">推荐理由</div>
    <div class="ia-reason-txt">${item.reason}</div>
  </div>

  <!-- 底部操作 -->
  <div style="display:flex;justify-content:flex-end;">
    <button class="ia-add-btn" data-code="${item.code}">＋ 加入自选</button>
  </div>
</div>`;
    }

    displayDefaultAdvice() {
        const c = document.getElementById('funds-container');
        if (c) c.innerHTML = '<div style="padding:40px;text-align:center;color:#444;font-size:13px;">获取投资建议失败，请稍后重试</div>';
    }
}

export default InvestmentAdvice;