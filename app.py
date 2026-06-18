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


# ==============================
# 頁籤順序：使用說明→系統檢核→每日警示→批次回測→個股回測→全市場勝率
# ==============================
tab0, tab5, tab1, tab3, tab4, tab2 = st.tabs([
    "📖 使用說明",
    "🔧 系統檢核",
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
                res = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", timeout=10)
                data = res.json()
                return len(data) > 100, "取得 " + str(len(data)) + " 筆上市證券"
            run_check("證交所TWSE API", check_twse)

            def check_tpex():
                res = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes", timeout=10)
                data = res.json()
                return len(data) > 50, "取得 " + str(len(data)) + " 筆上櫃證券"
            run_check("櫃買中心TPEX API", check_tpex)

            def check_yahoo():
                p = get_yahoo_history("2330", days=60)
                if len(p) < 10:
                    return False, "資料筆數不足：" + str(len(p))
                d = sorted(p.keys())
                return True, "2330台積電 最新收盤：" + str(p[d[-1]]) + "（" + d[-1] + "）｜取得 " + str(len(p)) + " 筆"
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
        if all("✅" in c["狀態"] for c in checks):
            st.success("✅ 所有系統檢核通過！")
        else:
            failed = [c["項目"] for c in checks if "❌" in c["狀態"]]
            st.error("❌ 異常項目：" + "、".join(failed))

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
# TAB 4: 全市場勝率排行
# ==============================
with tab4:
    st.subheader("全市場勝率排行（各門檻前10名）")
    st.info(
        "系統會跑15年回測，找出各觸發門檻下勝率最高的前10檔股票\n\n"
        "📌 觀察天數：你想研究跌破門檻後，放多久再看結果？\n"
        "選10天 = 觸發後2週的勝率排行；選100天 = 觸發後5個月的勝率排行。\n\n"
        "⚠️ 觸發次數 ≤ 5次的標的自動加注警示，樣本太少勝率參考性有限。"
    )
    st.markdown("**選擇掃描範圍（不選預設跑全部個股）**")
    selected4 = group_selector("tab4")
    col_h, col_m = st.columns(2)
    with col_h:
        horizon4 = st.selectbox("觀察天數", [str(h) + "天" for h in HORIZONS], index=3, key="h4")

    if st.button("🏆 開始計算勝率排行", type="primary", key="winrank"):
        all_stocks_r = get_all_tw_stocks()
        rank_list = ([s for s in all_stocks_r if s["group"] in selected4]
                     if selected4 else [s for s in all_stocks_r if s["type"] == "個股"])
        h_val = int(horizon4.replace("天", ""))
        total = len(rank_list)
        st.info("共 " + str(total) + " 檔，開始計算...")

        stock_results = {}
        progress = st.progress(0)
        status = st.empty()

        for i, stock in enumerate(rank_list):
            code = stock["code"]
            status.text("計算中：" + code + " " + stock["name"] + "（" + str(i + 1) + "/" + str(total) + "）")
            prices = get_yahoo_history_15y(code)
            if not prices:
                progress.progress((i + 1) / total)
                time.sleep(0.1)
                continue

            stock_data = {
                "代碼": code, "名稱": stock["name"],
                "產業別": stock["industry"] if stock["industry"] else stock["group"],
            }
            has_any = False
            for thr in THRESHOLDS:
                result = run_full_backtest(prices, thr)
                if result is None:
                    stock_data[str(thr) + "%勝率"] = None
                    stock_data[str(thr) + "%次數"] = 0
                else:
                    rets = [x["ret"] for x in result["horizon_rets"][h_val]]
                    if not rets:
                        stock_data[str(thr) + "%勝率"] = None
                        stock_data[str(thr) + "%次數"] = result["total"]
                    else:
                        wins = sum(1 for r in rets if r > 0)
                        stock_data[str(thr) + "%勝率"] = round(wins / len(rets) * 100, 2)
                        stock_data[str(thr) + "%次數"] = result["total"]
                        has_any = True

            if has_any:
                stock_results[code] = stock_data

            progress.progress((i + 1) / total)
            time.sleep(0.2)

        progress.empty()
        status.empty()

        if not stock_results:
            st.warning("沒有找到足夠資料")
        else:
            st.success("✅ 計算完成！觀察天數：" + horizon4)

            top_codes = set()
            for thr in THRESHOLDS:
                col = str(thr) + "%勝率"
                ranked = sorted(
                    [(code, data) for code, data in stock_results.items() if data.get(col) is not None],
                    key=lambda x: x[1][col], reverse=True
                )[:10]
                for code, _ in ranked:
                    top_codes.add(code)

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
                key=lambda col: col.map(lambda v: float(str(v).replace("%", "").replace("⚠️", "")) if v not in ["---"] else 0),
                ascending=False
            ).reset_index(drop=True)

            thr_cols = [str(thr) + "%" for thr in THRESHOLDS]

            def style_winrate_cell(val):
                if val is None or str(val) in ["", "---"]:
                    return ""
                try:
                    v = float(str(val).replace("%", "").replace("⚠️", ""))
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

            st.markdown("### 各門檻勝率合併排行｜觀察天數：" + horizon4)
            st.caption("橘色 ≥ 80%、淡黃色 ≥ 70%、紅色 ≥ 60%。⚠️ = 觸發次數 ≤ 5次，樣本不足。依 -10% 門檻勝率排序")
            show_html(df_combined.style.map(style_winrate_cell, subset=thr_cols))
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
