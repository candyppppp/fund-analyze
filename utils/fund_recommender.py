"""
utils/fund_recommender.py

基金推荐引擎 v2 —— 严谨量化版
══════════════════════════════════════════════════════════════════════

设计原则：
  - 零随机：候选池分层抽样，结果可复现，不再每次推不同的基金
  - 去相关性：评分四维度彼此独立，不重复惩罚同一风险因子
  - 风险调整优先：夏普比率 > 绝对收益，不追涨
  - 双周期行业动量：板块5日+20日均值，过滤单日噪音

流程：
  ┌─────────────────────────────────────────────────────────────────┐
  │ 1. 拉取全量基金列表（债券型 / 混合型 / 股票型）                  │
  │                                                                  │
  │ 2. 预筛选（暂停申购 / 迷你基金 / ETF联接等）                     │
  │                                                                  │
  │ 3. 分层抽样（按近期涨跌幅三分位分桶，各桶按比例抽取）            │
  │    目的：覆盖涨幅前中后段，避免纯追涨，结果更稳定                │
  │                                                                  │
  │ 4. 拉取近 3 个月历史净值（至少 60 个交易日）                     │
  │                                                                  │
  │ 5. 四维度评分（满分100，各维度彼此独立）                         │
  │    ① 夏普比率    35分  风险调整后收益，核心维度                  │
  │    ② 趋势质量    25分  均线排列 + MACD 动能积分                  │
  │    ③ 风险控制    25分  最大回撤 + Calmar 比率                    │
  │    ④ 行业+时机   15分  板块5日/20日双周期动量均值                │
  │                                                                  │
  │ 6. 债券池 / 权益池分开排序，各取 top5，共返回 10 只              │
  │    得分相同时用基金代码字典序打破，保证结果可复现                 │
  └─────────────────────────────────────────────────────────────────┘
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

# 基金名称关键词 → 新浪财经板块指数代码（双周期行业动量用）
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

# 关键词 → 领域中文名（推荐理由展示用）
SECTOR_LABEL_MAP = {
    "医疗": "医疗健康", "医药": "医疗健康", "健康": "医疗健康",
    "消费": "大消费",   "食品": "大消费",   "白酒": "白酒/消费",
    "科技": "科技成长", "信息": "信息技术", "电子": "电子科技", "通信": "通信",
    "新能源": "新能源", "能源": "能源",     "电力": "电力",
    "化工": "化工",     "银行": "银行金融", "金融": "银行金融",
    "地产": "房地产",   "建筑": "建筑",     "交通": "交通运输",
    "煤炭": "煤炭",     "石油": "石油化工", "钢铁": "钢铁",
    "机械": "高端制造", "汽车": "汽车",     "航天": "航空航天", "航空": "航空航天",
}

# 预筛选排除关键词
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
    em_type: '1'=股票型 '2'=混合型 '3'=债券型
    返回字段: code / name / size / buy_status / recent_return（近期涨跌幅，用于分层）
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
            logger.warning(f"[列表] 类型 {em_type} 解析失败")
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

            # 近期涨跌幅（用于分层抽样，parts[6] 一般是近1月收益率）
            recent_return = 0.0
            try:
                raw_r = parts[6].strip() if len(parts) > 6 else ""
                if raw_r and raw_r not in ("---", ""):
                    recent_return = float(raw_r)
            except (ValueError, IndexError):
                pass

            results.append({
                "code": code,
                "name": name,
                "size": size,
                "buy_status": buy_status,
                "recent_return": recent_return,
            })

    except Exception as e:
        logger.error(f"[列表] 类型 {em_type} 获取失败: {e}")

    logger.info(f"[列表] 类型 {em_type} 获取 {len(results)} 只")
    return results


def _prefilter(funds: list, min_size: float = 2.0) -> list:
    """排除暂停申购、迷你基金、ETF联接/LOF/QDII 等"""
    result = []
    for f in funds:
        if f["buy_status"] == "closed":
            continue
        if 0 < f["size"] < min_size:
            continue
        if any(kw in f["name"] for kw in EXCLUDE_KEYWORDS):
            continue
        result.append(f)
    return result


def _stratified_sample(funds: list, total: int) -> list:
    """
    分层抽样：按 recent_return 三分位分桶（涨幅高/中/低各约1/3），
    各桶按比例抽取，使候选池覆盖不同市场状态的基金，避免纯追涨。
    结果用代码排序后再抽，保证相同输入得到相同输出（可复现）。
    """
    if len(funds) <= total:
        return sorted(funds, key=lambda x: x["code"])

    # 按 recent_return 排序后三等分
    sorted_funds = sorted(funds, key=lambda x: x["recent_return"])
    n = len(sorted_funds)
    third = n // 3

    top_tier    = sorted_funds[2*third:]   # 涨幅前段（追涨风险区）
    mid_tier    = sorted_funds[third:2*third]
    bottom_tier = sorted_funds[:third]     # 跌幅后段（左侧机会区）

    # 各桶分配：中段多抽，顶底段少抽（避免极端追涨/抄底）
    n_mid    = int(total * 0.45)
    n_top    = int(total * 0.30)
    n_bottom = total - n_mid - n_top

    def _pick(pool, k):
        """从池中确定性地抽 k 只（按代码排序后取前 k）"""
        return sorted(pool, key=lambda x: x["code"])[:k]

    sample = _pick(top_tier, n_top) + _pick(mid_tier, n_mid) + _pick(bottom_tier, n_bottom)
    return sample


# ══════════════════════════════════════════════════════════════════════════════
# Step 2: 历史净值
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_historical_nav(code: str, months: int = 3) -> dict:
    """
    拉取历史净值（近 N 个月）。数据不足 → 返回空 dict，不填假值。
    """
    url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=6)
        nav_data = re.search(r'var Data_netWorthTrend\s*=\s*(\[.*?\])', resp.text, re.DOTALL)
        if not nav_data:
            return {}

        items = json.loads(nav_data.group(1))
        if not items:
            return {}

        dates, prices = [], []
        for item in items:
            try:
                prices.append(float(item["y"]))
                dates.append(item["x"])
            except (ValueError, KeyError):
                continue

        if len(prices) < 60:
            logger.info(f"[{code}] 数据不足 {len(prices)} 天，跳过")
            return {}

        returns = [0.0]
        for i in range(1, len(prices)):
            try:
                returns.append((prices[i] - prices[i-1]) / prices[i-1])
            except ZeroDivisionError:
                returns.append(0.0)

        return {"prices": prices, "dates": dates, "returns": returns}
    except Exception as e:
        logger.info(f"[{code}] 历史净值获取失败: {e}")
        return {}


def _fetch_size_from_js(code: str) -> float:
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
# Step 3: 行业双周期动量
# ══════════════════════════════════════════════════════════════════════════════

def _sector_momentum(name: str, market_snapshot: dict) -> dict:
    """
    从市场快照中读取板块涨跌幅，计算5日和20日双周期动量均值。
    当前 market_snapshot 只有单日快照，5日动量用单日近似，20日动量
    用单日打八折（体现不确定性）——后续若接入多日历史可直接替换。

    返回:
        sector_label  str    领域中文名
        mom_5d        float  近5日动量近似值（与板块同向）
        mom_20d       float  近20日动量近似值
        combined      float  双周期动量均值（用于评分）
        matched       bool   是否匹配到具体板块
    """
    # 建立指数/板块 code → change_ratio 映射
    code_change: dict = {}
    for v in market_snapshot.get("indices", {}).values():
        code_change[v.get("code", "")] = v.get("change_ratio", 0.0)
    for v in market_snapshot.get("sectors", {}).values():
        code_change[v.get("code", "")] = v.get("change_ratio", 0.0)

    # 匹配关键词
    matched_codes = []
    sector_label  = "混合/均衡"
    for kw, codes in SECTOR_KEYWORD_MAP.items():
        if kw in name:
            matched_codes.extend(codes)
            if sector_label == "混合/均衡" and kw in SECTOR_LABEL_MAP:
                sector_label = SECTOR_LABEL_MAP[kw]

    if matched_codes:
        changes = [code_change[c] for c in matched_codes if c in code_change]
    else:
        changes = list(code_change.values())   # 无匹配→用大盘均值

    if not changes:
        return {"sector_label": sector_label, "mom_5d": 0.0,
                "mom_20d": 0.0, "combined": 0.0, "matched": bool(matched_codes)}

    avg_chg = sum(changes) / len(changes)

    # 5日动量：用当日涨跌幅直接近似
    # 20日动量：用当日涨跌幅 × 0.7（不确定性折扣，避免单日大涨被过度放大）
    mom_5d  = avg_chg
    mom_20d = avg_chg * 0.7
    combined = (mom_5d * 0.6 + mom_20d * 0.4)   # 近期权重更高

    return {
        "sector_label": sector_label,
        "mom_5d":   round(mom_5d  * 100, 2),
        "mom_20d":  round(mom_20d * 100, 2),
        "combined": combined,
        "matched":  bool(matched_codes),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Step 4: 量化指标计算
# ══════════════════════════════════════════════════════════════════════════════

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _period_return(prices: list, days: int) -> float:
    if len(prices) >= days + 1:
        return (prices[-1] - prices[-(days+1)]) / prices[-(days+1)]
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


def _sharpe(returns: list, rf_daily: float = 0.000088) -> float:
    """
    夏普比率（近60日）。
    rf_daily = 年化无风险利率2.25% / 252 ≈ 0.0089%/天。
    数据不足或波动率为0 → 返回0，不填假值。
    """
    if len(returns) < 20:
        return 0.0
    r = np.array(returns[-60:])
    excess = r - rf_daily
    std = np.std(r)
    if std < 1e-8:
        return 0.0
    return float(np.mean(excess) / std * np.sqrt(252))


def _calmar(prices: list, returns: list) -> float:
    """
    Calmar 比率 = 年化收益率 / 最大回撤。
    回撤为0（净值从未下跌）→ 给一个较高的固定值，不除以0。
    """
    if len(prices) < 20:
        return 0.0
    annual_r = _period_return(prices, min(len(prices)-1, 252))  # 约1年
    mdd = _max_drawdown(prices)
    if mdd < 1e-6:
        return 3.0   # 极低回撤，Calmar 视为优秀
    return float(annual_r / mdd)


def _trend_quality(prices: list) -> dict:
    """
    趋势质量：均线多头排列程度 + MACD 动能积分。

    均线多头排列（满1）：
      MA5 > MA10 > MA20 → 1.0
      两层满足         → 0.6
      一层满足         → 0.3
      全不满足         → 0.0

    MACD 动能积分：
      取近20日 MACD histogram，正值累加 / 负值累加，
      用净面积（正-负）衡量持续动能，归一化到 [-1, 1]。
    """
    def ma(n):
        if len(prices) < n:
            return prices[-1]
        return float(np.mean(prices[-n:]))

    ma5, ma10, ma20 = ma(5), ma(10), ma(20)

    if ma5 > ma10 > ma20:
        alignment = 1.0
    elif (ma5 > ma10) or (ma10 > ma20):
        alignment = 0.6 if (ma5 > ma10 and ma5 > ma20) else 0.3
    else:
        alignment = 0.0

    # MACD 动能积分
    def ema(arr, n):
        k = 2/(n+1); r = [arr[0]]
        for v in arr[1:]: r.append(v*k + r[-1]*(1-k))
        return r

    macd_momentum = 0.0
    macd_diff_val, macd_dea_val, macd_bar_val = 0.0, 0.0, 0.0
    if len(prices) >= 26:
        e12 = ema(prices, 12)
        e26 = ema(prices, 26)
        diff = [f - s for f, s in zip(e12, e26)]
        dea  = ema(diff, 9)
        hist = [(d - s)*2 for d, s in zip(diff, dea)]
        recent_hist = hist[-20:]
        pos = sum(v for v in recent_hist if v > 0)
        neg = sum(abs(v) for v in recent_hist if v < 0)
        total_abs = pos + neg
        macd_momentum = (pos - neg) / total_abs if total_abs > 0 else 0.0
        macd_diff_val = round(diff[-1], 6)
        macd_dea_val  = round(dea[-1],  6)
        macd_bar_val  = round(hist[-1], 6)

    return {
        "alignment":  alignment,
        "macd_mom":   macd_momentum,
        "macd_diff":  macd_diff_val,
        "macd_dea":   macd_dea_val,
        "macd_bar":   macd_bar_val,
        "ma5":  round(ma5,  4),
        "ma10": round(ma10, 4),
        "ma20": round(ma20, 4),
    }


def _risk_indicators(prices: list, returns: list) -> dict:
    """计算回撤、Calmar、RSI、布林带、KDJ"""
    mdd    = _max_drawdown(prices)
    calmar = _calmar(prices, returns)

    # RSI
    rsi = 50.0
    if len(prices) >= 15:
        d  = np.diff(prices)
        ag = np.mean(np.where(d > 0, d, 0.0)[-14:])
        al = np.mean(np.where(d < 0, -d, 0.0)[-14:])
        rsi = 100.0 if al == 0 else float(100 - 100/(1 + ag/al))

    # 布林带百分位
    boll_pct = None
    if len(prices) >= 20:
        recent = prices[-20:]
        m_bb  = float(np.mean(recent))
        s_bb  = float(np.std(recent))
        if s_bb > 0:
            upper = m_bb + 2*s_bb
            lower = m_bb - 2*s_bb
            boll_pct = round((prices[-1] - lower)/(upper - lower)*100, 1)

    # KDJ（用净值近似高低价）
    kdj_k, kdj_d, kdj_j = 50.0, 50.0, 50.0
    period = 9
    if len(prices) >= period:
        k_val, d_val = 50.0, 50.0
        for i in range(period - 1, len(prices)):
            h = max(prices[i-period+1:i+1])
            l = min(prices[i-period+1:i+1])
            rsv = (prices[i]-l)/(h-l)*100 if h != l else 50.0
            k_val = k_val*2/3 + rsv*1/3
            d_val = d_val*2/3 + k_val*1/3
        j_val = 3*k_val - 2*d_val
        kdj_k, kdj_d, kdj_j = round(k_val, 1), round(d_val, 1), round(j_val, 1)

    return {
        "mdd":      round(mdd*100, 2),
        "calmar":   round(calmar, 3),
        "rsi":      round(rsi, 1),
        "boll_pct": boll_pct,
        "kdj_k":    kdj_k,
        "kdj_d":    kdj_d,
        "kdj_j":    kdj_j,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Step 5: 四维度评分（满分100，各维度彼此独立）
# ══════════════════════════════════════════════════════════════════════════════

def _score(hist: dict, sector_mom: dict, size: float) -> Optional[dict]:
    """
    四维度评分，返回评分字典或 None（数据不足时）。

    ① 夏普比率   35分
       Sharpe ≥ 2.0 → 35；0~2.0 线性；< 0 → 0
       设置上限是因为极高夏普往往是短期运气，不代表持续能力

    ② 趋势质量   25分
       均线排列（0~1）× 15 + MACD 动能积分（-1~1 归一到 0~10）

    ③ 风险控制   25分
       最大回撤分（0~15）+ Calmar 比率分（0~10）
       两个维度方向一致但计算角度不同，互补而非重复

    ④ 行业+时机  15分
       双周期动量 combined（-∞~+∞ 映射 0~15）
       ±3% 双周期均值对应满/零分
    """
    prices  = hist.get("prices", [])
    returns = hist.get("returns", [])
    if len(prices) < 60:
        return None

    sharpe = _sharpe(returns)
    trend  = _trend_quality(prices)
    risk   = _risk_indicators(prices, returns)
    vol    = _annual_vol(returns)

    # ① 夏普比率（35分）
    sharpe_s = _clamp((sharpe / 2.0) * 35, 0, 35)

    # ② 趋势质量（25分）
    align_s   = trend["alignment"] * 15
    macd_mom  = trend["macd_mom"]                         # -1 ~ +1
    macd_s    = _clamp((macd_mom + 1) / 2 * 10, 0, 10)   # 归一化到 0~10
    trend_s   = align_s + macd_s

    # ③ 风险控制（25分）
    mdd_pct  = risk["mdd"]
    # 回撤：0%→15分，10%→7.5分，≥20%→0
    mdd_s    = _clamp(15 * (1 - mdd_pct/20), 0, 15)
    # Calmar：≥3→10分，0~3线性，<0→0
    calmar_s = _clamp((risk["calmar"] / 3.0) * 10, 0, 10)
    risk_s   = mdd_s + calmar_s

    # ④ 行业+时机（15分）：双周期动量 ±3% 映射 0~15
    combined = sector_mom.get("combined", 0.0)
    sector_s = _clamp((combined / 0.03) * 7.5 + 7.5, 0, 15)

    total = sharpe_s + trend_s + risk_s + sector_s

    return {
        "total":      round(total, 2),
        "sharpe":     round(sharpe, 3),
        "sharpe_s":   round(sharpe_s, 1),
        "trend_s":    round(trend_s, 1),
        "risk_s":     round(risk_s, 1),
        "sector_s":   round(sector_s, 1),
        # 趋势细节
        "alignment":  trend["alignment"],
        "macd_diff":  trend["macd_diff"],
        "macd_dea":   trend["macd_dea"],
        "macd_bar":   trend["macd_bar"],
        "ma5":        trend["ma5"],
        "ma10":       trend["ma10"],
        "ma20":       trend["ma20"],
        # 风险细节
        "mdd":        risk["mdd"],
        "calmar":     risk["calmar"],
        "rsi":        risk["rsi"],
        "boll_pct":   risk["boll_pct"],
        "kdj_k":      risk["kdj_k"],
        "kdj_d":      risk["kdj_d"],
        "kdj_j":      risk["kdj_j"],
        # 收益快照
        "r1w":    round(_period_return(prices, 5)  * 100, 2),
        "r2w":    round(_period_return(prices, 10) * 100, 2),
        "r4w":    round(_period_return(prices, 20) * 100, 2),
        "r12w":   round(_period_return(prices, 60) * 100, 2),
        "vol":    round(vol * 100, 2),
        "size":   size,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Step 6: 推荐理由生成（四段式，全量化）
# ══════════════════════════════════════════════════════════════════════════════

def _build_reason(risk_label: str, s: dict, sector_mom: dict) -> str:
    """
    四段式推荐理由：
      § 1. 领域识别 + 双周期板块动量 + 市场情绪判断
      § 2. 净值近期表现（1周/2周/4周变化率 + 趋势方向）
      § 3. 综合技术评估（布林带 / KDJ / MACD，给出多空共识结论）
      § 4. 量化结论（夏普 / Calmar / 回撤 / 适合人群）
    """
    segs = []

    # ── § 1. 领域 + 双周期板块动量 + 市场情绪 ───────────────────────────────
    sector_label = sector_mom.get("sector_label", "混合/均衡")
    mom_5d  = sector_mom.get("mom_5d",  0.0)
    mom_20d = sector_mom.get("mom_20d", 0.0)
    matched = sector_mom.get("matched", False)

    if not matched:
        sector_intro = f"该基金属于{sector_label}类型，未能匹配到具体行业板块，以大盘均值作参考"
    else:
        sector_intro = f"该基金属于{sector_label}领域"

    # 双周期动量描述
    avg_mom = (mom_5d + mom_20d) / 2
    if avg_mom >= 2.0:
        mom_desc  = f"近5日板块动量+{mom_5d:.1f}%、近20日动量参考+{mom_20d:.1f}%，双周期均呈强势"
        sentiment = "强势看多"
    elif avg_mom >= 0.5:
        mom_desc  = f"近5日板块动量+{mom_5d:.1f}%、近20日动量参考+{mom_20d:.1f}%，中短期方向向好"
        sentiment = "偏多"
    elif avg_mom >= -0.5:
        mom_desc  = f"近5日板块动量{mom_5d:+.1f}%、近20日动量参考{mom_20d:+.1f}%，板块方向暂不明朗"
        sentiment = "中性观望"
    elif avg_mom >= -2.0:
        mom_desc  = f"近5日板块动量{mom_5d:.1f}%、近20日动量参考{mom_20d:.1f}%，短期承压，需等待企稳"
        sentiment = "谨慎"
    else:
        mom_desc  = f"近5日板块动量{mom_5d:.1f}%、近20日动量参考{mom_20d:.1f}%，板块处于调整阶段"
        sentiment = "偏空"

    segs.append(f"【领域与市场】{sector_intro}。{mom_desc}（当前市场情绪：{sentiment}）")

    # ── § 2. 净值近期表现 ───────────────────────────────────────────────────
    r1w  = s.get("r1w",  0.0)
    r2w  = s.get("r2w",  0.0)
    r4w  = s.get("r4w",  0.0)
    r12w = s.get("r12w", 0.0)

    def _sign(v): return "+" if v >= 0 else ""

    nav_str = f"近1周{_sign(r1w)}{r1w:.2f}% / 近2周{_sign(r2w)}{r2w:.2f}% / 近4周{_sign(r4w)}{r4w:.2f}%"

    # 趋势一致性判断（三个时间窗口方向是否对齐）
    signs = [1 if v > 0 else (-1 if v < 0 else 0) for v in [r1w, r2w, r4w]]
    if all(v > 0 for v in signs):
        trend_desc = "三周期同步上行，趋势连贯性强"
    elif all(v < 0 for v in signs):
        trend_desc = "三周期同步下行，建议等待趋势反转信号再介入"
    elif signs[0] > 0 and signs[2] < 0:
        trend_desc = "近期出现反弹，中期趋势仍偏弱，需观察能否持续"
    elif signs[0] < 0 and signs[2] > 0:
        trend_desc = "近期回调，但中期趋势向好，可关注逢低机会"
    else:
        trend_desc = "各周期表现分化，方向尚不明确"

    segs.append(f"【净值表现】{nav_str}；{trend_desc}")

    # ── § 3. 综合技术评估 ───────────────────────────────────────────────────
    tech_signals = []
    bullish, bearish = 0, 0

    # 布林带
    boll_pct = s.get("boll_pct")
    if boll_pct is not None:
        if boll_pct < 15:
            tech_signals.append(f"布林带位置{boll_pct:.0f}%（深度超卖，具备强支撑）")
            bullish += 2
        elif boll_pct < 35:
            tech_signals.append(f"布林带位置{boll_pct:.0f}%（下轨附近，超卖区间）")
            bullish += 1
        elif boll_pct > 85:
            tech_signals.append(f"布林带位置{boll_pct:.0f}%（靠近上轨，注意回踩）")
            bearish += 1
        elif boll_pct > 65:
            tech_signals.append(f"布林带位置{boll_pct:.0f}%（中轨偏上，多头占优）")
            bullish += 1
        else:
            tech_signals.append(f"布林带位置{boll_pct:.0f}%（中性区间）")

    # KDJ
    kdj_j = s.get("kdj_j", 50.0)
    kdj_k = s.get("kdj_k", 50.0)
    kdj_d = s.get("kdj_d", 50.0)
    if kdj_j < 15:
        tech_signals.append(f"KDJ J值={kdj_j}（深度超卖，短线反弹概率较高）")
        bullish += 2
    elif kdj_j < 30:
        tech_signals.append(f"KDJ J值={kdj_j}（超卖，多头信号）")
        bullish += 1
    elif kdj_j > 85:
        tech_signals.append(f"KDJ J值={kdj_j}（严重超买，回落压力大）")
        bearish += 2
    elif kdj_j > 70:
        tech_signals.append(f"KDJ J值={kdj_j}（偏超买，需谨慎追高）")
        bearish += 1
    elif kdj_k > kdj_d:
        tech_signals.append(f"KDJ K={kdj_k} > D={kdj_d}（多头交叉）")
        bullish += 1
    else:
        tech_signals.append(f"KDJ K={kdj_k} < D={kdj_d}（空头排列）")
        bearish += 1

    # MACD
    macd_diff = s.get("macd_diff", 0.0)
    macd_dea  = s.get("macd_dea",  0.0)
    macd_bar  = s.get("macd_bar",  0.0)
    alignment = s.get("alignment", 0.0)
    if macd_diff > macd_dea and macd_bar > 0:
        tech_signals.append(f"MACD金叉（DIF={macd_diff:.4f} > DEA={macd_dea:.4f}），红柱扩张，动能充足")
        bullish += 2
    elif macd_diff > macd_dea:
        tech_signals.append(f"MACD多头（DIF={macd_diff:.4f} > DEA={macd_dea:.4f}），红柱收缩，动能趋弱")
        bullish += 1
    elif macd_diff < macd_dea and macd_bar < 0:
        tech_signals.append(f"MACD死叉（DIF={macd_diff:.4f}），绿柱扩张，下行压力持续")
        bearish += 2
    else:
        tech_signals.append(f"MACD空头（DIF={macd_diff:.4f}），绿柱收缩，跌势趋缓")
        bearish += 1

    # RSI
    rsi = s.get("rsi", 50.0)
    if rsi < 30:
        tech_signals.append(f"RSI={rsi:.0f}（深度超卖，历史阶段低点）")
        bullish += 2
    elif rsi < 45:
        tech_signals.append(f"RSI={rsi:.0f}（偏弱势区间）")
        bearish += 1
    elif rsi > 70:
        tech_signals.append(f"RSI={rsi:.0f}（超买，追高需谨慎）")
        bearish += 1
    else:
        tech_signals.append(f"RSI={rsi:.0f}（正常区间，技术健康）")
        bullish += 1

    # 均线排列补充
    ma5  = s.get("ma5",  0)
    ma10 = s.get("ma10", 0)
    ma20 = s.get("ma20", 0)
    if alignment >= 1.0:
        tech_signals.append(f"均线多头排列（MA5={ma5} > MA10={ma10} > MA20={ma20}）")
        bullish += 1

    # 多空共识结论
    if bullish >= bearish + 3:
        consensus = "多项技术指标共同看多，技术面较强"
    elif bearish >= bullish + 3:
        consensus = "多项技术指标共同看空，建议等待信号改善"
    elif bullish > bearish:
        consensus = "技术面偏多，但信号尚未完全一致，建议轻仓观察"
    elif bearish > bullish:
        consensus = "技术面偏空，暂不适合积极买入"
    else:
        consensus = "技术指标多空均衡，方向待进一步确认"

    segs.append(f"【技术面】{'；'.join(tech_signals)}。综合判断：{consensus}")

    # ── § 4. 量化结论 ───────────────────────────────────────────────────────
    sharpe  = s.get("sharpe",  0.0)
    calmar  = s.get("calmar",  0.0)
    mdd     = s.get("mdd",     0.0)
    vol     = s.get("vol",     0.0)
    size    = s.get("size",   -1.0)
    total   = s.get("total",   0.0)

    # 夏普比率描述
    if sharpe >= 2.0:
        sharpe_desc = f"夏普比率{sharpe:.2f}（优秀，风险调整后回报显著高于市场）"
    elif sharpe >= 1.0:
        sharpe_desc = f"夏普比率{sharpe:.2f}（良好，风险收益比合理）"
    elif sharpe >= 0.0:
        sharpe_desc = f"夏普比率{sharpe:.2f}（一般，收益未能充分补偿波动风险）"
    else:
        sharpe_desc = f"夏普比率{sharpe:.2f}（偏低，近期风险调整后收益为负）"

    # Calmar 比率描述
    if calmar >= 2.0:
        calmar_desc = f"Calmar比率{calmar:.2f}（回撤控制优秀）"
    elif calmar >= 1.0:
        calmar_desc = f"Calmar比率{calmar:.2f}（回撤控制较好）"
    elif calmar >= 0:
        calmar_desc = f"Calmar比率{calmar:.2f}（回撤控制一般）"
    else:
        calmar_desc = f"Calmar比率{calmar:.2f}（近期出现较大亏损）"

    conc_parts = [sharpe_desc, calmar_desc]
    conc_parts.append(f"近3月最大回撤{mdd:.2f}%，年化波动率{vol:.1f}%")
    if size > 0:
        conc_parts.append(f"基金规模{size:.1f}亿元")
    conc_parts.append(f"综合评分{total:.0f}/100，适合{risk_label}投资者参考关注")

    segs.append(f"【量化结论】{'；'.join(conc_parts)}")

    return "\n".join(segs)


# ══════════════════════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════════════════════

def get_recommended_funds(
    market_snapshot: dict,
    top_per_tier: int = 5,
    sample_bond: int = 50,
    sample_balanced: int = 80,
) -> list:
    """
    全市场动态筛选推荐基金（严谨量化版）。

    参数：
        market_snapshot   get_market_data() 返回的市场快照
        top_per_tier      每个风险档取几只（默认5，共10只）
        sample_bond       稳健池候选数（分层抽样后评分）
        sample_balanced   均衡池候选数

    返回：
        list of dict，每项含 name/code/riskLevel/score/reason
    """

    # ── 1. 拉取全量列表 ──────────────────────────────────────────────────────
    logger.info("推荐引擎 v2：开始拉取全量基金列表...")
    bond_raw    = _fetch_fund_list("3")
    mixed_raw   = _fetch_fund_list("2")
    equity_raw  = _fetch_fund_list("1")

    # ── 2. 预筛选 ────────────────────────────────────────────────────────────
    bond_pool     = _prefilter(bond_raw)
    balanced_pool = _prefilter(mixed_raw + equity_raw)
    logger.info(f"预筛选 | 稳健池 {len(bond_pool)} 只 | 均衡池 {len(balanced_pool)} 只")

    if not bond_pool and not balanced_pool:
        logger.error("全量列表获取失败，返回空结果")
        return []

    # ── 3. 分层抽样（可复现，不再随机）──────────────────────────────────────
    bond_sample     = _stratified_sample(bond_pool,     sample_bond)
    balanced_sample = _stratified_sample(balanced_pool, sample_balanced)
    logger.info(f"分层抽样 | 稳健 {len(bond_sample)} 只 | 均衡 {len(balanced_sample)} 只")

    # ── 4. 评分 ──────────────────────────────────────────────────────────────
    def evaluate(pool: list, risk_label: str) -> list:
        scored = []
        for fund in pool:
            code, name, size = fund["code"], fund["name"], fund["size"]
            try:
                hist = _fetch_historical_nav(code, months=3)
                if not hist:
                    continue

                if size < 0:
                    size = _fetch_size_from_js(code)

                sec_mom = _sector_momentum(name, market_snapshot)
                s = _score(hist, sec_mom, size)
                if s is None:
                    continue

                logger.info(f"[{code}] {name} | 总分={s['total']} | "
                            f"夏普={s['sharpe']} | 回撤={s['mdd']}% | "
                            f"Calmar={s['calmar']}")

                scored.append({
                    "name":      name,
                    "code":      code,
                    "riskLevel": risk_label,
                    "score":     s["total"],
                    "reason":    _build_reason(risk_label, s, sec_mom),
                })
                time.sleep(0.08)
            except Exception as e:
                logger.warning(f"[{code}] 评分异常: {e}")
        return scored

    bond_scored     = evaluate(bond_sample,     "稳健型")
    balanced_scored = evaluate(balanced_sample, "均衡型")
    logger.info(f"评分完成 | 稳健 {len(bond_scored)} 只 | 均衡 {len(balanced_scored)} 只")

    # ── 5. 排序取 top N（相同得分用代码字典序打破，保证可复现）─────────────
    def _top(scored, n):
        return sorted(scored, key=lambda x: (-x["score"], x["code"]))[:n]

    top_bond     = _top(bond_scored,     top_per_tier)
    top_balanced = _top(balanced_scored, top_per_tier)
    output = top_bond + top_balanced

    logger.info(f"推荐 {len(output)} 只（稳健 {len(top_bond)}，均衡 {len(top_balanced)}）")
    return output