// blogger-tracker.js v3 — 博主追踪分析报告

class BloggerTracker {
    constructor() {
        this._signals     = [];
        this._myFundCodes = [];
        this._currentRange  = '7D';
        this._cache = {};
    }

    show() {
        if (window.activeTab !== 'blogger-tracker') return;
        const container = document.getElementById('funds-container');
        if (!container) return;
        const header = document.getElementById('fund-list-header');
        if (header) header.style.display = 'none';
        const sb = document.querySelector('.search-container');
        if (sb) sb.style.display = 'none';
        // 直接写 loading，同步，无中间状态
        const r = this._currentRange;
        container.innerHTML = '<div id="bt-root"><style>'
            + '#bt-root{font-family:-apple-system,BlinkMacSystemFont,sans-serif;color:#e0e0e0}'
            + '.bt-spin{width:20px;height:20px;border:2px solid #252525;border-top-color:#007bff;border-radius:50%;animation:btspin .8s linear infinite}'
            + '@keyframes btspin{to{transform:rotate(360deg)}}'
            + '</style>'
            + '<div style="padding:16px 20px 8px;font-size:18px;font-weight:600;color:#fff">博主追踪 · 分析报告</div>'
            + '<div style="padding:0 20px;font-size:11px;color:#444;margin-bottom:12px">加载中...</div>'
            + '<div style="display:flex;align-items:center;gap:12px;padding:60px 20px">'
            + '<div class="bt-spin"></div>'
            + '<div><div style="font-size:13px;color:#555">正在读取数据...</div>'
            + '<div style="font-size:11px;color:#333;margin-top:4px">通常 1-2 秒</div></div>'
            + '</div></div>';
        this._fetchAndRender(container);
    }

    _fetchAndRender(container) {
        const days = this._currentRange === '1D' ? 1 : this._currentRange === '3D' ? 3 : 7;
        const key  = 'bt_' + days;
        const cached = this._cache[key];

        const done = (data) => {
            if (window.activeTab !== 'blogger-tracker') return;
            this._signals = Array.isArray(data) ? data : [];
            window._bloggerSignals = this._signals;
            this._renderShell(container);
            const main = document.getElementById('bt-main');
            if (!main) { console.error('[bt] bt-main not found after renderShell'); return; }
            main.style.display = 'block';
            const btLoad = document.getElementById('bt-loading');
            if (btLoad) btLoad.style.display = 'none';
            try { this._signals.length > 0 ? this._renderReport() : this._renderEmpty(); }
            catch(e) { console.error('[bt] render error:', e); main.innerHTML = '<div style="padding:30px 20px;color:#555;font-size:12px;text-align:center">渲染出错: '+(e&&e.message||'unknown')+'</div>'; }
        };

        if (cached && (Date.now() - cached.ts) < 5*60*1000) { done(cached.data); return; }

        fetch('/api/blogger-signals?days=' + days)
            .then(r => r.ok ? r.json() : [])
            .then(data => { this._cache[key] = {data: data||[], ts: Date.now()}; done(data||[]); })
            .catch(e => { console.error('[bt] fetch error:', e); done([]); });
    }

    _loadAndRender() { this._fetchAndRender(document.getElementById('funds-container')); }

    _renderShell(container) {
        const r = this._currentRange;
        container.innerHTML = '<div id="bt-root">'
            + '<style>'
            + '#bt-root{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display",sans-serif;color:#e0e0e0;padding:0}'
            + '#bt-root *{box-sizing:border-box}'
            + '.bt-hdr{padding:16px 20px 12px;display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:10px}'
            + '.bt-title{font-size:18px;font-weight:600;color:#fff;letter-spacing:-.3px}'
            + '.bt-meta-info{font-size:11px;color:#444;margin-top:3px}'
            + '.bt-controls{display:flex;align-items:center;gap:6px;flex-wrap:wrap}'
            + '.bt-seg{display:flex;background:#1a1a1a;border-radius:7px;padding:2px;gap:1px;border:0.5px solid #252525}'
            + '.bt-seg-btn{padding:4px 12px;border-radius:5px;font-size:11px;font-weight:500;cursor:pointer;border:none;background:transparent;color:#555;transition:all .15s}'
            + '.bt-seg-btn.on{background:#2a2a2a;color:#e0e0e0}'
            + '.bt-ubar{margin:0 20px 12px;padding:10px 14px;background:#141414;border:0.5px dashed #252525;border-radius:8px;display:flex;align-items:center;gap:10px;cursor:pointer;transition:border-color .15s}'
            + '.bt-ubar:hover{border-color:#333}'
            + '.bt-umsg{font-size:11px;padding:6px 14px;margin:0 20px 10px;background:#1a1a1a;border-radius:6px;display:none}'
            + '#bt-loading{display:flex;align-items:center;justify-content:center;height:200px;gap:10px}'
            + '.bt-spin{width:20px;height:20px;border:2px solid #252525;border-top-color:#007bff;border-radius:50%;animation:btspin .8s linear infinite}'
            + '@keyframes btspin{to{transform:rotate(360deg)}}'
            + '.bt-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding:0 20px;margin-bottom:14px}'
            + '.bt-sc{background:#141414;border:0.5px solid #1e1e1e;border-radius:10px;padding:12px 14px}'
            + '.bt-sv{font-size:22px;font-weight:700;letter-spacing:-.5px;line-height:1}'
            + '.bt-sl{font-size:11px;color:#444;margin-top:4px}'
            + '.bt-ss{font-size:11px;color:#555;margin-top:2px}'
            + '.bt-sec{padding:0 20px;margin-bottom:16px}'
            + '.bt-sh{font-size:11px;font-weight:600;color:#444;letter-spacing:.8px;text-transform:uppercase;margin-bottom:10px;display:flex;align-items:center;gap:8px}'
            + '.bt-sh::after{content:"";flex:1;height:0.5px;background:#1a1a1a}'
            + '.bt-donuts{display:flex;gap:10px;flex-wrap:wrap}'
            + '.bt-dc{flex:1;min-width:150px;background:#141414;border:0.5px solid #1e1e1e;border-radius:10px;padding:14px}'
            + '.bt-dh{font-size:11px;font-weight:500;margin-bottom:10px}'
            + '.bt-di{display:flex;align-items:center;gap:12px}'
            + '.bt-dl{flex:1;overflow:hidden}'
            + '.bt-li{display:flex;align-items:center;gap:5px;margin-bottom:3px;overflow:hidden}'
            + '.bt-ld{width:7px;height:7px;border-radius:50%;flex-shrink:0}'
            + '.bt-ln{font-size:10px;color:#888;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}'
            + '.bt-lv{font-size:10px;color:#444;margin-left:auto;flex-shrink:0}'
            + '.bt-tg{display:grid;gap:4px}'
            + '.bt-tr{display:grid;grid-template-columns:28px 1fr 44px 44px 44px 36px;gap:6px;align-items:center;padding:7px 10px;border-radius:7px;transition:background .1s}'
            + '.bt-tr:hover{background:#1a1a1a}'
            + '.bt-ti{font-size:11px;color:#333;text-align:right;font-variant-numeric:tabular-nums}'
            + '.bt-r1{color:#ffc107}.bt-r2{color:#888}.bt-r3{color:#cd7f32}'
            + '.bt-tn{overflow:hidden}'
            + '.bt-tf{font-size:12px;color:#ddd;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}'
            + '.bt-tc{font-size:10px;color:#333;font-family:monospace;margin-top:1px}'
            + '.bt-bw{position:relative;height:3px;background:#1a1a1a;border-radius:2px;margin-top:3px}'
            + '.bt-bb{height:100%;border-radius:2px;background:linear-gradient(90deg,#dc3545,#ff6b6b)}'
            + '.bt-ts{font-size:11px;text-align:center;font-variant-numeric:tabular-nums}'
            + '.bt-bc{color:#dc3545}.bt-sc2{color:#28a745}.bt-dc2{color:#ffc107}.bt-nc{color:#555}'
            + '.bt-mt{display:inline-block;font-size:9px;padding:0 3px;border-radius:2px;background:rgba(0,123,255,.2);color:#4a9eff;margin-left:4px;vertical-align:middle}'
            + '.bt-mr{background:rgba(0,123,255,.04)!important;border-left:2px solid rgba(0,123,255,.3)}'
            + '.bt-bg{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:6px}'
            + '.bt-bcard{background:#141414;border:0.5px solid #1e1e1e;border-radius:8px;padding:10px 12px}'
            + '.bt-bname{font-size:12px;color:#ccc;margin-bottom:6px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}'
            + '.bt-bbar{height:24px;background:#0d0d0d;border-radius:4px;overflow:hidden;display:flex}'
            + '.bt-bseg{height:100%;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:600;color:rgba(255,255,255,.8);overflow:hidden;min-width:0}'
            + '.bt-bmeta{display:flex;justify-content:space-between;margin-top:5px;font-size:10px;color:#333}'
            + '.bt-ddate{font-size:12px;font-weight:600;color:#007bff;padding:10px 0 5px;border-bottom:0.5px solid #1a1a1a;margin-bottom:4px}'
            + '.bt-dtopic{font-size:10px;color:#333;letter-spacing:.4px;padding:5px 0 2px}'
            + '.bt-dhd{display:grid;grid-template-columns:88px 46px 62px 1fr 60px 48px;gap:5px;padding:3px 8px;font-size:10px;color:#333}'
            + '.bt-drow{display:grid;grid-template-columns:88px 46px 62px 1fr 60px 48px;gap:5px;align-items:center;padding:6px 8px;border-radius:5px;font-size:11px;transition:background .1s}'
            + '.bt-drow:hover{background:#1a1a1a}'
            + '.bt-dmine{border-left:2px solid rgba(0,123,255,.4)}'
            + '.bt-empty-wrap{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:60px 20px;color:#333}'
            + '.bt-trend-wrap{display:flex;gap:3px;align-items:flex-end;height:60px}'
            + '.bt-trend-col{flex:1;display:flex;flex-direction:column;gap:1px;align-items:center}'
            + '.bt-trend-bar{width:100%;border-radius:2px 2px 0 0;min-height:2px}'
            + '.bt-trend-lbl{font-size:9px;color:#333;margin-top:3px;white-space:nowrap}'
            + '.bt-collapse-hd:hover{background:#1a1a1a!important}'
            + '.bt-lv{font-size:10px;color:#555;margin-left:3px;flex-shrink:0}'
            + '.bt-lpct{font-size:9px;color:#2a2a2a;margin-left:2px;flex-shrink:0}'
            + '</style>'

            + '<div class="bt-hdr"><div>'
            + '<div class="bt-title">博主追踪 · 分析报告</div>'
            + '<div class="bt-meta-info" id="bt-meta-info">加载中...</div>'
            + '</div><div class="bt-controls">'
            + '<div class="bt-seg">'
            + '<button class="bt-seg-btn' + (r==='1D'?' on':'') + '" data-range="1D">1D</button>'
            + '<button class="bt-seg-btn' + (r==='3D'?' on':'') + '" data-range="3D">3D</button>'
            + '<button class="bt-seg-btn' + (r==='7D'?' on':'') + '" data-range="7D">7D</button>'
            + '</div></div></div>'

            + '<div class="bt-ubar" id="bt-ubar">'
            + '<span style="font-size:16px">📂</span>'
            + '<span style="font-size:11px;color:#555">上传博主实盘 xlsx（主题/博主/操作/金额/基金名称/基金代码）</span>'
            + '<input type="file" id="bt-file-main" accept=".xlsx,.xls" style="display:none">'
            + '</div>'
            + '<div class="bt-umsg" id="bt-umsg-main"></div>'
            + '<div id="bt-loading" style="display:flex"><div class="bt-spin"></div><div>'
            + '<div style="font-size:12px;color:#555" id="bt-loading-txt">正在从数据库读取...</div>'
            + '<div style="font-size:10px;color:#333;margin-top:3px" id="bt-loading-sub">通常需要 1-2 秒</div>'
            + '</div></div>'
            + '<div id="bt-main" style="display:none"></div>'
            + '</div>';

        document.getElementById('bt-ubar').addEventListener('click', () => {
            document.getElementById('bt-file-main').click();
        });
        document.getElementById('bt-file-main').addEventListener('change', e => {
            const f = e.target.files[0];
            if (f) this._parseAndUpload(f, document.getElementById('bt-umsg-main'));
            e.target.value = '';
        });
        const ubar = document.getElementById('bt-ubar');
        ubar.addEventListener('dragover', e => { e.preventDefault(); ubar.style.borderColor='#007bff'; });
        ubar.addEventListener('dragleave', () => { ubar.style.borderColor=''; });
        ubar.addEventListener('drop', e => {
            e.preventDefault(); ubar.style.borderColor='';
            const f = e.dataTransfer.files[0];
            if (f) this._parseAndUpload(f, document.getElementById('bt-umsg-main'));
        });
        document.getElementById('bt-root').addEventListener('click', e => {
            const rb = e.target.closest('.bt-seg-btn');
            if (rb) { this._currentRange = rb.dataset.range; this.show(); return; }
            // 操作筛选按钮已移除
        });
    }

    _renderEmpty() {
        const main = document.getElementById('bt-main');
        if (!main) return;
        main.innerHTML = '<div class="bt-empty-wrap"><div style="font-size:36px;margin-bottom:12px;opacity:.3">📊</div><div style="font-size:13px">暂无数据，请上传博主实盘 xlsx 文件</div></div>';
    }

    _renderErrorState(err) {
        const main = document.getElementById('bt-main');
        if (!main) return;
        main.innerHTML = '<div style="padding:40px 20px;text-align:center;color:#555;font-size:12px">渲染出错: ' + (err && err.message || '未知') + '<br><br><button onclick="window.bloggerTracker.show()" style="padding:6px 14px;background:#2a2a2a;border:0.5px solid #333;border-radius:5px;color:#aaa;cursor:pointer;font-size:11px">重试</button></div>';
    }

    _renderReport() {
        const main = document.getElementById('bt-main');
        if (!main) return;
        const data = this._signals; // 不再按操作类型筛选，显示全部
        const COLORS = ['#3b82f6','#ef4444','#f59e0b','#10b981','#8b5cf6','#f97316','#06b6d4','#ec4899','#84cc16','#6366f1'];

        const totalBuy  = data.filter(r => r.action === '买入').length;
        const totalSell = data.filter(r => r.action === '卖出').length;
        const totalDip  = data.filter(r => r.action === '定投').length;
        const bloggerSet = new Set(data.map(r => r.blogger_name));
        const fundSet    = new Set(data.map(r => r.fund_code));
        const dateSet    = new Set(data.map(r => r.date));

        const meta = document.getElementById('bt-meta-info');
        if (meta) {
            const dates = [...dateSet].sort();
            meta.textContent = (dates[0]||'') + (dates.length>1?' ~ '+dates[dates.length-1]:'') + ' · ' + bloggerSet.size + ' 位博主 · ' + fundSet.size + ' 只基金';
        }

        const topicMap = {};
        data.forEach(r => {
            const t = r.topic||'其他';
            if (!topicMap[t]) topicMap[t] = {buy:0,sell:0,dip:0};
            if (r.action==='买入') topicMap[t].buy++;
            else if (r.action==='卖出') topicMap[t].sell++;
            else topicMap[t].dip++;
        });
        const topicSorted = Object.entries(topicMap).sort((a,b)=>(b[1].buy+b[1].sell+b[1].dip)-(a[1].buy+a[1].sell+a[1].dip));

        const fundMap = {};
        data.forEach(r => {
            if (!fundMap[r.fund_code]) fundMap[r.fund_code] = {code:r.fund_code,name:r.fund_name,topic:r.topic,buy:0,sell:0,dip:0,bl:new Set()};
            if (r.action==='买入') fundMap[r.fund_code].buy++;
            else if (r.action==='卖出') fundMap[r.fund_code].sell++;
            else fundMap[r.fund_code].dip++;
            fundMap[r.fund_code].bl.add(r.blogger_name);
        });
        const fundsSorted = Object.values(fundMap).map(f=>({...f,bl:f.bl.size,total:f.buy+f.sell+f.dip})).sort((a,b)=>b.buy-a.buy||b.total-a.total);
        const maxBuy = Math.max(fundsSorted[0]&&fundsSorted[0].buy||0, 1);

        const bloggerMap = {};
        data.forEach(r => {
            if (!bloggerMap[r.blogger_name]) bloggerMap[r.blogger_name] = {buy:0,sell:0,dip:0,funds:new Set()};
            if (r.action==='买入') bloggerMap[r.blogger_name].buy++;
            else if (r.action==='卖出') bloggerMap[r.blogger_name].sell++;
            else bloggerMap[r.blogger_name].dip++;
            bloggerMap[r.blogger_name].funds.add(r.fund_code);
        });
        const bloggersSorted = Object.entries(bloggerMap).map(([n,s])=>({name:n,...s,funds:s.funds.size,total:s.buy+s.sell+s.dip})).sort((a,b)=>b.total-a.total);

        const dateMap = {};
        data.forEach(r => {
            if (!dateMap[r.date]) dateMap[r.date]={buy:0,sell:0,dip:0};
            if (r.action==='买入') dateMap[r.date].buy++;
            else if (r.action==='卖出') dateMap[r.date].sell++;
            else dateMap[r.date].dip++;
        });
        const dateTrend = Object.entries(dateMap).sort((a,b)=>a[0].localeCompare(b[0]));
        const maxDay = dateTrend.reduce((m,[,v])=>Math.max(m,v.buy+v.sell+v.dip),1);

        // 圆环图：正圆，图例含百分比
        const donut = (items, field, color, title) => {
            const filtered = items.filter(([,s])=>s[field]>0).slice(0,8);
            if (!filtered.length) return '';
            const total = filtered.reduce((s,[,v])=>s+v[field],0);
            // 使用正方形 viewBox 确保是正圆
            const R=42,cx=52,cy=52,sw=14,circ=2*Math.PI*R;
            let off=0, slices='';
            filtered.forEach(([t,st],i) => {
                const d=(st[field]/total)*circ;
                slices += '<circle cx="'+cx+'" cy="'+cy+'" r="'+R+'" fill="none" stroke="'+COLORS[i%10]+'"'
                    + ' stroke-width="'+sw+'" stroke-dasharray="'+d.toFixed(2)+' '+(circ-d).toFixed(2)+'"'
                    + ' stroke-dashoffset="'+(-(off/total)*circ).toFixed(2)+'" transform="rotate(-90 '+cx+' '+cy+')"/>';
                off+=st[field];
            });
            const legend = filtered.slice(0,6).map(([t,st],i) => {
                const pct = (st[field]/total*100).toFixed(1);
                return '<div class="bt-li"><div class="bt-ld" style="background:'+COLORS[i%10]+'"></div>'
                    +'<span class="bt-ln">'+t+'</span>'
                    +'<span class="bt-lv" style="color:#555">'+st[field]+'</span>'
                    +'<span style="font-size:9px;color:#333;margin-left:3px;flex-shrink:0">('+pct+'%)</span></div>';
            }).join('');
            return '<div class="bt-dc"><div class="bt-dh" style="color:'+color+'">'+title+'</div>'
                +'<div class="bt-di"><svg viewBox="0 0 104 104" style="width:84px;height:84px;flex-shrink:0">'
                +'<circle cx="'+cx+'" cy="'+cy+'" r="'+R+'" fill="none" stroke="#1a1a1a" stroke-width="'+sw+'"/>'
                +slices
                +'<text x="'+cx+'" y="'+(cy-6)+'" text-anchor="middle" dominant-baseline="middle" fill="#666" font-size="14" font-weight="700">'+total+'</text>'
                +'<text x="'+cx+'" y="'+(cy+10)+'" text-anchor="middle" dominant-baseline="middle" fill="#333" font-size="9">操作</text>'
                +'</svg><div class="bt-dl">'+legend+'</div></div></div>';
        };

        // TOP20 行
        const top20 = fundsSorted.slice(0,20).map((f,i) => {
            const mine = this._myFundCodes.includes(String(f.code));
            const bw = Math.round(f.buy/maxBuy*100);
            const medal = i===0?'🥇':i===1?'🥈':i===2?'🥉':(i+1);
            const rCls = i===0?' bt-r1':i===1?' bt-r2':i===2?' bt-r3':'';
            return '<div class="bt-tr'+(mine?' bt-mr':'')+'"><span class="bt-ti'+rCls+'">'+medal+'</span>'
                +'<div class="bt-tn"><div class="bt-tf">'+f.name+(mine?'<span class="bt-mt">自选</span>':'')+'</div>'
                +'<div class="bt-tc">'+f.code+(f.topic?' · <span style="color:#2a2a2a">'+f.topic+'</span>':'')+'</div>'
                +'<div class="bt-bw"><div class="bt-bb" style="width:'+bw+'%"></div></div></div>'
                +'<span class="bt-ts bt-bc">'+(f.buy?f.buy+'买':'')+'</span>'
                +'<span class="bt-ts bt-sc2">'+(f.sell?f.sell+'卖':'')+'</span>'
                +'<span class="bt-ts bt-dc2">'+(f.dip?f.dip+'投':'')+'</span>'
                +'<span class="bt-ts bt-nc">'+f.bl+'人</span></div>';
        }).join('');

        // 博主热力
        const blogCards = bloggersSorted.slice(0,24).map(b => {
            const bw = b.total?Math.round(b.buy/b.total*100):0;
            const sw = b.total?Math.round(b.sell/b.total*100):0;
            const dw = 100-bw-sw;
            return '<div class="bt-bcard"><div class="bt-bname" title="'+b.name+'">'+b.name+'</div>'
                +'<div class="bt-bbar">'
                +(bw?'<div class="bt-bseg" style="width:'+bw+'%;background:#dc3545">'+(bw>15?b.buy+'买':'')+'</div>':'')
                +(sw?'<div class="bt-bseg" style="width:'+sw+'%;background:#28a745">'+(sw>15?b.sell+'卖':'')+'</div>':'')
                +(dw?'<div class="bt-bseg" style="width:'+dw+'%;background:#f59e0b">'+(dw>15?b.dip+'投':'')+'</div>':'')
                +'</div><div class="bt-bmeta"><span>'+b.total+' 操作</span><span>'+b.funds+' 基金</span></div></div>';
        }).join('');

        // 趋势柱
        const trendBars = dateTrend.map(([date,v]) => {
            const tot=v.buy+v.sell+v.dip, h=Math.max(4,Math.round(tot/maxDay*54));
            const bh=Math.round(v.buy/tot*h), sh=Math.round(v.sell/tot*h), dh=h-bh-sh;
            return '<div class="bt-trend-col">'
                +'<div style="width:100%;display:flex;flex-direction:column;align-items:center;gap:1px">'
                +(bh?'<div class="bt-trend-bar" style="height:'+bh+'px;background:#dc3545;width:80%"></div>':'')
                +(sh?'<div class="bt-trend-bar" style="height:'+sh+'px;background:#28a745;width:80%"></div>':'')
                +(dh?'<div class="bt-trend-bar" style="height:'+dh+'px;background:#f59e0b;width:80%"></div>':'')
                +'</div><div class="bt-trend-lbl">'+date.slice(5)+'</div></div>';
        }).join('');

        // 明细
        const byDate = {};
        data.forEach(r => {
            const d=r.date||'未知';
            if (!byDate[d]) byDate[d]={};
            const t=r.topic||'其他';
            if (!byDate[d][t]) byDate[d][t]=[];
            byDate[d][t].push(r);
        });
        let detail = '';
        const dateKeys = Object.keys(byDate).sort().reverse();
        dateKeys.forEach((date, di) => {
            // 统计当天数量
            const dayTotal = Object.values(byDate[date]).reduce((s,arr)=>s+arr.length, 0);
            const dayBuy  = Object.values(byDate[date]).reduce((s,arr)=>s+arr.filter(r=>r.action==='买入').length, 0);
            const daySell = Object.values(byDate[date]).reduce((s,arr)=>s+arr.filter(r=>r.action==='卖出').length, 0);
            const dayDip  = dayTotal - dayBuy - daySell;
            const isFirst = di === 0; // 最新日期默认展开
            const colId = 'btd-'+date.replace(/-/g,'');
            detail += '<div style="border:0.5px solid #1e1e1e;border-radius:8px;margin-bottom:8px;overflow:hidden">'
                // 折叠头部
                +'<div data-btcol="'+colId+'" onclick="window._btToggle(this.dataset.btcol)" '
                +'style="display:flex;align-items:center;padding:10px 14px;cursor:pointer;background:#141414;user-select:none">'
                +'<span style="font-size:12px;font-weight:600;color:#007bff;flex:1">'+date+'</span>'
                +'<span style="font-size:10px;color:#444;display:flex;gap:8px;margin-right:10px">'
                +(dayBuy?'<span style="color:#dc3545">'+dayBuy+'买</span>':'')
                +(daySell?'<span style="color:#28a745">'+daySell+'卖</span>':'')
                +(dayDip?'<span style="color:#f59e0b">'+dayDip+'投</span>':'')
                +'</span>'
                +'<span class="bt-arrow" style="color:#333;font-size:12px;transition:transform .2s;transform:'+(isFirst?'rotate(90deg)':'rotate(0deg)')+'">▶</span>'
                +'</div>'
                // 内容区
                +'<div id="'+colId+'" style="display:'+(isFirst?'block':'none')+';padding:0 10px 8px">';
            Object.entries(byDate[date]).forEach(([topic,items]) => {
                detail += '<div class="bt-dtopic">'+topic+'</div>'
                    +'<div class="bt-dhd"><span>博主</span><span>操作</span><span>金额</span><span>基金名称</span><span>代码</span><span>近一年</span></div>';
                items.forEach(r => {
                    const mine=this._myFundCodes.includes(String(r.fund_code));
                    const ac=r.action==='买入'?'bt-bc':r.action==='卖出'?'bt-sc2':'bt-dc2';
                    const yr=r.yearly_return?'+'+((parseFloat(r.yearly_return)*100)||0).toFixed(0)+'%':'--';
                    detail += '<div class="bt-drow'+(mine?' bt-dmine':'')+'"><span style="color:#bbb;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+r.blogger_name+'</span>'
                        +'<span class="'+ac+'">'+r.action+'</span>'
                        +'<span style="color:#666">'+(r.amount||'--')+'</span>'
                        +'<span style="color:#bbb;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+r.fund_name+(mine?'<span class="bt-mt">自选</span>':'')+'</span>'
                        +'<span style="color:#333;font-family:monospace;font-size:10px">'+r.fund_code+'</span>'
                        +'<span style="color:#555">'+yr+'</span></div>';
                });
            });
            detail += '</div></div>';
        });

        // 组装
        let html = '<div class="bt-stats">'
            +'<div class="bt-sc"><div class="bt-sv" style="color:#dc3545">'+totalBuy+'</div><div class="bt-sl">买入操作</div><div class="bt-ss">'+bloggerSet.size+' 位博主</div></div>'
            +'<div class="bt-sc"><div class="bt-sv" style="color:#28a745">'+totalSell+'</div><div class="bt-sl">卖出操作</div><div class="bt-ss">'+fundSet.size+' 只基金</div></div>'
            +'<div class="bt-sc"><div class="bt-sv" style="color:#f59e0b">'+totalDip+'</div><div class="bt-sl">定投操作</div><div class="bt-ss">'+dateSet.size+' 个交易日</div></div>'
            +'<div class="bt-sc"><div class="bt-sv" style="color:#3b82f6">'+(totalBuy+totalSell+totalDip)+'</div><div class="bt-sl">总操作数</div><div class="bt-ss">近 '+this._currentRange+'</div></div>'
            +'</div>';

        if (dateTrend.length > 1) {
            html += '<div class="bt-sec"><div class="bt-sh">操作趋势</div>'
                +'<div style="background:#141414;border:0.5px solid #1e1e1e;border-radius:10px;padding:14px 14px 8px">'
                +'<div style="display:flex;gap:12px;font-size:10px;color:#444;margin-bottom:8px">'
                +'<span><span style="color:#dc3545">■</span> 买入</span>'
                +'<span><span style="color:#28a745">■</span> 卖出</span>'
                +'<span><span style="color:#f59e0b">■</span> 定投</span></div>'
                +'<div class="bt-trend-wrap">'+trendBars+'</div></div></div>';
        }

        html += '<div class="bt-sec"><div class="bt-sh">主题分布</div><div class="bt-donuts">'
            +donut(topicSorted,'buy','#dc3545','买入主题')
            +donut(topicSorted,'sell','#28a745','卖出主题')
            +donut(topicSorted,'dip','#f59e0b','定投主题')
            +'</div></div>';

        // 主题趋势图：多天用折线，单天用柱状
        if (dateTrend.length >= 1) {
            // 找买入 Top5 主题
            const top5Topics = topicSorted.slice(0,5).map(([t])=>t);
            // 按日期×主题统计买入数
            const topicByDate = {};
            data.forEach(r => {
                if (r.action !== '买入') return;
                if (!topicByDate[r.date]) topicByDate[r.date] = {};
                const t = r.topic||'其他';
                topicByDate[r.date][t] = (topicByDate[r.date][t]||0)+1;
            });
            // 单天时用水平柱状图，多天时用折线图
            if (dateTrend.length === 1) {
                const maxTopic = Math.max(...top5Topics.map(t => {
                    const d = dateTrend[0][0];
                    return topicByDate[d]&&topicByDate[d][t]||0;
                }), 1);
                const bars = top5Topics.map((t,i) => {
                    const d = dateTrend[0][0];
                    const v = topicByDate[d]&&topicByDate[d][t]||0;
                    if (!v) return '';
                    const w = Math.round(v/maxTopic*100);
                    return '<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">'
                        +'<span style="font-size:11px;color:#888;width:80px;text-align:right;flex-shrink:0">'+t+'</span>'
                        +'<div style="flex:1;height:18px;background:#1a1a1a;border-radius:3px;overflow:hidden">'
                        +'<div style="height:100%;width:'+w+'%;background:'+COLORS[i%10]+';border-radius:3px;display:flex;align-items:center;padding-left:6px">'
                        +'<span style="font-size:10px;color:rgba(255,255,255,.8);font-weight:600">'+v+'</span>'
                        +'</div></div></div>';
                }).join('');
                html += '<div class="bt-sec"><div class="bt-sh">主题买入分布（'+dateTrend[0][0]+'）</div>'
                    +'<div style="background:#141414;border:0.5px solid #1e1e1e;border-radius:10px;padding:14px">'
                    +bars+'</div></div>';
                // 跳过折线图代码
            } else {
            const lineW = 520, lineH = 120, padL = 28, padB = 20, padT = 10, padR = 10;
            const chartW = lineW - padL - padR, chartH = lineH - padT - padB;
            const dates = dateTrend.map(([d])=>d);
            const maxVal = Math.max(...dates.flatMap(d => top5Topics.map(t => topicByDate[d]&&topicByDate[d][t]||0)), 1);
            const xStep = chartW / Math.max(dates.length-1, 1);
            // Y轴刻度
            const yTicks = [0, Math.round(maxVal/2), maxVal];
            let yAxis = '';
            yTicks.forEach(v => {
                const y = padT + chartH - (v/maxVal)*chartH;
                yAxis += '<line x1="'+(padL-4)+'" y1="'+y.toFixed(1)+'" x2="'+(padL+chartW)+'" y2="'+y.toFixed(1)+'" stroke="#1a1a1a" stroke-width="0.5"/>'
                    +'<text x="'+(padL-6)+'" y="'+(y+4).toFixed(1)+'" text-anchor="end" fill="#333" font-size="8">'+v+'</text>';
            });
            // 各主题折线
            let lines = '', dots = '';
            top5Topics.forEach((topic, ti) => {
                const pts = dates.map((d,i) => {
                    const v = topicByDate[d]&&topicByDate[d][topic]||0;
                    const x = padL + i*xStep;
                    const y = padT + chartH - (v/maxVal)*chartH;
                    return {x, y, v};
                });
                const path = pts.map((p,i)=>(i===0?'M':'L')+p.x.toFixed(1)+','+p.y.toFixed(1)).join(' ');
                lines += '<path d="'+path+'" fill="none" stroke="'+COLORS[ti%10]+'" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>';
                pts.forEach((p,i) => {
                    if (p.v > 0) {
                        dots += '<circle cx="'+p.x.toFixed(1)+'" cy="'+p.y.toFixed(1)+'" r="3" fill="'+COLORS[ti%10]+'" stroke="#141414" stroke-width="1.5"/>';
                    }
                });
            });
            // X轴日期标签
            let xLabels = '';
            dates.forEach((d,i) => {
                const x = padL + i*xStep;
                xLabels += '<text x="'+x.toFixed(1)+'" y="'+(lineH-4)+'" text-anchor="middle" fill="#333" font-size="8">'+d.slice(5)+'</text>';
            });
            // 图例
            const legendItems = top5Topics.map((t,i)=>
                '<span style="display:inline-flex;align-items:center;gap:3px;margin-right:10px;font-size:10px;color:#888">'
                +'<span style="width:16px;height:2px;background:'+COLORS[i%10]+';border-radius:1px;display:inline-block"></span>'
                +t+'</span>'
            ).join('');

            html += '<div class="bt-sec"><div class="bt-sh">买入主题趋势（近'+this._currentRange+'）</div>'
                +'<div style="background:#141414;border:0.5px solid #1e1e1e;border-radius:10px;padding:14px">'
                +'<div style="margin-bottom:10px">'+legendItems+'</div>'
                +'<div style="overflow-x:auto"><svg viewBox="0 0 '+lineW+' '+lineH+'" style="width:100%;min-width:260px;height:'+lineH+'px">'
                +yAxis+lines+dots+xLabels
                +'</svg></div>'
                +'</div></div>';
            } // end else (多天折线图)
        }

        html += '<div class="bt-sec"><div class="bt-sh">博主买入 TOP'+Math.min(20,fundsSorted.length)+' 基金</div>'
            +'<div style="background:#141414;border:0.5px solid #1e1e1e;border-radius:10px;padding:8px">'
            +'<div class="bt-tr" style="font-size:10px;color:#333;padding:3px 10px;margin-bottom:2px"><span></span><span></span>'
            +'<span style="text-align:center">买入</span><span style="text-align:center">卖出</span><span style="text-align:center">定投</span><span style="text-align:center">博主</span></div>'
            +'<div class="bt-tg">'+top20+'</div></div></div>';

        html += '<div class="bt-sec"><div class="bt-sh">博主操作分布（'+bloggersSorted.length+' 位）</div>'
            +'<div class="bt-bg">'+blogCards+'</div></div>';

        html += '<div class="bt-sec"><div class="bt-sh">操作明细</div>'+detail+'</div>';

        main.innerHTML = html;
    }

    _parseAndUpload(file, msgEl) {
        if (msgEl) { msgEl.style.display='block'; msgEl.style.color='#888'; msgEl.textContent='正在解析...'; }
        const reader = new FileReader();
        reader.onload = e => {
            try {
                const wb = XLSX.read(e.target.result, { type: 'array' });
                const raw = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]], { header:1, defval:'' });
                const result = this._parseRawRows(raw, file.name);
                if (!result.ok) { if(msgEl){msgEl.textContent='❌ '+result.error;msgEl.style.color='#dc3545';} return; }
                if (msgEl) msgEl.textContent = '已解析 '+result.records.length+' 条，上传中...';
                this._doUpload(result, msgEl);
            } catch(err) { if(msgEl){msgEl.textContent='❌ '+err.message;msgEl.style.color='#dc3545';} }
        };
        reader.readAsArrayBuffer(file);
    }

    _parseAndUploadFromSettings(file, msgEl) { this._parseAndUpload(file, msgEl); }

    _doUpload(result, msgEl) {
        fetch('/api/blogger-signals', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(result.records) })
        .then(r => r.json())
        .then(res => {
            const bj = new Date(new Date().toLocaleString('en-US',{timeZone:'Asia/Shanghai'}));
            const ts = bj.getFullYear()+'-'+String(bj.getMonth()+1).padStart(2,'0')+'-'+String(bj.getDate()).padStart(2,'0')+' '+String(bj.getHours()).padStart(2,'0')+':'+String(bj.getMinutes()).padStart(2,'0');
            const dup = result.originalCount>(res.unique||res.inserted)?'，'+( result.originalCount-(res.unique||res.inserted))+'条重复已合并':'';
            if (msgEl) { msgEl.textContent = res.success?'✅ 成功 '+res.inserted+' 条'+dup+' | '+ts:'❌ '+res.error; msgEl.style.color = res.success?'#28a745':'#dc3545'; }
            if (res.success) {
                // 清除缓存，强制重新加载
                this._cache = {};
                this._refreshGlobalSignals();
                if (window.activeTab === 'blogger-tracker') this._loadAndRender();
            }
        })
        .catch(() => { if(msgEl){msgEl.textContent='❌ 网络错误';msgEl.style.color='#dc3545';} });
    }

    _parseRawRows(raw, fileName) {
        let hi=-1;
        for (let i=0;i<Math.min(raw.length,5);i++) {
            const s=(raw[i]||[]).map(c=>String(c)).join('');
            if (s.includes('博主')&&s.includes('操作')){hi=i;break;}
        }
        if (hi===-1) return {ok:false,error:'未找到表头行（需包含"博主"和"操作"列）'};
        const hr=raw[hi],ci={};
        hr.forEach((h,i)=>{
            const k=String(h).trim();
            if(k.includes('主题'))ci.topic=i;
            if(k.includes('博主'))ci.bn=i;
            if(k.includes('近一年'))ci.yr=i;
            if(k.includes('操作'))ci.action=i;
            if(k.includes('金额'))ci.amount=i;
            if(k.includes('基金名'))ci.fn=i;
            if(k.includes('基金代码')||k.includes('fund_code'))ci.fc=i;
        });
        hr.forEach((h,i)=>{if(String(h).trim().includes('修正后名称'))ci.fn=i;});
        if(ci.fc===undefined) return {ok:false,error:'文件里没有"基金代码"列，请新增后重试'};
        let fileDate='';
        for(let i=0;i<hi;i++){const m=String((raw[i]||[]).join('')).match(/(\d{4})[.\-\/](\d{1,2})[.\-\/](\d{1,2})/);if(m){fileDate=m[1]+'-'+m[2].padStart(2,'0')+'-'+m[3].padStart(2,'0');break;}}
        if(!fileDate){
            const fn=(fileName||'').replace(/\.xlsx?$/i,'');
            const m3=fn.match(/^(\d{1,2})[_\-](\d{1,2})/);
            if(m3)fileDate=new Date().getFullYear()+'-'+m3[1].padStart(2,'0')+'-'+m3[2].padStart(2,'0');
            else{const m2=fn.match(/(\d{4})(\d{2})(\d{2})/);
                if(m2)fileDate=m2[1]+'-'+m2[2]+'-'+m2[3];
                else{const bj=new Date(new Date().toLocaleString('en-US',{timeZone:'Asia/Shanghai'}));fileDate=bj.getFullYear()+'-'+String(bj.getMonth()+1).padStart(2,'0')+'-'+String(bj.getDate()).padStart(2,'0');}}
        }
        const recs=[],VALID=new Set(['买入','卖出','定投']);let ct='';
        for(let i=hi+1;i<raw.length;i++){
            const row=raw[i];
            if(!row||row.every(c=>c===''||c===null||c===undefined))continue;
            const tv=String(row[ci.topic]??'').trim().replace(/[\u200b\u00a0\u200c]/g,'');
            if(tv&&tv!=='undefined'&&tv!=='nan')ct=tv;
            const fcR=row[ci.fc];
            if(fcR==null||String(fcR) in {'':'','nan':'','undefined':''})continue;
            let fc;try{fc=String(Math.floor(Number(String(fcR)))).padStart(6,'0');}catch{continue;}
            if(!fc||fc==='000000'||fc.includes('NaN'))continue;
            const fn=ci.fn!==undefined?String(row[ci.fn]??'').trim():'';
            if(!fn||fn==='nan')continue;
            const action=String(row[ci.action]??'').trim();
            const blogger=String(row[ci.bn]??'').trim();
            if(!blogger||!VALID.has(action))continue;
            recs.push({date:fileDate,blogger_name:blogger,fund_code:fc,fund_name:fn,action,amount:String(row[ci.amount]??'').trim(),topic:ct,yearly_return:String(row[ci.yr]??'').trim()});
        }
        if(!recs.length)return{ok:false,error:'未解析到有效数据（表头第'+(hi+1)+'行）'};
        const dd={};
        recs.forEach(r=>{const k=r.blogger_name+'||'+r.fund_code+'||'+r.action;if(!dd[k])dd[k]={...r};else dd[k].amount=[dd[k].amount,r.amount].filter(Boolean).join('+');});
        return{ok:true,records:Object.values(dd),fileDate,originalCount:recs.length};
    }

    _refreshGlobalSignals() {
        fetch('/api/blogger-signals')
            .then(r=>r.ok?r.json():[])
            .then(data=>{
                window._bloggerSignals=data||[];
                if(window.activeTab!=='blogger-tracker'){
                    try{const c=cacheManager.get('fundsList');if(c&&typeof renderFunds==='function')renderFunds(c);}catch(_){}
                }
            }).catch(()=>{});
    }
}

const bloggerTracker = new BloggerTracker();
window.bloggerTracker = bloggerTracker;
bloggerTracker._refreshGlobalSignals();

// 明细折叠切换（全局函数，避免 onclick 里的引号冲突）
window._btToggle = function(colId) {
    const c = document.getElementById(colId);
    const hd = document.querySelector('[data-btcol="'+colId+'"]');
    if (!c || !hd) return;
    const open = c.style.display !== 'none';
    c.style.display = open ? 'none' : 'block';
    const arrow = hd.querySelector('.bt-arrow');
    if (arrow) arrow.style.transform = open ? 'rotate(0deg)' : 'rotate(90deg)';
};