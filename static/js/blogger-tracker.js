// blogger-tracker.js — 博主追踪模块（3.0）
// 职责：解析 xlsx、上传博主信号、展示博主操作汇总

class BloggerTracker {
    constructor() {
        this._signals = [];       // 当前展示的信号数据
        this._myFundCodes = [];   // 用户自选基金代码列表
        this._rendered = false;
        this._currentDate = '';
    }

    // ── 入口：切换到博主追踪 tab 时调用 ────────────────────────────────────
    show() {
        const container = document.getElementById('funds-container');
        const header    = document.getElementById('fund-list-header');
        const searchBar = document.querySelector('.search-container');
        if (searchBar) searchBar.style.display = 'none';
        if (header)    header.style.display    = 'none';

        // 第一次进入时渲染骨架
        if (!this._rendered) {
            this._renderShell(container);
            this._rendered = true;
        }

        // 拉取用户自选基金代码（用于高亮重合）
        this._loadMyFundCodes();

        // 如果已有上传过的数据，自动加载最近一天
        this._loadLatest();
    }

    // ── 从设置弹窗调用的上传（带弹窗提示）──────────────────────────────
    _parseAndUploadFromSettings(file, msgEl) {
        const setMsg = (text, color='#888') => {
            if (msgEl) { msgEl.textContent = text; msgEl.style.color = color; }
        };
        setMsg('正在解析文件...');
        const reader = new FileReader();
        reader.onload = e => {
            try {
                const wb = XLSX.read(e.target.result, { type: 'array' });
                const ws = wb.Sheets[wb.SheetNames[0]];
                const raw = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' });
                // 复用解析逻辑
                const result = this._parseRawRows(raw, file.name);
                if (!result.ok) { setMsg('❌ ' + result.error, '#dc3545'); return; }
                setMsg(`已解析 ${result.records.length} 条，上传中...`);
                fetch('/api/blogger-signals', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(result.records),
                })
                .then(r => r.json())
                .then(res => {
                    if (res.success) {
                        const bj = new Date(new Date().toLocaleString('en-US',{timeZone:'Asia/Shanghai'}));
                        const ts = `${bj.getFullYear()}-${String(bj.getMonth()+1).padStart(2,'0')}-${String(bj.getDate()).padStart(2,'0')} ${String(bj.getHours()).padStart(2,'0')}:${String(bj.getMinutes()).padStart(2,'0')}`;
                        setMsg(`✅ 上传成功 ${res.inserted} 条｜Supabase 更新于 ${ts}`, '#28a745');
                        // 刷新全局信号数据
                        this._refreshGlobalSignals();
                    } else {
                        setMsg('❌ ' + res.error, '#dc3545');
                    }
                })
                .catch(() => setMsg('❌ 网络错误', '#dc3545'));
            } catch(err) {
                setMsg('❌ 解析失败：' + err.message, '#dc3545');
            }
        };
        reader.readAsArrayBuffer(file);
    }

    // ── 把解析逻辑抽取为独立方法，供两个上传入口复用 ──────────────────────
    _parseRawRows(raw, fileName) {
        // ── 自动检测表头行（找到包含"博主"和"操作"的那一行）────────────────
        let headerRowIdx = -1;
        for (let i = 0; i < Math.min(raw.length, 5); i++) {
            const row = raw[i] || [];
            const rowStr = row.map(c => String(c)).join('');
            if (rowStr.includes('博主') && rowStr.includes('操作')) {
                headerRowIdx = i;
                break;
            }
        }
        if (headerRowIdx === -1)
            return { ok: false, error: '未找到表头行，请确认文件包含"博主"和"操作"列' };

        const headerRow = raw[headerRowIdx];
        const colIdx = {};
        headerRow.forEach((h, i) => {
            const k = String(h).trim();
            if (k.includes('主题'))                             colIdx.topic         = i;
            if (k.includes('博主'))                             colIdx.blogger_name  = i;
            if (k.includes('近一年'))                           colIdx.yearly_return = i;
            if (k.includes('操作'))                             colIdx.action        = i;
            if (k.includes('金额'))                             colIdx.amount        = i;
            if (k.includes('修正后名称') || k.includes('基金名称')) colIdx.fund_name  = i;
            if (k.includes('基金代码') || k.includes('fund_code')) colIdx.fund_code  = i;
        });
        // 如果同时有"修正后名称"和"基金名称"，优先用修正后名称
        headerRow.forEach((h, i) => {
            if (String(h).trim().includes('修正后名称')) colIdx.fund_name = i;
        });

        if (colIdx.fund_code === undefined)
            return { ok: false, error: '文件里没有"基金代码"列，请新增后重试' };

        // ── 推算日期：从文件名或表头上方的标题行中提取 ──────────────────────
        let fileDate = '';
        // 先扫描表头行之前的行找日期
        for (let i = 0; i < headerRowIdx; i++) {
            const titleText = String(raw[i]?.[0] || '') + String(raw[i]?.[1] || '');
            const m = titleText.match(/(\d{4})[.\-\/](\d{1,2})[.\-\/](\d{1,2})/);
            if (m) { fileDate = `${m[1]}-${m[2].padStart(2,'0')}-${m[3].padStart(2,'0')}`; break; }
        }
        if (!fileDate) {
            // 从文件名提取日期
            // 优先找 M_DD 或 MM_DD 短格式（如 4_21_v3.xlsx），避免误识别时间戳（20260426_151258）
            const _fn = (fileName || '').replace(/\.xlsx?$/i, '');
            const m3 = _fn.match(/^(\d{1,2})[_\-](\d{1,2})/);  // 开头的 M_DD
            if (m3) {
                fileDate = `${new Date().getFullYear()}-${m3[1].padStart(2,'0')}-${m3[2].padStart(2,'0')}`;
            } else {
                // 降级：找 YYYYMMDD 格式
                const m2 = _fn.match(/(\d{4})(\d{2})(\d{2})/);
                if (m2) {
                    fileDate = `${m2[1]}-${m2[2]}-${m2[3]}`;
                } else {
                    // 默认今天
                    const bj = new Date(new Date().toLocaleString('en-US',{timeZone:'Asia/Shanghai'}));
                    fileDate = `${bj.getFullYear()}-${String(bj.getMonth()+1).padStart(2,'0')}-${String(bj.getDate()).padStart(2,'0')}`;
                }
            }
        }

        // ── 解析数据行 ──────────────────────────────────────────────────────
        const records = [];
        let currentTopic = '';
        const VALID_ACTIONS = new Set(['买入','卖出','定投']);

        for (let i = headerRowIdx + 1; i < raw.length; i++) {
            const row = raw[i];
            if (!row || row.every(c => c === '' || c === null || c === undefined)) continue;

            // 主题列（可能是合并单元格，有值就更新当前主题）
            const topicVal = String(row[colIdx.topic] ?? '').trim().replace(/[​ ‌]/g,'').trim();
            if (topicVal && topicVal !== 'undefined') currentTopic = topicVal;

            const fund_code_raw = row[colIdx.fund_code];
            const fund_code = fund_code_raw != null && String(fund_code_raw).trim() !== '' && String(fund_code_raw) !== 'NaN'
                ? String(Math.floor(Number(fund_code_raw))).padStart(6, '0')  // 数字型代码补零
                : '';
            if (!fund_code) continue;  // 无代码（failed/all_rejected）跳过

            // fund_name 优先修正后名称，降级原始名称
            const fund_name_raw = colIdx.fund_name !== undefined ? String(row[colIdx.fund_name] ?? '').trim() : '';
            const fund_name = fund_name_raw && fund_name_raw !== 'NaN' ? fund_name_raw
                : String(row[headerRow.indexOf('基金名称')] ?? '').trim();
            if (!fund_name) continue;

            const action  = String(row[colIdx.action] ?? '').trim();
            const blogger = String(row[colIdx.blogger_name] ?? '').trim();
            if (!blogger || !VALID_ACTIONS.has(action)) continue;

            records.push({
                date:          fileDate,
                blogger_name:  blogger,
                fund_code,
                fund_name,
                action,
                amount:        String(row[colIdx.amount] ?? '').trim(),
                topic:         currentTopic,
                yearly_return: String(row[colIdx.yearly_return] ?? '').trim(),
            });
        }

        if (records.length === 0)
            return { ok: false, error: `没有解析到有效数据（表头在第${headerRowIdx+1}行，共扫描${raw.length - headerRowIdx - 1}行，需要：有效基金代码 + 买入/卖出/定投）` };
        return { ok: true, records, fileDate };
    }

    // ── 刷新全局信号数据（供基金列表标签使用）───────────────────────────
    _refreshGlobalSignals() {
        fetch('/api/blogger-signals')
            .then(r => r.ok ? r.json() : [])
            .then(data => { window._bloggerSignals = data || []; })
            .catch(() => {});
    }

    // ── 隐藏（切换到其他 tab 时恢复搜索框）────────────────────────────────
    hide() {
        const searchBar = document.querySelector('.search-container');
        const header    = document.getElementById('fund-list-header');
        if (searchBar) searchBar.style.display = '';
        if (header)    header.style.display    = '';
    }

    // ── 加载用户自选基金代码 ─────────────────────────────────────────────
    _loadMyFundCodes() {
        fetch('/api/funds?basic_only=1')
            .then(r => r.ok ? r.json() : [])
            .then(funds => {
                this._myFundCodes = (funds || []).map(f => String(f.code));
            })
            .catch(() => {});
    }

    // ── 加载最近一次上传的数据 ──────────────────────────────────────────
    _loadLatest() {
        fetch('/api/blogger-signals')
            .then(r => r.ok ? r.json() : [])
            .then(data => {
                if (data && data.length > 0) {
                    this._signals = data;
                    // 找最新日期
                    const dates = [...new Set(data.map(d => d.date))].sort().reverse();
                    this._currentDate = dates[0];
                    this._updateDateSelector(dates);
                    this._renderTable(data.filter(d => d.date === this._currentDate));
                } else {
                    this._renderEmpty();
                }
            })
            .catch(() => this._renderEmpty());
    }

    // ── 渲染主骨架（上传区 + 日期选择 + 表格区）───────────────────────────
    _renderShell(container) {
        container.innerHTML = `
<div id="bt-wrap" style="padding:0 4px">
  <!-- 上传区 -->
  <div id="bt-upload-area" style="
    border:1.5px dashed #333333;
    border-radius:12px;padding:28px 20px;text-align:center;
    margin-bottom:16px;cursor:pointer;transition:border-color .15s;
  " onclick="document.getElementById('bt-file-input').click()">
    <div style="font-size:13px;color:#aaaaaa;margin-bottom:8px">
      点击上传博主实盘 xlsx 文件
    </div>
    <div style="font-size:11px;color:#666666">
      需包含：主题、博主、近一年、操作、金额、基金名称、基金代码
    </div>
    <input type="file" id="bt-file-input" accept=".xlsx,.xls" style="display:none">
  </div>

  <!-- 上传进度提示 -->
  <div id="bt-upload-msg" style="display:none;font-size:12px;color:#aaaaaa;
    margin-bottom:12px;padding:8px 12px;background:#2a2a2a;
    border-radius:8px;"></div>

  <!-- 日期选择 -->
  <div id="bt-date-row" style="display:none;align-items:center;gap:10px;margin-bottom:12px">
    <span style="font-size:12px;color:#666666">日期</span>
    <select id="bt-date-sel" style="
      background:#2a2a2a;color:#e0e0e0;
      border:0.5px solid #333333;border-radius:6px;
      padding:4px 10px;font-size:12px;cursor:pointer;
    "></select>
    <span id="bt-count" style="font-size:11px;color:#666666"></span>
  </div>

  <!-- 操作筛选 -->
  <div id="bt-filter-row" style="display:none;gap:8px;margin-bottom:14px;flex-wrap:wrap">
    <button class="bt-filter-btn active" data-action="">全部</button>
    <button class="bt-filter-btn" data-action="买入">买入</button>
    <button class="bt-filter-btn" data-action="卖出">卖出</button>
    <button class="bt-filter-btn" data-action="定投">定投</button>
  </div>

  <!-- 表格 -->
  <div id="bt-table-wrap"></div>
</div>

<style>
#bt-wrap { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
.bt-filter-btn {
  background: #2a2a2a;
  color: #aaaaaa;
  border: 0.5px solid #2a2a2a;
  border-radius: 6px; padding: 4px 12px;
  font-size: 12px; cursor: pointer; transition: all .15s;
}
.bt-filter-btn.active {
  background: #007bff; color: #fff; border-color: #007bff;
}
.bt-row { display:grid; grid-template-columns: 80px 90px 80px 1fr 70px 60px; gap:8px;
  align-items:center; padding:9px 10px; border-radius:8px;
  border-bottom: 0.5px solid #2a2a2a; font-size:12px; }
.bt-row:hover { background: #2a2a2a; }
.bt-hd { font-weight:500; color:#666666; font-size:11px;
  padding:6px 10px; letter-spacing:.4px; }
.bt-buy  { color: #dc3545; font-weight:500; }
.bt-sell { color: #28a745; font-weight:500; }
.bt-dip  { color: #ffc107; font-weight:500; }
.bt-mine { background: rgba(0,123,255,.06); border-left: 2px solid #007bff !important; }
.bt-tag { display:inline-block; font-size:10px; padding:1px 6px; border-radius:4px;
  background:rgba(0,123,255,.12); color:#4a9eff; margin-left:4px; }
.bt-topic { font-size:11px; color:#666666; }
</style>`;

        // 绑定文件上传
        document.getElementById('bt-file-input').addEventListener('change', e => {
            const file = e.target.files[0];
            if (file) this._parseAndUpload(file);
            e.target.value = ''; // 允许重复上传同一文件
        });

        // 拖拽上传
        const area = document.getElementById('bt-upload-area');
        area.addEventListener('dragover', e => { e.preventDefault(); area.style.borderColor='#007bff'; });
        area.addEventListener('dragleave', () => { area.style.borderColor=''; });
        area.addEventListener('drop', e => {
            e.preventDefault(); area.style.borderColor='';
            const file = e.dataTransfer.files[0];
            if (file && (file.name.endsWith('.xlsx') || file.name.endsWith('.xls'))) {
                this._parseAndUpload(file);
            }
        });

        // 日期切换
        document.getElementById('bt-date-sel').addEventListener('change', e => {
            this._currentDate = e.target.value;
            const filtered = this._signals.filter(d => d.date === this._currentDate);
            this._renderTable(filtered);
        });

        // 操作筛选
        document.getElementById('bt-filter-row').addEventListener('click', e => {
            const btn = e.target.closest('.bt-filter-btn');
            if (!btn) return;
            document.querySelectorAll('.bt-filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const action = btn.dataset.action;
            let filtered = this._signals.filter(d => d.date === this._currentDate);
            if (action) filtered = filtered.filter(d => d.action === action);
            this._renderTable(filtered);
        });
    }

    // ── 解析 xlsx 并上传（博主追踪 tab 内调用）─────────────────────────────
    _parseAndUpload(file) {
        const msg = document.getElementById('bt-upload-msg');
        msg.style.display = 'block';
        msg.textContent = '正在解析文件...';
        msg.style.color = '';
        const reader = new FileReader();
        reader.onload = e => {
            try {
                const wb = XLSX.read(e.target.result, { type: 'array' });
                const ws = wb.Sheets[wb.SheetNames[0]];
                const raw = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' });
                const result = this._parseRawRows(raw, file.name);
                if (!result.ok) {
                    msg.textContent = '❌ ' + result.error;
                    msg.style.color = '#dc3545';
                    return;
                }
                msg.textContent = `已解析 ${result.records.length} 条，正在上传...`;
                fetch('/api/blogger-signals', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(result.records),
                })
                .then(r => r.json())
                .then(res => {
                    if (res.success) {
                        msg.textContent = `✅ 上传成功：${res.inserted} 条`;
                        this._refreshGlobalSignals();
                        this._loadLatest();
                    } else {
                        msg.textContent = '❌ 上传失败：' + res.error;
                        msg.style.color = '#dc3545';
                    }
                })
                .catch(() => { msg.textContent = '❌ 网络错误'; });
            } catch (err) {
                msg.textContent = '❌ 解析失败：' + err.message;
                msg.style.color = '#dc3545';
            }
        };
        reader.readAsArrayBuffer(file);
    }

    // ── 更新日期选择器 ──────────────────────────────────────────────────
    _updateDateSelector(dates) {
        const sel = document.getElementById('bt-date-sel');
        const row = document.getElementById('bt-date-row');
        const filterRow = document.getElementById('bt-filter-row');
        if (!sel) return;

        sel.innerHTML = dates.map(d => `<option value="${d}">${d}</option>`).join('');
        row.style.display = 'flex';
        filterRow.style.display = 'flex';
    }

    // ── 渲染表格 ────────────────────────────────────────────────────────
    _renderTable(rows) {
        const wrap = document.getElementById('bt-table-wrap');
        const countEl = document.getElementById('bt-count');
        if (!wrap) return;

        if (countEl) countEl.textContent = `${rows.length} 条`;

        if (rows.length === 0) {
            wrap.innerHTML = '<div style="color:#666666;font-size:12px;padding:20px 0">暂无数据</div>';
            return;
        }

        // 按主题分组
        const grouped = {};
        rows.forEach(r => {
            const t = r.topic || '其他';
            if (!grouped[t]) grouped[t] = [];
            grouped[t].push(r);
        });

        let html = '';
        for (const [topic, items] of Object.entries(grouped)) {
            html += `<div style="font-size:11px;font-weight:500;color:#666666;
                letter-spacing:.5px;padding:12px 0 6px;border-bottom:0.5px solid #2a2a2a;
                margin-bottom:4px">${topic}</div>`;

            // 表头
            html += `<div class="bt-row bt-hd" style="border-bottom:none">
                <span>博主</span><span>操作</span><span>金额</span>
                <span>基金名称</span><span>代码</span><span>近一年</span>
            </div>`;

            items.forEach(r => {
                const isMine = this._myFundCodes.includes(String(r.fund_code));
                const actionCls = r.action === '买入' ? 'bt-buy' : r.action === '卖出' ? 'bt-sell' : 'bt-dip';
                const mineTag = isMine ? '<span class="bt-tag">自选</span>' : '';
                const yr = r.yearly_return ? `+${(parseFloat(r.yearly_return)*100||0).toFixed(0)}%` : '';

                html += `<div class="bt-row${isMine ? ' bt-mine' : ''}">
                    <span style="color:#e0e0e0">${r.blogger_name}</span>
                    <span class="${actionCls}">${r.action}</span>
                    <span style="color:#aaaaaa">${r.amount || '--'}</span>
                    <span style="color:#e0e0e0">${r.fund_name}${mineTag}</span>
                    <span style="color:#666666;font-family:"SF Mono", "Fira Code", monospace;font-size:11px">${r.fund_code}</span>
                    <span style="color:#aaaaaa">${yr}</span>
                </div>`;
            });

            html += '<div style="margin-bottom:16px"></div>';
        }

        wrap.innerHTML = html;
    }

    // ── 空状态 ──────────────────────────────────────────────────────────
    _renderEmpty() {
        const wrap = document.getElementById('bt-table-wrap');
        if (wrap) wrap.innerHTML = `
            <div style="color:#666666;font-size:12px;padding:30px 0;text-align:center">
                暂无数据，请上传博主实盘 xlsx 文件
            </div>`;
    }
}

// 初始化并挂载到全局
const bloggerTracker = new BloggerTracker();
window.bloggerTracker = bloggerTracker;

// 页面加载后静默预拉博主信号，供基金列表标签显示
bloggerTracker._refreshGlobalSignals();

// 监听其他 tab 切换时隐藏博主追踪界面
window.addEventListener('updateFundList', () => {
    if (window.activeTab !== 'blogger-tracker') bloggerTracker.hide();
});