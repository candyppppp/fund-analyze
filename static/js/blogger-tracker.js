// blogger-tracker.js — 博主追踪模块 v2
// 修复：每次 show() 都重建 DOM，防止其他 tab 切换后挂载点丢失
// 新增：1D/3D/7D 切换、主题圆环图、TOP20基金

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
        const header    = document.getElementById('fund-list-header');
        const searchBar = document.querySelector('.search-container');
        if (searchBar) searchBar.style.display = 'none';
        if (header)    header.style.display    = 'none';
        // 每次都重建 DOM，防止其他 tab 覆盖后挂载点丢失
        this._renderShell(container);
        this._loadMyFundCodes();
        this._loadAndRender();
    }

    hide() {
        const searchBar = document.querySelector('.search-container');
        const header    = document.getElementById('fund-list-header');
        if (searchBar) searchBar.style.display = '';
        if (header)    header.style.display    = '';
    }

    _loadMyFundCodes() {
        fetch('/api/funds?basic_only=1')
            .then(r => r.ok ? r.json() : [])
            .then(funds => { this._myFundCodes = (funds||[]).map(f=>String(f.code)); })
            .catch(()=>{});
    }

    _loadAndRender() {
        const wrap = document.getElementById('bt-table-wrap');
        if (wrap) wrap.innerHTML = '<div style="color:#555;font-size:12px;padding:20px 0;text-align:center">加载中...</div>';
        const days = this._currentRange==='1D'?1:this._currentRange==='3D'?3:7;
        fetch('/api/blogger-signals?days='+days)
            .then(r => r.ok ? r.json() : [])
            .then(data => {
                this._signals = data||[];
                window._bloggerSignals = this._signals;
                if (this._signals.length > 0) {
                    this._renderAll();
                } else {
                    const w = document.getElementById('bt-table-wrap');
                    if (w) w.innerHTML = '<div style="color:#555;font-size:12px;padding:30px 0;text-align:center">暂无数据，请上传博主实盘 xlsx 文件</div>';
                }
            })
            .catch(()=>{
                const w = document.getElementById('bt-table-wrap');
                if (w) w.innerHTML = '<div style="color:#dc3545;font-size:12px;padding:20px 0;text-align:center">加载失败，请刷新重试</div>';
            });
    }

    _renderAll() {
        const data = this._currentAction
            ? this._signals.filter(r=>r.action===this._currentAction)
            : this._signals;
        const countEl = document.getElementById('bt-count');
        if (countEl) countEl.textContent = data.length+' 条';
        this._renderCharts(data);
        this._renderTop20(data);
        this._renderTable(data);
    }

    _renderShell(container) {
        const rangeHTML = ['1D','3D','7D'].map(r=>`
            <button class="bt-btn${r===this._currentRange?' bt-btn-active':''}" data-range="${r}"
                style="background:${r===this._currentRange?'#007bff':'#2a2a2a'};
                color:${r===this._currentRange?'#fff':'#888'};
                border:0.5px solid ${r===this._currentRange?'#007bff':'#333'};
                border-radius:5px;padding:4px 10px;font-size:11px;cursor:pointer">${r}</button>`).join('');
        const actionHTML = [['','全部'],['买入','买入'],['卖出','卖出'],['定投','定投']].map(([v,l])=>`
            <button class="bt-btn${v===this._currentAction?' bt-btn-active':''}" data-action="${v}"
                style="background:${v===this._currentAction?'#444':'#2a2a2a'};
                color:${v===this._currentAction?'#fff':'#888'};
                border:0.5px solid #333;border-radius:5px;padding:4px 10px;font-size:11px;cursor:pointer">${l}</button>`).join('');

        container.innerHTML = `
<div id="bt-wrap" style="padding:0 4px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <div id="bt-upload-area" style="border:1.5px dashed #333;border-radius:10px;padding:12px 16px;
    margin-bottom:12px;cursor:pointer;display:flex;align-items:center;gap:10px"
    onclick="document.getElementById('bt-file-input').click()">
    <span style="font-size:18px">📂</span>
    <div style="font-size:12px;color:#888">点击上传博主实盘 xlsx（主题/博主/操作/金额/基金名称/基金代码）</div>
    <input type="file" id="bt-file-input" accept=".xlsx,.xls" style="display:none">
  </div>
  <div id="bt-upload-msg" style="display:none;font-size:12px;padding:6px 10px;background:#2a2a2a;border-radius:6px;margin-bottom:10px"></div>

  <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;flex-wrap:wrap">
    <div style="display:flex;gap:4px">${rangeHTML}</div>
    <div style="width:1px;height:14px;background:#333"></div>
    <div style="display:flex;gap:4px">${actionHTML}</div>
    <span id="bt-count" style="font-size:11px;color:#444;margin-left:auto"></span>
  </div>

  <div id="bt-charts" style="margin-bottom:16px"></div>
  <div id="bt-top20" style="margin-bottom:16px"></div>
  <div id="bt-table-wrap"></div>
</div>
<style>
.bt-btn:hover{opacity:.8}
.bt-row{display:grid;grid-template-columns:90px 50px 65px 1fr 62px 50px;gap:6px;
  align-items:center;padding:7px 10px;border-radius:6px;border-bottom:0.5px solid #1e1e1e;font-size:12px}
.bt-row:hover{background:#242424}
.bt-buy{color:#dc3545;font-weight:500}.bt-sell{color:#28a745;font-weight:500}.bt-dip{color:#ffc107;font-weight:500}
.bt-mine{border-left:2px solid #007bff!important}
.bt-self{display:inline-block;font-size:10px;padding:0 4px;border-radius:3px;background:rgba(0,123,255,.15);color:#4a9eff;margin-left:3px}
</style>`;

        document.getElementById('bt-file-input').addEventListener('change', e=>{
            const f=e.target.files[0]; if(f)this._parseAndUpload(f); e.target.value='';
        });
        const area = document.getElementById('bt-upload-area');
        area.addEventListener('dragover', e=>{e.preventDefault();area.style.borderColor='#007bff';});
        area.addEventListener('dragleave', ()=>{area.style.borderColor='#333';});
        area.addEventListener('drop', e=>{
            e.preventDefault();area.style.borderColor='#333';
            const f=e.dataTransfer.files[0]; if(f)this._parseAndUpload(f);
        });
        document.getElementById('bt-wrap').addEventListener('click', e=>{
            const rb=e.target.closest('[data-range]');
            if(rb&&!rb.dataset.action){this._currentRange=rb.dataset.range;this.show();return;}
            const ab=e.target.closest('[data-action]');
            if(ab){this._currentAction=ab.dataset.action;this._renderAll();}
        });
    }

    _renderCharts(data) {
        const el=document.getElementById('bt-charts'); if(!el)return;
        if(!data.length){el.innerHTML='';return;}
        const COLORS=['#007bff','#dc3545','#ffc107','#28a745','#6f42c1','#fd7e14','#20c997','#e83e8c'];
        const topicStats={};
        data.forEach(r=>{
            const t=r.topic||'其他';
            if(!topicStats[t])topicStats[t]={买入:0,卖出:0,定投:0};
            if(r.action in topicStats[t])topicStats[t][r.action]++;
        });
        const sorted=Object.entries(topicStats).sort((a,b)=>(b[1].买入+b[1].卖出+b[1].定投)-(a[1].买入+a[1].卖出+a[1].定投)).slice(0,8);

        const donut=(field,color)=>{
            const items=sorted.map(([t,s])=>({t,v:s[field]||0})).filter(x=>x.v>0).sort((a,b)=>b.v-a.v);
            if(!items.length)return'';
            const total=items.reduce((s,x)=>s+x.v,0);
            const r=38,cx=50,cy=50,sw=14,circ=2*Math.PI*r;
            let off=0,slices='';
            items.forEach((item,i)=>{
                const d=(item.v/total)*circ;
                slices+=`<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${COLORS[i%8]}"
                    stroke-width="${sw}" stroke-dasharray="${d.toFixed(1)} ${(circ-d).toFixed(1)}"
                    stroke-dashoffset="${(-off*circ/total).toFixed(1)}" transform="rotate(-90 ${cx} ${cy})"/>`;
                off+=item.v;
            });
            const legend=items.slice(0,5).map((item,i)=>`
                <div style="display:flex;align-items:center;gap:4px;margin-bottom:2px">
                    <div style="width:7px;height:7px;border-radius:50%;background:${COLORS[i%8]};flex-shrink:0"></div>
                    <span style="font-size:10px;color:#888;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:72px">${item.t}</span>
                    <span style="font-size:10px;color:#555;margin-left:auto">${item.v}</span>
                </div>`).join('');
            return`<div style="flex:1;min-width:130px;background:#1e1e1e;border-radius:10px;padding:10px;border:0.5px solid #2a2a2a">
                <div style="font-size:11px;font-weight:500;color:${color};margin-bottom:8px;text-align:center">${field}</div>
                <div style="display:flex;align-items:center;gap:8px">
                    <svg viewBox="0 0 100 100" style="width:65px;height:65px;flex-shrink:0">
                        <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#2a2a2a" stroke-width="${sw}"/>
                        ${slices}
                        <text x="${cx}" y="${cy}" text-anchor="middle" dominant-baseline="middle"
                            style="font-size:13px;fill:#888;font-weight:500">${total}</text>
                    </svg>
                    <div style="flex:1;overflow:hidden">${legend}</div>
                </div>
            </div>`;
        };

        el.innerHTML=`
        <div style="font-size:11px;color:#444;letter-spacing:.5px;margin-bottom:8px">主题分布</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
            ${donut('买入','#dc3545')}${donut('卖出','#28a745')}${donut('定投','#ffc107')}
        </div>`;
    }

    _renderTop20(data) {
        const el=document.getElementById('bt-top20'); if(!el)return;
        if(!data.length){el.innerHTML='';return;}
        const fm={};
        data.forEach(r=>{
            if(!fm[r.fund_code])fm[r.fund_code]={code:r.fund_code,name:r.fund_name,topic:r.topic,buy:0,sell:0,dip:0,bl:new Set()};
            if(r.action==='买入')fm[r.fund_code].buy++;
            else if(r.action==='卖出')fm[r.fund_code].sell++;
            else fm[r.fund_code].dip++;
            fm[r.fund_code].bl.add(r.blogger_name);
        });
        const funds=Object.values(fm).map(f=>({...f,bl:f.bl.size,tot:f.buy+f.sell+f.dip}))
            .sort((a,b)=>b.buy-a.buy||b.tot-a.tot).slice(0,20);
        const maxBuy=funds[0]?.buy||1;
        const rows=funds.map((f,i)=>{
            const mine=this._myFundCodes.includes(String(f.code));
            const bw=Math.max(2,Math.round(f.buy/maxBuy*60));
            return`<div style="display:grid;grid-template-columns:22px 1fr 45px 45px 45px 38px;gap:5px;
                align-items:center;padding:5px 8px;border-radius:5px;font-size:12px;
                ${mine?'background:rgba(0,123,255,.06);border-left:2px solid #007bff;':''}" >
                <span style="color:#444;font-size:10px;text-align:right">${i+1}</span>
                <div style="overflow:hidden">
                    <div style="color:#ddd;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                        ${f.name}${mine?'<span class="bt-self">自选</span>':''}
                    </div>
                    <div style="display:flex;align-items:center;gap:5px;margin-top:1px">
                        <span style="font-size:10px;color:#444;font-family:monospace">${f.code}</span>
                        <div style="height:3px;width:${bw}px;background:#dc3545;border-radius:2px;opacity:.7"></div>
                    </div>
                </div>
                <span style="color:#dc3545;font-size:11px;text-align:center">${f.buy?f.buy+'买':''}</span>
                <span style="color:#28a745;font-size:11px;text-align:center">${f.sell?f.sell+'卖':''}</span>
                <span style="color:#ffc107;font-size:11px;text-align:center">${f.dip?f.dip+'投':''}</span>
                <span style="color:#444;font-size:11px;text-align:center">${f.bl}人</span>
            </div>`;
        }).join('');
        el.innerHTML=`
        <div style="font-size:11px;color:#444;letter-spacing:.5px;margin-bottom:8px">博主买入 TOP${funds.length} 基金</div>
        <div style="background:#1e1e1e;border-radius:10px;padding:8px;border:0.5px solid #2a2a2a">
            <div style="display:grid;grid-template-columns:22px 1fr 45px 45px 45px 38px;gap:5px;
                padding:3px 8px;margin-bottom:3px;font-size:10px;color:#444">
                <span>#</span><span>基金</span>
                <span style="text-align:center">买入</span><span style="text-align:center">卖出</span>
                <span style="text-align:center">定投</span><span style="text-align:center">博主</span>
            </div>${rows}
        </div>`;
    }

    _renderTable(data) {
        const wrap=document.getElementById('bt-table-wrap'); if(!wrap)return;
        if(!data.length){
            wrap.innerHTML='<div style="color:#444;font-size:12px;padding:16px 0;text-align:center">无符合条件的数据</div>';
            return;
        }
        const byDate={};
        data.forEach(r=>{
            const d=r.date||'未知';
            if(!byDate[d])byDate[d]={};
            const t=r.topic||'其他';
            if(!byDate[d][t])byDate[d][t]=[];
            byDate[d][t].push(r);
        });
        let html='';
        Object.keys(byDate).sort().reverse().forEach(date=>{
            html+=`<div style="font-size:12px;font-weight:500;color:#007bff;padding:12px 0 6px;border-bottom:0.5px solid #222;margin-bottom:4px">${date}</div>`;
            Object.entries(byDate[date]).forEach(([topic,items])=>{
                html+=`<div style="font-size:10px;color:#444;padding:6px 0 3px;letter-spacing:.4px">${topic}</div>`;
                html+=`<div class="bt-row" style="font-size:10px;color:#444;border-bottom:none;padding:3px 10px">
                    <span>博主</span><span>操作</span><span>金额</span><span>基金名称</span><span>代码</span><span>近一年</span></div>`;
                items.forEach(r=>{
                    const mine=this._myFundCodes.includes(String(r.fund_code));
                    const ac=r.action==='买入'?'bt-buy':r.action==='卖出'?'bt-sell':'bt-dip';
                    const yr=r.yearly_return?`+${(parseFloat(r.yearly_return)*100||0).toFixed(0)}%`:'--';
                    html+=`<div class="bt-row${mine?' bt-mine':''}">
                        <span style="color:#ddd;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${r.blogger_name}</span>
                        <span class="${ac}">${r.action}</span>
                        <span style="color:#777">${r.amount||'--'}</span>
                        <span style="color:#ddd;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${r.fund_name}${mine?'<span class="bt-self">自选</span>':''}</span>
                        <span style="color:#444;font-family:monospace;font-size:11px">${r.fund_code}</span>
                        <span style="color:#555">${yr}</span>
                    </div>`;
                });
                html+='<div style="margin-bottom:10px"></div>';
            });
        });
        wrap.innerHTML=html;
    }

    _parseAndUpload(file) {
        const msg=document.getElementById('bt-upload-msg');
        msg.style.display='block'; msg.style.color='#aaa'; msg.textContent='正在解析...';
        const reader=new FileReader();
        reader.onload=e=>{
            try{
                const wb=XLSX.read(e.target.result,{type:'array'});
                const raw=XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]],{header:1,defval:''});
                const res=this._parseRawRows(raw,file.name);
                if(!res.ok){msg.textContent='❌ '+res.error;msg.style.color='#dc3545';return;}
                msg.textContent=`已解析 ${res.records.length} 条，上传中...`;
                this._doUpload(res,msg,null);
            }catch(err){msg.textContent='❌ '+err.message;msg.style.color='#dc3545';}
        };
        reader.readAsArrayBuffer(file);
    }

    _parseAndUploadFromSettings(file,msgEl) {
        const sm=(t,c='#888')=>{if(msgEl){msgEl.textContent=t;msgEl.style.color=c;}};
        sm('正在解析...');
        const reader=new FileReader();
        reader.onload=e=>{
            try{
                const wb=XLSX.read(e.target.result,{type:'array'});
                const raw=XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]],{header:1,defval:''});
                const res=this._parseRawRows(raw,file.name);
                if(!res.ok){sm('❌ '+res.error,'#dc3545');return;}
                sm(`已解析 ${res.records.length} 条，上传中...`);
                this._doUpload(res,null,sm);
            }catch(err){sm('❌ '+err.message,'#dc3545');}
        };
        reader.readAsArrayBuffer(file);
    }

    _doUpload(result,msgEl,setMsg) {
        fetch('/api/blogger-signals',{
            method:'POST',headers:{'Content-Type':'application/json'},
            body:JSON.stringify(result.records),
        })
        .then(r=>r.json())
        .then(res=>{
            const bj=new Date(new Date().toLocaleString('en-US',{timeZone:'Asia/Shanghai'}));
            const ts=`${bj.getFullYear()}-${String(bj.getMonth()+1).padStart(2,'0')}-${String(bj.getDate()).padStart(2,'0')} ${String(bj.getHours()).padStart(2,'0')}:${String(bj.getMinutes()).padStart(2,'0')}`;
            const dup=result.originalCount>(res.unique||res.inserted)?`，${result.originalCount-(res.unique||res.inserted)}条重复已合并`:'';
            const txt=res.success?`✅ 成功 ${res.inserted} 条${dup} | ${ts}`:`❌ ${res.error}`;
            const c=res.success?'#28a745':'#dc3545';
            if(msgEl){msgEl.textContent=txt;msgEl.style.color=c;}
            if(setMsg)setMsg(txt,c);
            if(res.success){this._refreshGlobalSignals();if(window.activeTab==='blogger-tracker')this._loadAndRender();}
        })
        .catch(()=>{
            if(msgEl){msgEl.textContent='❌ 网络错误';msgEl.style.color='#dc3545';}
            if(setMsg)setMsg('❌ 网络错误','#dc3545');
        });
    }

    _parseRawRows(raw,fileName) {
        let hi=-1;
        for(let i=0;i<Math.min(raw.length,5);i++){
            const s=(raw[i]||[]).map(c=>String(c)).join('');
            if(s.includes('博主')&&s.includes('操作')){hi=i;break;}
        }
        if(hi===-1)return{ok:false,error:'未找到表头行（需包含"博主"和"操作"列）'};
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
        if(ci.fc===undefined)return{ok:false,error:'文件里没有"基金代码"列，请新增后重试'};

        let fileDate='';
        for(let i=0;i<hi;i++){
            const m=String((raw[i]||[]).join('')).match(/(\d{4})[.\-\/](\d{1,2})[.\-\/](\d{1,2})/);
            if(m){fileDate=`${m[1]}-${m[2].padStart(2,'0')}-${m[3].padStart(2,'0')}`;break;}
        }
        if(!fileDate){
            const fn=(fileName||'').replace(/\.xlsx?$/i,'');
            const m3=fn.match(/^(\d{1,2})[_\-](\d{1,2})/);
            if(m3)fileDate=`${new Date().getFullYear()}-${m3[1].padStart(2,'0')}-${m3[2].padStart(2,'0')}`;
            else{const m2=fn.match(/(\d{4})(\d{2})(\d{2})/);
                if(m2)fileDate=`${m2[1]}-${m2[2]}-${m2[3]}`;
                else{const bj=new Date(new Date().toLocaleString('en-US',{timeZone:'Asia/Shanghai'}));
                    fileDate=`${bj.getFullYear()}-${String(bj.getMonth()+1).padStart(2,'0')}-${String(bj.getDate()).padStart(2,'0')}`;}}
        }

        const recs=[],VALID=new Set(['买入','卖出','定投']);
        let ct='';
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
            recs.push({date:fileDate,blogger_name:blogger,fund_code:fc,fund_name:fn,action,
                amount:String(row[ci.amount]??'').trim(),topic:ct,
                yearly_return:String(row[ci.yr]??'').trim()});
        }
        if(!recs.length)return{ok:false,error:`未解析到有效数据（表头第${hi+1}行，共${raw.length-hi-1}行）`};
        const dd={};
        recs.forEach(r=>{
            const k=`${r.blogger_name}||${r.fund_code}||${r.action}`;
            if(!dd[k])dd[k]={...r};
            else dd[k].amount=[dd[k].amount,r.amount].filter(Boolean).join('+');
        });
        return{ok:true,records:Object.values(dd),fileDate,originalCount:recs.length};
    }

    _refreshGlobalSignals() {
        fetch('/api/blogger-signals')
            .then(r=>r.ok?r.json():[])
            .then(data=>{
                window._bloggerSignals=data||[];
                if(window.activeTab!=='blogger-tracker'){
                    try{
                        const cached=cacheManager.get('fundsList');
                        if(cached&&typeof renderFunds==='function')renderFunds(cached);
                    }catch(_){}
                }
            }).catch(()=>{});
    }
}

const bloggerTracker = new BloggerTracker();
window.bloggerTracker = bloggerTracker;
bloggerTracker._refreshGlobalSignals();