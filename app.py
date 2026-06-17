import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import numpy as np

INDUSTRY_GROUP = {
    "被動ETF": [], "主動ETF": [],
    "半導體": ["半導體業"],
    "電腦與週邊": ["電腦及週邊設備業", "電子通路業", "資訊服務業"],
    "光電與通信": ["光電業", "通信網路業"],
    "電子零組件": ["電子零組件業", "其他電子業"],
    "金融保險": ["金融保險業"], "生技醫療": ["生技醫療業"],
    "水泥": ["水泥工業"], "食品": ["食品工業"], "塑膠": ["塑膠工業"],
    "紡織": ["紡織纖維"], "電機機械": ["電機機械"], "電器電纜": ["電器電纜"],
    "化學": ["化學工業"], "玻璃陶瓷": ["玻璃陶瓷"], "造紙": ["造紙工業"],
    "鋼鐵": ["鋼鐵工業"], "橡膠": ["橡膠工業"], "汽車": ["汽車工業"],
    "能源": ["油電燃氣業"], "綠能環保": ["綠能環保"],
    "航運": ["航運業"], "建材營造": ["建材營造"],
    "觀光餐旅": ["觀光餐旅"], "貿易百貨": ["貿易百貨"],
    "數位雲端": ["數位雲端"], "運動休閒": ["運動休閒"],
    "居家生活": ["居家生活"], "綜合": ["綜合"],
}

GROUP_ICONS = {
    "被動ETF": "📊", "主動ETF": "✨", "半導體": "🔵", "電腦與週邊": "🖥️",
    "光電與通信": "📡", "電子零組件": "⚙️", "金融保險": "🏦", "生技醫療": "🧬",
    "水泥": "🏗️", "食品": "🍱", "塑膠": "🧪", "紡織": "🧵",
    "電機機械": "⚡", "電器電纜": "🔌", "化學": "🔬", "玻璃陶瓷": "🏺",
    "造紙": "📄", "鋼鐵": "🔩", "橡膠": "🔄", "汽車": "🚗",
    "能源": "⛽", "綠能環保": "☀️", "航運": "🚢", "建材營造": "🏠",
    "觀光餐旅": "🏨", "貿易百貨": "🛒", "數位雲端": "☁️",
    "運動休閒": "⛳", "居家生活": "🏡", "綜合": "📌",
}

THRESHOLDS = [-5, -7, -10, -15, -20]
HORIZONS = [10, 20, 50, 100, 200]

st.set_page_config(page_title="台股滾動10日跌幅系統", layout="wide")
st.title("📉 台股滾動10日跌幅系統")
st.caption("資料來源：Yahoo Finance 還原後股價 | 回測年限：最長15年 | 更新時間：" + datetime.now().strftime("%Y-%m-%d %H:%M"))


def get_industry_group(industry, stock_type):
    if stock_type in ["被動ETF", "主動ETF"]:
        return stock_type
    for group, industries in INDUSTRY_GROUP.items():
        if group in ["被動ETF", "主動ETF"]:
            continue
        for ind in industries:
            if ind in str(industry):
                return group
    return "綜合"


def classify_code(code):
    has_alpha = any(c.isalpha() for c in code)
    if has_alpha:
        return "主動ETF"
    elif code.startswith("00") or (code.startswith("0") and len(code) >= 4):
        return "被動ETF"
    elif code.isdigit() and len(code) == 4:
        return "個股"
    else:
        return "其他"


def get_yahoo_history(code, days=60):
    end = datetime.today()
    start = end - timedelta(days=days)
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/" + code + ".TW"
           + "?interval=1d&period1=" + str(int(start.timestamp()))
           + "&period2=" + str(int(end.timestamp())))
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json()
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        adjclose = result["indicators"].get("adjclose")
        if adjclose and len(adjclose) > 0 and adjclose[0].get("adjclose"):
            closes = adjclose[0]["adjclose"]
        else:
            closes = result["indicators"]["quote"][0]["close"]
        prices = {}
        for ts, cl in zip(timestamps, closes):
            if cl is not None:
                date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                prices[date] = round(cl, 2)
        return prices
    except:
        return {}


def get_yahoo_history_15y(code):
    end = datetime.today()
    start = end - timedelta(days=365 * 15 + 30)
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/" + code + ".TW"
           + "?interval=1d&period1=" + str(int(start.timestamp()))
           + "&period2=" + str(int(end.timestamp())))
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        data = res.json()
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        adjclose = result["indicators"].get("adjclose")
        if adjclose and len(adjclose) > 0 and adjclose[0].get("adjclose"):
            closes = adjclose[0]["adjclose"]
        else:
            closes = result["indicators"]["quote"][0]["close"]
        prices = {}
        for ts, cl in zip(timestamps, closes):
            if cl is not None:
                date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                prices[date] = round(cl, 2)
        return prices
    except:
        return {}


def calc_rolling_return_latest(prices_dict):
    if len(prices_dict) < 11:
        return None
    dates = sorted(prices_dict.keys())
    latest_price = prices_dict[dates[-1]]
    base_price = prices_dict[dates[-11]]
    if base_price == 0:
        return None
    return (latest_price - base_price) / base_price * 100


def calc_latest_close(prices_dict):
    if not prices_dict:
        return None
    return prices_dict[sorted(prices_dict.keys())[-1]]


def calc_consecutive_trigger_days(prices_dict, threshold):
    if len(prices_dict) < 11:
        return 0
    dates = sorted(prices_dict.keys())
    consec = 0
    for i in range(len(dates) - 1, 9, -1):
        base_price = prices_dict[dates[i - 10]]
        curr_price = prices_dict[dates[i]]
        if base_price > 0:
            ret = (curr_price - base_price) / base_price * 100
            if ret <= threshold:
                consec += 1
            else:
                break
        else:
            break
    return consec


def calc_all_rolling_returns(prices_dict):
    if len(prices_dict) < 11:
        return []
    dates = sorted(prices_dict.keys())
    results = []
    for i in range(10, len(dates)):
        base_price = prices_dict[dates[i - 10]]
        curr_price = prices_dict[dates[i]]
        if base_price > 0:
            ret = (curr_price - base_price) / base_price * 100
            results.append({
                "date": dates[i],
                "base_date": dates[i - 10],
                "base_price": base_price,
                "curr_price": curr_price,
                "return": round(ret, 2)
            })
    return results


def run_full_backtest(prices_dict, threshold):
    rolling = calc_all_rolling_returns(prices_dict)
    if not rolling:
        return None
    dates = sorted(prices_dict.keys())
    date_to_idx = {d: i for i, d in enumerate(dates)}
    triggers = [r for r in rolling if r["return"] <= threshold]
    if not triggers:
        return None

    trigger_dates = set(t["date"] for t in triggers)
    max_consecutive = 0
    current_consecutive = 0
    for r in rolling:
        if r["date"] in trigger_dates:
            current_consecutive += 1
            max_consecutive = max(max_consecutive, current_consecutive)
        else:
            current_consecutive = 0

    horizon_rets = {h: [] for h in HORIZONS}
    horizon_drawdowns = {h: [] for h in HORIZONS}

    for t in triggers:
        idx = date_to_idx.get(t["date"])
        if idx is None:
            continue
        entry_price = t["curr_price"]
        year = t["date"][:4]
        for h in HORIZONS:
            future_idx = idx + h
            if future_idx < len(dates):
                future_price = prices_dict[dates[future_idx]]
                ret = (future_price - entry_price) / entry_price * 100
                horizon_rets[h].append({"ret": round(ret, 2), "year": year, "date": t["date"]})
                min_ret = 0.0
                for d in range(1, h + 1):
                    fi = idx + d
                    if fi < len(dates):
                        p = prices_dict[dates[fi]]
                        r = (p - entry_price) / entry_price * 100
                        if r < min_ret:
                            min_ret = r
                horizon_drawdowns[h].append({"dd": round(min_ret, 2), "year": year, "date": t["date"]})

    yearly = {}
    for t in triggers:
        year = t["date"][:4]
        if year not in yearly:
            yearly[year] = {
                "trigger_dates": set(),
                "max_consec": 0,
                "rets": {hh: [] for hh in HORIZONS},
                "dds": {hh: [] for hh in HORIZONS},
            }
        yearly[year]["trigger_dates"].add(t["date"])

    for h in HORIZONS:
        for item in horizon_rets[h]:
            y = item["year"]
            if y in yearly:
                yearly[y]["rets"][h].append(item["ret"])
        for item in horizon_drawdowns[h]:
            y = item["year"]
            if y in yearly:
                yearly[y]["dds"][h].append(item["dd"])

    for year in yearly:
        mc = cc = 0
        for r in rolling:
            if r["date"][:4] == year and r["date"] in yearly[year]["trigger_dates"]:
                cc += 1
                mc = max(mc, cc)
            elif r["date"][:4] == year:
                cc = 0
        yearly[year]["max_consec"] = mc

    return {
        "triggers": triggers,
        "trigger_dates": list(trigger_dates),
        "max_consecutive": max_consecutive,
        "horizon_rets": horizon_rets,
        "horizon_drawdowns": horizon_drawdowns,
        "yearly": yearly,
        "total": len(triggers)
    }


# ==============================
# 顏色函數
# ==============================
def color_ret(val):
    if val is None or str(val) in ["", "---", "待觀察"]:
        return ""
    try:
        v = float(str(val).replace("%", ""))
        return "color: red; font-weight: bold" if v > 0 else "color: green; font-weight: bold"
    except:
        return ""


def color_dd(val):
    if val is None or str(val) in ["", "---", "待觀察"]:
        return ""
    try:
        v = float(str(val).replace("%", ""))
        return "color: green; font-weight: bold" if v < 0 else "color: red; font-weight: bold"
    except:
        return ""


def color_winrate(val):
    if val is None or str(val) in ["", "---", "待觀察"]:
        return ""
    try:
        v = float(str(val).replace("%", ""))
        if v >= 80:
            return "background-color: #FF8C00; color: white; font-weight: bold"
        return ""
    except:
        return ""


def heatmap_ret_style(df, cols):
    """熱力圖：正報酬用紅色深淺（越高越深），負報酬用綠色深淺"""
    styled = df.style
    all_vals = []
    for c in cols:
        for v in df[c]:
            try:
                all_vals.append(float(str(v).replace("%", "")))
            except:
                pass
    if not all_vals:
        return styled
    max_pos = max((v for v in all_vals if v > 0), default=1)
    min_neg = min((v for v in all_vals if v < 0), default=-1)

    def cell_style(val):
        if val is None or str(val) in ["", "---", "待觀察"]:
            return ""
        try:
            v = float(str(val).replace("%", ""))
            if v > 0:
                intensity = min(v / max_pos, 1.0)
                r = int(255 - intensity * 80)
                g = int(200 - intensity * 180)
                b = int(200 - intensity * 180)
                text_color = "white" if intensity > 0.5 else "#8B0000"
                return "background-color: rgb({},{},{}); color: {}; font-weight: bold".format(r, g, b, text_color)
            elif v < 0:
                intensity = min(abs(v) / abs(min_neg), 1.0)
                r = int(200 - intensity * 160)
                g = int(255 - intensity * 80)
                b = int(200 - intensity * 160)
                text_color = "white" if intensity > 0.5 else "#006400"
                return "background-color: rgb({},{},{}); color: {}; font-weight: bold".format(r, g, b, text_color)
            else:
                return ""
        except:
            return ""

    return styled.map(cell_style, subset=cols)


def fmt(v):
    if v is None:
        return "待觀察"
    return "{:.2f}%".format(v)


def show_html(df):
    st.markdown(df.to_html(index=False), unsafe_allow_html=True)


# ==============================
# 建立整合總覽表 (A+B+C+E合一)
# ==============================
def build_summary_integrated(prices_dict):
    rows = []
    for thr in THRESHOLDS:
        result = run_full_backtest(prices_dict, thr)
        row = {"觸發門檻": str(thr) + "%", "樣本數": 0 if result is None else result["total"]}
        for h in HORIZONS:
            if result is None:
                row[str(h) + "天勝率"] = "---"
                row[str(h) + "天平均%"] = "---"
                row[str(h) + "天累積%"] = "---"
                row[str(h) + "天回撤%"] = "---"
            else:
                rets = [x["ret"] for x in result["horizon_rets"][h]]
                dds = [x["dd"] for x in result["horizon_drawdowns"][h]]
                if not rets:
                    row[str(h) + "天勝率"] = "待觀察"
                    row[str(h) + "天平均%"] = "待觀察"
                    row[str(h) + "天累積%"] = "待觀察"
                    row[str(h) + "天回撤%"] = "待觀察"
                else:
                    wins = sum(1 for r in rets if r > 0)
                    row[str(h) + "天勝率"] = "{:.2f}%".format(wins / len(rets) * 100)
                    row[str(h) + "天平均%"] = "{:.2f}%".format(sum(rets) / len(rets))
                    row[str(h) + "天累積%"] = "{:.2f}%".format(sum(rets))
                    row[str(h) + "天回撤%"] = "{:.2f}%".format(sum(dds) / len(dds))
        rows.append(row)
    return pd.DataFrame(rows)


# ==============================
# 建立年度明細（分5張表）
# ==============================
def build_yearly_tables(prices_dict, threshold):
    result = run_full_backtest(prices_dict, threshold)
    if not result:
        return None, None

    base_rows = []
    for year in sorted(result["yearly"].keys()):
        y = result["yearly"][year]
        base_rows.append({
            "年度": year,
            "觸發次數": len(y["trigger_dates"]),
            "最長連續觸發": y["max_consec"],
        })
    # 合計列
    base_rows.append({
        "年度": "合計/平均",
        "觸發次數": result["total"],
        "最長連續觸發": result["max_consecutive"],
    })

    tables = {}
    for h in HORIZONS:
        rows = []
        for year in sorted(result["yearly"].keys()):
            y = result["yearly"][year]
            rets = y["rets"][h]
            dds = y["dds"][h]
            rows.append({
                "年度": year,
                "觸發次數": len(y["trigger_dates"]),
                "最長連續觸發": y["max_consec"],
                str(h) + "天平均%": fmt(round(sum(rets) / len(rets), 2) if rets else None),
                str(h) + "天累積%": fmt(round(sum(rets), 2) if rets else None),
                str(h) + "天回撤%": fmt(round(sum(dds) / len(dds), 2) if dds else None),
            })
        # 合計
        rets_all = [x["ret"] for x in result["horizon_rets"][h]]
        dds_all = [x["dd"] for x in result["horizon_drawdowns"][h]]
        rows.append({
            "年度": "合計/平均",
            "觸發次數": result["total"],
            "最長連續觸發": result["max_consecutive"],
            str(h) + "天平均%": fmt(round(sum(rets_all) / len(rets_all), 2) if rets_all else None),
            str(h) + "天累積%": fmt(round(sum(rets_all), 2) if rets_all else None),
            str(h) + "天回撤%": fmt(round(sum(dds_all) / len(dds_all), 2) if dds_all else None),
        })
        tables[h] = pd.DataFrame(rows)

    return tables, result


# ==============================
# 建立進場時機表（分5張）
# ==============================
def build_entry_timing_tables(prices_dict, threshold):
    rolling = calc_all_rolling_returns(prices_dict)
    if not rolling:
        return None
    dates = sorted(prices_dict.keys())
    date_to_idx = {d: i for i, d in enumerate(dates)}
    triggers = [r for r in rolling if r["return"] <= threshold]
    if not triggers:
        return None

    trigger_date_set = set(t["date"] for t in triggers)
    consec_day = {}
    cc = 0
    for r in rolling:
        if r["date"] in trigger_date_set:
            cc += 1
            consec_day[r["date"]] = cc
        else:
            cc = 0

    groups = {
        "連續第1天進場": [],
        "連續第2天進場": [],
        "連續第3天以後進場": [],
        "連續結束翌日進場": [],
    }
    rolling_list = list(rolling)
    for i, r in enumerate(rolling_list):
        d = r["date"]
        if d not in trigger_date_set:
            if i > 0 and rolling_list[i - 1]["date"] in trigger_date_set:
                idx = date_to_idx.get(d)
                if idx is None:
                    continue
                ep = r["curr_price"]
                rets = {}
                for h in HORIZONS:
                    fi = idx + h
                    rets[h] = round((prices_dict[dates[fi]] - ep) / ep * 100, 2) if fi < len(dates) else None
                groups["連續結束翌日進場"].append({"rets": rets})
        else:
            day_num = consec_day.get(d, 1)
            idx = date_to_idx.get(d)
            if idx is None:
                continue
            ep = r["curr_price"]
            rets = {}
            for h in HORIZONS:
                fi = idx + h
                rets[h] = round((prices_dict[dates[fi]] - ep) / ep * 100, 2) if fi < len(dates) else None
            item = {"rets": rets}
            if day_num == 1:
                groups["連續第1天進場"].append(item)
            elif day_num == 2:
                groups["連續第2天進場"].append(item)
            else:
                groups["連續第3天以後進場"].append(item)

    tables = {}
    for h in HORIZONS:
        rows = []
        for gname, items in groups.items():
            row = {"進場時機": gname, "樣本數": len(items)}
            rets = [x["rets"][h] for x in items if x["rets"].get(h) is not None]
            if not rets:
                row[str(h) + "天勝率"] = "---"
                row[str(h) + "天平均%"] = "---"
                row[str(h) + "天累積%"] = "---"
            else:
                wins = sum(1 for r in rets if r > 0)
                row[str(h) + "天勝率"] = "{:.2f}%".format(wins / len(rets) * 100)
                row[str(h) + "天平均%"] = "{:.2f}%".format(sum(rets) / len(rets))
                row[str(h) + "天累積%"] = "{:.2f}%".format(sum(rets))
            rows.append(row)
        tables[h] = pd.DataFrame(rows)
    return tables


@st.cache_data(ttl=86400)
def get_industry_lookup():
    lookup = {}
    try:
        res = requests.get("https://openapi.twse.com.tw/v1/company/companyInfo", timeout=10)
        for d in res.json():
            code = d.get("公司代號", "").strip()
            industry = d.get("產業別", "").strip()
            if code:
                lookup[code] = industry
    except:
        pass
    return lookup


@st.cache_data(ttl=86400)
def get_all_tw_stocks():
    stocks = []
    industry_lookup = get_industry_lookup()
    try:
        res = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", timeout=10)
        for d in res.json():
            code = d.get("Code", "").strip()
            name = d.get("Name", "").strip()
            if not code:
                continue
            t = classify_code(code)
            industry = industry_lookup.get(code, "")
            group = get_industry_group(industry, t)
            stocks.append({"code": code, "name": name, "market": "上市", "type": t, "industry": industry, "group": group})
    except:
        pass
    try:
        res = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes", timeout=10)
        for d in res.json():
            code = d.get("SecuritiesCompanyCode", "").strip()
            name = d.get("CompanyName", "").strip()
            if not code:
                continue
            t = classify_code(code)
            industry = industry_lookup.get(code, "")
            group = get_industry_group(industry, t)
            stocks.append({"code": code, "name": name, "market": "上櫃", "type": t, "industry": industry, "group": group})
    except:
        pass
    return stocks


def group_selector(key_prefix):
    groups = list(INDUSTRY_GROUP.keys())
    selected = []
    col_all, _ = st.columns([1, 5])
    with col_all:
        select_all = st.checkbox("✅ 全選", key=key_prefix + "_all")
    cols = st.columns(6)
    for i, g in enumerate(groups):
        icon = GROUP_ICONS.get(g, "")
        with cols[i % 6]:
            checked = st.checkbox(icon + " " + g, key=key_prefix + "_" + g, value=select_all)
            if checked:
                selected.append(g)
    return selected


tab0, tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📖 使用說明", "🔍 每日警示掃描", "📊 批次回測",
    "🔬 個股回測", "🏆 全市場勝率排行", "🔧 系統檢核"
])

# ==============================
# TAB 0
# ==============================
with tab0:
    st.markdown("## 系統使用說明")
    st.info(
        "資料說明：\n"
        "- 股價使用 Yahoo Finance 還原後收盤價（Adjusted Close）\n"
        "- 已自動處理股票分拆、除息、配股的價格調整\n"
        "- 回測年限最長15年（依各標的上市日期而定）"
    )
    st.divider()
    st.markdown("### 顏色說明（台灣慣例）")
    st.markdown("""
- 🔴 **紅色文字** = 正數（獲利）
- 🟢 **綠色文字** = 負數（虧損）
- 🟠 **橘色背景** = 勝率 ≥ 80%
- **報酬熱力圖**：正報酬越深紅越高，負報酬越深綠越低
    """)
    st.divider()
    st.markdown("### 觀察天數說明")
    st.markdown("""
| 天數 | 約等於 | 觀察意義 |
|------|--------|---------|
| 10天 | 2週 | 短期反彈 |
| 20天 | 1個月 | 月線修復 |
| 50天 | 2.5個月 | 季線修復 |
| 100天 | 5個月 | 半年趨勢 |
| 200天 | 1年 | 年線修復 |

> **建議中長線投資者**：主要參考100天及200天的勝率與報酬
    """)
    st.divider()
    st.markdown("### 全市場勝率排行：參數說明")
    st.markdown("""
- **觀察天數**：你進場後要持有多久再看結果。選100天代表「觸發後持有5個月的勝率」
- **最低觸發次數**：過濾掉樣本太少的股票，避免只觸發1次就100%勝率的假象。建議設8~10次以上
- 中長線投資者建議：觀察天數選**100天或200天**，最低觸發次數設**8次以上**
    """)
    st.divider()
    st.markdown("### 核心表格說明")
    st.markdown("""
| 表格 | 用途 |
|------|------|
| 勝率（表A） | 觸發後持有N天，收益為正的機率（≥80%橘色highlight） |
| 平均報酬%（表B） | 平均每次觸發進場，持有N天的平均單筆獲利 |
| 累積報酬%（表C） | 所有觸發報酬直接加總，不除筆數 |
| 進場時機（表D） | 連續觸發第幾天進場效果最好 |
| 平均最大回撤%（表E） | 持有期間內最深跌幅的平均值 |
    """)
    st.divider()
    st.markdown("### 建議使用流程")
    st.markdown("""
1. **全市場勝率排行** → 找出各門檻下勝率最高的股票群
2. **批次回測** → 針對特定產業深入分析
3. **個股回測** → 找出最適合的進場門檻與時機
4. **每日警示掃描** → 每天收盤後檢查當天觸發標的
    """)
    st.warning("本系統為輔助研究工具，不構成投資建議。歷史回測不代表未來績效。")

# ==============================
# TAB 1: 每日警示
# ==============================
with tab1:
    threshold1 = st.slider("警示門檻（跌幅%）", min_value=-30, max_value=-3, value=-10, step=1, key="t1")
    st.markdown("**篩選範圍（可多選，不選代表全部）**")
    selected1 = group_selector("tab1")

    if st.button("🔍 開始掃描", type="primary", key="scan"):
        all_stocks = get_all_tw_stocks()
        scan_list = [s for s in all_stocks if s["group"] in selected1] if selected1 else all_stocks
        total = len(scan_list)
        st.info("共 " + str(total) + " 檔，開始掃描...")
        results = []
        progress = st.progress(0)
        status = st.empty()

        for i, stock in enumerate(scan_list):
            code = stock["code"]
            status.text("掃描中：" + code + " " + stock["name"] + "（" + str(i + 1) + "/" + str(total) + "）")
            prices = get_yahoo_history(code, days=60)
            ret = calc_rolling_return_latest(prices)
            if ret is not None and ret <= threshold1:
                close = calc_latest_close(prices)
                consec = calc_consecutive_trigger_days(prices, threshold1)
                results.append({
                    "產業群組": stock["group"],
                    "產業別": stock["industry"],
                    "代碼": code,
                    "名稱": stock["name"],
                    "最新收盤價": close,
                    "滾動10日報酬率": "{:.2f}%".format(ret),
                    "連續觸發天數": consec,
                    "數值": ret
                })
            progress.progress((i + 1) / total)
            time.sleep(0.15)

        progress.empty()
        status.empty()

        if results:
            df = pd.DataFrame(results).sort_values("數值").drop(columns=["數值"])
            st.error("⚠️ 共 " + str(len(results)) + " 檔觸發（門檻：" + str(threshold1) + "%）")
            show_html(df)
            st.download_button("📥 下載CSV", df.to_csv(index=False).encode("utf-8-sig"), "alert.csv", "text/csv")
        else:
            st.success("目前沒有標的觸發 " + str(threshold1) + "% 警示")

# ==============================
# TAB 2: 批次回測
# ==============================
with tab2:
    st.subheader("批次回測（最長15年）")
    threshold2 = st.slider("觸發門檻（跌幅%）", min_value=-30, max_value=-3, value=-10, step=1, key="t2")
    st.markdown("**選擇回測範圍（可多選，不選預設跑全部ETF）**")
    selected2 = group_selector("tab2")

    if st.button("🚀 開始回測", type="primary", key="backtest"):
        all_stocks_bt = get_all_tw_stocks()
        if selected2:
            bt_list = [s for s in all_stocks_bt if s["group"] in selected2]
        else:
            bt_list = [s for s in all_stocks_bt if s["type"] in ["被動ETF", "主動ETF"]]

        total = len(bt_list)
        st.info("共 " + str(total) + " 檔，開始回測...")
        # 分5張表收集
        all_rows = {h: [] for h in HORIZONS}
        progress = st.progress(0)
        status = st.empty()

        for i, stock in enumerate(bt_list):
            code = stock["code"]
            status.text("回測中：" + code + " " + stock["name"] + "（" + str(i + 1) + "/" + str(total) + "）")
            prices = get_yahoo_history_15y(code)
            result = run_full_backtest(prices, threshold2)

            if result:
                for year in sorted(result["yearly"].keys()):
                    y = result["yearly"][year]
                    base = {
                        "產業群組": stock["group"],
                        "代碼": code,
                        "名稱": stock["name"],
                        "年度": year,
                        "觸發次數": len(y["trigger_dates"]),
                        "最長連續觸發": y["max_consec"],
                    }
                    for h in HORIZONS:
                        rets = y["rets"][h]
                        dds = y["dds"][h]
                        row = dict(base)
                        row[str(h) + "天平均%"] = fmt(round(sum(rets) / len(rets), 2) if rets else None)
                        row[str(h) + "天累積%"] = fmt(round(sum(rets), 2) if rets else None)
                        row[str(h) + "天回撤%"] = fmt(round(sum(dds) / len(dds), 2) if dds else None)
                        all_rows[h].append(row)

            progress.progress((i + 1) / total)
            time.sleep(0.2)

        progress.empty()
        status.empty()

        has_data = any(len(all_rows[h]) > 0 for h in HORIZONS)
        if has_data:
            st.success("✅ 回測完成！")
            for h in HORIZONS:
                if not all_rows[h]:
                    continue
                df_bt = pd.DataFrame(all_rows[h])
                ret_cols = [str(h) + "天平均%", str(h) + "天累積%"]
                dd_cols = [str(h) + "天回撤%"]
                st.markdown("#### " + str(h) + " 天觀察")
                styled = heatmap_ret_style(df_bt, ret_cols)
                styled = styled.map(color_dd, subset=dd_cols)
                show_html(styled)
                st.divider()
            st.download_button("📥 下載CSV（10天）",
                pd.DataFrame(all_rows[10]).to_csv(index=False).encode("utf-8-sig"),
                "backtest_10d.csv", "text/csv")
        else:
            st.warning("沒有找到任何觸發紀錄")

# ==============================
# TAB 3: 個股回測
# ==============================
with tab3:
    st.subheader("個股／ETF 回測＋線圖")
    col1, col2 = st.columns([2, 1])
    with col1:
        single_code = st.text_input("輸入股票／ETF代碼", value="0050", key="single")
    with col2:
        ref_threshold = st.selectbox("線圖與年度明細顯示門檻", [str(t) + "%" for t in THRESHOLDS], index=2, key="ref_thr")

    if st.button("🔬 開始分析", type="primary", key="single_bt"):
        with st.spinner("抓取 " + single_code + " 15年資料中..."):
            prices = get_yahoo_history_15y(single_code)

        if not prices:
            st.error("抓取失敗，請確認代碼是否正確")
        else:
            st.success("成功抓取 " + str(len(prices)) + " 個交易日（" + min(prices.keys()) + " ~ " + max(prices.keys()) + "）")

            with st.spinner("計算各門檻回測中..."):
                df_summary = build_summary_integrated(prices)

            # 表A：勝率
            win_cols = [str(h) + "天勝率" for h in HORIZONS]
            st.markdown("### 表A：勝率（各門檻 x 觀察天數）｜橘色 ≥ 80%")
            win_display = df_summary[["觸發門檻", "樣本數"] + win_cols]
            show_html(win_display.style.map(color_winrate, subset=win_cols))

            # 表B/C/E：分5張（每天數一張）
            st.markdown("### 表B/C/E：報酬與回撤（每觀察天數一張）")
            st.caption("平均%：平均單次報酬 ｜ 累積%：所有觸發加總 ｜ 回撤%：持有期間最深跌幅平均")
            for h in HORIZONS:
                avg_col = str(h) + "天平均%"
                cum_col = str(h) + "天累積%"
                dd_col = str(h) + "天回撤%"
                sub = df_summary[["觸發門檻", "樣本數", avg_col, cum_col, dd_col]]
                st.markdown("**" + str(h) + " 天**")
                ret_cols_h = [avg_col, cum_col]
                styled = heatmap_ret_style(sub, ret_cols_h)
                styled = styled.map(color_dd, subset=[dd_col])
                show_html(styled)

            st.info(
                "計算邏輯：\n"
                "- 每個觸發日各自進場，連續觸發N天即有N筆紀錄\n"
                "- 勝率：觀察日報酬 > 0% 的比例\n"
                "- 平均%：所有觸發的單次報酬算術平均\n"
                "- 累積%：所有觸發報酬直接加總，不除筆數\n"
                "- 回撤%：持有期間內最深跌幅的平均\n"
                "- 待觀察：觸發後未滿觀察天數，不計入統計"
            )

            thr_val = int(ref_threshold.replace("%", ""))

            # 年度明細（分5張）
            yearly_tables, result = build_yearly_tables(prices, thr_val)
            if yearly_tables:
                st.markdown("### 年度明細（門檻 " + ref_threshold + "）")
                for h in HORIZONS:
                    df_y = yearly_tables[h]
                    ret_cols_y = [str(h) + "天平均%", str(h) + "天累積%"]
                    dd_cols_y = [str(h) + "天回撤%"]
                    st.markdown("**" + str(h) + " 天**")
                    styled_y = heatmap_ret_style(df_y, ret_cols_y)
                    styled_y = styled_y.map(color_dd, subset=dd_cols_y)
                    show_html(styled_y)

            # 表D：進場時機（分5張）
            timing_tables = build_entry_timing_tables(prices, thr_val)
            if timing_tables:
                st.markdown("### 表D：進場時機比較（門檻 " + ref_threshold + "）")
                st.caption("連續第幾天進場效果最好？")
                for h in HORIZONS:
                    df_t = timing_tables[h]
                    ret_cols_t = [str(h) + "天平均%", str(h) + "天累積%"]
                    win_col_t = [str(h) + "天勝率"]
                    st.markdown("**" + str(h) + " 天**")
                    styled_t = heatmap_ret_style(df_t, ret_cols_t)
                    styled_t = styled_t.map(color_winrate, subset=win_col_t)
                    show_html(styled_t)
                st.info(
                    "進場時機說明：\n"
                    "- 連續第1天：跌幅首次觸發門檻當天進場\n"
                    "- 連續第2天：已連續觸發2天第2天進場\n"
                    "- 連續第3天以後：連續觸發3天以上每天進場\n"
                    "- 連續結束翌日：連續觸發結束後第一天進場（止跌確認）"
                )
            else:
                st.warning("此門檻無觸發紀錄")

            # 線圖
            if result:
                st.markdown("### 股價走勢＋觸發標記（門檻 " + ref_threshold + "）")
                dates = sorted(prices.keys())
                price_values = [prices[d] for d in dates]
                trigger_dates = set(result["trigger_dates"])
                trigger_x = [d for d in dates if d in trigger_dates]
                trigger_y = [prices[d] for d in trigger_x]
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=dates, y=price_values, mode="lines", name="收盤價",
                                         line=dict(color="#2196F3", width=1.5)))
                fig.add_trace(go.Scatter(x=trigger_x, y=trigger_y, mode="markers",
                                         name="觸發日（" + ref_threshold + "）",
                                         marker=dict(color="red", size=8, symbol="circle")))
                fig.update_layout(height=500, xaxis_title="日期", yaxis_title="收盤價",
                                  hovermode="x unified",
                                  legend=dict(orientation="h", yanchor="bottom", y=1.02))
                st.plotly_chart(fig, use_container_width=True)

                with st.expander("查看所有觸發日明細"):
                    df_trig = pd.DataFrame([{
                        "觸發日": t["date"], "基準日": t["base_date"],
                        "基準價": t["base_price"], "觸發當日收盤": t["curr_price"],
                        "滾動10日報酬率": "{:.2f}%".format(t["return"])
                    } for t in result["triggers"]])
                    show_html(df_trig)

# ==============================
# TAB 4: 全市場勝率排行
# ==============================
with tab4:
    st.subheader("全市場勝率排行（各門檻前10名）")
    st.info(
        "系統會跑15年回測，找出各觸發門檻下勝率最高的前10檔股票\n\n"
        "參數說明：\n"
        "- **觀察天數**：進場後持有多久再看結果（建議中長線選100天或200天）\n"
        "- **最低觸發次數**：過濾樣本太少的股票（建議設8~10次以上，避免假勝率）"
    )
    st.markdown("**選擇掃描範圍**")
    selected4 = group_selector("tab4")
    col_h, col_m = st.columns(2)
    with col_h:
        horizon4 = st.selectbox("觀察天數", [str(h) + "天" for h in HORIZONS], index=3, key="h4")
    with col_m:
        min_triggers = st.number_input("最低觸發次數", min_value=3, max_value=30, value=8)

    if st.button("🏆 開始計算勝率排行", type="primary", key="winrank"):
        all_stocks_r = get_all_tw_stocks()
        rank_list = [s for s in all_stocks_r if s["group"] in selected4] if selected4 else [s for s in all_stocks_r if s["type"] == "個股"]

        h_val = int(horizon4.replace("天", ""))
        total = len(rank_list)
        st.info("共 " + str(total) + " 檔，開始計算...")

        thr_results = {thr: [] for thr in THRESHOLDS}
        progress = st.progress(0)
        status = st.empty()

        for i, stock in enumerate(rank_list):
            code = stock["code"]
            status.text("計算中：" + code + " " + stock["name"] + "（" + str(i + 1) + "/" + str(total) + "）")
            prices = get_yahoo_history_15y(code)
            if not prices:
                progress.progress((i + 1) / total)
                continue
            for thr in THRESHOLDS:
                result = run_full_backtest(prices, thr)
                if result is None:
                    continue
                rets = [x["ret"] for x in result["horizon_rets"][h_val]]
                if len(rets) < min_triggers:
                    continue
                wins = sum(1 for r in rets if r > 0)
                thr_results[thr].append({
                    "代碼": code, "名稱": stock["name"],
                    "產業群組": stock["group"], "產業別": stock["industry"],
                    "觸發次數": result["total"],
                    "勝率%": round(wins / len(rets) * 100, 2),
                    "平均報酬%": round(sum(rets) / len(rets), 2),
                })
            progress.progress((i + 1) / total)
            time.sleep(0.2)

        progress.empty()
        status.empty()
        st.success("✅ 計算完成！觀察天數：" + horizon4 + "｜最低觸發次數：" + str(min_triggers))

        for thr in THRESHOLDS:
            items = thr_results[thr]
            if not items:
                st.markdown("#### 門檻 " + str(thr) + "%：無足夠資料")
                continue
            df_rank = pd.DataFrame(items).sort_values("勝率%", ascending=False).head(10).reset_index(drop=True)
            industry_str = "、".join([k + "(" + str(v) + "檔)" for k, v in df_rank["產業群組"].value_counts().items()])
            st.markdown("#### 門檻 " + str(thr) + "%：勝率前10名")
            st.caption("產業分布：" + industry_str)
            df_rank["勝率%"] = df_rank["勝率%"].apply(lambda x: "{:.2f}%".format(x))
            df_rank["平均報酬%"] = df_rank["平均報酬%"].apply(lambda x: "{:.2f}%".format(x))
            styled_rank = df_rank.style.map(color_winrate, subset=["勝率%"]).map(color_ret, subset=["平均報酬%"])
            show_html(styled_rank)
            st.divider()

# ==============================
# TAB 5: 系統檢核
# ==============================
with tab5:
    st.subheader("🔧 系統檢核")
    st.info("點擊下方按鈕，自動驗證各項資料來源與計算邏輯是否正常")

    if st.button("▶️ 執行系統檢核", type="primary", key="check"):
        checks = []

        def run_check(name, fn):
            try:
                ok, detail = fn()
                checks.append({"項目": name, "狀態": "✅ 正常" if ok else "❌ 異常", "說明": detail})
            except Exception as e:
                checks.append({"項目": name, "狀態": "❌ 失敗", "說明": str(e)})

        def check_twse():
            res = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", timeout=10)
            data = res.json()
            return len(data) > 100, "取得 " + str(len(data)) + " 筆上市證券"

        def check_tpex():
            res = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes", timeout=10)
            data = res.json()
            return len(data) > 50, "取得 " + str(len(data)) + " 筆上櫃證券"

        def check_yahoo():
            p = get_yahoo_history("2330", days=60)
            if len(p) < 10:
                return False, "資料筆數不足：" + str(len(p))
            dates_c = sorted(p.keys())
            return True, "2330台積電 最新收盤：" + str(p[dates_c[-1]]) + "（" + dates_c[-1] + "）｜取得 " + str(len(p)) + " 筆"

        def check_logic():
            tp = {}
            for i in range(20):
                d = (datetime.today() - timedelta(days=20 - i)).strftime("%Y-%m-%d")
                tp[d] = 100.0 if i < 11 else 88.0
            ret = calc_rolling_return_latest(tp)
            ok = ret is not None and abs(ret - (-12.0)) < 0.01
            return ok, "計算結果：{:.2f}%（預期 -12.00%）{}".format(ret or 0, "✓" if ok else "✗")

        def check_15y():
            p = get_yahoo_history_15y("0050")
            if len(p) < 1000:
                return False, "資料筆數不足：" + str(len(p))
            dates_c = sorted(p.keys())
            return True, "0050 取得 " + str(len(p)) + " 日（" + dates_c[0] + " ~ " + dates_c[-1] + "）還原後股價"

        def check_trigger():
            p = get_yahoo_history_15y("2330")
            r = run_full_backtest(p, -7)
            if r and r["total"] > 0:
                return True, "2330 @-7%：觸發 " + str(r["total"]) + " 次，最長連續 " + str(r["max_consecutive"]) + " 天"
            return False, "觸發次數為0"

        with st.spinner("執行中..."):
            run_check("證交所TWSE API", check_twse)
            run_check("櫃買中心TPEX API", check_tpex)
            run_check("Yahoo Finance API（2330）", check_yahoo)
            run_check("滾動10日報酬計算邏輯", check_logic)
            run_check("還原後股價（0050 15年）", check_15y)
            run_check("觸發計算驗證（2330 @-7%）", check_trigger)

        show_html(pd.DataFrame(checks))
        if all("✅" in c["狀態"] for c in checks):
            st.success("✅ 所有系統檢核通過！")
        else:
            failed = [c["項目"] for c in checks if "❌" in c["狀態"]]
            st.error("❌ 異常項目：" + "、".join(failed))
