// blogger-tracker.js v3 — 博主追踪分析报告
// 修复：renderFunds guard 防止覆盖内容
// 新增：完整分析报告页面

class BloggerTracker {
    constructor() {
        this._signals     = [];
        this._myFundCodes = [];
        this._currentRange  = '7D';
        this._currentAction = '';
    }

    show() {
        const container = document.getElementById('funds-container');
        if (!container) return;
        ['fund-list-header','fund-list-subheader'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.display = 'none';
        });
        const searchBar = document.querySelector('.search-container');
        if (searchBar) searchBar.style.display = 'none';

        this._renderShell(container);
        this._loadMyFundCodes();
        this._loadAndRender();
    }

    hide() {
        const searchBar = document.querySelector('.search-container');
        if (searchBar) searchBar.style.display = '';
        ['fund-list-header','fund-list-subheader'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.display = '';
        });
    }

    _loadMyFundCodes() {
        fetch('/api/funds?basic=true')
            .then(r => r.ok ? r.json() : [])
            .then(funds => { this._myFundCodes = (funds||[]).map(f => String(f.code)); })
            .catch(() => {});
    }

    _loadAndRender() {
        const days = this._currentRange === '1D' ? 1 : this._currentRange === '3D' ? 3 : 7;
        const el = document.getElementById('bt-loading');
        if (el) el.style.display = 'flex';
        const main = document.getElementById('bt-main');
        if (main) main.style.display = 'none';

        fetch('/api/blogger-signals?days=' + days)
            .then(r => r.ok ? r.json() : [])
            .then(data => {
                this._signals = data || [];
                window._bloggerSignals = this._signals;
                if (el) el.style.display = 'none';
                if (main) main.style.display = 'block';
                if (this._signals.length > 0) {
                    this._renderReport();
                } else {
                    this._renderEmpty();
                }
            })
            .catch(() => {
                if (el) el.style.display = 'none';
                this._renderEmpty();
            });
    }

    _renderShell(container) {
        container.innerHTML = `
<div id="bt-root">
<style>
#bt-root{font-family:-apple-system,BlinkMacSystemFont,'SF Pro Display',sans-serif;color:#e0e0e0;padding:0}
#bt-root *{box-sizing:border-box}
.bt-header{padding:16px 20px 0;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:14px}
.bt-title{font-size:18px;font-weight:600;color:#fff;letter-spacing:-.3px}
.bt-meta{font-size:11px;color:#444;margin-top:2px}
.bt-controls{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.bt-seg{display:flex;background:#1e1e1e;border-radius:7px;padding:2px;gap:1px;border:0.5px solid #2a2a2a}
.bt-seg-btn{padding:4px 12px;border-radius:5px;font-size:11px;font-weight:500;cursor:pointer;border:none;background:transparent;color:#555;transition:all .15s}
.bt-seg-btn.on{background:#2a2a2a;color:#e0e0e0}
.bt-action-seg{display:flex;gap:4px}
.bt-action-btn{padding:4px 10px;border-radius:5px;font-size:11px;cursor:pointer;border:0.5px solid #2a2a2a;background:#1a1a1a;color:#555;transition:all .15s}
.bt-action-btn.on{background:#2a2a2a;color:#e0e0e0;border-color:#3a3a3a}
.bt-upload-bar{margin:0 20px 14px;padding:10px 14px;background:#1a1a1a;border:0.5px dashed #2a2a2a;border-radius:8px;display:flex;align-items:center;gap:10px;cursor:pointer;transition:border-color .15s}
.bt-upload-bar:hover{border-color:#3a3a3a}
.bt-upload-icon{font-size:16px;flex-shrink:0}
.bt-upload-text{font-size:11px;color:#555}
.bt-upload-msg{font-size:11px;padding:6px 14px;margin:0 20px 10px;background:#1e1e1e;border-radius:6px;display:none}

/* Loading */
#bt-loading{display:flex;align-items:center;justify-content:center;height:200px;gap:10px}
.bt-spinner{width:20px;height:20px;border:2px solid #2a2a2a;border-top-color:#007bff;border-radius:50%;animation:bt-spin .8s linear infinite}
@keyframes bt-spin{to{transform:rotate(360deg)}}

/* Stats row */
.bt-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding:0 20px;margin-bottom:14px}
.bt-stat-card{background:#1a1a1a;border:0.5px solid #222;border-radius:10px;padding:12px 14px}
.bt-stat-val{font-size:22px;font-weight:700;letter-spacing:-.5px;line-height:1}
.bt-stat-lbl{font-size:11px;color:#444;margin-top:4px}
.bt-stat-sub{font-size:11px;color:#555;margin-top:2px}

/* Section */
.bt-section{padding:0 20px;margin-bottom:16px}
.bt-section-title{font-size:11px;font-weight:600;color:#444;letter-spacing:.8px;text-transform:uppercase;margin-bottom:10px;display:flex;align-items:center;gap:8px}
.bt-section-title::after{content:'';flex:1;height:0.5px;background:#1e1e1e}

/* Donut row */
.bt-donuts{display:flex;gap:10px;flex-wrap:wrap}
.bt-donut-card{flex:1;min-width:150px;background:#1a1a1a;border:0.5px solid #222;border-radius:10px;padding:14px}
.bt-donut-head{font-size:11px;font-weight:500;margin-bottom:10px}
.bt-donut-inner{display:flex;align-items:center;gap:12px}
.bt-donut-legend{flex:1;overflow:hidden}
.bt-legend-item{display:flex;align-items:center;gap:5px;margin-bottom:3px;overflow:hidden}
.bt-legend-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.bt-legend-name{font-size:10px;color:#888;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}
.bt-legend-val{font-size:10px;color:#444;margin-left:auto;flex-shrink:0}

/* Top funds */
.bt-top-grid{display:grid;gap:4px}
.bt-top-row{display:grid;grid-template-columns:28px 1fr 44px 44px 44px 36px;gap:6px;align-items:center;padding:7px 10px;border-radius:7px;transition:background .1s}
.bt-top-row:hover{background:#1e1e1e}
.bt-top-idx{font-size:11px;color:#333;text-align:right;font-variant-numeric:tabular-nums}
.bt-top-rank-1{color:#ffc107}
.bt-top-rank-2{color:#888}
.bt-top-rank-3{color:#cd7f32}
.bt-top-name{overflow:hidden}
.bt-top-fname{font-size:12px;color:#ddd;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bt-top-fcode{font-size:10px;color:#333;font-family:monospace;margin-top:1px}
.bt-top-bar-wrap{position:relative;height:3px;background:#1e1e1e;border-radius:2px;margin-top:3px}
.bt-top-bar{height:100%;border-radius:2px;background:linear-gradient(90deg,#dc3545,#ff6b6b)}
.bt-top-stat{font-size:11px;text-align:center;font-variant-numeric:tabular-nums}
.bt-buy-c{color:#dc3545}.bt-sell-c{color:#28a745}.bt-dip-c{color:#ffc107}.bt-bl-c{color:#555}
.bt-mine-tag{display:inline-block;font-size:9px;padding:0 3px;border-radius:2px;background:rgba(0,123,255,.2);color:#4a9eff;margin-left:4px;vertical-align:middle}
.bt-mine-row{background:rgba(0,123,255,.04)!important;border-left:2px solid rgba(0,123,255,.3)}

/* Blogger heat */
.bt-blogger-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:6px}
.bt-blogger-card{background:#1a1a1a;border:0.5px solid #222;border-radius:8px;padding:10px 12px}
.bt-blogger-name{font-size:12px;color:#ccc;margin-bottom:6px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bt-blogger-bar-wrap{height:24px;background:#111;border-radius:4px;overflow:hidden;display:flex}
.bt-blogger-seg{height:100%;transition:width .3s;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:600;color:rgba(255,255,255,.8);overflow:hidden;min-width:0}
.bt-blogger-meta{display:flex;justify-content:space-between;margin-top:5px;font-size:10px;color:#333}

/* Detail table */
.bt-detail-date{font-size:12px;font-weight:600;color:#007bff;padding:10px 0 5px;border-bottom:0.5px solid #1e1e1e;margin-bottom:4px}
.bt-detail-topic{font-size:10px;color:#333;letter-spacing:.4px;padding:5px 0 2px}
.bt-detail-hd{display:grid;grid-template-columns:88px 46px 62px 1fr 60px 48px;gap:5px;padding:3px 8px;font-size:10px;color:#333}
.bt-detail-row{display:grid;grid-template-columns:88px 46px 62px 1fr 60px 48px;gap:5px;align-items:center;padding:6px 8px;border-radius:5px;font-size:11px;transition:background .1s}
.bt-detail-row:hover{background:#1e1e1e}
.bt-detail-mine{border-left:2px solid rgba(0,123,255,.4)}

/* Empty */
.bt-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:60px 20px;color:#333}
.bt-empty-icon{font-size:40px;margin-bottom:12px;opacity:.4}
.bt-empty-text{font-size:13px}

/* Trend bar chart */
.bt-trend-wrap{display:flex;gap:3px;align-items:flex-end;height:60px}
.bt-trend-col{flex:1;display:flex;flex-direction:column;gap:1px;align-items:center}
.bt-trend-bar{width:100%;border-radius:2px 2px 0 0;min-height:2px;transition:height .3s}
.bt-trend-lbl{font-size:9px;color:#333;margin-top:3px;white-space:nowrap}
</style>

<div class="bt-header">
  <div>
    <div class="bt-title">博主追踪 · 分析报告</div>
    <div class="bt-meta" id="bt-meta-info">加载中...</div>
  </div>
  <div class="bt-controls">
    <div class="bt-seg">
      <button class="bt-seg-btn${this._currentRange==='1D'?' on':''}" data-range="1D">1D</button>
      <button class="bt-seg-btn${this._currentRange==='3D'?' on':''}" data-range="3D">3D</button>
      <button class="bt-seg-btn${this._currentRange==='7D'?' on':''}" data-range="7D">7D</button>
    </div>
    <div class="bt-action-seg">
      <button class="bt-action-btn${this._currentAction===''?' on':''}" data-action="">全部</button>
      <button class="bt-action-btn${this._currentAction==='买入'?' on':''}" data-action="买入">买入</button>
      <button class="bt-action-btn${this._currentAction==='卖出'?' on':''}" data-action="卖出">卖出</button>
      <button class="bt-action-btn${this._currentAction==='定投'?' on':''}" data-action="定投">定投</button>
    </div>
  </div>
</div>

<div class="bt-upload-bar" id="bt-upload-bar" onclick="document.getElementById('bt-file-input-main').click()">
  <span class="bt-upload-icon">📂</span>
  <span class="bt-upload-text">上传博主实盘 xlsx（主题/博主/操作/金额/基金名称/基金代码）</span>
  <input type="file" id="bt-file-input-main" accept=".xlsx,.xls" style="display:none">
</div>
<div class="bt-upload-msg" id="bt-upload-msg-main"></div>

<div id="bt-loading" style="display:flex"><div class="bt-spinner"></div><span style="font-size:12px;color:#333">加载数据中...</span></div>
<div id="bt-main" style="display:none"></div>
</div>`;

        // 事件绑定
        document.getElementById('bt-file-input-main').addEventListener('change', e => {
            const f = e.target.files[0];
            if (f) this._parseAndUpload(f, document.getElementById('bt-upload-msg-main'));
            e.target.value = '';
        });

        const bar = document.getElementById('bt-upload-bar');
        bar.addEventListener('dragover', e => { e.preventDefault(); bar.style.borderColor = '#007bff'; });
        bar.addEventListener('dragleave', () => { bar.style.borderColor = ''; });
        bar.addEventListener('drop', e => {
            e.preventDefault(); bar.style.borderColor = '';
            const f = e.dataTransfer.files[0];
            if (f) this._parseAndUpload(f, document.getElementById('bt-upload-msg-main'));
        });

        document.getElementById('bt-root').addEventListener('click', e => {
            const rb = e.target.closest('[data-range]');
            if (rb && rb.classList.contains('bt-seg-btn')) {
                this._currentRange = rb.dataset.range;
                this.show(); return;
            }
            const ab = e.target.closest('[data-action]');
            if (ab && ab.classList.contains('bt-action-btn')) {
                this._currentAction = ab.dataset.action;
                this._renderReport();
            }
        });
    }

    _renderEmpty() {
        const main = document.getElementById('bt-main');
        if (!main) return;
        main.innerHTML = `<div class="bt-empty">
            <div class="bt-empty-icon">📊</div>
            <div class="bt-empty-text">暂无数据，请上传博主实盘 xlsx 文件</div>
        </div>`;
        main.style.display = 'block';
    }

    _renderReport() {
        const main = document.getElementById('bt-main');
        if (!main) return;

        const data = this._currentAction
            ? this._signals.filter(r => r.action === this._currentAction)
            : this._signals;

        const COLORS = ['#3b82f6','#ef4444','#f59e0b','#10b981','#8b5cf6','#f97316','#06b6d4','#ec4899','#84cc16','#6366f1'];

        // ── 数据聚合 ────────────────────────────────────────────────────
        const totalBuy  = data.filter(r => r.action === '买入').length;
        const totalSell = data.filter(r => r.action === '卖出').length;
        const totalDip  = data.filter(r => r.action === '定投').length;
        const bloggerSet = new Set(data.map(r => r.blogger_name));
        const fundSet    = new Set(data.map(r => r.fund_code));
        const dateSet    = new Set(data.map(r => r.date));

        // 更新 meta
        const meta = document.getElementById('bt-meta-info');
        if (meta) {
            const dates = [...dateSet].sort();
            meta.textContent = `${dates[0] || ''} ${dates.length > 1 ? '~ ' + dates[dates.length-1] : ''} · ${bloggerSet.size} 位博主 · ${fundSet.size} 只基金`;
        }

        // 主题统计
        const topicMap = {};
        data.forEach(r => {
            const t = r.topic || '其他';
            if (!topicMap[t]) topicMap[t] = { buy: 0, sell: 0, dip: 0 };
            if (r.action === '买入') topicMap[t].buy++;
            else if (r.action === '卖出') topicMap[t].sell++;
            else topicMap[t].dip++;
        });
        const topicSorted = Object.entries(topicMap).sort((a,b) => (b[1].buy+b[1].sell+b[1].dip) - (a[1].buy+a[1].sell+a[1].dip));

        // 基金统计
        const fundMap = {};
        data.forEach(r => {
            if (!fundMap[r.fund_code]) fundMap[r.fund_code] = { code: r.fund_code, name: r.fund_name, topic: r.topic, buy: 0, sell: 0, dip: 0, bloggers: new Set() };
            if (r.action === '买入') fundMap[r.fund_code].buy++;
            else if (r.action === '卖出') fundMap[r.fund_code].sell++;
            else fundMap[r.fund_code].dip++;
            fundMap[r.fund_code].bloggers.add(r.blogger_name);
        });
        const fundsSorted = Object.values(fundMap).map(f => ({ ...f, bloggers: f.bloggers.size, total: f.buy + f.sell + f.dip })).sort((a,b) => b.buy - a.buy || b.total - a.total);
        const maxBuy = fundsSorted[0]?.buy || 1;

        // 博主统计
        const bloggerMap = {};
        data.forEach(r => {
            if (!bloggerMap[r.blogger_name]) bloggerMap[r.blogger_name] = { buy: 0, sell: 0, dip: 0, funds: new Set() };
            if (r.action === '买入') bloggerMap[r.blogger_name].buy++;
            else if (r.action === '卖出') bloggerMap[r.blogger_name].sell++;
            else bloggerMap[r.blogger_name].dip++;
            bloggerMap[r.blogger_name].funds.add(r.fund_code);
        });
        const bloggersSorted = Object.entries(bloggerMap).map(([n,s]) => ({ name: n, ...s, funds: s.funds.size, total: s.buy + s.sell + s.dip })).sort((a,b) => b.total - a.total);

        // 日期趋势
        const dateMap = {};
        data.forEach(r => {
            if (!dateMap[r.date]) dateMap[r.date] = { buy: 0, sell: 0, dip: 0 };
            if (r.action === '买入') dateMap[r.date].buy++;
            else if (r.action === '卖出') dateMap[r.date].sell++;
            else dateMap[r.date].dip++;
        });
        const dateTrend = Object.entries(dateMap).sort((a,b) => a[0].localeCompare(b[0]));
        const maxDay = Math.max(...dateTrend.map(([,v]) => v.buy + v.sell + v.dip), 1);

        // ── 生成 donut SVG ───────────────────────────────────────────────
        const donut = (items, field, color, title) => {
            const filtered = items.filter(([,s]) => s[field] > 0).slice(0, 8);
            if (!filtered.length) return '';
            const total = filtered.reduce((s,[,v]) => s + v[field], 0);
            const R = 36, cx = 40, cy = 40, sw = 12, circ = 2 * Math.PI * R;
            let off = 0;
            const slices = filtered.map(([t,s], i) => {
                const pct = s[field] / total;
                const d = pct * circ;
                const slice = `<circle cx="${cx}" cy="${cy}" r="${R}" fill="none" stroke="${COLORS[i%10]}"
                    stroke-width="${sw}" stroke-dasharray="${d.toFixed(1)} ${(circ-d).toFixed(1)}"
                    stroke-dashoffset="${(-(off / total) * circ).toFixed(1)}" transform="rotate(-90 ${cx} ${cy})"/>`;
                off += s[field]; return slice;
            }).join('');
            const legend = filtered.slice(0, 6).map(([t,s], i) => `
                <div class="bt-legend-item">
                    <div class="bt-legend-dot" style="background:${COLORS[i%10]}"></div>
                    <span class="bt-legend-name">${t}</span>
                    <span class="bt-legend-val">${s[field]}</span>
                </div>`).join('');
            return `<div class="bt-donut-card">
                <div class="bt-donut-head" style="color:${color}">${title}</div>
                <div class="bt-donut-inner">
                    <svg viewBox="0 0 80 80" style="width:70px;height:70px;flex-shrink:0">
                        <circle cx="${cx}" cy="${cy}" r="${R}" fill="none" stroke="#111" stroke-width="${sw}"/>
                        ${slices}
                        <text x="${cx}" y="${cy}" text-anchor="middle" dominant-baseline="middle" fill="#666" font-size="11" font-weight="600">${total}</text>
                    </svg>
                    <div class="bt-donut-legend">${legend}</div>
                </div>
            </div>`;
        };

        // ── Top20 行 ─────────────────────────────────────────────────────
        const top20Rows = fundsSorted.slice(0, 20).map((f, i) => {
            const mine = this._myFundCodes.includes(String(f.code));
            const bw = Math.round(f.buy / maxBuy * 100);
            const rankStyle = i === 0 ? 'bt-top-rank-1' : i === 1 ? 'bt-top-rank-2' : i === 2 ? 'bt-top-rank-3' : '';
            return `<div class="bt-top-row${mine ? ' bt-mine-row' : ''}">
                <span class="bt-top-idx ${rankStyle}">${i < 3 ? ['🥇','🥈','🥉'][i] : i+1}</span>
                <div class="bt-top-name">
                    <div class="bt-top-fname">${f.name}${mine ? '<span class="bt-mine-tag">自选</span>' : ''}</div>
                    <div class="bt-top-fcode">${f.code}
                        <span style="color:#2a2a2a;margin-left:4px">${f.topic||''}</span>
                    </div>
                    <div class="bt-top-bar-wrap"><div class="bt-top-bar" style="width:${bw}%"></div></div>
                </div>
                <span class="bt-top-stat bt-buy-c">${f.buy ? f.buy+'买' : ''}</span>
                <span class="bt-top-stat bt-sell-c">${f.sell ? f.sell+'卖' : ''}</span>
                <span class="bt-top-stat bt-dip-c">${f.dip ? f.dip+'投' : ''}</span>
                <span class="bt-top-stat bt-bl-c">${f.bloggers}人</span>
            </div>`;
        }).join('');

        // ── 博主热力 ──────────────────────────────────────────────────────
        const bloggerCards = bloggersSorted.slice(0, 24).map(b => {
            const buyW  = b.total ? Math.round(b.buy  / b.total * 100) : 0;
            const sellW = b.total ? Math.round(b.sell / b.total * 100) : 0;
            const dipW  = 100 - buyW - sellW;
            return `<div class="bt-blogger-card">
                <div class="bt-blogger-name" title="${b.name}">${b.name}</div>
                <div class="bt-blogger-bar-wrap">
                    ${buyW  ? `<div class="bt-blogger-seg" style="width:${buyW}%;background:#dc3545">${buyW>15?b.buy+'买':''}</div>` : ''}
                    ${sellW ? `<div class="bt-blogger-seg" style="width:${sellW}%;background:#28a745">${sellW>15?b.sell+'卖':''}</div>` : ''}
                    ${dipW  ? `<div class="bt-blogger-seg" style="width:${dipW}%;background:#f59e0b">${dipW>15?b.dip+'投':''}</div>` : ''}
                </div>
                <div class="bt-blogger-meta">
                    <span>${b.total} 操作</span>
                    <span>${b.funds} 基金</span>
                </div>
            </div>`;
        }).join('');

        // ── 趋势柱 ───────────────────────────────────────────────────────
        const trendBars = dateTrend.map(([date, v]) => {
            const tot = v.buy + v.sell + v.dip;
            const h = Math.max(4, Math.round(tot / maxDay * 54));
            const bh = Math.round(v.buy  / tot * h);
            const sh = Math.round(v.sell / tot * h);
            const dh = h - bh - sh;
            const shortDate = date.slice(5);
            return `<div class="bt-trend-col">
                <div style="width:100%;display:flex;flex-direction:column;align-items:center;gap:1px">
                    ${bh ? `<div class="bt-trend-bar" style="height:${bh}px;background:#dc3545;width:80%"></div>` : ''}
                    ${sh ? `<div class="bt-trend-bar" style="height:${sh}px;background:#28a745;width:80%"></div>` : ''}
                    ${dh ? `<div class="bt-trend-bar" style="height:${dh}px;background:#f59e0b;width:80%"></div>` : ''}
                </div>
                <div class="bt-trend-lbl">${shortDate}</div>
            </div>`;
        }).join('');

        // ── 明细表格 ──────────────────────────────────────────────────────
        const byDate = {};
        data.forEach(r => {
            const d = r.date || '未知';
            if (!byDate[d]) byDate[d] = {};
            const t = r.topic || '其他';
            if (!byDate[d][t]) byDate[d][t] = [];
            byDate[d][t].push(r);
        });
        let detailHTML = '';
        Object.keys(byDate).sort().reverse().forEach(date => {
            detailHTML += `<div class="bt-detail-date">${date}</div>`;
            Object.entries(byDate[date]).forEach(([topic, items]) => {
                detailHTML += `<div class="bt-detail-topic">${topic}</div>`;
                detailHTML += `<div class="bt-detail-hd"><span>博主</span><span>操作</span><span>金额</span><span>基金名称</span><span>代码</span><span>近一年</span></div>`;
                items.forEach(r => {
                    const mine = this._myFundCodes.includes(String(r.fund_code));
                    const ac = r.action==='买入'?'bt-buy-c':r.action==='卖出'?'bt-sell-c':'bt-dip-c';
                    const yr = r.yearly_return ? `+${(parseFloat(r.yearly_return)*100||0).toFixed(0)}%` : '--';
                    detailHTML += `<div class="bt-detail-row${mine?' bt-detail-mine':''}">
                        <span style="color:#bbb;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${r.blogger_name}</span>
                        <span class="${ac}">${r.action}</span>
                        <span style="color:#666">${r.amount||'--'}</span>
                        <span style="color:#bbb;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${r.fund_name}${mine?'<span class="bt-mine-tag">自选</span>':''}</span>
                        <span style="color:#333;font-family:monospace;font-size:10px">${r.fund_code}</span>
                        <span style="color:#555">${yr}</span>
                    </div>`;
                });
            });
            detailHTML += '<div style="margin-bottom:14px"></div>';
        });

        main.innerHTML = `
        <!-- 统计卡片 -->
        <div class="bt-stats">
            <div class="bt-stat-card">
                <div class="bt-stat-val" style="color:#dc3545">${totalBuy}</div>
                <div class="bt-stat-lbl">买入操作</div>
                <div class="bt-stat-sub">${bloggerSet.size} 位博主</div>
            </div>
            <div class="bt-stat-card">
                <div class="bt-stat-val" style="color:#28a745">${totalSell}</div>
                <div class="bt-stat-lbl">卖出操作</div>
                <div class="bt-stat-sub">${fundSet.size} 只基金</div>
            </div>
            <div class="bt-stat-card">
                <div class="bt-stat-val" style="color:#f59e0b">${totalDip}</div>
                <div class="bt-stat-lbl">定投操作</div>
                <div class="bt-stat-sub">${dateSet.size} 个交易日</div>
            </div>
            <div class="bt-stat-card">
                <div class="bt-stat-val" style="color:#3b82f6">${totalBuy+totalSell+totalDip}</div>
                <div class="bt-stat-lbl">总操作数</div>
                <div class="bt-stat-sub">近 ${this._currentRange}</div>
            </div>
        </div>

        ${dateTrend.length > 1 ? `
        <div class="bt-section">
            <div class="bt-section-title">操作趋势</div>
            <div style="background:#1a1a1a;border:0.5px solid #222;border-radius:10px;padding:14px 14px 8px">
                <div style="display:flex;gap:12px;font-size:10px;color:#444;margin-bottom:8px">
                    <span><span style="color:#dc3545">■</span> 买入</span>
                    <span><span style="color:#28a745">■</span> 卖出</span>
                    <span><span style="color:#f59e0b">■</span> 定投</span>
                </div>
                <div class="bt-trend-wrap">${trendBars}</div>
            </div>
        </div>` : ''}

        <div class="bt-section">
            <div class="bt-section-title">主题分布</div>
            <div class="bt-donuts">
                ${donut(topicSorted, 'buy',  '#dc3545', '买入主题')}
                ${donut(topicSorted, 'sell', '#28a745', '卖出主题')}
                ${donut(topicSorted, 'dip',  '#f59e0b', '定投主题')}
            </div>
        </div>

        <div class="bt-section">
            <div class="bt-section-title">博主买入 TOP${Math.min(20,fundsSorted.length)} 基金</div>
            <div style="background:#1a1a1a;border:0.5px solid #222;border-radius:10px;padding:8px">
                <div class="bt-top-row" style="font-size:10px;color:#333;padding:3px 10px;margin-bottom:2px">
                    <span></span><span></span>
                    <span style="text-align:center">买入</span><span style="text-align:center">卖出</span>
                    <span style="text-align:center">定投</span><span style="text-align:center">博主</span>
                </div>
                <div class="bt-top-grid">${top20Rows}</div>
            </div>
        </div>

        <div class="bt-section">
            <div class="bt-section-title">博主操作分布（${bloggersSorted.length} 位）</div>
            <div class="bt-blogger-grid">${bloggerCards}</div>
        </div>

        <div class="bt-section">
            <div class="bt-section-title">操作明细</div>
            ${detailHTML}
        </div>`;
    }

    _parseAndUpload(file, msgEl) {
        if (msgEl) { msgEl.style.display='block'; msgEl.style.color='#888'; msgEl.textContent='正在解析...'; }
        const reader = new FileReader();
        reader.onload = e => {
            try {
                const wb = XLSX.read(e.target.result, { type: 'array' });
                const raw = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]], { header: 1, defval: '' });
                const result = this._parseRawRows(raw, file.name);
                if (!result.ok) {
                    if (msgEl) { msgEl.textContent='❌ '+result.error; msgEl.style.color='#dc3545'; }
                    return;
                }
                if (msgEl) msgEl.textContent = `已解析 ${result.records.length} 条，上传中...`;
                this._doUpload(result, msgEl);
            } catch(err) {
                if (msgEl) { msgEl.textContent='❌ '+err.message; msgEl.style.color='#dc3545'; }
            }
        };
        reader.readAsArrayBuffer(file);
    }

    _parseAndUploadFromSettings(file, msgEl) {
        this._parseAndUpload(file, msgEl);
    }

    _doUpload(result, msgEl) {
        fetch('/api/blogger-signals', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(result.records),
        })
        .then(r => r.json())
        .then(res => {
            const bj = new Date(new Date().toLocaleString('en-US',{timeZone:'Asia/Shanghai'}));
            const ts = `${bj.getFullYear()}-${String(bj.getMonth()+1).padStart(2,'0')}-${String(bj.getDate()).padStart(2,'0')} ${String(bj.getHours()).padStart(2,'0')}:${String(bj.getMinutes()).padStart(2,'0')}`;
            const dup = result.originalCount > (res.unique||res.inserted) ? `，${result.originalCount-(res.unique||res.inserted)}条重复已合并` : '';
            if (msgEl) {
                msgEl.textContent = res.success ? `✅ 成功 ${res.inserted} 条${dup} | ${ts}` : `❌ ${res.error}`;
                msgEl.style.color = res.success ? '#28a745' : '#dc3545';
            }
            if (res.success) {
                this._refreshGlobalSignals();
                if (window.activeTab === 'blogger-tracker') this._loadAndRender();
            }
        })
        .catch(() => { if (msgEl) { msgEl.textContent='❌ 网络错误'; msgEl.style.color='#dc3545'; } });
    }

    _parseRawRows(raw, fileName) {
        let hi = -1;
        for (let i = 0; i < Math.min(raw.length, 5); i++) {
            const s = (raw[i]||[]).map(c=>String(c)).join('');
            if (s.includes('博主') && s.includes('操作')) { hi = i; break; }
        }
        if (hi === -1) return { ok: false, error: '未找到表头行（需包含"博主"和"操作"列）' };

        const hr = raw[hi], ci = {};
        hr.forEach((h, i) => {
            const k = String(h).trim();
            if (k.includes('主题'))    ci.topic = i;
            if (k.includes('博主'))    ci.bn    = i;
            if (k.includes('近一年'))  ci.yr    = i;
            if (k.includes('操作'))    ci.action= i;
            if (k.includes('金额'))    ci.amount= i;
            if (k.includes('基金名'))  ci.fn    = i;
            if (k.includes('基金代码') || k.includes('fund_code')) ci.fc = i;
        });
        hr.forEach((h,i) => { if (String(h).trim().includes('修正后名称')) ci.fn = i; });
        if (ci.fc === undefined) return { ok: false, error: '文件里没有"基金代码"列，请新增后重试' };

        let fileDate = '';
        for (let i = 0; i < hi; i++) {
            const m = String((raw[i]||[]).join('')).match(/(\d{4})[.\-\/](\d{1,2})[.\-\/](\d{1,2})/);
            if (m) { fileDate=`${m[1]}-${m[2].padStart(2,'0')}-${m[3].padStart(2,'0')}`; break; }
        }
        if (!fileDate) {
            const fn = (fileName||'').replace(/\.xlsx?$/i,'');
            const m3 = fn.match(/^(\d{1,2})[_\-](\d{1,2})/);
            if (m3) fileDate = `${new Date().getFullYear()}-${m3[1].padStart(2,'0')}-${m3[2].padStart(2,'0')}`;
            else {
                const m2 = fn.match(/(\d{4})(\d{2})(\d{2})/);
                if (m2) fileDate = `${m2[1]}-${m2[2]}-${m2[3]}`;
                else { const bj=new Date(new Date().toLocaleString('en-US',{timeZone:'Asia/Shanghai'})); fileDate=`${bj.getFullYear()}-${String(bj.getMonth()+1).padStart(2,'0')}-${String(bj.getDate()).padStart(2,'0')}`; }
            }
        }

        const recs = [], VALID = new Set(['买入','卖出','定投']);
        let ct = '';
        for (let i = hi+1; i < raw.length; i++) {
            const row = raw[i];
            if (!row || row.every(c => c===''||c===null||c===undefined)) continue;
            const tv = String(row[ci.topic]??'').trim().replace(/[\u200b\u00a0\u200c]/g,'');
            if (tv && tv!=='undefined' && tv!=='nan') ct = tv;
            const fcR = row[ci.fc];
            if (fcR==null || String(fcR) in {'':'','nan':'','undefined':''}) continue;
            let fc; try { fc = String(Math.floor(Number(String(fcR)))).padStart(6,'0'); } catch { continue; }
            if (!fc || fc==='000000' || fc.includes('NaN')) continue;
            const fn = ci.fn!==undefined ? String(row[ci.fn]??'').trim() : '';
            if (!fn || fn==='nan') continue;
            const action = String(row[ci.action]??'').trim();
            const blogger = String(row[ci.bn]??'').trim();
            if (!blogger || !VALID.has(action)) continue;
            recs.push({ date:fileDate, blogger_name:blogger, fund_code:fc, fund_name:fn, action,
                amount: String(row[ci.amount]??'').trim(), topic:ct, yearly_return: String(row[ci.yr]??'').trim() });
        }
        if (!recs.length) return { ok:false, error:`未解析到有效数据（表头第${hi+1}行）` };

        const dd = {};
        recs.forEach(r => {
            const k = `${r.blogger_name}||${r.fund_code}||${r.action}`;
            if (!dd[k]) dd[k] = { ...r };
            else dd[k].amount = [dd[k].amount, r.amount].filter(Boolean).join('+');
        });
        return { ok:true, records:Object.values(dd), fileDate, originalCount:recs.length };
    }

    _refreshGlobalSignals() {
        fetch('/api/blogger-signals')
            .then(r => r.ok ? r.json() : [])
            .then(data => {
                window._bloggerSignals = data || [];
                if (window.activeTab !== 'blogger-tracker') {
                    try {
                        const cached = cacheManager.get('fundsList');
                        if (cached && typeof renderFunds === 'function') renderFunds(cached);
                    } catch(_) {}
                }
            }).catch(() => {});
    }
}

const bloggerTracker = new BloggerTracker();
window.bloggerTracker = bloggerTracker;
bloggerTracker._refreshGlobalSignals();