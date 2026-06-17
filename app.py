import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time

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
                "date": dates[i], "base_date": dates[i - 10],
                "base_price": base_price, "curr_price": curr_price,
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
    max_consecutive = current_consecutive = 0
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
                horizon_drawdowns[h].append({"dd": round(min_ret, 2), "year": year})

    yearly = {}
    for t in triggers:
        year = t["date"][:4]
        if year not in yearly:
            yearly[year] = {"trigger_dates": set(), "max_consec": 0,
                            "rets": {hh: [] for hh in HORIZONS},
                            "dds": {hh: [] for hh in HORIZONS}}
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

    return {"triggers": triggers, "trigger_dates": list(trigger_dates),
            "max_consecutive": max_consecutive, "horizon_rets": horizon_rets,
            "horizon_drawdowns": horizon_drawdowns, "yearly": yearly, "total": len(triggers)}


# ==============================
# 顏色與樣式函數
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


def heatmap_positive(df, cols):
    """正報酬熱力圖：越高越深紅，負報酬越深綠，確保文字可讀"""
    all_vals = []
    for c in cols:
        for v in df[c]:
            try:
                all_vals.append(float(str(v).replace("%", "")))
            except:
                pass
    max_pos = max((v for v in all_vals if v > 0), default=1)
    min_neg = min((v for v in all_vals if v < 0), default=-1)

    def cell_style(val):
        if val is None or str(val) in ["", "---", "待觀察"]:
            return ""
        try:
            v = float(str(val).replace("%", ""))
            if v > 0:
                intensity = min(v / max_pos, 1.0)
                # 淺到深紅：從 #FFE0E0 到 #8B0000
                r = int(255 - intensity * 115)
                g = int(224 - intensity * 224)
                b = int(224 - intensity * 224)
                text = "white" if intensity > 0.55 else "#8B0000"
                return "background-color: rgb({},{},{}); color: {}; font-weight: bold".format(r, g, b, text)
            elif v < 0:
                intensity = min(abs(v) / abs(min_neg), 1.0)
                # 淺到深綠：從 #E0FFE0 到 #006400
                r = int(224 - intensity * 224)
                g = int(255 - intensity * 111)
                b = int(224 - intensity * 224)
                text = "white" if intensity > 0.55 else "#006400"
                return "background-color: rgb({},{},{}); color: {}; font-weight: bold".format(r, g, b, text)
            return ""
        except:
            return ""

    return df.style.map(cell_style, subset=cols)


def heatmap_negative(df, cols):
    """回撤熱力圖：越深（越負）越深橘/紅，代表風險越高"""
    all_vals = []
    for c in cols:
        for v in df[c]:
            try:
                all_vals.append(float(str(v).replace("%", "")))
            except:
                pass
    min_neg = min((v for v in all_vals if v < 0), default=-1)

    def cell_style(val):
        if val is None or str(val) in ["", "---", "待觀察"]:
            return ""
        try:
            v = float(str(val).replace("%", ""))
            if v < 0:
                intensity = min(abs(v) / abs(min_neg), 1.0)
                # 淺黃到深橘紅：代表回撤越深風險越高
                r = int(255)
                g = int(255 - intensity * 180)
                b = int(200 - intensity * 200)
                text = "white" if intensity > 0.65 else "#8B2500"
                return "background-color: rgb({},{},{}); color: {}; font-weight: bold".format(r, g, b, text)
            return ""
        except:
            return ""

    return df.style.map(cell_style, subset=cols)


def fmt(v):
    if v is None:
        return "待觀察"
    return "{:.2f}%".format(v)


def show_html(styled_or_df):
    if hasattr(styled_or_df, "to_html"):
        st.markdown(styled_or_df.to_html(index=False), unsafe_allow_html=True)
    else:
        st.markdown(styled_or_df.to_html(index=False), unsafe_allow_html=True)


# ==============================
# 建立整合總覽表（A/B/E）
# ==============================
def build_summary_tables(prices_dict):
    """建立三張總覽表：勝率、平均報酬、最大回撤（格式：門檻 x 觀察天數）"""
    win_rows, avg_rows, dd_rows = [], [], []
    for thr in THRESHOLDS:
        result = run_full_backtest(prices_dict, thr)
        win_row = {"觸發門檻": str(thr) + "%", "樣本數": 0 if result is None else result["total"]}
        avg_row = {"觸發門檻": str(thr) + "%", "樣本數": 0 if result is None else result["total"]}
        dd_row = {"觸發門檻": str(thr) + "%", "樣本數": 0 if result is None else result["total"]}
        for h in HORIZONS:
            col_w = str(h) + "天勝率"
            col_a = str(h) + "天平均報酬%"
            col_d = str(h) + "天平均最大回撤%"
            if result is None:
                win_row[col_w] = "---"
                avg_row[col_a] = "---"
                dd_row[col_d] = "---"
            else:
                rets = [x["ret"] for x in result["horizon_rets"][h]]
                dds = [x["dd"] for x in result["horizon_drawdowns"][h]]
                if not rets:
                    win_row[col_w] = "待觀察"
                    avg_row[col_a] = "待觀察"
                    dd_row[col_d] = "待觀察"
                else:
                    wins = sum(1 for r in rets if r > 0)
                    win_row[col_w] = "{:.2f}%".format(wins / len(rets) * 100)
                    avg_row[col_a] = "{:.2f}%".format(sum(rets) / len(rets))
                    dd_row[col_d] = "{:.2f}%".format(sum(dds) / len(dds))
        win_rows.append(win_row)
        avg_rows.append(avg_row)
        dd_rows.append(dd_row)
    return pd.DataFrame(win_rows), pd.DataFrame(avg_rows), pd.DataFrame(dd_rows)


# ==============================
# 年度明細：一張表，只留平均報酬（簡潔可讀）
# ==============================
def build_yearly_table(prices_dict, threshold):
    result = run_full_backtest(prices_dict, threshold)
    if not result:
        return None, None
    rows = []
    for year in sorted(result["yearly"].keys()):
        y = result["yearly"][year]
        row = {"年度": year, "觸發次數": len(y["trigger_dates"]), "最長連續觸發": y["max_consec"]}
        for h in HORIZONS:
            rets = y["rets"][h]
            row[str(h) + "天平均%"] = fmt(round(sum(rets) / len(rets), 2) if rets else None)
        rows.append(row)
    # 合計列
    total_row = {"年度": "合計/平均", "觸發次數": result["total"], "最長連續觸發": result["max_consecutive"]}
    for h in HORIZONS:
        rets = [x["ret"] for x in result["horizon_rets"][h]]
        total_row[str(h) + "天平均%"] = fmt(round(sum(rets) / len(rets), 2) if rets else None)
    rows.append(total_row)
    return pd.DataFrame(rows), result


# ==============================
# 進場時機：單一天數，四時機橫向比較
# ==============================
def build_entry_timing_table(prices_dict, threshold, horizon):
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

    groups = {"連續第1天進場": [], "連續第2天進場": [], "連續第3天以後進場": [], "連續結束翌日進場": []}
    rolling_list = list(rolling)
    for i, r in enumerate(rolling_list):
        d = r["date"]
        if d not in trigger_date_set:
            if i > 0 and rolling_list[i - 1]["date"] in trigger_date_set:
                idx = date_to_idx.get(d)
                if idx is None:
                    continue
                ep = r["curr_price"]
                fi = idx + horizon
                ret = round((prices_dict[dates[fi]] - ep) / ep * 100, 2) if fi < len(dates) else None
                groups["連續結束翌日進場"].append(ret)
        else:
            day_num = consec_day.get(d, 1)
            idx = date_to_idx.get(d)
            if idx is None:
                continue
            ep = r["curr_price"]
            fi = idx + horizon
            ret = round((prices_dict[dates[fi]] - ep) / ep * 100, 2) if fi < len(dates) else None
            if day_num == 1:
                groups["連續第1天進場"].append(ret)
            elif day_num == 2:
                groups["連續第2天進場"].append(ret)
            else:
                groups["連續第3天以後進場"].append(ret)

    rows = []
    for gname, rets_raw in groups.items():
        rets = [r for r in rets_raw if r is not None]
        row = {"進場時機": gname, "樣本數": len(rets_raw)}
        if not rets:
            row["勝率"] = "---"
            row["平均報酬%"] = "---"
            row["累積報酬%"] = "---"
        else:
            wins = sum(1 for r in rets if r > 0)
            row["勝率"] = "{:.2f}%".format(wins / len(rets) * 100)
            row["平均報酬%"] = "{:.2f}%".format(sum(rets) / len(rets))
            row["累積報酬%"] = "{:.2f}%".format(sum(rets))
        rows.append(row)
    return pd.DataFrame(rows)


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
# TAB 0: 使用說明
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
- **報酬熱力圖**：越深紅 = 報酬越高，越深綠 = 報酬越低（虧損越深）
- **回撤熱力圖**：越深橘紅 = 回撤越深 = 持有過程越痛苦
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

> **中長線投資者建議**：主要參考 100天 及 200天 的勝率與報酬
    """)
    st.divider()
    st.markdown("### 全市場勝率排行：參數說明")
    st.markdown("""
- **觀察天數**：你進場後要持有多久再看結果。選100天代表「觸發後持有5個月的勝率」
- **最低觸發次數**：過濾掉樣本太少的股票，避免只觸發1次就100%勝率的假象
- 中長線投資者建議：觀察天數選 **100天或200天**，最低觸發次數設 **8次以上**
    """)
    st.divider()
    st.markdown("### 核心表格說明")
    st.markdown("""
| 表格 | 用途 |
|------|------|
| 表A 勝率 | 觸發後持有N天，收益為正的機率（≥80%橘色highlight） |
| 表B 平均報酬% | 平均每次觸發進場，持有N天的平均獲利（熱力圖：越深紅越好） |
| 表E 平均最大回撤% | 持有期間內最深跌幅平均（熱力圖：越深橘紅風險越高） |
| 年度明細 | 各年度觸發次數與平均報酬，一眼看出哪幾年表現最好 |
| 進場時機（表D） | 連續觸發第幾天進場勝率最高（搭配觀察天數選單切換） |
    """)
    st.divider()
    st.markdown("### 建議使用流程")
    st.markdown("""
1. **全市場勝率排行** → 找出各門檻下勝率最高的股票群
2. **批次回測** → 針對特定產業深入分析年度表現
3. **個股回測** → 找出最適合的進場門檻與時機
4. **每日警示掃描** → 每天收盤後檢查當天觸發標的
    """)
    st.warning("本系統為輔助研究工具，不構成投資建議。歷史回測不代表未來績效。")

# ==============================
# TAB 1: 每日警示掃描
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
        all_rows = []
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
                    row = {
                        "產業群組": stock["group"], "代碼": code, "名稱": stock["name"],
                        "年度": year, "觸發次數": len(y["trigger_dates"]), "最長連續觸發": y["max_consec"],
                    }
                    for h in HORIZONS:
                        rets = y["rets"][h]
                        dds = y["dds"][h]
                        row[str(h) + "天平均%"] = fmt(round(sum(rets) / len(rets), 2) if rets else None)
                        row[str(h) + "天回撤%"] = fmt(round(sum(dds) / len(dds), 2) if dds else None)
                    all_rows.append(row)

            progress.progress((i + 1) / total)
            time.sleep(0.2)

        progress.empty()
        status.empty()

        if all_rows:
            df_bt = pd.DataFrame(all_rows)
            avg_cols = [str(h) + "天平均%" for h in HORIZONS]
            dd_cols = [str(h) + "天回撤%" for h in HORIZONS]
            st.success("✅ 回測完成！")
            styled = heatmap_positive(df_bt, avg_cols)
            styled = heatmap_negative(df_bt.style, dd_cols) if hasattr(df_bt, "style") else styled
            # 分兩段顯示：報酬 + 回撤
            st.markdown("**報酬表（熱力圖：越深紅報酬越高）**")
            avg_display = df_bt[["產業群組", "代碼", "名稱", "年度", "觸發次數", "最長連續觸發"] + avg_cols]
            show_html(heatmap_positive(avg_display, avg_cols))
            st.markdown("**回撤表（熱力圖：越深橘紅回撤越深）**")
            dd_display = df_bt[["產業群組", "代碼", "名稱", "年度", "觸發次數", "最長連續觸發"] + dd_cols]
            show_html(heatmap_negative(dd_display, dd_cols))
            st.download_button("📥 下載CSV", df_bt.to_csv(index=False).encode("utf-8-sig"), "backtest.csv", "text/csv")
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
        ref_threshold = st.selectbox("年度明細與進場時機顯示門檻", [str(t) + "%" for t in THRESHOLDS], index=2, key="ref_thr")

    if st.button("🔬 開始分析", type="primary", key="single_bt"):
        with st.spinner("抓取 " + single_code + " 15年資料中..."):
            prices = get_yahoo_history_15y(single_code)

        if not prices:
            st.error("抓取失敗，請確認代碼是否正確")
        else:
            st.success("成功抓取 " + str(len(prices)) + " 個交易日（" + min(prices.keys()) + " ~ " + max(prices.keys()) + "）")

            with st.spinner("計算各門檻回測中..."):
                df_win, df_avg, df_dd = build_summary_tables(prices)

            win_cols = [str(h) + "天勝率" for h in HORIZONS]
            avg_cols = [str(h) + "天平均報酬%" for h in HORIZONS]
            dd_cols = [str(h) + "天平均最大回撤%" for h in HORIZONS]

            # 表A：勝率
            st.markdown("### 表A：勝率（各門檻 × 觀察天數）｜橘色 ≥ 80%")
            st.caption("勝率 = 觸發進場後，持有到觀察天數當天收益為正的比例")
            show_html(df_win.style.map(color_winrate, subset=win_cols))

            # 表B：平均報酬（熱力圖）
            st.markdown("### 表B：平均單次報酬%（各門檻 × 觀察天數）")
            st.caption("每次觸發進場後，持有到觀察天數的平均報酬。越深紅 = 報酬越高")
            show_html(heatmap_positive(df_avg, avg_cols))

            # 表E：平均最大回撤（熱力圖）
            st.markdown("### 表E：平均最大回撤%（各門檻 × 觀察天數）")
            st.caption("觸發進場後，持有期間曾經最深跌到多少。越深橘紅 = 持有過程越痛苦，需有心理準備")
            show_html(heatmap_negative(df_dd, dd_cols))

            st.info(
                "計算邏輯：\n"
                "- 每個觸發日各自進場，連續觸發N天即有N筆紀錄\n"
                "- 勝率：觀察天數當天報酬 > 0% 的比例\n"
                "- 平均報酬%：所有觸發單次報酬的算術平均\n"
                "- 最大回撤%：每筆觸發在持有期間曾出現的最深跌幅，取平均\n"
                "- 待觀察：觸發後未滿觀察天數，不計入統計"
            )

            thr_val = int(ref_threshold.replace("%", ""))

            # 年度明細：一張表，只顯示平均報酬，有熱力圖
            df_yearly, result = build_yearly_table(prices, thr_val)
            if df_yearly is not None:
                yearly_avg_cols = [str(h) + "天平均%" for h in HORIZONS]
                st.markdown("### 年度明細（門檻 " + ref_threshold + "）")
                st.caption(
                    "各年度觸發次數與各持有天數的平均報酬。\n"
                    "解讀重點：橫向看哪個持有天數報酬最穩；縱向看哪幾年跌破門檻後反彈最強。"
                )
                show_html(heatmap_positive(df_yearly, yearly_avg_cols))

            # 進場時機：選單切換天數，單一張表四時機比較
            st.markdown("### 進場時機比較（表D）｜門檻 " + ref_threshold + "）")
            st.caption(
                "連續觸發第幾天進場勝率最高？\n"
                "解讀重點：比較四種進場時機的勝率與報酬，找出最佳切入點。\n"
                "切換下方天數選單，觀察不同持有長度下各進場時機的差異。"
            )
            horizon_choice = st.selectbox(
                "選擇觀察天數",
                [str(h) + "天" for h in HORIZONS],
                index=2,
                key="timing_horizon"
            )
            h_timing = int(horizon_choice.replace("天", ""))
            df_timing = build_entry_timing_table(prices, thr_val, h_timing)
            if df_timing is not None:
                ret_cols_t = ["平均報酬%", "累積報酬%"]
                win_col_t = ["勝率"]
                styled_t = heatmap_positive(df_timing, ret_cols_t)
                styled_t = styled_t.map(color_winrate, subset=win_col_t)
                show_html(styled_t)
                st.caption(
                    "四種進場時機說明：\n"
                    "• 連續第1天：跌幅首次觸發門檻當天進場（最早，風險最高但數量最多）\n"
                    "• 連續第2天：已連續觸發2天才進場（稍微確認下跌趨勢）\n"
                    "• 連續第3天以後：連續觸發3天以上才進場（等待更深的超跌）\n"
                    "• 連續結束翌日：連續觸發全部結束、止跌後第一天進場（最保守，確認止跌）"
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
        rank_list = ([s for s in all_stocks_r if s["group"] in selected4]
                     if selected4 else [s for s in all_stocks_r if s["type"] == "個股"])
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
            show_html(df_rank.style.map(color_winrate, subset=["勝率%"]).map(color_ret, subset=["平均報酬%"]))
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

        with st.spinner("執行中..."):
            run_check("證交所TWSE API", lambda: (
                len(requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", timeout=10).json()) > 100,
                "取得 " + str(len(requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", timeout=10).json())) + " 筆上市證券"
            ))
            run_check("櫃買中心TPEX API", lambda: (
                len(requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes", timeout=10).json()) > 50,
                "取得 " + str(len(requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes", timeout=10).json())) + " 筆上櫃證券"
            ))

            def check_yahoo():
                p = get_yahoo_history("2330", days=60)
                if len(p) < 10:
                    return False, "資料筆數不足：" + str(len(p))
                d = sorted(p.keys())
                return True, "2330台積電 最新收盤：" + str(p[d[-1]]) + "（" + d[-1] + "）｜取得 " + str(len(p)) + " 筆"
            run_check("Yahoo Finance API（2330）", check_yahoo)
def check_data_freshness():
                p = get_yahoo_history("2330", days=10)
                if not p:
                    return False, "無法取得資料"
                latest_date = sorted(p.keys())[-1]
                latest_dt = datetime.strptime(latest_date, "%Y-%m-%d")
                days_diff = (datetime.today() - latest_dt).days
                # 允許週末+假日，超過4天才算異常
                if days_diff <= 4:
                    return True, "最新資料日期：" + latest_date + "（距今 " + str(days_diff) + " 天）✓"
                else:
                    return False, "最新資料距今 " + str(days_diff) + " 天，可能有延遲！最新日期：" + latest_date
            run_check("資料即時性（最新資料距今天數）", check_data_freshness)

            def check_adj_price():
                # 驗證0050在2021-10-21除息後還原股價是否合理
                # 除息前後兩個月各抓，還原後不應有大跳空
                p = get_yahoo_history_15y("0050")
                if len(p) < 100:
                    return False, "資料不足"
                dates = sorted(p.keys())
                # 找2021-10附近的價格，還原後應該平滑連續
                nearby = [d for d in dates if "2021-10" in d or "2021-09" in d or "2021-11" in d]
                if len(nearby) < 10:
                    return True, "無法取得2021年資料驗證（標的可能較新），跳過此項"
                prices_nearby = [p[d] for d in sorted(nearby)]
                # 計算相鄰日價差，還原後不應超過15%的單日跳空
                max_jump = max(abs(prices_nearby[i] - prices_nearby[i-1]) / prices_nearby[i-1] * 100
                               for i in range(1, len(prices_nearby)))
                if max_jump < 15:
                    return True, "0050還原股價連續性正常（2021年除息前後最大單日跳空：{:.2f}%）".format(max_jump)
                else:
                    return False, "還原股價異常！最大單日跳空：{:.2f}%（超過15%門檻）".format(max_jump)
            run_check("還原股價連續性驗證（0050除息）", check_adj_price)
            def check_logic():
                tp = {(datetime.today() - timedelta(days=20 - i)).strftime("%Y-%m-%d"): (100.0 if i < 11 else 88.0) for i in range(20)}
                ret = calc_rolling_return_latest(tp)
                ok = ret is not None and abs(ret - (-12.0)) < 0.01
                return ok, "計算結果：{:.2f}%（預期 -12.00%）{}".format(ret or 0, "✓" if ok else "✗")
            run_check("滾動10日報酬計算邏輯", check_logic)

            def check_15y():
                p = get_yahoo_history_15y("0050")
                if len(p) < 1000:
                    return False, "資料筆數不足：" + str(len(p))
                d = sorted(p.keys())
                return True, "0050 取得 " + str(len(p)) + " 日（" + d[0] + " ~ " + d[-1] + "）還原後股價"
            run_check("還原後股價（0050 15年）", check_15y)

            def check_trigger():
                p = get_yahoo_history_15y("2330")
                r = run_full_backtest(p, -7)
                if r and r["total"] > 0:
                    return True, "2330 @-7%：觸發 " + str(r["total"]) + " 次，最長連續 " + str(r["max_consecutive"]) + " 天"
                return False, "觸發次數為0"
            run_check("觸發計算驗證（2330 @-7%）", check_trigger)

        show_html(pd.DataFrame(checks))
        if all("✅" in c["狀態"] for c in checks):
            st.success("✅ 所有系統檢核通過！")
        else:
            failed = [c["項目"] for c in checks if "❌" in c["狀態"]]
            st.error("❌ 異常項目：" + "、".join(failed))
