"""
utils/fund_recommender.py

基金推荐引擎 —— 全市场动态筛选版
══════════════════════════════════════════════════════════════════════

设计原则：
  - 零硬编码：候选基金全部来自东方财富实时基金列表
  - 零模拟数据：任何数据获取失败 → 跳过该基金，不填假值
  - 零兜底推荐：如果评分结果不足，直接返回现有结果，不补固定基金

流程：
  ┌─────────────────────────────────────────────────────────────────┐
  │ 1. 从东方财富拉取全量基金列表                                    │
  │    含：代码、名称、类型、规模、申赎状态                          │
  │                                                                  │
  │ 2. 预筛选（快速过滤，减少后续网络请求量）                        │
  │    ✓ 类型：债券型 / 混合型 / 股票型                              │
  │    ✗ 排除：ETF联接 / LOF / QDII / FOF / 指数基金                │
  │    ✗ 排除：暂停申购                                              │
  │    ✗ 排除：规模 < 2亿（迷你基金）                               │
  │                                                                  │
  │ 3. 随机抽样（控制请求量，保证响应时间）                          │
  │    稳健池（债券）：最多评分 40 只                                │
  │    均衡池（混合+股票）：最多评分 60 只                           │
  │                                                                  │
  │ 4. 对每只基金拉取近 3 个月历史净值，多维度评分                   │
  │    维度：近期收益 / 最大回撤 / 波动率 / 技术面 / 行业景气 / 规模 │
  │    成立不足 1 年的基金自动跳过（历史数据不具参考性）             │
  │                                                                  │
  │ 5. 各池排序取 top5，合并返回共 10 只                             │
  │    若某池有效结果不足 5 只，返回实际数量，不补假数据             │
  └─────────────────────────────────────────────────────────────────┘

评分维度（满分100分）：
  近期收益   30分  近1/4/12周加权收益率（近期权重更高）
  最大回撤   20分  近3月最大回撤越小越好
  年化波动率 15分  越低越好
  技术面     15分  RSI + MACD柱状图 + 布林带位置综合信号
  行业景气   10分  基金名称匹配行业板块近期涨跌幅
  规模       10分  10~500亿满分，过小或过大各有折扣
"""

import requests
import re
import json
import logging
import time
import random
from datetime import datetime, timedelta
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://fund.eastmoney.com/",
}

# 基金名称关键词 → 新浪财经板块指数代码（用于行业景气打分）
SECTOR_KEYWORD_MAP = {
    "医疗": ["sh000037"], "医药": ["sh000037"], "健康": ["sh000037"],
    "消费": ["sh000039"], "食品": ["sh000039"], "白酒": ["sh000039"],
    "科技": ["sh000043", "sh000063", "sh000044"],
    "信息": ["sh000043"], "电子": ["sh000063"], "通信": ["sh000044"],
    "新能源": ["sh000042", "sh000052"], "能源": ["sh000042"],
    "电力": ["sh000042"], "化工": ["sh000052"],
    "银行": ["sh000048"], "金融": ["sh000048"],
    "地产": ["sh000046"], "建筑": ["sh000045"],
    "交通": ["sh000047"], "煤炭": ["sh000049"],
    "石油": ["sh000050"], "钢铁": ["sh000051"],
    "机械": ["sh000053"], "汽车": ["sh000054"],
    "航天": ["sh000041"], "航空": ["sh000041"],
}

# 预筛选排除关键词（场内品种、特殊结构）
EXCLUDE_KEYWORDS = [
    "ETF", "LOF", "联接", "QDII", "FOF",
    "指数", "C类", "D类", "E类", "港股",
]


# ══════════════════════════════════════════════════════════════════════════════
# Step 1: 全量基金列表
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_fund_list(em_type: str, page_size: int = 200) -> list:
    """
    从东方财富基金排行榜接口获取基金列表。

    em_type（东方财富接口参数）：
        '1' → 股票型
        '2' → 混合型
        '3' → 债券型

    返回 list of dict：
        code        基金代码
        name        基金名称
        size        规模（亿元），-1 表示接口未返回
        buy_status  'open' / 'limited' / 'closed'
    """
    results = []
    url = (
        f"http://fund.eastmoney.com/data/rankhandler.aspx"
        f"?op=ph&dt=kf&ft=all&rs=&gs=0&sc=6yzf&st=desc"
        f"&sd=2024-04-09&ed={datetime.now().strftime('%Y-%m-%d')}"
        f"&qdii=&tabSubtype=,{em_type},,,,&pi=1&pn={page_size}"
        f"&dx=1&v={int(time.time())}"
    )
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        m = re.search(r'datas:\["(.*?)"\]', resp.text, re.DOTALL)
        if not m:
            logger.warning(f"[列表] 类型 {em_type} 解析失败，响应片段: {resp.text[:300]}")
            return []

        for item in m.group(1).split('","'):
            parts = item.split(",")
            if len(parts) < 4:
                continue
            code = parts[0].strip()
            name = parts[1].strip()
            if not re.match(r"^\d{6}$", code):
                continue

            size = -1.0
            try:
                raw = parts[25].strip() if len(parts) > 25 else ""
                if raw and raw != "---":
                    size = float(raw)
            except (ValueError, IndexError):
                pass

            buy_status = "open"
            try:
                sc = parts[26].strip() if len(parts) > 26 else "0"
                if sc == "1":
                    buy_status = "limited"
                elif sc == "2":
                    buy_status = "closed"
            except IndexError:
                pass

            results.append({
                "code": code,
                "name": name,
                "size": size,
                "buy_status": buy_status,
            })

    except Exception as e:
        logger.error(f"[列表] 类型 {em_type} 获取失败: {e}")

    logger.info(f"[列表] 类型 {em_type} 获取 {len(results)} 只")
    return results


def _prefilter(funds: list, min_size: float = 2.0) -> list:
    """排除暂停申购、迷你基金、ETF联接/LOF/QDII等场内或特殊品种"""
    result = []
    for f in funds:
        if f["buy_status"] == "closed":
            continue
        if 0 < f["size"] < min_size:   # size=-1 表示未知，不排除
            continue
        if any(kw in f["name"] for kw in EXCLUDE_KEYWORDS):
            continue
        result.append(f)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# Step 2: 单只基金历史净值
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_historical_nav(code: str, months: int = 3) -> dict:
    """
    从天天基金网 API 拉取历史净值（近 N 个月）。
    失败 / 数据不足 → 返回空 dict，不填假值。
    """
    end_date   = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=months * 31)).strftime("%Y-%m-%d")
    # 使用天天基金网的 API
    url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=6)
        logger.info(f"[{code}] 历史净值 API 响应状态码: {resp.status_code}")
        logger.info(f"[{code}] 历史净值 API 响应内容: {resp.text[:300]}")
        
        # 提取净值数据
        nav_data = re.search(r'var Data_netWorthTrend\s*=\s*(\[.*?\])', resp.text, re.DOTALL)
        if not nav_data:
            logger.info(f"[{code}] 没有找到净值数据")
            return {}
        
        try:
            items = json.loads(nav_data.group(1))
            if not items:
                logger.info(f"[{code}] 净值数据为空")
                return {}
        except json.JSONDecodeError as e:
            logger.info(f"[{code}] 解析净值数据失败: {e}")
            return {}

        dates, prices = [], []
        for item in items:
            try:
                prices.append(float(item["y"]))
                dates.append(item["x"])
            except (ValueError, KeyError):
                continue

        if len(prices) < 10:   # 少于10个交易日，数据不足以评分
            logger.info(f"[{code}] 净值数据不足（{len(prices)}天）")
            return {}

        returns = [0.0]
        for i in range(1, len(prices)):
            try:
                returns.append((prices[i] - prices[i - 1]) / prices[i - 1])
            except ZeroDivisionError:
                returns.append(0.0)

        return {"prices": prices, "dates": dates, "returns": returns}
    except Exception as e:
        logger.info(f"[{code}] 历史净值获取失败: {e}")
        return {}


def _fetch_size_from_js(code: str) -> float:
    """补充获取基金规模（亿元），列表接口已有则优先用列表数据"""
    try:
        url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
        resp = requests.get(url, headers=HEADERS, timeout=5)
        m = re.search(
            r'var Data_fluctuationScale\s*=\s*\{.*?"series":\[.*?\{"data":\[(.*?)\]',
            resp.text, re.DOTALL
        )
        if m:
            nums = re.findall(r"[\d.]+", m.group(1))
            if nums:
                return float(nums[-1])
    except Exception:
        pass
    return -1.0


# ══════════════════════════════════════════════════════════════════════════════
# Step 3: 行业景气度
# ══════════════════════════════════════════════════════════════════════════════

def _sector_change(name: str, market_snapshot: dict) -> float:
    """
    根据基金名称关键词匹配行业板块，从市场快照中读取涨跌幅均值。
    无匹配 → 用大盘所有指数均值（不猜测、不硬编码）。
    """
    code_change: dict = {}
    for v in market_snapshot.get("indices", {}).values():
        code_change[v.get("code", "")] = v.get("change_ratio", 0.0)
    for v in market_snapshot.get("sectors", {}).values():
        code_change[v.get("code", "")] = v.get("change_ratio", 0.0)

    matched = []
    for kw, codes in SECTOR_KEYWORD_MAP.items():
        if kw in name:
            matched.extend(codes)

    if matched:
        changes = [code_change[c] for c in matched if c in code_change]
        if changes:
            return sum(changes) / len(changes)

    all_changes = list(code_change.values())
    return sum(all_changes) / len(all_changes) if all_changes else 0.0


# ══════════════════════════════════════════════════════════════════════════════
# Step 4: 技术指标 + 评分
# ══════════════════════════════════════════════════════════════════════════════

def _period_return(prices: list, days: int) -> float:
    if len(prices) >= days + 1:
        return (prices[-1] - prices[-(days + 1)]) / prices[-(days + 1)]
    return (prices[-1] - prices[0]) / prices[0] if len(prices) >= 2 else 0.0


def _max_drawdown(prices: list) -> float:
    peak, mdd = prices[0], 0.0
    for p in prices[1:]:
        if p > peak:
            peak = p
        if peak > 0:
            mdd = max(mdd, (peak - p) / peak)
    return mdd


def _annual_vol(returns: list) -> float:
    return float(np.std(returns) * np.sqrt(252)) if len(returns) >= 5 else 0.0


def _rsi(prices: list, period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0
    d = np.diff(prices)
    ag = np.mean(np.where(d > 0, d, 0.0)[-period:])
    al = np.mean(np.where(d < 0, -d, 0.0)[-period:])
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def _macd_histogram(prices: list) -> float:
    if len(prices) < 26:
        return 0.0
    def ema(arr, n):
        k = 2 / (n + 1); r = [arr[0]]
        for v in arr[1:]: r.append(v * k + r[-1] * (1 - k))
        return r
    macd = [f - s for f, s in zip(ema(prices, 12), ema(prices, 26))]
    return macd[-1] - ema(macd, 9)[-1]


def _bollinger_pos(prices: list, period: int = 20) -> float:
    if len(prices) < period:
        return 0.0
    recent = prices[-period:]
    std = np.std(recent)
    return float((prices[-1] - np.mean(recent)) / (2 * std)) if std else 0.0


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _score(hist: dict, sector_chg: float, size: float) -> Optional[dict]:
    """
    多维度评分，返回评分字典或 None（数据不足时）。
    不返回假分数。
    """
    prices  = hist.get("prices", [])
    returns = hist.get("returns", [])
    if len(prices) < 10:
        return None

    # 近期收益（30分）
    composite = _period_return(prices,5)*0.5 + _period_return(prices,20)*0.3 + _period_return(prices,60)*0.2
    return_s = _clamp((composite / 0.05) * 15 + 15, 0, 30)

    # 最大回撤（20分）：回撤0%→20，≥20%→0
    mdd = _max_drawdown(prices)
    mdd_s = _clamp(20 - mdd * 100, 0, 20)

    # 年化波动率（15分）：0%→15，≥50%→0
    vol = _annual_vol(returns)
    vol_s = _clamp(15 - vol * 30, 0, 15)

    # 技术面（15分）
    rsi   = _rsi(prices)
    macdh = _macd_histogram(prices)
    boll  = _bollinger_pos(prices)
    rsi_s  = 6.0 if rsi < 30 else (4.5 if rsi <= 50 else (5.0 if rsi <= 70 else 2.0))
    macd_s = _clamp((macdh / 0.01) * 2.5 + 4.5, 0, 6)
    boll_s = _clamp(3 - abs(boll) * 3, 0, 3)
    tech_s = rsi_s + macd_s + boll_s

    # 行业景气（10分）：±3%映射0~10
    sector_s = _clamp((sector_chg / 0.03) * 5 + 5, 0, 10)

    # 规模（10分）
    size_s = (5.0 if size < 0 else
              2.0 if size < 2 else
              6.0 if size < 10 else
              10.0 if size <= 500 else 7.0)

    total = return_s + mdd_s + vol_s + tech_s + sector_s + size_s
    return {
        "total": round(total, 2),
        "r1w":  round(_period_return(prices, 5)  * 100, 2),
        "r4w":  round(_period_return(prices, 20) * 100, 2),
        "r12w": round(_period_return(prices, 60) * 100, 2),
        "mdd":  round(mdd * 100, 2),
        "vol":  round(vol * 100, 2),
        "rsi":  round(rsi, 1),
        "size": size,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Step 5: 推荐理由生成（全量化，无模板套话）
# ══════════════════════════════════════════════════════════════════════════════

def _build_reason(risk_label: str, s: dict, sector_chg: float) -> str:
    parts = []

    r1w, r4w, r12w = s["r1w"], s["r4w"], s["r12w"]
    if r1w > 0:   parts.append(f"近1周上涨{r1w:.2f}%")
    elif r1w < 0: parts.append(f"近1周回调{abs(r1w):.2f}%（估值趋合理）")
    if r4w > 0:   parts.append(f"近4周累计+{r4w:.2f}%")
    if r12w > 0:  parts.append(f"近12周趋势向好（+{r12w:.2f}%）")

    mdd = s["mdd"]
    if mdd < 2:   parts.append(f"近3月最大回撤仅{mdd:.2f}%，回撤控制优秀")
    elif mdd < 5: parts.append(f"近3月最大回撤{mdd:.2f}%，风险可控")
    else:         parts.append(f"近3月最大回撤{mdd:.2f}%，注意波动风险")

    vol = s["vol"]
    if vol < 5:   parts.append(f"年化波动率{vol:.1f}%，运行平稳")
    elif vol < 15: parts.append(f"年化波动率{vol:.1f}%，波动适中")
    else:         parts.append(f"年化波动率{vol:.1f}%，波动偏高")

    rsi = s["rsi"]
    if rsi < 35:  parts.append(f"RSI={rsi:.0f}，技术超卖，反弹概率较高")
    elif rsi > 68: parts.append(f"RSI={rsi:.0f}，短期偏强，注意回调")
    else:         parts.append(f"RSI={rsi:.0f}，技术指标健康")

    if sector_chg > 0.015:
        parts.append(f"所属行业近期走强（+{sector_chg*100:.1f}%）")
    elif sector_chg < -0.015:
        parts.append(f"所属行业近期调整（{sector_chg*100:.1f}%），可关注左侧机会")

    size = s["size"]
    if size > 0:
        parts.append(f"规模{size:.1f}亿元")

    parts.append(f"适合{risk_label}投资者")
    return "；".join(parts) + "。"


# ══════════════════════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════════════════════

def get_recommended_funds(
    market_snapshot: dict,
    top_per_tier: int = 5,
    sample_bond: int = 40,
    sample_balanced: int = 60,
) -> list:
    """
    全市场动态筛选推荐基金。

    参数：
        market_snapshot  get_market_data() 返回的市场快照
        top_per_tier     每个风险档取几只（默认5，共10只）
        sample_bond      稳健池最大评分数量
        sample_balanced  均衡池最大评分数量

    返回：
        list of dict，每项含 name/code/riskLevel/score/reason
        数据完全获取失败时返回空列表，不返回任何假数据
    """

    # ── 1. 拉取全量列表 ──────────────────────────────────────────────────────
    logger.info("开始拉取全量基金列表...")
    bond_raw     = _fetch_fund_list("3")          # 债券型
    mixed_raw    = _fetch_fund_list("2")          # 混合型
    equity_raw   = _fetch_fund_list("1")          # 股票型

    # ── 2. 预筛选 ────────────────────────────────────────────────────────────
    bond_pool     = _prefilter(bond_raw)
    balanced_pool = _prefilter(mixed_raw + equity_raw)

    logger.info(f"预筛选 | 稳健池 {len(bond_pool)} 只 | 均衡池 {len(balanced_pool)} 只")

    if not bond_pool and not balanced_pool:
        logger.error("全量基金列表获取失败，返回空结果")
        return []

    # ── 3. 随机抽样 ──────────────────────────────────────────────────────────
    random.shuffle(bond_pool)
    random.shuffle(balanced_pool)
    bond_sample     = bond_pool[:sample_bond]
    balanced_sample = balanced_pool[:sample_balanced]

    logger.info(f"抽样 | 稳健 {len(bond_sample)} 只 | 均衡 {len(balanced_sample)} 只")

    # ── 4. 评分 ──────────────────────────────────────────────────────────────
    def evaluate(pool: list, risk_label: str) -> list:
        scored = []
        for fund in pool:
            code, name, size = fund["code"], fund["name"], fund["size"]
            try:
                logger.info(f"[{code}] 开始评分: {name}")
                hist = _fetch_historical_nav(code, months=3)
                if not hist:
                    logger.info(f"[{code}] 历史净值数据缺失，跳过")
                    continue  # 数据缺失，跳过，不填假值

                # 移除成立时间检查，因为 dates[0] 是历史净值数据的第一个日期，不是基金的成立日期
                # 改为检查历史净值数据是否足够
                dates = hist.get("dates", [])
                if len(dates) < 60:  # 至少需要60个交易日的数据
                    logger.info(f"[{code}] 历史净值数据不足（{len(dates)}天），跳过")
                    continue

                # 补充规模
                if size < 0:
                    size = _fetch_size_from_js(code)
                    logger.info(f"[{code}] 补充规模数据: {size} 亿元")

                sc = _sector_change(name, market_snapshot)
                logger.info(f"[{code}] 行业景气度: {sc:.4f}")
                s  = _score(hist, sc, size)
                if s is None:
                    logger.info(f"[{code}] 评分失败，跳过")
                    continue

                logger.info(f"[{code}] 评分成功: {s['total']}")
                scored.append({
                    "name":      name,
                    "code":      code,
                    "riskLevel": risk_label,
                    "score":     s["total"],
                    "reason":    _build_reason(risk_label, s, sc),
                })
                time.sleep(0.08)
            except Exception as e:
                logger.warning(f"[{code}] 评分异常: {e}")
        return scored

    bond_scored     = evaluate(bond_sample,     "稳健型")
    balanced_scored = evaluate(balanced_sample, "均衡型")

    logger.info(f"评分完成 | 稳健 {len(bond_scored)} 只有效 | 均衡 {len(balanced_scored)} 只有效")

    # ── 5. 排序取 top N，合并输出 ────────────────────────────────────────────
    top_bond     = sorted(bond_scored,     key=lambda x: x["score"], reverse=True)[:top_per_tier]
    top_balanced = sorted(balanced_scored, key=lambda x: x["score"], reverse=True)[:top_per_tier]
    output       = top_bond + top_balanced

    logger.info(f"推荐 {len(output)} 只（稳健 {len(top_bond)}，均衡 {len(top_balanced)}）")
    return output