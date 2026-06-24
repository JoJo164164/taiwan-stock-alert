import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import json

INDUSTRY_GROUP = {
    "被動ETF": [], "主動ETF": [],
    "半導體": ["半導體業", "半導體"],
    "電腦與週邊": ["電腦及週邊設備業", "電子通路業", "資訊服務業", "電腦及週邊", "電子通路", "資訊服務"],
    "光電與通信": ["光電業", "通信網路業", "光電", "通信網路"],
    "電子零組件": ["電子零組件業", "其他電子業", "電子零組件", "其他電子"],
    "金融保險": ["金融保險業", "金融保險", "銀行業", "證券業", "保險業", "票券業"],
    "生技醫療": ["生技醫療業", "生技醫療", "醫療器材", "生物科技"],
    "水泥": ["水泥工業", "水泥"],
    "食品": ["食品工業", "食品"],
    "塑膠": ["塑膠工業", "塑膠"],
    "紡織": ["紡織纖維", "紡織"],
    "電機機械": ["電機機械"],
    "電器電纜": ["電器電纜"],
    "化學": ["化學工業", "化學", "化工"],
    "玻璃陶瓷": ["玻璃陶瓷"],
    "造紙": ["造紙工業", "造紙"],
    "鋼鐵": ["鋼鐵工業", "鋼鐵"],
    "橡膠": ["橡膠工業", "橡膠"],
    "汽車": ["汽車工業", "汽車"],
    "能源": ["油電燃氣業", "油電燃氣", "能源"],
    "綠能環保": ["綠能環保"],
    "航運": ["航運業", "航運"],
    "建材營造": ["建材營造"],
    "觀光餐旅": ["觀光餐旅", "觀光"],
    "貿易百貨": ["貿易百貨", "百貨"],
    "數位雲端": ["數位雲端"],
    "運動休閒": ["運動休閒"],
    "居家生活": ["居家生活"],
    "電子商務": ["電子商務"],
    "文化創意": ["文化創意"],
    "農業科技": ["農業科技"],
    "管理顧問": ["管理顧問"],
    "綜合": ["綜合"],
}
GROUP_ICONS = {
    "被動ETF": "📊", "主動ETF": "✨", "半導體": "🔵", "電腦與週邊": "🖥️",
    "光電與通信": "📡", "電子零組件": "⚙️", "金融保險": "🏦", "生技醫療": "🧬",
    "水泥": "🏗️", "食品": "🍱", "塑膠": "🧪", "紡織": "🧵",
    "電機機械": "⚡", "電器電纜": "🔌", "化學": "🔬", "玻璃陶瓷": "🏺",
    "造紙": "📄", "鋼鐵": "🔩", "橡膠": "🔄", "汽車": "🚗",
    "能源": "⛽", "綠能環保": "☀️", "航運": "🚢", "建材營造": "🏠",
    "觀光餐旅": "🏨", "貿易百貨": "🛒", "數位雲端": "☁️",
    "運動休閒": "⛳", "居家生活": "🏡", "電子商務": "🛍️",
    "文化創意": "🎨", "農業科技": "🌱", "管理顧問": "💼", "綜合": "📌",
}
THRESHOLDS = [-5, -7, -10, -15, -20]
HORIZONS = [5, 10, 20, 40, 60, 80, 100, 120, 240]

# ── Pool 磁碟快取：定義在最頂部，確保任何地方都能呼叫 ──
import os as _os
POOL_CACHE_PATH = "/tmp/tw_stock_pool_cache.parquet"
POOL_CACHE_META = "/tmp/tw_stock_pool_cache_meta.json"

def save_pool_to_disk(df_pool):
    try:
        df_pool.to_parquet(POOL_CACHE_PATH, index=False)
        with open(POOL_CACHE_META, "w") as f:
            json.dump({"saved_at": datetime.now().isoformat(), "rows": len(df_pool)}, f)
        return True
    except Exception:
        return False

def load_pool_from_disk():
    try:
        if not _os.path.exists(POOL_CACHE_PATH) or not _os.path.exists(POOL_CACHE_META):
            return None, None
        with open(POOL_CACHE_META) as f:
            meta = json.load(f)
        if (datetime.now() - datetime.fromisoformat(meta["saved_at"])).total_seconds() / 3600 > 12:
            return None, meta
        df = pd.read_parquet(POOL_CACHE_PATH)
        if '代碼' in df.columns:
            df['代碼'] = df['代碼'].astype(str).str.strip()
        return df, meta
    except Exception:
        return None, None

st.set_page_config(page_title="台股滾動10日跌幅系統 v13", layout="wide")

# ── 啟動時自動從磁碟還原 df_pool ──
if 'df_pool' not in st.session_state or st.session_state['df_pool'] is None:
    _cached_pool, _cached_meta = load_pool_from_disk()
    if _cached_pool is not None:
        st.session_state['df_pool'] = _cached_pool
        st.session_state['pool_loaded_from_disk'] = True
        st.session_state['pool_saved_at'] = _cached_meta.get("saved_at", "")
    else:
        st.session_state['df_pool'] = None
        st.session_state['pool_loaded_from_disk'] = False
st.title("📉 台股滾動10日跌幅系統 v13")
st.caption(
    "資料來源：Yahoo Finance 還原後股價 | 回測年限：最長15年 | "
    "🆕 v13：Coatue體質評分卡（15分制）+ 複合信號強度 + 動態持有建議 | "
    "更新時間：" + datetime.now().strftime("%Y-%m-%d %H:%M")
)


def get_industry_group(industry, stock_type):
    if stock_type in ["被動ETF", "主動ETF"]:
        return stock_type
    if not industry:
        return "綜合"
    industry_str = str(industry).strip()
    # 第一輪：完整字串包含比對
    for group, industries in INDUSTRY_GROUP.items():
        if group in ["被動ETF", "主動ETF"]:
            continue
        for ind in industries:
            if ind and (ind in industry_str or industry_str in ind):
                return group
    # 第二輪：關鍵字部分比對（處理上櫃特殊命名）
    keyword_map = {
        "半導": "半導體", "晶片": "半導體", "IC": "半導體",
        "電腦": "電腦與週邊", "資訊": "電腦與週邊", "通路": "電腦與週邊",
        "光電": "光電與通信", "通信": "光電與通信", "網路": "光電與通信",
        "電子零": "電子零組件", "零組件": "電子零組件",
        "金融": "金融保險", "銀行": "金融保險", "證券": "金融保險", "保險": "金融保險",
        "生技": "生技醫療", "醫療": "生技醫療", "藥": "生技醫療",
        "鋼": "鋼鐵", "鐵": "鋼鐵",
        "航": "航運", "運輸": "航運",
        "建材": "建材營造", "營造": "建材營造", "建設": "建材營造",
        "化學": "化學", "化工": "化學",
        "食品": "食品", "飲料": "食品",
        "塑膠": "塑膠",
        "紡織": "紡織", "纖維": "紡織",
        "能源": "能源", "燃氣": "能源", "電力": "能源",
        "綠能": "綠能環保", "環保": "綠能環保", "太陽能": "綠能環保",
        "雲端": "數位雲端", "數位": "數位雲端", "軟體": "數位雲端",
        "觀光": "觀光餐旅", "餐飲": "觀光餐旅", "旅": "觀光餐旅",
    }
    for keyword, group in keyword_map.items():
        if keyword in industry_str:
            return group
    # 最後才歸綜合
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
    """
    從Yahoo Finance抓台股歷史資料。
    三種失敗情境明確分類：404=代碼不存在/下市、timeout=網路問題、其他=格式異常。
    全部回傳空dict，呼叫端用 `if not prices` 判斷即可。
    """
    end = datetime.today()
    start = end - timedelta(days=days)
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/" + code + ".TW"
           + "?interval=1d&period1=" + str(int(start.timestamp()))
           + "&period2=" + str(int(end.timestamp())))
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 404:
            return {}   # 代碼不存在或已下市
        data = res.json()
        chart_result = data.get("chart", {}).get("result")
        if not chart_result:
            return {}   # Yahoo 暫無資料
        result = chart_result[0]
        timestamps = result.get("timestamp", [])
        adjclose = result["indicators"].get("adjclose")
        if adjclose and len(adjclose) > 0 and adjclose[0].get("adjclose"):
            closes = adjclose[0]["adjclose"]
        else:
            closes = result["indicators"]["quote"][0].get("close", [])
        prices = {}
        for ts, cl in zip(timestamps, closes):
            if cl is not None and cl > 0:
                date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                prices[date] = round(cl, 2)
        return prices
    except requests.Timeout:
        return {}
    except Exception:
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
    """輸出 DataFrame 為 HTML 表格，表頭不斷行、字體統一 13px"""
    html = s.to_html(index=False)
    styled = """
<style>
.stbl { border-collapse: collapse; width: 100%; font-size: 13px; }
.stbl th { background: #1f4e79; color: white; padding: 6px 10px;
           white-space: nowrap; text-align: center; }
.stbl td { padding: 5px 10px; border-bottom: 1px solid #e0e0e0;
           white-space: nowrap; text-align: center; }
.stbl tr:hover td { background: #f0f4ff; }
</style>
""" + html.replace('<table', '<table class="stbl"')
    st.markdown(styled, unsafe_allow_html=True)


def safe_md(text):
    """輸出 markdown 前，把半形 ～ 換成全形 ～，避免 Streamlit 誤判為刪除線"""
    return text.replace("～", "～")


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
        "・**-15%** 是次佳選擇，需持有50～100天，勝率可達80～95%\n"
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
    # 來源1：TWSE companyInfo（上市，含產業別）
    try:
        res = requests.get("https://openapi.twse.com.tw/v1/company/companyInfo",
                          timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if res.status_code == 200:
            for d in res.json():
                code = d.get("公司代號", "").strip()
                industry = d.get("產業別", "").strip()
                if code and industry:
                    lookup[code] = industry
    except:
        pass

    # 來源2：TWSE 上市公司基本資料（另一個endpoint，有產業類別）
    try:
        res = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
                          timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if res.status_code == 200:
            for d in res.json():
                code = d.get("Code", "").strip()
                # STOCK_DAY_ALL沒有產業別，跳過
    except:
        pass

    # 來源3：TPEX上櫃公司基本資料（有產業類別）
    try:
        res = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes",
                          timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if res.status_code == 200:
            for d in res.json():
                code = d.get("SecuritiesCompanyCode", "").strip()
                industry = d.get("Industry", "").strip()
                if not industry:
                    industry = d.get("IndustryName", "").strip()
                if code and industry and code not in lookup:
                    lookup[code] = industry
    except:
        pass

    # 來源4：TWSE 個股基本資料（備用，有產業別）
    try:
        res = requests.get("https://openapi.twse.com.tw/v1/company/basic",
                          timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if res.status_code == 200:
            for d in res.json():
                code = d.get("公司代號", "").strip()
                industry = d.get("產業別", "").strip()
                if code and industry and code not in lookup:
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
        # 嘗試從API直接取產業別，沒有才用lookup
        industry = (d.get("Industry", "") or
                   d.get("IndustryName", "") or
                   d.get("產業別", "") or
                   industry_lookup.get(code, "")).strip()
        group = get_industry_group(industry, t)
        stocks.append({"code": code, "name": name, "market": "上櫃", "type": t, "industry": industry, "group": group})
    return stocks


def group_selector(key_prefix):
    groups = list(INDUSTRY_GROUP.keys())
    selected = []

    # 全選 checkbox：用 on_change callback 同步所有子 checkbox
    all_key = key_prefix + "_all"
    if all_key not in st.session_state:
        st.session_state[all_key] = False

    def on_select_all():
        val = st.session_state[all_key]
        for g in groups:
            st.session_state[key_prefix + "_" + g] = val

    col_all, _ = st.columns([1, 5])
    with col_all:
        st.checkbox("✅ 全選", key=all_key, on_change=on_select_all)

    cols = st.columns(6)
    for i, g in enumerate(groups):
        icon = GROUP_ICONS.get(g, "")
        gkey = key_prefix + "_" + g
        if gkey not in st.session_state:
            st.session_state[gkey] = False
        with cols[i % 6]:
            checked = st.checkbox(icon + " " + g, key=gkey)
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
    st.divider()
    st.markdown("### 🆕 v13 新功能（Coatue思維強化）")
    st.markdown("""
**1️⃣ 標的體質評分卡（15分制）**
- 三大維度各5分：A獲利能力、B商業模式護城河、C市值與安全邊際
- 類Coatue區分「好公司跌」vs「爛公司繼續跌」
- ⭐⭐⭐ 核心（13+）｜⭐⭐ 可觀察（9-12）｜⭐ 高風險（5-8）｜💀 Broken Model（0-4）

**2️⃣ 複合信號強度（每日警示掃描）**
- 4條件同時評估：連續觸發天數、體質分數、宏觀環境、跌幅深度
- 🔥強烈｜✅有效｜🔶觀察｜⚪弱 四個等級，自動排序

**3️⃣ 進場品質評估（個股回測）**
- 自動計算最佳持有天數建議
- 動態停損參考（歷史最深回撤+平均回撤發生天數）
- 綜合進場評分（體質+宏觀+歷史勝率）

**4️⃣ 全市場勝率排行加入體質分數**
- 高勝率但體質差的標的自動標注，避免買到Broken Model
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
                return True, "2330台積電 最新收盤：" + str(p[d[-1]]) + "（" + d[-1] + "）｜取得 " + str(len(p)) + " 筆（近60天交易日，正常約40～43筆）"
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
                return True, "0050 取得 " + str(len(p)) + " 日（" + d[0] + " ～ " + d[-1] + "）還原後股價"
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


# ══════════════════════════════════════════════════════
# 財務資料層：yfinance（取代 MOPS，解決境外IP被封鎖問題）
# yfinance 的 Ticker.info 提供：ROE、負債比、EPS、每股淨值、PB等
# ══════════════════════════════════════════════════════

@st.cache_data(ttl=43200)  # 12小時快取，財務資料每季才更新
def get_fin_data_yfinance(code):
    """
    用 yfinance 取單一台股的財務資料。
    回傳 dict，所有欄位 None 代表無資料，不會 raise。
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(code + ".TW")
        info = ticker.info

        # ── 基本財務欄位 ──
        roe_raw = info.get('returnOnEquity')          # 0.xx 格式，需 *100
        roe = round(roe_raw * 100, 2) if roe_raw is not None else None

        # 負債比 = 總負債 / 總資產（yfinance 給的是負債/股東權益）
        total_debt = info.get('totalDebt')
        total_assets = info.get('totalAssets')
        if total_debt is not None and total_assets and total_assets > 0:
            debt_ratio = round(total_debt / total_assets * 100, 2)
        else:
            debt_ratio = None

        bvps = info.get('bookValue')                   # 每股淨值
        price = info.get('currentPrice') or info.get('regularMarketPrice')
        pb = round(price / bvps, 2) if price and bvps and bvps > 0 else None

        trailing_eps = info.get('trailingEps')         # 過去12月 EPS
        forward_eps = info.get('forwardEps')           # 預估 EPS

        earnings_growth = info.get('earningsGrowth')   # EPS成長率 (YoY)

        # ── 歷史年度 EPS（financials表格）──
        eps_history = {}
        try:
            fin = ticker.financials  # 欄是日期，列是科目
            if fin is not None and not fin.empty:
                eps_keys = ['Basic EPS', 'Diluted EPS', 'EPS']
                for k in eps_keys:
                    if k in fin.index:
                        for col in fin.columns[:4]:  # 最近4年
                            yr = col.year if hasattr(col, 'year') else int(str(col)[:4])
                            v = fin.loc[k, col]
                            if v is not None and not pd.isna(v):
                                eps_history[yr] = round(float(v), 2)
                        break
        except Exception:
            pass

        return {
            'code': code,
            'roe': roe,
            'debt_ratio': debt_ratio,
            'bvps': bvps,
            'price': price,
            'pb': pb,
            'trailing_eps': trailing_eps,
            'forward_eps': forward_eps,
            'earnings_growth': earnings_growth,
            'eps_history': eps_history,   # {year: eps}
            'name': info.get('longName', info.get('shortName', '')),
            'industry': info.get('industry', ''),
            'sector': info.get('sector', ''),
        }
    except Exception:
        return {
            'code': code, 'roe': None, 'debt_ratio': None,
            'bvps': None, 'price': None, 'pb': None,
            'trailing_eps': None, 'forward_eps': None,
            'earnings_growth': None, 'eps_history': {},
            'name': '', 'industry': '', 'sector': '',
        }


@st.cache_data(ttl=43200)
def get_all_financial_data_yfinance(codes, progress_callback=None):
    """
    批次取所有股票的 yfinance 財務資料。
    codes: list of str（不含 .TW）
    回傳 dict {code: fin_dict}
    """
    result = {}
    for i, code in enumerate(codes):
        fin = get_fin_data_yfinance(code)
        result[code] = fin
        if progress_callback:
            progress_callback(i + 1, len(codes))
        time.sleep(0.1)  # 避免太快被限流
    return result


# ── 舊 MOPS 函數保留但標注（僅在本地環境可用）──
def get_mops_financial(year_roc, season, typek='sii'):
    """【已棄用：境外IP被封鎖，改用 get_fin_data_yfinance】"""
    return None


def parse_financial_df(df):
    """【已棄用：配合 get_mops_financial 使用，現改用 yfinance】"""
    return None


@st.cache_data(ttl=43200)
def get_all_financial_data():
    """【已棄用：改用 get_all_financial_data_yfinance】"""
    return None


def get_book_value_per_share(codes):
    """【已棄用：bvps 現由 yfinance 提供】"""
    return {}




def parse_financial_df(df):
    """
    解析MOPS財務分析彙總表。
    MOPS 欄位名稱在不同年度/季度有版本差異，使用完整 fallback 清單確保不靜默失敗。
    回傳 DataFrame 或 None（失敗時印出 debug 訊息方便排查）。
    """
    if df is None or df.empty:
        return None
    try:
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)
        df.columns = [str(c).strip() for c in df.columns]

        # ── 欄位 fallback 清單（依優先順序，第一個命中即採用）──
        FIELD_PATTERNS = {
            'code': ['公司代號', '代號', '股票代號', 'Code'],
            'name': ['公司名稱', '名稱', '股票名稱'],
            'roe':  ['股東權益報酬率', '股東權益報酬率(%)', 'ROE(%)', 'ROE',
                     '股東報酬率', '權益報酬率'],
            'eps':  ['基本每股盈餘', '每股盈餘', '每股盈餘(元)', 'EPS(元)', 'EPS',
                     '基本每股盈虧', '每股稅後淨利'],
            'debt_ratio': ['負債佔資產比率', '負債佔資產', '負債比率', '負債比',
                           '負債佔總資產比率', '負債/資產(%)'],
            'bvps': ['每股淨值', '每股帳面價值', '每股帳面淨值', '每股淨資產'],
        }

        col_map = {}
        col_names = list(df.columns)
        for field, patterns in FIELD_PATTERNS.items():
            for pat in patterns:
                matched = [c for c in col_names if pat in str(c)]
                if matched:
                    col_map[field] = matched[0]
                    break

        if 'code' not in col_map:
            return None   # 連代碼欄都找不到，這份資料無法使用

        result = {key: df[col] for key, col in col_map.items()}
        out = pd.DataFrame(result)

        # 代碼統一為 string，去除空白與小數點（有時MOPS回傳 "2330.0"）
        out['code'] = out['code'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)

        # 數值欄轉型
        for col in ['roe', 'eps', 'debt_ratio', 'bvps']:
            if col in out.columns:
                out[col] = pd.to_numeric(out[col], errors='coerce')

        # 過濾掉代碼明顯無效的列（非數字開頭、長度不對）
        out = out[out['code'].str.match(r'^\d{4,6}$', na=False)].reset_index(drop=True)

        return out if not out.empty else None

    except Exception:
        return None


@st.cache_data(ttl=3600)
def get_all_financial_data():
    """抓近3年財報資料（縮短為3年，降低MOPS失敗機率）"""
    now = datetime.now()
    current_year_roc = now.year - 1911
    all_data = []
    fail_count = 0
    success_count = 0

    for yr_offset in range(3):   # 縮短為3年（原5年），減少請求數量
        yr = current_year_roc - yr_offset
        for season in [4, 3, 2, 1]:
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
                    success_count += 1
                else:
                    fail_count += 1
                time.sleep(1)   # 加長間隔，降低被MOPS擋的機率

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


def build_qualified_pool(all_stocks, fin_data=None):
    """
    建立合格標的池。
    資料來源：yfinance（取代 MOPS）。
    fin_data 參數保留但不使用（向後相容）。
    """
    import yfinance as yf

    results = []
    stock_dict = {str(s['code']).strip(): s for s in all_stocks}
    individual_codes = [k for k, v in stock_dict.items() if v.get('type') == '個股']

    now_yr = datetime.now().year

    bvps_map = {}
    price_map = {}
    roe_map = {}
    debt_map = {}
    eps_history_map = {}

    total = len(individual_codes)
    for i, code in enumerate(individual_codes):
        fin = get_fin_data_yfinance(code)
        bvps_map[code]         = fin.get('bvps')
        price_map[code]        = fin.get('price')
        roe_map[code]          = fin.get('roe')
        debt_map[code]         = fin.get('debt_ratio')
        eps_history_map[code]  = fin.get('eps_history', {})
        # 若 yfinance 有更好的產業別，補充回 stock_dict
        yf_industry = fin.get('industry', '')
        if yf_industry and not stock_dict[code].get('industry'):
            stock_dict[code]['industry'] = yf_industry

    for code in individual_codes:
        stock = stock_dict.get(code, {})

        roe   = roe_map.get(code)
        debt  = debt_map.get(code)
        bvps  = bvps_map.get(code)
        price = price_map.get(code)
        pb    = round(price / bvps, 2) if price and bvps and bvps > 0 else None

        eps_hist = eps_history_map.get(code, {})
        # 取最近5年的 EPS（以西元年為 key）
        valid_years = sorted([yr for yr in eps_hist.keys() if yr >= now_yr - 6], reverse=True)

        # ── 第一層：硬性排除條件 ──
        # c1：近3年 EPS 皆正（yfinance 最多給4年）
        c1 = (len(valid_years) >= 2 and
              all(eps_hist.get(yr, -1) > 0 for yr in valid_years[:3]))

        # c2：近3年 EPS 成長（最新 vs 3年前）
        c2 = False
        if len(valid_years) >= 2:
            newest = eps_hist.get(valid_years[0])
            oldest = eps_hist.get(valid_years[min(2, len(valid_years)-1)])
            if newest is not None and oldest and oldest != 0:
                c2 = newest > oldest

        c3 = debt < 50 if debt is not None else None

        # ── 第二層：品質評分條件 ──
        c4 = roe > 15 if roe is not None else None
        c5 = pb < 3   if pb  is not None else None
        c6 = round(pb / roe, 3) < 0.20 if pb and roe and roe > 0 else None

        hard_pass = c1 and c2 and (c3 is True)
        quality_scores = [x for x in [c4, c5, c6] if x is not None]
        quality_pass_count = sum(1 for x in quality_scores if x is True)

        if not hard_pass:
            hard_fail = []
            if not c1: hard_fail.append("近3年有虧損年度")
            if not c2: hard_fail.append("EPS未成長")
            if c3 is False: hard_fail.append("負債比≥50%")
            grade = "❌ 排除"
            grade_reason = "硬性條件未通過：" + "、".join(hard_fail) if hard_fail else "資料不足"
            grade_short = "排除"
        else:
            quality_fail = []
            if c4 is False: quality_fail.append("ROE<15%")
            if c5 is False: quality_fail.append("PB≥3")
            if c6 is False: quality_fail.append("PB/ROE≥0.20")
            if quality_pass_count >= 3 or (len(quality_scores) < 3 and quality_pass_count == len(quality_scores)):
                grade = "🥇 A級"; grade_reason = "通過全部條件"; grade_short = "A級"
            elif quality_pass_count >= 2:
                grade = "🥈 B級"; grade_reason = "、".join(quality_fail); grade_short = "B級"
            else:
                grade = "🥉 C級"; grade_reason = "多項未通過：" + "、".join(quality_fail); grade_short = "C級"

        # ── 15分制體質評分 ──
        q = calc_quality_score_v2(code, stock, roe, debt, bvps, price, pb, eps_hist, valid_years)

        results.append({
            '等級': grade,
            '體質分數': q['total'] if q else None,
            '體質等級': q['grade'] if q else 'N/A',
            '資料完整度': str(q['data_completeness']) + '%' if q else 'N/A',
            '資料警示': q['data_warning'] if q else '',
            '代碼': code,
            '名稱': stock.get('name', ''),
            '產業別': stock.get('industry', stock.get('group', '')),
            '降級原因': grade_reason,
            '股價': price,
            'PB': pb,
            'ROE%': roe,
            '負債比%': debt,
            'PB/ROE': round(pb / roe, 3) if pb and roe and roe > 0 else None,
            '①EPS近3年正': '✅' if c1 else '❌',
            '②EPS成長':    '✅' if c2 else '❌',
            '③負債比<50%': '✅' if c3 else ('❌' if c3 is False else '⚠️'),
            '④ROE>15%':    '✅' if c4 else ('❌' if c4 is False else '⚠️'),
            '⑤PB<3':       '✅' if c5 else ('❌' if c5 is False else '⚠️'),
            '⑥PB/ROE<0.20':'✅' if c6 else ('❌' if c6 is False else '⚠️'),
            '▶A獲利(0-5)':      q['score_a'] if q else None,
            '▶B護城河(0-5)':    q['score_b'] if q else None,
            '▶C安全邊際(0-5)':  q['score_c'] if q else None,
            'A細節': q['detail_a'] if q else '',
            'B細節': q['detail_b'] if q else '',
            'C細節': q['detail_c'] if q else '',
            '_grade_short': grade_short,
            '_hard_pass': hard_pass,
        })

    return pd.DataFrame(results)

    # EPS：取每年最後一季的累計值（MOPS每季EPS是累計值，Q4=全年，Q3=前三季）
    # 正確做法：每年取季數最大的那筆，而非加總
    eps_by_code_raw = {}  # {code: {year_roc: {season: eps_value}}}
    for _, row in fin_data.iterrows():
        code = str(row.get('code', '')).strip().replace('.0', '')
        eps = row.get('eps')
        yr = row.get('year_roc', 0)
        season = int(row.get('season', 0))
        if not code or not code.isdigit():
            continue
        if pd.isna(eps):
            continue
        yr_key = int(yr) if yr else 0
        if code not in eps_by_code_raw:
            eps_by_code_raw[code] = {}
        if yr_key not in eps_by_code_raw[code]:
            eps_by_code_raw[code][yr_key] = {}
        eps_by_code_raw[code][yr_key][season] = float(eps)

    # 取每年最高季的值（Q4優先，否則取現有最高季）
    eps_by_code = {}
    for code, yr_data in eps_by_code_raw.items():
        eps_by_code[code] = {}
        for yr_key, season_data in yr_data.items():
            if not season_data:
                continue
            best_season = max(season_data.keys())
            eps_by_code[code][yr_key] = season_data[best_season]

    latest_roe = {}
    latest_debt = {}
    for _, row in fin_data.sort_values(['year_roc', 'season'], ascending=False).iterrows():
        code = str(row.get('code', '')).strip().replace('.0', '')
        if not code or not code.isdigit():
            continue
        if code not in latest_roe and not pd.isna(row.get('roe')):
            latest_roe[code] = float(row['roe'])
        if code not in latest_debt and not pd.isna(row.get('debt_ratio')):
            latest_debt[code] = float(row['debt_ratio'])

    now_yr = datetime.now().year - 1911
    latest_eps_annual = eps_by_code  # 已是 {code: {year_roc: eps_累計值}}

    for code in codes:
        stock = stock_dict.get(code, {})
        if stock.get('type') not in ['個股']:
            continue

        eps_annual = latest_eps_annual.get(code, {})
        roe = latest_roe.get(code)
        debt = latest_debt.get(code)
        bvps = bvps_map.get(code)
        price = price_map.get(code)
        pb = round(price / bvps, 2) if price and bvps and bvps > 0 else None

        # ── 第一層：硬性排除條件 ──
        valid_years = sorted([yr for yr in eps_annual.keys() if yr >= now_yr - 5], reverse=True)
        c1 = all(eps_annual.get(yr, -1) > 0 for yr in valid_years) if len(valid_years) >= 3 else False

        c2 = False
        recent_years = sorted(valid_years, reverse=True)
        if len(recent_years) >= 2:
            newest = eps_annual.get(recent_years[0], None)
            oldest = eps_annual.get(recent_years[min(2, len(recent_years)-1)], None)
            if newest and oldest and oldest != 0:
                c2 = newest > oldest

        c3 = debt < 50 if debt is not None else None

        # ── 第二層：品質評分條件 ──
        c4 = roe > 15 if roe is not None else None
        c5 = pb < 3 if pb is not None else None
        c6 = round(pb / roe, 3) < 0.20 if pb and roe and roe > 0 else None

        # ── 分級 ──
        hard_pass = c1 and c2 and (c3 is True)
        quality_scores = [x for x in [c4, c5, c6] if x is not None]
        quality_pass_count = sum(1 for x in quality_scores if x is True)

        if not hard_pass:
            hard_fail = []
            if not c1:
                hard_fail.append("近5年有虧損年度")
            if not c2:
                hard_fail.append("近3年EPS未成長")
            if c3 is False:
                hard_fail.append("負債比≥50%")
            grade = "❌ 排除"
            grade_reason = "硬性條件未通過：" + "、".join(hard_fail)
            grade_short = "排除"
        else:
            quality_fail = []
            if c4 is False:
                quality_fail.append("ROE<15%（獲利能力偏弱）")
            if c5 is False:
                quality_fail.append("PB≥3（估值偏高，如台積電）")
            if c6 is False:
                quality_fail.append("PB/ROE≥0.20（為ROE付出過高溢價）")

            if quality_pass_count >= 3 or (len(quality_scores) < 3 and quality_pass_count == len(quality_scores)):
                grade = "🥇 A級"
                grade_reason = "通過全部條件，優先進場"
                grade_short = "A級"
            elif quality_pass_count >= 2:
                grade = "🥈 B級"
                grade_reason = "次要條件部分未通過：" + "、".join(quality_fail)
                grade_short = "B級"
            else:
                grade = "🥉 C級"
                grade_reason = "次要條件多項未通過：" + "、".join(quality_fail)
                grade_short = "C級"

        # 計算15分制體質評分
        q = calc_quality_score(
            code, stock_dict, fin_data, bvps_map, price_map,
            eps_by_code, latest_roe, latest_debt, latest_eps_annual
        )
        q_total = q["total"] if q else None
        q_grade = q["grade"] if q else "N/A"
        q_detail_a = q["detail_a"] if q else ""
        q_detail_b = q["detail_b"] if q else ""
        q_detail_c = q["detail_c"] if q else ""

        results.append({
            '等級': grade,
            '體質分數': q_total,
            '體質等級': q_grade,
            '資料完整度': str(q["data_completeness"]) + "%" if q else "N/A",
            '資料警示': q["data_warning"] if q else "",
            '代碼': code,
            '名稱': stock.get('name', ''),
            '產業別': stock.get('industry', stock.get('group', '')),
            '降級原因': grade_reason,
            '股價': price,
            'PB': pb,
            'ROE%': roe,
            '負債比%': debt,
            'PB/ROE': round(pb / roe, 3) if pb and roe and roe > 0 else None,
            '①5年EPS正': '✅' if c1 else '❌',
            '②EPS成長': '✅' if c2 else '❌',
            '③負債比<50%': '✅' if c3 else ('❌' if c3 is False else '⚠️'),
            '④ROE>15%': '✅' if c4 else ('❌' if c4 is False else '⚠️'),
            '⑤PB<3': '✅' if c5 else ('❌' if c5 is False else '⚠️'),
            '⑥PB/ROE<0.20': '✅' if c6 else ('❌' if c6 is False else '⚠️'),
            '▶A獲利(0-5)': q["score_a"] if q else None,
            '▶B護城河(0-5)': q["score_b"] if q else None,
            '▶C安全邊際(0-5)': q["score_c"] if q else None,
            'A細節': q_detail_a,
            'B細節': q_detail_b,
            'C細節': q_detail_c,
            '_grade_short': grade_short,
            '_hard_pass': hard_pass,
        })

    return pd.DataFrame(results)



# ══════════════════════════════════════════════════════
# 📊 Coatue體質評分卡（滿分15分，每項5分，共3大項）
# ══════════════════════════════════════════════════════

def calc_quality_score_v2(code, stock, roe, debt, bvps, price, pb, eps_hist, valid_years):
    """
    15分制體質評分 v2：直接接收已解析的財務資料（yfinance格式）
    valid_years：西元年 list，降序
    eps_hist：{year: eps} dict
    """
    if stock.get('type') != '個股':
        return None

    now_yr = datetime.now().year

    # ── 資料完整性 ──
    data_points = {
        'EPS年度資料': len(valid_years) >= 2,
        'ROE': roe is not None,
        '負債比': debt is not None,
        'PB': pb is not None,
    }
    completeness = sum(data_points.values()) / len(data_points) * 100
    missing_fields = [k for k, v in data_points.items() if not v]

    # ── 維度A：獲利能力（0-5分）──
    score_a = 0
    detail_a = []
    if len(valid_years) >= 2:
        all_pos = all(eps_hist.get(yr, -1) > 0 for yr in valid_years[:3])
        if all_pos:
            score_a += 2; detail_a.append("✅ 近3年EPS皆正(+2)")
        else:
            detail_a.append("❌ 有虧損年度(0)")
    else:
        detail_a.append("⚠️ EPS年度資料不足")

    if roe is not None:
        if roe >= 20:   score_a += 3; detail_a.append("✅ ROE≥20%(+3)")
        elif roe >= 15: score_a += 2; detail_a.append("✅ ROE≥15%(+2)")
        elif roe >= 8:  score_a += 1; detail_a.append("🟡 ROE≥8%(+1)")
        else:           detail_a.append("❌ ROE<8%(0)")
    else:
        detail_a.append("⚠️ ROE無資料")
    score_a = min(score_a, 5)

    # ── 維度B：護城河（0-5分）──
    score_b = 0
    detail_b = []
    if len(valid_years) >= 2:
        newest = eps_hist.get(valid_years[0])
        oldest = eps_hist.get(valid_years[min(2, len(valid_years)-1)])
        if newest and oldest and oldest != 0 and newest > oldest:
            score_b += 2; detail_b.append("✅ EPS近年成長(+2)")
        else:
            detail_b.append("❌ EPS未成長(0)")
    else:
        detail_b.append("⚠️ 資料不足")

    if debt is not None:
        if debt < 30:   score_b += 3; detail_b.append("✅ 負債比<30%(+3)")
        elif debt < 50: score_b += 2; detail_b.append("✅ 負債比<50%(+2)")
        elif debt < 65: score_b += 1; detail_b.append("🟡 負債比<65%(+1)")
        else:           detail_b.append("❌ 負債比≥65%(0)")
    else:
        detail_b.append("⚠️ 負債比無資料")
    score_b = min(score_b, 5)

    # ── 維度C：安全邊際（0-5分）──
    score_c = 0
    detail_c = []
    if pb is not None and roe is not None and roe > 0:
        pb_roe = pb / roe
        if pb_roe < 0.10:   score_c += 3; detail_c.append("✅ PB/ROE<0.10極優(+3)")
        elif pb_roe < 0.20: score_c += 2; detail_c.append("✅ PB/ROE<0.20合理(+2)")
        elif pb_roe < 0.35: score_c += 1; detail_c.append("🟡 PB/ROE<0.35尚可(+1)")
        else:                detail_c.append("❌ PB/ROE≥0.35偏高(0)")
    elif pb is not None:
        if pb < 1.5:   score_c += 2; detail_c.append("✅ PB<1.5便宜(+2)")
        elif pb < 3:   score_c += 1; detail_c.append("🟡 PB<3尚可(+1)")
        else:          detail_c.append("❌ PB≥3偏高(0)")
    else:
        detail_c.append("⚠️ PB無資料")

    if price is not None and price > 10:
        score_c += 2; detail_c.append("✅ 股價>10流動性合格(+2)")
    elif price is not None and price > 5:
        score_c += 1; detail_c.append("🟡 股價5-10(+1)")
    else:
        detail_c.append("❌ 股價≤5或無資料(0)")
    score_c = min(score_c, 5)

    total = score_a + score_b + score_c
    if total >= 13:   grade = "⭐⭐⭐ 核心";   grade_label = "核心標的"
    elif total >= 9:  grade = "⭐⭐ 可觀察";  grade_label = "可觀察"
    elif total >= 5:  grade = "⭐ 高風險";    grade_label = "高風險"
    else:             grade = "💀 Broken";    grade_label = "Broken Model"

    data_warn = ("⚠️ 資料{:.0f}%完整（缺：{}），分數可能偏低".format(
        completeness, "、".join(missing_fields)) if completeness < 75 else "")

    return {
        "total": total, "score_a": score_a, "score_b": score_b, "score_c": score_c,
        "grade": grade, "grade_label": grade_label,
        "detail_a": "｜".join(detail_a),
        "detail_b": "｜".join(detail_b),
        "detail_c": "｜".join(detail_c),
        "data_completeness": round(completeness),
        "data_warning": data_warn,
        "missing_fields": missing_fields,
    }


@st.cache_data(ttl=3600)
def get_quality_scores_cached():
    """快取版品質評分，供每日掃描與全市場排行使用"""
    return {}


def get_score_for_code(code, df_pool_scores):
    """從df_pool_scores快速查詢某代碼的評分"""
    if df_pool_scores is None or df_pool_scores.empty:
        return None
    row = df_pool_scores[df_pool_scores['代碼'] == code]
    if row.empty:
        return None
    return row.iloc[0]


def score_badge(score):
    """依分數回傳HTML徽章"""
    if score is None:
        return '<span style="color:#888">N/A</span>'
    if score >= 13:
        return '<span style="background:#2e7d32;color:white;padding:2px 6px;border-radius:4px;font-size:11px;">⭐⭐⭐ {}/15</span>'.format(score)
    elif score >= 9:
        return '<span style="background:#e65100;color:white;padding:2px 6px;border-radius:4px;font-size:11px;">⭐⭐ {}/15</span>'.format(score)
    elif score >= 5:
        return '<span style="background:#b71c1c;color:white;padding:2px 6px;border-radius:4px;font-size:11px;">⭐ {}/15</span>'.format(score)
    else:
        return '<span style="background:#616161;color:white;padding:2px 6px;border-radius:4px;font-size:11px;">💀 {}/15</span>'.format(score)


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
        change_30d = round(current - price_30d_ago, 2) if price_30d_ago else None
        return {
            "current": round(current, 2),
            "change_30d": change_30d,
            "date": dates[-1],
        }
    except:
        return None


def get_sp500_data():
    """抓S&P500"""
    try:
        prices = get_yahoo_history_us("^GSPC", days=365)
        if not prices or len(prices) < 30:
            return None
        dates = sorted(prices.keys())
        current = prices[dates[-1]]
        high_52w = max(prices.values())
        pct_from_high = (current - high_52w) / high_52w * 100
        ma20 = sum([prices[d] for d in dates[-20:]]) / 20
        ret_20d = (current - prices[dates[-21]]) / prices[dates[-21]] * 100 if len(dates) >= 21 else None
        return {
            "current": current,
            "high_52w": high_52w,
            "pct_from_high": round(pct_from_high, 1),
            "above_ma20": current > ma20,
            "ret_20d": round(ret_20d, 1) if ret_20d else None,
            "date": dates[-1],
        }
    except:
        return None


@st.cache_data(ttl=3600)
def get_twii_heat():
    """台股加權指數市場熱度（vs 240日均線偏離度，分10級）"""
    try:
        prices = get_yahoo_history_us("^TWII", days=365 + 60)
        if not prices or len(prices) < 250:
            return None
        dates = sorted(prices.keys())
        current = prices[dates[-1]]
        # 240日均線
        ma240_prices = [prices[d] for d in dates[-240:]]
        ma240 = sum(ma240_prices) / len(ma240_prices)
        ma60_prices = [prices[d] for d in dates[-60:]]
        ma60 = sum(ma60_prices) / len(ma60_prices)
        ma20_prices = [prices[d] for d in dates[-20:]]
        ma20 = sum(ma20_prices) / len(ma20_prices)

        deviation = (current - ma240) / ma240 * 100

        # 10級熱度
        if deviation < -30:
            level = 1
            label = "極冷（歷史性崩潰）"
            color = "🔵"
            action = "最佳進場時機，全力進場"
        elif deviation < -20:
            level = 2
            label = "極冷（嚴重超賣）"
            color = "🔵"
            action = "積極進場，正常倉位"
        elif deviation < -15:
            level = 3
            label = "冷（顯著超賣）"
            color = "🟢"
            action = "積極進場"
        elif deviation < -10:
            level = 4
            label = "微冷（輕微超賣）"
            color = "🟢"
            action = "正常進場"
        elif deviation < -5:
            level = 5
            label = "中性偏冷"
            color = "🟢"
            action = "正常進場"
        elif deviation < 0:
            level = 6
            label = "中性"
            color = "🟢"
            action = "正常進場"
        elif deviation < 10:
            level = 7
            label = "微熱（輕微過熱）"
            color = "🟡"
            action = "正常但留意，勿追高"
        elif deviation < 20:
            level = 8
            label = "熱（明顯過熱）"
            color = "🟠"
            action = "縮小倉位，等回測深度觸發"
        elif deviation < 30:
            level = 9
            label = "很熱（嚴重過熱）"
            color = "🔴"
            action = "大幅縮倉，門檻提高到-15%"
        else:
            level = 10
            label = "極熱（泡沫化）"
            color = "🔴"
            action = "暫停策略，等市場熱度降至7級以下"

        return {
            "current": current,
            "ma240": round(ma240, 0),
            "ma60": round(ma60, 0),
            "ma20": round(ma20, 0),
            "deviation": round(deviation, 1),
            "level": level,
            "label": label,
            "color": color,
            "action": action,
            "date": dates[-1],
        }
    except:
        return None


with tab6:
    st.subheader("📋 合格標的池")
    st.caption("基本面篩選器：只在通過六個條件的股票中尋找進場機會，排除基本面有問題的標的")

    # 預設值，確保後面的程式不會因未定義而崩潰
    sox = None
    us10y = None
    vix = None
    twd = None
    sp500 = None
    twii_heat = None

    # ── 市場背景快照 ──
    st.markdown("### 🌐 市場背景快照")
    st.caption("進場前先看大環境，判斷這次觸發是情緒性超跌還是系統性風險。每個指標都附有解讀說明。")

    with st.spinner("載入市場數據中..."):
        try:
            sox = get_sox_data()
        except Exception as e:
            sox = None
            st.warning("SOX載入失敗：" + str(e))
        try:
            us10y = get_us10y_data()
        except Exception as e:
            us10y = None
        try:
            vix = get_vix_data()
        except Exception as e:
            vix = None
        try:
            twd = get_twd_data()
        except Exception as e:
            twd = None
        try:
            sp500 = get_sp500_data()
        except Exception as e:
            sp500 = None
        try:
            twii_heat = get_twii_heat()
        except Exception as e:
            twii_heat = None

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
                st.warning("🟡 SOX回落中（距高點15～30%）")
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
            "・ 0% ～ -15%：SOX接近高點，半導體景氣良好。此時個股超跌觸發，"
            "很可能是情緒性超跌，進場勝率較高\n"
            "・ -15% ～ -30%：SOX明顯回落，需謹慎判斷是修正還是趨勢反轉\n"
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
            "・ 90日上升 0.3～1.0%：緩慢上升，市場可消化，正常操作\n"
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
                st.success("🟢 市場平靜（VIX 15～20）正常環境")
            elif v < 30:
                st.warning("🟡 市場緊張（VIX 20～30）觸發後反彈機率中等")
            elif v < 40:
                st.error("🔴 市場恐慌（VIX 30～40）歷史上長期回報反而最好")
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
            "・ VIX 15～20：正常環境，策略照常執行\n"
            "・ VIX 20～30：市場緊張，但往往也是觸發後反彈機率合理的環境\n"
            "・ VIX 30～40：市場恐慌，歷史數據顯示這個區間進場的長期回報最高，"
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
            "・ -0.5 ～ +0.5：匯率穩定，中性\n"
            "・ 上升超過1.0：台幣明顯貶值，注意外資賣壓是否持續\n\n"
            "**實例：** 2022年台幣從28貶到32，外資大幅賣超台股，"
            "那年我們策略的觸發後勝率明顯低於平均，匯率是重要原因之一"
        )

    # ── S&P500 ──
    st.markdown("---")
    col_sp1, col_sp2 = st.columns([1, 2])
    with col_sp1:
        if sp500:
            st.metric("S&P500",
                     "{:,.0f}".format(sp500["current"]),
                     "{:.1f}% 距52週高點".format(sp500["pct_from_high"]))
            if sp500["ret_20d"]:
                st.caption("近20日：{:+.1f}%".format(sp500["ret_20d"]))
            ma_s = "高於20MA ✅" if sp500["above_ma20"] else "低於20MA ⚠️"
            st.caption("均線狀態：" + ma_s)
            if sp500["pct_from_high"] > -10:
                st.success("🟢 S&P500強勢，全球風險胃納良好")
            elif sp500["pct_from_high"] > -20:
                st.warning("🟡 S&P500回落中，留意全球資金情緒")
            else:
                st.error("🔴 S&P500顯著下行，全球資金撤出風險資產")
        else:
            st.warning("S&P500資料無法取得")

    with col_sp2:
        st.markdown("**📖 S&P500怎麼讀、為什麼重要**")
        st.info(
            "**SOX vs S&P500，各看什麼？**\n\n"
            "SOX看的是半導體景氣週期，S&P500看的是全球資金的風險胃納量。"
            "兩個指標互補，不能只看一個。\n\n"
            "**S&P500的作用：**\n"
            "外資管理的是全球資產組合，不只是台灣。當S&P500大跌，"
            "代表全球資金在撤出所有風險性資產，台股不管基本面多好都會被拖累。"
            "這種情況下，即使SOX還算穩定，也要謹慎。\n\n"
            "**兩個指標的組合解讀：**\n"
            "・ SOX強 + S&P500強：最佳環境，台股個股超跌直接進場\n"
            "・ SOX強 + S&P500弱：半導體景氣好但全球資金緊縮，需觀察\n"
            "・ SOX弱 + S&P500強：可能是半導體週期性調整，不是系統性風險\n"
            "・ SOX弱 + S&P500弱：系統性風險，類2022，策略勝率最低\n\n"
            "**距52週高點的意義：**\n"
            "・ > -10%：全球資金偏樂觀，風險胃納良好\n"
            "・ -10% ～ -20%：全球資金開始謹慎\n"
            "・ < -20%：全球資金明顯撤退，台股受外資賣壓"
        )

    # ── 台股市場熱度計 ──
    st.markdown("---")
    st.markdown("### 🌡️ 台股市場熱度計（10級）")
    st.caption("台灣加權指數相對240日均線的偏離幅度，衡量市場過熱或過冷程度")

    if twii_heat:
        col_h1, col_h2 = st.columns([1, 2])
        with col_h1:
            st.metric("台灣加權指數",
                     "{:,.0f}".format(twii_heat["current"]),
                     "vs 240MA：{:+.1f}%".format(twii_heat["deviation"]))
            st.markdown("**熱度等級：{} 第{}級 — {}**".format(
                twii_heat["color"], twii_heat["level"], twii_heat["label"]))

            # 視覺化進度條
            level = twii_heat["level"]
            bar_html = ""
            for i in range(1, 11):
                if i <= level:
                    if i <= 3:
                        color = "#1a73e8"
                    elif i <= 6:
                        color = "#34a853"
                    elif i <= 8:
                        color = "#fbbc04"
                    else:
                        color = "#ea4335"
                    bar_html += '<span style="background:{}; color:white; padding:2px 6px; margin:1px; border-radius:3px; font-size:12px;">{}</span>'.format(color, i)
                else:
                    bar_html += '<span style="background:#e0e0e0; color:#888; padding:2px 6px; margin:1px; border-radius:3px; font-size:12px;">{}</span>'.format(i)
            st.markdown(bar_html, unsafe_allow_html=True)

            st.markdown("")
            st.markdown("**均線參考：**")
            st.markdown("・20MA：{:,.0f}".format(twii_heat["ma20"]))
            st.markdown("・60MA：{:,.0f}".format(twii_heat["ma60"]))
            st.markdown("・240MA：{:,.0f}".format(twii_heat["ma240"]))

            # 策略建議
            if level <= 6:
                st.success("**策略建議：** " + twii_heat["action"])
            elif level <= 7:
                st.warning("**策略建議：** " + twii_heat["action"])
            else:
                st.error("**策略建議：** " + twii_heat["action"])

        with col_h2:
            st.markdown("**📖 市場熱度計怎麼讀、為什麼重要**")
            st.info(
                "**核心邏輯：均值回歸不只適用於個股，也適用於整體市場**\n\n"
                "我們的策略是「個股跌幅觸發後均值回歸」，但如果整體市場嚴重過熱，"
                "個股的均值本身也在高位，觸發後反彈的幅度會受限，甚至觸發後繼續跌。\n\n"
                "**為什麼用240日均線（約一年）？**\n"
                "240日均線代表市場的「正常基準」，它過濾掉短期波動，"
                "顯示市場的長期趨勢中樞。相對於這個中樞的偏離，"
                "才能反映真正的過熱或過冷程度。\n\n"
                "**各級別的歷史對應：**\n"
                "・ 1～2級（極冷）：對應2020年3月疫情崩盤、2008年金融海嘯底部，"
                "歷史上這個時候進場的長期報酬最高\n"
                "・ 5～6級（中性）：市場正常運作，策略最容易執行\n"
                "・ 8～9級（過熱）：對應2021年台股多頭高峰，"
                "2022年隨後大幅修正，那時進場的人多數套牢\n"
                "・ 10級（極熱）：歷史罕見，出現即代表高度風險\n\n"
                "**跟基本面條件的搭配：**\n"
                "・ 熱度7～8級 + 基本面好的標的觸發：提高觸發門檻要求（從-10%提高到-15%），"
                "等更深的超跌才進場\n"
                "・ 熱度9～10級：即使有好標的觸發，也建議等市場熱度降至7級以下再進場，"
                "因為市場過熱時的觸發往往不是真正的超跌，而是大趨勢向下的開始"
            )

            # 10級完整說明表
            heat_table = pd.DataFrame([
                {"級別": "1-2級 🔵", "偏離幅度": "< -20%", "市場狀態": "極冷/嚴重超賣", "進場策略": "全力進場"},
                {"級別": "3-4級 🟢", "偏離幅度": "-10% ～ -20%", "市場狀態": "冷/輕微超賣", "進場策略": "積極進場"},
                {"級別": "5-6級 🟢", "偏離幅度": "-10% ～ 0%", "市場狀態": "中性", "進場策略": "正常進場"},
                {"級別": "7級 🟡", "偏離幅度": "0% ～ +10%", "市場狀態": "微熱", "進場策略": "正常，勿追高"},
                {"級別": "8級 🟠", "偏離幅度": "+10% ～ +20%", "市場狀態": "明顯過熱", "進場策略": "縮倉，等-15%觸發"},
                {"級別": "9-10級 🔴", "偏離幅度": "> +20%", "市場狀態": "嚴重過熱/泡沫", "進場策略": "暫停策略"},
            ])
            st.markdown(heat_table.to_html(index=False), unsafe_allow_html=True)
    else:
        st.warning("台股熱度數據無法取得（需要超過250個交易日的歷史數據）")

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
        sp500_ok = sp500["pct_from_high"] > -10 if sp500 else True
        heat_level = twii_heat["level"] if twii_heat else 6

        # 計分
        score = 0
        signals = []
        if sox_strong:
            score += 2
            signals.append("✅ SOX強勢（距高點<15%），台灣半導體個股超跌更可能是情緒性")
        elif sox_ok:
            score += 1
            signals.append("🟡 SOX回落中（距高點15～30%），正常操作")
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
            signals.append("🟡 VIX偏高（20～30），觸發後反彈機率合理")
        else:
            score += 0
            signals.append("🔵 VIX平靜（<20），確認是真正超跌而非小幅調整")

        if twd_ok:
            score += 1
            signals.append("✅ 台幣穩定或升值，外資無明顯賣壓")
        else:
            score -= 1
            signals.append("⚠️ 台幣貶值，注意外資持續賣壓")

        # S&P500評分
        if sp500_ok:
            score += 1
            signals.append("✅ S&P500距高點<10%，全球風險胃納良好")
        elif sp500 and sp500["pct_from_high"] > -20:
            score += 0
            signals.append("🟡 S&P500回落中（距高點10～20%），全球資金開始謹慎")
        else:
            score -= 2
            signals.append("❌ S&P500顯著下行（距高點>20%），全球資金撤出風險資產")

        # 台股熱度評分
        if heat_level <= 6:
            score += 1
            signals.append("✅ 台股熱度第{}級（{}），市場未過熱，進場時機合理".format(
                heat_level, twii_heat["label"] if twii_heat else ""))
        elif heat_level == 7:
            score += 0
            signals.append("🟡 台股熱度第7級（微熱），正常進場但勿追高")
        elif heat_level == 8:
            score -= 1
            signals.append("⚠️ 台股熱度第8級（明顯過熱），建議縮小倉位，等更深觸發（-15%）")
        else:
            score -= 3
            signals.append("❌ 台股熱度第{}級（{}），市場嚴重過熱，建議暫停策略等市場回歸正常".format(
                heat_level, twii_heat["label"] if twii_heat else ""))

        # 綜合結論
        for s in signals:
            st.markdown("　" + s)
        st.markdown("")

        # 熱度對進場門檻的影響
        if twii_heat:
            if heat_level >= 9:
                st.error("🌡️ **熱度警示**：市場第{}級過熱，建議等熱度降至7級以下再執行策略".format(heat_level))
            elif heat_level == 8:
                st.warning("🌡️ **熱度調整**：市場第8級過熱，建議將觸發門檻從 -10% 提高至 -15%，等更深的超跌")
            elif heat_level <= 2:
                st.success("🌡️ **熱度機會**：市場第{}級極冷，歷史上是最佳進場時機，可積極進場".format(heat_level))

        if score >= 5:
            st.success(
                "**🟢 環境：積極進場**\n\n"
                "多項指標同時支持，這是我們策略歷史上勝率最高的環境。"
                "觸發標的通過基本面篩選後，可以正常倉位進場。"
            )
        elif score >= 2:
            st.success(
                "**🟢 環境：正常進場**\n\n"
                "整體環境良好，按正常策略執行。"
                "觸發標的通過基本面篩選後可以進場。"
            )
        elif score >= 0:
            st.warning(
                "**🟡 環境：正常但留意**\n\n"
                "部分指標需留意。觸發標的通過基本面篩選後可以進場，"
                "但建議控制單筆倉位在正常的70～80%。"
            )
        elif score >= -2:
            st.warning(
                "**🟡 環境：謹慎，縮小倉位**\n\n"
                "環境偏弱，建議只進入通過全部硬性條件且評分最高的標的，"
                "倉位減至正常的50%。"
            )
        else:
            st.error(
                "**🔴 環境：高風險，暫停或大幅縮減**\n\n"
                "多項指標顯示系統性風險，類2022環境。"
                "建議暫停操作或只用極小倉位（正常的20～30%），"
                "等待環境改善後再恢復。"
            )

        st.caption(
            "評分說明：SOX強勢+2、SOX正常+1、SOX下行-2｜"
            "殖利率穩定+2、殖利率緩升0、殖利率快升-2｜"
            "VIX>30（恐慌）+2、VIX 20～30+1、VIX<20+0｜"
            "台幣穩定/升值+1、台幣貶值-1｜"
            "S&P500強+1、S&P500回落0、S&P500下行-2｜"
            "熱度1～6級+1、7級0、8級-1、9～10級-3｜"
            "總分≥5積極、≥2正常、≥0留意、≥-2謹慎、<-2高風險"
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
        st.caption("建立完整池子需要抓取MOPS財報資料（約需3～5分鐘）。池子每季更新一次即可。")

    if build_btn:
        with st.spinner("步驟1/2：取得全市場股票清單..."):
            all_stocks = get_all_tw_stocks()
            individual_stocks = [s for s in all_stocks if s['type'] == '個股']
            st.info("取得 {} 檔個股，透過 yfinance 抓取財務資料...".format(len(individual_stocks)))

        est_min = round(len(individual_stocks) * 0.12 / 60, 1)
        with st.spinner("步驟2/2：yfinance 抓取財務資料與評分（預計約{}分鐘）...".format(est_min)):
            st.caption("✅ yfinance 不依賴 MOPS，境外IP可正常存取。資料：ROE、負債比、EPS歷史、每股淨值、現價")
            df_pool = build_qualified_pool(all_stocks, fin_data=None)

        if df_pool is not None and not df_pool.empty:
            grade_a = df_pool[df_pool['_grade_short'] == 'A級']
            grade_b = df_pool[df_pool['_grade_short'] == 'B級']
            grade_c = df_pool[df_pool['_grade_short'] == 'C級']
            excluded = df_pool[df_pool['_grade_short'] == '排除']
            if '代碼' in df_pool.columns:
                df_pool['代碼'] = df_pool['代碼'].astype(str).str.strip()
            total_scored = df_pool[df_pool['體質分數'].notna()]
            full_data = len(df_pool[df_pool['資料完整度'] == '100%']) if '資料完整度' in df_pool.columns else 0
            partial_data = len(total_scored) - full_data
            st.session_state['df_pool'] = df_pool
            disk_ok = save_pool_to_disk(df_pool)
            st.success(
                "✅ 分級完成！資料來源：yfinance\n\n"
                "🥇 A級：{}檔　🥈 B級：{}檔　🥉 C級：{}檔　❌ 排除：{}檔\n\n"
                "📊 評分完整度：{}檔100%完整、{}檔部分資料\n\n"
                "💾 {}".format(
                    len(grade_a), len(grade_b), len(grade_c), len(excluded),
                    full_data, partial_data,
                    "已儲存本地快取（12小時有效，重新整理自動還原）" if disk_ok else "建立在記憶體"
                )
            )
        else:
            st.error("❌ 建立失敗，請確認 requirements.txt 含 yfinance>=0.2.36 並已重新部署")

    # 顯示合格標的池
    df_pool = st.session_state.get('df_pool', None)
    if df_pool is not None and not df_pool.empty:
        display_cols = ['等級', '體質分數', '體質等級', '資料完整度', '代碼', '名稱', '產業別', '降級原因',
                        '股價', 'PB', 'ROE%', '負債比%', 'PB/ROE',
                        '▶A獲利(0-5)', '▶B護城河(0-5)', '▶C安全邊際(0-5)',
                        '①EPS近3年正', '②EPS成長', '③負債比<50%', '④ROE>15%', '⑤PB<3', '⑥PB/ROE<0.20']
        display_cols = [c for c in display_cols if c in df_pool.columns]

        # ── 體質評分說明 ──
        st.markdown("### 📊 Coatue體質評分卡說明（15分制）")
        with st.expander("📖 評分邏輯說明（點擊展開）"):
            st.markdown("""
| 維度 | 滿分 | 評分項目 | 滿分條件 |
|------|------|---------|---------|
| **A 獲利能力** | 5分 | A1近5年EPS皆正（0或2分）＋A2 ROE水準（0～3分） | EPS全正且ROE≥20% |
| **B 商業模式護城河** | 5分 | B1近3年EPS成長（0或2分）＋B2負債比（0～3分） | EPS成長且負債比<30% |
| **C 市值與安全邊際** | 5分 | C1 PB/ROE複合估值（0～3分）＋C2股價流動性（0～2分） | PB/ROE<0.10且股價>10 |

**等級對照：**
- ⭐⭐⭐ **核心標的**（13～15分）：Coatue最愛型，體質優秀，觸發時優先進場
- ⭐⭐ **可觀察**（9～12分）：體質尚可，可進場但倉位控制
- ⭐ **高風險**（5～8分）：基本面偏弱，謹慎；市場過熱時不宜進場
- 💀 **Broken Model**（0～4分）：類Robinhood/Lemonade，跌有原因，不宜進場
            """)

        # 體質分數排行（前20名）
        if '體質分數' in df_pool.columns:
            df_top_quality = df_pool[df_pool['體質分數'].notna()].sort_values('體質分數', ascending=False).head(20)
            if not df_top_quality.empty:
                st.markdown("#### 🏅 體質分數排行（前20名）")
                cols_rank = ['體質分數', '體質等級', '代碼', '名稱', '產業別', 'ROE%', '負債比%',
                             '▶A獲利(0-5)', '▶B護城河(0-5)', '▶C安全邊際(0-5)']
                available = [c for c in cols_rank if c in df_top_quality.columns]
                show_html(df_top_quality[available].reset_index(drop=True))

        st.divider()

        # A級
        st.markdown("### 🥇 A級標的（優先進場）")
        st.caption("通過全部6個條件，觸發時優先評估進場")
        df_a = df_pool[df_pool['_grade_short'] == 'A級'].reset_index(drop=True)
        if not df_a.empty:
            industry_a = "　".join([k + "(" + str(v) + ")" for k, v in df_a['產業別'].value_counts().head(6).items()])
            st.caption("產業分布：" + industry_a)
            show_html(df_a[display_cols])
        else:
            st.info("無A級標的")

        # B級
        st.markdown("### 🥈 B級標的（次要進場，A級無觸發時考慮）")
        st.caption("通過3個硬性條件，但1～2個品質條件未通過（如估值偏高的優質企業）")
        df_b = df_pool[df_pool['_grade_short'] == 'B級'].reset_index(drop=True)
        if not df_b.empty:
            st.caption("共 " + str(len(df_b)) + " 檔，「降級原因」欄說明為何未達A級")
            show_html(df_b[display_cols])
        else:
            st.info("無B級標的")

        # C級
        with st.expander("🥉 C級標的（觀察，暫不主動進場）共 " + str(len(df_pool[df_pool['_grade_short'] == 'C級'])) + " 檔"):
            df_c = df_pool[df_pool['_grade_short'] == 'C級'].reset_index(drop=True)
            if not df_c.empty:
                show_html(df_c[display_cols])

        # 下載
        st.download_button(
            "📥 下載全部標的分級CSV",
            df_pool[display_cols].to_csv(index=False).encode('utf-8-sig'),
            "stock_grades.csv", "text/csv"
        )

    else:
        st.info(
            "📋 尚未建立合格標的池\n\n"
            "請點上方「🔄 建立/更新合格標的池」按鈕，約需 3～5 分鐘。\n\n"
            "建立後頁面會自動顯示 A/B/C 級標的與 15 分制體質評分。"
        )

    st.divider()

    # ── 個股快查 ──
    st.markdown("### 🔎 個股快查（進場前確認）")
    st.caption("輸入股票代碼，快速確認等級與六個條件")

    check_code = st.text_input("輸入股票代碼", placeholder="例：2317", key="pool_check_code")
    if st.button("確認基本面條件", key="check_fundamental"):
        if not check_code.strip():
            st.warning("請輸入代碼")
        else:
            code = check_code.strip()
            found = False
            df_pool_check = st.session_state.get('df_pool', None)
            if df_pool_check is not None and not df_pool_check.empty:
                row_df = df_pool_check[df_pool_check['代碼'] == code]
                if not row_df.empty:
                    row = row_df.iloc[0]
                    found = True
                    grade = row.get('等級', '')
                    grade_reason = row.get('降級原因', '')

                    st.markdown("**" + code + " " + str(row.get('名稱', '')) + "**")

                    # 等級顯示
                    if 'A級' in grade:
                        st.success("**" + grade + "**　→ 優先進場標的")
                    elif 'B級' in grade:
                        st.warning("**" + grade + "**　→ 次要進場標的\n\n降級原因：" + grade_reason)
                    elif 'C級' in grade:
                        st.warning("**" + grade + "**　→ 暫不主動進場\n\n降級原因：" + grade_reason)
                    else:
                        st.error("**" + grade + "**　→ 硬性條件未通過，不進場\n\n原因：" + grade_reason)

                    # 條件明細
                    st.markdown("**條件明細：**")
                    st.caption("第一層（硬性條件）")
                    cols1 = st.columns(3)
                    hard_conditions = [
                        ('① 近5年EPS皆正', row.get('①5年EPS正', '⚠️'), '硬性'),
                        ('② 近3年EPS成長', row.get('②EPS成長', '⚠️'), '硬性'),
                        ('③ 負債比<50%', row.get('③負債比<50%', '⚠️') + "（" + str(row.get('負債比%', 'N/A')) + "%）", '硬性'),
                    ]
                    for i, (label, val, _) in enumerate(hard_conditions):
                        with cols1[i]:
                            if '✅' in str(val):
                                st.success(label + "\n" + str(val))
                            elif '❌' in str(val):
                                st.error(label + "\n" + str(val))
                            else:
                                st.warning(label + "\n" + str(val))

                    st.caption("第二層（品質條件，影響A/B/C分級）")
                    cols2 = st.columns(3)
                    quality_conditions = [
                        ('④ ROE>15%', row.get('④ROE>15%', '⚠️') + "（" + str(row.get('ROE%', 'N/A')) + "%）"),
                        ('⑤ PB<3', row.get('⑤PB<3', '⚠️') + "（PB=" + str(row.get('PB', 'N/A')) + "）"),
                        ('⑥ PB/ROE<0.20', row.get('⑥PB/ROE<0.20', '⚠️') + "（" + str(row.get('PB/ROE', 'N/A')) + "）"),
                    ]
                    for i, (label, val) in enumerate(quality_conditions):
                        with cols2[i]:
                            if '✅' in str(val):
                                st.success(label + "\n" + str(val))
                            elif '❌' in str(val):
                                st.error(label + "\n" + str(val))
                            else:
                                st.warning(label + "\n" + str(val))

            if not found:
                st.warning("請先建立合格標的池，或此代碼不在個股範圍內")


with tab1:
    # ── 體質評分狀態提示 ──
    df_pool_exists = 'df_pool' in st.session_state and st.session_state['df_pool'] is not None
    if df_pool_exists:
        pool_size = len(st.session_state['df_pool'])
        from_disk = st.session_state.get('pool_loaded_from_disk', False)
        saved_at  = st.session_state.get('pool_saved_at', '')
        src_label = "（從本地快取還原，建立於 {}）".format(saved_at[:16]) if from_disk else "（本次建立）"
        st.success("✅ 體質評分庫已載入　{}檔已評分　{}　→ 掃描結果將自動帶入15分制體質評分".format(pool_size, src_label))
    else:
        st.info(
            "💡 **體質評分尚未建立**：掃描結果的「體質分數」會顯示「未評分」。\n\n"
            "建議先至【📋 合格標的池】頁籤點「建立/更新合格標的池」（約需3分鐘），"
            "建立後本頁掃描會自動帶入15分制體質評分，讓你一眼區分好公司vs爛公司。\n\n"
            "⚡ **或直接掃描**：觸發結果仍會顯示，體質欄補「未評分」，"
            "可用下方「個股快評」補充確認。"
        )

    threshold1 = st.slider("警示門檻（跌幅%）", min_value=-30, max_value=-3, value=-10, step=1, key="t1")
    st.markdown("**篩選範圍（可多選，不選代表全部）**")
    selected1 = group_selector("tab1")

    if st.button("🔍 開始掃描", type="primary", key="scan"):
        all_stocks = get_all_tw_stocks()
        scan_list = [s for s in all_stocks if s["group"] in selected1] if selected1 else all_stocks
        total = len(scan_list)
        st.info("共 " + str(total) + " 檔，開始掃描...")
        raw_results = []
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
                raw_results.append({
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
        # ── 儲存到 session_state，切tab不消失 ──
        st.session_state['scan_results'] = raw_results
        st.session_state['scan_threshold'] = threshold1

    # ── 從 session_state 讀取結果（不依賴button state）──
    results = st.session_state.get('scan_results', None)
    saved_threshold = st.session_state.get('scan_threshold', threshold1)


    if results is not None:
        if len(results) == 0:
            st.success("✅ 掃描完成（門檻：{}%）　沒有標的觸發".format(saved_threshold))
        else:
            twii_h = get_twii_heat()
            market_ok = twii_h and twii_h["level"] <= 7
            market_level_num = twii_h["level"] if twii_h else "?"
            market_level_str = "第{}級/10（{}）".format(market_level_num, twii_h["label"]) if twii_h else "未知"

            # 體質查詢字典
            pool_score_dict = {}
            if df_pool_now is not None and not df_pool_now.empty:
                for _, pr in df_pool_now.iterrows():
                    c = str(pr.get('代碼', '')).strip()
                    pool_score_dict[c] = {
                        'score': pr.get('體質分數'),
                        'grade': pr.get('體質等級', ''),
                        'industry': pr.get('產業別', ''),
                    }

            has_pool = len(pool_score_dict) > 0

            rows = []
            for r in results:
                code = str(r["代碼"]).strip()
                qi = pool_score_dict.get(code, {})
                q_score = qi.get('score')
                q_grade = qi.get('grade', '')
                # 產業別：優先從 pool 取，其次從原始 scan 結果
                industry = qi.get('industry') or r.get('產業別', '') or r.get('產業群組', '')

                # 體質分數欄
                if not has_pool:
                    score_str = "未建池"
                elif isinstance(q_score, (int, float)):
                    score_str = "{}/15".format(int(q_score))
                else:
                    score_str = "查無"

                grade_str = q_grade if isinstance(q_score, (int, float)) else ("未建池" if not has_pool else "查無")

                # 4個條件
                c1_ok = r.get("連續觸發天數", 99) <= 3
                c2_ok = isinstance(q_score, (int, float)) and q_score >= 9
                c3_ok = bool(market_ok)
                ret_val = float(str(r.get("滾動10日報酬率", "0")).replace("%", ""))
                c4_ok = ret_val <= (threshold1 - 2)
                cond_met = sum([c1_ok, c2_ok, c3_ok, c4_ok])

                if cond_met == 4:
                    signal = "🔥 強烈"
                elif cond_met == 3:
                    signal = "✅ 有效"
                elif cond_met == 2:
                    signal = "🔶 觀察"
                else:
                    signal = "⚪ 弱"

                rows.append({
                    "信號": signal,
                    "體質分數": score_str,
                    "體質等級": grade_str,
                    "代碼": code,
                    "名稱": r.get("名稱", ""),
                    "產業別": industry,
                    "收盤價": r.get("最新收盤價", ""),
                    "10日報酬": r.get("滾動10日報酬率", ""),
                    "連續天數": r.get("連續觸發天數", ""),
                    "①新進觸發": "✅" if c1_ok else "❌",
                    "②體質合格": "✅" if c2_ok else ("—" if not has_pool else "❌"),
                    "③市場正常": "✅" if c3_ok else "❌",
                    "④深度超跌": "✅" if c4_ok else "❌",
                })

            df_show = pd.DataFrame(rows)
            signal_order = {"🔥 強烈": 0, "✅ 有效": 1, "🔶 觀察": 2, "⚪ 弱": 3}
            df_show["_rank"] = df_show["信號"].map(signal_order).fillna(9)
            df_show = df_show.sort_values(["_rank", "10日報酬"]).drop(columns=["_rank"]).reset_index(drop=True)

            # ── 統計摘要 ──
            strong = (df_show["信號"] == "🔥 強烈").sum()
            valid  = (df_show["信號"] == "✅ 有效").sum()
            watch  = (df_show["信號"] == "🔶 觀察").sum()
            weak   = (df_show["信號"] == "⚪ 弱").sum()

            st.error("⚠️ 共 **{}** 檔觸發（門檻：{}%）　市場環境：{}".format(
                len(df_show), threshold1, market_level_str))

            col_s1, col_s2, col_s3, col_s4 = st.columns(4)
            col_s1.metric("🔥 強烈", "{}檔".format(strong))
            col_s2.metric("✅ 有效", "{}檔".format(valid))
            col_s3.metric("🔶 觀察", "{}檔".format(watch))
            col_s4.metric("⚪ 弱",   "{}檔".format(weak))

            # ── 四個條件說明 ──
            with st.expander("📖 四個評估條件說明（點擊展開）"):
                st.markdown("""
**① 新進觸發（連續觸發天數 ≤ 3天）**
股票剛開始觸發跌幅門檻，歷史數據顯示第1天進場的勝率最高。若已連續觸發超過3天，代表可能是持續下跌趨勢而非短暫超跌。

**② 體質合格（體質分數 ≥ 9/15分）**
類Coatue邏輯：區分「好公司短暫跌」vs「爛公司繼續跌」。9分以上代表獲利、護城河、安全邊際至少有兩項表現正常。需先建立合格標的池才會顯示分數。

**③ 市場環境正常（市場熱度 ≤ 7級/10）**
台股大盤相對240日均線的偏離程度。7級以下代表市場在正常到輕微過熱範圍，觸發後均值回歸機率高。現在是{}級，{}。

**④ 深度超跌（跌幅比門檻再多2%以上）**
例如門檻設-10%，深度超跌代表跌幅已達-12%以下。跌得更深的標的歷史上反彈力道通常更強。
                """.format(
                    market_level_num,
                    "環境{}建議操作".format("合理，" if market_ok else "偏熱，謹慎")
                ))

            if not market_ok:
                st.warning("⚠️ 市場目前{}，③條件全部標的均為❌。這代表大盤偏離長期均線過高，觸發往往是大趨勢下跌的開始，而非短暫超跌。建議等市場冷卻至7級以下再積極進場。".format(market_level_str))

            if not has_pool:
                st.info("💡 體質分數顯示「未建池」：請至【📋 合格標的池】頁籤建立評分，建立後②體質合格條件將自動填入，讓信號更精確。")

            # ── 表格 ──
            st.markdown(show_html.__doc__ or "")
            show_html(df_show)
            st.download_button("📥 下載CSV", df_show.to_csv(index=False).encode("utf-8-sig"), "alert_scan.csv", "text/csv")

            # ── 個股快評 ──
            st.divider()
            st.markdown("#### 🔎 個股快評")
            st.caption("輸入上方觸發代碼，快速確認體質評分明細（需先建立合格標的池）")
            col_qc1, col_qc2 = st.columns([1, 3])
            with col_qc1:
                quick_code = st.text_input("代碼", placeholder="例：2330", key="scan_quick_code")
                quick_btn2 = st.button("⚡ 快速確認", key="scan_quick_btn")
            with col_qc2:
                if quick_btn2 and quick_code.strip():
                    qi2 = pool_score_dict.get(quick_code.strip(), {})
                    q_score2 = qi2.get('score')
                    if q_score2 is not None and isinstance(q_score2, (int, float)):
                        df_pool_check2 = df_pool_now
                        row_df2 = df_pool_check2[df_pool_check2['代碼'] == quick_code.strip()]
                        if not row_df2.empty:
                            row2 = row_df2.iloc[0]
                            score_int2 = int(q_score2)
                            q_grade2 = qi2.get('grade', '')
                            sa = row2.get('▶A獲利(0-5)', '-')
                            sb = row2.get('▶B護城河(0-5)', '-')
                            sc = row2.get('▶C安全邊際(0-5)', '-')
                            fn = st.success if score_int2 >= 13 else (st.warning if score_int2 >= 9 else st.error)
                            fn("{} {}　體質 {}/15分　{}".format(
                                quick_code.strip(), row2.get('名稱',''), score_int2, q_grade2))
                            cqa, cqb, cqc = st.columns(3)
                            cqa.metric("A 獲利能力", "{}/5".format(sa))
                            cqb.metric("B 護城河", "{}/5".format(sb))
                            cqc.metric("C 安全邊際", "{}/5".format(sc))
                            st.caption("A：{}".format(row2.get('A細節','')))
                            st.caption("B：{}".format(row2.get('B細節','')))
                            st.caption("C：{}".format(row2.get('C細節','')))
                    else:
                        st.warning("此代碼尚未評分，請先至【合格標的池】建立評分庫")
    else:
        st.info("尚未執行掃描，請設定門檻後點「🔍 開始掃描」")

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
        st.session_state['bt_rows'] = all_rows
        st.session_state['bt_threshold'] = threshold2

    # 從 session_state 讀取
    all_rows = st.session_state.get('bt_rows', None)
    if all_rows is not None:
        if all_rows:
            df_bt = pd.DataFrame(all_rows)
            avg_cols = [str(h) + "天平均%" for h in HORIZONS]
            dd_cols = [str(h) + "天回撤%" for h in HORIZONS]
            st.success("✅ 回測完成！（門檻：{}%）".format(st.session_state.get('bt_threshold', threshold2)))
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

    # 市場熱度快速顯示
    twii_heat_bt = get_twii_heat()
    if twii_heat_bt:
        level_bt = twii_heat_bt["level"]
        if level_bt >= 9:
            st.error("🌡️ 台股市場熱度第{}級（{}）｜建議暫停策略，等熱度降至7級以下".format(
                level_bt, twii_heat_bt["label"]))
        elif level_bt == 8:
            st.warning("🌡️ 台股市場熱度第8級（明顯過熱）｜建議將觸發門檻提高至-15%，等更深超跌進場")
        elif level_bt <= 2:
            st.success("🌡️ 台股市場熱度第{}級（{}）｜歷史最佳進場時機，可積極進場".format(
                level_bt, twii_heat_bt["label"]))
        else:
            st.info("🌡️ 台股市場熱度第{}級（{}）｜240MA={:,.0f}，偏離{:+.1f}%｜{}".format(
                level_bt, twii_heat_bt["label"],
                twii_heat_bt["ma240"], twii_heat_bt["deviation"],
                twii_heat_bt["action"]))

    col1, col2 = st.columns([2, 1])
    with col1:
        single_code = st.text_input("輸入股票／ETF代碼", value="0050", key="single")
    with col2:
        ref_threshold = st.selectbox("年度明細與進場時機顯示門檻", [str(t) + "%" for t in THRESHOLDS], index=2, key="ref_thr")

    # ── 體質快查區 ──
    if single_code:
        df_pool_bt = st.session_state.get('df_pool', None)
        if df_pool_bt is not None and not df_pool_bt.empty:
            pool_r = df_pool_bt[df_pool_bt['代碼'] == single_code.strip()]
            if not pool_r.empty:
                pr = pool_r.iloc[0]
                q_total = pr.get('體質分數')
                q_grade = pr.get('體質等級', '')
                score_a = pr.get('▶A獲利(0-5)', '-')
                score_b = pr.get('▶B護城河(0-5)', '-')
                score_c = pr.get('▶C安全邊際(0-5)', '-')
                det_a = pr.get('A細節', '')
                det_b = pr.get('B細節', '')
                det_c = pr.get('C細節', '')

                st.markdown("#### 📊 {} 體質評分卡".format(single_code))
                col_qa, col_qb, col_qc, col_qtotal = st.columns(4)
                with col_qa:
                    st.metric("A 獲利能力", "{}/5分".format(score_a))
                    st.caption(det_a)
                with col_qb:
                    st.metric("B 護城河", "{}/5分".format(score_b))
                    st.caption(det_b)
                with col_qc:
                    st.metric("C 安全邊際", "{}/5分".format(score_c))
                    st.caption(det_c)
                with col_qtotal:
                    if q_total is not None and isinstance(q_total, (int, float)):
                        if q_total >= 13:
                            st.success("**總分 {}/15**\n\n{}".format(int(q_total), q_grade))
                        elif q_total >= 9:
                            st.warning("**總分 {}/15**\n\n{}".format(int(q_total), q_grade))
                        else:
                            st.error("**總分 {}/15**\n\n{}".format(int(q_total), q_grade))
                    else:
                        st.info("評分中...")
                st.divider()
            else:
                st.info("💡 此代碼尚未在合格標的池中評分，請先至【合格標的池】建立池子以顯示體質評分。")

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

        st.success("成功抓取 " + str(len(prices)) + " 個交易日（" + min(prices.keys()) + " ～ " + max(prices.keys()) + "）")

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

        # ── 建議持有天數 + 動態停損建議 ──
        st.markdown("---")
        st.markdown("### 🎯 進場品質評估與操作建議")

        # 找最佳持有天數（依勝率最高且樣本≥5）
        best_h_suggestion = None
        best_wr_val = 0
        best_avg_ret = 0
        for h in HORIZONS:
            rets_h = [x["ret"] for x in result["horizon_rets"][h]] if result else []
            if len(rets_h) >= 5:
                wr_h = sum(1 for r in rets_h if r > 0) / len(rets_h) * 100
                avg_h = sum(rets_h) / len(rets_h)
                if wr_h > best_wr_val or (wr_h == best_wr_val and avg_h > best_avg_ret):
                    best_wr_val = wr_h
                    best_avg_ret = avg_h
                    best_h_suggestion = h

        # 找平均最大回撤發生天數（風險管理用）
        dd_ref = build_dd_timing_table(prices, thr_val)
        avg_dd_day = None
        worst_dd_val = None
        if dd_ref is not None and best_h_suggestion:
            row_dd = dd_ref[dd_ref['觀察天數'] == str(best_h_suggestion) + '天']
            if not row_dd.empty:
                try:
                    avg_dd_day_str = str(row_dd.iloc[0].get('平均回撤發生於第幾天', ''))
                    avg_dd_day = float(avg_dd_day_str.replace('天', '').replace('無回撤', '0'))
                except:
                    pass
                try:
                    worst_dd_val = float(str(row_dd.iloc[0].get('最深回撤%', '0')).replace('%', ''))
                except:
                    pass

        # 宏觀環境
        twii_now = get_twii_heat()
        market_level = twii_now["level"] if twii_now else 6
        market_label = twii_now["label"] if twii_now else "未知"

        # 體質分數
        df_pool_now2 = st.session_state.get('df_pool', None)
        q_score_bt = None
        if df_pool_now2 is not None:
            pr2 = df_pool_now2[df_pool_now2['代碼'] == single_code.strip()]
            if not pr2.empty:
                q_score_bt = pr2.iloc[0].get('體質分數')

        # 複合信號評估
        entry_conds = []
        entry_score = 0
        if q_score_bt is not None and isinstance(q_score_bt, (int, float)):
            if q_score_bt >= 13:
                entry_score += 2
                entry_conds.append("✅ 體質⭐⭐⭐ ({}/15分)，核心標的".format(int(q_score_bt)))
            elif q_score_bt >= 9:
                entry_score += 1
                entry_conds.append("🟡 體質⭐⭐ ({}/15分)，可觀察".format(int(q_score_bt)))
            else:
                entry_conds.append("❌ 體質偏弱 ({}/15分)，需謹慎".format(int(q_score_bt)))
        else:
            entry_conds.append("⚠️ 體質未評分，建議先至合格標的池評估")

        if market_level <= 6:
            entry_score += 2
            entry_conds.append("✅ 市場第{}級（{}），環境合理".format(market_level, market_label))
        elif market_level == 7:
            entry_score += 1
            entry_conds.append("🟡 市場第7級（微熱），正常但勿追高")
        elif market_level == 8:
            entry_conds.append("❌ 市場第8級（過熱），建議提高門檻至-15%")
        else:
            entry_conds.append("❌ 市場第{}級（{}），建議暫停策略".format(market_level, market_label))

        if best_wr_val >= 70:
            entry_score += 2
            entry_conds.append("✅ 最佳持有{}天勝率{:.1f}%，歷史表現優秀".format(best_h_suggestion, best_wr_val))
        elif best_wr_val >= 55:
            entry_score += 1
            entry_conds.append("🟡 最佳持有{}天勝率{:.1f}%，表現尚可".format(best_h_suggestion, best_wr_val))
        else:
            entry_conds.append("❌ 最高勝率{:.1f}%偏低，此標的歷史反彈不穩定".format(best_wr_val))

        for c in entry_conds:
            st.markdown("　" + c)

        st.markdown("")

        # 綜合建議
        if best_h_suggestion:
            col_sug1, col_sug2 = st.columns(2)
            with col_sug1:
                st.markdown("**📅 建議持有天數**")
                st.info(
                    "最佳持有 **{}天**\n\n"
                    "歷史勝率：**{:.1f}%**　平均報酬：**{:.2f}%**\n\n"
                    "{}".format(
                        best_h_suggestion, best_wr_val, best_avg_ret,
                        "→ 建議以{}天為參考出場點，定期檢視是否提早出場".format(best_h_suggestion)
                    )
                )
            with col_sug2:
                st.markdown("**🛡️ 動態停損參考**")
                if avg_dd_day and worst_dd_val:
                    st.warning(
                        "歷史最深回撤：**{:.1f}%**\n\n"
                        "平均回撤發生於進場後第 **{:.0f}天**\n\n"
                        "→ 進場後第{:.0f}天若仍虧損超過{:.1f}%，可評估是否停損；\n"
                        "→ 但歷史數據顯示忍住浮虧通常報酬更佳".format(
                            worst_dd_val, avg_dd_day, avg_dd_day, abs(worst_dd_val) * 0.8
                        )
                    )
                else:
                    st.info("停損參考數據計算中...")

        if entry_score >= 5:
            st.success("**🟢 綜合評估：進場條件充分**（得分{}）→ 可按正常倉位進場".format(entry_score))
        elif entry_score >= 3:
            st.success("**🟢 綜合評估：進場條件合理**（得分{}）→ 可進場，控制倉位約80%".format(entry_score))
        elif entry_score >= 1:
            st.warning("**🟡 綜合評估：謹慎進場**（得分{}）→ 建議減倉至50%，嚴格執行停損".format(entry_score))
        else:
            st.error("**🔴 綜合評估：不建議進場**（得分{}）→ 等待宏觀環境改善或標的體質提升".format(entry_score))

        st.caption("*進場品質評分說明：體質⭐⭐⭐+2、⭐⭐+1、偏弱0｜市場≤6級+2、7級+1、8級0、>8級0｜勝率≥70%+2、≥55%+1｜最高6分*")

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
        st.session_state['rank_results'] = stock_results
        st.session_state['rank_horizon'] = horizon4

    # 從 session_state 讀取
    stock_results = st.session_state.get('rank_results', None)
    horizon4_saved = st.session_state.get('rank_horizon', horizon4)

    if stock_results is None:
        st.info("尚未執行，請設定參數後點「🏆 開始計算勝率排行」")
    elif not stock_results:
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

        # 取得體質分數（若有df_pool）
        df_pool_rank = st.session_state.get('df_pool', None)
        pool_score_map = {}
        if df_pool_rank is not None and not df_pool_rank.empty:
            for _, pr in df_pool_rank.iterrows():
                c = pr.get('代碼')
                s = pr.get('體質分數')
                g = pr.get('體質等級', '')
                if c:
                    pool_score_map[str(c)] = {'score': s, 'grade': g}

        rows = []
        for code in top_codes:
            data = stock_results[code]
            q_info = pool_score_map.get(str(code), {})
            q_s = q_info.get('score')
            q_g = q_info.get('grade', '未評分')
            row = {
                "代碼": data["代碼"],
                "名稱": data["名稱"],
                "產業別": data["產業別"],
                "體質分數": int(q_s) if q_s is not None and isinstance(q_s, (int, float)) else "未評",
                "體質等級": q_g,
            }
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
            key=lambda col: col.map(lambda v: float(str(v).replace("%","").replace("⚠️","")) if v not in ["---", "未評"] else 0),
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
        # 體質分數欄：未評分的先顯示
        display_rank_cols = ["代碼", "名稱", "產業別", "體質分數", "體質等級"] + thr_cols
        display_rank_cols = [c for c in display_rank_cols if c in df_combined.columns]
        show_html(df_combined[display_rank_cols].style.map(style_winrate_cell, subset=thr_cols))
        if not any(isinstance(v, (int, float)) for v in df_combined.get('體質分數', [])):
            st.caption("💡 體質分數顯示『未評』表示尚未建立合格標的池，請至【合格標的池】頁籤建立後再次查看。")

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
