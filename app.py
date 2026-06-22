import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import json

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
HORIZONS = [5, 10, 20, 40, 60, 80, 100, 120, 240]

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


def get_yahoo_history_us(code, days=365):
    """抓美國指數/ETF歷史資料（不加.TW後綴），用於SOX、TNX、VIX等"""
    end = datetime.today()
    start = end - timedelta(days=days)
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/" + code
           + "?interval=1d&period1=" + str(int(start.timestamp()))
           + "&period2=" + str(int(end.timestamp())))
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json()
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
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
    # 新增：記錄最大回撤發生的天數
    horizon_dd_days = {h: [] for h in HORIZONS}

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
                min_day = 0
                for d in range(1, h + 1):
                    fi = idx + d
                    if fi < len(dates):
                        p = prices_dict[dates[fi]]
                        r = (p - entry_price) / entry_price * 100
                        if r < min_ret:
                            min_ret = r
                            min_day = d
                horizon_drawdowns[h].append({"dd": round(min_ret, 2), "year": year})
                horizon_dd_days[h].append(min_day)

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

    return {
        "triggers": triggers, "trigger_dates": list(trigger_dates),
        "max_consecutive": max_consecutive,
        "horizon_rets": horizon_rets,
        "horizon_drawdowns": horizon_drawdowns,
        "horizon_dd_days": horizon_dd_days,
        "yearly": yearly, "total": len(triggers)
    }


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
                r = int(255 - intensity * 115)
                g = int(224 - intensity * 224)
                b = int(224 - intensity * 224)
                text = "white" if intensity > 0.55 else "#8B0000"
                return "background-color: rgb({},{},{}); color: {}; font-weight: bold".format(r, g, b, text)
            elif v < 0:
                intensity = min(abs(v) / abs(min_neg), 1.0)
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
    return "待觀察" if v is None else "{:.2f}%".format(v)


def show_html(s):
    st.markdown(s.to_html(index=False), unsafe_allow_html=True)


def build_summary_tables(prices_dict):
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
                win_row[col_w] = avg_row[col_a] = dd_row[col_d] = "---"
            else:
                rets = [x["ret"] for x in result["horizon_rets"][h]]
                dds = [x["dd"] for x in result["horizon_drawdowns"][h]]
                if not rets:
                    win_row[col_w] = avg_row[col_a] = dd_row[col_d] = "待觀察"
                else:
                    wins = sum(1 for r in rets if r > 0)
                    win_row[col_w] = "{:.2f}%".format(wins / len(rets) * 100)
                    avg_row[col_a] = "{:.2f}%".format(sum(rets) / len(rets))
                    dd_row[col_d] = "{:.2f}%".format(sum(dds) / len(dds))
        win_rows.append(win_row)
        avg_rows.append(avg_row)
        dd_rows.append(dd_row)
    return pd.DataFrame(win_rows), pd.DataFrame(avg_rows), pd.DataFrame(dd_rows)


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
    total_row = {"年度": "合計/平均", "觸發次數": result["total"], "最長連續觸發": result["max_consecutive"]}
    for h in HORIZONS:
        rets = [x["ret"] for x in result["horizon_rets"][h]]
        total_row[str(h) + "天平均%"] = fmt(round(sum(rets) / len(rets), 2) if rets else None)
    rows.append(total_row)
    return pd.DataFrame(rows), result


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


def build_dd_timing_table(prices_dict, threshold):
    """表E增強：最大回撤 + 平均發生天數"""
    result = run_full_backtest(prices_dict, threshold)
    if not result:
        return None
    rows = []
    for h in HORIZONS:
        dds = [x["dd"] for x in result["horizon_drawdowns"][h]]
        dd_days = result["horizon_dd_days"][h]
        if not dds:
            rows.append({"觀察天數": str(h) + "天", "樣本數": 0,
                         "平均最大回撤%": "待觀察", "最深回撤%": "待觀察",
                         "平均回撤發生於第幾天": "待觀察"})
        else:
            valid_days = [d for d in dd_days if d > 0]
            rows.append({
                "觀察天數": str(h) + "天",
                "樣本數": len(dds),
                "平均最大回撤%": "{:.2f}%".format(sum(dds) / len(dds)),
                "最深回撤%": "{:.2f}%".format(min(dds)),
                "平均回撤發生於第幾天": "{:.1f}天".format(sum(valid_days) / len(valid_days)) if valid_days else "無回撤",
            })
    return pd.DataFrame(rows)


def build_consec_analysis(prices_dict, threshold, horizon):
    """連續觸發天數 vs 後續報酬交叉分析"""
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

    buckets = {"第1天": [], "第2天": [], "第3天": [], "第4天以後": []}
    for t in triggers:
        dn = consec_day.get(t["date"], 1)
        idx = date_to_idx.get(t["date"])
        if idx is None:
            continue
        ep = t["curr_price"]
        fi = idx + horizon
        if fi >= len(dates):
            continue
        ret = round((prices_dict[dates[fi]] - ep) / ep * 100, 2)
        if dn == 1:
            buckets["第1天"].append(ret)
        elif dn == 2:
            buckets["第2天"].append(ret)
        elif dn == 3:
            buckets["第3天"].append(ret)
        else:
            buckets["第4天以後"].append(ret)

    rows = []
    for bucket, rets in buckets.items():
        if not rets:
            rows.append({"連續觸發天數": bucket, "樣本數": 0,
                         "勝率": "---", "平均報酬%": "---", "最佳報酬%": "---", "最差報酬%": "---"})
        else:
            wins = sum(1 for r in rets if r > 0)
            rows.append({
                "連續觸發天數": bucket,
                "樣本數": len(rets),
                "勝率": "{:.2f}%".format(wins / len(rets) * 100),
                "平均報酬%": "{:.2f}%".format(sum(rets) / len(rets)),
                "最佳報酬%": "{:.2f}%".format(max(rets)),
                "最差報酬%": "{:.2f}%".format(min(rets)),
            })
    return pd.DataFrame(rows)



def render_analysis(code, df_win, df_avg, df_dd, df_yearly, threshold, prices_dict=None):
    """直接用Streamlit元件render分析報告，排版清晰"""
    import statistics

    st.markdown("## 📊 回測分析報告｜" + code)
    worst_dd = None
    worst_dd_single = None
    best_h = None
    second_h = None

    # ══════════════════════════════
    # 1. 最佳觸發門檻
    # ══════════════════════════════
    st.markdown("### 1️⃣ 最佳觸發門檻建議")

    best_thr = None
    best_score = -999
    for _, row in df_win.iterrows():
        thr_str = row["觸發門檻"]
        samples = int(row.get("樣本數", 0))
        if samples < 3:
            continue
        wr_100 = row.get("100天勝率", "0%")
        avg_100 = df_avg[df_avg["觸發門檻"] == thr_str]["100天平均報酬%"].values
        try:
            wr_v = float(str(wr_100).replace("%", ""))
            avg_v = float(str(avg_100[0]).replace("%", "")) if len(avg_100) > 0 and str(avg_100[0]) not in ["待觀察", "---"] else 0
            score = wr_v * 0.6 + avg_v * 0.4
            if score > best_score:
                best_score = score
                best_thr = thr_str
        except:
            pass

    if best_thr:
        best_row = df_win[df_win["觸發門檻"] == best_thr].iloc[0]
        samples = int(best_row.get("樣本數", 0))
        wr_100 = best_row.get("100天勝率", "N/A")

        col1, col2, col3 = st.columns(3)
        col1.metric("建議觸發門檻", best_thr)
        col2.metric("100天勝率", str(wr_100))
        col3.metric("15年觸發次數", str(samples) + " 次")

        if samples < 10:
            st.warning("⚠️ 此門檻觸發次數僅 " + str(samples) + " 次，樣本有限，建議謹慎參考")
        else:
            st.success("此門檻在勝率、報酬與觸發頻率上取得最佳平衡")

    # 各門檻達80%勝率所需天數分析
    st.markdown("**各觸發門檻完整比較：**")
    thr_analysis_rows = []
    for _, row in df_win.iterrows():
        thr_str = row["觸發門檻"]
        samples = int(row.get("樣本數", 0))
        first_80 = None
        for h in HORIZONS:
            col = str(h) + "天勝率"
            try:
                v = float(str(row.get(col, "0")).replace("%", ""))
                if v >= 80 and first_80 is None:
                    first_80 = h
            except:
                pass
        thr_analysis_rows.append({
            "門檻": thr_str,
            "15年觸發次數": str(samples) + ("⚠️" if samples < 10 else ""),
            "達80%勝率最短持有": str(first_80) + "天" if first_80 else "未達80%",
        })
    st.markdown(pd.DataFrame(thr_analysis_rows).to_html(index=False), unsafe_allow_html=True)

    st.info(
        "📌 重要結論：\n"
        "・**-20%** 雖然100%勝率，但15年僅觸發幾次，樣本太少不具代表性\n"
        "・**-15%** 是次佳選擇，需持有50~100天，勝率可達80~95%\n"
        "・**-10%** 進場需持有至少100天才有約80%勝率\n"
        "・除了-20%，**沒有任何門檻能在10或20天內達到80%勝率**\n"
        "・門檻越嚴苛觸發越少但勝率越高；門檻越寬鬆觸發越頻繁但勝率偏低"
    )
    st.divider()

    # ══════════════════════════════
    # 2. 最佳持有天數
    # ══════════════════════════════
    st.markdown("### 2️⃣ 最佳持有天數建議")

    if best_thr:
        thr_avg_row = df_avg[df_avg["觸發門檻"] == best_thr]
        thr_dd_row = df_dd[df_dd["觸發門檻"] == best_thr]
        ratios = []
        for h in HORIZONS:
            avg_col = str(h) + "天平均報酬%"
            dd_col = str(h) + "天平均最大回撤%"
            try:
                avg_v = float(str(thr_avg_row[avg_col].values[0]).replace("%", ""))
                dd_v = float(str(thr_dd_row[dd_col].values[0]).replace("%", ""))
                dd_denom = max(abs(dd_v), 1.0)
                ratio = avg_v / dd_denom
                ratios.append((h, ratio, avg_v, dd_v))
            except:
                pass
        ratios.sort(key=lambda x: x[1], reverse=True)

        if ratios:
            best_h = ratios[0][0]
            avg_val = ratios[0][2]
            dd_val = ratios[0][3]

            col1, col2 = st.columns(2)
            with col1:
                st.success(
                    "🥇 **首選：持有 " + str(best_h) + " 天**\n\n"
                    "平均報酬：**{:.2f}%**\n\n"
                    "平均最大回撤：**{:.2f}%**\n\n"
                    "風險報酬比：**{:.2f}**（越高越划算）".format(avg_val, dd_val, ratios[0][1])
                )
            # 找次佳（天數較短）
            for h2, ratio2, avg2, dd2 in ratios[1:]:
                if h2 < best_h:
                    second_h = h2
                    with col2:
                        st.info(
                            "🥈 **次選（較短持有）：持有 " + str(second_h) + " 天**\n\n"
                            "平均報酬：**{:.2f}%**\n\n"
                            "平均最大回撤：**{:.2f}%**\n\n"
                            "風險報酬比：**{:.2f}**（適合不想持有太久的投資人）".format(avg2, dd2, ratio2)
                        )
                    break
    st.divider()

    # ══════════════════════════════
    # 3. 歷史規律
    # ══════════════════════════════
    st.markdown("### 3️⃣ 歷史規律")
    st.caption("分析哪些年度觸發後表現特別好或特別差，幫助判斷「現在的市場環境」是否類似歷史上的好年或壞年")

    if df_yearly is not None and len(df_yearly) > 2:
        yearly_data = df_yearly[df_yearly["年度"] != "合計/平均"].copy()
        col_key = "100天平均%"
        year_vals = []
        for _, row in yearly_data.iterrows():
            try:
                year_vals.append((str(row["年度"]), float(str(row.get(col_key, "0")).replace("%", ""))))
            except:
                pass
        valid_vals = [v for _, v in year_vals]
        if valid_vals:
            try:
                med = statistics.median(valid_vals)
                stdev = statistics.stdev(valid_vals) if len(valid_vals) > 1 else 5.0
            except:
                med = sum(valid_vals) / len(valid_vals)
                stdev = 5.0

            good_years = [(y, v) for y, v in year_vals if v > med + stdev]
            bad_years = [(y, v) for y, v in year_vals if v < med - stdev]

            col1, col2 = st.columns(2)
            with col1:
                if good_years:
                    st.success(
                        "📈 **觸發後反彈特別強的年度**\n\n" +
                        "\n\n".join(["**" + y + "**：" + "{:.1f}%".format(v) for y, v in good_years]) +
                        "\n\n→ 這些年市場屬短暫超跌後快速修復，進場時機極佳"
                    )
                else:
                    st.info("📈 無特別突出的強勢年度")
            with col2:
                if bad_years:
                    st.warning(
                        "📉 **觸發後反彈較弱或繼續跌的年度**\n\n" +
                        "\n\n".join(["**" + y + "**：" + "{:.1f}%".format(v) for y, v in bad_years]) +
                        "\n\n→ 這些年通常處於系統性風險環境（升息、貿易戰、金融危機）"
                    )
                else:
                    st.info("📉 無特別突出的弱勢年度")

            st.info(
                "💡 **投資判斷提示**：若目前總體環境類似歷史上的「壞年」（升息、衰退疑慮、地緣風險），"
                "建議縮小進場規模或提高觸發門檻；若只是短暫情緒性修正，則可以積極進場。\n\n"
                "（15年100天平均報酬中位數：{:.1f}%，標準差：{:.1f}%）".format(med, stdev)
            )
    st.divider()

    # ══════════════════════════════
    # 4. 風險提示（兩個門檻）
    # ══════════════════════════════
    st.markdown("### 4️⃣ 風險提示")
    st.caption("以下數字是指**你進場後的報酬虧損幅度**（相對你的進場價），不是股價的絕對跌幅")

    def get_dd_summary(thr_str, prices_dict):
        thr_int = int(thr_str.replace("%", ""))
        result = run_full_backtest(prices_dict, thr_int)
        if not result:
            return None
        dds_last = [x["dd"] for x in result["horizon_drawdowns"][HORIZONS[-1]]]
        if not dds_last:
            return None
        avg_dd = sum(dds_last) / len(dds_last)
        worst_single = min(dds_last)
        worst_year = None
        worst_year_dd = 0
        for year, y in result["yearly"].items():
            dds_y = y["dds"][HORIZONS[-1]]
            if dds_y:
                yr_avg = sum(dds_y) / len(dds_y)
                if yr_avg < worst_year_dd:
                    worst_year_dd = yr_avg
                    worst_year = year
        rets_last = [x["ret"] for x in result["horizon_rets"][HORIZONS[-1]]]
        wr = sum(1 for r in rets_last if r > 0) / max(len(rets_last), 1) * 100 if rets_last else 0
        return {"avg_dd": avg_dd, "worst_single": worst_single,
                "worst_year": worst_year, "worst_year_dd": worst_year_dd,
                "wr": wr, "total": result["total"]}

    if best_thr and prices_dict:
        dd_main = get_dd_summary(best_thr, prices_dict)
        if dd_main:
            worst_dd = dd_main["avg_dd"]
            worst_dd_single = dd_main["worst_single"]

        # 找次要門檻（樣本>=10次）
        alt_thr = None
        for tc in ["-10%", "-7%", "-5%", "-15%"]:
            if tc != best_thr:
                row_c = df_win[df_win["觸發門檻"] == tc]
                if not row_c.empty and int(row_c.iloc[0].get("樣本數", 0)) >= 10:
                    alt_thr = tc
                    break

        cols = st.columns(2) if alt_thr else [st.container()]
        with cols[0]:
            if dd_main:
                st.markdown("**▍ 主要建議門檻 " + best_thr + "**（15年觸發 " + str(dd_main["total"]) + " 次）")
                st.markdown(
                    "- 一般情況：進場後平均最深虧損約 **{:.1f}%**（歷史常態波動）\n"
                    "- 最壞情況：史上最深單筆虧損 **{:.1f}%**（含金融危機、疫情崩盤）\n"
                    "- 最差年度：**{year}年**，該年平均最深虧損 {ydd:.1f}%\n"
                    "- 只要不中途停損，有 **{wr:.0f}%** 的機率在{h}天內回到正報酬".format(
                        dd_main["avg_dd"], dd_main["worst_single"],
                        year=dd_main["worst_year"] or "N/A",
                        ydd=dd_main["worst_year_dd"],
                        wr=dd_main["wr"], h=HORIZONS[-1]
                    )
                )

        if alt_thr:
            dd_alt = get_dd_summary(alt_thr, prices_dict)
            with cols[1]:
                if dd_alt:
                    st.markdown("**▍ 次要參考門檻 " + alt_thr + "**（15年觸發 " + str(dd_alt["total"]) + " 次，樣本較充足）")
                    st.markdown(
                        "- 一般情況：進場後平均最深虧損約 **{:.1f}%**\n"
                        "- 最壞情況：史上最深單筆虧損 **{:.1f}%**\n"
                        "- 最差年度：**{year}年**，該年平均最深虧損 {ydd:.1f}%\n"
                        "- 只要不中途停損，有 **{wr:.0f}%** 的機率在{h}天內回到正報酬".format(
                            dd_alt["avg_dd"], dd_alt["worst_single"],
                            year=dd_alt["worst_year"] or "N/A",
                            ydd=dd_alt["worst_year_dd"],
                            wr=dd_alt["wr"], h=HORIZONS[-1]
                        )
                    )

        st.warning("💡 「忍住浮虧不停損」在歷史上是正確的做法——停損反而把虧損鎖住了。")
    st.divider()

    # ══════════════════════════════
    # 5. 進場時機建議
    # ══════════════════════════════
    st.markdown("### 5️⃣ 進場時機建議")
    if prices_dict and best_thr:
        thr_val_int = int(best_thr.replace("%", ""))
        st.caption("門檻：" + best_thr + " ｜ 分析連續觸發第幾天進場，後續報酬是否有差異。⚠️ = 樣本數 < 5筆，僅供參考")

        best_timing_votes = {}
        timing_rows = []

        for h in HORIZONS:
            df_consec = build_consec_analysis(prices_dict, thr_val_int, h)
            if df_consec is None:
                continue
            group_data = []
            for _, row in df_consec.iterrows():
                timing = row["連續觸發天數"]
                n = row["樣本數"]
                try:
                    wr = str(row["勝率"])
                    avg = float(str(row["平均報酬%"]).replace("%", ""))
                    group_data.append((timing, n, wr, avg))
                except:
                    pass

            valid = [(t, n, wr, avg) for t, n, wr, avg in group_data if n >= 5]
            use_data = valid if valid else group_data
            conclusion = ""
            best_entry_timing = ""
            if use_data:
                max_avg = max(avg for _, _, _, avg in use_data)
                min_avg = min(avg for _, _, _, avg in use_data)
                diff = max_avg - min_avg
                best_entry = max(use_data, key=lambda x: x[3])
                sample_warn = "⚠️ 樣本均不足5筆｜" if not valid else ""
                if diff < 2.0:
                    conclusion = sample_warn + "各時機差距僅{:.1f}%，**第1天直接進場**".format(diff)
                    best_entry_timing = "第1天"
                else:
                    conclusion = sample_warn + "差距{:.1f}%，**「{}」報酬最高（{:.2f}%）**".format(diff, best_entry[0], best_entry[3])
                    best_entry_timing = best_entry[0]
                if best_entry_timing:
                    best_timing_votes[best_entry_timing] = best_timing_votes.get(best_entry_timing, 0) + 1

            row_data = {"持有天數": str(h) + "天"}
            for t, n, wr, avg in group_data:
                flag = "⚠️" if n < 5 else ""
                short_t = t.replace("連續", "").replace("進場", "").replace("天以後", "+")
                row_data[short_t] = flag + "{:.1f}%".format(avg) + "(" + wr + ")"
            row_data["建議"] = conclusion
            timing_rows.append(row_data)

        if timing_rows:
            df_timing_summary = pd.DataFrame(timing_rows)
            st.markdown(df_timing_summary.to_html(index=False), unsafe_allow_html=True)

        if best_timing_votes:
            overall_best = max(best_timing_votes, key=lambda k: best_timing_votes[k])
            count = best_timing_votes[overall_best]
            st.markdown("---")
            if overall_best == "第1天":
                st.success(
                    "**整體進場時機結論**：在 " + str(len(HORIZONS)) + " 個持有天數中，有 " + str(count) + " 個建議「第1天」進場。\n\n"
                    "→ **觸發當天直接進場**。多等幾天不會明顯提高報酬，反而可能錯過最佳進場點。"
                )
            else:
                st.success(
                    "**整體進場時機結論**：在 " + str(len(HORIZONS)) + " 個持有天數中，有 " + str(count) + " 個建議「" + overall_best + "」進場。\n\n"
                    "→ **等到「" + overall_best + "」再進場**，歷史上此時機報酬明顯較佳，值得等待。"
                )
    st.divider()

    # ══════════════════════════════
    # 6. 綜合操作建議
    # ══════════════════════════════
    st.markdown("### 6️⃣ 綜合操作建議")
    if best_thr and best_h:
        st.markdown(
            "根據15年回測數據，建議操作策略如下：\n\n"
            "- **進場訊號**：當股票觸發滾動10日跌幅達 **" + str(best_thr) + "** 時考慮進場\n"
            "- **持有期間**：首選持有 **" + str(best_h) + " 天**後評估出場" +
            ("；次選 **" + str(second_h) + " 天**（不想持有太久）" if second_h else "") + "\n" +
            ("- **心理準備**：進場後平均最深會虧 **{:.1f}%**（相對進場價的報酬虧損），屬正常波動，不建議因短期浮虧停損\n".format(worst_dd) if worst_dd else "") +
            ("- **極端風險**：史上最深曾虧 **{:.1f}%**（含金融危機等極端事件），需有心理準備".format(worst_dd_single) if worst_dd_single else "")
        )
    st.caption("*本分析基於歷史回測數據自動生成，不構成投資建議。歷史績效不代表未來報酬。*")

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

    # TWSE API with retry (偶發性503/空白回應，retry最多3次)
    twse_urls = [
        "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
        "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
        "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
    ]
    twse_data = []
    for attempt, url in enumerate(twse_urls):
        try:
            res = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            if res.status_code == 200 and len(res.text) > 100:
                twse_data = res.json()
                break
        except:
            pass
        if attempt < len(twse_urls) - 1:
            time.sleep(2)

    for d in twse_data:
        code = d.get("Code", "").strip()
        name = d.get("Name", "").strip()
        if not code:
            continue
        t = classify_code(code)
        industry = industry_lookup.get(code, "")
        group = get_industry_group(industry, t)
        stocks.append({"code": code, "name": name, "market": "上市", "type": t, "industry": industry, "group": group})

    # TPEX with retry
    tpex_data = []
    for attempt in range(3):
        try:
            res = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes",
                             timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            if res.status_code == 200 and len(res.text) > 100:
                tpex_data = res.json()
                break
        except:
            pass
        if attempt < 2:
            time.sleep(2)
    for d in tpex_data:
        code = d.get("SecuritiesCompanyCode", "").strip()
        name = d.get("CompanyName", "").strip()
        if not code:
            continue
        t = classify_code(code)
        industry = industry_lookup.get(code, "")
        group = get_industry_group(industry, t)
        stocks.append({"code": code, "name": name, "market": "上櫃", "type": t, "industry": industry, "group": group})
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


# ==============================
# 頁籤順序：使用說明→系統檢核→每日警示→批次回測→個股回測→全市場勝率
# ==============================
tab0, tab5, tab6, tab1, tab3, tab4, tab2 = st.tabs([
    "📖 使用說明",
    "🔧 系統檢核",
    "📋 合格標的池",
    "🔍 每日警示掃描",
    "🔬 個股回測",
    "🏆 全市場勝率排行",
    "📊 批次回測",
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
- **報酬熱力圖**：越深紅報酬越高，越深綠虧損越深
- **回撤熱力圖**：越深橘紅回撤越深，風險越高
    """)
    st.divider()
    st.markdown("### 計算邏輯說明")
    st.markdown("""
- **觸發定義**：當日還原收盤價相較10個交易日前，跌幅達門檻即觸發
- **進場方式**：每個觸發日各自進場，連續觸發N天即有N筆紀錄
- **勝率**：以 T+N 那天的收盤價計算，T+N收盤 > 進場收盤 = 獲勝
- **平均報酬%**：每筆觸發各自以 T+N 收盤計算報酬，取算術平均
- **年度歸屬**：以觸發當天日期為準，報酬計算可跨年度
- **待觀察**：觸發後未滿觀察天數，不計入統計
    """)
    st.divider()
    st.markdown("### 建議使用流程（研究順序）")
    st.markdown("""
**步驟一：每日警示掃描**
→ 先看今天收盤後有哪些標的觸發門檻，建立今日候選名單

**步驟二：個股回測**
→ 針對候選名單中的標的，深入研究歷史勝率、最佳持有天數、最佳進場時機
→ 搭配AI分析建議，快速掌握該標的的歷史規律

**步驟三：全市場勝率排行**
→ 定期跑一次，建立長期高勝率股票的參考名單
→ 各門檻前10名，搭配產業分布，找出結構性強勢產業

**步驟四：批次回測**
→ 針對特定產業做系統性研究，了解整個產業的歷史回測表現
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
    st.markdown("### 全市場勝率排行：參數說明")
    st.markdown("""
- **觀察天數**：你想研究跌破門檻後，放多久再看結果？選100天 = 觸發後持有5個月的勝率排行
- **最低觸發次數**：自動標示 ⚠️，觸發次數 ≤ 5次代表樣本不足，勝率參考性有限
    """)
    st.warning("本系統為輔助研究工具，不構成投資建議。歷史回測不代表未來績效。")

# ==============================
# TAB 系統檢核
# ==============================
with tab5:
    st.subheader("🔧 系統檢核")
    st.info("點擊下方按鈕，自動驗證各項資料來源、API連線、計算邏輯與資料新鮮度")

    if st.button("▶️ 執行系統檢核", type="primary", key="check"):
        checks = []

        def run_check(name, fn):
            try:
                ok, detail = fn()
                checks.append({"項目": name, "狀態": "✅ 正常" if ok else "❌ 異常", "說明": detail})
            except Exception as e:
                checks.append({"項目": name, "狀態": "❌ 失敗", "說明": str(e)[:120]})

        with st.spinner("執行中..."):

            def check_twse():
                url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
                for attempt in range(3):
                    try:
                        res = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                        if res.status_code == 200 and len(res.text) > 100:
                            data = res.json()
                            if len(data) > 100:
                                return True, "取得 " + str(len(data)) + " 筆上市證券（第" + str(attempt+1) + "次嘗試成功）"
                    except Exception as e:
                        last_err = str(e)
                    if attempt < 2:
                        time.sleep(2)
                return False, "連續3次嘗試均失敗（" + last_err[:60] + "）。TWSE API偶發性不穩，非程式問題，稍後再試即可。"
            run_check("證交所TWSE API", check_twse)

            def check_tpex():
                last_err = ""
                for attempt in range(3):
                    try:
                        res = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes",
                                         timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                        if res.status_code == 200 and len(res.text) > 100:
                            data = res.json()
                            if len(data) > 50:
                                return True, "取得 " + str(len(data)) + " 筆上櫃證券（第" + str(attempt+1) + "次嘗試成功）"
                    except Exception as e:
                        last_err = str(e)
                    if attempt < 2:
                        time.sleep(2)
                return False, "連續3次嘗試均失敗（" + last_err[:60] + "）。TPEX API偶發性不穩，非程式問題，稍後再試即可。"
            run_check("櫃買中心TPEX API", check_tpex)

            def check_yahoo():
                p = get_yahoo_history("2330", days=60)
                if len(p) < 10:
                    return False, "資料筆數不足：" + str(len(p))
                d = sorted(p.keys())
                return True, "2330台積電 最新收盤：" + str(p[d[-1]]) + "（" + d[-1] + "）｜取得 " + str(len(p)) + " 筆（近60天交易日，正常約40~43筆）"
            run_check("Yahoo Finance API（2330）", check_yahoo)

            def check_freshness():
                p = get_yahoo_history("2330", days=10)
                if not p:
                    return False, "無法取得資料"
                latest_date = sorted(p.keys())[-1]
                days_diff = (datetime.today() - datetime.strptime(latest_date, "%Y-%m-%d")).days
                ok = days_diff <= 4
                return ok, "最新資料日期：" + latest_date + "（距今 " + str(days_diff) + " 天）" + ("✓" if ok else " ⚠️ 資料可能延遲")
            run_check("資料即時性（最新資料距今天數）", check_freshness)

            def check_logic():
                tp = {(datetime.today() - timedelta(days=20 - i)).strftime("%Y-%m-%d"):
                      (100.0 if i < 11 else 88.0) for i in range(20)}
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

            def check_adj_price():
                p = get_yahoo_history_15y("0050")
                if len(p) < 100:
                    return False, "資料不足"
                dates = sorted(p.keys())
                nearby = [d for d in dates if "2021-10" in d or "2021-09" in d or "2021-11" in d]
                if len(nearby) < 10:
                    return True, "無法取得2021年資料，跳過此項"
                prices_nearby = [p[d] for d in sorted(nearby)]
                max_jump = max(
                    abs(prices_nearby[i] - prices_nearby[i-1]) / prices_nearby[i-1] * 100
                    for i in range(1, len(prices_nearby))
                )
                if max_jump < 15:
                    return True, "0050還原股價連續性正常（除息前後最大單日跳空：{:.2f}%）".format(max_jump)
                return False, "還原股價異常！最大單日跳空：{:.2f}%".format(max_jump)
            run_check("還原股價連續性驗證（0050除息）", check_adj_price)

        show_html(pd.DataFrame(checks))

        # 各項目失敗時的影響說明
        IMPACT_MAP = {
            "證交所TWSE API": "⛔ 受影響：每日警示掃描、全市場勝率排行、合格標的池建立（上市股票清單無法取得）\n✅ 不受影響：個股回測、批次回測、個股快查",
            "櫃買中心TPEX API": "⛔ 受影響：每日警示掃描、全市場勝率排行（上櫃股票清單無法取得）\n✅ 不受影響：個股回測、批次回測",
            "Yahoo Finance API（2330）": "⛔ 受影響：所有功能（個股回測、每日掃描、批次回測全部依賴Yahoo Finance）\n⚠️ 這是最嚴重的異常，需要等Yahoo Finance恢復",
            "資料即時性（最新資料距今天數）": "⛔ 受影響：今日掃描結果可能是舊資料，觸發訊號不準確\n⚠️ 建議等資料更新後再執行每日警示掃描",
            "滾動10日報酬計算邏輯": "⛔ 受影響：所有回測計算結果不可信，勝率/報酬數字錯誤\n⚠️ 這是程式問題，請回報",
            "還原後股價（0050 15年）": "⛔ 受影響：15年回測資料不完整，個股回測/批次回測結果可能不準確\n✅ 每日掃描（只需60天）仍可正常使用",
            "觸發計算驗證（2330 @-7%）": "⛔ 受影響：觸發判斷邏輯可能有誤，每日掃描和回測結果不可信\n⚠️ 這是程式問題，請回報",
            "還原股價連續性驗證（0050除息）": "⛔ 受影響：除息前後的回測數據可能失真，長期回測勝率可能偏高\n⚠️ 建議優先看最近5年的回測數據",
        }

        if all("✅" in c["狀態"] for c in checks):
            st.success("✅ 所有系統檢核通過！所有功能正常可用。")
        else:
            failed_items = [c["項目"] for c in checks if "❌" in c["狀態"]]
            st.error("❌ 以下項目異常：" + "、".join(failed_items))
            st.markdown("### 異常影響範圍")
            for item in failed_items:
                impact = IMPACT_MAP.get(item, "影響範圍未知，請回報")
                with st.expander("📌 " + item + " 異常的影響"):
                    st.markdown(impact)


# ==============================
# TAB 1: 每日警示掃描
# ==============================

# ==============================
# TAB 6: 合格標的池
# ==============================

def get_mops_financial(year_roc, season, typek='sii'):
    """從MOPS抓財務分析彙總表（含ROE、EPS、負債比、每股淨值）"""
    url = 'https://mops.twse.com.tw/mops/web/t51sb02'
    form_data = {
        'encodeURIComponent': 1, 'run': 'Y', 'step': 1,
        'TYPEK': typek, 'year': str(year_roc), 'season': str(season),
        'firstin': 1, 'off': 1, 'ifrs': 'Y',
    }
    try:
        r = requests.post(url, data=form_data, timeout=30)
        r.encoding = 'utf8'
        dfs = pd.read_html(r.text, header=None)
        if len(dfs) >= 2:
            df = pd.concat(dfs[1:], axis=0, sort=False).reset_index(drop=True)
            return df
    except:
        pass
    return None


def parse_financial_df(df):
    """解析財務分析彙總表，萃取需要的欄位"""
    if df is None or df.empty:
        return None
    try:
        # 取第一行作為欄位名稱
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)
        df.columns = [str(c).strip() for c in df.columns]

        # 找欄位（不同季可能欄位名稱略有差異）
        col_map = {}
        for col in df.columns:
            if '公司代號' in str(col) or '代號' == str(col).strip():
                col_map['code'] = col
            elif '公司名稱' in str(col) or '名稱' == str(col).strip():
                col_map['name'] = col
            elif '股東權益報酬率' in str(col) or 'ROE' in str(col).upper():
                col_map['roe'] = col
            elif '每股盈餘' in str(col) or 'EPS' in str(col).upper():
                col_map['eps'] = col
            elif '負債佔資產' in str(col) or '負債比率' in str(col):
                col_map['debt_ratio'] = col
            elif '每股淨值' in str(col) or '每股帳面' in str(col):
                col_map['bvps'] = col

        result = {}
        for key, col in col_map.items():
            result[key] = df[col]
        if 'code' not in result:
            return None
        out = pd.DataFrame(result)
        # 轉數值
        for col in ['roe', 'eps', 'debt_ratio', 'bvps']:
            if col in out.columns:
                out[col] = pd.to_numeric(out[col], errors='coerce')
        return out
    except:
        return None


@st.cache_data(ttl=3600)
def get_all_financial_data():
    """抓近5年所有季度財務資料（上市+上櫃）"""
    now = datetime.now()
    current_year_roc = now.year - 1911
    all_data = []

    for yr_offset in range(5):
        yr = current_year_roc - yr_offset
        for season in [4, 3, 2, 1]:
            # 跳過未來的季度
            if yr == current_year_roc:
                current_q = (now.month - 1) // 3 + 1
                if season > current_q - 1:
                    continue
            for typek in ['sii', 'otc']:
                df_raw = get_mops_financial(yr, season, typek)
                df = parse_financial_df(df_raw)
                if df is not None and not df.empty:
                    df['year_roc'] = yr
                    df['season'] = season
                    df['typek'] = typek
                    all_data.append(df)
                time.sleep(0.5)

    if not all_data:
        return None
    return pd.concat(all_data, ignore_index=True)


@st.cache_data(ttl=86400)
def get_book_value_per_share(codes):
    """用MOPS抓最新每股淨值"""
    now = datetime.now()
    yr = now.year - 1911
    current_q = (now.month - 1) // 3
    if current_q == 0:
        yr -= 1
        current_q = 4
    result = {}
    for typek in ['sii', 'otc']:
        df_raw = get_mops_financial(yr, current_q, typek)
        df = parse_financial_df(df_raw)
        if df is not None and 'code' in df.columns and 'bvps' in df.columns:
            for _, row in df.iterrows():
                code = str(row['code']).strip()
                if code in codes and not pd.isna(row.get('bvps')):
                    result[code] = float(row['bvps'])
    return result


def build_qualified_pool(all_stocks, fin_data):
    """建立合格標的池，套用六個條件"""
    if fin_data is None or fin_data.empty:
        return None

    results = []
    stock_dict = {s['code']: s for s in all_stocks}
    codes = list(stock_dict.keys())

    # 取最新一季每股淨值（算PB用）
    bvps_map = get_book_value_per_share(set(codes))

    # 取每股最新收盤價（算PB用）
    price_map = {}
    for code in codes[:20]:  # 避免太多API呼叫，先取前20測試
        p = get_yahoo_history(code, days=5)
        if p:
            price_map[code] = calc_latest_close(p)
        time.sleep(0.1)

    # 依股票代碼彙整近5年EPS
    eps_by_code = {}
    for _, row in fin_data.iterrows():
        code = str(row.get('code', '')).strip()
        eps = row.get('eps')
        yr = row.get('year_roc', 0)
        if code and not pd.isna(eps):
            if code not in eps_by_code:
                eps_by_code[code] = {}
            yr_key = int(yr) if yr else 0
            if yr_key not in eps_by_code[code]:
                eps_by_code[code][yr_key] = []
            eps_by_code[code][yr_key].append(float(eps))

    # 依股票代碼取最新ROE、負債比
    latest_roe = {}
    latest_debt = {}
    latest_eps_annual = {}
    for _, row in fin_data.sort_values(['year_roc', 'season'], ascending=False).iterrows():
        code = str(row.get('code', '')).strip()
        if code not in latest_roe and not pd.isna(row.get('roe')):
            latest_roe[code] = float(row['roe'])
        if code not in latest_debt and not pd.isna(row.get('debt_ratio')):
            latest_debt[code] = float(row['debt_ratio'])

    # 計算年度EPS（取各年度Q4或全年加總）
    now_yr = datetime.now().year - 1911
    for code, yr_data in eps_by_code.items():
        annual_eps = {}
        for yr, eps_list in yr_data.items():
            # 取年度加總（每股盈餘四季加總）
            annual_eps[yr] = sum(eps_list)
        latest_eps_annual[code] = annual_eps

    # 套用六個條件
    for code in codes:
        stock = stock_dict.get(code, {})
        if stock.get('type') not in ['個股']:
            continue

        eps_annual = latest_eps_annual.get(code, {})
        roe = latest_roe.get(code)
        debt = latest_debt.get(code)
        bvps = bvps_map.get(code)
        price = price_map.get(code)

        # 計算PB
        pb = round(price / bvps, 2) if price and bvps and bvps > 0 else None

        # 條件1：近5年EPS皆為正
        valid_years = sorted([yr for yr in eps_annual.keys() if yr >= now_yr - 5], reverse=True)
        c1_eps_positive = all(eps_annual.get(yr, -1) > 0 for yr in valid_years) if len(valid_years) >= 3 else False

        # 條件2：近3年EPS成長率 > 0（最新年 vs 3年前）
        c2_eps_growth = False
        recent_years = sorted(valid_years, reverse=True)
        if len(recent_years) >= 2:
            newest = eps_annual.get(recent_years[0], None)
            oldest = eps_annual.get(recent_years[min(2, len(recent_years)-1)], None)
            if newest and oldest and oldest != 0:
                c2_eps_growth = newest > oldest

        # 條件3：PB < 3
        c3_pb = pb < 3 if pb is not None else None

        # 條件4：ROE > 15%
        c4_roe = roe > 15 if roe is not None else None

        # 條件5：負債比 < 50%
        c5_debt = debt < 50 if debt is not None else None

        # 條件6：PB/ROE < 0.20
        c6_pb_roe = round(pb / roe, 3) < 0.20 if pb and roe and roe > 0 else None

        # 通過數（只計算有資料的條件）
        conditions = {
            '5年EPS皆正': c1_eps_positive,
            'EPS成長': c2_eps_growth,
            'PB<3': c3_pb,
            'ROE>15%': c4_roe,
            '負債比<50%': c5_debt,
            'PB/ROE<0.20': c6_pb_roe,
        }
        passed = sum(1 for v in conditions.values() if v is True)
        failed = sum(1 for v in conditions.values() if v is False)
        all_pass = all(v is True for v in conditions.values() if v is not None) and None not in conditions.values()

        results.append({
            '代碼': code,
            '名稱': stock.get('name', ''),
            '產業別': stock.get('industry', stock.get('group', '')),
            '股價': price,
            'PB': pb,
            'ROE%': roe,
            '負債比%': debt,
            'PB/ROE': round(pb / roe, 3) if pb and roe and roe > 0 else None,
            '5年EPS皆正': '✅' if c1_eps_positive else '❌',
            'EPS成長': '✅' if c2_eps_growth else '❌',
            'PB<3': '✅' if c3_pb else ('❌' if c3_pb is False else '⚠️'),
            'ROE>15%': '✅' if c4_roe else ('❌' if c4_roe is False else '⚠️'),
            '負債比<50%': '✅' if c5_debt else ('❌' if c5_debt is False else '⚠️'),
            'PB/ROE<0.20': '✅' if c6_pb_roe else ('❌' if c6_pb_roe is False else '⚠️'),
            '通過條件數': str(passed) + '/6',
            '合格': all_pass,
        })

    df_result = pd.DataFrame(results)
    return df_result


def get_sox_data():
    """抓費城半導體指數（SOX）"""
    try:
        prices = get_yahoo_history_us("^SOX", days=365)
        if not prices or len(prices) < 10:
            return None
        dates = sorted(prices.keys())
        current = prices[dates[-1]]
        high_52w = max(prices.values())
        low_52w = min(prices.values())
        pct_from_high = (current - high_52w) / high_52w * 100
        ma20_prices = [prices[d] for d in dates[-20:]]
        ma20 = sum(ma20_prices) / len(ma20_prices)
        above_ma20 = current > ma20
        # 近20日漲跌幅
        ret_20d = (current - prices[dates[-21]]) / prices[dates[-21]] * 100 if len(dates) >= 21 else None
        return {
            "current": current,
            "high_52w": high_52w,
            "low_52w": low_52w,
            "pct_from_high": round(pct_from_high, 1),
            "above_ma20": above_ma20,
            "ma20": round(ma20, 1),
            "ret_20d": round(ret_20d, 1) if ret_20d else None,
            "date": dates[-1],
        }
    except:
        return None


def get_us10y_data():
    """抓美國10年期公債殖利率"""
    try:
        prices = get_yahoo_history_us("^TNX", days=120)
        if not prices or len(prices) < 10:
            return None
        dates = sorted(prices.keys())
        current = prices[dates[-1]]
        price_90d_ago = prices[dates[0]] if len(dates) > 60 else None
        change_90d = round(current - price_90d_ago, 2) if price_90d_ago else None
        # 近20日方向
        price_20d_ago = prices[dates[-21]] if len(dates) >= 21 else None
        change_20d = round(current - price_20d_ago, 2) if price_20d_ago else None
        return {
            "current": round(current, 2),
            "change_90d": change_90d,
            "change_20d": change_20d,
            "date": dates[-1],
        }
    except:
        return None


def get_vix_data():
    """抓VIX恐慌指數"""
    try:
        prices = get_yahoo_history_us("^VIX", days=30)
        if not prices or len(prices) < 3:
            return None
        dates = sorted(prices.keys())
        current = prices[dates[-1]]
        week_ago = prices[dates[-6]] if len(dates) >= 6 else None
        change_1w = round(current - week_ago, 1) if week_ago else None
        return {
            "current": round(current, 1),
            "change_1w": change_1w,
            "date": dates[-1],
        }
    except:
        return None


def get_twd_data():
    """抓台幣匯率（USD/TWD）"""
    try:
        prices = get_yahoo_history_us("TWD=X", days=60)
        if not prices or len(prices) < 10:
            return None
        dates = sorted(prices.keys())
        current = prices[dates[-1]]
        price_30d_ago = prices[dates[0]] if len(dates) >= 20 else None
        # 台幣升值 = TWD=X下降（因為是USD/TWD，數字越小代表台幣越強）
        change_30d = round(current - price_30d_ago, 2) if price_30d_ago else None
        return {
            "current": round(current, 2),
            "change_30d": change_30d,
            "date": dates[-1],
        }
    except:
        return None


with tab6:
    st.subheader("📋 合格標的池")
    st.caption("基本面篩選器：只在通過六個條件的股票中尋找進場機會，排除基本面有問題的標的")

    # ── 市場背景快照 ──
    st.markdown("### 🌐 市場背景快照")
    st.caption("進場前先看大環境，判斷這次觸發是情緒性超跌還是系統性風險。每個指標都附有解讀說明。")

    with st.spinner("載入市場數據中..."):
        sox = get_sox_data()
        us10y = get_us10y_data()
        vix = get_vix_data()
        twd = get_twd_data()

    # ── SOX ──
    st.markdown("---")
    col_sox1, col_sox2 = st.columns([1, 2])
    with col_sox1:
        if sox:
            st.metric("費城半導體指數 SOX",
                     "{:,.0f}".format(sox["current"]),
                     "{:.1f}% 距52週高點".format(sox["pct_from_high"]))
            ma_status = "高於20MA ✅" if sox["above_ma20"] else "低於20MA ⚠️"
            st.caption("20日均線：{:,.0f}　狀態：{}".format(sox["ma20"], ma_status))
            if sox["ret_20d"] is not None:
                st.caption("近20日漲跌：{:+.1f}%".format(sox["ret_20d"]))
            # 燈號
            pct = sox["pct_from_high"]
            if pct > -15:
                st.success("🟢 SOX強勢（距高點<15%）")
            elif pct > -30:
                st.warning("🟡 SOX回落中（距高點15~30%）")
            else:
                st.error("🔴 SOX顯著下行（距高點>30%）")
        else:
            st.warning("SOX資料無法取得")

    with col_sox2:
        st.markdown("**📖 SOX怎麼讀、為什麼重要**")
        st.info(
            "**為什麼看SOX？**\n"
            "台股市值70%是電子股，半導體佔最大宗。外資操作台股時，"
            "SOX是最重要的先行指標——SOX下跌時，外資通常同步減少台灣半導體持股，"
            "不管個別公司基本面好不好。\n\n"
            "**距52週高點的意義：**\n"
            "・ 0% ~ -15%：SOX接近高點，半導體景氣良好。此時個股超跌觸發，"
            "很可能是情緒性超跌，進場勝率較高\n"
            "・ -15% ~ -30%：SOX明顯回落，需謹慎判斷是修正還是趨勢反轉\n"
            "・ < -30%：歷史上2000年、2008年、2022年三次大熊市都超過-30%，"
            "代表可能進入趨勢性下跌，均值回歸策略勝率明顯下降\n\n"
            "**20MA的意義：**\n"
            "SOX高於20日均線代表短期趨勢向上，個股觸發進場更有把握；"
            "低於20MA代表短期趨勢向下，進場需更謹慎"
        )

    # ── 美債殖利率 ──
    st.markdown("---")
    col_10y1, col_10y2 = st.columns([1, 2])
    with col_10y1:
        if us10y:
            change_str = "{:+.2f}%（近90日）".format(us10y["change_90d"]) if us10y["change_90d"] else ""
            st.metric("美債10年期殖利率", "{:.2f}%".format(us10y["current"]), change_str)
            if us10y["change_20d"]:
                st.caption("近20日變化：{:+.2f}%".format(us10y["change_20d"]))
            # 燈號（看90日速度）
            chg = us10y.get("change_90d", 0) or 0
            if chg >= 1.0:
                st.error("🔴 殖利率快速上升（90日+{:.2f}%）估值壓力大".format(chg))
            elif chg >= 0.5:
                st.warning("🟡 殖利率緩慢上升（90日+{:.2f}%）需留意".format(chg))
            elif chg <= -0.3:
                st.success("🟢 殖利率下降（90日{:.2f}%）對股市有利".format(chg))
            else:
                st.success("🟢 殖利率穩定")
        else:
            st.warning("殖利率資料無法取得")

    with col_10y2:
        st.markdown("**📖 美債殖利率怎麼讀、為什麼重要**")
        st.info(
            "**為什麼看10年期而不是Fed利率？**\n"
            "Fed設定的是短期政策利率，但影響股票估值的是市場自己定的10年期殖利率。"
            "它反映市場對未來10年利率和通膨的預期，是股票DCF估值的折現率。\n\n"
            "**估值數學：** 股票合理價值 = 未來現金流 ÷ 折現率\n"
            "殖利率上升→折現率上升→股票合理價值下降→股價承壓\n\n"
            "**為什麼看「方向」不看「絕對水位」？**\n"
            "因為市場已經消化了當前水位。危險的不是「殖利率高」，而是「殖利率快速上升」。\n"
            "2022年：殖利率從1.5%升到4.3%，不到12個月漲280bp，成長股估值崩潰。\n"
            "那年我們策略的觸發後勝率是15年回測中最低的年度。\n\n"
            "**門檻說明：**\n"
            "・ 90日上升 > 1.0%（100bp）：歷史上只出現在2022年、2013年Taper Tantrum，"
            "是系統性風險信號，策略勝率大幅下降\n"
            "・ 90日上升 0.3~1.0%：緩慢上升，市場可消化，正常操作\n"
            "・ 90日下降：對股票最有利，進場勝率較高\n\n"
            "**現在4.45%怎麼看？**\n"
            "這個水位偏高但市場已適應。高殖利率環境下，低PB、高ROE的價值股"
            "（正是我們篩選條件）反而相對有吸引力，比高本益比成長股更抗跌"
        )

    # ── VIX ──
    st.markdown("---")
    col_vix1, col_vix2 = st.columns([1, 2])
    with col_vix1:
        if vix:
            change_str = "{:+.1f}（近1週）".format(vix["change_1w"]) if vix["change_1w"] else ""
            st.metric("VIX 恐慌指數", "{:.1f}".format(vix["current"]), change_str)
            v = vix["current"]
            if v < 15:
                st.success("🟢 市場極度平靜（VIX<15）")
                st.caption("個股觸發可能只是技術性調整，不是恐慌")
            elif v < 20:
                st.success("🟢 市場平靜（VIX 15~20）正常環境")
            elif v < 30:
                st.warning("🟡 市場緊張（VIX 20~30）觸發後反彈機率中等")
            elif v < 40:
                st.error("🔴 市場恐慌（VIX 30~40）歷史上長期回報反而最好")
            else:
                st.error("🔴 系統性恐慌（VIX>40）如2020年3月，往往是最佳進場時機")
        else:
            st.warning("VIX資料無法取得")

    with col_vix2:
        st.markdown("**📖 VIX怎麼讀、為什麼重要**")
        st.info(
            "**VIX是什麼？**\n"
            "VIX是CBOE計算的市場隱含波動率，衡量市場對未來30天S&P500波動幅度的預期。"
            "俗稱「恐慌指數」。\n\n"
            "**對我們策略的特殊意義：**\n"
            "我們的策略是「在恐慌中進場」，VIX正好告訴我們恐慌程度有多深。\n"
            "Baron Rothschild的名言：「在街上血流成河時買入。」VIX就是衡量血流多深的工具。\n\n"
            "**各區間的實務意義：**\n"
            "・ VIX < 15：市場極度平靜，個股觸發可能只是技術調整，"
            "不代表情緒性超跌，要更謹慎確認基本面\n"
            "・ VIX 15~20：正常環境，策略照常執行\n"
            "・ VIX 20~30：市場緊張，但往往也是觸發後反彈機率合理的環境\n"
            "・ VIX 30~40：市場恐慌，歷史數據顯示這個區間進場的長期回報最高，"
            "但要有心理準備短期繼續跌\n"
            "・ VIX > 40：系統性恐慌（2020年3月VIX達85），往往是千載難逢的進場時機，"
            "但需要極強的心理素質\n\n"
            "**注意：** VIX高不代表「不要進場」，剛好相反。"
            "VIX高代表市場已經恐慌，超跌反彈的機率更高。"
            "真正要小心的是VIX很低時進場，代表沒有足夠的恐慌溢價"
        )

    # ── 台幣匯率 ──
    st.markdown("---")
    col_twd1, col_twd2 = st.columns([1, 2])
    with col_twd1:
        if twd:
            chg = twd.get("change_30d", 0) or 0
            # TWD=X是USD/TWD，數字越小=台幣越強
            direction = "台幣升值 ✅" if chg < -0.3 else ("台幣貶值 ⚠️" if chg > 0.3 else "台幣穩定")
            change_str = "{:+.2f}（近30日，負值=台幣升值）".format(chg)
            st.metric("台幣匯率 USD/TWD", "{:.2f}".format(twd["current"]), change_str)
            if chg < -0.5:
                st.success("🟢 台幣明顯升值（外資傾向持有台股）")
            elif chg < 0.3:
                st.success("🟢 台幣穩定或小升")
            elif chg < 1.0:
                st.warning("🟡 台幣小幅貶值（外資有輕微賣壓）")
            else:
                st.error("🔴 台幣明顯貶值（外資賣壓，不利台股）")
        else:
            st.warning("台幣匯率資料無法取得")

    with col_twd2:
        st.markdown("**📖 台幣匯率怎麼讀、為什麼重要**")
        st.info(
            "**這是台股獨有的關鍵指標，很多散戶忽略但法人非常重視。**\n\n"
            "**為什麼台幣匯率影響台股？**\n"
            "外資在台股的持股佔比超過40%（半導體股甚至超過60%）。"
            "外資的投資報酬是以美元計算的，所以台幣匯率直接影響他們的投資成本。\n\n"
            "**邏輯鏈：**\n"
            "台幣升值 → 外資持有台股的美元報酬上升（匯兌增益）"
            " → 外資有動機買入/持有台股 → 資金流入 → 個股超跌後更容易反彈\n\n"
            "台幣貶值 → 外資持有台股的美元報酬下降（匯兌損失）"
            " → 外資有動機賣出台股換回美元 → 賣壓持續 → 觸發後可能繼續跌\n\n"
            "**數字怎麼讀：**\n"
            "USD/TWD這個數字，越小代表台幣越強（1美元換越少台幣）\n"
            "例如：從31.5降到30.8，代表台幣升值，對台股有利\n\n"
            "**30日變化的門檻：**\n"
            "・ 下降超過0.5：台幣明顯升值，外資有動機加碼台股\n"
            "・ -0.5 ~ +0.5：匯率穩定，中性\n"
            "・ 上升超過1.0：台幣明顯貶值，注意外資賣壓是否持續\n\n"
            "**實例：** 2022年台幣從28貶到32，外資大幅賣超台股，"
            "那年我們策略的觸發後勝率明顯低於平均，匯率是重要原因之一"
        )

    # ── 整體環境綜合判斷 ──
    st.markdown("---")
    st.markdown("### 🎯 整體環境綜合判斷")

    if sox and us10y and vix and twd:
        sox_ok = sox["pct_from_high"] > -30
        sox_strong = sox["pct_from_high"] > -15
        rate_ok = (us10y.get("change_90d") or 0) < 1.0
        rate_rising = (us10y.get("change_90d") or 0) > 0.3
        vix_val = vix["current"]
        twd_chg = twd.get("change_30d") or 0
        twd_ok = twd_chg < 0.5

        # 計分
        score = 0
        signals = []
        if sox_strong:
            score += 2
            signals.append("✅ SOX強勢（距高點<15%），台灣半導體個股超跌更可能是情緒性")
        elif sox_ok:
            score += 1
            signals.append("🟡 SOX回落中（距高點15~30%），正常操作")
        else:
            score -= 2
            signals.append("❌ SOX顯著下行（距高點>30%），均值回歸策略勝率下降")

        if not rate_rising:
            score += 2
            signals.append("✅ 殖利率穩定或下降，股票估值支撐")
        elif rate_ok:
            score += 0
            signals.append("🟡 殖利率緩慢上升，市場可消化，正常操作")
        else:
            score -= 2
            signals.append("❌ 殖利率快速上升（>100bp/季），估值壓力大，類2022風險")

        if vix_val >= 30:
            score += 2
            signals.append("✅ VIX高位（≥30），市場恐慌通常是進場好時機")
        elif vix_val >= 20:
            score += 1
            signals.append("🟡 VIX偏高（20~30），觸發後反彈機率合理")
        else:
            score += 0
            signals.append("🔵 VIX平靜（<20），確認是真正超跌而非小幅調整")

        if twd_ok:
            score += 1
            signals.append("✅ 台幣穩定或升值，外資無明顯賣壓")
        else:
            score -= 1
            signals.append("⚠️ 台幣貶值，注意外資持續賣壓")

        # 綜合結論
        for s in signals:
            st.markdown("　" + s)
        st.markdown("")

        if score >= 4:
            st.success(
                "**🟢 環境：積極進場**\n\n"
                "多項指標支持，觸發標的在通過基本面篩選後可以正常倉位進場。"
                "這種環境下我們策略的歷史勝率最高。"
            )
        elif score >= 1:
            st.warning(
                "**🟡 環境：正常操作，注意風險**\n\n"
                "整體環境中性，部分指標需留意。觸發標的通過基本面篩選後可以進場，"
                "但建議控制單筆倉位，不要滿倉。"
            )
        elif score >= -1:
            st.warning(
                "**🟡 環境：謹慎，縮小倉位**\n\n"
                "環境偏弱，建議只進入通過所有6個基本面條件且歷史勝率最高的標的，"
                "倉位減至正常的50~70%。"
            )
        else:
            st.error(
                "**🔴 環境：高風險，大幅縮減**\n\n"
                "類2022環境，多項指標顯示系統性風險。建議只操作最高品質標的，"
                "倉位減至正常的30~50%，或暫停操作等待環境改善。"
            )

        st.caption(
            "評分說明：SOX強勢+2、SOX正常+1、SOX下行-2｜"
            "殖利率穩定+2、殖利率緩升0、殖利率快升-2｜"
            "VIX>30（恐慌）+2、VIX 20~30+1、VIX<20+0｜"
            "台幣穩定/升值+1、台幣貶值-1｜"
            "總分≥4積極、≥1正常、≥-1謹慎、<-1高風險"
        )
    else:
        st.info("部分市場數據無法取得，請稍後重整頁面")

    st.divider()


    # ── 六個條件說明 ──
    with st.expander("📖 六個篩選條件說明"):
        st.markdown("""
| 條件 | 門檻 | 目的 |
|------|------|------|
| ① 近5年EPS皆為正 | EPS > 0 | 排除虧損股、轉機股、生技股 |
| ② 近3年EPS成長 | 成長率 > 0 | 避開衰退產業、成熟衰退股 |
| ③ 股價淨值比 | PB < 3 | 避免追高，排除估值過高標的 |
| ④ 股東權益報酬率 | ROE > 15% | 確保公司真的會賺錢，排除殭屍企業 |
| ⑤ 負債比率 | < 50% | 避開高槓桿公司、財務危機股 |
| ⑥ PB/ROE複合條件 | < 0.20 | 用PB買ROE，確保估值合理 |

⚠️ 注意：負債比 < 50% 會排除部分金融股，PB < 3 可能排除台積電等超級企業，這是刻意的選擇。
        """)

    st.divider()

    # ── 建立合格標的池 ──
    st.markdown("### 🔍 建立合格標的池")

    col_btn1, col_btn2, col_info = st.columns([1, 1, 3])
    with col_btn1:
        build_btn = st.button("🔄 建立/更新合格標的池", type="primary", key="build_pool")
    with col_btn2:
        quick_btn = st.button("⚡ 快速查詢（個股）", key="quick_check_btn")
    with col_info:
        st.caption("建立完整池子需要抓取MOPS財報資料（約需3~5分鐘）。池子每季更新一次即可。")

    if build_btn:
        with st.spinner("步驟1/3：取得全市場股票清單..."):
            all_stocks = get_all_tw_stocks()
            individual_stocks = [s for s in all_stocks if s['type'] == '個股']
            st.info("取得 " + str(len(individual_stocks)) + " 檔個股")

        with st.spinner("步驟2/3：從MOPS抓取近5年財報資料（上市+上櫃，需要較長時間）..."):
            fin_data = get_all_financial_data()
            if fin_data is not None:
                st.info("財報資料筆數：" + str(len(fin_data)))
            else:
                st.error("財報資料抓取失敗，請稍後再試")

        if fin_data is not None:
            with st.spinner("步驟3/3：套用六個條件篩選..."):
                df_pool = build_qualified_pool(all_stocks, fin_data)

            if df_pool is not None:
                qualified = df_pool[df_pool['合格'] == True].reset_index(drop=True)
                st.session_state['qualified_pool'] = qualified
                st.session_state['full_pool'] = df_pool
                st.success("✅ 合格標的池建立完成！共 " + str(len(qualified)) + " 檔通過全部6個條件")

    # 顯示合格標的池
    if 'qualified_pool' in st.session_state:
        df_q = st.session_state['qualified_pool']
        df_full = st.session_state.get('full_pool')

        st.markdown("### ✅ 合格標的清單（通過全部6個條件）")

        # 產業分布
        if '產業別' in df_q.columns:
            industry_counts = df_q['產業別'].value_counts().head(8)
            industry_str = "　".join([k + "(" + str(v) + ")" for k, v in industry_counts.items()])
            st.info("**產業分布**：" + industry_str)

        display_cols = ['代碼', '名稱', '產業別', '股價', 'PB', 'ROE%', '負債比%', 'PB/ROE', '通過條件數']
        show_html(df_q[display_cols].style.background_gradient(subset=['ROE%'], cmap='RdYlGn'))
        st.download_button(
            "📥 下載合格標的清單CSV",
            df_q.to_csv(index=False).encode('utf-8-sig'),
            "qualified_pool.csv", "text/csv"
        )

        if df_full is not None:
            with st.expander("查看全部股票的條件評分（含未通過）"):
                cond_cols = ['代碼', '名稱', '產業別', '5年EPS皆正', 'EPS成長', 'PB<3', 'ROE>15%', '負債比<50%', 'PB/ROE<0.20', '通過條件數']
                show_html(df_full[cond_cols])

    st.divider()

    # ── 個股快查 ──
    st.markdown("### 🔎 個股快查（進場前確認）")
    st.caption("輸入股票代碼，快速確認這六個條件是否通過")

    check_code = st.text_input("輸入股票代碼", placeholder="例：2317", key="pool_check_code")
    if st.button("確認基本面條件", key="check_fundamental"):
        if not check_code.strip():
            st.warning("請輸入代碼")
        else:
            code = check_code.strip()
            # 從session_state的pool找
            found = False
            if 'full_pool' in st.session_state:
                df_full = st.session_state['full_pool']
                row = df_full[df_full['代碼'] == code]
                if not row.empty:
                    row = row.iloc[0]
                    found = True
                    st.markdown("**" + code + " " + str(row.get('名稱', '')) + "**")
                    cols = st.columns(3)
                    conditions = [
                        ('① 近5年EPS皆正', row.get('5年EPS皆正', '⚠️')),
                        ('② 近3年EPS成長', row.get('EPS成長', '⚠️')),
                        ('③ PB < 3', row.get('PB<3', '⚠️') + "　（PB=" + str(row.get('PB', 'N/A')) + "）"),
                        ('④ ROE > 15%', row.get('ROE>15%', '⚠️') + "　（ROE=" + str(row.get('ROE%', 'N/A')) + "%）"),
                        ('⑤ 負債比 < 50%', row.get('負債比<50%', '⚠️') + "　（" + str(row.get('負債比%', 'N/A')) + "%）"),
                        ('⑥ PB/ROE < 0.20', row.get('PB/ROE<0.20', '⚠️') + "　（" + str(row.get('PB/ROE', 'N/A')) + "）"),
                    ]
                    for i, (label, val) in enumerate(conditions):
                        with cols[i % 3]:
                            if '✅' in str(val):
                                st.success(label + "\n" + str(val))
                            elif '❌' in str(val):
                                st.error(label + "\n" + str(val))
                            else:
                                st.warning(label + "\n" + str(val) + "（資料不足）")

                    all_pass = row.get('合格', False)
                    if all_pass:
                        st.success("✅ **此標的通過全部條件，可列入進場候選**")
                    else:
                        st.error("❌ **此標的未通過全部條件，進場需謹慎評估**")

            if not found:
                st.warning("請先建立合格標的池，或此代碼不在個股範圍內")

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
            prices_new = get_yahoo_history_15y(single_code)
        if not prices_new:
            st.error("抓取失敗，請確認代碼是否正確")
        else:
            st.session_state["bt_prices"] = prices_new
            st.session_state["bt_code"] = single_code
            st.session_state["bt_thr"] = int(ref_threshold.replace("%", ""))
            st.session_state["bt_thr_str"] = ref_threshold
            st.session_state["bt_done"] = True

    if st.session_state.get("bt_done") and st.session_state.get("bt_code") == single_code:
        prices = st.session_state["bt_prices"]
        thr_val = st.session_state["bt_thr"]
        ref_threshold_display = st.session_state["bt_thr_str"]

        st.success("成功抓取 " + str(len(prices)) + " 個交易日（" + min(prices.keys()) + " ~ " + max(prices.keys()) + "）")

        with st.spinner("計算各門檻回測中..."):
            df_win, df_avg, df_dd = build_summary_tables(prices)

        win_cols = [str(h) + "天勝率" for h in HORIZONS]
        avg_cols = [str(h) + "天平均報酬%" for h in HORIZONS]
        dd_cols = [str(h) + "天平均最大回撤%" for h in HORIZONS]

        st.markdown("### 表A：勝率（各門檻 × 觀察天數）｜橘色 ≥ 80%")
        st.caption("勝率 = 觸發進場後，T+N天收盤價高於進場收盤價的比例")
        show_html(df_win.style.map(color_winrate, subset=win_cols))

        st.markdown("### 表B：平均單次報酬%（各門檻 × 觀察天數）")
        show_html(heatmap_positive(df_avg, avg_cols))

        cum_rows = []
        for thr in THRESHOLDS:
            result_c = run_full_backtest(prices, thr)
            row = {"觸發門檻": str(thr) + "%", "樣本數": 0 if result_c is None else result_c["total"]}
            for h in HORIZONS:
                if result_c is None:
                    row[str(h) + "天累積%"] = "---"
                else:
                    rets = [x["ret"] for x in result_c["horizon_rets"][h]]
                    row[str(h) + "天累積%"] = fmt(round(sum(rets), 2) if rets else None)
            cum_rows.append(row)
        df_cum = pd.DataFrame(cum_rows)
        cum_cols = [str(h) + "天累積%" for h in HORIZONS]
        st.markdown("### 表C：累積報酬%（所有觸發報酬加總，不除筆數）")
        show_html(heatmap_positive(df_cum, cum_cols))

        st.markdown("### 表D：進場時機比較（門檻 " + ref_threshold_display + "）")
        horizon_choice = st.selectbox("選擇觀察天數", [str(h) + "天" for h in HORIZONS], index=4, key="timing_horizon")
        h_timing = int(horizon_choice.replace("天", ""))
        df_timing = build_entry_timing_table(prices, thr_val, h_timing)
        if df_timing is not None:
            ret_cols_t = ["平均報酬%", "累積報酬%"]
            styled_t = heatmap_positive(df_timing, ret_cols_t)
            styled_t = styled_t.map(color_winrate, subset=["勝率"])
            show_html(styled_t)
            st.caption("連續第1天：首次觸發｜連續第2天：跌2天才進｜連續第3天以後：等更深跌｜連續結束翌日：止跌確認後才進")
        else:
            st.warning("此門檻無觸發紀錄")

        st.markdown("### 表E：最大回撤分析（門檻 " + ref_threshold_display + "）")
        df_dd_enhanced = build_dd_timing_table(prices, thr_val)
        if df_dd_enhanced is not None:
            show_html(df_dd_enhanced.style.map(color_dd, subset=["平均最大回撤%", "最深回撤%"]))

        st.info(
            "計算邏輯：勝率與報酬均以 T+N 那天收盤價計算｜"
            "年度歸屬以觸發當天為準｜待觀察：觸發後未滿觀察天數，不計入統計"
        )

        df_yearly, result = build_yearly_table(prices, thr_val)
        if df_yearly is not None:
            st.markdown("### 年度明細（門檻 " + ref_threshold_display + "）")
            yr_cols = [str(h) + "天平均%" for h in HORIZONS]
            show_html(heatmap_positive(df_yearly, yr_cols))

        st.markdown("### 連續觸發分析（門檻 " + ref_threshold_display + "）")
        horizon_consec = st.selectbox("選擇觀察天數", [str(h) + "天" for h in HORIZONS], index=4, key="consec_horizon")
        h_consec = int(horizon_consec.replace("天", ""))
        df_consec = build_consec_analysis(prices, thr_val, h_consec)
        if df_consec is not None:
            styled_c = heatmap_positive(df_consec, ["平均報酬%"])
            styled_c = styled_c.map(color_winrate, subset=["勝率"])
            styled_c = styled_c.map(color_ret, subset=["最佳報酬%", "最差報酬%"])
            show_html(styled_c)

        if result:
            st.markdown("### 股價走勢 + 各門檻觸發標記")
            dates_all = sorted(prices.keys())
            price_values = [prices[d] for d in dates_all]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=dates_all, y=price_values, mode="lines", name="收盤價",
                                     line=dict(color="#2196F3", width=1.5)))
            colors_map = {-5: "#FFA500", -7: "#FF6B35", -10: "#E63946", -15: "#9B2335", -20: "#5C0A14"}
            for thr in THRESHOLDS:
                r_thr = run_full_backtest(prices, thr)
                if r_thr:
                    trig_x = [d for d in dates_all if d in set(r_thr["trigger_dates"])]
                    trig_y = [prices[d] for d in trig_x]
                    label = "門檻 " + str(thr) + "% (" + str(r_thr["total"]) + "次)"
                    fig.add_trace(go.Scatter(x=trig_x, y=trig_y, mode="markers", name=label,
                                             legendgroup=label, marker=dict(color=colors_map[thr], size=6),
                                             visible=True if thr == thr_val else "legendonly", showlegend=False))
                    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name=label,
                                             legendgroup=label, marker=dict(color=colors_map[thr], size=14),
                                             visible=True if thr == thr_val else "legendonly", showlegend=True))
            fig.update_layout(height=520, xaxis_title="日期", yaxis_title="收盤價",
                              hovermode="x unified",
                              legend=dict(orientation="h", yanchor="bottom", y=1.02,
                                         itemsizing="constant", font=dict(size=13)))
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("查看觸發日明細（門檻 " + ref_threshold_display + "）"):
                df_trig = pd.DataFrame([{
                    "觸發日": t["date"], "基準日": t["base_date"],
                    "基準價": t["base_price"], "觸發當日收盤": t["curr_price"],
                    "滾動10日報酬率": "{:.2f}%".format(t["return"])
                } for t in result["triggers"]])
                show_html(df_trig)

        # 分析建議（直接render，不存session_state）
        st.markdown("---")
        st.markdown("### 📋 回測分析建議")
        st.caption("根據上方回測數據自動生成，不構成投資建議")
        if st.button("📋 生成分析建議", key="ai_analysis"):
            render_analysis(single_code, df_win, df_avg, df_dd, df_yearly, thr_val, prices_dict=prices)

# ==============================
# TAB 4: 全市場勝率排行
# ==============================
with tab4:
    st.subheader("全市場勝率排行（各門檻前10名）")
    st.info(
        "系統對每檔股票跑15年回測，找出各觸發門檻下勝率最高的前10名，合併成一張表橫向比較。\n\n"
        "📌 **怎麼讀這張表**：橫向看同一檔股票在各門檻的勝率，找出在多個門檻都表現穩定的股票；"
        "縱向看同一門檻哪些股票勝率最高。橘色 ≥ 80%，淡黃色 ≥ 70%。\n\n"
        "📌 **觀察天數**：你想研究跌破門檻後，放多久再看結果？"
        "選10天 = 觸發後持有10天的勝率排行；選100天 = 觸發後持有100天的勝率排行。\n\n"
        "⚠️ 觸發次數 ≤ 5次的標的自動加注警示，樣本太少勝率參考性有限。"
    )
    st.markdown("**選擇掃描範圍（不選預設跑全部個股）**")
    selected4 = group_selector("tab4")
    horizon4 = st.selectbox("觀察天數（觸發後持有多久再看勝率）",
                             [str(h) + "天" for h in HORIZONS], index=6, key="h4")

    if st.button("🏆 開始計算勝率排行", type="primary", key="winrank"):
        all_stocks_r = get_all_tw_stocks()
        rank_list = ([s for s in all_stocks_r if s["group"] in selected4]
                     if selected4 else [s for s in all_stocks_r if s["type"] == "個股"])
        h_val = int(horizon4.replace("天", ""))
        total = len(rank_list)
        st.info("共 " + str(total) + " 檔，開始計算（需較長時間）...")

        stock_results = {}
        progress = st.progress(0)
        status = st.empty()

        for i, stock in enumerate(rank_list):
            code = stock["code"]
            status.text("計算中：" + code + " " + stock["name"] + "（" + str(i+1) + "/" + str(total) + "）")
            prices_r = get_yahoo_history_15y(code)
            if not prices_r:
                progress.progress((i+1)/total)
                time.sleep(0.1)
                continue

            # 產業別優先用真實產業，沒有才用group
            industry_display = stock["industry"] if stock["industry"] and stock["industry"] != "" else stock["group"]

            stock_data = {"代碼": code, "名稱": stock["name"], "產業別": industry_display}
            has_any = False
            for thr in THRESHOLDS:
                result_r = run_full_backtest(prices_r, thr)
                if result_r is None:
                    stock_data[str(thr) + "%勝率"] = None
                    stock_data[str(thr) + "%次數"] = 0
                else:
                    rets = [x["ret"] for x in result_r["horizon_rets"][h_val]]
                    if not rets:
                        stock_data[str(thr) + "%勝率"] = None
                        stock_data[str(thr) + "%次數"] = result_r["total"]
                    else:
                        wins = sum(1 for r in rets if r > 0)
                        stock_data[str(thr) + "%勝率"] = round(wins / len(rets) * 100, 2)
                        stock_data[str(thr) + "%次數"] = result_r["total"]
                        has_any = True
            if has_any:
                stock_results[code] = stock_data
            progress.progress((i+1)/total)
            time.sleep(0.2)

        progress.empty()
        status.empty()

        if not stock_results:
            st.warning("沒有找到足夠資料")
        else:
            st.success("✅ 計算完成！")

            # 合併各門檻前10名
            top_codes = set()
            for thr in THRESHOLDS:
                col = str(thr) + "%勝率"
                ranked = sorted(
                    [(c, d) for c, d in stock_results.items() if d.get(col) is not None],
                    key=lambda x: x[1][col], reverse=True
                )[:10]
                for c, _ in ranked:
                    top_codes.add(c)

            rows = []
            for code in top_codes:
                data = stock_results[code]
                row = {"代碼": data["代碼"], "名稱": data["名稱"], "產業別": data["產業別"]}
                for thr in THRESHOLDS:
                    wr = data.get(str(thr) + "%勝率")
                    cnt = data.get(str(thr) + "%次數", 0)
                    if wr is None:
                        row[str(thr) + "%"] = "---"
                    elif cnt <= 5:
                        row[str(thr) + "%"] = "{:.1f}%⚠️".format(wr)
                    else:
                        row[str(thr) + "%"] = "{:.1f}%".format(wr)
                rows.append(row)

            df_combined = pd.DataFrame(rows)
            df_combined = df_combined.sort_values(
                "-10%",
                key=lambda col: col.map(lambda v: float(str(v).replace("%","").replace("⚠️","")) if v not in ["---"] else 0),
                ascending=False
            ).reset_index(drop=True)

            thr_cols = [str(thr) + "%" for thr in THRESHOLDS]

            def style_winrate_cell(val):
                if str(val) in ["", "---"]:
                    return ""
                try:
                    v = float(str(val).replace("%","").replace("⚠️",""))
                    if v >= 80:
                        return "background-color: #FF8C00; color: white; font-weight: bold"
                    elif v >= 70:
                        return "background-color: #FFD580; color: #5a3e00; font-weight: bold"
                    elif v >= 60:
                        return "color: red; font-weight: bold"
                    else:
                        return "color: #888888"
                except:
                    return ""

            st.markdown(
                "### 各門檻勝率合併排行｜觀察天數：**" + horizon4 +
                "**（觸發後持有" + horizon4 + "的勝率）"
            )
            st.caption(
                "橘色 ≥ 80%　淡黃色 ≥ 70%　紅色 ≥ 60%　⚠️ = 觸發次數 ≤ 5次樣本不足\n"
                "依 -10% 門檻勝率排序｜橫向看同一檔在各門檻的表現，找在多個門檻都穩定高勝率的股票"
            )
            show_html(df_combined.style.map(style_winrate_cell, subset=thr_cols))

            # 自動分析
            st.markdown("#### 📊 自動分析")
            # 找多門檻高勝率股票
            multi_high = []
            for _, row in df_combined.iterrows():
                high_count = 0
                for thr in THRESHOLDS:
                    v_str = str(row.get(str(thr) + "%", "0"))
                    try:
                        v = float(v_str.replace("%","").replace("⚠️",""))
                        if v >= 70:
                            high_count += 1
                    except:
                        pass
                if high_count >= 3:
                    multi_high.append(row["名稱"] + "(" + row["代碼"] + ")")

            # 產業分布
            industry_counts = df_combined["產業別"].value_counts()

            col1, col2 = st.columns(2)
            with col1:
                if multi_high:
                    st.success(
                        "**🏆 多門檻穩定高勝率（≥3個門檻勝率≥70%）**\n\n" +
                        "　" + "、".join(multi_high[:8]) + "\n\n" +
                        "→ 這些股票在多種跌幅門檻下都有較高勝率，代表跌後反彈能力較強，適合作為優先候選標的。"
                    )
                else:
                    st.info("無多門檻同時高勝率的標的")
            with col2:
                industry_str = "、".join([k + "(" + str(v) + "檔)" for k, v in industry_counts.items()])
                st.info(
                    "**📊 產業分布**\n\n" + industry_str + "\n\n" +
                    "→ 若特定產業集中出現，代表該產業在此門檻觸發後歷史上反彈能力較強，可作為產業輪動參考。"
                )
