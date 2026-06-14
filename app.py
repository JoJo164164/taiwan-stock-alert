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
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/" + code + ".TW"
        + "?interval=1d&period1=" + str(int(start.timestamp()))
        + "&period2=" + str(int(end.timestamp()))
    )
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
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/" + code + ".TW"
        + "?interval=1d&period1=" + str(int(start.timestamp()))
        + "&period2=" + str(int(end.timestamp()))
    )
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


def calc_all_rolling_returns(prices_dict):
    if len(prices_dict) < 11:
        return []
    dates = sorted(prices_dict.keys())
    results = []
    for i in range(10, len(dates)):
        base_date = dates[i - 10]
        curr_date = dates[i]
        base_price = prices_dict[base_date]
        curr_price = prices_dict[curr_date]
        if base_price > 0:
            ret = (curr_price - base_price) / base_price * 100
            results.append({
                "date": curr_date,
                "base_date": base_date,
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
                horizon_rets[h].append({
                    "ret": round(ret, 2),
                    "year": year,
                    "date": t["date"]
                })

                min_ret = 0.0
                for d in range(1, h + 1):
                    fi = idx + d
                    if fi < len(dates):
                        p = prices_dict[dates[fi]]
                        r = (p - entry_price) / entry_price * 100
                        if r < min_ret:
                            min_ret = r
                horizon_drawdowns[h].append({
                    "dd": round(min_ret, 2),
                    "year": year,
                    "date": t["date"]
                })

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
            year = item["year"]
            if year in yearly:
                yearly[year]["rets"][h].append(item["ret"])
        for item in horizon_drawdowns[h]:
            year = item["year"]
            if year in yearly:
                yearly[year]["dds"][h].append(item["dd"])

    for year in yearly:
        mc = 0
        cc = 0
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


def build_entry_timing_table(prices_dict, threshold):
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
                entry_price = r["curr_price"]
                rets = {}
                for h in HORIZONS:
                    future_idx = idx + h
                    if future_idx < len(dates):
                        future_price = prices_dict[dates[future_idx]]
                        rets[h] = round((future_price - entry_price) / entry_price * 100, 2)
                    else:
                        rets[h] = None
                groups["連續結束翌日進場"].append({"rets": rets, "date": d})
        else:
            day_num = consec_day.get(d, 1)
            idx = date_to_idx.get(d)
            if idx is None:
                continue
            entry_price = r["curr_price"]
            rets = {}
            for h in HORIZONS:
                future_idx = idx + h
                if future_idx < len(dates):
                    future_price = prices_dict[dates[future_idx]]
                    rets[h] = round((future_price - entry_price) / entry_price * 100, 2)
                else:
                    rets[h] = None
            item = {"rets": rets, "date": d}
            if day_num == 1:
                groups["連續第1天進場"].append(item)
            elif day_num == 2:
                groups["連續第2天進場"].append(item)
            else:
                groups["連續第3天以後進場"].append(item)
    rows = []
    for group_name, items in groups.items():
        row = {"進場時機": group_name, "樣本數": len(items)}
        if not items:
            for h in HORIZONS:
                row[str(h) + "天勝率"] = "---"
                row[str(h) + "天平均報酬%"] = "---"
                row[str(h) + "天累積報酬%"] = "---"
        else:
            for h in HORIZONS:
                rets = [x["rets"][h] for x in items if x["rets"].get(h) is not None]
                if not rets:
                    row[str(h) + "天勝率"] = "待觀察"
                    row[str(h) + "天平均報酬%"] = "待觀察"
                    row[str(h) + "天累積報酬%"] = "待觀察"
                else:
                    wins = sum(1 for r in rets if r > 0)
                    row[str(h) + "天勝率"] = "{:.2f}%".format(wins / len(rets) * 100)
                    row[str(h) + "天平均報酬%"] = "{:.2f}%".format(sum(rets) / len(rets))
                    row[str(h) + "天累積報酬%"] = "{:.2f}%".format(sum(rets))
        rows.append(row)
    return pd.DataFrame(rows)


def build_summary_tables(prices_dict):
    win_rows, avg_rows, cum_rows, dd_rows = [], [], [], []
    for thr in THRESHOLDS:
        result = run_full_backtest(prices_dict, thr)
        win_row = {"觸發門檻": str(thr) + "%", "樣本數": 0}
        avg_row = {"觸發門檻": str(thr) + "%"}
        cum_row = {"觸發門檻": str(thr) + "%"}
        dd_row = {"觸發門檻": str(thr) + "%"}
        if result is None:
            for h in HORIZONS:
                win_row[str(h) + "天勝率"] = "---"
                avg_row[str(h) + "天平均報酬%"] = "---"
                cum_row[str(h) + "天累積報酬%"] = "---"
                dd_row[str(h) + "天平均最大回撤%"] = "---"
        else:
            win_row["樣本數"] = result["total"]
            for h in HORIZONS:
                rets = [x["ret"] for x in result["horizon_rets"][h]]
                dds = [x["dd"] for x in result["horizon_drawdowns"][h]]
                if not rets:
                    win_row[str(h) + "天勝率"] = "待觀察"
                    avg_row[str(h) + "天平均報酬%"] = "待觀察"
                    cum_row[str(h) + "天累積報酬%"] = "待觀察"
                    dd_row[str(h) + "天平均最大回撤%"] = "待觀察"
                else:
                    wins = sum(1 for r in rets if r > 0)
                    win_row[str(h) + "天勝率"] = "{:.2f}%".format(wins / len(rets) * 100)
                    avg_row[str(h) + "天平均報酬%"] = "{:.2f}%".format(sum(rets) / len(rets))
                    cum_row[str(h) + "天累積報酬%"] = "{:.2f}%".format(sum(rets))
                    dd_row[str(h) + "天平均最大回撤%"] = "{:.2f}%".format(sum(dds) / len(dds))
        win_rows.append(win_row)
        avg_rows.append(avg_row)
        cum_rows.append(cum_row)
        dd_rows.append(dd_row)
    return pd.DataFrame(win_rows), pd.DataFrame(avg_rows), pd.DataFrame(cum_rows), pd.DataFrame(dd_rows)


def build_yearly_table(prices_dict, threshold):
    result = run_full_backtest(prices_dict, threshold)
    if not result:
        return None, None
    rows = []
    for year in sorted(result["yearly"].keys()):
        y = result["yearly"][year]
        row = {
            "年度": year,
            "觸發次數": len(y["trigger_dates"]),
            "最長連續觸發天數": y["max_consec"],
        }
        for h in HORIZONS:
            rets = y["rets"][h]
            dds = y["dds"][h]
            if not rets:
                row[str(h) + "天平均報酬%"] = "待觀察"
                row[str(h) + "天累積報酬%"] = "待觀察"
                row[str(h) + "天平均最大回撤%"] = "待觀察"
            else:
                row[str(h) + "天平均報酬%"] = "{:.2f}%".format(sum(rets) / len(rets))
                row[str(h) + "天累積報酬%"] = "{:.2f}%".format(sum(rets))
                row[str(h) + "天平均最大回撤%"] = "{:.2f}%".format(sum(dds) / len(dds))
        rows.append(row)
    total_row = {
        "年度": "合計/平均",
        "觸發次數": result["total"],
        "最長連續觸發天數": result["max_consecutive"],
    }
    for h in HORIZONS:
        rets = [x["ret"] for x in result["horizon_rets"][h]]
        dds = [x["dd"] for x in result["horizon_drawdowns"][h]]
        if not rets:
            total_row[str(h) + "天平均報酬%"] = "待觀察"
            total_row[str(h) + "天累積報酬%"] = "待觀察"
            total_row[str(h) + "天平均最大回撤%"] = "待觀察"
        else:
            total_row[str(h) + "天平均報酬%"] = "{:.2f}%".format(sum(rets) / len(rets))
            total_row[str(h) + "天累積報酬%"] = "{:.2f}%".format(sum(rets))
            total_row[str(h) + "天平均最大回撤%"] = "{:.2f}%".format(sum(dds) / len(dds))
    rows.append(total_row)
    return pd.DataFrame(rows), result


@st.cache_data(ttl=86400)
def get_all_tw_stocks():
    stocks = []
    try:
        url = "https://openapi.twse.com.tw/v1/company/companyInfo"
        res = requests.get(url, timeout=10)
        data = res.json()
        for d in data:
            code = d.get("公司代號", "").strip()
            name = d.get("公司簡稱", "").strip()
            industry = d.get("產業別", "").strip()
            t = classify_code(code)
            group = get_industry_group(industry, t)
            stocks.append({"code": code, "name": name, "market": "上市", "type": t, "industry": industry, "group": group})
    except:
        pass
    try:
        url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
        res = requests.get(url, timeout=10)
        data = res.json()
        for d in data:
            code = d["SecuritiesCompanyCode"].strip()
            name = d["CompanyName"].strip()
            t = classify_code(code)
            group = get_industry_group("", t)
            stocks.append({"code": code, "name": name, "market": "上櫃", "type": t, "industry": "", "group": group})
    except:
        pass
    return stocks


def color_ret(val):
    if val is None or val == "" or val == "---" or val == "待觀察":
        return ""
    try:
        v = float(str(val).replace("%", ""))
        return "color: green; font-weight: bold" if v > 0 else "color: red; font-weight: bold"
    except:
        return ""


def color_dd(val):
    if val is None or val == "" or val == "---" or val == "待觀察":
        return ""
    try:
        v = float(str(val).replace("%", ""))
        return "color: red; font-weight: bold" if v < 0 else ""
    except:
        return ""


def group_selector(key_prefix):
    groups = list(INDUSTRY_GROUP.keys())
    selected = []
    cols = st.columns(6)
    for i, g in enumerate(groups):
        icon = GROUP_ICONS.get(g, "")
        with cols[i % 6]:
            if st.checkbox(icon + " " + g, key=key_prefix + "_" + g):
                selected.append(g)
    return selected


tab0, tab1, tab2, tab3 = st.tabs(["📖 使用說明", "🔍 每日警示掃描", "📊 批次回測", "🔬 個股回測"])

with tab0:
    st.markdown("## 系統使用說明")
    st.info(
        "資料說明：\n"
        "- 股價使用 Yahoo Finance 還原後收盤價（Adjusted Close）\n"
        "- 已自動處理股票分拆、除息、配股的價格調整\n"
        "- 回測年限最長15年（依各標的上市日期而定）\n"
        "- 除息日不會產生假觸發，回測結果更準確"
    )
    st.divider()
    st.markdown("### 什麼是滾動10日跌幅？")
    st.markdown("每個交易日，計算當天收盤價相較於 **10個交易日前** 收盤價的跌幅。當跌幅達到你設定的門檻，系統發出警示。")
    st.code("滾動10日報酬率 = (今天還原收盤 - 10天前還原收盤) / 10天前還原收盤 x 100%")
    st.divider()
    st.markdown("### 建議使用流程")
    st.markdown("""
**步驟一：批次回測**
- 選擇產業或ETF類別
- 找出哪些標的歷史上觸發後勝率高、報酬佳

**步驟二：個股回測**
- 針對感興趣的標的深入分析
- 比較不同觸發門檻（-5% 到 -20%）下的勝率與報酬
- 找出最適合該標的的進場門檻
- 用表D比較連續觸發第幾天進場效果最好
- 用表E了解持有期間最深會跌多少

**步驟三：每日警示掃描**
- 設定你選好的門檻與產業
- 每天收盤後掃描，找出當天觸發的標的
- 結合基本面判斷是否進場
    """)
    st.divider()
    st.markdown("### 核心表格說明")
    st.markdown("""
| 表格 | 用途 |
|------|------|
| 表A 勝率表 | 觸發後持有N天，收益為正的機率 |
| 表B 平均報酬表 | 平均每次觸發進場，持有N天的平均單筆獲利% |
| 表C 累積報酬表 | 所有觸發的單筆報酬加總（不除筆數），代表全部跟進的總損益佔單筆本金的倍數 |
| 表D 進場時機表 | 比較連續觸發第幾天進場效果最好 |
| 表E 平均最大回撤表 | 持有期間內最深跌幅的平均值，代表這個策略最痛的時候會痛多少 |
    """)
    st.divider()
    st.markdown("### 表B 與表C 的差異")
    st.markdown("""
假設某門檻一年觸發30次，每次都投入10000元：

- **表B（平均報酬%）** = 30筆報酬率加總 / 30 = 平均每筆賺/虧幾%
- **表C（累積報酬%）** = 30筆報酬率直接加總，不除以30

表C的數字會比表B大很多（次數越多差距越大），它代表的是「如果每次觸發都跟進，總損益相當於單筆本金的幾倍」，
而表B代表的是「平均每一筆操作的績效」。兩者用途不同：表B看單筆操作品質，表C看整體曝險後的總成果。
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
    """)
    st.divider()
    st.markdown("### 計算邏輯說明")
    st.markdown("""
- **觸發定義**：當日還原收盤價相較10個交易日前還原收盤價，跌幅達門檻即觸發
- **進場方式**：每個觸發日各自進場，連續觸發N天即有N筆紀錄
- **年度歸屬**：以觸發當天日期為準，報酬計算可跨年度
- **勝率**：觀察日當天報酬率大於0%的比例
- **平均報酬%**：所有觸發的單次報酬算術平均（表B）
- **累積報酬%**：所有觸發報酬直接加總，不除筆數（表C）
- **平均最大回撤%**：每筆觸發在持有期間內，相對進場價的最深跌幅，取平均（表E）
- **待觀察**：觸發後未滿觀察天數，資料不足，不計入統計
    """)
    st.divider()
    st.warning("本系統為輔助研究工具，不構成投資建議。歷史回測不代表未來績效，建議搭配基本面分析與產業趨勢判斷後再做決策。")

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
                results.append({
                    "產業群組": stock["group"],
                    "產業別": stock["industry"],
                    "代碼": code,
                    "名稱": stock["name"],
                    "滾動10日報酬率": "{:.2f}%".format(ret),
                    "數值": ret
                })
            progress.progress((i + 1) / total)
            time.sleep(0.15)
        progress.empty()
        status.empty()
        if results:
            df = pd.DataFrame(results).sort_values("數值").drop(columns=["數值"])
            st.error("共 " + str(len(results)) + " 檔觸發（門檻：" + str(threshold1) + "%）")
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button("📥 下載CSV", df.to_csv(index=False).encode("utf-8-sig"), "alert.csv", "text/csv")
        else:
            st.success("目前沒有標的觸發 " + str(threshold1) + "% 警示")

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
        st.info("共 " + str(total) + " 檔，開始回測（約需數分鐘）...")
        all_rows = []
        progress = st.progress(0)
        status = st.empty()
        for i, stock in enumerate(bt_list):
            code = stock["code"]
            status.text("回測中：" + code + " " + stock["name"] + "（" + str(i + 1) + "/" + str(total) + "）")
            prices = get_yahoo_history_15y(code)
            status.text("回測中：" + code + " " + stock["name"] + "（" + str(i + 1) + "/" + str(total) + "）資料筆數=" + str(len(prices)))
            result = run_full_backtest(prices, threshold2)
            if result:
                for year in sorted(result["yearly"].keys()):
                    y = result["yearly"][year]
                    row = {
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
                        if not rets:
                            row[str(h) + "天平均報酬%"] = "待觀察"
                            row[str(h) + "天累積報酬%"] = "待觀察"
                            row[str(h) + "天平均最大回撤%"] = "待觀察"
                        else:
                            row[str(h) + "天平均報酬%"] = "{:.2f}%".format(sum(rets) / len(rets))
                            row[str(h) + "天累積報酬%"] = "{:.2f}%".format(sum(rets))
                            row[str(h) + "天平均最大回撤%"] = "{:.2f}%".format(sum(dds) / len(dds))
                    all_rows.append(row)
            progress.progress((i + 1) / total)
            time.sleep(0.2)
        progress.empty()
        status.empty()
        if all_rows:
            df_bt = pd.DataFrame(all_rows)
            ret_cols = [c for c in df_bt.columns if "報酬%" in c]
            dd_cols = [c for c in df_bt.columns if "回撤%" in c]
            st.success("回測完成！")
            styled = df_bt.style.map(color_ret, subset=ret_cols)
            styled = styled.map(color_dd, subset=dd_cols)
            st.dataframe(styled, use_container_width=True, hide_index=True)
            st.download_button("📥 下載CSV", df_bt.to_csv(index=False).encode("utf-8-sig"), "backtest.csv", "text/csv")
        else:
            st.warning("沒有找到任何觸發紀錄")

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
                df_win, df_avg, df_cum, df_dd = build_summary_tables(prices)

            ret_cols_avg = [c for c in df_avg.columns if "報酬%" in c]
            ret_cols_cum = [c for c in df_cum.columns if "報酬%" in c]
            dd_cols = [c for c in df_dd.columns if "回撤%" in c]

            st.markdown("### 表A：各門檻 x 觀察天數 勝率")
            st.dataframe(df_win, use_container_width=True, hide_index=True)

            st.markdown("### 表B：各門檻 x 觀察天數 平均單次報酬%")
            st.dataframe(df_avg.style.map(color_ret, subset=ret_cols_avg), use_container_width=True, hide_index=True)

            st.markdown("### 表C：各門檻 x 觀察天數 累積報酬%（所有觸發報酬加總，不除筆數）")
            st.dataframe(df_cum.style.map(color_ret, subset=ret_cols_cum), use_container_width=True, hide_index=True)

            st.markdown("### 表E：各門檻 x 觀察天數 平均最大回撤%")
            st.caption("每筆觸發在持有期間內，相對進場價的最深跌幅，取平均")
            st.dataframe(df_dd.style.map(color_dd, subset=dd_cols), use_container_width=True, hide_index=True)

            st.info(
                "計算邏輯說明：\n"
                "- 每個觸發日各自進場，連續觸發N天即有N筆紀錄\n"
                "- 年度歸屬以觸發當天為準，報酬計算可跨年度\n"
                "- 勝率：觀察日當天報酬率大於0%的比例\n"
                "- 平均報酬%（表B）：所有觸發的單次報酬算術平均\n"
                "- 累積報酬%（表C）：所有觸發報酬直接加總，不除筆數，代表總曝險後的總成果\n"
                "- 平均最大回撤%（表E）：持有期間內最深跌幅的平均，代表最痛時刻的平均深度\n"
                "- 待觀察：觸發後未滿觀察天數，不計入統計"
            )

            thr_val = int(ref_threshold.replace("%", ""))
            df_yearly, result = build_yearly_table(prices, thr_val)
            if df_yearly is not None:
                st.markdown("### 年度明細（門檻 " + ref_threshold + "）")
                yearly_ret_cols = [c for c in df_yearly.columns if "報酬%" in c]
                yearly_dd_cols = [c for c in df_yearly.columns if "回撤%" in c]
                styled_yearly = df_yearly.style.map(color_ret, subset=yearly_ret_cols)
                styled_yearly = styled_yearly.map(color_dd, subset=yearly_dd_cols)
                st.dataframe(styled_yearly, use_container_width=True, hide_index=True)

            st.markdown("### 表D：進場時機比較（門檻 " + ref_threshold + "）")
            st.caption("比較連續觸發第幾天進場，對後續報酬的影響")
            df_timing = build_entry_timing_table(prices, thr_val)
            if df_timing is not None:
                timing_ret_cols = [c for c in df_timing.columns if "報酬%" in c]
                st.dataframe(
                    df_timing.style.map(color_ret, subset=timing_ret_cols),
                    use_container_width=True, hide_index=True
                )
                st.info(
                    "進場時機說明：\n"
                    "- 連續第1天：跌幅首次觸發門檻當天進場\n"
                    "- 連續第2天：已連續觸發2天，第2天進場\n"
                    "- 連續第3天以後：連續觸發3天以上每天進場\n"
                    "- 連續結束翌日：連續觸發結束後第一天進場（止跌確認）\n"
                    "樣本數為該時機的進場筆數"
                )
            else:
                st.warning("此門檻無觸發紀錄")

            if result:
                st.markdown("### 股價走勢＋觸發標記（門檻 " + ref_threshold + "）")
                dates = sorted(prices.keys())
                price_values = [prices[d] for d in dates]
                trigger_dates = set(result["trigger_dates"])
                trigger_x = [d for d in dates if d in trigger_dates]
                trigger_y = [prices[d] for d in trigger_x]
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=dates, y=price_values,
                    mode="lines", name="收盤價",
                    line=dict(color="#2196F3", width=1.5)
                ))
                fig.add_trace(go.Scatter(
                    x=trigger_x, y=trigger_y,
                    mode="markers",
                    name="觸發日（" + ref_threshold + "）",
                    marker=dict(color="red", size=8, symbol="circle")
                ))
                fig.update_layout(
                    height=500, xaxis_title="日期", yaxis_title="收盤價",
                    hovermode="x unified",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02)
                )
                st.plotly_chart(fig, use_container_width=True)
                with st.expander("查看所有觸發日明細"):
                    triggered = result["triggers"]
                    df_trig = pd.DataFrame([{
                        "觸發日": t["date"],
                        "基準日": t["base_date"],
                        "基準價": t["base_price"],
                        "觸發當日收盤": t["curr_price"],
                        "滾動10日報酬率": "{:.2f}%".format(t["return"])
                    } for t in triggered])
                    st.dataframe(df_trig, use_container_width=True, hide_index=True)
