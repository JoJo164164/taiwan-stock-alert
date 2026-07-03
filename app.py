import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import json
import logging
import warnings
import os

# ── 徹底靜音 yfinance 所有 noisy 輸出 ──
os.environ["YFINANCE_LOG_LEVEL"] = "CRITICAL"  # yfinance 環境變數
for _logger_name in ["yfinance", "yfinance.base", "yfinance.ticker",
                      "yfinance.utils", "yfinance.scrapers",
                      "peewee", "urllib3", "charset_normalizer"]:
    logging.getLogger(_logger_name).setLevel(logging.CRITICAL)
    logging.getLogger(_logger_name).propagate = False

warnings.filterwarnings("ignore", message=".*possibly delisted.*")
warnings.filterwarnings("ignore", message=".*no timezone.*")
warnings.filterwarnings("ignore", message=".*No data found.*")
warnings.filterwarnings("ignore", message=".*auto_adjust.*")
warnings.filterwarnings("ignore", message=".*Ticker.*")
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# root logger 也調整，避免 yfinance 用 print 以外的方式輸出
logging.basicConfig(level=logging.ERROR)

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

st.set_page_config(page_title="台股滾動10日跌幅系統 v14", layout="wide")

# ── 全域 CSS：完整字型體系，覆蓋 Streamlit Cloud 所有元件 ──

# ── 圓框 SVG icon 全域定義 ──
st.markdown("""
<!-- 圓框 SVG icon 定義（全域，與你提供的設計風格一致） -->
<svg xmlns="http://www.w3.org/2000/svg" style="display:none">
  <symbol id="icon-chart" viewBox="0 0 48 48">
    <circle cx="24" cy="24" r="22" fill="none" stroke="#003781" stroke-width="1.5"/>
    <rect x="12" y="28" width="5" height="8" rx="1" fill="none" stroke="#003781" stroke-width="1.5"/>
    <rect x="21" y="20" width="5" height="16" rx="1" fill="none" stroke="#003781" stroke-width="1.5"/>
    <rect x="30" y="13" width="5" height="23" rx="1" fill="none" stroke="#003781" stroke-width="1.5"/>
  </symbol>
  <symbol id="icon-alert" viewBox="0 0 48 48">
    <circle cx="24" cy="24" r="22" fill="none" stroke="#003781" stroke-width="1.5"/>
    <path d="M24 14v14" stroke="#003781" stroke-width="2" stroke-linecap="round"/>
    <circle cx="24" cy="33" r="1.5" fill="#003781"/>
  </symbol>
  <symbol id="icon-trend" viewBox="0 0 48 48">
    <circle cx="24" cy="24" r="22" fill="none" stroke="#003781" stroke-width="1.5"/>
    <polyline points="11,32 20,22 27,27 37,16" fill="none" stroke="#003781" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
    <polyline points="31,16 37,16 37,22" fill="none" stroke="#003781" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
  </symbol>
  <symbol id="icon-clock" viewBox="0 0 48 48">
    <circle cx="24" cy="24" r="22" fill="none" stroke="#003781" stroke-width="1.5"/>
    <circle cx="24" cy="24" r="13" fill="none" stroke="#003781" stroke-width="1.5"/>
    <polyline points="24,17 24,24 29,27" fill="none" stroke="#003781" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
  </symbol>
  <symbol id="icon-search" viewBox="0 0 48 48">
    <circle cx="24" cy="24" r="22" fill="none" stroke="#003781" stroke-width="1.5"/>
    <circle cx="22" cy="22" r="8" fill="none" stroke="#003781" stroke-width="1.5"/>
    <line x1="28" y1="28" x2="35" y2="35" stroke="#003781" stroke-width="1.8" stroke-linecap="round"/>
  </symbol>
  <symbol id="icon-building" viewBox="0 0 48 48">
    <circle cx="24" cy="24" r="22" fill="none" stroke="#003781" stroke-width="1.5"/>
    <rect x="14" y="16" width="20" height="20" rx="1" fill="none" stroke="#003781" stroke-width="1.5"/>
    <rect x="17" y="20" width="4" height="4" rx="0.5" fill="none" stroke="#003781" stroke-width="1.2"/>
    <rect x="26" y="20" width="4" height="4" rx="0.5" fill="none" stroke="#003781" stroke-width="1.2"/>
    <rect x="17" y="27" width="4" height="4" rx="0.5" fill="none" stroke="#003781" stroke-width="1.2"/>
    <rect x="26" y="27" width="4" height="4" rx="0.5" fill="none" stroke="#003781" stroke-width="1.2"/>
    <line x1="20" y1="36" x2="20" y2="36" stroke="#003781" stroke-width="1.5"/>
  </symbol>
  <symbol id="icon-news" viewBox="0 0 48 48">
    <circle cx="24" cy="24" r="22" fill="none" stroke="#003781" stroke-width="1.5"/>
    <rect x="13" y="14" width="22" height="20" rx="1.5" fill="none" stroke="#003781" stroke-width="1.5"/>
    <line x1="17" y1="20" x2="31" y2="20" stroke="#003781" stroke-width="1.5" stroke-linecap="round"/>
    <line x1="17" y1="24" x2="31" y2="24" stroke="#003781" stroke-width="1.5" stroke-linecap="round"/>
    <line x1="17" y1="28" x2="25" y2="28" stroke="#003781" stroke-width="1.5" stroke-linecap="round"/>
  </symbol>
  <symbol id="icon-ai" viewBox="0 0 48 48">
    <circle cx="24" cy="24" r="22" fill="none" stroke="#003781" stroke-width="1.5"/>
    <circle cx="24" cy="22" r="7" fill="none" stroke="#003781" stroke-width="1.5"/>
    <line x1="24" y1="15" x2="24" y2="11" stroke="#003781" stroke-width="1.5" stroke-linecap="round"/>
    <line x1="30" y1="17" x2="33" y2="14" stroke="#003781" stroke-width="1.5" stroke-linecap="round"/>
    <line x1="31" y1="22" x2="35" y2="22" stroke="#003781" stroke-width="1.5" stroke-linecap="round"/>
    <line x1="18" y1="17" x2="15" y2="14" stroke="#003781" stroke-width="1.5" stroke-linecap="round"/>
    <line x1="17" y1="22" x2="13" y2="22" stroke="#003781" stroke-width="1.5" stroke-linecap="round"/>
    <path d="M18 29 Q24 35 30 29" fill="none" stroke="#003781" stroke-width="1.5" stroke-linecap="round"/>
  </symbol>
  <symbol id="icon-trophy" viewBox="0 0 48 48">
    <circle cx="24" cy="24" r="22" fill="none" stroke="#003781" stroke-width="1.5"/>
    <path d="M17 13h14v10a7 7 0 0 1-14 0z" fill="none" stroke="#003781" stroke-width="1.5" stroke-linejoin="round"/>
    <path d="M17 17h-3a3 3 0 0 0 3 6" fill="none" stroke="#003781" stroke-width="1.5"/>
    <path d="M31 17h3a3 3 0 0 1-3 6" fill="none" stroke="#003781" stroke-width="1.5"/>
    <line x1="24" y1="30" x2="24" y2="34" stroke="#003781" stroke-width="1.5" stroke-linecap="round"/>
    <line x1="19" y1="34" x2="29" y2="34" stroke="#003781" stroke-width="1.5" stroke-linecap="round"/>
  </symbol>
</svg>
""", unsafe_allow_html=True)

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
st.title("📉 台股滾動10日跌幅系統 v14")
st.caption(
    "資料來源：Yahoo Finance 還原後股價 | 回測年限：最長15年 | "
    "🆕 v14：分析報告 UI 全面重設計——結論先行橫幅 + 進場時機最佳行突出 + 出場策略模組 + 四格摘要卡 | "
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
    抓台股歷史股價（adjclose）。
    使用 yfinance 繞過境外IP的403封鎖。
    回傳 {日期字串: 收盤價} dict，失敗回傳 {}。
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(code + ".TW")
        end = datetime.today()
        start = end - timedelta(days=days + 10)
        df = ticker.history(start=start.strftime("%Y-%m-%d"),
                            end=end.strftime("%Y-%m-%d"),
                            auto_adjust=True)
        if df is None or df.empty:
            return {}
        prices = {}
        for idx, row in df.iterrows():
            date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, 'strftime') else str(idx)[:10]
            close = row.get('Close')
            if close is not None and close > 0:
                prices[date_str] = round(float(close), 2)
        return prices
    except Exception:
        return {}


def get_yahoo_history_us(code, days=365):
    """
    抓美國指數/ETF歷史資料（SOX、TNX、VIX等，不加.TW後綴）。
    使用 yfinance。
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(code)
        end = datetime.today()
        start = end - timedelta(days=days + 10)
        df = ticker.history(start=start.strftime("%Y-%m-%d"),
                            end=end.strftime("%Y-%m-%d"),
                            auto_adjust=True)
        if df is None or df.empty:
            return {}
        prices = {}
        for idx, row in df.iterrows():
            date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, 'strftime') else str(idx)[:10]
            close = row.get('Close')
            if close is not None:
                prices[date_str] = round(float(close), 2)
        return prices
    except Exception:
        return {}


def get_yahoo_history_15y(code):
    """
    抓台股最長15年歷史股價（用於回測）。
    使用 yfinance，period='max' 自動取最長可用資料。
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(code + ".TW")
        df = ticker.history(period="max", auto_adjust=True)
        if df is None or df.empty:
            return {}
        prices = {}
        cutoff = (datetime.today() - timedelta(days=365 * 15 + 30)).strftime("%Y-%m-%d")
        for idx, row in df.iterrows():
            date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, 'strftime') else str(idx)[:10]
            if date_str < cutoff:
                continue
            close = row.get('Close')
            if close is not None and close > 0:
                prices[date_str] = round(float(close), 2)
        return prices
    except Exception:
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
                horizon_rets[h].append({
                    "ret": round(ret, 2),
                    "year": year,
                    "date": t["date"],
                    "entry_price": entry_price,
                    "future_price": future_price,
                })
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
        v = float(str(val).replace("%", "").replace("⚠️", ""))
        if v >= 80:
            return "background-color: #F86200; color: white; font-weight: bold"
        return ""
    except:
        return ""


def color_winrate_80only(val):
    """連續觸發勝率表專用：只塗 ≥80% 的格子，其他不塗色"""
    if val is None or str(val) in ["", "---", "待觀察"]:
        return ""
    try:
        raw = str(val).replace("⚠️", "").replace("%", "").strip()
        v = float(raw)
        if v >= 80:
            return "background-color: #F86200; color: white; font-weight: bold"
        return "color: #414141"
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
    """輸出 DataFrame 為 HTML 表格，表頭不斷行、字體 14px，文字靠左"""
    html = s.to_html(index=False)
    styled = """
<style>
.stbl { border-collapse: collapse; width: 100%; font-size: 14px; }
.stbl th { background: #003781; color: white; padding: 8px 14px;
           white-space: nowrap; text-align: left; font-size: 13px; font-weight: 600; }
.stbl td { padding: 8px 14px; border-bottom: 1px solid #e0e0e0;
           white-space: nowrap; text-align: left; font-size: 14px; }
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


def build_yearly_cumulative_table(prices_dict, threshold):
    """年度實際累積損益%（按股價進場）：Σ(出場價-進場價)/Σ進場價 × 100，依年度分組"""
    result = run_full_backtest(prices_dict, threshold)
    if not result:
        return None

    rows = []
    for year in sorted(result["yearly"].keys()):
        row = {"年度": year,
               "觸發次數": len(result["yearly"][year]["trigger_dates"]),
               "最長連續觸發": result["yearly"][year]["max_consec"]}
        for h in HORIZONS:
            items = [x for x in result["horizon_rets"][h] if x["year"] == year]
            if items:
                total_entry  = sum(x["entry_price"]  for x in items)
                total_future = sum(x["future_price"] for x in items)
                cum = (total_future - total_entry) / total_entry * 100 if total_entry > 0 else None
                row[str(h) + "天累積%"] = fmt(round(cum, 2)) if cum is not None else "---"
            else:
                row[str(h) + "天累積%"] = "待觀察"
        rows.append(row)

    # 合計列
    total_row = {"年度": "合計", "觸發次數": result["total"],
                 "最長連續觸發": result["max_consecutive"]}
    for h in HORIZONS:
        items = result["horizon_rets"][h]
        if items:
            total_entry  = sum(x["entry_price"]  for x in items)
            total_future = sum(x["future_price"] for x in items)
            cum = (total_future - total_entry) / total_entry * 100 if total_entry > 0 else None
            total_row[str(h) + "天累積%"] = fmt(round(cum, 2)) if cum is not None else "---"
        else:
            total_row[str(h) + "天累積%"] = "---"
    rows.append(total_row)
    return pd.DataFrame(rows)


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



def _tab_icon(icon_id, label, sub=""):
    """產生圓框 SVG icon + 標題的組合 HTML，用於 tab 內頁首"""
    sub_html = '<div style="font-size:13px;color:#888;font-weight:400;margin-top:2px">{}</div>'.format(sub) if sub else ""
    return """
<div style="display:flex;align-items:center;gap:14px;margin:4px 0 16px">
  <svg width="44" height="44" style="flex-shrink:0"><use href="#{icon}"/></svg>
  <div>
    <div style="font-size:20px;font-weight:700;color:#003781">{label}</div>
    {sub}
  </div>
</div>""".format(icon=icon_id, label=label, sub=sub_html)
    """統一區塊標題樣式：藍色數字徽章 + 標題文字"""
    sub_html = '<span style="font-size:12px;color:#888;font-weight:400;margin-left:6px">{}</span>'.format(sub) if sub else ""
    st.markdown("""
<div style="display:flex;align-items:center;gap:8px;margin:8px 0 10px">
  <div style="width:24px;height:24px;border-radius:6px;background:#003781;color:#fff;
       font-size:13px;font-weight:600;display:flex;align-items:center;justify-content:center;flex-shrink:0">{num}</div>
  <span style="font-size:15px;font-weight:600;color:#003781">{text}</span>{sub}
</div>""".format(num=num, text=text, sub=sub_html), unsafe_allow_html=True)


def _section_title(num, text, sub=""):
    """統一區塊標題樣式：藍色數字徽章 + 標題文字"""
    sub_html = '<span style="font-size:13px;color:#888;font-weight:400;margin-left:8px">{}</span>'.format(sub) if sub else ""
    st.markdown("""
<div style="display:flex;align-items:center;gap:8px;margin:10px 0 12px">
  <div style="width:26px;height:26px;border-radius:6px;background:#003781;color:#fff;
       font-size:13px;font-weight:600;display:flex;align-items:center;justify-content:center;flex-shrink:0">{num}</div>
  <span style="font-size:16px;font-weight:600;color:#003781">{text}</span>{sub}
</div>""".format(num=num, text=text, sub=sub_html), unsafe_allow_html=True)


def _render_conclusion_banner(level_now, best_thr, best_h):
    """頂部一句話結論橫幅（v14新增）"""
    if level_now >= 9:
        bg, border, icon, title, sub = (
            "#FEE0CC", "#F86200", "⛔",
            "現在不建議進場（市場第{}級過熱）".format(level_now),
            "即使觸發信號出現，此環境下觸發往往是趨勢下跌開始，而非超跌反彈。建議等市場熱度降至7級以下。"
        )
    elif level_now >= 8:
        bg, border, icon, title, sub = (
            "#FEF0CC", "#FAB600", "⚠️",
            "謹慎進場（市場第{}級偏熱）".format(level_now),
            "建議將觸發門檻提高至 -15% 以上，等更深超跌再進，控制部位規模。"
        )
    else:
        bg, border, icon, title, sub = (
            "#E1F5EE", "#1D9E75", "✅",
            "可以進場（市場第{}級正常）".format(level_now),
            "環境合理，觸發信號出現時按策略執行，建議觸發門檻 {}、持有 {} 天。".format(
                best_thr or "—", best_h or "—")
        )
    st.markdown("""
<div style="background:{bg};border-left:5px solid {bd};border-radius:0 8px 8px 0;
     padding:14px 20px;display:flex;align-items:flex-start;gap:14px;margin-bottom:8px">
  <div style="font-size:24px;line-height:1;margin-top:2px">{ic}</div>
  <div>
    <div style="font-size:15px;font-weight:600;color:#003781;margin-bottom:4px">{t}</div>
    <div style="font-size:13px;color:#414141;line-height:1.5">{s}</div>
  </div>
</div>""".format(bg=bg, bd=border, ic=icon, t=title, s=sub), unsafe_allow_html=True)


def _render_timing_table_v14(df_consec, best_t, diff):
    """進場時機表格——最佳行突出（v14重設計）"""
    if df_consec is None or df_consec.empty:
        return
    drop_c = [c for c in ["累積報酬%"] if c in df_consec.columns]
    df_show = df_consec.drop(columns=drop_c) if drop_c else df_consec.copy()

    # 計算最佳行 index
    best_idx = None
    try:
        valid = df_show[pd.to_numeric(df_show["樣本數"], errors='coerce').fillna(0) >= 5]
        if not valid.empty:
            best_idx = pd.to_numeric(
                valid["平均報酬%"].str.replace("%", ""), errors='coerce').idxmax()
    except Exception:
        pass

    rows_html = ""
    for i, (idx, row) in enumerate(df_show.iterrows()):
        is_best = (idx == best_idx)
        row_bg = "#FEF0CC" if is_best else ("#f8f9fa" if i % 2 else "#ffffff")
        left_border = "border-left:3px solid #F86200;" if is_best else "border-left:3px solid transparent;"

        # 勝率 badge
        wr_str = str(row.get("勝率", "---"))
        try:
            wr_v = float(wr_str.replace("%", ""))
            if wr_v >= 80:
                badge = '<span style="background:#F86200;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:600">{}</span>'.format(wr_str)
            elif wr_v >= 70:
                badge = '<span style="background:#FAB600;color:#414141;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:600">{}</span>'.format(wr_str)
            else:
                badge = '<span style="background:#e0e0e0;color:#414141;padding:2px 8px;border-radius:4px;font-size:12px">{}</span>'.format(wr_str)
        except Exception:
            badge = wr_str

        # 平均報酬
        avg_str = str(row.get("平均報酬%", "---"))
        try:
            avg_v = float(avg_str.replace("%", ""))
            avg_color = "#A32D2D" if avg_v > 0 else "#0F6E56"
            avg_size = "15px" if is_best else "13px"
            avg_weight = "700" if is_best else "500"
            avg_html = '<span style="color:{};font-size:{};font-weight:{}">{}</span>'.format(
                avg_color, avg_size, avg_weight, avg_str)
        except Exception:
            avg_html = avg_str

        timing_label = str(row.get("進場時機", ""))
        if is_best:
            timing_label = "<strong>{}</strong> ★ 最佳".format(timing_label)

        rows_html += """
<tr style="background:{bg};{lb}">
  <td style="padding:9px 12px;border-bottom:0.5px solid #e0e0e0;font-size:13px">{tm}</td>
  <td style="padding:9px 12px;border-bottom:0.5px solid #e0e0e0;font-size:13px;text-align:center">{sn}</td>
  <td style="padding:9px 12px;border-bottom:0.5px solid #e0e0e0;text-align:center">{wr}</td>
  <td style="padding:9px 12px;border-bottom:0.5px solid #e0e0e0;text-align:center">{av}</td>
</tr>""".format(bg=row_bg, lb=left_border,
               tm=timing_label, sn=row.get("樣本數", ""),
               wr=badge, av=avg_html)

    table_html = """
<style>
.tm-table{{border-collapse:collapse;width:100%;font-size:13px}}
.tm-table th{{background:#003781;color:#fff;padding:8px 12px;text-align:center;
             font-weight:500;white-space:nowrap;font-size:12px}}
.tm-table th:first-child{{text-align:left}}
</style>
<table class="tm-table">
  <thead><tr>
    <th>進場時機</th><th>樣本數</th><th>勝率</th><th>平均報酬%</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table>""".format(rows=rows_html)
    st.markdown(table_html, unsafe_allow_html=True)
    st.caption("觀察基準：持有60天　｜　⚠ 樣本<5不具統計意義")

    # 結論框
    if diff is not None:
        if diff < 3.0:
            st.markdown("""
<div style="background:#E6F1FB;border-left:3px solid #003781;border-radius:0 6px 6px 0;
     padding:10px 14px;font-size:13px;color:#003781;margin-top:8px">
⏱ <strong>進場時機結論：各時機差異不大（{:.1f}%），觸發當天直接進場即可，不需要等待。</strong>
</div>""".format(diff), unsafe_allow_html=True)
        else:
            st.markdown("""
<div style="background:#E6F1FB;border-left:3px solid #003781;border-radius:0 6px 6px 0;
     padding:10px 14px;font-size:13px;color:#003781;margin-top:8px">
⏱ <strong>進場時機結論：「{t}」平均報酬最高，比最差時機多 {d:.1f}%，值得等待。</strong>
</div>""".format(t=best_t, d=diff), unsafe_allow_html=True)


def _render_decision_table_v14(best_thr, best_h, second_h, worst_dd, worst_dd_single, level_now):
    """綜合操作建議——三欄決策表 + 四格摘要卡（v14重設計）"""
    rows = [
        ("進場訊號", "滾動10日跌幅達 {}".format(best_thr or "—"), "樣本充足，統計可靠"),
        ("持有期間",
         "首選 {} 天，次選 {} 天".format(best_h or "—", second_h or best_h or "—"),
         "風險報酬比最佳"),
        ("正常浮虧",
         "進場後平均最深 {:.1f}%".format(worst_dd) if worst_dd else "資料不足",
         "屬正常，不建議停損"),
        ("極端風險",
         "史上最深單筆 {:.1f}%".format(worst_dd_single) if worst_dd_single else "資料不足",
         "含金融危機極端情境"),
        ("心理準備", "持有期間忍住浮虧", "歷史上停損反而鎖住虧損"),
    ]
    rows_html = ""
    for i, (label, val, desc) in enumerate(rows):
        bg = "#f8f9fa" if i % 2 else "#ffffff"
        rows_html += """
<tr style="background:{bg};border-bottom:0.5px solid #e0e0e0">
  <td style="padding:9px 14px;font-size:13px;color:#888;white-space:nowrap;width:90px">{lb}</td>
  <td style="padding:9px 14px;font-size:13px;font-weight:600;color:#003781;width:200px">{vl}</td>
  <td style="padding:9px 14px;font-size:14px;color:#414141">{ds}</td>
</tr>""".format(bg=bg, lb=label, vl=val, ds=desc)

    st.markdown("""
<style>
.dt-table{{border-collapse:collapse;width:100%;border-radius:8px;overflow:hidden;
          border:0.5px solid #e0e0e0}}
</style>
<table class="dt-table"><tbody>{}</tbody></table>""".format(rows_html),
        unsafe_allow_html=True)

    # 四格摘要卡
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    best_wr_for_card = "—"
    if best_h:
        pass  # 會在呼叫端傳入
    c1, c2, c3, c4 = st.columns(4)
    def _card(col, label, value, sub, val_color="#003781"):
        col.markdown("""
<div style="background:#f8f9fa;border-radius:8px;padding:14px 16px;border:0.5px solid #e0e0e0">
  <div style="font-size:13px;color:#888;margin-bottom:5px">{lb}</div>
  <div style="font-size:20px;font-weight:600;color:{vc}">{vl}</div>
  <div style="font-size:13px;color:#888;margin-top:5px">{sb}</div>
</div>""".format(lb=label, vl=value, sb=sub, vc=val_color), unsafe_allow_html=True)

    _card(c1, "首選持有天數", "{}天".format(best_h) if best_h else "—",
          "次選 {}天".format(second_h) if second_h else "")
    _card(c2, "正常浮虧上限",
          "{:.1f}%".format(worst_dd) if worst_dd else "—",
          "15年平均最深回撤", val_color="#F86200")
    _card(c3, "極端單筆風險",
          "{:.1f}%".format(worst_dd_single) if worst_dd_single else "—",
          "含金融危機情境", val_color="#A32D2D")
    _card(c4, "進場訊號門檻", best_thr or "—",
          "滾動10日跌幅")

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.caption("本分析基於歷史回測數據自動生成，不構成投資建議。歷史績效不代表未來報酬。")


def _render_exit_strategy_v14(prices_dict, best_thr, best_h, code):
    """
    7️⃣ 出場策略模組（v14新增）
    三層出場邏輯：①時間到期、②報酬目標提前出場、③分批出場建議
    基於歷史回測的報酬分布計算各分位數，給出量化的出場價位建議。
    """
    _section_title("7", "出場策略", "不只看持有幾天——報酬提前到頂時怎麼做")
    st.caption("不只看「持有幾天」——當報酬提前到達目標時，歷史告訴你該怎麼做")

    if not best_thr or not best_h or not prices_dict:
        st.info("需先完成回測計算才能顯示出場策略")
        return

    thr_int = int(best_thr.replace("%", ""))
    result = run_full_backtest(prices_dict, thr_int)
    if not result:
        st.info("此標的回測樣本不足，無法計算出場策略")
        return

    # ── 取最佳持有天數的所有歷史報酬分布 ──
    all_rets = [x["ret"] for x in result["horizon_rets"].get(best_h, [])]
    if len(all_rets) < 5:
        st.info("樣本數不足（{}次），無法可靠計算出場分位數".format(len(all_rets)))
        return

    all_rets_sorted = sorted(all_rets)
    n = len(all_rets_sorted)

    def pct(q):
        idx = max(0, min(n - 1, int(q / 100 * n)))
        return round(all_rets_sorted[idx], 1)

    p25, p50, p75, p90 = pct(25), pct(50), pct(75), pct(90)
    avg_ret = round(sum(all_rets) / n, 1)
    max_ret = round(max(all_rets), 1)
    win_rate = round(sum(1 for r in all_rets if r > 0) / n * 100, 1)

    # ── 路徑分析：計算多少比例的觸發在 best_h 天內曾到達某個高點 ──
    # 對每次觸發，逐日追蹤最高點（用於判斷「提前出場」的合理性）
    triggers = result["triggers"]
    dates = sorted(prices_dict.keys())
    date_to_idx = {d: i for i, d in enumerate(dates)}

    peak_rets = []   # 每次觸發在 best_h 天內曾達到的最高報酬
    day_of_peak = [] # 峰值發生在第幾天
    for t in triggers:
        idx = date_to_idx.get(t["date"])
        if idx is None:
            continue
        ep = t["curr_price"]
        local_max = 0.0
        local_max_day = 0
        for d in range(1, best_h + 1):
            fi = idx + d
            if fi >= len(dates):
                break
            r = (prices_dict[dates[fi]] - ep) / ep * 100
            if r > local_max:
                local_max = r
                local_max_day = d
        if local_max > 0:
            peak_rets.append(round(local_max, 1))
            day_of_peak.append(local_max_day)

    if peak_rets:
        avg_peak = round(sum(peak_rets) / len(peak_rets), 1)
        med_peak_day = sorted(day_of_peak)[len(day_of_peak) // 2]
        pct_reach_10 = round(sum(1 for r in peak_rets if r >= 10) / len(peak_rets) * 100, 1) if peak_rets else 0
        pct_reach_15 = round(sum(1 for r in peak_rets if r >= 15) / len(peak_rets) * 100, 1) if peak_rets else 0
        pct_reach_20 = round(sum(1 for r in peak_rets if r >= 20) / len(peak_rets) * 100, 1) if peak_rets else 0
    else:
        avg_peak = med_peak_day = pct_reach_10 = pct_reach_15 = pct_reach_20 = 0

    # ── UI ──
    # 報酬分布摘要
    st.markdown("#### 📊 歷史報酬分布（持有{}天後，共{}次樣本）".format(best_h, n))
    col1, col2, col3, col4, col5 = st.columns(5)
    def _stat(col, label, val, color="#003781"):
        col.markdown("""
<div style="background:#f8f9fa;border-radius:8px;padding:10px 12px;border:0.5px solid #e0e0e0;text-align:center">
  <div style="font-size:13px;color:#888;margin-bottom:5px">{lb}</div>
  <div style="font-size:20px;font-weight:700;color:{c}">{vl}%</div>
</div>""".format(lb=label, vl=val, c=color), unsafe_allow_html=True)
    _stat(col1, "最差25%（P25）", p25, "#0F6E56" if p25 >= 0 else "#A32D2D")
    _stat(col2, "中位數（P50）", p50, "#0F6E56" if p50 >= 0 else "#A32D2D")
    _stat(col3, "平均報酬", avg_ret, "#0F6E56" if avg_ret >= 0 else "#A32D2D")
    _stat(col4, "優秀75%（P75）", p75, "#0F6E56")
    _stat(col5, "頂部10%（P90）", p90, "#F86200")

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # 三層出場邏輯
    st.markdown("#### 🎯 三層出場策略建議")

    # ── 策略一：時間到期 ──
    with st.expander("**策略一：時間到期出場**（最簡單，適合紀律差的投資人）", expanded=True):
        st.markdown("""
**做法**：進場後直接設定 **{}天** 到期提醒，到期當天無論盈虧全部出場。

**歷史績效**：
- 平均報酬 **{:.1f}%**，勝率 **{:.1f}%**
- 中位數報酬 **{:.1f}%**（超過一半的人可以拿到的報酬）

**適合情境**：你沒有時間每天盯盤、或情緒容易在浮虧時動搖的投資人。
""".format(best_h, avg_ret, win_rate, p50))

    # ── 策略二：提前獲利出場（分位數門檻） ──
    with st.expander("**策略二：報酬目標提前出場**（推薦，鎖住獲利）", expanded=True):
        lines = []
        if avg_peak > 0:
            lines.append("歷史上，進場後持有期間（{}天）的平均**最高點為 +{:.1f}%**，通常發生在第 **{}天** 前後。".format(
                best_h, avg_peak, med_peak_day))
        if pct_reach_10 > 0:
            lines.append("有 **{:.0f}%** 的觸發曾在持有期內達到 +10% 以上".format(pct_reach_10))
        if pct_reach_15 > 0:
            lines.append("有 **{:.0f}%** 的觸發曾達到 +15% 以上".format(pct_reach_15))
        if pct_reach_20 > 0:
            lines.append("有 **{:.0f}%** 的觸發曾達到 +20% 以上".format(pct_reach_20))

        for line in lines:
            st.markdown("- " + line)

        # 推薦門檻
        suggest_tgt = p75 if p75 > 5 else (p50 if p50 > 0 else None)
        if suggest_tgt and suggest_tgt > 0:
            st.markdown("""
---
**建議出場門檻設定：**

| 保守出場 | 標準出場 | 積極持有 |
|---------|---------|---------|
| **+{p50:.1f}%** 達到時出場 | **+{p75:.1f}%** 達到時出場 | 持滿 {bh} 天再出場 |
| 對應歷史中位數 | 對應歷史P75 | 讓獲利繼續跑 |
| 勝率高、報酬穩定 | 比平均多拿 | 適合有耐心的人 |
""".format(p50=p50, p75=p75, bh=best_h))
        else:
            st.info("此標的歷史報酬中位數偏低，建議以時間到期為主要出場方式。")

    # ── 策略三：分批出場 ──
    with st.expander("**策略三：分批出場**（最優化風險報酬，進階用法）", expanded=True):
        if p50 > 0 and p75 > p50:
            st.markdown("""
**做法（以投入100%資金為例）**：

| 批次 | 出場時機 | 出場比例 | 說明 |
|-----|---------|---------|------|
| 第一批 | 報酬達 **+{p50:.1f}%** 或持滿 **{h_half}天** | 出場 **30%** | 先鎖住基本獲利，降低心理壓力 |
| 第二批 | 報酬達 **+{p75:.1f}%** 或持滿 **{bh}天** | 再出場 **50%** | 鎖住大部分獲利 |
| 第三批 | 持滿 **{bh}天** 或報酬回撤超過峰值 **30%** | 出清剩餘 **20%** | 留一部分追尾段漲幅 |

**回撤停利邏輯**：若報酬曾達 +{p75:.1f}% 但後來回撤至 +{stop:.1f}%（峰值-30%），視為峰值已過，提前出場第三批。

**為什麼分批？**  
歷史上報酬分布極不均勻——P25是 {p25:.1f}%、P90是 {p90:.1f}%。分批可以確保在各種情境下都能捕捉到一定獲利，而不是賭全部。
""".format(
                p50=p50, p75=p75, p25=p25, p90=p90,
                bh=best_h,
                h_half=max(5, best_h // 2),
                stop=round(p75 * 0.7, 1)
            ))
        else:
            st.info("此標的歷史報酬中位數偏低，分批出場優勢不明顯，建議使用策略一（時間到期）。")

    st.markdown("""
<div style="background:#E6F1FB;border-left:3px solid #003781;border-radius:0 6px 6px 0;
     padding:10px 14px;font-size:14px;color:#414141;margin-top:8px">
⚡ <strong>出場策略優先序建議</strong>：若無特殊判斷，優先用「策略二標準出場（+{p75:.1f}%）」
＋「時間到期（{bh}天）」雙重觸發——哪個先到就先出。這樣兼顧了獲利鎖定與時間紀律，
歷史上能有效避免「拿到頂點又吐回去」的情況。
</div>""".format(p75=p75, bh=best_h), unsafe_allow_html=True)


def render_analysis(code, df_win, df_avg, df_dd, df_yearly, threshold, prices_dict=None):
    """直接用Streamlit元件render分析報告，v14全面重設計"""
    import statistics

    # ══════════════════════════════════════════════════════
    # 報告標題
    # ══════════════════════════════════════════════════════
    st.markdown("""
<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
  <div style="width:36px;height:36px;border-radius:8px;background:#003781;color:#fff;
       font-size:18px;display:flex;align-items:center;justify-content:center;flex-shrink:0">📊</div>
  <div>
    <div style="font-size:20px;font-weight:700;color:#003781">回測分析報告</div>
    <div style="font-size:13px;color:#888;margin-top:1px">{code}　｜　{date}</div>
  </div>
</div>""".format(code=code, date=datetime.now().strftime("%Y-%m-%d")), unsafe_allow_html=True)

    # 當前市場背景——統一灰底卡片
    twii_now = get_twii_heat()
    fin_now = get_fin_data_yfinance(code)
    roe_now   = fin_now.get('roe')
    debt_now  = fin_now.get('debt_ratio')
    pb_now    = fin_now.get('pb')
    eps_now   = fin_now.get('trailing_eps')

    def _mini_card(col, label, value, hint="", val_color="#003781"):
        col.markdown("""
<div style="background:#f8f9fa;border-radius:8px;border:0.5px solid #e0e0e0;padding:12px 14px">
  <div style="font-size:13px;color:#888;margin-bottom:5px">{lb}</div>
  <div style="font-size:22px;font-weight:700;color:{vc}">{vl}</div>
  {hint_html}
</div>""".format(lb=label, vc=val_color, vl=value,
        hint_html='<div style="font-size:13px;color:#888;margin-top:5px">{}</div>'.format(hint) if hint else ""),
        unsafe_allow_html=True)

    level_val = twii_now["level"] if twii_now else None
    level_str = "第{}級".format(level_val) if level_val else "—"
    level_color = "#A32D2D" if (level_val and level_val >= 9) else ("#F86200" if (level_val and level_val >= 8) else "#003781")
    level_hint = twii_now.get("label", "") if twii_now else ""

    def _is_valid_num(v):
        if v is None: return False
        try:
            import math; return not math.isnan(float(v))
        except Exception: return False

    col_bg1, col_bg2, col_bg3, col_bg4, col_bg5 = st.columns(5)
    _mini_card(col_bg1, "市場熱度", level_str, level_hint, level_color)
    _mini_card(col_bg2, "ROE",
               "{}%".format(round(float(roe_now), 1)) if _is_valid_num(roe_now) else "—",
               "優秀(≥15%)" if _is_valid_num(roe_now) and float(roe_now) >= 15 else ("普通(≥8%)" if _is_valid_num(roe_now) and float(roe_now) >= 8 else "偏弱") if _is_valid_num(roe_now) else "無資料",
               "#0F6E56" if _is_valid_num(roe_now) and float(roe_now) >= 15 else ("#F86200" if _is_valid_num(roe_now) and float(roe_now) >= 8 else "#A32D2D") if _is_valid_num(roe_now) else "#888")
    _mini_card(col_bg3, "負債比",
               "{}%".format(round(float(debt_now), 1)) if _is_valid_num(debt_now) else "—",
               "健康(<50%)" if _is_valid_num(debt_now) and float(debt_now) < 50 else ("偏高(<65%)" if _is_valid_num(debt_now) and float(debt_now) < 65 else "過高") if _is_valid_num(debt_now) else "無資料",
               "#0F6E56" if _is_valid_num(debt_now) and float(debt_now) < 50 else ("#F86200" if _is_valid_num(debt_now) and float(debt_now) < 65 else "#A32D2D") if _is_valid_num(debt_now) else "#888")
    _mini_card(col_bg4, "PB",
               str(round(float(pb_now), 2)) if _is_valid_num(pb_now) else "—",
               "合理(<3)" if _is_valid_num(pb_now) and float(pb_now) < 3 else ("偏貴(<5)" if _is_valid_num(pb_now) and float(pb_now) < 5 else "高估") if _is_valid_num(pb_now) else "無資料")
    _mini_card(col_bg5, "EPS(年)",
               str(round(float(eps_now), 2)) if _is_valid_num(eps_now) else "—",
               "獲利穩定" if _is_valid_num(eps_now) and float(eps_now) > 0 else "虧損" if _is_valid_num(eps_now) else "無資料",
               "#0F6E56" if _is_valid_num(eps_now) and float(eps_now) > 0 else "#A32D2D" if _is_valid_num(eps_now) else "#888")
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    worst_dd = None
    worst_dd_single = None
    best_h = None
    second_h = None

    # ══════════════════════════════
    # 1. 最佳觸發門檻
    # ══════════════════════════════
    _section_title("1", "建議觸發門檻")

    thr_scores = []
    for _, row in df_win.iterrows():
        thr_str = row["觸發門檻"]
        samples = int(row.get("樣本數", 0))
        wr_100 = row.get("100天勝率", "0%")
        avg_100 = df_avg[df_avg["觸發門檻"] == thr_str]["100天平均報酬%"].values
        try:
            wr_v = float(str(wr_100).replace("%", ""))
            avg_v = float(str(avg_100[0]).replace("%", "")) if len(avg_100) > 0 and str(avg_100[0]) not in ["待觀察", "---"] else 0
            score = wr_v * 0.6 + avg_v * 0.4
            thr_scores.append((thr_str, samples, score, wr_v, avg_v))
        except Exception:
            pass

    valid_thrs = [(t, s, sc, w, a) for t, s, sc, w, a in thr_scores if s >= 5]
    if not valid_thrs:
        valid_thrs = [(t, s, sc, w, a) for t, s, sc, w, a in thr_scores if s >= 3]

    best_thr = None
    if valid_thrs:
        best_thr = max(valid_thrs, key=lambda x: x[2])[0]

    effective_thr = best_thr
    if best_thr:
        best_samples = next((s for t, s, sc, w, a in valid_thrs if t == best_thr), 0)
        if best_samples < 10:
            reliable_thrs = [(t, s, sc, w, a) for t, s, sc, w, a in thr_scores if s >= 10]
            if reliable_thrs:
                effective_thr = max(reliable_thrs, key=lambda x: x[2])[0]

    if best_thr:
        best_info = next((x for x in thr_scores if x[0] == best_thr), None)
        eff_info  = next((x for x in thr_scores if x[0] == effective_thr), None)

        if best_thr != effective_thr:
            st.info(
                "📌 「{}」理論最高勝率，但樣本僅{}次（統計不可靠）。"
                "→ 建議使用「{}」作為主要分析門檻（{}次觸發，樣本充足）".format(
                    best_thr, best_info[1] if best_info else "?",
                    effective_thr, eff_info[1] if eff_info else "?"
                )
            )
        thr_rows = []
        for thr_str, samples, score, wr_v, avg_v in thr_scores:
            first_80 = None
            row_w = df_win[df_win["觸發門檻"] == thr_str]
            if not row_w.empty:
                for h in HORIZONS:
                    try:
                        v = float(str(row_w.iloc[0].get(str(h) + "天勝率", "0")).replace("%", ""))
                        if v >= 80 and first_80 is None:
                            first_80 = h
                    except Exception:
                        pass
            marker = "★ 建議" if thr_str == effective_thr else (
                "△ 理論最佳" if thr_str == best_thr and best_thr != effective_thr else "")
            thr_rows.append({
                "門檻": thr_str,
                "15年觸發次數": "{}{}".format(samples, "⚠️" if samples < 10 else ""),
                "100天勝率": "{:.1f}%".format(wr_v),
                "達80%勝率最短持有": "{}天".format(first_80) if first_80 else "未達80%",
                "建議": marker,
            })
        show_html(pd.DataFrame(thr_rows))
        st.caption("⚠️ = 樣本不足10次，勝率數字易因少數極端值失真　★ = 本報告主要分析門檻")
        best_thr = effective_thr
    st.divider()

    # ══════════════════════════════
    # 2. 最佳持有天數
    # ══════════════════════════════
    _section_title("2", "最佳持有天數建議")

    if best_thr:
        thr_avg_row = df_avg[df_avg["觸發門檻"] == best_thr]
        thr_dd_row  = df_dd[df_dd["觸發門檻"] == best_thr]
        ratios = []
        for h in HORIZONS:
            avg_col = str(h) + "天平均報酬%"
            dd_col  = str(h) + "天平均最大回撤%"
            try:
                avg_v = float(str(thr_avg_row[avg_col].values[0]).replace("%", ""))
                dd_v  = float(str(thr_dd_row[dd_col].values[0]).replace("%", ""))
                dd_denom = max(abs(dd_v), 1.0)
                ratio = avg_v / dd_denom
                ratios.append((h, ratio, avg_v, dd_v))
            except Exception:
                pass
        ratios.sort(key=lambda x: x[1], reverse=True)

        if ratios:
            best_h   = ratios[0][0]
            avg_val  = ratios[0][2]
            dd_val   = ratios[0][3]

            col1, col2 = st.columns(2)
            with col1:
                st.success(
                    "🥇 **首選：持有 {} 天**\n\n"
                    "平均報酬：**{:.2f}%**\n\n"
                    "平均最大回撤：**{:.2f}%**\n\n"
                    "風險報酬比：**{:.2f}**（越高越划算）".format(best_h, avg_val, dd_val, ratios[0][1])
                )
            for h2, ratio2, avg2, dd2 in ratios[1:]:
                if h2 < best_h:
                    second_h = h2
                    with col2:
                        st.info(
                            "🥈 **次選（較短持有）：持有 {} 天**\n\n"
                            "平均報酬：**{:.2f}%**\n\n"
                            "平均最大回撤：**{:.2f}%**\n\n"
                            "風險報酬比：**{:.2f}**（適合不想持有太久的投資人）".format(
                                h2, avg2, dd2, ratio2)
                        )
                    break
    st.divider()

    # ══════════════════════════════
    # 3. 歷史規律
    # ══════════════════════════════
    _section_title("3", "歷史規律", "哪些年觸發後特別強或弱")
    st.caption("分析哪些年度觸發後表現特別好或特別差，幫助判斷「現在的市場環境」是否類似歷史上的好年或壞年")

    if df_yearly is not None and len(df_yearly) > 2:
        yearly_data = df_yearly[df_yearly["年度"] != "合計/平均"].copy()
        col_key = "100天平均%"
        year_vals = []
        for _, row in yearly_data.iterrows():
            try:
                year_vals.append((str(row["年度"]), float(str(row.get(col_key, "0")).replace("%", ""))))
            except Exception:
                pass
        valid_vals = [v for _, v in year_vals]
        if valid_vals:
            try:
                med   = statistics.median(valid_vals)
                stdev = statistics.stdev(valid_vals) if len(valid_vals) > 1 else 5.0
            except Exception:
                med   = sum(valid_vals) / len(valid_vals)
                stdev = 5.0

            good_years = [(y, v) for y, v in year_vals if v > med + stdev]
            bad_years  = [(y, v) for y, v in year_vals if v < med - stdev]

            col1, col2 = st.columns(2)
            with col1:
                if good_years:
                    st.success(
                        "📈 **觸發後反彈特別強的年度**\n\n" +
                        "\n\n".join(["**{}**：{:.1f}%".format(y, v) for y, v in good_years]) +
                        "\n\n→ 這些年市場屬短暫超跌後快速修復，進場時機極佳"
                    )
                else:
                    st.info("📈 無特別突出的強勢年度")
            with col2:
                if bad_years:
                    st.warning(
                        "📉 **觸發後反彈較弱或繼續跌的年度**\n\n" +
                        "\n\n".join(["**{}**：{:.1f}%".format(y, v) for y, v in bad_years]) +
                        "\n\n→ 這些年通常處於系統性風險環境（升息、貿易戰、金融危機）"
                    )
                else:
                    st.info("📉 無特別突出的弱勢年度")

            st.info(
                "💡 **投資判斷提示**：若目前總體環境類似歷史上的「壞年」，"
                "建議縮小進場規模或提高觸發門檻；若只是短暫情緒性修正，則可以積極進場。\n\n"
                "（15年100天平均報酬中位數：{:.1f}%，標準差：{:.1f}%）".format(med, stdev)
            )
    st.divider()

    # ══════════════════════════════
    # 4. 風險提示
    # ══════════════════════════════
    _section_title("4", "風險提示")
    st.caption("以下數字是指你進場後的報酬虧損幅度（相對你的進場價），不是股價的絕對跌幅")

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
            worst_dd        = dd_main["avg_dd"]
            worst_dd_single = dd_main["worst_single"]

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
                st.markdown("**▍ 主要建議門檻 {}**（15年觸發 {} 次）".format(best_thr, dd_main["total"]))
                st.markdown(
                    "- 一般情況：進場後平均最深虧損約 **{:.1f}%**\n"
                    "- 最壞情況：史上最深單筆虧損 **{:.1f}%**（含金融危機、疫情崩盤）\n"
                    "- 最差年度：**{}年**，該年平均最深虧損 {:.1f}%\n"
                    "- 只要不中途停損，有 **{:.0f}%** 的機率在{}天內回到正報酬".format(
                        dd_main["avg_dd"], dd_main["worst_single"],
                        dd_main["worst_year"] or "N/A",
                        dd_main["worst_year_dd"],
                        dd_main["wr"], HORIZONS[-1]
                    )
                )

        if alt_thr:
            dd_alt = get_dd_summary(alt_thr, prices_dict)
            with cols[1]:
                if dd_alt:
                    st.markdown("**▍ 次要參考門檻 {}**（15年觸發 {} 次，樣本較充足）".format(alt_thr, dd_alt["total"]))
                    st.markdown(
                        "- 一般情況：進場後平均最深虧損約 **{:.1f}%**\n"
                        "- 最壞情況：史上最深單筆虧損 **{:.1f}%**\n"
                        "- 最差年度：**{}年**，該年平均最深虧損 {:.1f}%\n"
                        "- 只要不中途停損，有 **{:.0f}%** 的機率在{}天內回到正報酬".format(
                            dd_alt["avg_dd"], dd_alt["worst_single"],
                            dd_alt["worst_year"] or "N/A",
                            dd_alt["worst_year_dd"],
                            dd_alt["wr"], HORIZONS[-1]
                        )
                    )

        st.warning("💡 「忍住浮虧不停損」在歷史上是正確的做法——停損反而把虧損鎖住了。")
    st.divider()

    # ══════════════════════════════
    # 5. 進場時機建議（v14重設計）
    # ══════════════════════════════
    _section_title("5", "進場時機")
    best_t_timing = None
    diff_timing   = None
    if prices_dict and best_thr:
        thr_val_int   = int(best_thr.replace("%", ""))
        df_consec_60  = build_entry_timing_table(prices_dict, thr_val_int, 60)

        if df_consec_60 is not None:
            valid_rows = df_consec_60[pd.to_numeric(
                df_consec_60["樣本數"], errors='coerce').fillna(0) >= 5]
            if not valid_rows.empty:
                best_row_t  = valid_rows.loc[
                    pd.to_numeric(valid_rows["平均報酬%"].str.replace("%", ""), errors='coerce').idxmax()]
                worst_row_t = valid_rows.loc[
                    pd.to_numeric(valid_rows["平均報酬%"].str.replace("%", ""), errors='coerce').idxmin()]
                best_t_timing = best_row_t["進場時機"]
                try:
                    diff_timing = (float(str(best_row_t["平均報酬%"]).replace("%", "")) -
                                   float(str(worst_row_t["平均報酬%"]).replace("%", "")))
                except Exception:
                    diff_timing = 0
            _render_timing_table_v14(df_consec_60, best_t_timing, diff_timing)
        else:
            st.info("樣本數不足，無法計算進場時機分析")
    st.divider()

    # ══════════════════════════════
    # 6. 綜合操作建議（v14重設計）
    # ══════════════════════════════
    _section_title("6", "綜合操作建議")
    level_now = twii_now["level"] if twii_now else 6

    # 頂部結論橫幅
    _render_conclusion_banner(level_now, best_thr, best_h)

    if best_thr and best_h:
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        _render_decision_table_v14(best_thr, best_h, second_h, worst_dd, worst_dd_single, level_now)
    st.divider()

    # ══════════════════════════════
    # 7. 出場策略（v14新增）
    # ══════════════════════════════
    if prices_dict and best_thr and best_h:
        _render_exit_strategy_v14(prices_dict, best_thr, best_h, code)

    # ══════════════════════════════
    # 8. 智能操作解讀（分析師＋交易員＋經理人三方觀點）
    # ══════════════════════════════
    if prices_dict and df_win is not None:
        _render_smart_analysis(code, prices_dict, df_win, df_avg)


def _render_smart_analysis(code, prices_dict, df_win, df_avg):
    """
    智能操作解讀引擎：從回測數據自動生成三層分析
    ① 分析師：門檻特性解讀（哪個門檻才值得進）
    ② 交易員：趨勢位置判斷（現在在哪個位置）
    ③ 基金經理人：三情境操作劇本
    """
    _section_title("8", "智能操作解讀",
                   "分析師 · 交易員 · 基金經理人三方觀點")

    dates = sorted(prices_dict.keys())
    price_list = [prices_dict[d] for d in dates]
    curr_price = price_list[-1]

    # ── 計算各門檻的「可靠勝率」（樣本≥10次的最高勝率門檻）──
    thr_analysis = []
    for _, row in df_win.iterrows():
        thr_str = row["觸發門檻"]
        samples = int(row.get("樣本數", 0))
        try:
            thr_int = int(thr_str.replace("%", ""))
        except Exception:
            continue

        # 找最高勝率的持有天數（樣本≥5）
        best_wr, best_h_for_thr, best_horizon_wr = 0, None, 0
        for h in HORIZONS:
            col = "{}天勝率".format(h)
            try:
                wr = float(str(row.get(col, "0")).replace("%", ""))
                if wr > best_wr:
                    best_wr = wr
                    best_h_for_thr = h
            except Exception:
                pass

        # 平均報酬（對應最佳持有天數）
        avg_ret = None
        try:
            avg_row = df_avg[df_avg["觸發門檻"] == thr_str]
            if not avg_row.empty and best_h_for_thr:
                avg_ret = float(str(avg_row.iloc[0].get(
                    "{}天平均報酬%".format(best_h_for_thr), "0")
                ).replace("%", ""))
        except Exception:
            pass

        thr_analysis.append({
            "thr": thr_str, "thr_int": thr_int,
            "samples": samples, "best_wr": best_wr,
            "best_h": best_h_for_thr, "avg_ret": avg_ret,
            "reliable": samples >= 10,
        })

    thr_analysis.sort(key=lambda x: x["thr_int"])  # 由淺到深

    # 找主推門檻（可靠且勝率最高）
    reliable = [t for t in thr_analysis if t["reliable"]]
    if not reliable:
        reliable = thr_analysis
    main_thr   = max(reliable, key=lambda x: x["best_wr"]) if reliable else None
    # 找積極加碼門檻（比主推更深且有樣本）
    aggressive = None
    if main_thr:
        deeper = [t for t in thr_analysis if t["thr_int"] < main_thr["thr_int"] and t["samples"] >= 5]
        if deeper:
            aggressive = max(deeper, key=lambda x: x["best_wr"])

    # ── 趨勢位置計算 ──
    ma60  = sum(price_list[-60:])  / min(60,  len(price_list))
    ma120 = sum(price_list[-120:]) / min(120, len(price_list))
    ma240 = sum(price_list[-240:]) / min(240, len(price_list))

    # 52週高低點
    w52_high = max(price_list[-252:]) if len(price_list) >= 252 else max(price_list)
    w52_low  = min(price_list[-252:]) if len(price_list) >= 252 else min(price_list)
    pct_from_high = (curr_price - w52_high) / w52_high * 100
    pct_from_low  = (curr_price - w52_low)  / w52_low  * 100

    # 均線多空判斷
    ma60_prev  = sum(price_list[-80:-20])  / 60  if len(price_list) >= 80  else ma60
    ma120_prev = sum(price_list[-140:-20]) / 120 if len(price_list) >= 140 else ma120
    ma60_rising  = ma60  > ma60_prev  * 1.005
    ma120_rising = ma120 > ma120_prev * 1.003

    if curr_price > ma60 > ma120 and ma60_rising and ma120_rising:
        trend_label = "多頭格局"
        trend_color = "#0F6E56"
        trend_desc  = "股價站穩60日與120日均線之上，且均線方向向上，屬於多頭趨勢中的超跌機會。"
    elif curr_price > ma120 and ma120_rising:
        trend_label = "偏多格局"
        trend_color = "#185FA5"
        trend_desc  = "股價在120日均線之上，中期趨勢仍偏多，但短期均線已走平，需確認方向。"
    elif curr_price < ma120 and not ma120_rising:
        trend_label = "空頭格局"
        trend_color = "#A32D2D"
        trend_desc  = "股價跌破120日均線且均線方向向下，屬中期下跌趨勢，超跌反彈力道可能有限。"
    else:
        trend_label = "盤整格局"
        trend_color = "#F86200"
        trend_desc  = "股價在均線附近震盪，方向不明確，需等待明確突破方向再評估。"

    # 股價位階判斷
    if pct_from_high > -10:
        pos_label = "歷史相對高位"
        pos_color = "#A32D2D"
        pos_desc  = "目前股價接近52週高點（距高點 {:.1f}%），估值相對偏高，超跌後的反彈空間可能有限。建議等待更深的修正再考慮進場。".format(pct_from_high)
    elif pct_from_high > -25:
        pos_label = "中間位置"
        pos_color = "#F86200"
        pos_desc  = "目前股價已從52週高點修正 {:.1f}%，進入中間位置。若業績無重大惡化，屬合理的進場觀察區。".format(abs(pct_from_high))
    else:
        pos_label = "歷史相對低位"
        pos_color = "#0F6E56"
        pos_desc  = "目前股價已從52週高點大幅修正 {:.1f}%，接近歷史低估區。若基本面未惡化，是系統設計最能發揮威力的進場時機。".format(abs(pct_from_high))

    # ── 分析師觀點 ──
    st.markdown("""
<div style="background:#f8f9fa;border-radius:10px;border:0.5px solid #e0e0e0;padding:18px 22px;margin-bottom:12px">
  <div style="font-size:13px;font-weight:600;color:#888;margin-bottom:10px;letter-spacing:1px">📊 分析師觀點：哪個門檻才值得進？</div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin-bottom:14px">""",
        unsafe_allow_html=True)

    # 各門檻概覽卡片
    cards_html = ""
    for t in thr_analysis:
        is_main = (main_thr and t["thr"] == main_thr["thr"])
        is_agg  = (aggressive and t["thr"] == aggressive["thr"])
        border  = "2px solid #0F6E56" if is_main else ("2px solid #F86200" if is_agg else "0.5px solid #e0e0e0")
        badge   = '<div style="font-size:11px;background:#0F6E56;color:#fff;padding:2px 8px;border-radius:3px;margin-bottom:6px;display:inline-block">★ 主推</div>' if is_main else (
                  '<div style="font-size:11px;background:#F86200;color:#fff;padding:2px 8px;border-radius:3px;margin-bottom:6px;display:inline-block">▲ 積極</div>' if is_agg else "")
        wr_color = "#0F6E56" if t["best_wr"] >= 80 else ("#F86200" if t["best_wr"] >= 65 else "#888")
        reliable_tag = "" if t["reliable"] else '<div style="font-size:11px;color:#A32D2D;margin-top:4px">⚠ 樣本僅{}次</div>'.format(t["samples"])
        cards_html += """
<div style="background:#fff;border-radius:8px;border:{bd};padding:12px 14px">
  {badge}
  <div style="font-size:15px;font-weight:700;color:#003781">{thr}</div>
  <div style="font-size:12px;color:#888;margin-top:3px">樣本 {n} 次</div>
  <div style="font-size:18px;font-weight:700;color:{wrc};margin-top:6px">{wr:.1f}%</div>
  <div style="font-size:12px;color:#888">最高勝率（持有{h}天）</div>
  {rtag}
</div>""".format(bd=border, badge=badge, thr=t["thr"], n=t["samples"],
                 wrc=wr_color, wr=t["best_wr"], h=t["best_h"] or "—", rtag=reliable_tag)

    st.markdown(cards_html + "</div>", unsafe_allow_html=True)

    # 分析師文字解讀
    analyst_text = ""
    if main_thr:
        analyst_text = "主推門檻 <strong>{}</strong>（{}次樣本，{:.0f}天勝率最高達 <strong>{:.1f}%</strong>）。".format(
            main_thr["thr"], main_thr["samples"], main_thr["best_h"] or 0, main_thr["best_wr"])
        if aggressive:
            analyst_text += " 若市場恐慌性大跌觸及 <strong>{}</strong>（{}次樣本，勝率 {:.1f}%），則屬罕見的積極加碼機會。".format(
                aggressive["thr"], aggressive["samples"], aggressive["best_wr"])
        # 判斷「要等更深才進」
        shallow = [t for t in thr_analysis if t["thr_int"] >= -10 and t["reliable"]]
        if shallow and main_thr["thr_int"] < -10:
            max_shallow_wr = max(t["best_wr"] for t in shallow)
            analyst_text += " 注意：{} 門檻的勝率僅 {:.0f}%，遠低於主推門檻，<strong>代表這檔股票要等夠深的跌幅才值得進場，不宜在第一波下跌就追進。</strong>".format(
                shallow[-1]["thr"], max_shallow_wr)

    st.markdown('<div style="font-size:14px;color:#414141;line-height:1.8">{}</div></div>'.format(analyst_text),
                unsafe_allow_html=True)

    # ── 交易員觀點 ──
    st.markdown("""
<div style="background:#f8f9fa;border-radius:10px;border:0.5px solid #e0e0e0;padding:18px 22px;margin-bottom:12px">
  <div style="font-size:13px;font-weight:600;color:#888;margin-bottom:12px;letter-spacing:1px">📉 交易員觀點：現在在哪個位置？</div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:14px">""",
        unsafe_allow_html=True)

    def _pos_card(label, value, sub, color="#003781"):
        return """<div style="background:#fff;border-radius:8px;border:0.5px solid #e0e0e0;padding:12px 14px">
  <div style="font-size:12px;color:#888;margin-bottom:4px">{lb}</div>
  <div style="font-size:18px;font-weight:700;color:{c}">{vl}</div>
  <div style="font-size:12px;color:#888;margin-top:3px">{sb}</div>
</div>""".format(lb=label, c=color, vl=value, sb=sub)

    pos_cards = (
        _pos_card("現價", "{:.1f}".format(curr_price), "今日收盤")
        + _pos_card("距52週高點", "{:.1f}%".format(pct_from_high),
                    "{:.1f}元".format(w52_high),
                    "#A32D2D" if pct_from_high > -10 else ("#F86200" if pct_from_high > -25 else "#0F6E56"))
        + _pos_card("均線格局", trend_label, "60日/120日均線判斷", trend_color)
    )
    st.markdown(pos_cards + "</div>", unsafe_allow_html=True)

    st.markdown("""
<div style="background:#fff;border-radius:8px;border-left:4px solid {tc};padding:12px 16px;margin-bottom:4px">
  <div style="font-size:13px;font-weight:600;color:{tc};margin-bottom:4px">{pl}</div>
  <div style="font-size:14px;color:#414141;line-height:1.7">{pd}</div>
</div>
<div style="background:#fff;border-radius:8px;border-left:4px solid {tc2};padding:12px 16px">
  <div style="font-size:13px;font-weight:600;color:{tc2};margin-bottom:4px">{tl}</div>
  <div style="font-size:14px;color:#414141;line-height:1.7">{td}</div>
</div></div>""".format(
        tc=pos_color, pl=pos_label, pd=pos_desc,
        tc2=trend_color, tl=trend_label, td=trend_desc),
        unsafe_allow_html=True)

    # ── 基金經理人觀點：三情境操作劇本 ──
    st.markdown("""
<div style="background:#f8f9fa;border-radius:10px;border:0.5px solid #e0e0e0;padding:18px 22px">
  <div style="font-size:13px;font-weight:600;color:#888;margin-bottom:14px;letter-spacing:1px">💼 基金經理人觀點：三情境操作劇本</div>""",
        unsafe_allow_html=True)

    # 劇本一：等待
    observe_thr = thr_analysis[1]["thr"] if len(thr_analysis) > 1 else (thr_analysis[0]["thr"] if thr_analysis else "-5%")
    # 劇本二：建倉（主推門檻）
    build_thr = main_thr["thr"] if main_thr else "-10%"
    build_wr  = main_thr["best_wr"] if main_thr else 0
    build_h   = main_thr["best_h"] if main_thr else 120
    build_ret = main_thr["avg_ret"] if main_thr and main_thr["avg_ret"] else 0
    # 劇本三：積極加碼（更深門檻）
    agg_thr = aggressive["thr"] if aggressive else build_thr
    agg_wr  = aggressive["best_wr"] if aggressive else build_wr
    agg_h   = aggressive["best_h"] if aggressive else build_h

    scenarios = [
        {
            "no": "情境一", "action": "持續觀察，不進場",
            "trigger": "觸發門檻僅達 {} 以內".format(observe_thr),
            "reason": "淺跌信號的歷史勝率不穩定，進場後容易承受更大浮虧。此時應耐心等待更深的修正。",
            "position": "0%",
            "color": "#888",
        },
        {
            "no": "情境二", "action": "開始建倉",
            "trigger": "觸發門檻達 {}".format(build_thr),
            "reason": "歷史{}次樣本，最高勝率 {:.0f}%（持有{}天），平均報酬 {:.1f}%。這是系統驗證過的主要進場信號。".format(
                main_thr["samples"] if main_thr else "—",
                build_wr, build_h, build_ret),
            "position": "50-70%",
            "color": "#185FA5",
        },
        {
            "no": "情境三", "action": "積極加碼",
            "trigger": "觸發門檻達 {}（恐慌性大跌）".format(agg_thr),
            "reason": "{}次樣本，勝率 {:.0f}%（持有{}天）。市場恐慌往往是最好的進場點，此時全力加碼。".format(
                aggressive["samples"] if aggressive else "—",
                agg_wr, agg_h),
            "position": "100%",
            "color": "#0F6E56",
        },
    ]

    for s in scenarios:
        st.markdown("""
<div style="background:#fff;border-radius:8px;border:0.5px solid #e0e0e0;padding:14px 18px;margin-bottom:8px;
     display:grid;grid-template-columns:90px 1fr 80px;gap:14px;align-items:start">
  <div>
    <div style="font-size:12px;color:#888">{no}</div>
    <div style="font-size:15px;font-weight:700;color:{c};margin-top:3px">{action}</div>
  </div>
  <div>
    <div style="font-size:13px;font-weight:600;color:#003781;margin-bottom:4px">📍 {trigger}</div>
    <div style="font-size:13px;color:#414141;line-height:1.7">{reason}</div>
  </div>
  <div style="text-align:center;background:#f8f9fa;border-radius:6px;padding:8px">
    <div style="font-size:11px;color:#888">建議倉位</div>
    <div style="font-size:18px;font-weight:700;color:{c}">{pos}</div>
  </div>
</div>""".format(no=s["no"], c=s["color"], action=s["action"],
                trigger=s["trigger"], reason=s["reason"], pos=s["position"]),
            unsafe_allow_html=True)

    st.markdown("""
<div style="font-size:12px;color:#888;margin-top:8px;padding:8px 4px;border-top:0.5px solid #e0e0e0">
本解讀由系統根據15年回測數據自動生成，不構成投資建議。實際操作請結合基本面與市場環境判斷。
</div></div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
# MOPS 重大訊息關鍵字（根據 MOPS 重訊主旨的實際用語設計）
# 注意：這邊用詞要貼近「MOPS 主旨欄位的官方文字」，不是口語
# ══════════════════════════════════════════════════════════
MOPS_DANGER_KW = [
    # 財務危機
    "掏空", "侵占", "背信", "詐欺", "違約", "停業",
    "清算", "破產", "聲請重整", "無法繼續",
    "財務困難", "財報重編", "重大虧損", "業績大幅衰退",
    # 法律/監管
    "撤銷上市", "廢止上市", "警示股票", "全額交割",
    "配合檢調", "搜索調查", "司法調查", "遭檢察署",
    "起訴", "聲請假扣押", "假處分",
    # 會計師
    "會計師出具保留", "會計師出具否定", "無法表示意見",
    "會計師辭任", "更換會計師", "更換簽證會計師",
    # 董監事/高管異動（MOPS 主旨用語）
    "辭任董事長", "辭任總經理", "辭任財務長", "辭任執行長",
    "解任董事", "撤換董事", "臨時董事會",
    "董事長異動", "董事會改選", "重大人事異動",
    # 股權/大股東
    "申報轉讓", "強制執行", "股票質押遭強制",
    "主要股東", "持股低於", "公開收購",
    # 營運
    "主要客戶終止", "重大合約終止", "工廠停工", "停產",
    "裁員", "歇業", "暫停營業",
    # 法說會異動（基金經理人特別強調）
    "法說會取消", "法說會延期", "法說會暫停", "法人說明會取消",
]

MOPS_WARN_KW = [
    # 治理
    "內控缺失", "內部控制", "內部稽核異常",
    "更換簽證", "更換審計", "會計師事務所變更",
    # 人事
    "發言人異動", "財務主管異動", "會計主管異動",
    "董事辭任", "監察人辭任", "獨立董事辭任",
    "代理董事長", "代理總經理",
    # 合約/客戶
    "主要客戶調整", "合約異動", "訂單調整",
    # 財務
    "現金增資", "可轉換公司債", "債務展期",
    "流動比率", "速動比率", "負債比率偏高",
    # 處置措施
    "交易所公布", "注意股票", "異常股票",
]

# ══════════════════════════════════════════════════════════
# 新聞搜尋關鍵字（根據媒體實際報導用語設計，比 MOPS 更口語化）
# 注意：這邊要貼近「媒體標題的口語化用詞」
# ══════════════════════════════════════════════════════════
NEWS_DANGER_KW = [
    # 犯罪/法律（媒體用語）
    "掏空", "侵占", "背信", "詐欺", "弊案",
    "檢調", "搜索", "約談", "羈押", "起訴", "判刑",
    "違規", "不法", "非法",
    # 公司治理危機（媒體用語）
    "閃辭", "無預警辭", "突然辭", "緊急辭",
    "經營權爭", "大股東失和", "經營權糾紛",
    "惡意收購", "強行入主", "粗暴", "奪權",
    # 法說/溝通異常（媒體用語）
    "法說會取消", "法說會喊卡", "法說會緊急取消",
    "拒絕媒體", "不接受訪問",
    # 股價異常（媒體用語）
    "連續跌停", "跌停鎖死", "崩跌", "暴跌",
    "股價腰斬", "股價崩潰",
    # 財務危機（媒體用語）
    "財報造假", "帳目不清", "財務黑洞",
    "票據跳票", "現金危機",
    # 監管處置
    "全額交割", "下市", "停止買賣", "交易所處置",
    "金管會", "證交所警示",
    # 員工/供應商警訊
    "員工欠薪", "供應商停供", "客戶出走",
    "裁員潮", "大規模離職",
    # KY/境外特別風險
    "KY股疑雲", "境外公司不透明",
]

NEWS_WARN_KW = [
    # 高管異動（媒體用語）
    "董事長辭", "總經理辭", "執行長辭", "財務長辭",
    "高層震盪", "人事大換血", "管理層異動",
    "創辦人出走", "元老離職",
    # 股東動向
    "大股東減持", "大股東出脫", "外資大賣",
    "外資連續賣超", "投信出清",
    "融資斷頭", "融資強制回補",
    # 市場訊號
    "股價重挫", "單日暴跌", "跌破支撐",
    "三大法人齊賣", "主力出貨",
    # 財務警示（媒體角度）
    "獲利大減", "虧損擴大", "毛利率崩跌",
    "現金流轉負", "應收帳款暴增",
    # 治理警示
    "更換會計師", "審計師異動", "內控問題",
    "董監持股質押", "質押比偏高",
    # 業務警示
    "失去大客戶", "主力客戶轉單", "訂單驟減",
    "產能利用率暴跌",
]


@st.cache_data(ttl=3600)
def get_all_mops_announcements():
    """
    一次抓取全市場「重大訊息」清單（TWSE OpenAPI t187ap04_L）。
    回傳：{ 'ok': bool, 'data': list, 'error': str, 'fetched_at': str }
    """
    result = {"ok": False, "data": [], "error": "", "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M")}
    try:
        res = requests.get(
            "https://openapi.twse.com.tw/v1/opendata/t187ap04_L",
            timeout=15, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        )
        body  = res.text or ""
        ctype = res.headers.get("Content-Type", "")
        is_json = "application/json" in ctype or body.strip().startswith("[")
        if res.status_code == 200 and is_json:
            data = res.json()
            if isinstance(data, list) and len(data) > 0:
                result["ok"] = True
                result["data"] = data
            else:
                result["error"] = "API 回傳空清單"
        else:
            result["error"] = "非JSON回應或連線失敗（HTTP{}）".format(res.status_code)
    except Exception as e:
        result["error"] = "連線例外：{}".format(str(e)[:80])
    return result


@st.cache_data(ttl=3600)
def get_director_holdings():
    """t187ap03_L：董監事持股申報（最新快照），用於偵測董監事大量申報轉讓或持股比例異常"""
    try:
        res = requests.get(
            "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
            timeout=15, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        )
        body  = res.text or ""
        ctype = res.headers.get("Content-Type", "")
        is_json = "application/json" in ctype or body.strip().startswith("[")
        if res.status_code == 200 and is_json:
            data = res.json()
            if isinstance(data, list) and len(data) > 0:
                lookup = {}
                for d in data:
                    code = str(d.get("公司代號", "")).strip()
                    if code:
                        lookup.setdefault(code, []).append(d)
                return {"ok": True, "data": lookup}
        return {"ok": False, "data": {}, "error": "連線失敗或空資料"}
    except Exception as e:
        return {"ok": False, "data": {}, "error": str(e)[:60]}


@st.cache_data(ttl=3600)
def get_major_shareholder_holdings():
    """t187ap08_L：持股 5%+ 大股東申報（最新快照），用於偵測大股東大量轉讓"""
    try:
        res = requests.get(
            "https://openapi.twse.com.tw/v1/opendata/t187ap08_L",
            timeout=15, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        )
        body  = res.text or ""
        ctype = res.headers.get("Content-Type", "")
        is_json = "application/json" in ctype or body.strip().startswith("[")
        if res.status_code == 200 and is_json:
            data = res.json()
            if isinstance(data, list) and len(data) > 0:
                lookup = {}
                for d in data:
                    code = str(d.get("公司代號", "")).strip()
                    if code:
                        lookup.setdefault(code, []).append(d)
                return {"ok": True, "data": lookup}
        return {"ok": False, "data": {}, "error": "連線失敗或空資料"}
    except Exception as e:
        return {"ok": False, "data": {}, "error": str(e)[:60]}

@st.cache_data(ttl=1800)
@st.cache_data(ttl=1800)
def search_news_risk(code, name):
    """
    用 yfinance Ticker.news 取得個股相關新聞，偵測市場傳聞/治理危機/檢調動態等。
    資料源：Yahoo Finance 新聞（透過 yfinance，Streamlit Cloud 已確認能通）。
    Google News RSS 在 Streamlit Cloud 被封鎖，改用此方案。
    回傳 dict：{ status, danger_kw, warn_kw, headlines, error }
    """
    import re as _re
    import yfinance as yf
    result = {
        "status": "no_data", "danger_kw": [], "warn_kw": [],
        "headlines": [], "error": ""
    }
    try:
        # 嘗試 .TW（上市）先，失敗再試 .TWO（上櫃）
        news_items = []
        for suffix in [".TW", ".TWO"]:
            try:
                ticker = yf.Ticker(code + suffix)
                news = ticker.news
                if news:
                    news_items = news
                    break
            except Exception:
                continue

        if not news_items:
            result["status"] = "clean"
            return result

        headlines = []
        all_titles_text = ""
        for item in news_items[:15]:
            title   = item.get("title", "") or ""
            pub_ts  = item.get("providerPublishTime", 0)
            source  = item.get("publisher", "")
            link    = item.get("link", "")
            # 時間戳轉日期
            try:
                from datetime import datetime as _dt
                pub = _dt.fromtimestamp(pub_ts).strftime("%Y-%m-%d") if pub_ts else ""
            except Exception:
                pub = ""
            headlines.append({"title": title, "date": pub, "source": source, "link": link})
            all_titles_text += " " + title

        danger = [kw for kw in NEWS_DANGER_KW if _re.search(kw, all_titles_text)]
        warn   = [kw for kw in NEWS_WARN_KW   if _re.search(kw, all_titles_text)]

        result["headlines"]  = headlines
        result["danger_kw"]  = danger
        result["warn_kw"]    = warn

        if danger:
            result["status"] = "danger"
        elif warn:
            result["status"] = "warning"
        else:
            result["status"] = "clean"

    except Exception as e:
        result["status"] = "error"
        result["error"]  = "yfinance 新聞查詢失敗：{}".format(str(e)[:80])

    return result

    return result


def query_mops_risk_detail(code):
    """
    查詢單一個股的多層風險偵測完整結果：
    ① MOPS 重大訊息（t187ap04_L）
    ② 董監事持股申報（t187ap03_L）—偵測大量申報轉讓
    ③ 大股東5%+持股（t187ap08_L）—偵測大股東換手
    """
    import re as _re
    result = {
        "status": "no_data",
        "danger_kw": [], "warn_kw": [],
        "matched_records": [],
        "director_flags": [],
        "shareholder_flags": [],
        "query_url": "https://mops.twse.com.tw/mops/web/t05st01?co_id={}".format(code),
        "error": "", "data_source_ok": False
    }
    any_source_ok = False
    code_str = str(code).strip()

    # ── ① MOPS 重大訊息 ──
    all_data = get_all_mops_announcements()
    if all_data["ok"]:
        any_source_ok = True
        matched = [d for d in all_data["data"]
                   if str(d.get("公司代號", "")).strip() == code_str]
        result["matched_records"] = matched
        if matched:
            full_text = " ".join(str(d.get("主旨", "")) for d in matched)
            danger = [kw for kw in MOPS_DANGER_KW if _re.search(kw, full_text)]
            warn   = [kw for kw in MOPS_WARN_KW   if _re.search(kw, full_text)]
            result["danger_kw"] = danger
            result["warn_kw"]   = warn
    else:
        result["error"] += "重大訊息：{}；".format(all_data["error"])

    # ── ② 董監事持股申報 ──
    dir_data = get_director_holdings()
    if dir_data["ok"]:
        any_source_ok = True
        flags = []
        for rec in dir_data["data"].get(code_str, []):
            transfer = str(rec.get("申報轉讓股數", "0") or "0").replace(",", "")
            name = rec.get("職稱", "") or rec.get("姓名", "") or ""
            try:
                n = int(transfer)
                if n > 100000:
                    flags.append("{}申報轉讓{}張".format(name, n // 1000))
            except Exception:
                pass
        if flags:
            result["director_flags"] = flags
            if "董監事申報轉讓" not in result["warn_kw"]:
                result["warn_kw"].append("董監事申報轉讓")

    # ── ③ 大股東5%+持股 ──
    sh_data = get_major_shareholder_holdings()
    if sh_data["ok"]:
        any_source_ok = True
        flags = []
        for rec in sh_data["data"].get(code_str, []):
            change = str(rec.get("本次申報增減股數", "0") or "0").replace(",","").replace("+","")
            name = rec.get("持股人姓名", "") or rec.get("持股人名稱", "") or ""
            try:
                n = int(change)
                if n < -500000:
                    flags.append("大股東{}減持{}張".format(name, abs(n) // 1000))
            except Exception:
                pass
        if flags:
            result["shareholder_flags"] = flags
            if "大股東大量減持" not in result["warn_kw"]:
                result["warn_kw"].append("大股東大量減持")

    result["data_source_ok"] = any_source_ok

    # 綜合判斷
    if result["danger_kw"]:
        result["status"] = "danger"
    elif result["warn_kw"] or result["director_flags"] or result["shareholder_flags"]:
        result["status"] = "warning"
    elif any_source_ok:
        result["status"] = "clean"
    else:
        result["status"] = "error"
        result["error"] = result["error"] or "所有資料源均查詢失敗"

    return result


@st.cache_data(ttl=86400)
def get_industry_lookup():
    """
    取得台股代碼→產業別 lookup dict。
    優先嘗試 TWSE/TPEX API；境外IP失敗時回傳內建常用對照表。
    產業別會在 get_fin_data_yfinance 裡被 yfinance 的 sector/industry 補充。
    """
    lookup = {}

    # 嘗試 TWSE companyInfo
    try:
        res = requests.get("https://openapi.twse.com.tw/v1/company/companyInfo",
                          timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if res.status_code == 200:
            for d in res.json():
                code = d.get("公司代號", "").strip()
                industry = d.get("產業別", "").strip()
                if code and industry:
                    lookup[code] = industry
    except Exception:
        pass

    # 嘗試 TPEX
    try:
        res = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes",
                          timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if res.status_code == 200:
            for d in res.json():
                code = d.get("SecuritiesCompanyCode", "").strip()
                industry = (d.get("Industry","") or d.get("IndustryName","")).strip()
                if code and industry and code not in lookup:
                    lookup[code] = industry
    except Exception:
        pass

    # 若 API 全失敗，使用內建對照表（主要大型股）
    if not lookup:
        lookup = {
            "2330":"半導體","2317":"電子零組件","2454":"半導體","2308":"電子零組件",
            "2382":"電腦與週邊","2395":"電腦與週邊","3008":"光電與通信","2357":"電腦與週邊",
            "2412":"光電與通信","2882":"金融保險","2881":"金融保險","2886":"金融保險",
            "2884":"金融保險","2885":"金融保險","2891":"金融保險","2892":"金融保險",
            "2880":"金融保險","2887":"金融保險","2888":"金融保險","5880":"金融保險",
            "1301":"塑膠","1303":"塑膠","1326":"塑膠","6505":"能源","2002":"鋼鐵",
            "1216":"食品","2207":"汽車","1101":"水泥","1102":"水泥",
            "2303":"半導體","2311":"電子零組件","2344":"半導體","2379":"半導體",
            "2409":"光電與通信","3034":"半導體","3037":"電子零組件","4938":"電子零組件",
            "2603":"航運","2609":"航運","2615":"航運","2618":"航運",
            "0050":"被動ETF","0056":"被動ETF","00878":"被動ETF","00919":"被動ETF",
            "00929":"被動ETF","006208":"被動ETF","6669":"電腦與週邊",
            "5871":"金融保險","3661":"半導體","5269":"半導體",
        }
    return lookup


@st.cache_data(ttl=3600)
def get_all_tw_stocks():
    """
    取得台股全市場股票清單。
    方法1：TWSE openapi（上市）/ TPEX openapi（上櫃）—正常情況取得約 1368 + 1012 = 2380 檔
    方法2：TWSE/TPEX 失敗時，fallback 到內建靜態清單（約 745 上市 + 24 上櫃）
    """
    import yfinance as yf
    industry_lookup = get_industry_lookup()

    listed_stocks = []
    otc_stocks    = []

    # ── 上市：TWSE openapi ──
    try:
        res = requests.get(
            "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
            timeout=10, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        body  = res.text or ""
        ctype = res.headers.get("Content-Type", "")
        is_json = "application/json" in ctype or body.strip().startswith("[")
        if res.status_code == 200 and is_json:
            for d in res.json():
                code = d.get("Code", "").strip()
                name = d.get("Name", "").strip()
                if not code: continue
                t = classify_code(code)
                industry = industry_lookup.get(code, "")
                group = get_industry_group(industry, t)
                listed_stocks.append({"code": code, "name": name, "market": "上市",
                                      "type": t, "industry": industry, "group": group})
    except Exception:
        pass

    # ── 上市方法2：TWSE 失敗時，直接用內建靜態清單（745個主要個股）──
    # 移除了原本的 yfinance 批次掃描方案，原因：
    # 1. 批次掃描耗時數分鐘，在 Streamlit Cloud 上不穩定
    # 2. 每批超時失敗導致只掃到部分代碼，反而比內建清單少
    # 3. 掃到的代碼名稱只有代碼本身，沒有中文名稱
    # 內建清單745個 + TPEX的1010個上櫃 = 共約1755檔，已覆蓋主要標的
    if not listed_stocks:
        builtin = _get_builtin_stock_list()
        for code, name, market in builtin:
            if market == "上市":
                t = classify_code(code)
                industry = industry_lookup.get(code, "")
                group = get_industry_group(industry, t)
                listed_stocks.append({"code": code, "name": name, "market": "上市",
                                      "type": t, "industry": industry, "group": group})

    # ── 上櫃：TPEX openapi ──
    try:
        res = requests.get(
            "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes",
            timeout=10, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        body  = res.text or ""
        ctype = res.headers.get("Content-Type", "")
        is_json = "application/json" in ctype or body.strip().startswith("[")
        if res.status_code == 200 and is_json:
            for d in res.json():
                code = d.get("SecuritiesCompanyCode", "").strip()
                name = d.get("CompanyName", "").strip()
                if not code: continue
                t = classify_code(code)
                industry = (d.get("Industry","") or d.get("IndustryName","") or
                            industry_lookup.get(code,"")).strip()
                group = get_industry_group(industry, t)
                otc_stocks.append({"code": code, "name": name, "market": "上櫃",
                                   "type": t, "industry": industry, "group": group})
    except Exception:
        pass

    # ── 上櫃 fallback ──
    if not otc_stocks:
        builtin = _get_builtin_stock_list()
        for code, name, market in builtin:
            if market == "上櫃":
                t = classify_code(code)
                industry = industry_lookup.get(code, "")
                group = get_industry_group(industry, t)
                otc_stocks.append({"code": code, "name": name, "market": "上櫃",
                                   "type": t, "industry": industry, "group": group})

    # 合併去重
    stocks = listed_stocks + otc_stocks
    seen = set()
    unique = []
    for s in stocks:
        if s['code'] not in seen:
            seen.add(s['code'])
            unique.append(s)
    return unique

def _get_builtin_stock_list():
    """
    內建台股代碼靜態清單（上市903個＋上櫃主要個股）。
    TWSE API 在 Streamlit Cloud 無法連線時的 fallback。
    涵蓋台股各產業主要個股。
    """
    LISTED = {
        # 水泥
        "1101":"台泥","1102":"亞泥","1103":"嘉泥","1104":"環泥","1108":"幸福","1109":"信大","1110":"東泥",
        # 食品
        "1201":"味全","1203":"味王","1210":"大成","1213":"大飲","1215":"卜蜂","1216":"統一",
        "1217":"愛之味","1218":"泰山","1219":"福壽","1220":"台榮","1225":"福懋油","1227":"佳格",
        "1229":"聯華","1231":"聯華食","1232":"大統益","1233":"天仁","1234":"黑松","1236":"宏亞",
        "1702":"南僑","1707":"葡萄王","1710":"東洋","1711":"永光","1712":"興農","1714":"和桐",
        "1717":"長興","1718":"中纖","1722":"台肥","1723":"中碳","1724":"台硝","1730":"花仙子",
        "1731":"美吾華","1732":"毛寶","1733":"五鼎","1734":"杏輝","1736":"喬山","1737":"臺鹽",
        "1738":"茂順","1740":"九豪","1742":"台達化學","1745":"名佳利","1750":"台灣化纖",
        # 紡織
        "1301":"台塑","1303":"南亞","1304":"台聚","1305":"華夏","1308":"亞聚","1309":"台達化",
        "1310":"台苯","1312":"國喬","1313":"聯成","1314":"中石化","1316":"上曜","1319":"東陽",
        "1321":"大洋","1323":"永裕","1325":"恆大","1326":"台化",
        "1402":"遠東新","1403":"遠紡","1404":"福懋","1408":"中興紡","1409":"新纖","1410":"南染",
        "1413":"宏洲","1414":"東和","1416":"廣豐","1417":"嘉裕","1419":"新紡","1423":"利華",
        "1425":"江申","1429":"永豐餘","1430":"彰源","1432":"大魯閣","1434":"福懋興業",
        "1437":"勤益控","1438":"裕豐","1440":"南紡","1441":"大東","1444":"力麗","1445":"大宇",
        "1446":"宏和","1447":"力鵬","1449":"佳和","1451":"年興","1452":"宏益","1456":"怡華",
        "1457":"宜進","1459":"聯發","1460":"宏遠","1463":"強盛","1464":"得力","1466":"聚紡",
        "1467":"南緯實業","1468":"昶和","1470":"大統紡","1471":"首利","1472":"三洋紡","1473":"台南",
        # 機械/電機
        "1504":"東元","1506":"正道","1507":"永大","1512":"光隆","1513":"中興電",
        "1515":"力山","1517":"利奇","1519":"華城","1521":"大億","1522":"堤維西",
        "1523":"富田","1524":"耿鼎","1525":"江興鍛","1526":"日馳","1527":"鑽全",
        "1528":"恩德","1530":"亞崴","1531":"高林股","1532":"勤美","1533":"車王電",
        "1535":"中宇","1536":"和大","1537":"廣隆","1539":"巨庭","1540":"喬福",
        # 鋼鐵
        "1604":"聲寶","1605":"華新","1608":"華榮","1609":"大亞","1611":"中電","1612":"宏泰",
        "2002":"中鋼","2006":"東和鋼鐵","2007":"燁興","2008":"高興昌","2009":"第一銅",
        "2010":"春源鋼鐵","2012":"春雨","2013":"中鋼構","2014":"中鴻","2015":"豐興",
        "2017":"官田鋼","2020":"美亞","2022":"聚亨","2023":"燁輝","2024":"志聯",
        "2025":"千興","2027":"大成鋼","2029":"盛餘",
        # 汽車/橡膠
        "2101":"南港","2102":"泰豐","2103":"台橡","2104":"中橡","2105":"正新",
        "2106":"建大","2107":"厚生","2108":"南帝","2201":"裕隆","2204":"中華",
        "2206":"三陽工業","2207":"和泰車","2208":"台船","2227":"裕日車","2231":"泰銘","2233":"宇隆",
        # 電子（核心大型股）
        "2301":"光寶科","2303":"聯電","2308":"台達電","2311":"日月光投控","2312":"金寶",
        "2313":"華通","2317":"鴻海","2323":"中環","2324":"仁寶","2325":"矽品",
        "2327":"國巨","2330":"台積電","2331":"精英","2332":"友訊","2337":"旺宏",
        "2340":"台亞","2341":"英業達","2344":"華邦電","2345":"智邦","2347":"聯強",
        "2352":"佳世達","2353":"宏碁","2354":"鴻準","2356":"英業達","2357":"華碩",
        "2360":"致茂","2363":"矽統","2365":"昆盈","2368":"金像電","2369":"菱生",
        "2371":"大同","2374":"佳能","2376":"技嘉","2377":"微星","2379":"瑞昱",
        "2382":"廣達","2383":"台光電","2385":"群光","2387":"精元","2388":"威盛",
        "2392":"正崴","2393":"億光","2395":"研華","2399":"映泰","2401":"凌陽",
        "2402":"毅嘉","2404":"漢唐","2406":"國碩","2408":"南亞科","2409":"友達",
        "2412":"中華電","2413":"環科","2414":"精技","2421":"建準","2424":"隴華",
        "2426":"鑫創","2428":"興勤","2429":"銘異","2430":"燦坤","2434":"統懋",
        "2436":"偉詮電","2438":"翔耀","2439":"美律","2441":"超豐","2444":"兆赫",
        "2447":"飛宏","2448":"晶電","2449":"京元電子","2451":"創見","2452":"彩晶",
        "2454":"聯發科","2455":"全新","2456":"奇力新","2458":"義隆","2461":"光群雷",
        "2464":"盟立","2471":"資通","2472":"立隆電","2474":"可成","2476":"鉅祥",
        "2480":"敦陽科","2481":"強茂","2482":"連宇","2483":"百容","2484":"希華",
        "2486":"一詮","2488":"漢平","2489":"瑞軒","2492":"華新科","2496":"卓越",
        "2498":"宏達電","2501":"國建","2504":"國產建材","2505":"國揚","2511":"太子",
        "2515":"中工","2524":"京城建設","2527":"宏璟","2534":"宏盛","2535":"達欣工",
        "2536":"宏普","2538":"基泰",
        # 航運
        "2601":"益航","2603":"長榮","2605":"新興","2606":"裕民","2607":"榮運",
        "2608":"嘉里大榮","2609":"陽明","2610":"華航","2611":"志信","2615":"萬海",
        "2617":"台航","2618":"長榮航","2626":"台灣國際造船","2628":"台灣高鐵",
        "2634":"漢翔","2637":"慧洋-KY",
        # 金融
        "2801":"彰銀","2809":"京城銀","2812":"台中銀","2823":"中壽","2824":"台壽保",
        "2832":"台產","2834":"臺企銀","2836":"高雄銀","2838":"聯邦銀","2845":"遠東銀",
        "2850":"新產","2851":"中再保","2852":"第一保","2855":"統一證","2867":"三商壽",
        "2880":"華南金","2881":"富邦金","2882":"國泰金","2883":"開發金","2884":"玉山金",
        "2885":"元大金","2886":"兆豐金","2887":"台新金","2888":"新光金","2889":"國票金",
        "2890":"永豐金","2891":"中信金","2892":"第一金","2897":"王道銀行",
        "2901":"欣欣","2903":"遠百","2912":"統一超","2913":"農林",
        # 其他電子3000-3999
        "3003":"健和興","3005":"神基","3006":"晶豪科","3008":"大立光","3009":"奇美材",
        "3010":"華立","3017":"奇鋐","3022":"威達電","3023":"信邦","3026":"禾伸堂",
        "3030":"德律","3033":"文曄","3034":"聯詠","3035":"智原","3036":"文曄",
        "3037":"欣興","3041":"揚智","3042":"晶技","3044":"健鼎","3045":"台灣大",
        "3046":"建碁","3048":"益登","3051":"力特","3054":"立積","3057":"喬鼎",
        "3059":"華晶科","3060":"銘異","3064":"泰偉","3066":"光聖","3068":"大揚",
        "3073":"創意","3078":"僑威","3081":"聯亞","3094":"聯傑","3101":"泓博",
        "3105":"穩懋","3110":"東哥遊艇","3114":"恒耀","3121":"鉅詮","3130":"一零四",
        "3131":"弘塑","3149":"正達","3161":"新漢","3182":"倍力","3189":"景碩",
        "3218":"大學光","3220":"龍德造船","3224":"三竹","3227":"原相","3231":"緯創",
        "3234":"光環","3237":"緯謙科技","3241":"憶碟","3260":"威剛","3264":"欣銓",
        "3269":"元太","3272":"聯陽","3281":"錦明","3293":"鈊象","3299":"群電",
        "3305":"昱泉","3308":"聯德控股","3311":"閎暉","3323":"加百裕","3324":"雙鴻",
        "3326":"東台精機","3337":"台表科","3356":"奇偶","3374":"精材","3376":"新日興",
        "3380":"明泰","3406":"玉晶光","3413":"京鼎","3443":"創意","3481":"群創",
        "3494":"誠研","3498":"陽程","3505":"南茂","3515":"華擎","3519":"綠能",
        "3526":"凡甲","3529":"力旺","3530":"晶相光","3532":"台勝科","3533":"嘉澤",
        "3534":"昇陽半導體","3545":"旭曜","3548":"長虹","3556":"禾瑞亞","3558":"神準",
        "3563":"牧德","3576":"新日興","3577":"榮創","3583":"辛耘","3587":"閎康",
        "3588":"通嘉","3592":"瑞鼎","3596":"研揚","3607":"谷崧","3611":"聖暉企業",
        "3615":"安可","3622":"洋華","3624":"光穎","3630":"新鉅科","3636":"泰林",
        "3643":"MPI","3645":"達航科技","3646":"艾迪科","3653":"健策","3661":"世芯-KY",
        "3665":"貿聯-KY","3673":"TPK宸鴻","3675":"德微","3680":"凱巧","3682":"艾華",
        "3686":"達邁","3691":"碩禾","3698":"隆達","3701":"大眾電腦","3702":"大聯大",
        "3704":"合勤控","3706":"神達","3707":"漢微科","3709":"鑫禾","3711":"日月光投控",
        "3714":"富采","3715":"定穎投控","3718":"奇偶","3726":"漢磊","3731":"明泰科技",
        "3741":"晶達光電","3745":"藤倉科技","3749":"精聯電子","3751":"優群科技",
        "3760":"鈦鑽科技","3762":"達發科技","3771":"崑鼎","3773":"德隆材料",
        # 生技醫療
        "4105":"台灣神隆","4107":"邦特","4108":"懷特","4114":"健喬","4119":"旭富",
        "4121":"優盛","4122":"可寧衛","4123":"晟德","4124":"中天","4126":"太醫",
        "4127":"天良","4128":"中天生技","4129":"聯合","4130":"健亞","4131":"東洋",
        "4132":"大學光學","4141":"龍燈-KY","4142":"國光生技","4144":"喬山健康科技",
        "4152":"台微體","4154":"鐿鈦","4157":"太景","4162":"智擎","4164":"臺康生技",
        "4168":"醣聯生技","4174":"浩鼎","4175":"聯生藥","4180":"虹映","4183":"佑全",
        "4197":"益安",
        # 5000-5999
        "5009":"台鋁","5017":"台塑化","5269":"祥碩","5274":"信驊","5347":"世界先進",
        "5371":"中光電","5374":"精誠","5388":"中磊電子","5522":"遠雄","5871":"中租-KY",
        "5876":"上海商銀","5880":"合庫金",
        # 6000-6999
        "6005":"群益證","6101":"弘榮能源","6104":"創惟科技","6108":"競國科技",
        "6121":"新普科技","6125":"廣運機械","6126":"信音","6132":"瑞儀","6138":"茂順",
        "6139":"亞翔工程","6141":"億豐窗簾","6146":"耕興","6153":"嘉聯益","6155":"堡達",
        "6163":"華電網","6165":"浩鑫股份","6166":"瑞祺電通","6167":"久元電子",
        "6168":"宏齊科技","6176":"瑞儀光電","6177":"達欣工程","6178":"亞太電信",
        "6182":"合晶科技","6183":"關貿網路","6185":"幃翔精密","6186":"威強電",
        "6189":"豐藝電子","6196":"帆宣系統","6197":"佳必琪","6201":"亞元科技",
        "6202":"盛群半導體","6203":"海韻電子","6205":"詮欣","6209":"今國光學",
        "6213":"聯茂電子","6214":"精誠資訊","6215":"和椿科技","6216":"居易科技",
        "6220":"岱宇","6221":"晶宏半導體","6223":"旺矽科技","6226":"光洋應材",
        "6230":"超衆科技","6231":"系統電子","6232":"崑鼎環境","6235":"華孚科技",
        "6236":"欣銓科技","6237":"驊訊電子","6238":"勤美","6239":"力成科技",
        "6241":"瀚荃","6244":"茂迪","6245":"立端科技","6269":"台郡科技",
        "6271":"同欣電子","6274":"台燿科技","6278":"台表科","6282":"康舒科技",
        "6285":"彩富電子","6291":"聖暉企業","6294":"智基科技","6296":"廣宇科技",
        "6298":"崑鼎","6302":"嘉聯益科技","6306":"關貿網路","6308":"天霖工業",
        "6309":"豐泰企業","6312":"東誠能源","6313":"華涵科技","6314":"明安",
        "6315":"慧洋海運","6318":"精德科技","6321":"日新電機","6323":"榮成紙業",
        "6337":"上銀科技","6409":"旭隼科技","6414":"樺漢科技","6415":"矽力-KY",
        "6416":"景碩科技","6429":"元晶太陽能","6438":"迅得機械","6439":"台康生技",
        "6441":"廣明光電","6446":"藥華藥","6462":"神盾","6464":"台光電子",
        "6488":"環球晶","6505":"台塑化","6510":"精測電子","6533":"晶心科技",
        "6592":"和潤企業","6643":"M31","6669":"緯穎","6770":"力積電","6789":"采鈺",
        # 8000-8999
        "8008":"建興電","8021":"尖點","8033":"雷虎科技","8046":"南電","8048":"德勝",
        "8050":"廣積","8051":"菱生精密","8060":"泰偉電子","8066":"股王","8069":"元太科技",
        "8081":"致新","8085":"福懋科","8086":"宏捷科","8089":"康普","8090":"鉅邦",
        "8099":"華容","8101":"華泰電子","8103":"丞相","8104":"錸寶","8105":"凌巨",
        "8110":"萬達光電","8114":"宇瞻","8119":"明基醫","8121":"越峰","8127":"日友",
        "8131":"福是","8132":"普誠","8141":"晶磊","8143":"台揚","8145":"非常棒",
        "8146":"耀登","8148":"承啟科技","8150":"南茂科技","8163":"乾坤","8171":"富喬",
        "8175":"達邦","8179":"中美晶","8183":"精英電腦","8192":"翼騰","8193":"達麗",
        "8210":"勤誠","8213":"志超","8299":"群聯",
        # 9000-9999
        "9901":"欣天然","9902":"台火","9903":"中鼎工程","9904":"寶雅",
        "9905":"大華","9906":"欣雄","9907":"統一實","9908":"大台北瓦斯",
        "9910":"豐泰","9911":"櫻花","9912":"奇隆","9914":"美利達",
        "9917":"中保科","9919":"康和證","9921":"巨大","9922":"神基科技",
        "9924":"台揚","9925":"新保","9926":"新泰伸","9928":"中纖",
        "9930":"中聯資源","9933":"中鼎","9934":"成霖","9937":"全國電子",
        "9938":"百和工業","9939":"宏全","9940":"信義房屋","9941":"裕融企業",
        "9942":"茂順","9943":"好樂迪","9945":"潤泰全","9946":"三發地產",
        "9958":"世紀鋼","9960":"邁達特",
        # ETF
        "0050":"元大台灣50","0051":"元大中型100","0052":"富邦科技","0053":"元大電子",
        "0054":"元大台商50","0055":"元大MSCI金融","0056":"元大高股息",
        "0057":"富邦摩台","0058":"富邦發達","0059":"富邦金融","0061":"元大寶滬深",
        "006201":"元大MSCI台灣","006203":"元大MSCI金融","006204":"永豐臺灣加權","006208":"富邦台50",
        "00631L":"元大台灣50正2","00632R":"元大台灣50反1","00636":"國泰台灣加權",
        "00642U":"元大S&P石油","00643":"群益深証中小","00645":"富邦日本",
        "00646":"元大S&P500","00650L":"復華美國正2","00652":"富邦印度",
        "00657":"國泰日本正2","00658":"國泰美國債20年",
        "00660":"元大歐洲50","00662":"富邦NASDAQ",
        "00670L":"富邦NASDAQ正2","00672L":"元大那斯達克正2",
        "00675L":"富邦恒生正2","00677U":"富邦VIX","00678":"群益NBI生技",
        "00679B":"元大美債20年","00690":"兆豐藍籌30","00692":"富邦公司治理",
        "00701":"國泰台灣低波動30","00706L":"元大S&P石油正2","00707L":"元大S&P天然氣正2",
        "00708L":"元大S&P黃金正2","00713":"元大台灣高息低波","00715L":"元大20年美債正2",
        "00720B":"元大投資等級公司債","00721B":"元大AAA至A公司債",
        "00730":"富邦臺灣優質高息","00733":"富邦臺灣中小",
        "00735":"國泰新興市場","00736":"國泰臺韓科技",
        "00739":"宏利全球動態股息","00742":"新光S&P500","00757":"統一FANG+",
        "00850":"元大臺灣ESG永續","00878":"國泰永續高股息","00881":"國泰台灣5G+",
        "00882":"中信中國高股息","00884":"永豐ESG低碳高息","00885":"富邦印度",
        "00886":"永豐美國500大","00890":"中信關鍵半導體","00891":"中信美國500大",
        "00892":"富邦台灣半導體","00893":"國泰智能電動車","00895":"富邦未來車",
        "00905":"野村全球電動車","00907":"永豐優息存股","00910":"台新智慧零售",
        "00911":"兆豐台灣晶圓製造","00912":"中信台灣智慧50","00915":"凱基優選高股息30",
        "00916":"國泰台灣科技100","00919":"群益台灣精選高息","00920":"富邦台灣核心半導體",
        "00922":"國泰台灣ESG低碳50","00923":"群益台灣精選高息","00925":"富邦特選高股息30",
        "00927":"群益半導體收益","00929":"復華台灣科技優息","00930":"永豐ESG低碳高息",
        "00931":"野村優質高息","00932":"兆豐永續高息等權","00933":"國泰台灣半導體",
        "00934":"中信成長高股息","00935":"野村台灣新科技50","00936":"台新臺灣永續高息",
        "00937":"統一台灣動能高息","00939":"統一台灣科技金融","00940":"元大台灣價值高息",
    }

    OTC = [
        ("3661","世芯-KY","上櫃"),("6488","環球晶","上櫃"),("5269","祥碩","上櫃"),
        ("3529","力旺","上櫃"),("4966","譜瑞-KY","上櫃"),("6510","精測","上櫃"),
        ("6409","旭隼","上櫃"),("4958","臻鼎-KY","上櫃"),("6643","M31","上櫃"),
        ("6533","晶心科","上櫃"),("3665","貿聯-KY","上櫃"),("6269","台郡","上櫃"),
        ("6271","同欣電","上櫃"),("6789","采鈺","上櫃"),("3691","碩禾","上櫃"),
        ("6592","和潤企業","上櫃"),("4170","新齊","上櫃"),("4174","浩鼎","上櫃"),
        ("4175","聯生藥","上櫃"),("4121","優盛","上櫃"),("4126","太醫","上櫃"),
        ("4127","天良","上櫃"),("4128","中天","上櫃"),("6121","新普","上櫃"),
        ("1786","科妍","上市"),("2543","皇昌","上市"),
    ]

    listed = [(code, name, "上市") for code, name in LISTED.items()]
    # 過濾 OTC 中已在 LISTED 的代碼
    listed_codes = set(LISTED.keys())
    otc = [(code, name, market) for code, name, market in OTC if code not in listed_codes]
    return listed + otc


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
tab0, tab5, tab6, tab1, tab3, tab4, tab2, tab_mops, tab_brief = st.tabs([
    "📖 使用說明",
    "🔧 系統檢核",
    "📋 合格標的池",
    "🔍 每日警示掃描",
    "🔬 個股回測",
    "🏆 全市場勝率排行",
    "📊 批次回測",
    "🛡️ 個股風險查詢",
    "📰 每日市場簡報",
])

# ==============================
# PDF 匯出模組
# ==============================

def _pdf_header(c, title, subtitle, page_w, page_h, y_start):
    """PDF 共用頁首：深藍色橫幅 + 標題"""
    from reportlab.lib.colors import HexColor
    from reportlab.pdfbase import pdfmetrics
    NAVY = HexColor("#003781")
    LIGHT = HexColor("#f8f9fa")
    # 頁首色塊
    c.setFillColor(NAVY)
    c.rect(0, page_h - 56, page_w, 56, fill=1, stroke=0)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica-Bold", 15)
    c.drawString(32, page_h - 34, title)
    c.setFont("Helvetica", 9)
    c.drawString(32, page_h - 48, subtitle)
    # 右上時間戳
    c.setFont("Helvetica", 8)
    c.drawRightString(page_w - 24, page_h - 34, datetime.now().strftime("%Y-%m-%d"))
    return page_h - 72  # 返回可用起始 y

def _pdf_footer(c, page_w, page_no):
    """PDF 共用頁尾"""
    from reportlab.lib.colors import HexColor
    c.setStrokeColor(HexColor("#e0e0e0"))
    c.line(32, 36, page_w - 32, 36)
    c.setFillColor(HexColor("#888888"))
    c.setFont("Helvetica", 8)
    c.drawString(32, 24, "本報告由台股滾動10日跌幅系統自動生成，不構成投資建議。歷史績效不代表未來報酬。")
    c.drawRightString(page_w - 32, 24, "第 {} 頁".format(page_no))

def _pdf_section(c, title, y, page_w, color="#003781"):
    """PDF 區塊標題"""
    from reportlab.lib.colors import HexColor
    c.setFillColor(HexColor(color))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(32, y, title)
    c.setStrokeColor(HexColor(color))
    c.setLineWidth(1.5)
    c.line(32, y - 3, page_w - 32, y - 3)
    return y - 18

def _pdf_kv_row(c, key, val, y, page_w, alt=False):
    """PDF 鍵值對橫排"""
    from reportlab.lib.colors import HexColor
    if alt:
        c.setFillColor(HexColor("#f8f9fa"))
        c.rect(32, y - 4, page_w - 64, 18, fill=1, stroke=0)
    c.setFillColor(HexColor("#888888"))
    c.setFont("Helvetica", 9)
    c.drawString(40, y + 2, str(key))
    c.setFillColor(HexColor("#003781"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(180, y + 2, str(val))
    return y - 18

def _pdf_df_table(c, df, y, page_w, page_h, col_widths=None, font_size=8):
    """DataFrame → PDF 表格，自動換頁"""
    from reportlab.lib.colors import HexColor
    NAVY = HexColor("#003781")
    LIGHT = HexColor("#f8f9fa")
    ORANGE = HexColor("#F86200")

    cols = list(df.columns)
    n_cols = len(cols)
    usable_w = page_w - 64

    if col_widths is None:
        col_widths = [usable_w / n_cols] * n_cols
    else:
        # 等比例縮放到 usable_w
        total = sum(col_widths)
        col_widths = [w / total * usable_w for w in col_widths]

    row_h = font_size + 7
    header_h = row_h + 2

    def draw_header(yy):
        x = 32
        c.setFillColor(NAVY)
        c.rect(32, yy - header_h + 4, usable_w, header_h, fill=1, stroke=0)
        c.setFillColor(HexColor("#ffffff"))
        c.setFont("Helvetica-Bold", font_size - 1)
        for i, col in enumerate(cols):
            c.drawString(x + 3, yy - 4, str(col)[:20])
            x += col_widths[i]
        return yy - header_h

    y = draw_header(y)

    for ridx, (_, row) in enumerate(df.iterrows()):
        if y < 70:  # 換頁
            _pdf_footer(c, page_w, "")
            c.showPage()
            y = page_h - 80
            y = draw_header(y)

        # 交替底色
        if ridx % 2 == 0:
            c.setFillColor(LIGHT)
            c.rect(32, y - row_h + 4, usable_w, row_h, fill=1, stroke=0)

        x = 32
        c.setFont("Helvetica", font_size)
        for i, col in enumerate(cols):
            val = str(row[col]) if row[col] is not None else "—"
            # 高勝率橘色
            try:
                if "%" in val and float(val.replace("%","").replace("⚠️","")) >= 80:
                    c.setFillColor(ORANGE)
                elif "%" in val and float(val.replace("%","").replace("⚠️","")) < 0:
                    c.setFillColor(HexColor("#0F6E56"))
                else:
                    c.setFillColor(HexColor("#333333"))
            except Exception:
                c.setFillColor(HexColor("#333333"))
            c.drawString(x + 3, y - 4, val[:18])
            x += col_widths[i]
        y -= row_h

    return y - 6


def generate_html_report_scan(df_scan, threshold, scan_date, market_level=None):
    """
    生成每日警示掃描的獨立 HTML 報告（可在瀏覽器完整列印/存PDF）
    使用者下載後在瀏覽器開啟，Ctrl+P 即可完整輸出

    排序邏輯（三方辯證後裁決）：
      - ✅有效：組內按體質分數高→低（已過篩選，比的是體質）
      - 🔶觀察：組內按跌幅深→淺（離進場甜蜜點的距離）
      - ⚪弱／其他：組內按體質分數低→高（優先看最危險的）
    信號組之間的順序固定：✅有效 → 🔶觀察 → ⚪弱
    """
    if df_scan is None or df_scan.empty:
        rows_html = "<tr><td colspan='99' style='text-align:center;color:#888;padding:20px'>無觸發標的</td></tr>"
        headers = ""
    else:
        df_sorted = df_scan.copy()

        # 解析體質分數欄（可能是 "10/15*"、"ETF"、"資料不足" 等格式）
        def _parse_score(v):
            try:
                s = str(v).replace("*", "").strip()
                if "/" in s:
                    return float(s.split("/")[0])
                return -1  # ETF/資料不足 等非數字，排在最後
            except Exception:
                return -1

        def _parse_pct(v):
            try:
                return float(str(v).replace("%", "").strip())
            except Exception:
                return 0.0

        signal_col = df_sorted.columns[0] if len(df_sorted.columns) > 0 else None
        score_col  = next((c for c in df_sorted.columns if "體質分數" in str(c)), None)
        pct_col    = next((c for c in df_sorted.columns if "報酬" in str(c)), None)

        if signal_col is not None:
            df_sorted["_score_num"] = df_sorted[score_col].apply(_parse_score) if score_col else -1
            df_sorted["_pct_num"]   = df_sorted[pct_col].apply(_parse_pct) if pct_col else 0.0

            # 信號分組優先序（加上強烈）
            def _signal_group(v):
                s = str(v)
                if "強烈" in s: return 0
                if "有效" in s: return 1
                if "觀察" in s: return 2
                if "弱" in s:   return 3
                return 4
            df_sorted["_grp"] = df_sorted[signal_col].apply(_signal_group)

            # 組內排序（全員辯證統一標準）：
            # 強烈/有效/觀察：體質高→低，同分時跌幅深→淺
            # 弱：跌幅深→淺（這組是警示，跌最深的放最上面）
            def _sort_key(row):
                grp = row["_grp"]
                if grp == 3:   # 弱組：跌幅深→淺
                    return (grp, row["_pct_num"], -row["_score_num"])
                else:           # 強烈/有效/觀察：體質高→低，同分時跌幅深→淺
                    return (grp, -row["_score_num"], row["_pct_num"])

            df_sorted["_sortkey_a"] = df_sorted.apply(lambda r: _sort_key(r)[0], axis=1)
            df_sorted["_sortkey_b"] = df_sorted.apply(lambda r: _sort_key(r)[1], axis=1)
            df_sorted["_sortkey_c"] = df_sorted.apply(lambda r: _sort_key(r)[2], axis=1)
            df_sorted = df_sorted.sort_values(["_sortkey_a", "_sortkey_b", "_sortkey_c"]).drop(
                columns=["_score_num", "_pct_num", "_grp",
                         "_sortkey_a", "_sortkey_b", "_sortkey_c"])

        rows_html = ""
        for _, row in df_sorted.iterrows():
            cells = "".join(
                "<td style='padding:8px 12px;border-bottom:1px solid #eee;white-space:nowrap'>{}</td>".format(
                    str(v) if v is not None else "—") for v in row.values)
            rows_html += "<tr>{}</tr>".format(cells)

        headers = "".join(
            "<th onclick='sortTable({idx})' style='background:#003781;color:#fff;padding:9px 12px;"
            "white-space:nowrap;text-align:center;cursor:pointer;user-select:none' "
            "title='點擊排序'>{name} <span style=\"font-size:10px;opacity:0.7\">⇕</span></th>".format(
                idx=i, name=c)
            for i, c in enumerate(df_sorted.columns))

    market_html = ""
    if market_level:
        color = "#A32D2D" if market_level >= 9 else ("#F86200" if market_level >= 8 else "#003781")
        market_html = '<p style="color:{};font-weight:600">台股市場熱度：第{}級</p>'.format(color, market_level)

    html = """<!DOCTYPE html>
<html lang="zh-TW"><head>
<meta charset="UTF-8">
<title>每日警示掃描 {date}</title>
<style>
  body {{ font-family: "PingFang TC","Microsoft JhengHei",sans-serif; font-size:14px; color:#333; margin:20px 40px; }}
  h1 {{ color:#003781; border-bottom:2px solid #003781; padding-bottom:8px; }}
  table {{ border-collapse:collapse; width:100%; margin-top:16px; }}
  th {{ font-size:12px; }}
  td {{ font-size:13px; }}
  tr:nth-child(even) td {{ background:#f9f9f9; }}
  @page {{ size:A4 landscape; margin:15mm; }}
  @media print {{
    body {{ margin:0; }}
    h1 {{ font-size:16px; }}
    table {{ font-size:11px; }}
    th,td {{ padding:5px 8px !important; }}
  }}
</style>
</head><body>
<h1>📊 每日警示掃描報告</h1>
<p>掃描日期：{date}　｜　警示門檻：{thr}%　｜　生成時間：{date}</p>
<p style="color:#888;font-size:12px">
  排序說明：✅有效組按體質分數高→低；🔶觀察組按跌幅深→淺；⚪弱組按體質分數低→高。點擊表頭可自訂排序。
</p>
{market}
<table id="scanTable">
  <thead><tr>{headers}</tr></thead>
  <tbody>{rows}</tbody>
</table>
<p style="color:#888;font-size:12px;margin-top:24px">
  本報告由台股滾動10日跌幅系統自動生成，不構成投資建議。歷史績效不代表未來報酬。
</p>
<script>
  // 點擊表頭排序（純前端，不影響原始樣式）
  var sortDirs = {{}};
  function sortTable(colIdx) {{
    var table = document.getElementById("scanTable");
    var tbody = table.tBodies[0];
    var rows = Array.from(tbody.rows);
    var dir = sortDirs[colIdx] = !sortDirs[colIdx];

    rows.sort(function(a, b) {{
      var av = a.cells[colIdx].innerText.trim();
      var bv = b.cells[colIdx].innerText.trim();
      var an = parseFloat(av.replace(/[^\\-0-9.]/g, ''));
      var bn = parseFloat(bv.replace(/[^\\-0-9.]/g, ''));
      var bothNum = !isNaN(an) && !isNaN(bn) && av.match(/[0-9]/) && bv.match(/[0-9]/);
      if (bothNum) {{
        return dir ? an - bn : bn - an;
      }}
      return dir ? av.localeCompare(bv, 'zh-TW') : bv.localeCompare(av, 'zh-TW');
    }});
    rows.forEach(function(r) {{ tbody.appendChild(r); }});
  }}

  // 開啟即自動詢問列印
  window.onload = function() {{
    setTimeout(function() {{
      var r = confirm("是否立即列印/存成PDF？\\n\\n建議：選「另存為PDF」，版面選「A4 橫向」，開啟「背景圖形」");
      if (r) window.print();
    }}, 500);
  }};
</script>
</body></html>""".format(
        date=scan_date, thr=threshold,
        market=market_html, headers=headers, rows=rows_html)
    return html.encode('utf-8')


def generate_html_report_pool(df_pool):
    """生成合格標的池獨立 HTML 報告"""
    if df_pool is None or df_pool.empty:
        return "<html><body>無資料</body></html>".encode('utf-8')

    show_cols = ['體質分數','體質等級','代碼','名稱','股價','產業別','ROE%','負債比%',
                 '▶A獲利(0-5)','▶B護城河(0-5)','▶C安全邊際(0-5)']
    show_cols = [c for c in show_cols if c in df_pool.columns]
    df_show = df_pool[show_cols].sort_values('體質分數', ascending=False) if '體質分數' in df_pool.columns else df_pool[show_cols]

    headers = "".join(
        "<th style='background:#003781;color:#fff;padding:8px 12px;white-space:nowrap'>{}</th>".format(c)
        for c in show_cols)
    rows_html = ""
    for _, row in df_show.iterrows():
        cells = "".join(
            "<td style='padding:7px 10px;border-bottom:1px solid #eee;text-align:center'>{}</td>".format(
                str(row.get(c,"—")) if row.get(c) is not None else "—") for c in show_cols)
        rows_html += "<tr>{}</tr>".format(cells)

    html = """<!DOCTYPE html>
<html lang="zh-TW"><head>
<meta charset="UTF-8">
<title>合格標的池報告</title>
<style>
  body {{ font-family:"PingFang TC","Microsoft JhengHei",sans-serif; font-size:14px; margin:20px 40px; }}
  h1 {{ color:#003781; border-bottom:2px solid #003781; padding-bottom:8px; }}
  table {{ border-collapse:collapse; width:100%; }}
  tr:nth-child(even) td {{ background:#f9f9f9; }}
  @page {{ size:A4 landscape; margin:15mm; }}
  @media print {{ th,td {{ font-size:11px; padding:5px 8px !important; }} }}
</style></head><body>
<h1>📋 合格標的池體質評分報告</h1>
<p>生成日期：{date}　｜　共 {n} 檔個股評分</p>
<table><thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table>
<p style="color:#888;font-size:12px;margin-top:20px">不構成投資建議。歷史績效不代表未來報酬。</p>
<script>window.onload=function(){{setTimeout(function(){{if(confirm("列印/存成PDF？"))window.print();}},500);}}</script>
</body></html>""".format(
        date=datetime.now().strftime("%Y-%m-%d"),
        n=len(df_show), headers=headers, rows=rows_html)
    return html.encode('utf-8')


# ── reportlab 版本保留（純數字，備用）──
def generate_pdf_backtest(code, prices, df_win, df_avg, df_dd, df_yearly, thr_val,
                           q_score=None, q_grade="", market_level=None):
    """生成個股回測的獨立 HTML 報告（可完整列印）"""
    rows_win = ""
    if df_win is not None:
        for _, row in df_win.iterrows():
            cells = "".join("<td style='padding:6px 10px;border-bottom:1px solid #eee;text-align:center'>{}</td>".format(str(v)) for v in row.values)
            rows_win += "<tr>{}</tr>".format(cells)
    headers_win = "".join("<th style='background:#003781;color:#fff;padding:8px 10px;font-size:12px'>{}</th>".format(c) for c in (df_win.columns if df_win is not None else []))

    rows_yr = ""
    if df_yearly is not None:
        for _, row in df_yearly.iterrows():
            cells = "".join("<td style='padding:5px 8px;border-bottom:1px solid #eee;text-align:center;font-size:12px'>{}</td>".format(str(v)) for v in row.values)
            rows_yr += "<tr>{}</tr>".format(cells)
    headers_yr = "".join("<th style='background:#003781;color:#fff;padding:7px 8px;font-size:11px'>{}</th>".format(c) for c in (df_yearly.columns if df_yearly is not None else []))

    score_html = ""
    if q_score is not None:
        sc = int(q_score)
        sc_color = "#0F6E56" if sc >= 13 else "#F86200" if sc >= 9 else "#A32D2D"
        score_html = '<p>體質評分：<strong style="color:{c};font-size:18px">{sc}/15</strong>　{grade}</p>'.format(
            c=sc_color, sc=sc, grade=q_grade)

    ml_html = ""
    if market_level:
        ml_color = "#A32D2D" if market_level >= 9 else "#F86200" if market_level >= 8 else "#003781"
        ml_html = '<p>市場熱度：<strong style="color:{c}">第{}級</strong></p>'.format(market_level, c=ml_color)

    dates = sorted(prices.keys()) if prices else []
    price_range = "{} ～ {}".format(dates[0], dates[-1]) if dates else "—"

    html = """<!DOCTYPE html>
<html lang="zh-TW"><head>
<meta charset="UTF-8">
<title>個股回測報告 {code}</title>
<style>
  body {{ font-family:"PingFang TC","Microsoft JhengHei",sans-serif; font-size:14px; margin:20px 40px; color:#333; }}
  h1 {{ color:#003781; border-bottom:3px solid #003781; padding-bottom:8px; }}
  h2 {{ color:#003781; margin-top:28px; border-left:4px solid #003781; padding-left:12px; }}
  table {{ border-collapse:collapse; width:100%; margin:12px 0; }}
  tr:nth-child(even) td {{ background:#f9f9f9; }}
  .warn {{ background:#FEF0CC; border-left:4px solid #F86200; padding:10px 16px; margin:12px 0; border-radius:0 6px 6px 0; }}
  @page {{ size:A4 portrait; margin:15mm 12mm; }}
  @media print {{
    h1 {{ font-size:18px; }}
    h2 {{ font-size:14px; }}
    table {{ font-size:11px; }}
    th,td {{ padding:4px 7px !important; }}
    .no-print {{ display:none; }}
  }}
</style></head><body>
<h1>📊 個股回測分析報告　{code}</h1>
<p>資料期間：{price_range}　｜　分析門檻：{thr}%　｜　生成：{date}</p>
{score}{ml}
<h2>表A：勝率（各門檻 × 觀察天數）</h2>
<table><thead><tr>{h_win}</tr></thead><tbody>{r_win}</tbody></table>
<h2>年度明細 A：每年平均單次報酬%（門檻 {thr}%）</h2>
<table><thead><tr>{h_yr}</tr></thead><tbody>{r_yr}</tbody></table>
<p style="color:#888;font-size:12px;margin-top:24px">本報告由台股滾動10日跌幅系統自動生成，不構成投資建議。歷史績效不代表未來報酬。</p>
<script>window.onload=function(){{setTimeout(function(){{if(confirm("列印/存成PDF？\\n建議選A4直向"))window.print();}},500);}}</script>
</body></html>""".format(
        code=code, price_range=price_range, thr=thr_val,
        date=datetime.now().strftime("%Y-%m-%d"),
        score=score_html, ml=ml_html,
        h_win=headers_win, r_win=rows_win,
        h_yr=headers_yr, r_yr=rows_yr)
    return html.encode('utf-8')


def generate_pdf_pool(df_pool):
    """合格標的池 PDF 報告"""
    import io
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.colors import HexColor

    buf = io.BytesIO()
    page_w, page_h = A4
    c = rl_canvas.Canvas(buf, pagesize=A4)
    page_no = [1]

    y = _pdf_header(c, "合格標的池報告",
                    "台股15分體質評分 · 生成日期 {}".format(datetime.now().strftime("%Y-%m-%d")),
                    page_w, page_h, page_h - 56)

    # 統計摘要
    y -= 8
    y = _pdf_section(c, "評分統計摘要", y, page_w)
    if df_pool is not None and not df_pool.empty:
        total = len(df_pool)
        grade_a = len(df_pool[df_pool.get('_grade_short', df_pool.get('等級','')) == 'A級']) if '_grade_short' in df_pool.columns else 0
        grade_b = len(df_pool[df_pool.get('_grade_short', df_pool.get('等級','')) == 'B級']) if '_grade_short' in df_pool.columns else 0
        y = _pdf_kv_row(c, "評分標的總數", "{}檔個股".format(total), y, page_w)
        y = _pdf_kv_row(c, "A級（核心）", "{}檔".format(grade_a), y, page_w, alt=True)
        y = _pdf_kv_row(c, "B級（可觀察）", "{}檔".format(grade_b), y, page_w)
        if '體質分數' in df_pool.columns:
            top15 = len(df_pool[pd.to_numeric(df_pool['體質分數'], errors='coerce') >= 15])
            top13 = len(df_pool[pd.to_numeric(df_pool['體質分數'], errors='coerce') >= 13])
            y = _pdf_kv_row(c, "15分滿分標的", "{}檔".format(top15), y, page_w, alt=True)
            y = _pdf_kv_row(c, "13分以上標的", "{}檔".format(top13), y, page_w)

    # A級清單
    y -= 14
    y = _pdf_section(c, "A級核心標的清單", y, page_w, color="#0F6E56")
    if df_pool is not None and not df_pool.empty and '_grade_short' in df_pool.columns:
        df_a = df_pool[df_pool['_grade_short'] == 'A級'].copy()
        if not df_a.empty:
            show_cols = ['代碼','名稱','體質分數','股價','ROE%','負債比%','▶A獲利(0-5)','▶B護城河(0-5)','▶C安全邊際(0-5)']
            show_cols = [col for col in show_cols if col in df_a.columns]
            widths_a = [36,60,36,40,40,40,50,50,50]
            y = _pdf_df_table(c, df_a[show_cols].reset_index(drop=True),
                              y, page_w, page_h,
                              col_widths=widths_a[:len(show_cols)], font_size=7.5)

    _pdf_footer(c, page_w, page_no[0])
    c.save()
    buf.seek(0)
    return buf.read()


def generate_pdf_scan(df_scan, threshold, scan_date):
    """每日警示掃描 PDF 報告"""
    import io
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.colors import HexColor

    buf = io.BytesIO()
    page_w, page_h = A4
    c = rl_canvas.Canvas(buf, pagesize=A4)

    y = _pdf_header(c,
        "每日警示掃描報告　{}".format(scan_date),
        "台股滾動10日跌幅系統 · 警示門檻 {}%".format(threshold),
        page_w, page_h, page_h - 56)

    y -= 8
    y = _pdf_section(c, "今日觸發標的（門檻 {}%）".format(threshold), y, page_w)

    if df_scan is not None and not df_scan.empty:
        show_cols = [col for col in ['代碼','名稱','產業群組','滾動10日報酬率','目前收盤','體質分數','體質等級'] if col in df_scan.columns]
        widths_s = [36, 60, 60, 65, 50, 40, 60]
        y = _pdf_df_table(c, df_scan[show_cols].head(50).reset_index(drop=True),
                          y, page_w, page_h,
                          col_widths=widths_s[:len(show_cols)], font_size=8)
        c.setFillColor(HexColor("#888"))
        c.setFont("Helvetica", 8)
        c.drawString(32, y - 10, "共 {} 檔觸發（最多顯示50筆）".format(len(df_scan)))
    else:
        c.setFillColor(HexColor("#888"))
        c.setFont("Helvetica", 10)
        c.drawString(32, y - 20, "今日無標的觸發警示門檻 {}%".format(threshold))

    _pdf_footer(c, page_w, 1)
    c.save()
    buf.seek(0)
    return buf.read()


def generate_pdf_briefing(premarket_data, events):
    """每日市場簡報 PDF"""
    import io
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.colors import HexColor

    buf = io.BytesIO()
    page_w, page_h = A4
    c = rl_canvas.Canvas(buf, pagesize=A4)

    today_str = datetime.now().strftime("%Y-%m-%d")
    y = _pdf_header(c, "每日市場簡報　{}".format(today_str),
                    "台股滾動10日跌幅系統 · 盤前快訊 + 事件日曆",
                    page_w, page_h, page_h - 56)

    # 盤前快訊
    y -= 8
    y = _pdf_section(c, "今日盤前快訊", y, page_w)
    if premarket_data:
        alt = False
        for key, d in premarket_data.items():
            if d.get("val") and d["val"] != "—":
                chg = "+{:.2f}%".format(d["chg_pct"]) if (d.get("chg_pct") or 0) > 0 else "{:.2f}%".format(d.get("chg_pct") or 0)
                y = _pdf_kv_row(c, d["name"], "{} ({})".format(d["val"], chg), y, page_w, alt=alt)
                alt = not alt

    # 事件日曆
    y -= 14
    y = _pdf_section(c, "近期重大事件日曆", y, page_w)
    if events:
        alt = False
        for ev in events[:20]:
            date_str = ev["date"].strftime("%m/%d") if hasattr(ev["date"], "strftime") else str(ev["date"])
            y = _pdf_kv_row(c, "[{}] {}".format(date_str, ev["category"]),
                            ev["title"], y, page_w, alt=alt)
            if y < 70:
                break
            alt = not alt

    _pdf_footer(c, page_w, 1)
    c.save()
    buf.seek(0)
    return buf.read()


# ==============================
# TAB 0: 使用說明
# ==============================
with tab0:
    st.markdown(_tab_icon("icon-news", "系統使用說明", "操作流程 · 顏色說明 · 計算邏輯"), unsafe_allow_html=True)
    st.caption("📄 PDF說明：請用下方「下載HTML報告」按鈕，下載後在瀏覽器直接開啟，再按 Ctrl+P 存成PDF（完整輸出，不受 iframe 限制）")

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
    st.markdown("### 🆕 v13 新功能（合格標的池篩選）")
    st.markdown("""
**1️⃣ 標的體質評分卡（15分制）**
- 三大維度各5分：A獲利能力、B商業模式護城河、C市值與安全邊際
- 六條件篩選區分「好公司短暫跌」vs「爛公司繼續跌」
- ⭐⭐⭐ 核心（13+）｜⭐⭐ 可觀察（9-12）｜⭐ 高風險（5-8）｜⚠️ 資料不足（0-4，yfinance 財報欄位缺失）

**2️⃣ 複合信號強度（每日警示掃描）**
- 4條件同時評估：連續觸發天數、體質分數、宏觀環境、跌幅深度
- ⚠️ 「Coatue」一詞僅在早期開發說明中提到其思維啟發，本系統的條件設計基於台股財務數據，非 Coatue 的實際選股框架
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
    st.markdown(_tab_icon("icon-search", "系統檢核", "市場背景快照 · 整體環境判斷"), unsafe_allow_html=True)
    st.caption("📄 PDF說明：請用下方「下載HTML報告」按鈕，下載後在瀏覽器直接開啟，再按 Ctrl+P 存成PDF（完整輸出，不受 iframe 限制）")

    st.info("點擊下方按鈕，自動驗證各項資料來源、API連線、計算邏輯與資料新鮮度")

    if st.button("▶️ 執行系統檢核", type="primary", key="check"):
        checks = []

        def run_check(name, fn):
            try:
                ok, detail = fn()
                # 偵測「偶發性網路問題」→ 用警告而非錯誤
                is_transient = any(kw in detail for kw in [
                    "偶發性", "稍後再試", "Expecting value", "Connection", "Timeout",
                    "JSONDecodeError", "ConnectionError", "ReadTimeout"
                ])
                if ok:
                    status = "✅ 正常"
                elif is_transient:
                    status = "⚠️ 暫時異常"   # 橘色警告，不算系統失敗
                else:
                    status = "❌ 異常"
                checks.append({"項目": name, "狀態": status, "說明": detail})
            except Exception as e:
                checks.append({"項目": name, "狀態": "❌ 失敗", "說明": str(e)[:120]})

        with st.spinner("執行中..."):

            def check_twse():
                url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
                last_err = ""
                for attempt in range(3):
                    try:
                        res = requests.get(url, timeout=15, headers={
                            "User-Agent": "Mozilla/5.0",
                            "Accept": "application/json",
                        })
                        body  = res.text or ""
                        ctype = res.headers.get("Content-Type", "")
                        if res.status_code == 200:
                            # 先確認是 JSON（Content-Type 或 body 起始字元）
                            is_json = "application/json" in ctype or body.strip().startswith("[")
                            if is_json:
                                try:
                                    data = res.json()
                                    if len(data) > 100:
                                        return True, "取得 {} 筆上市證券即時清單（第{}次成功）".format(len(data), attempt+1)
                                    last_err = "筆數不足 {}".format(len(data))
                                except Exception as je:
                                    last_err = "JSON解析失敗: {} | body: {}".format(str(je)[:30], repr(body[:60]))
                            else:
                                # 非 JSON：代理回傳 HTML/純文字錯誤頁
                                last_err = "非JSON回應(Content-Type:{}) | {}".format(
                                    ctype[:25], repr(body[:80]))
                        elif res.status_code == 403:
                            last_err = "403封鎖 | {}".format(repr(body[:60]))
                        else:
                            last_err = "HTTP{} | {}".format(res.status_code, repr(body[:60]))
                    except Exception as e:
                        last_err = "例外: {}".format(str(e)[:60])
                    if attempt < 2:
                        time.sleep(2)
                return False, "連線失敗（{}）→ 自動改用內建靜態清單".format(last_err)
            run_check("證交所TWSE API", check_twse)

            def check_tpex():
                last_err = ""
                for attempt in range(3):
                    try:
                        res = requests.get(
                            "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes",
                            timeout=15, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
                        body  = res.text or ""
                        ctype = res.headers.get("Content-Type", "")
                        if res.status_code == 200:
                            is_json = "application/json" in ctype or body.strip().startswith("[")
                            if is_json:
                                try:
                                    data = res.json()
                                    if len(data) > 50:
                                        return True, "取得 {} 筆上櫃證券（第{}次成功）".format(len(data), attempt+1)
                                    last_err = "筆數不足 {}".format(len(data))
                                except Exception as je:
                                    last_err = "JSON解析失敗: {}".format(str(je)[:40])
                            else:
                                last_err = "非JSON回應 | {}".format(repr(body[:60]))
                        else:
                            last_err = "HTTP{} | {}".format(res.status_code, repr(body[:60]))
                    except Exception as e:
                        last_err = str(e)[:60]
                    if attempt < 2:
                        time.sleep(2)
                return False, "連線失敗（{}）→ 自動改用內建靜態清單".format(last_err)
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
        # ── 各頁籤功能影響與交易決策說明 ──
        TWSE_FALLBACK_DETAIL = """
**備援靜態清單說明**（當 TWSE/TPEX API 無法連線時）

這份清單是程式碼內建的靜態股票代碼列表，約 2,000 檔主要個股。
- **不是** 昨日的即時資料；**不是** 從任何 API 即時抓取的
- 只包含代碼和名稱，**不含今日股價**（今日股價仍由 Yahoo Finance 即時提供）
- 可能遺漏：近期新上市個股、近期下市個股、近期更名個股

| 頁籤 | 狀態 | 交易決策建議 |
|------|------|------------|
| 🔍 每日警示掃描 | ✅ 可使用 | 股價訊號可信（Yahoo Finance 即時），但清單範圍略有缺漏 |
| 🏆 全市場勝率排行 | ✅ 可使用 | 同上 |
| 📋 合格標的池 | ✅ 可建立 | 可能遺漏近期新上市個股 |
| 🔬 個股回測 | ✅ 完全正常 | 直接輸入代碼，不受影響 |
| 📊 批次回測 | ✅ 完全正常 | 同上 |
"""

        IMPACT_MAP = {
            "證交所TWSE API":   ("warning", "股票清單使用內建靜態備援", TWSE_FALLBACK_DETAIL),
            "櫃買中心TPEX API": ("warning", "上櫃清單使用內建靜態備援", TWSE_FALLBACK_DETAIL),
            "Yahoo Finance API（2330）": ("error", "🚨 嚴重：所有頁籤股價資料失效", """
**Yahoo Finance 是本系統唯一的股價資料源，若此項異常：**

| 頁籤 | 狀態 | 交易決策建議 |
|------|------|------------|
| 🔍 每日警示掃描 | ❌ 不可使用 | 訊號完全不可信，勿下單 |
| 🏆 全市場勝率排行 | ❌ 不可使用 | 同上 |
| 📋 合格標的池 | ❌ 無法建立 | 同上 |
| 🔬 個股回測 | ❌ 不可使用 | 同上 |
| 📊 批次回測 | ❌ 不可使用 | 同上 |

**⛔ 今日所有訊號暫停參考，不建議下單。等 Yahoo Finance 恢復後重試。**
"""),
            "資料即時性（最新資料距今天數）": ("warning", "股價資料可能延遲", """
Yahoo Finance 台股資料通常於盤後（16:00 後）更新。
若距今超過 2 天，今日掃描訊號的觸發價格可能是舊資料。

**交易決策建議：資料延遲超過 2 天時，今日訊號暫停參考。**
"""),
            "滾動10日報酬計算邏輯": ("error", "🚨 程式計算錯誤", """
計算邏輯驗證失敗，所有回測數字（勝率、報酬率）不可信。

**⛔ 立即停止使用所有頁籤，截圖回報開發者修復後再使用。**
"""),
            "還原後股價（0050 15年）": ("warning", "歷史股價資料不完整", """
15年歷史資料不足，長期回測結果可能偏差。

| 頁籤 | 狀態 |
|------|------|
| 🔍 每日警示掃描 | ✅ 正常（只需近60天） |
| 🔬 個股回測（近3年） | ✅ 可參考 |
| 🔬 個股回測（15年） | ⚠️ 需謹慎，樣本可能不足 |
"""),
            "觸發計算驗證（2330 @-7%）": ("error", "🚨 觸發邏輯計算錯誤", """
觸發判斷計算結果不符預期，每日掃描和回測的觸發訊號不可信。

**⛔ 立即停止使用掃描和回測功能，截圖回報開發者。**
"""),
            "還原股價連續性驗證（0050除息）": ("warning", "除息還原可能失真", """
除息前後股價還原有異常跳空，含除息期間的長期回測勝率可能偏高。

**交易決策建議：優先參考近 2 年的回測數據，15年長期數據需謹慎解讀。**
"""),
        }

        failed_items = [c["項目"] for c in checks if "❌" in c["狀態"]]
        warn_items   = [c["項目"] for c in checks if "⚠️" in c["狀態"]]

        if not failed_items and not warn_items:
            st.success("✅ 所有系統檢核通過！各頁籤功能均正常，今日訊號可正常參考。")
        else:
            if failed_items:
                st.error("❌ 程式錯誤，以下功能**不可信**：{}".format("、".join(failed_items)))
            if warn_items:
                st.warning("⚠️ 以下項目降級運作（點開查看各頁籤影響）：{}".format("、".join(warn_items)))

        problem_items = failed_items + warn_items
        if problem_items:
            st.markdown("---")
            st.markdown("### 📋 各頁籤功能影響說明 ＆ 今日交易決策建議")
            for item in problem_items:
                if item in IMPACT_MAP:
                    level, short_desc, detail = IMPACT_MAP[item]
                    icon = "🔴" if level == "error" else "🟡"
                    with st.expander(
                        "{} {}：{}".format(icon, item, short_desc),
                        expanded=(level == "error")
                    ):
                        st.markdown(detail)


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

@st.cache_data(ttl=43200)
def get_fin_data_yfinance(code):
    """
    用 yfinance 取台股財務資料。
    不依賴 .info（yfinance 1.x 台股支援不穩定），
    改用 .financials / .balance_sheet / .history 直接取數字。
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(code + ".TW")

        # ── 現價（最可靠）──
        hist_now = ticker.history(period="5d")
        price = float(hist_now['Close'].iloc[-1]) if not hist_now.empty else None

        # ── 損益表：EPS、淨利 ──
        eps_history = {}
        net_income_history = {}
        try:
            fin = ticker.financials  # index=科目, columns=日期(降序)
            if fin is not None and not fin.empty:
                # EPS
                for eps_key in ['Basic EPS', 'Diluted EPS', 'EPS']:
                    if eps_key in fin.index:
                        for col in fin.columns:
                            yr = col.year if hasattr(col, 'year') else int(str(col)[:4])
                            v = fin.loc[eps_key, col]
                            if v is not None and not pd.isna(v):
                                eps_history[yr] = round(float(v), 2)
                        break
                # 淨利（算ROE用）
                for ni_key in ['Net Income', 'Net Income Common Stockholders']:
                    if ni_key in fin.index:
                        for col in fin.columns:
                            yr = col.year if hasattr(col, 'year') else int(str(col)[:4])
                            v = fin.loc[ni_key, col]
                            if v is not None and not pd.isna(v):
                                net_income_history[yr] = float(v)
                        break
        except Exception:
            pass

        # ── 資產負債表：股東權益、負債、資產、每股淨值 ──
        equity_map = {}
        total_debt_map = {}
        total_assets_map = {}
        bvps = None
        try:
            bs = ticker.balance_sheet  # index=科目, columns=日期
            if bs is not None and not bs.empty:
                for col in bs.columns:
                    yr = col.year if hasattr(col, 'year') else int(str(col)[:4])
                    # 股東權益
                    for eq_key in ['Stockholders Equity', 'Total Equity Gross Minority Interest',
                                   'Common Stock Equity']:
                        if eq_key in bs.index:
                            v = bs.loc[eq_key, col]
                            if v is not None and not pd.isna(v):
                                equity_map[yr] = float(v)
                            break
                    # 總負債
                    for debt_key in ['Total Liabilities Net Minority Interest', 'Total Debt']:
                        if debt_key in bs.index:
                            v = bs.loc[debt_key, col]
                            if v is not None and not pd.isna(v):
                                total_debt_map[yr] = float(v)
                            break
                    # 總資產
                    for asset_key in ['Total Assets']:
                        if asset_key in bs.index:
                            v = bs.loc[asset_key, col]
                            if v is not None and not pd.isna(v):
                                total_assets_map[yr] = float(v)
                            break

                # 每股淨值：最新年度股東權益 / 股數（用市值/股價推算股數）
                if equity_map and price:
                    latest_yr = max(equity_map.keys())
                    eq = equity_map[latest_yr]
                    # 嘗試用 info 取股數
                    try:
                        shares = ticker.info.get('sharesOutstanding')
                        if shares and shares > 0:
                            bvps = round(eq / shares, 2)
                    except Exception:
                        pass
        except Exception:
            pass

        # ── 計算 ROE（最新年度）──
        roe = None
        latest_yr = None
        if net_income_history and equity_map:
            common_yrs = set(net_income_history.keys()) & set(equity_map.keys())
            if common_yrs:
                latest_yr = max(common_yrs)
                ni = net_income_history[latest_yr]
                eq = equity_map[latest_yr]
                if eq and eq > 0:
                    roe = round(ni / eq * 100, 2)

        # ── 計算負債比（最新年度）──
        debt_ratio = None
        if total_debt_map and total_assets_map:
            common_yrs = set(total_debt_map.keys()) & set(total_assets_map.keys())
            if common_yrs:
                yr = max(common_yrs)
                debt = total_debt_map[yr]
                assets = total_assets_map[yr]
                if assets and assets > 0:
                    debt_ratio = round(debt / assets * 100, 2)

        # ── PB ──
        pb = round(price / bvps, 2) if price and bvps and bvps > 0 else None

        # ── trailing EPS（最新年度）──
        trailing_eps = eps_history.get(max(eps_history.keys())) if eps_history else None

        # ── 產業別（yfinance info，最精確）──
        industry_zh = ""
        try:
            info = ticker.info or {}
            _ind_en = info.get('industry', '') or info.get('sector', '') or ''
            IND_MAP = {
                "Semiconductors": "半導體", "Semiconductor Equipment & Materials": "半導體設備",
                "Electronic Components": "電子零組件", "Electronics Distribution": "電子通路",
                "Computer Hardware": "電腦硬體", "Consumer Electronics": "消費電子",
                "Communication Equipment": "通訊設備", "Information Technology Services": "資訊服務",
                "Software—Application": "應用軟體", "Software—Infrastructure": "基礎軟體",
                "Internet Content & Information": "網路內容",
                "Specialty Chemicals": "特化材料", "Chemicals": "化學",
                "Steel": "鋼鐵", "Aluminum": "鋁業", "Copper": "銅業",
                "Specialty Industrial Machinery": "工業機械", "Electrical Equipment & Parts": "電氣設備",
                "Scientific & Technical Instruments": "科學儀器",
                "Auto Parts": "汽車零件", "Auto Manufacturers": "整車製造",
                "Aerospace & Defense": "航太國防", "Contract Manufacturers": "代工製造",
                "Optical Fiber": "光纖", "Fiber Optic & Cable": "光纖電纜",
                "Telecom Services": "電信服務",
                "Banks—Regional": "區域銀行", "Banks—Diversified": "銀行",
                "Insurance—Life": "壽險", "Insurance—Property & Casualty": "產險",
                "Asset Management": "資產管理", "Capital Markets": "資本市場",
                "Real Estate—Diversified": "不動產", "REIT—Diversified": "REITs",
                "Biotechnology": "生技", "Drug Manufacturers—General": "製藥",
                "Medical Devices": "醫療器材", "Medical Care Facilities": "醫療服務",
                "Diagnostics & Research": "診斷研究",
                "Food Distribution": "食品", "Packaged Foods": "包裝食品",
                "Beverages—Non-Alcoholic": "飲料", "Apparel Manufacturing": "成衣",
                "Department Stores": "百貨", "Grocery Stores": "超市",
                "Specialty Retail": "特殊零售", "Residential Construction": "住宅建設",
                "Engineering & Construction": "工程建設",
                "Airlines": "航空", "Marine Shipping": "海運", "Trucking": "陸運",
                "Transportation": "運輸",
                "Utilities—Regulated Electric": "電力", "Utilities—Diversified": "公用事業",
                "Oil & Gas E&P": "石油天然氣", "Coal": "煤礦",
                "Technology": "科技", "Financial Services": "金融服務",
                "Healthcare": "醫療健康", "Industrials": "工業製造",
                "Consumer Defensive": "民生消費", "Consumer Cyclical": "景氣消費",
                "Communication Services": "通訊服務", "Energy": "能源",
                "Real Estate": "不動產", "Utilities": "公用事業",
                "Basic Materials": "基礎材料",
            }
            industry_zh = IND_MAP.get(_ind_en, _ind_en)
        except Exception:
            pass

        return {
            'code': code,
            'roe': roe, 'debt_ratio': debt_ratio, 'bvps': bvps,
            'price': price, 'pb': pb, 'trailing_eps': trailing_eps,
            'eps_history': eps_history, 'net_income_history': net_income_history,
            'equity_map': equity_map, 'industry': industry_zh,
        }
    except Exception:
        return {
            'code': code, 'roe': None, 'debt_ratio': None,
            'bvps': None, 'price': None, 'pb': None,
            'trailing_eps': None, 'eps_history': {},
            'net_income_history': {}, 'equity_map': {}, 'industry': '',
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
    資料來源：yfinance。
    改進：分批處理 + 即時進度更新 + 中途結果暫存（避免 Streamlit Cloud timeout）
    """
    import yfinance as yf

    results = []
    stock_dict = {str(s['code']).strip(): s for s in all_stocks}
    individual_codes = [k for k, v in stock_dict.items() if v.get('type') == '個股']

    now_yr = datetime.now().year
    total = len(individual_codes)

    # ── 進度顯示元件 ──
    progress_bar = st.progress(0)
    status_text  = st.empty()
    partial_save = st.empty()

    BATCH_SIZE = 50  # 每50檔存一次暫存，避免整批丟失

    for i, code in enumerate(individual_codes):
        # 即時更新進度
        pct = (i + 1) / total
        progress_bar.progress(pct)
        status_text.text("評分中 {}/{} — {} （{:.0f}%）".format(
            i + 1, total, code, pct * 100))

        try:
            fin = get_fin_data_yfinance(code)
            stock = stock_dict.get(code, {})

            roe   = fin.get('roe')
            debt  = fin.get('debt_ratio')
            bvps  = fin.get('bvps')
            price = fin.get('price')
            pb    = round(price / bvps, 2) if price and bvps and bvps > 0 else None
            eps_hist    = fin.get('eps_history', {})
            valid_years = sorted([yr for yr in eps_hist.keys() if yr >= now_yr - 6], reverse=True)

            # 補充 yfinance 產業別
            yf_industry = fin.get('industry', '')
            if yf_industry and not stock.get('industry'):
                stock_dict[code]['industry'] = yf_industry

            # ── NaN 保護 ──
            import math
            def _v(x):
                if x is None: return None
                try:
                    return None if math.isnan(float(x)) else float(x)
                except Exception:
                    return None
            roe = _v(roe); debt = _v(debt); bvps = _v(bvps); price = _v(price)
            if price and bvps and bvps > 0:
                pb = round(price / bvps, 2)
            else:
                pb = None

            # ── 硬性條件 ──
            c1 = (len(valid_years) >= 2 and
                  all(eps_hist.get(yr, -1) > 0 for yr in valid_years[:3]))
            c2 = False
            if len(valid_years) >= 2:
                newest = eps_hist.get(valid_years[0])
                oldest = eps_hist.get(valid_years[min(2, len(valid_years)-1)])
                if newest is not None and oldest and oldest != 0:
                    c2 = newest > oldest
            c3 = (debt < 50) if debt is not None else None

            # ── 品質條件 ──
            c4 = (roe  > 15)  if roe  is not None else None
            c5 = (pb   < 3)   if pb   is not None else None
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

            q = calc_quality_score_v2(code, stock, roe, debt, bvps, price, pb, eps_hist, valid_years)

            results.append({
                '等級': grade, '_grade_short': grade_short,
                '體質分數': q['total'] if q else None,
                '體質等級': q['grade'] if q else 'N/A',
                '資料完整度': str(q['data_completeness']) + '%' if q else 'N/A',
                '資料警示': q['data_warning'] if q else '',
                '代碼': code, '名稱': stock.get('name', ''),
                '產業別': stock.get('industry', stock.get('group', '')),
                '降級原因': grade_reason,
                '股價': price, 'PB': pb, 'ROE%': roe, '負債比%': debt,
                'PB/ROE': round(pb / roe, 3) if pb and roe and roe > 0 else None,
                '①EPS近3年正': '✅' if c1 else '❌',
                '②EPS成長':    '✅' if c2 else '❌',
                '③負債比<50%': '✅' if c3 else ('❌' if c3 is False else '⚠️'),
                '④ROE>15%':   '✅' if c4 else ('❌' if c4 is False else '⚠️'),
                '⑤PB<3':      '✅' if c5 else ('❌' if c5 is False else '⚠️'),
                '⑥PB/ROE<0.20': '✅' if c6 else ('❌' if c6 is False else '⚠️'),
                '▶A獲利(0-5)': q['score_a'] if q else 0,
                '▶B護城河(0-5)': q['score_b'] if q else 0,
                '▶C安全邊際(0-5)': q['score_c'] if q else 0,
                'A細節': q['detail_a'] if q else '',
                'B細節': q['detail_b'] if q else '',
                'C細節': q['detail_c'] if q else '',
            })

        except Exception as e:
            # 單檔失敗不中斷整體
            results.append({
                '等級': '⚠️ 跳過', '_grade_short': '排除',
                '體質分數': None, '體質等級': 'N/A', '資料完整度': '0%',
                '資料警示': str(e)[:50], '代碼': code,
                '名稱': stock_dict.get(code, {}).get('name', ''),
                '產業別': '', '降級原因': '資料抓取失敗',
            })

        # 每 BATCH_SIZE 檔暫存到 session_state，讓使用者即使斷線也不會完全重頭
        if (i + 1) % BATCH_SIZE == 0:
            df_partial = pd.DataFrame(results)
            st.session_state['df_pool_partial'] = df_partial
            partial_save.caption("已完成 {}/{} 檔，暫存中...".format(i + 1, total))

    progress_bar.empty()
    status_text.empty()
    partial_save.empty()

    if not results:
        return None
    return pd.DataFrame(results)



# ══════════════════════════════════════════════════════
# 📊 體質評分卡（滿分15分，每項5分，共3大項）
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
            score_a += 2; detail_a.append("✅ 近3年EPS皆正 +2")
        else:
            detail_a.append("❌ 有虧損年度")
    else:
        detail_a.append("⚠️ EPS年度資料不足")

    if roe is not None:
        if roe >= 20:   score_a += 3; detail_a.append("✅ ROE≥20% +3")
        elif roe >= 15: score_a += 2; detail_a.append("✅ ROE≥15% +2")
        elif roe >= 8:  score_a += 1; detail_a.append("🟡 ROE≥8% +1")
        else:           detail_a.append("❌ ROE<8%")
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
            score_b += 2; detail_b.append("✅ EPS近年成長 +2")
        else:
            detail_b.append("❌ EPS未成長")
    else:
        detail_b.append("⚠️ 資料不足")

    if debt is not None:
        if debt < 30:   score_b += 3; detail_b.append("✅ 負債比<30% +3")
        elif debt < 50: score_b += 2; detail_b.append("✅ 負債比<50% +2")
        elif debt < 65: score_b += 1; detail_b.append("🟡 負債比<65% +1")
        else:           detail_b.append("❌ 負債比≥65%")
    else:
        detail_b.append("⚠️ 負債比無資料")
    score_b = min(score_b, 5)

    # ── 維度C：安全邊際（0-5分）──
    score_c = 0
    detail_c = []
    if pb is not None and roe is not None and roe > 0:
        pb_roe = pb / roe
        if pb_roe < 0.10:   score_c += 3; detail_c.append("✅ PB/ROE<0.10 +3")
        elif pb_roe < 0.20: score_c += 2; detail_c.append("✅ PB/ROE<0.20 +2")
        elif pb_roe < 0.35: score_c += 1; detail_c.append("🟡 PB/ROE<0.35 +1")
        else:                detail_c.append("❌ PB/ROE≥0.35")
    elif pb is not None:
        if pb < 1.5:   score_c += 2; detail_c.append("✅ PB<1.5 +2")
        elif pb < 3:   score_c += 1; detail_c.append("🟡 PB<3 +1")
        else:          detail_c.append("❌ PB≥3")
    else:
        detail_c.append("⚠️ PB無資料")

    if price is not None and price > 10:
        score_c += 2; detail_c.append("✅ 股價>10 +2")
    elif price is not None and price > 5:
        score_c += 1; detail_c.append("🟡 股價5-10 +1")
    else:
        detail_c.append("❌ 股價≤5")
    score_c = min(score_c, 5)

    total = score_a + score_b + score_c
    if total >= 13:   grade = "⭐⭐⭐ 核心";   grade_label = "核心標的"
    elif total >= 9:  grade = "⭐⭐ 可觀察";  grade_label = "可觀察"
    elif total >= 5:  grade = "⭐ 高風險";    grade_label = "高風險"
    else:             grade = "⚠️ 資料不足";  grade_label = "資料不足"

    # KY 股警示（境外上市，財報可信度較低）
    name_str = stock.get('name', '') or ''
    is_ky = "KY" in str(code).upper() or "-KY" in name_str.upper() or "KY" in name_str.upper()
    ky_warning = "⛔ 境外上市（KY）股：財報申報在境外，資訊透明度低於台灣本土股，評分數字需謹慎參考。" if is_ky else ""

    data_warn = ("⚠️ 資料{:.0f}%完整（缺：{}），分數可能偏低".format(
        completeness, "、".join(missing_fields)) if completeness < 75 else "")

    full_warning = " | ".join(filter(None, [ky_warning, data_warn])) if (ky_warning or data_warn) else ""

    return {
        "total": total, "score_a": score_a, "score_b": score_b, "score_c": score_c,
        "grade": grade, "grade_label": grade_label,
        "detail_a": "<br>".join(detail_a),
        "detail_b": "<br>".join(detail_b),
        "detail_c": "<br>".join(detail_c),
        "data_completeness": round(completeness),
        "data_warning": full_warning,
        "missing_fields": missing_fields,
        "is_ky": is_ky,
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
    st.markdown(_tab_icon("icon-building", "合格標的池", "15分體質評分篩選 · 找出值得進場的好公司"), unsafe_allow_html=True)
    st.caption("📄 PDF說明：請用下方「下載HTML報告」按鈕，下載後在瀏覽器直接開啟，再按 Ctrl+P 存成PDF（完整輸出，不受 iframe 限制）")

    st.caption("體質評分系統：從ROE、EPS成長、負債比、估值三個維度為個股打分，找出「基本面紮實、值得在超跌時進場」的標的。合格標的池的用途是縮小候選範圍，觸發信號仍以每日警示掃描為準。")
    st.divider()

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
    with st.expander("📖 六個篩選條件說明（價值投資財務門檻，非 Coatue 條件）"):
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
        st.caption("建立完整池子需要抓取約2000檔財務資料（約需3～5分鐘）。池子每季更新一次即可。")

    # ── 快速查詢（不需要建立完整池子）──
    if quick_btn:
        st.markdown("#### 個股即時體質查詢")
        q_col1, q_col2 = st.columns([1, 3])
        with q_col1:
            instant_code = st.text_input("輸入代碼", placeholder="例：2330", key="instant_query_code")
            instant_go = st.button("查詢", key="instant_query_go")
        with q_col2:
            if instant_go and instant_code.strip():
                code_q = instant_code.strip()
                # 先查 pool
                df_pool_check = st.session_state.get('df_pool', None)
                found_in_pool = False
                if df_pool_check is not None and not df_pool_check.empty:
                    df_pool_check['代碼'] = df_pool_check['代碼'].astype(str).str.strip()
                    row_df = df_pool_check[df_pool_check['代碼'] == code_q]
                    if not row_df.empty:
                        found_in_pool = True
                        row = row_df.iloc[0]
                        sc = "#0F6E56" if row.get('體質分數', 0) >= 13 else "#F86200" if row.get('體質分數', 0) >= 9 else "#A32D2D"
                        st.markdown("""
<div style="background:#f8f9fa;border-radius:8px;border:2px solid {c};padding:14px 18px">
  <div style="font-size:13px;color:#888;margin-bottom:4px">{code} {name} ── 合格標的池記錄</div>
  <div style="font-size:22px;font-weight:700;color:{c}">{grade} 　{sc}/15分</div>
  <div style="font-size:13px;color:#414141;margin-top:6px">{reason}</div>
</div>""".format(c=sc, code=code_q, name=row.get('名稱',''),
                grade=row.get('等級',''), sc=int(row.get('體質分數',0)) if row.get('體質分數') else '—',
                reason=row.get('降級原因','')), unsafe_allow_html=True)

                if not found_in_pool:
                    # 即時抓 yfinance
                    with st.spinner("即時抓取 {} 財務資料...".format(code_q)):
                        fin_q = get_fin_data_yfinance(code_q)
                    import math
                    def _vq(x):
                        if x is None: return None
                        try: return None if math.isnan(float(x)) else float(x)
                        except: return None
                    roe_q = _vq(fin_q.get('roe')); debt_q = _vq(fin_q.get('debt_ratio'))
                    pb_q  = _vq(fin_q.get('pb'));  eps_q  = _vq(fin_q.get('trailing_eps'))
                    eps_hist_q = fin_q.get('eps_history', {})
                    valid_yr_q = sorted([y for y in eps_hist_q if eps_hist_q[y] is not None], reverse=True)
                    q_result = calc_quality_score_v2(code_q, {'type':'個股'}, roe_q, debt_q,
                                                     fin_q.get('bvps'), fin_q.get('price'), pb_q,
                                                     eps_hist_q, valid_yr_q)
                    if q_result:
                        sc = "#0F6E56" if q_result['total'] >= 13 else "#F86200" if q_result['total'] >= 9 else "#A32D2D"
                        st.markdown("""
<div style="background:#f8f9fa;border-radius:8px;border:2px solid {c};padding:14px 18px">
  <div style="font-size:13px;color:#888;margin-bottom:4px">{code} ── 即時計算（未建池）</div>
  <div style="font-size:22px;font-weight:700;color:{c}">{grade}　{sc}/15分</div>
  <div style="font-size:13px;color:#414141;margin-top:4px">A:{sa}/5　B:{sb}/5　C:{scc}/5</div>
</div>""".format(c=sc, code=code_q, grade=q_result['grade'], sc=q_result['total'],
                sa=q_result['score_a'], sb=q_result['score_b'], scc=q_result['score_c']),
                unsafe_allow_html=True)
                    else:
                        st.warning("{} 財務資料不足，無法評分（ETF 或新掛牌股）".format(code_q))
            elif instant_go:
                st.warning("請輸入股票代碼")

    if build_btn:
        with st.spinner("步驟1/2：取得全市場股票清單..."):
            all_stocks = get_all_tw_stocks()
            individual_stocks = [s for s in all_stocks if s['type'] == '個股']
            n_total = len(all_stocks)
            n_indiv = len(individual_stocks)
            n_etf_p = sum(1 for s in all_stocks if s['type'] == '被動ETF')
            n_etf_a = sum(1 for s in all_stocks if s['type'] == '主動ETF')
            n_other = n_total - n_indiv - n_etf_p - n_etf_a
            st.info(
                "取得 {} 筆股票（個股 {} 檔 ｜ 被動ETF {} 檔 ｜ 主動ETF/含字母 {} 檔 ｜ 特別股/其他 {} 檔）\n"
                "→ 合格標的池評分對象：{} 檔個股（ETF 與特別股不做體質評分）".format(
                    n_total, n_indiv, n_etf_p, n_etf_a, n_other, n_indiv)
            )

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
        st.markdown("### 📊 體質評分卡說明（15分制）")
        with st.expander("📖 評分邏輯說明（點擊展開）"):
            st.markdown("""
| 維度 | 滿分 | 評分項目 | 滿分條件 |
|------|------|---------|---------|
| **A 獲利能力** | 5分 | A1近5年EPS皆正（0或2分）＋A2 ROE水準（0～3分） | EPS全正且ROE≥20% |
| **B 商業模式護城河** | 5分 | B1近3年EPS成長（0或2分）＋B2負債比（0～3分） | EPS成長且負債比<30% |
| **C 市值與安全邊際** | 5分 | C1 PB/ROE複合估值（0～3分）＋C2股價流動性（0～2分） | PB/ROE<0.10且股價>10 |

**等級對照：**
- ⭐⭐⭐ **核心標的**（13～15分）：體質優秀（ROE高+負債低+估值合理），觸發時優先進場
- ⭐⭐ **可觀察**（9～12分）：體質尚可，可進場但倉位控制
- ⭐ **高風險**（5～8分）：基本面偏弱，謹慎；市場過熱時不宜進場
- 💀 **Broken Model**（0～4分）：類Robinhood/Lemonade，跌有原因，不宜進場
            """)

        # ── ② 滿分 / 高分標的快速篩選 ──
        if '體質分數' in df_pool.columns:
            df_scored = df_pool[df_pool['體質分數'].notna()].copy()
            df_scored['體質分數'] = pd.to_numeric(df_scored['體質分數'], errors='coerce')
            df_15 = df_scored[df_scored['體質分數'] >= 15].sort_values('體質分數', ascending=False)
            df_13 = df_scored[(df_scored['體質分數'] >= 13) & (df_scored['體質分數'] < 15)].sort_values('體質分數', ascending=False)

            cols_rank = ['體質分數', '體質等級', '代碼', '名稱', '股價', '產業別', 'ROE%', '負債比%',
                         '▶A獲利(0-5)', '▶B護城河(0-5)', '▶C安全邊際(0-5)']

            st.markdown("""
<div style="background:#f8f9fa;border-radius:10px;border:0.5px solid #e0e0e0;padding:16px 20px;margin-bottom:16px">
  <div style="font-size:15px;font-weight:700;color:#003781;margin-bottom:10px">體質滿分 / 高分標的清單（不限是否觸發）</div>
  <div style="font-size:13px;color:#414141;margin-bottom:4px">這裡顯示市場上所有高體質評分的標的，與是否已觸發進場信號無關。</div>
  <div style="font-size:13px;color:#888">觸發進場信號請至【每日警示掃描】頁籤確認。</div>
</div>""", unsafe_allow_html=True)

            col_s15, col_s13 = st.columns(2)
            col_s15.markdown("""
<div style="background:#f8f9fa;border-radius:8px;border:2px solid #0F6E56;padding:10px 14px;text-align:center">
  <div style="font-size:13px;color:#888;margin-bottom:5px">滿分標的</div>
  <div style="font-size:28px;font-weight:700;color:#0F6E56">{n}<span style="font-size:13px;color:#888;font-weight:400"> 檔</span></div>
  <div style="font-size:13px;color:#0F6E56">15 / 15 分</div>
</div>""".format(n=len(df_15)), unsafe_allow_html=True)
            col_s13.markdown("""
<div style="background:#f8f9fa;border-radius:8px;border:2px solid #185FA5;padding:10px 14px;text-align:center">
  <div style="font-size:13px;color:#888;margin-bottom:5px">A級標的</div>
  <div style="font-size:28px;font-weight:700;color:#185FA5">{n}<span style="font-size:13px;color:#888;font-weight:400"> 檔</span></div>
  <div style="font-size:13px;color:#185FA5">13–14 分</div>
</div>""".format(n=len(df_13)), unsafe_allow_html=True)

            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

            if not df_15.empty:
                st.markdown("**15/15 滿分標的**")
                available_15 = [c for c in cols_rank if c in df_15.columns]
                show_html(df_15[available_15].reset_index(drop=True))
            else:
                st.info("目前無 15/15 滿分標的（資料庫中所有個股均有至少一項扣分）")

            if not df_13.empty:
                with st.expander("A級標的（13–14分）共 {} 檔".format(len(df_13))):
                    available_13 = [c for c in cols_rank if c in df_13.columns]
                    show_html(df_13[available_13].reset_index(drop=True))

            st.divider()

        # 體質分數排行（前20名）
        if '體質分數' in df_pool.columns:
            df_top_quality = df_pool[df_pool['體質分數'].notna()].sort_values('體質分數', ascending=False).head(20)
            if not df_top_quality.empty:
                st.markdown("#### 體質分數排行（前20名）")
                cols_rank = ['體質分數', '體質等級', '代碼', '名稱', '股價', '產業別', 'ROE%', '負債比%',
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
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                "📥 下載CSV",
                df_pool[display_cols].to_csv(index=False).encode('utf-8-sig'),
                "stock_grades.csv", "text/csv"
            )
        with col_dl2:
            try:
                html_bytes = generate_html_report_pool(df_pool)
                st.download_button(
                    "📄 下載HTML報告（開啟後 Ctrl+P 存PDF）",
                    html_bytes,
                    "合格標的池_{}.html".format(datetime.now().strftime("%Y%m%d")),
                    "text/html", key="dl_pool_html"
                )
            except Exception:
                pass

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
    st.caption("📄 PDF說明：請用下方「下載HTML報告」按鈕，下載後在瀏覽器直接開啟，再按 Ctrl+P 存成PDF（完整輸出，不受 iframe 限制）")

    # ── df_pool_now：全 tab1 共用，必須在最頂部定義 ──
    df_pool_now = st.session_state.get('df_pool', None)

    # ── 體質評分狀態提示 ──
    if df_pool_now is not None and not df_pool_now.empty:
        pool_size = len(df_pool_now)
        from_disk = st.session_state.get('pool_loaded_from_disk', False)
        saved_at  = st.session_state.get('pool_saved_at', '')
        src_label = "（從快取還原，建立於 {}）".format(saved_at[:16]) if from_disk else "（本次建立）"
        st.success("✅ 體質評分庫已載入　{}檔已評分　{}".format(pool_size, src_label))
    else:
        st.info(
            "💡 **體質評分尚未建立**：掃描結果的體質分數會顯示「未建池」。\n\n"
            "建議先至【📋 合格標的池】頁籤建立評分庫，建立後掃描自動帶入15分制評分。"
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
                        'score':    pr.get('體質分數'),
                        'grade':    pr.get('體質等級', ''),
                        'industry': pr.get('產業別', ''),
                        'score_a':  pr.get('▶A獲利(0-5)', 0),
                        'score_b':  pr.get('▶B護城河(0-5)', 0),
                        'score_c':  pr.get('▶C安全邊際(0-5)', 0),
                    }

            has_pool = len(pool_score_dict) > 0

            rows = []
            for r in results:
                code = str(r["代碼"]).strip()
                qi = pool_score_dict.get(code, {})
                q_score = qi.get('score')
                q_grade = qi.get('grade', '')
                # 產業別：優先從 pool 取（yfinance精確分類），其次原始掃描結果
                industry = qi.get('industry') or r.get('產業別', '') or r.get('產業群組', '')

                # 體質分數欄
                _is_etf_code = (len(code) == 6 and code.startswith('00')) or \
                               any(kw in r.get('名稱','') for kw in ['ETF','指數','基金','債券'])

                if _is_etf_code:
                    score_str = "ETF"; grade_str = "不適用"

                elif isinstance(q_score, (int, float)):
                    # 在池中：直接用 pool 的分數
                    import math as _math_scan
                    try:
                        _qs_f = float(q_score)
                        if _math_scan.isnan(_qs_f) or _qs_f == 0:
                            _sa = int(qi.get('score_a', 0) or 0)
                            _sb = int(qi.get('score_b', 0) or 0)
                            _sc = int(qi.get('score_c', 0) or 0)
                            _recalc = _sa + _sb + _sc
                            q_score   = _recalc if _recalc > 0 else None
                            score_str = "{}/15".format(_recalc) if _recalc > 0 else "資料不足"
                            grade_str = ("核心標的" if _recalc >= 13 else "可觀察" if _recalc >= 9 else "高風險" if _recalc >= 5 else "資料不足") if _recalc > 0 else "資料不足"
                        else:
                            score_str = "{}/15".format(int(_qs_f))
                            grade_str = q_grade if q_grade and q_grade not in ("Broken Model","查無","","資料不足") else (
                                "核心標的" if _qs_f >= 13 else "可觀察" if _qs_f >= 9 else "高風險" if _qs_f >= 5 else "資料不足")
                    except Exception:
                        score_str = "資料不足"; grade_str = "資料不足"

                else:
                    # 不在池中（或無pool）：一律即時 yfinance 計算，不依賴 pool
                    try:
                        _fin_i = get_fin_data_yfinance(code)
                        if _fin_i.get('industry'):
                            industry = _fin_i['industry']
                        import math as _mi2
                        def _vi2(x):
                            if x is None: return None
                            try: return None if _mi2.isnan(float(x)) else float(x)
                            except: return None
                        _qi2 = calc_quality_score_v2(
                            code, {'type':'個股'},
                            _vi2(_fin_i.get('roe')), _vi2(_fin_i.get('debt_ratio')),
                            _fin_i.get('bvps'), _fin_i.get('price'),
                            _vi2(_fin_i.get('pb')),
                            _fin_i.get('eps_history', {}),
                            sorted([y for y in _fin_i.get('eps_history',{}) if _fin_i['eps_history'][y] is not None], reverse=True)
                        )
                        if _qi2 and _qi2['total'] > 0:
                            q_score   = _qi2['total']
                            score_str = "{}/15{}".format(q_score, "" if has_pool else "*")
                            grade_str = _qi2['grade_label']
                        else:
                            score_str = "資料不足"; grade_str = "資料不足"
                    except Exception:
                        score_str = "資料不足"; grade_str = "資料不足"

                # 4個條件
                c1_ok = r.get("連續觸發天數", 99) <= 3
                c2_ok = isinstance(q_score, (int, float)) and q_score >= 9
                c3_ok = bool(market_ok)
                ret_val = float(str(r.get("滾動10日報酬率", "0")).replace("%", ""))
                c4_ok = ret_val <= (threshold1 - 2)
                cond_met = sum([c1_ok, c2_ok, c3_ok, c4_ok])

                # 信號判斷邏輯（以體質分數為核心）：
                # 體質分數 < 9 → 直接弱，不管其他條件
                # 體質分數 ≥ 9（公司體質OK）才進一步看市場條件
                #   強烈：體質好 + 市場正常 + 深度超跌 + 新進
                #   有效：體質好 + 深度超跌（核心兩條，市場非必要）
                #   觀察：體質好，但跌幅不夠深或市場偏熱
                #   弱：體質分數 < 9，不建議進場
                if not c2_ok:
                    signal = "⚪ 弱"
                elif cond_met == 4:
                    signal = "🔥 強烈"
                elif c2_ok and c4_ok and c3_ok:
                    signal = "✅ 有效"
                elif c2_ok and c4_ok:
                    signal = "🔶 觀察"
                else:
                    signal = "🔶 觀察"

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

                    "②體質合格": "✅" if c2_ok else ("—" if not has_pool else "❌"),
                    "③市場正常": "✅" if c3_ok else "❌",
                    "④深度超跌": "✅" if c4_ok else "❌",
                    "_signal_raw": signal,  # 內部用，篩選 MOPS 查詢範圍
                })

            df_show = pd.DataFrame(rows)
            signal_order = {"🔥 強烈": 0, "✅ 有效": 1, "🔶 觀察": 2, "⚪ 弱": 3}
            df_show["_rank"] = df_show["信號"].map(signal_order).fillna(9)

            def _parse_score_sort(v):
                try: return -float(str(v).replace("*","").split("/")[0])  # 負號讓高分在前
                except: return 0

            def _parse_pct_sort(v):
                try: return float(str(v).replace("%",""))  # 越負越深，排在前
                except: return 0

            df_show["_score_sort"] = df_show["體質分數"].apply(_parse_score_sort)
            df_show["_pct_sort"]   = df_show["10日報酬"].apply(_parse_pct_sort)

            # 排序邏輯（全員辯證結論）：
            # 強烈/有效/觀察：體質高→低（核心），同分時跌幅深→淺（次要）
            # 弱：跌幅深→淺（提醒最危險的在最上面，這組是警示不是進場）
            def _inner_sort_fn(r):
                if r["_rank"] == 3:   # 弱組
                    return r["_pct_sort"]          # 跌幅深→淺
                else:                  # 強烈/有效/觀察
                    return r["_score_sort"]         # 體質高→低（主鍵）

            df_show["_inner_sort"] = df_show.apply(_inner_sort_fn, axis=1)

            # 弱組次要鍵用跌幅，其他組次要鍵也用跌幅（同體質時跌更深的優先）
            df_show = df_show.sort_values(
                ["_rank", "_inner_sort", "_pct_sort"]).reset_index(drop=True)

            # ── 風險偵測：MOPS 重大訊息 + Google News 新聞搜尋（雙層）──
            # 僅對「強烈／有效／觀察」組查詢
            # 設計原則：查詢失敗靜默顯示「—」，不顯示「❓」干擾判讀
            # 只有真正偵測到風險或確認無異常時才顯示結果
            MOPS_CHECK_SIGNALS = {"🔥 強烈", "✅ 有效", "🔶 觀察"}
            check_targets = df_show[df_show["_signal_raw"].isin(MOPS_CHECK_SIGNALS)]

            try:
                if len(check_targets) > 0:
                    with st.spinner("風險偵測中（MOPS + 新聞）..."):
                        risk_lookup = {}
                        any_news_ok = False
                        any_mops_ok = False

                        for _, rr in check_targets.iterrows():
                            code_c = rr["代碼"]
                            name_c = rr["名稱"]

                            # MOPS 查詢
                            mops_detail = query_mops_risk_detail(code_c)
                            if mops_detail["data_source_ok"]:
                                any_mops_ok = True

                            # 新聞查詢（失敗就忽略，不影響 MOPS 結果）
                            news_detail = search_news_risk(code_c, name_c)
                            if news_detail["status"] != "error":
                                any_news_ok = True

                            # 判斷：只有真正查到結果才顯示，失敗靜默為「—」
                            mops_ok = mops_detail["status"] != "error"
                            news_ok = news_detail["status"] != "error"

                            if not mops_ok and not news_ok:
                                # 兩個都查不到：不顯示任何結論
                                risk_lookup[code_c] = "—"
                            elif mops_detail["status"] == "danger" or news_detail["status"] == "danger":
                                # 任一層偵測到高風險
                                kws = (mops_detail.get("danger_kw", [])[:1] +
                                       news_detail.get("danger_kw", [])[:1])
                                src_label = "MOPS" if mops_detail["status"] == "danger" else "新聞"
                                risk_lookup[code_c] = "🚨 高風險[{}]：{}".format(
                                    src_label, "、".join(kws) or "詳見查詢頁")
                            elif mops_detail["status"] == "warning" or news_detail["status"] == "warning":
                                kws = (mops_detail.get("warn_kw", [])[:1] +
                                       news_detail.get("warn_kw", [])[:1])
                                src_label = "MOPS" if mops_detail["status"] == "warning" else "新聞"
                                risk_lookup[code_c] = "⚠️ 留意[{}]：{}".format(
                                    src_label, "、".join(kws) or "詳見查詢頁")
                            else:
                                # 查到了，沒有風險
                                risk_lookup[code_c] = "✅ 無異常"

                    # 說明哪些資料源有成功（只在底部 caption 說，不占表格欄位）
                    src_status = []
                    if any_mops_ok: src_status.append("MOPS✅")
                    else: src_status.append("MOPS❌")
                    if any_news_ok: src_status.append("新聞✅")
                    else: src_status.append("新聞❌（可能被網路封鎖）")

                    df_show["風險偵測"] = df_show["代碼"].map(
                        lambda c: risk_lookup.get(c, "—")
                    )
                    st.caption("風險偵測資料源：{}　｜　「—」= 查詢未成功，請至【🛡️ 個股風險查詢】頁籤手動查詢".format(
                        "　".join(src_status)))
                else:
                    df_show["風險偵測"] = "—"

            except Exception as _risk_err:
                df_show["風險偵測"] = "—"

            df_show = df_show.drop(columns=["_rank", "_signal_raw",
                                             "_score_sort", "_pct_sort", "_inner_sort"],
                                    errors="ignore")
            st.caption("💡 想看「風險偵測」欄位的完整詳情（含新聞標題、重訊記錄）？前往【🛡️ 個股風險查詢】頁籤輸入代碼查看。")

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
體質評分邏輯：區分「好公司短暫跌」vs「爛公司繼續跌」。9分以上代表獲利、護城河、安全邊際至少有兩項表現正常。評分以 ROE / EPS 穩定性 / 負債比 / 本淨比等財務指標為基礎，不需先建立標的池，可即時計算（標示 * 號）。

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
                st.caption("ℹ️ 標示「*」的體質分數為單檔即時計算；建立合格標的池後分數會被快取保存，重複掃描時不需重新呼叫 API（速度較快），但兩者使用的財務資料來源完全相同，準確度沒有差異。")

            # ── 表格 ──
            st.markdown(show_html.__doc__ or "")
            # 網頁版：用 st.dataframe（有原生點擊排序功能）
            # 先把下載用的欄位移除，只顯示有意義的欄
            _display_cols = [c for c in df_show.columns
                             if c not in ["_rank","_score_sort","_pct_sort","_inner_sort","_signal_raw"]]
            _df_display = df_show[_display_cols].copy()
            st.dataframe(
                _df_display,
                use_container_width=True,
                hide_index=True,
                height=min(50 + len(_df_display) * 35, 600),
            )
            col_scan_dl1, col_scan_dl2 = st.columns(2)
            with col_scan_dl1:
                st.download_button("📥 下載CSV", df_show.to_csv(index=False).encode("utf-8-sig"), "alert_scan.csv", "text/csv")
            with col_scan_dl2:
                try:
                    html_bytes = generate_html_report_scan(df_show, threshold1, datetime.now().strftime("%Y-%m-%d"))
                    st.download_button(
                        "📄 下載HTML報告（開啟後 Ctrl+P 存PDF）",
                        html_bytes,
                        "每日警示_{}.html".format(datetime.now().strftime("%Y%m%d")),
                        "text/html", key="dl_scan_html"
                    )
                except Exception:
                    pass
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
                            st.caption("A：{}".format(row2.get('A細節','').replace('｜',' | ')))
                            st.caption("B：{}".format(row2.get('B細節','').replace('｜',' | ')))
                            st.caption("C：{}".format(row2.get('C細節','').replace('｜',' | ')))
                    else:
                        st.warning("此代碼尚未評分，請先至【合格標的池】建立評分庫")
    else:
        st.info("尚未執行掃描，請設定門檻後點「🔍 開始掃描」")

# ==============================
# TAB 2: 批次回測
# ==============================
with tab2:
    st.markdown(_tab_icon("icon-trend", "批次回測", "最長15年 · 多標的同時回測"), unsafe_allow_html=True)
    st.caption("📄 PDF說明：請用下方「下載HTML報告」按鈕，下載後在瀏覽器直接開啟，再按 Ctrl+P 存成PDF（完整輸出，不受 iframe 限制）")

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
            col_bt_dl1, col_bt_dl2 = st.columns(2)
            with col_bt_dl1:
                st.download_button("📥 下載CSV", df_bt.to_csv(index=False).encode("utf-8-sig"), "backtest.csv", "text/csv")
            with col_bt_dl2:
                pass  # 批次回測暫無HTML報告按鈕
            st.warning("沒有找到任何觸發紀錄")

# ==============================
# TAB 3: 個股回測
# ==============================
with tab3:
    st.markdown(_tab_icon("icon-chart", "個股 / ETF 回測＋線圖", "15年回測 · 操作結論 · 出場策略"), unsafe_allow_html=True)
    st.caption("📄 PDF說明：請用下方「下載HTML報告」按鈕，下載後在瀏覽器直接開啟，再按 Ctrl+P 存成PDF（完整輸出，不受 iframe 限制）")

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
        code_clean = single_code.strip()
        df_pool_bt = st.session_state.get('df_pool', None)
        pool_r = pd.DataFrame()

        if df_pool_bt is not None and not df_pool_bt.empty:
            # 統一型別比對
            df_pool_bt['代碼'] = df_pool_bt['代碼'].astype(str).str.strip()
            pool_r = df_pool_bt[df_pool_bt['代碼'] == code_clean]

        if not pool_r.empty:
            pr = pool_r.iloc[0]
            score_a = pr.get('▶A獲利(0-5)', 0)
            score_b = pr.get('▶B護城河(0-5)', 0)
            score_c = pr.get('▶C安全邊際(0-5)', 0)
            det_a   = pr.get('A細節', '').replace('｜','<br>')
            det_b   = pr.get('B細節', '').replace('｜','<br>')
            det_c   = pr.get('C細節', '').replace('｜','<br>')

            # q_total：優先讀 pool 的體質分數；若為 None/NaN，從 A+B+C 重算
            import math as _math
            q_total_raw = pr.get('體質分數')
            try:
                q_total = float(q_total_raw) if (q_total_raw is not None and not _math.isnan(float(q_total_raw))) else None
            except Exception:
                q_total = None

            if q_total is None:
                # 從子分數重建總分
                try:
                    sa = int(score_a) if score_a not in (None, '-', '') else 0
                    sb = int(score_b) if score_b not in (None, '-', '') else 0
                    sc_v = int(score_c) if score_c not in (None, '-', '') else 0
                    q_total = sa + sb + sc_v
                except Exception:
                    q_total = None

            q_grade = pr.get('體質等級', '')
            # 若 grade 也缺失，根據分數重建
            if not q_grade and q_total is not None:
                q_grade = "核心標的" if q_total >= 13 else ("可觀察" if q_total >= 9 else ("高風險" if q_total >= 5 else "資料不足"))

            st.markdown("""
<div style="font-size:14px;font-weight:600;color:#003781;margin:4px 0 10px">{code} 體質評分卡</div>""".format(
    code=code_clean), unsafe_allow_html=True)

            col_qa, col_qb, col_qc, col_qtotal = st.columns(4)
            for col, label, score, detail in [
                (col_qa, "A 獲利能力", score_a, det_a),
                (col_qb, "B 護城河",   score_b, det_b),
                (col_qc, "C 安全邊際", score_c, det_c),
            ]:
                col.markdown("""
<div style="background:#f8f9fa;border-radius:8px;border:0.5px solid #e0e0e0;padding:12px 14px">
  <div style="font-size:13px;color:#888;margin-bottom:5px">{lb}</div>
  <div style="font-size:22px;font-weight:700;color:#003781">{sc}<span style="font-size:13px;color:#888;font-weight:400"> /5</span></div>
  <div style="font-size:13px;color:#888;margin-top:5px;line-height:1.8">{dt}</div>
</div>""".format(lb=label, sc=score, dt=detail), unsafe_allow_html=True)

            if q_total is not None and isinstance(q_total, (int, float)):
                score_int = int(q_total)
                sc_color = "#0F6E56" if score_int >= 13 else ("#F86200" if score_int >= 9 else "#A32D2D")
                col_qtotal.markdown("""
<div style="background:#f8f9fa;border-radius:8px;border:2px solid {c};padding:12px 14px;text-align:center">
  <div style="font-size:13px;color:#888;margin-bottom:5px">體質總分</div>
  <div style="font-size:26px;font-weight:700;color:{c}">{sc}<span style="font-size:13px;color:#888;font-weight:400"> /15</span></div>
  <div style="font-size:12px;color:{c};margin-top:4px;font-weight:600">{gr}</div>
</div>""".format(c=sc_color, sc=score_int, gr=q_grade), unsafe_allow_html=True)
            else:
                col_qtotal.markdown("""
<div style="background:#f8f9fa;border-radius:8px;border:0.5px solid #e0e0e0;padding:12px 14px;text-align:center">
  <div style="font-size:13px;color:#888">體質總分</div>
  <div style="font-size:18px;color:#888;margin-top:8px">資料不足</div>
</div>""", unsafe_allow_html=True)
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        else:
            try:
                fin_quick = get_fin_data_yfinance(code_clean)
                roe_q    = fin_quick.get('roe')
                debt_q   = fin_quick.get('debt_ratio')
                pb_q     = fin_quick.get('pb')
                eps_q    = fin_quick.get('trailing_eps')
                eps_hist = fin_quick.get('eps_history', {})
                valid_yrs = sorted([y for y in eps_hist if eps_hist[y] is not None], reverse=True)

                if any(v is not None for v in [roe_q, debt_q, pb_q, eps_q]):
                    # ── 財務數字卡片 ──
                    col_f1, col_f2, col_f3, col_f4 = st.columns(4)

                    def _is_valid(v):
                        """None 和 NaN 都視為無效"""
                        if v is None: return False
                        try:
                            import math
                            return not math.isnan(float(v))
                        except Exception:
                            return False

                    def _fin_card(col, label, val_str, hint, val_color="#003781"):
                        col.markdown("""
<div style="background:#f8f9fa;border-radius:8px;border:0.5px solid #e0e0e0;padding:12px 14px">
  <div style="font-size:13px;color:#888;margin-bottom:5px">{lb}</div>
  <div style="font-size:22px;font-weight:700;color:{vc}">{vl}</div>
  <div style="font-size:13px;color:#888;margin-top:5px">{ht}</div>
</div>""".format(lb=label, vc=val_color, vl=val_str, ht=hint), unsafe_allow_html=True)

                    roe_ok  = _is_valid(roe_q)
                    debt_ok = _is_valid(debt_q)
                    pb_ok   = _is_valid(pb_q)
                    eps_ok  = _is_valid(eps_q)

                    roe_str  = "{}%".format(round(float(roe_q),  1)) if roe_ok  else "—"
                    debt_str = "{}%".format(round(float(debt_q), 1)) if debt_ok else "—"
                    pb_str   = str(round(float(pb_q),  2))           if pb_ok   else "—"
                    eps_str  = str(round(float(eps_q), 2))           if eps_ok  else "—"

                    roe_hint  = ("優秀(≥20%)" if roe_ok  and float(roe_q)  >= 20 else "良好(≥15%)" if roe_ok  and float(roe_q)  >= 15 else "普通(≥8%)"  if roe_ok  and float(roe_q)  >= 8  else "偏弱(<8%)")  if roe_ok  else "無資料"
                    debt_hint = ("健康(<30%)" if debt_ok and float(debt_q) < 30 else "合格(<50%)" if debt_ok and float(debt_q) < 50 else "偏高(<65%)" if debt_ok and float(debt_q) < 65 else "過高(≥65%)") if debt_ok else "無資料"
                    pb_hint   = ("便宜(<1.5)" if pb_ok   and float(pb_q)   < 1.5 else "合理(<3)"  if pb_ok   and float(pb_q)   < 3   else "偏貴(<5)"  if pb_ok   and float(pb_q)   < 5   else "高估(≥5)")  if pb_ok   else "無資料"
                    eps_hint  = ("獲利穩定" if eps_ok and float(eps_q) > 0 else "虧損") if eps_ok else "無資料"

                    roe_c  = "#0F6E56" if roe_ok  and float(roe_q)  >= 15 else "#F86200" if roe_ok  and float(roe_q)  >= 8  else "#A32D2D" if roe_ok  else "#888"
                    debt_c = "#0F6E56" if debt_ok and float(debt_q) < 50  else "#F86200" if debt_ok and float(debt_q) < 65  else "#A32D2D" if debt_ok else "#888"
                    pb_c   = "#0F6E56" if pb_ok   and float(pb_q)   < 3   else "#F86200" if pb_ok   and float(pb_q)   < 5   else "#A32D2D" if pb_ok   else "#888"
                    eps_c  = "#0F6E56" if eps_ok  and float(eps_q)  > 0   else "#A32D2D" if eps_ok  else "#888"

                    _fin_card(col_f1, "ROE",     roe_str,  roe_hint,  roe_c)
                    _fin_card(col_f2, "負債比",  debt_str, debt_hint, debt_c)
                    _fin_card(col_f3, "PB",      pb_str,   pb_hint,   pb_c)
                    _fin_card(col_f4, "EPS(年)", eps_str,  eps_hint,  eps_c)

                    # ── 即時體質評分（用 calc_quality_score_v2）──
                    q_quick = calc_quality_score_v2(
                        code_clean,
                        {'type': '個股'},
                        roe_q, debt_q,
                        fin_quick.get('bvps'),
                        fin_quick.get('price'),
                        pb_q,
                        eps_hist, valid_yrs
                    )

                    if q_quick:
                        total_q = q_quick['total']
                        grade_q = q_quick['grade']
                        warn_q  = q_quick.get('data_warning', '')
                        sa, sb, sc_val = q_quick['score_a'], q_quick['score_b'], q_quick['score_c']

                        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                        col_qa, col_qb, col_qc, col_qtotal2 = st.columns(4)
                        for col_x, lbl, scr, det in [
                            (col_qa, "A 獲利能力", sa, q_quick.get('detail_a', '').replace('｜','<br>')),
                            (col_qb, "B 護城河",   sb, q_quick.get('detail_b', '').replace('｜','<br>')),
                            (col_qc, "C 安全邊際", sc_val, q_quick.get('detail_c', '').replace('｜','<br>')),
                        ]:
                            col_x.markdown("""
<div style="background:#f8f9fa;border-radius:8px;border:0.5px solid #e0e0e0;padding:12px 14px">
  <div style="font-size:13px;color:#888;margin-bottom:5px">{lb}</div>
  <div style="font-size:22px;font-weight:700;color:#003781">{sc}<span style="font-size:13px;color:#888;font-weight:400"> /5</span></div>
  <div style="font-size:13px;color:#888;margin-top:5px;line-height:1.8">{dt}</div>
</div>""".format(lb=lbl, sc=scr, dt=det), unsafe_allow_html=True)

                        sc_color2 = "#0F6E56" if total_q >= 13 else ("#F86200" if total_q >= 9 else "#A32D2D")
                        col_qtotal2.markdown("""
<div style="background:#f8f9fa;border-radius:8px;border:2px solid {c};padding:12px 14px;text-align:center">
  <div style="font-size:13px;color:#888;margin-bottom:5px">體質總分</div>
  <div style="font-size:26px;font-weight:700;color:{c}">{sc}<span style="font-size:13px;color:#888;font-weight:400"> /15</span></div>
  <div style="font-size:12px;color:{c};margin-top:4px;font-weight:600">{gr}</div>
</div>""".format(c=sc_color2, sc=total_q, gr=grade_q), unsafe_allow_html=True)

                        if warn_q:
                            st.caption(warn_q)

                    st.caption("即時財務（yfinance）｜建立合格標的池可取得含EPS歷史的完整評分")
                else:
                    st.caption("財務資料暫無（ETF或新掛牌股票）")
            except Exception:
                st.caption("財務資料查詢失敗")

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

        # ══════════════════════════════════════════════════════
        # ⚠️ 三層風險保護機制（辯證結果：均值回歸策略的前提條件）
        # ══════════════════════════════════════════════════════
        _risk_flags = []

        # ① KY 股 / 境外股警示
        _code_upper = single_code.strip().upper()
        _name_str = ""
        try:
            _df_all = get_all_tw_stocks()
            _match = [s for s in _df_all if s['code'] == single_code.strip()]
            if _match:
                _name_str = _match[0].get('name', '')
        except Exception:
            pass
        if "KY" in _code_upper or "KY" in _name_str.upper() or "-KY" in _name_str:
            _risk_flags.append({
                "level": "danger",
                "icon": "⛔",
                "title": "境外上市（KY）股票警示",
                "body": "此標的為境外上市公司（KY股），財報申報地點在境外，資訊透明度和財報可信度低於台灣本土股。"
                        "體質評分基於歷史 yfinance 數據，無法驗證財報真實性。"
                        "均值回歸策略在 KY 股的有效性大幅降低，建議不納入交易標的。"
            })

        # ② 近期觸發頻率異常偵測
        try:
            dates_all = sorted(prices.keys())
            result_thr = run_full_backtest(prices, thr_val)
            if result_thr and result_thr["total"] > 0:
                # 計算近6個月觸發次數
                from datetime import datetime as _dt, timedelta as _td
                cutoff_6m = (_dt.now() - _td(days=180)).strftime("%Y-%m-%d")
                recent_triggers = [t for t in result_thr["triggers"] if t["date"] >= cutoff_6m]
                recent_count = len(recent_triggers)
                # 歷史平均：總次數 / 年數 / 2（換算成6個月）
                total_years = max((len(dates_all) / 252), 1)
                hist_avg_6m = result_thr["total"] / total_years / 2
                if recent_count > hist_avg_6m * 2.5 and recent_count >= 5:
                    _risk_flags.append({
                        "level": "warning",
                        "icon": "⚠️",
                        "title": "近期觸發頻率異常密集",
                        "body": "近6個月觸發 {} 次（歷史6個月平均 {:.1f} 次），為歷史平均的 {:.1f} 倍。"
                                "觸發密集通常代表趨勢性下跌，而非情緒性超跌。"
                                "均值回歸策略在趨勢性下跌中勝率大幅下降，建議等待觸發頻率回歸正常再進場。".format(
                                    recent_count, hist_avg_6m,
                                    recent_count / max(hist_avg_6m, 0.1))
                    })
        except Exception:
            pass

        # ③ 均線空頭排列警示（股價低於120日均線且均線向下）
        try:
            dates_all = sorted(prices.keys())
            price_list = [prices[d] for d in dates_all]
            if len(price_list) >= 120:
                ma120_now  = sum(price_list[-120:]) / 120
                ma120_prev = sum(price_list[-140:-20]) / 120 if len(price_list) >= 140 else ma120_now
                curr_price_now = price_list[-1]
                ma120_falling = ma120_now < ma120_prev * 0.99
                price_below_ma = curr_price_now < ma120_now
                pct_below = (curr_price_now - ma120_now) / ma120_now * 100
                if price_below_ma and ma120_falling:
                    _risk_flags.append({
                        "level": "warning", "icon": "📉",
                        "title": "均線空頭排列：股價低於下降中的120日均線",
                        "body": "現價 {:.1f}，120日均線 {:.1f}（現價低於均線 {:.1f}%），且均線方向向下。"
                                "建議等待股價站回120日均線後再考慮進場，或將觸發門檻提高至 -15% 以上。".format(
                                    curr_price_now, ma120_now, abs(pct_below))
                    })
        except Exception:
            pass

        # ④ 公司面風險偵測：MOPS 重大訊息 + 月營收異動
        # 原則：1786科妍/2233宇隆/2543皇昌類型的公司面地雷，在觸發時主動查詢
        try:
            import requests as _req
            _code4 = single_code.strip()

            # ── ④-A：MOPS 重大訊息（共用函數，使用 TWSE OpenAPI t187ap04_L 正式資料）──
            _mops_detail = query_mops_risk_detail(_code4)

            if _mops_detail["status"] == "error":
                _risk_flags.append({
                    "level": "warning", "icon": "❓",
                    "title": "MOPS 風險偵測本次查詢失敗",
                    "body": "{}\n無法確認此股票是否有公司面風險，建議至【🛡️ 個股風險查詢】頁籤重試，或直接前往公開資訊觀測站（mops.twse.com.tw）核實。".format(
                        _mops_detail["error"])
                })
            elif _mops_detail["status"] == "danger":
                _risk_flags.append({
                    "level": "danger", "icon": "🚨",
                    "title": "MOPS 公開資訊觀測站偵測到高風險關鍵字",
                    "body": "近期重大訊息中出現以下關鍵字：{}。\n"
                            "此類訊息通常代表公司面臨重大財務或法律問題，強烈建議暫停進場，"
                            "可至【🛡️ 個股風險查詢】頁籤查看完整記錄，或前往公開資訊觀測站核實。".format(
                                "、".join(_mops_detail["danger_kw"][:5]))
                })
            elif _mops_detail["status"] == "warning":
                _risk_flags.append({
                    "level": "warning", "icon": "⚠️",
                    "title": "MOPS 偵測到需留意的公司異動",
                    "body": "近期公告出現以下關鍵字：{}。\n"
                            "建議至【🛡️ 個股風險查詢】頁籤查看完整記錄，確認公司營運無重大異常。".format(
                                "、".join(_mops_detail["warn_kw"][:3]))
                })

            # ── ④-A2：新聞搜尋（補足重大訊息未涵蓋的市場傳聞/治理危機）──
            try:
                _news_detail = search_news_risk(_code4, _code4)
                if _news_detail["status"] == "danger":
                    _risk_flags.append({
                        "level": "danger", "icon": "📰",
                        "title": "新聞搜尋偵測到高風險訊號",
                        "body": "近期新聞標題中出現以下關鍵字：{}。\n"
                                "重大訊息只涵蓋公司法定揭露事項，但經營權鬥爭、檢調動態等"
                                "媒體報導未必會立即發正式重訊。可至【🛡️ 個股風險查詢】頁籤查看完整新聞列表。".format(
                                    "、".join(_news_detail["danger_kw"][:5]))
                    })
                elif _news_detail["status"] == "warning":
                    _risk_flags.append({
                        "level": "warning", "icon": "📰",
                        "title": "新聞搜尋偵測到需留意的訊號",
                        "body": "近期新聞標題出現以下關鍵字：{}。\n"
                                "建議至【🛡️ 個股風險查詢】頁籤查看完整新聞，確認是否為重大事件。".format(
                                    "、".join(_news_detail["warn_kw"][:3]))
                    })
            except Exception:
                pass

            # ── ④-B：月營收異動警示（TWSE OpenAPI 公開資料）──
            try:
                _now_dt = datetime.now()
                _yr_tw  = _now_dt.year - 1911
                _mo     = _now_dt.month - 1 or 12
                _yr_tw2 = _yr_tw if _mo > 1 else _yr_tw - 1
                _rev_url = (
                    "https://mops.twse.com.tw/nas/t21/sii/t21sc03_{}_{}_{}.html".format(
                        _yr_tw2, str(_mo).zfill(2), 0)
                )
                _rev_res = _req.get(_rev_url, timeout=5,
                                    headers={"User-Agent": "Mozilla/5.0"})
                if _rev_res.status_code == 200:
                    _rev_text = _rev_res.text
                    # 找該代碼的當月YoY
                    import re as _re4b
                    _pat = r'{}.*?(-?\d+\.\d+)%'.format(_re4b.escape(_code4))
                    _m = _re4b.search(_pat, _re4b.sub(r'<[^>]+>', ' ', _rev_text))
                    if _m:
                        _yoy = float(_m.group(1))
                        if _yoy < -30:
                            _risk_flags.append({
                                "level": "warning", "icon": "📊",
                                "title": "月營收年增率大幅衰退 {:.1f}%".format(_yoy),
                                "body": "最近公布的月營收相較去年同期衰退 {:.1f}%（閾值：>-30% 觸發警示）。"
                                        "月營收大幅衰退可能代表主要客戶流失或產業需求下滑，"
                                        "請確認是否為一次性因素還是趨勢性惡化後再決定進場。".format(_yoy)
                            })
            except Exception:
                pass

        except Exception:
            pass

        # ── 顯示風險警示 ──
        if _risk_flags:
            st.markdown("---")
            st.markdown("""
<div style="font-size:15px;font-weight:700;color:#A32D2D;margin-bottom:10px">
  ⚠️ 進場前風險提示（共 {} 項，請逐一確認）
</div>""".format(len(_risk_flags)), unsafe_allow_html=True)

            for flag in _risk_flags:
                bg   = "#FEE0CC" if flag["level"] == "danger" else "#FEF0CC"
                bd   = "#A32D2D" if flag["level"] == "danger" else "#F86200"
                tc   = "#A32D2D" if flag["level"] == "danger" else "#633806"
                st.markdown("""
<div style="background:{bg};border-left:5px solid {bd};border-radius:0 8px 8px 0;
     padding:14px 18px;margin-bottom:10px">
  <div style="font-size:14px;font-weight:700;color:{tc};margin-bottom:6px">{icon} {title}</div>
  <div style="font-size:14px;color:#414141;line-height:1.7">{body}</div>
</div>""".format(bg=bg, bd=bd, tc=tc, icon=flag["icon"],
                title=flag["title"], body=flag["body"]), unsafe_allow_html=True)

            if not any(f["level"] == "danger" for f in _risk_flags):
                st.caption("以上為系統自動偵測的風險提示，不構成投資建議。請結合基本面判斷後決定是否進場。")
        else:
            st.markdown("""
<div style="background:#E1F5EE;border-left:5px solid #0F6E56;border-radius:0 8px 8px 0;
     padding:10px 18px;margin-bottom:6px">
  <div style="font-size:14px;color:#085041">✅ 風險偵測通過：無 KY 股 / 觸發頻率正常 / 均線方向中性或偏多</div>
</div>""", unsafe_allow_html=True)
        st.markdown("---")

        with st.spinner("計算各門檻回測中..."):
            df_win, df_avg, df_dd = build_summary_tables(prices)

        win_cols = [str(h) + "天勝率" for h in HORIZONS]
        avg_cols = [str(h) + "天平均報酬%" for h in HORIZONS]
        dd_cols = [str(h) + "天平均最大回撤%" for h in HORIZONS]

        st.markdown("### 表A：勝率（各門檻 × 觀察天數）｜橘色 ≥ 80%")
        st.caption("勝率 = 觸發進場後，T+N天收盤價高於進場收盤價的比例")
        show_html(df_win.style.map(color_winrate, subset=win_cols))

        st.markdown("### 表B：平均單次報酬%（各門檻 × 觀察天數）")
        st.caption("📐 **計算方式（按股數進場）**：各筆報酬率 = (出場價 - 進場價) / 進場價 × 100；平均報酬 = Σ報酬率 / 筆數。"
                   "　⚠️ 此為「各筆獨立報酬率算術平均」，假設每筆進場股數相同（非等金額）。等金額進場者，各筆權重因股價不同而略有差異。")
        show_html(heatmap_positive(df_avg, avg_cols))

        cum_rows = []
        for thr in THRESHOLDS:
            result_c = run_full_backtest(prices, thr)
            row = {"觸發門檻": str(thr) + "%", "樣本數": 0 if result_c is None else result_c["total"]}
            for h in HORIZONS:
                if result_c is None:
                    row[str(h) + "天累積%"] = "---"
                else:
                    items = result_c["horizon_rets"][h]
                    if items:
                        total_entry  = sum(x["entry_price"]  for x in items)
                        total_future = sum(x["future_price"] for x in items)
                        if total_entry > 0:
                            cum_pct = (total_future - total_entry) / total_entry * 100
                            row[str(h) + "天累積%"] = fmt(round(cum_pct, 2))
                        else:
                            row[str(h) + "天累積%"] = "---"
                    else:
                        row[str(h) + "天累積%"] = "---"
            cum_rows.append(row)

        st.markdown("### 表C：實際累積損益%（按股價進場）")
        st.caption("📐 **計算方式（按股價進場／每次買相同股數）**：把所有觸發的進場價加總、出場價加總，再計算整體損益。"
                   "　例：進場100+50+200=350元，出場110+55+180=345元，累積損益=(345-350)/350=-1.4%。"
                   "　反映「每次觸發買進相同股數」的整體真實報酬，高價股的影響權重較大。")
        df_cum = pd.DataFrame(cum_rows)
        cum_cols = [str(h) + "天累積%" for h in HORIZONS]
        show_html(heatmap_positive(df_cum, cum_cols))

        # ── 表D：等金額累積損益 ──
        eq_rows = []
        for thr in THRESHOLDS:
            result_d = run_full_backtest(prices, thr)
            row = {"觸發門檻": str(thr) + "%", "樣本數": 0 if result_d is None else result_d["total"]}
            for h in HORIZONS:
                if result_d is None:
                    row[str(h) + "天累積%"] = "---"
                else:
                    rets = [x["ret"] for x in result_d["horizon_rets"][h]]
                    row[str(h) + "天累積%"] = fmt(round(sum(rets), 2)) if rets else "---"
            eq_rows.append(row)

        st.markdown("### 表D：等金額累積損益%（每次投入相同金額）")
        st.caption("📐 **計算方式（等金額進場／每次投入固定金額如10萬）**：直接將各筆報酬率加總。"
                   "　例：+10%、+10%、-10% → 累積=+10%，意義為「以單次投入金額為基準，15年累積多賺了幾個投入金額的%」。"
                   "　與表C的差異：本表不受股價高低影響，每次觸發權重相同。")
        df_eq = pd.DataFrame(eq_rows)
        show_html(heatmap_positive(df_eq, cum_cols))

        st.markdown("### 表E：進場時機完整比較")
        st.caption("連續第1天：首次觸發當天進｜連續第2天：等跌第2天再進｜連續第3天以後：等更深跌｜連續結束翌日：止跌後才進")

        thr_choice_e = st.selectbox(
            "選擇觸發門檻",
            [str(t) + "%" for t in THRESHOLDS],
            index=THRESHOLDS.index(thr_val) if thr_val in THRESHOLDS else 2,
            key="timing_thr_e"
        )
        thr_val_e = int(thr_choice_e.replace("%", ""))

        # 建立全觀察天數對照表（行=進場時機，列=觀察天數）
        timing_groups = ["連續第1天進場", "連續第2天進場", "連續第3天以後進場", "連續結束翌日進場"]
        timing_short  = ["第1天進", "第2天進", "第3天+進", "止跌後進"]
        timing_matrix_wr  = {"進場時機": timing_short}
        timing_matrix_ret = {"進場時機": timing_short}

        for h in HORIZONS:
            df_t = build_entry_timing_table(prices, thr_val_e, h)
            wr_col  = []
            ret_col = []
            for g in timing_groups:
                if df_t is not None and g in df_t["進場時機"].values:
                    row_t = df_t[df_t["進場時機"] == g].iloc[0]
                    n = int(row_t.get("樣本數", 0))
                    flag = "⚠️" if n < 5 else ""
                    wr_col.append(str(row_t.get("勝率","---")) + flag)
                    ret_col.append(str(row_t.get("平均報酬%","---")) + flag)
                else:
                    wr_col.append("---")
                    ret_col.append("---")
            timing_matrix_wr[str(h)  + "天"] = wr_col
            timing_matrix_ret[str(h) + "天"] = ret_col

        df_tw = pd.DataFrame(timing_matrix_wr)
        df_tr = pd.DataFrame(timing_matrix_ret)
        h_cols = [str(h) + "天" for h in HORIZONS]

        st.markdown("**勝率對照**")
        show_html(df_tw.style.map(color_winrate, subset=h_cols))
        st.markdown("**平均報酬%對照**")
        show_html(heatmap_positive(df_tr, h_cols))
        st.caption("⚠️ = 樣本數 < 5筆，數字僅供參考")

        # ── 表F、年度明細共用門檻選單 ──
        thr_choice_f = st.selectbox(
            "選擇觸發門檻",
            [str(t) + "%" for t in THRESHOLDS],
            index=THRESHOLDS.index(thr_val) if thr_val in THRESHOLDS else 2,
            key="thr_f_yearly"
        )
        thr_val_f = int(thr_choice_f.replace("%", ""))

        st.markdown("### 表F：最大回撤分析（門檻 " + thr_choice_f + "）")
        st.caption("意義：進場後股價會先跌到低點再反彈。「平均回撤發生於第幾天」= 最低點平均在進場後第幾天出現，代表你需要撐過這段浮虧期。")
        df_dd_enhanced = build_dd_timing_table(prices, thr_val_f)
        if df_dd_enhanced is not None:
            if "平均回撤發生於第幾天" in df_dd_enhanced.columns:
                df_dd_enhanced["平均回撤發生於第幾天"] = df_dd_enhanced["平均回撤發生於第幾天"].apply(
                    lambda x: str(int(float(str(x).replace("天","").replace("無回撤","0")))) + "天"
                    if str(x) not in ["待觀察","---","無回撤"] else x
                )
            show_html(df_dd_enhanced.style.map(color_dd, subset=["平均最大回撤%", "最深回撤%"]))

        st.info(
            "計算邏輯：勝率與報酬均以 T+N 那天收盤價計算｜"
            "年度歸屬以觸發當天為準｜待觀察：觸發後未滿觀察天數，不計入統計"
        )

        df_yearly, result_yr = build_yearly_table(prices, thr_val_f)
        if df_yearly is not None:
            st.markdown("### 年度明細 A：每年平均單次報酬%（門檻 " + thr_choice_f + "）")
            st.caption("每年各筆報酬率算術平均。★ = 該年報酬最高的持有天數（反白標記）。")
            yr_cols = [str(h) + "天平均%" for h in HORIZONS]

            def _mark_best_per_row(df, cols):
                """每行找最高正報酬格，在該格文字前加 ★ 反白標記"""
                df_out = df.copy()
                for idx in df_out.index:
                    best_col, best_val = None, None
                    for c in cols:
                        try:
                            v = float(str(df_out.at[idx, c]).replace("%","").replace("待觀察","").replace("---","").strip())
                            if best_val is None or v > best_val:
                                best_val, best_col = v, c
                        except Exception:
                            pass
                    if best_col and best_val is not None and best_val > 0:
                        orig = str(df_out.at[idx, best_col])
                        df_out.at[idx, best_col] = "★ " + orig
                return df_out

            def _style_best_star(val):
                """把含 ★ 的格子變深色背景白字"""
                if isinstance(val, str) and val.startswith("★ "):
                    return "background-color:#003781;color:#fff;font-weight:700"
                return ""

            df_yr_marked = _mark_best_per_row(df_yearly, yr_cols)
            styled_a = heatmap_positive(df_yr_marked, yr_cols)
            styled_a = styled_a.map(_style_best_star)
            show_html(styled_a)

            df_yearly_cum = build_yearly_cumulative_table(prices, thr_val_f)
            if df_yearly_cum is not None:
                st.markdown("### 年度明細 B：每年實際累積損益%（門檻 " + thr_choice_f + "，按股價進場）")
                st.caption("每年 Σ(出場價-進場價)/Σ進場價 × 100。★ = 該年累積損益最高的持有天數（反白標記）。")
                yr_cum_cols = [str(h) + "天累積%" for h in HORIZONS]

                df_cum_marked = _mark_best_per_row(df_yearly_cum, yr_cum_cols)
                styled_b = heatmap_positive(df_cum_marked, yr_cum_cols)
                styled_b = styled_b.map(_style_best_star)
                show_html(styled_b)

        st.markdown("### 連續觸發分析")
        st.caption("第1天：首次觸發｜第2天：連跌第2天｜第3天：連跌第3天｜第4天以後：持續下跌")

        thr_choice_consec = st.selectbox(
            "選擇觸發門檻",
            [str(t) + "%" for t in THRESHOLDS],
            index=THRESHOLDS.index(thr_val) if thr_val in THRESHOLDS else 2,
            key="thr_consec"
        )
        thr_val_consec = int(thr_choice_consec.replace("%", ""))

        consec_groups = ["第1天", "第2天", "第3天", "第4天以後"]
        consec_matrix_wr  = {"連續觸發天數": consec_groups}
        consec_matrix_ret = {"連續觸發天數": consec_groups}

        for h in HORIZONS:
            df_c = build_consec_analysis(prices, thr_val_consec, h)
            wr_col = []; ret_col = []
            for g in consec_groups:
                if df_c is not None and g in df_c["連續觸發天數"].values:
                    row_c = df_c[df_c["連續觸發天數"] == g].iloc[0]
                    n = int(row_c.get("樣本數", 0))
                    flag = "⚠️" if n < 5 else ""
                    wr_col.append(str(row_c.get("勝率", "---")) + flag)
                    ret_col.append(str(row_c.get("平均報酬%", "---")) + flag)
                else:
                    wr_col.append("---"); ret_col.append("---")
            consec_matrix_wr[str(h)  + "天"] = wr_col
            consec_matrix_ret[str(h) + "天"] = ret_col

        h_cols = [str(h) + "天" for h in HORIZONS]
        df_cwr = pd.DataFrame(consec_matrix_wr)
        df_cret = pd.DataFrame(consec_matrix_ret)

        st.markdown("**勝率（橘色 = 歷史勝率 ≥ 80%）**")
        show_html(pd.DataFrame(consec_matrix_wr).style.map(color_winrate_80only, subset=h_cols))
        st.markdown("**平均報酬%**")
        show_html(heatmap_positive(df_cret, h_cols))
        st.caption("⚠️ = 樣本數 < 5筆")

        # 股價走勢圖用主要門檻的 result
        result = run_full_backtest(prices, thr_val)
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
        best_cum_ret_c = None   # 表C：按股價進場累積損益
        best_cum_ret_d = None   # 表D：等金額累積損益

        for h in HORIZONS:
            items_h = result["horizon_rets"][h] if result else []
            rets_h = [x["ret"] for x in items_h]
            if len(rets_h) >= 5:
                wr_h = sum(1 for r in rets_h if r > 0) / len(rets_h) * 100
                avg_h = sum(rets_h) / len(rets_h)
                if wr_h > best_wr_val or (wr_h == best_wr_val and avg_h > best_avg_ret):
                    best_wr_val = wr_h
                    best_avg_ret = avg_h
                    best_h_suggestion = h
                    # 表C：按股價進場
                    total_entry  = sum(x["entry_price"]  for x in items_h)
                    total_future = sum(x["future_price"] for x in items_h)
                    best_cum_ret_c = round((total_future - total_entry) / total_entry * 100, 2) if total_entry > 0 else None
                    # 表D：等金額
                    best_cum_ret_d = round(sum(rets_h), 2)

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

        # 體質分數：優先從 pool 取，fallback 用即時 yfinance 評分
        q_score_bt = None
        df_pool_now2 = st.session_state.get('df_pool', None)
        if df_pool_now2 is not None and not df_pool_now2.empty:
            df_pool_now2['代碼'] = df_pool_now2['代碼'].astype(str).str.strip()
            pr2 = df_pool_now2[df_pool_now2['代碼'] == single_code.strip()]
            if not pr2.empty:
                _raw_score = pr2.iloc[0].get('體質分數')
                try:
                    import math as _m
                    _sa = int(pr2.iloc[0].get('▶A獲利(0-5)', 0) or 0)
                    _sb = int(pr2.iloc[0].get('▶B護城河(0-5)', 0) or 0)
                    _sc = int(pr2.iloc[0].get('▶C安全邊際(0-5)', 0) or 0)
                    q_score_bt = float(_raw_score) if (_raw_score is not None and not _m.isnan(float(_raw_score))) else (_sa + _sb + _sc)
                except Exception:
                    q_score_bt = None

        # 若 pool 沒有，用即時 yfinance 計算
        if q_score_bt is None or not isinstance(q_score_bt, (int, float)):
            try:
                fin_bt = get_fin_data_yfinance(single_code.strip())
                eps_h = fin_bt.get('eps_history', {})
                valid_yrs_bt = sorted([y for y in eps_h if eps_h[y] is not None], reverse=True)
                q_instant = calc_quality_score_v2(
                    single_code.strip(), {'type': '個股'},
                    fin_bt.get('roe'), fin_bt.get('debt_ratio'),
                    fin_bt.get('bvps'), fin_bt.get('price'), fin_bt.get('pb'),
                    eps_h, valid_yrs_bt
                )
                if q_instant:
                    q_score_bt = q_instant['total']
            except Exception:
                pass

        # ══════════════════════════════════════════════════════
        # 操作結論
        # ══════════════════════════════════════════════════════
        st.markdown("---")
        st.markdown(_tab_icon("icon-ai", "操作結論", "市場環境 · 個股體質 · 建議觸發門檻 · 建議持有天數"), unsafe_allow_html=True)

        # ── 收集所有需要的數據 ──
        twii_now = get_twii_heat()
        market_level = twii_now["level"] if twii_now else 6
        market_label = twii_now["label"] if twii_now else "未知"

        q_score_bt = None
        q_grade_bt = ""
        df_pool_now2 = st.session_state.get('df_pool', None)
        if df_pool_now2 is not None and not df_pool_now2.empty:
            df_pool_now2['代碼'] = df_pool_now2['代碼'].astype(str).str.strip()
            pr2 = df_pool_now2[df_pool_now2['代碼'] == single_code.strip()]
            if not pr2.empty:
                _raw_score2 = pr2.iloc[0].get('體質分數')
                try:
                    import math as _m2
                    _sa2 = int(pr2.iloc[0].get('▶A獲利(0-5)', 0) or 0)
                    _sb2 = int(pr2.iloc[0].get('▶B護城河(0-5)', 0) or 0)
                    _sc2 = int(pr2.iloc[0].get('▶C安全邊際(0-5)', 0) or 0)
                    q_score_bt = float(_raw_score2) if (_raw_score2 is not None and not _m2.isnan(float(_raw_score2))) else (_sa2 + _sb2 + _sc2)
                except Exception:
                    q_score_bt = None
                q_grade_bt = pr2.iloc[0].get('體質等級', '')
                if not q_grade_bt and q_score_bt is not None:
                    q_grade_bt = "核心標的" if q_score_bt >= 13 else ("可觀察" if q_score_bt >= 9 else "高風險")

        if q_score_bt is None or not isinstance(q_score_bt, (int, float)):
            try:
                fin_bt = get_fin_data_yfinance(single_code.strip())
                eps_h = fin_bt.get('eps_history', {})
                valid_yrs_bt = sorted([y for y in eps_h if eps_h[y] is not None], reverse=True)
                q_inst = calc_quality_score_v2(
                    single_code.strip(), {'type': '個股'},
                    fin_bt.get('roe'), fin_bt.get('debt_ratio'),
                    fin_bt.get('bvps'), fin_bt.get('price'), fin_bt.get('pb'),
                    eps_h, valid_yrs_bt
                )
                if q_inst:
                    q_score_bt = q_inst['total']
                    q_grade_bt = q_inst['grade']
            except Exception:
                pass

        best_h_suggestion = None
        best_wr_val = 0
        best_avg_ret = 0
        best_cum_ret_c = None
        best_cum_ret_d = None
        for h in HORIZONS:
            items_h = result["horizon_rets"][h] if result else []
            rets_h = [x["ret"] for x in items_h]
            if len(rets_h) >= 5:
                wr_h = sum(1 for r in rets_h if r > 0) / len(rets_h) * 100
                avg_h = sum(rets_h) / len(rets_h)
                if wr_h > best_wr_val or (wr_h == best_wr_val and avg_h > best_avg_ret):
                    best_wr_val = wr_h
                    best_avg_ret = avg_h
                    best_h_suggestion = h
                    total_entry  = sum(x["entry_price"]  for x in items_h)
                    total_future = sum(x["future_price"] for x in items_h)
                    best_cum_ret_c = round((total_future - total_entry) / total_entry * 100, 2) if total_entry > 0 else None
                    best_cum_ret_d = round(sum(rets_h), 2)

        dd_ref = build_dd_timing_table(prices, thr_val)
        avg_dd_day = None
        worst_dd_val = None
        if dd_ref is not None and best_h_suggestion:
            row_dd = dd_ref[dd_ref['觀察天數'] == str(best_h_suggestion) + '天']
            if not row_dd.empty:
                try:
                    avg_dd_day = float(str(row_dd.iloc[0].get('平均回撤發生於第幾天','')).replace('天','').replace('無回撤','0'))
                except Exception:
                    pass
                try:
                    worst_dd_val = float(str(row_dd.iloc[0].get('最深回撤%','0')).replace('%',''))
                except Exception:
                    pass

        def get_thr_label(n):
            if n >= 30:   return "統計可靠（≥30筆）"
            elif n >= 15: return "尚可參考（15-29筆）"
            elif n >= 5:  return "樣本偏少（5-14筆）"
            else:         return "不具統計意義（<5筆）"

        thr_ranking = []
        for _, row in df_win.iterrows():
            thr_s = row["觸發門檻"]
            samples = int(row.get("樣本數", 0))
            try:
                wr_v = float(str(row.get("100天勝率","0%")).replace("%",""))
                avg_arr = df_avg[df_avg["觸發門檻"] == thr_s]["100天平均報酬%"].values
                avg_v = float(str(avg_arr[0]).replace("%","")) if len(avg_arr) > 0 and str(avg_arr[0]) not in ["待觀察","---"] else 0
                reliability = 1.0 if samples >= 30 else (0.8 if samples >= 15 else (0.5 if samples >= 5 else 0.0))
                score_t = (wr_v * 0.6 + avg_v * 0.4) * reliability
                thr_ranking.append((thr_s, samples, wr_v, avg_v, score_t, get_thr_label(samples)))
            except Exception:
                pass
        thr_ranking.sort(key=lambda x: x[4], reverse=True)
        valid_thrs = [t for t in thr_ranking if t[1] >= 5]
        first_thr  = valid_thrs[0] if valid_thrs else None
        second_thr = valid_thrs[1] if len(valid_thrs) > 1 else None
        skipped_thrs = [t for t in thr_ranking if t[1] < 5 and first_thr and t[2] > first_thr[2]]

        # ── 結論 1：市場環境 ──
        st.markdown("### 結論 1　市場環境")
        if market_level >= 9:
            bg1 = st.error
            market_verdict = "台股市場熱度 **第 {} 級**（**{}**）。歷史上此熱度觸發往往是趨勢性下跌的開始，而非短暫超跌。**建議暫停進場**，等熱度降至 **7 級**以下再評估。".format(market_level, market_label)
        elif market_level >= 8:
            bg1 = st.warning
            market_verdict = "台股市場熱度 **第 {} 級**（偏熱）。可進場但需提高門檻至 **-15%** 以上，等更深超跌再進。".format(market_level)
        elif market_level >= 6:
            bg1 = st.info
            market_verdict = "台股市場熱度 **第 {} 級**（{}）。市場偏熱但尚未極端，觸發信號可正常參考。".format(market_level, market_label)
        else:
            bg1 = st.success
            market_verdict = "台股市場熱度 **第 {} 級**（{}）。市場環境正常，策略可正常執行。".format(market_level, market_label)
        bg1(market_verdict)

        # ── 結論 2：個股體質 ──
        st.markdown("### 結論 2　個股體質（{}）".format(single_code))
        if q_score_bt is not None and isinstance(q_score_bt, (int, float)):
            score_int = int(q_score_bt)
            if score_int >= 13:
                bg2 = st.success
                q_verdict = "體質評分 **{}/15 分**（**{}**）。ROE、獲利穩定性、安全邊際均表現優秀，屬於「好公司短暫跌」的進場機會。".format(score_int, q_grade_bt)
            elif score_int >= 9:
                bg2 = st.info
                q_verdict = "體質評分 **{}/15 分**（**{}**）。基本面尚可，非核心持股型，進場後需更嚴格監控。".format(score_int, q_grade_bt)
            else:
                bg2 = st.warning
                q_verdict = "體質評分 **{}/15 分**（**{}**）。基本面偏弱，需確認是短暫超跌而非基本面惡化導致的下跌。".format(score_int, q_grade_bt)
            bg2(q_verdict)
        else:
            st.info("體質資料不足，建議至合格標的池建立完整評分後再參考。")

        # ── 結論 3：建議觸發門檻 ──
        st.markdown("### 結論 3　建議觸發門檻")
        if first_thr:
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                st.markdown("""
<div style="background:#f8f9fa;border-radius:8px;border:0.5px solid #e0e0e0;padding:14px 18px">
<div style="font-size:13px;color:#0F6E56;font-weight:600;margin-bottom:6px">首選　{t0}</div>
<div style="font-size:13px;color:#003781">15年觸發 <strong>{t1}筆</strong>　{t5}</div>
<div style="font-size:14px;color:#003781;margin-top:5px">100天勝率 <strong>{t2:.1f}%</strong>　平均報酬 <strong>{t3:.1f}%</strong></div>
</div>""".format(t0=first_thr[0], t1=first_thr[1], t5=first_thr[5],
                t2=first_thr[2], t3=first_thr[3]), unsafe_allow_html=True)
            with col_t2:
                if second_thr:
                    st.markdown("""
<div style="background:#f8f9fa;border-radius:8px;border:0.5px solid #e0e0e0;padding:14px 18px">
<div style="font-size:13px;color:#185FA5;font-weight:600;margin-bottom:6px">次選　{t0}</div>
<div style="font-size:13px;color:#003781">15年觸發 <strong>{t1}筆</strong>　{t5}</div>
<div style="font-size:14px;color:#003781;margin-top:5px">100天勝率 <strong>{t2:.1f}%</strong>　平均報酬 <strong>{t3:.1f}%</strong></div>
{cmp}
</div>""".format(t0=second_thr[0], t1=second_thr[1], t5=second_thr[5],
                t2=second_thr[2], t3=second_thr[3],
                cmp='<div style="font-size:13px;color:#888;margin-top:6px">次選勝率較高（{:.1f}% vs {:.1f}%），但觸發機會較少（{}筆 vs {}筆）</div>'.format(
                    second_thr[2], first_thr[2], second_thr[1], first_thr[1])
                if second_thr[2] > first_thr[2] else ""), unsafe_allow_html=True)
                else:
                    st.markdown("""
<div style="background:#f8f9fa;border-radius:8px;border:0.5px solid #e0e0e0;padding:14px 18px">
<div style="font-size:13px;color:#888;margin-bottom:6px">次選</div>
<div style="font-size:13px;color:#888">其餘門檻樣本不足 5 筆，不採用</div>
</div>""", unsafe_allow_html=True)
            for sk in skipped_thrs:
                st.caption("{} 理論勝率 {:.1f}% 最高，但僅 {}筆（< 5 筆不採用）".format(sk[0], sk[2], sk[1]))
            st.caption("樣本標準：≥30筆可靠　15–29筆尚可　5–14筆偏少　<5筆不採用")

        # ── 結論 4：建議持有天數 ──
        st.markdown("### 結論 4　建議持有天數")
        if best_h_suggestion:
            col_h1, col_h2 = st.columns(2)
            with col_h1:
                cum_c_str = "{:.1f}%".format(best_cum_ret_c) if best_cum_ret_c is not None else "—"
                cum_d_str = "{:.1f}%".format(best_cum_ret_d) if best_cum_ret_d is not None else "—"
                st.markdown("""
<div style="background:#f8f9fa;border-radius:8px;border:0.5px solid #e0e0e0;padding:14px 18px">
<div style="font-size:13px;color:#0F6E56;font-weight:600;margin-bottom:6px">建議持有　{h} 天</div>
<div style="font-size:13px;color:#003781">歷史勝率　<strong>{wr:.1f}%</strong></div>
<div style="font-size:14px;color:#003781;margin-top:5px">平均單次報酬　<strong>{avg:.1f}%</strong></div>
<div style="font-size:14px;color:#003781;margin-top:5px">15年累積損益（按股數）　<strong>{cc}</strong></div>
<div style="font-size:14px;color:#003781;margin-top:5px">15年累積損益（等金額）　<strong>{cd}</strong></div>
</div>""".format(h=best_h_suggestion, wr=best_wr_val, avg=best_avg_ret,
                cc=cum_c_str, cd=cum_d_str), unsafe_allow_html=True)
            with col_h2:
                if avg_dd_day and worst_dd_val:
                    st.markdown("""
<div style="background:#f8f9fa;border-radius:8px;border:0.5px solid #e0e0e0;padding:14px 18px">
<div style="font-size:13px;color:#F86200;font-weight:600;margin-bottom:6px">最大回撤參考</div>
<div style="font-size:13px;color:#003781">歷史最深單筆回撤　<strong>{wd:.1f}%</strong></div>
<div style="font-size:14px;color:#003781;margin-top:5px">平均最低點出現於進場後第　<strong>{dd:.0f} 天</strong></div>
<div style="font-size:14px;color:#414141;margin-top:5px">進場後第 <strong>{dd:.0f} 天</strong>若浮虧仍超過 <strong>{lim:.1f}%</strong>，可評估是否停損</div>
<div style="font-size:13px;color:#888;margin-top:6px">注意：歷史數據顯示忍住浮虧的整體報酬通常優於停損</div>
</div>""".format(wd=worst_dd_val, dd=avg_dd_day, lim=abs(worst_dd_val) * 0.8), unsafe_allow_html=True)

        # ── 綜合決策 ──
        st.markdown("### 綜合決策")

        level = market_level
        heat_bars = ""
        for i in range(1, 11):
            if i <= level:
                if i <= 4:   heat_bars += "🟢"
                elif i <= 7: heat_bars += "🟡"
                elif i <= 9: heat_bars += "🟠"
                else:        heat_bars += "🔴"
            else:
                heat_bars += "⬜"

        if level >= 9:
            market_color = "#b71c1c"; market_advice = "建議暫停進場，等熱度降至7級以下"
        elif level >= 8:
            market_color = "#e65100"; market_advice = "偏熱，建議提高觸發門檻至-15%"
        elif level >= 6:
            market_color = "#f57f17"; market_advice = "輕微偏熱，正常操作但勿追高"
        else:
            market_color = "#1b5e20"; market_advice = "環境合理，策略可正常執行"

        st.markdown("""
<div style="background:#f8f9fa;border-left:5px solid {color};padding:14px 18px;border-radius:6px;margin-bottom:16px">
<div style="font-size:13px;color:#555;margin-bottom:4px">台股市場熱度</div>
<div style="font-size:22px;letter-spacing:2px;margin-bottom:6px">{bars}</div>
<div style="font-size:15px;font-weight:600;color:{color}">第 {level} 級／10　{label}</div>
<div style="font-size:13px;color:#444;margin-top:4px">{advice}</div>
</div>""".format(color=market_color, bars=heat_bars, level=level,
                 label=market_label, advice=market_advice), unsafe_allow_html=True)

        q_val2 = int(q_score_bt) if q_score_bt is not None and isinstance(q_score_bt, (int, float)) else None
        q_pct2 = round(q_val2 / 15 * 100) if q_val2 is not None else 0
        q_color2 = "#1b5e20" if (q_val2 and q_val2 >= 13) else ("#e65100" if (q_val2 and q_val2 >= 9) else "#b71c1c")
        w_color2 = "#1b5e20" if best_wr_val >= 80 else ("#e65100" if best_wr_val >= 65 else "#b71c1c")
        wr_label2 = "優秀" if best_wr_val >= 80 else ("良好" if best_wr_val >= 65 else "偏低")

        if level >= 9:
            f_color = "#b71c1c"; f_advice = "暫停進場"; f_reason = "市場第{}級過熱".format(level)
        elif q_val2 and q_val2 >= 9 and best_wr_val >= 75:
            f_color = "#1b5e20"; f_advice = "可以進場"; f_reason = "體質合格且勝率優秀"
        elif q_val2 and q_val2 >= 9 and best_wr_val >= 60:
            f_color = "#2e7d32"; f_advice = "謹慎進場"; f_reason = "體質合格，勝率尚可"
        elif best_wr_val >= 75:
            f_color = "#e65100"; f_advice = "留意體質"; f_reason = "勝率高但體質偏弱"
        else:
            f_color = "#b71c1c"; f_advice = "建議觀望"; f_reason = "條件不足"

        col_q2, col_w2, col_final2 = st.columns(3)
        with col_q2:
            st.markdown("""
<div style="background:#f8f9fa;border-radius:8px;border:0.5px solid #e0e0e0;padding:16px;text-align:center">
<div style="font-size:13px;color:#888;margin-bottom:8px">個股體質</div>
<div style="background:#e0e0e0;border-radius:4px;height:5px;margin-bottom:10px">
  <div style="background:{c};border-radius:4px;height:5px;width:{p}%"></div>
</div>
<div style="font-size:28px;font-weight:700;color:{c}">{s}<span style="font-size:13px;color:#888;font-weight:400"> / 15分</span></div>
<div style="font-size:12px;color:{c};margin-top:5px">{g}</div>
</div>""".format(c=q_color2, p=q_pct2, s=q_val2 if q_val2 else "—",
                g=q_grade_bt if q_grade_bt else "未評分"), unsafe_allow_html=True)

        with col_w2:
            st.markdown("""
<div style="background:#f8f9fa;border-radius:8px;border:0.5px solid #e0e0e0;padding:16px;text-align:center">
<div style="font-size:13px;color:#888;margin-bottom:8px">歷史勝率（持有{d}天）</div>
<div style="background:#e0e0e0;border-radius:4px;height:5px;margin-bottom:10px">
  <div style="background:{c};border-radius:4px;height:5px;width:{p}%"></div>
</div>
<div style="font-size:28px;font-weight:700;color:{c}">{w}<span style="font-size:13px;color:#888;font-weight:400">%</span></div>
<div style="font-size:12px;color:{c};margin-top:5px">{lb}</div>
</div>""".format(c=w_color2, p=min(best_wr_val, 100), d=best_h_suggestion or "—",
                w="{:.1f}".format(best_wr_val), lb=wr_label2), unsafe_allow_html=True)

        with col_final2:
            st.markdown("""
<div style="background:#f8f9fa;border-radius:8px;border:2px solid {c};padding:16px;text-align:center">
<div style="font-size:13px;color:#888;margin-bottom:12px">綜合建議</div>
<div style="font-size:24px;font-weight:700;color:{c};margin-bottom:6px">{a}</div>
<div style="font-size:12px;color:#666">{r}</div>
</div>""".format(c=f_color, a=f_advice, r=f_reason), unsafe_allow_html=True)

        st.caption("市場熱度為獨立警示，不納入評分　｜　本分析基於歷史回測數據自動生成，不構成投資建議")

        # ── ④ 15分滿分標的清單入口 ──
        st.markdown("---")
        st.markdown("""
<div style="background:#f8f9fa;border-radius:8px;border:0.5px solid #e0e0e0;padding:12px 18px;display:flex;align-items:center;gap:14px">
  <div style="font-size:20px">📋</div>
  <div>
    <div style="font-size:13px;font-weight:600;color:#003781;margin-bottom:2px">尋找 15/15 滿分或高分標的？</div>
    <div style="font-size:14px;color:#414141">前往【<strong>合格標的池</strong>】頁籤 → 建立完整評分庫後，在「體質分數排行」中篩選 ≥13分（A級）或 15分（滿分）的標的清單。</div>
    <div style="font-size:13px;color:#888;margin-top:2px">注意：合格標的池顯示的是「體質合格」清單，不代表目前已觸發進場信號。觸發信號請至【每日警示掃描】頁籤確認。</div>
  </div>
</div>""", unsafe_allow_html=True)

        # ── ②整合：詳細分析報告（不再是獨立按鈕區塊，直接展開）──
        st.markdown("---")
        st.markdown("### 詳細回測分析報告")
        st.caption("以下為完整的七段式分析——觸發門檻、持有天數、歷史規律、風險提示、進場時機、綜合建議、出場策略")

        # HTML 報告下載按鈕（下載後在瀏覽器開啟，可完整 Ctrl+P 存PDF）
        try:
            _twii_pdf = get_twii_heat()
            _ml_pdf = _twii_pdf["level"] if _twii_pdf else None
            _qs_pdf = st.session_state.get('df_pool', None)
            _qscore = None; _qgrade = ""
            if _qs_pdf is not None and not _qs_pdf.empty:
                _pr = _qs_pdf[_qs_pdf['代碼'].astype(str).str.strip() == single_code.strip()]
                if not _pr.empty:
                    _qscore = _pr.iloc[0].get('體質分數')
                    _qgrade = _pr.iloc[0].get('體質等級', '')
            html_bytes = generate_pdf_backtest(
                single_code, prices, df_win, df_avg, df_dd, df_yearly, thr_val,
                q_score=_qscore, q_grade=_qgrade, market_level=_ml_pdf)
            st.download_button(
                "📄 下載完整分析報告 HTML（開啟後 Ctrl+P 可存PDF）",
                html_bytes,
                "回測分析_{}_{}.html".format(single_code, datetime.now().strftime("%Y%m%d")),
                "text/html", key="dl_backtest_html"
            )
        except Exception:
            pass

        render_analysis(single_code, df_win, df_avg, df_dd, df_yearly, thr_val, prices_dict=prices)

        # 報告末尾列印按鈕

        # 報告末尾再放一個列印按鈕（讀完不用滾回頂部）

# ==============================
# TAB 4: 全市場勝率排行
# ==============================
with tab4:
    st.markdown(_tab_icon("icon-trophy", "全市場勝率排行", "各門檻前10名 · 多門檻交叉比較"), unsafe_allow_html=True)
    st.caption("📄 PDF說明：請用下方「下載HTML報告」按鈕，下載後在瀏覽器直接開啟，再按 Ctrl+P 存成PDF（完整輸出，不受 iframe 限制）")

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
        # 排序：各標的在所有門檻裡的「最佳勝率」高→低
        # 避免單一門檻偏見（有些標的 -15% 勝率極高但 -10% 普通）
        def _best_wr(row):
            best = 0
            for col in thr_cols:
                v = str(row.get(col, "0")).replace("%","").replace("⚠️","")
                try:
                    best = max(best, float(v))
                except Exception:
                    pass
            return best
        thr_cols_for_sort = [str(thr) + "%" for thr in THRESHOLDS]
        df_combined["_best_wr"] = df_combined.apply(
            lambda r: _best_wr(r) if set(thr_cols_for_sort).issubset(df_combined.columns) else 0,
            axis=1
        )
        df_combined = df_combined.sort_values("_best_wr", ascending=False).drop(
            columns=["_best_wr"]).reset_index(drop=True)

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
            "依「最佳門檻勝率」高→低排序（取各門檻最高值），避免單一門檻偏見｜橫向看同一檔在各門檻的穩定性"
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


# ==============================
# TAB: 每日市場簡報
# ==============================

# ── 免費資料抓取函數 ──────────────────────────────────────

@st.cache_data(ttl=900)
def _brief_get_premarket():
    """
    第一區：盤前快訊
    資料源：Yahoo Finance（yfinance）- 免費、無需API key
    tickers: TSM ADR、NVDA ADR、費半SOX、台指期夜盤、美元指數、美債10年、VIX
    回傳 dict: { ticker_key: {name, val, chg_pct, signal, signal_color} }
    """
    import yfinance as yf
    TICKERS = [
        ("TSM",    "台積電 ADR",       "半導體",  "tsm"),
        ("NVDA",   "輝達 NVDA",        "半導體",  "nvda"),
        ("AMD",    "超微 AMD",         "半導體",  "amd"),
        ("AVGO",   "博通 AVGO",        "半導體",  "avgo"),
        ("^SOX",   "費半指數 SOX",     "指數",    "sox"),
        ("^GSPC",  "S&P 500",          "指數",    "sp500"),
        ("0050.TW","台灣大盤（ETF代理）","台股",  "txf"),  # 台指期 yfinance 無穩定 ticker，用0050代理走勢
        ("DX-Y.NYB","美元指數 DXY",    "匯率",    "dxy"),
        ("^TNX",   "美債10年殖利率",   "債券",    "tnx"),
        ("^VIX",   "VIX 恐慌指數",     "風險",    "vix"),
    ]
    result = {}
    for ticker, name, category, key in TICKERS:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d", interval="1d")
            if hist.empty or len(hist) < 2:
                result[key] = {"name": name, "category": category, "val": None,
                               "chg_pct": None, "signal": "資料不足", "color": "#888"}
                continue
            latest = float(hist["Close"].iloc[-1])
            prev   = float(hist["Close"].iloc[-2])
            chg_pct = (latest - prev) / prev * 100

            # 信號判斷
            if key == "vix":
                if latest > 30:
                    sig, col = "⚠️ 極度恐慌（>30），市場高度不確定", "#A32D2D"
                elif latest > 20:
                    sig, col = "🟡 恐慌升溫（20-30），波動加大", "#F86200"
                else:
                    sig, col = "🟢 市場平靜（<20），風險偏好正常", "#0F6E56"
            elif key == "tnx":
                if chg_pct > 2:
                    sig, col = "🔴 殖利率快速上升，科技股估值承壓", "#A32D2D"
                elif chg_pct < -2:
                    sig, col = "🟢 殖利率下行，有利成長股估值", "#0F6E56"
                else:
                    sig, col = "⚪ 殖利率變化平穩，影響中性", "#888"
            elif key == "dxy":
                if chg_pct > 0.5:
                    sig, col = "🟡 美元走強，外資匯出壓力偏大", "#F86200"
                elif chg_pct < -0.5:
                    sig, col = "🟢 美元走弱，台幣升值利多外資留台", "#0F6E56"
                else:
                    sig, col = "⚪ 美元持穩，匯率影響中性", "#888"
            elif key == "txf":
                if chg_pct > 0.5:
                    sig, col = "🟢 台指期夜盤偏多，今日開盤預估強勢", "#0F6E56"
                elif chg_pct < -0.5:
                    sig, col = "🔴 台指期夜盤偏空，今日開盤預估弱勢", "#A32D2D"
                else:
                    sig, col = "⚪ 台指期夜盤持平，開盤方向未定", "#888"
            elif key in ("tsm", "nvda", "amd", "avgo"):
                if chg_pct > 2:
                    sig, col = "🟢 強勢大漲，供應鏈族群今日看漲", "#0F6E56"
                elif chg_pct > 0:
                    sig, col = "🟢 小幅上漲，偏多", "#0F6E56"
                elif chg_pct > -2:
                    sig, col = "🔴 小幅下跌，偏空", "#A32D2D"
                else:
                    sig, col = "🔴 明顯下跌，供應鏈族群今日承壓", "#A32D2D"
            else:
                if chg_pct > 0.5:
                    sig, col = "🟢 上漲", "#0F6E56"
                elif chg_pct < -0.5:
                    sig, col = "🔴 下跌", "#A32D2D"
                else:
                    sig, col = "⚪ 持平", "#888"

            # 格式化顯示值
            if key == "tnx":
                val_str = "{:.2f}%".format(latest)
            elif key in ("dxy",):
                val_str = "{:.2f}".format(latest)
            elif key == "txf":
                val_str = "{:,.0f}".format(latest)
            else:
                val_str = "{:,.2f}".format(latest)

            result[key] = {
                "name": name, "category": category,
                "val": val_str,
                "chg_pct": round(chg_pct, 2),
                "signal": sig, "color": col,
            }
        except Exception as e:
            result[key] = {"name": name, "category": category, "val": "—",
                           "chg_pct": None, "signal": "抓取失敗", "color": "#888"}
    return result


@st.cache_data(ttl=3600)
def _brief_get_foreign_net():
    """
    外資買賣超（TWSE OpenAPI）
    資料源：https://openapi.twse.com.tw - 官方免費API
    回傳 dict: {date, net_buy_b (億元), consecutive_days, direction}
    """
    try:
        url = "https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN"
        # 改用三大法人買賣超
        url2 = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_d"
        # 實際用三大法人總計
        url3 = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_t00.tw"
        # 最可靠：TWSE t86（三大法人）
        res = requests.get(
            "https://openapi.twse.com.tw/v1/exchangeReport/TWT44U",
            timeout=8, headers={"User-Agent": "Mozilla/5.0"}
        )
        if res.status_code == 200 and res.text.strip() not in ["[]", ""]:
            data = res.json()
            if data:
                latest = data[-1]
                # 外資買超金額（單位：千元）
                buy  = float(str(latest.get("外陸資買進股數","0")).replace(",",""))
                sell = float(str(latest.get("外陸資賣出股數","0")).replace(",",""))
                net  = (buy - sell) / 1e8  # 轉億股
                date_str = latest.get("日期", "")
                direction = "買超" if net > 0 else "賣超"
                return {"date": date_str, "net": round(net, 2),
                        "direction": direction, "unit": "億股"}
    except Exception:
        pass

    # 備援：簡單提示
    return {"date": "—", "net": None, "direction": "—", "unit": ""}


@st.cache_data(ttl=43200)  # 12小時快取
def _brief_get_news():
    """
    第二區：重大財經新聞
    yfinance 1.4.x 的 news 格式改為 contentType/thumbnail 結構，
    title 可能在 n["content"]["title"] 或 n["title"]，需同時兼容舊新格式。
    """
    import yfinance as yf
    import re as _re
    import html as _html_mod

    POSITIVE_KW = ["beat","surge","soar","record","upgrade","raise","raised guidance",
                   "strong demand","outperform","better than expected","bullish",
                   "優於預期","上調","創新高","強勁需求","獲利超預期"]
    NEGATIVE_KW = ["miss","slump","plunge","downgrade","cut","lower guidance",
                   "weak demand","below estimates","disappoints","warning",
                   "recall","layoffs","tariff","investigation","bearish",
                   "低於預期","下調","獲利警告","需求疲弱","裁員"]

    def classify(text):
        t = text.lower()
        pos = sum(1 for kw in POSITIVE_KW if kw.lower() in t)
        neg = sum(1 for kw in NEGATIVE_KW if kw.lower() in t)
        if pos > neg:   return "正面", "#E1F5EE", "#085041"
        elif neg > pos: return "負面", "#FEE0CC", "#993C1D"
        else:           return "中性", "#f0f0f0", "#555555"

    def try_translate(text):
        if not text: return text
        chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        if chinese / max(len(text), 1) > 0.3:
            return text
        try:
            from deep_translator import GoogleTranslator
            r = GoogleTranslator(source='auto', target='zh-TW').translate(text[:400])
            return r if r else text
        except Exception:
            pass
        try:
            from googletrans import Translator
            r = Translator().translate(text[:400], dest='zh-TW')
            return r.text if r and r.text else text
        except Exception:
            pass
        return text  # fallback：保留英文

    def strip_html(text):
        if not text: return ""
        text = _html_mod.unescape(str(text))
        text = _re.sub(r'<[^>]+>', '', text)
        return ' '.join(text.split()).strip()

    def extract_news_item(n):
        """
        兼容 yfinance 新舊格式：
        舊格式：{"title": ..., "link": ...}
        新格式：{"content": {"title": ..., "canonicalUrl": {"url": ...}}}
        """
        # 新格式（yfinance 1.4.x）
        content = n.get("content") or {}
        if isinstance(content, dict):
            title = content.get("title", "")
            url_obj = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
            url = url_obj.get("url", "") if isinstance(url_obj, dict) else ""
            if not url:
                url = content.get("url", "")
        else:
            title = ""
            url = ""

        # 舊格式 fallback
        if not title:
            title = n.get("title", "")
        if not url:
            url = n.get("link", n.get("url", ""))

        return strip_html(title), url

    news_items = []
    seen = set()

    TICKERS_NEWS = [
        ("TSM",  "台積電 ADR"),
        ("NVDA", "輝達 NVDA"),
        ("MU",   "美光 MU"),
        ("AVGO", "博通 AVGO"),
        ("AMD",  "超微 AMD"),
        ("AAPL", "蘋果 AAPL"),
        ("MSFT", "微軟 MSFT"),
    ]
    EXCLUDE_KW = ["nba", "nfl", "soccer", "football", "celebrity",
                  "music", "movie", "film", "oscar", "grammy",
                  "recipe", "weather", "horoscope"]

    for sym, sym_name in TICKERS_NEWS:
        if len(news_items) >= 14:
            break
        try:
            t = yf.Ticker(sym)
            raw_news = t.news or []
            for n in raw_news[:8]:
                title_raw, url = extract_news_item(n)
                if not title_raw or len(title_raw) < 8:
                    continue
                title_key = title_raw[:50].lower()
                if title_key in seen:
                    continue
                if any(kw in title_key for kw in EXCLUDE_KW):
                    continue
                seen.add(title_key)
                title_zh = try_translate(title_raw)
                impact, bg, fg = classify(title_raw)
                impact_zh = {"正面": "→ 台股供應鏈偏多",
                             "負面": "→ 台股供應鏈偏空",
                             "中性": "→ 影響方向待觀察"}.get(impact, "")
                news_items.append({
                    "title":   title_zh or title_raw,
                    "summary": "【{}】{}".format(sym_name, impact_zh),
                    "impact":  impact, "bg": bg, "fg": fg,
                    "source":  "Yahoo Finance / {}".format(sym_name),
                    "url":     url,
                })
        except Exception:
            continue

    # ── 備援：feedparser RSS ──
    if len(news_items) < 4:
        try:
            import feedparser
            RSS_BACKUP = [
                ("https://finance.yahoo.com/rss/headline?s=TSM",  "Yahoo Finance TSM"),
                ("https://finance.yahoo.com/rss/headline?s=NVDA", "Yahoo Finance NVDA"),
                ("https://finance.yahoo.com/rss/headline?s=MU",   "Yahoo Finance MU"),
            ]
            KEY_TOPICS = ["tsmc","nvidia","micron","semiconductor","fed","fomc",
                          "cpi","ai chip","broadcom","amd","hbm","cowos"]
            for rss_url, src_name in RSS_BACKUP:
                if len(news_items) >= 12:
                    break
                try:
                    feed = feedparser.parse(rss_url)
                    for entry in (feed.entries or [])[:10]:
                        title_raw = strip_html(entry.get("title",""))
                        if not title_raw: continue
                        if not any(kw in title_raw.lower() for kw in KEY_TOPICS): continue
                        title_key = title_raw[:50].lower()
                        if title_key in seen: continue
                        seen.add(title_key)
                        title_zh   = try_translate(title_raw)
                        summary_zh = try_translate(strip_html(entry.get("summary",""))[:200])
                        impact, bg, fg = classify(title_raw)
                        news_items.append({
                            "title": title_zh or title_raw,
                            "summary": summary_zh,
                            "impact": impact, "bg": bg, "fg": fg,
                            "source": src_name, "url": entry.get("link",""),
                        })
                except Exception:
                    continue
        except ImportError:
            pass

    # ── 最終 fallback：若完全抓不到，顯示提示訊息 ──
    if not news_items:
        news_items.append({
            "title":   "目前無法取得即時財經新聞（網路連線或 yfinance 暫時無回應）",
            "summary": "請稍後點「重新整理」按鈕，或直接前往 Yahoo Finance 查看最新資訊。",
            "impact":  "中性", "bg": "#f0f0f0", "fg": "#555",
            "source":  "系統提示", "url": "https://finance.yahoo.com",
        })

    return news_items[:14]


@st.cache_data(ttl=86400)
def _brief_get_calendar():
    """
    第三區：未來180天重大事件日曆
    策略：
      1. 內建硬編碼的已知固定事件（最可靠，不依賴外部API）
      2. Yahoo Finance earnings_dates 補充企業財報
    """
    import yfinance as yf
    from datetime import datetime, timedelta, date

    today = datetime.now().date()
    horizon = today + timedelta(days=180)  # 半年
    events = []

    HARDCODED = [
        # FOMC 會議
        (2025,  7, 30, "FOMC 利率決策會議", "聯準會利率決策＋聲明，直接影響全球資金成本與風險偏好", "美國總經", "#185FA5"),
        (2025,  9, 17, "FOMC 利率決策會議", "聯準會利率決策＋聲明，直接影響全球資金成本與風險偏好", "美國總經", "#185FA5"),
        (2025, 10, 29, "FOMC 利率決策會議", "聯準會利率決策＋聲明，直接影響全球資金成本與風險偏好", "美國總經", "#185FA5"),
        (2025, 12, 10, "FOMC 利率決策會議", "聯準會利率決策＋聲明，直接影響全球資金成本與風險偏好", "美國總經", "#185FA5"),
        (2026,  1, 28, "FOMC 利率決策會議", "聯準會利率決策＋聲明，直接影響全球資金成本與風險偏好", "美國總經", "#185FA5"),
        (2026,  3, 18, "FOMC 利率決策會議", "聯準會利率決策＋聲明，直接影響全球資金成本與風險偏好", "美國總經", "#185FA5"),
        (2026,  4, 29, "FOMC 利率決策會議", "聯準會利率決策＋聲明，直接影響全球資金成本與風險偏好", "美國總經", "#185FA5"),
        (2026,  6, 10, "FOMC 利率決策會議", "聯準會利率決策＋聲明，直接影響全球資金成本與風險偏好", "美國總經", "#185FA5"),
        (2026,  7, 29, "FOMC 利率決策會議", "聯準會利率決策＋聲明，直接影響全球資金成本與風險偏好", "美國總經", "#185FA5"),
        (2026,  9, 16, "FOMC 利率決策會議", "聯準會利率決策＋聲明，直接影響全球資金成本與風險偏好", "美國總經", "#185FA5"),
        (2026, 10, 28, "FOMC 利率決策會議", "聯準會利率決策＋聲明，直接影響全球資金成本與風險偏好", "美國總經", "#185FA5"),
        (2026, 12,  9, "FOMC 利率決策會議", "聯準會利率決策＋聲明，直接影響全球資金成本與風險偏好", "美國總經", "#185FA5"),
        # CPI
        (2025,  7, 15, "美國 CPI 通膨數據（6月）",  "Fed最關鍵通膨指標，影響降息預期與科技股估值", "美國總經", "#185FA5"),
        (2025,  8, 13, "美國 CPI 通膨數據（7月）",  "Fed最關鍵通膨指標，影響降息預期與科技股估值", "美國總經", "#185FA5"),
        (2025,  9, 11, "美國 CPI 通膨數據（8月）",  "Fed最關鍵通膨指標，影響降息預期與科技股估值", "美國總經", "#185FA5"),
        (2025, 10,  9, "美國 CPI 通膨數據（9月）",  "Fed最關鍵通膨指標，影響降息預期與科技股估值", "美國總經", "#185FA5"),
        (2025, 11, 13, "美國 CPI 通膨數據（10月）", "Fed最關鍵通膨指標，影響降息預期與科技股估值", "美國總經", "#185FA5"),
        (2025, 12, 11, "美國 CPI 通膨數據（11月）", "Fed最關鍵通膨指標，影響降息預期與科技股估值", "美國總經", "#185FA5"),
        (2026,  1, 15, "美國 CPI 通膨數據（12月）", "Fed最關鍵通膨指標，影響降息預期與科技股估值", "美國總經", "#185FA5"),
        (2026,  2, 12, "美國 CPI 通膨數據（1月）",  "Fed最關鍵通膨指標，影響降息預期與科技股估值", "美國總經", "#185FA5"),
        (2026,  3, 12, "美國 CPI 通膨數據（2月）",  "Fed最關鍵通膨指標，影響降息預期與科技股估值", "美國總經", "#185FA5"),
        (2026,  4,  9, "美國 CPI 通膨數據（3月）",  "Fed最關鍵通膨指標，影響降息預期與科技股估值", "美國總經", "#185FA5"),
        (2026,  5, 13, "美國 CPI 通膨數據（4月）",  "Fed最關鍵通膨指標，影響降息預期與科技股估值", "美國總經", "#185FA5"),
        (2026,  6, 11, "美國 CPI 通膨數據（5月）",  "Fed最關鍵通膨指標，影響降息預期與科技股估值", "美國總經", "#185FA5"),
        (2026,  7,  9, "美國 CPI 通膨數據（6月）",  "Fed最關鍵通膨指標，影響降息預期與科技股估值", "美國總經", "#185FA5"),
        (2026,  8, 12, "美國 CPI 通膨數據（7月）",  "Fed最關鍵通膨指標，影響降息預期與科技股估值", "美國總經", "#185FA5"),
        # 非農就業
        (2025,  8,  1, "美國非農就業報告（7月）",   "就業強弱影響Fed降息時程，波動大", "美國總經", "#185FA5"),
        (2025,  9,  5, "美國非農就業報告（8月）",   "就業強弱影響Fed降息時程，波動大", "美國總經", "#185FA5"),
        (2025, 10,  3, "美國非農就業報告（9月）",   "就業強弱影響Fed降息時程，波動大", "美國總經", "#185FA5"),
        (2025, 11,  7, "美國非農就業報告（10月）",  "就業強弱影響Fed降息時程，波動大", "美國總經", "#185FA5"),
        (2025, 12,  5, "美國非農就業報告（11月）",  "就業強弱影響Fed降息時程，波動大", "美國總經", "#185FA5"),
        (2026,  1,  9, "美國非農就業報告（12月）",  "就業強弱影響Fed降息時程，波動大", "美國總經", "#185FA5"),
        (2026,  2,  6, "美國非農就業報告（1月）",   "就業強弱影響Fed降息時程，波動大", "美國總經", "#185FA5"),
        (2026,  3,  6, "美國非農就業報告（2月）",   "就業強弱影響Fed降息時程，波動大", "美國總經", "#185FA5"),
        (2026,  4,  3, "美國非農就業報告（3月）",   "就業強弱影響Fed降息時程，波動大", "美國總經", "#185FA5"),
        (2026,  5,  8, "美國非農就業報告（4月）",   "就業強弱影響Fed降息時程，波動大", "美國總經", "#185FA5"),
        (2026,  6,  5, "美國非農就業報告（5月）",   "就業強弱影響Fed降息時程，波動大", "美國總經", "#185FA5"),
        # MSCI 季度調整
        (2025,  8, 15, "MSCI 季度調整生效",         "被動基金強制進出，成分股當日波動放大，留意流動性", "台股事件", "#534AB7"),
        (2025, 11, 21, "MSCI 季度調整生效",         "被動基金強制進出，成分股當日波動放大，留意流動性", "台股事件", "#534AB7"),
        (2026,  2, 27, "MSCI 季度調整生效",         "被動基金強制進出，成分股當日波動放大，留意流動性", "台股事件", "#534AB7"),
        (2026,  5, 29, "MSCI 季度調整生效",         "被動基金強制進出，成分股當日波動放大，留意流動性", "台股事件", "#534AB7"),
        # 台積電月營收
        (2025,  7, 10, "台積電月營收公告（6月）",   "每月10日前公布，是外資當日買賣超的重要參考", "台股事件", "#534AB7"),
        (2025,  8, 11, "台積電月營收公告（7月）",   "每月10日前公布，是外資當日買賣超的重要參考", "台股事件", "#534AB7"),
        (2025,  9, 10, "台積電月營收公告（8月）",   "每月10日前公布，是外資當日買賣超的重要參考", "台股事件", "#534AB7"),
        (2025, 10, 10, "台積電月營收公告（9月）",   "每月10日前公布，是外資當日買賣超的重要參考", "台股事件", "#534AB7"),
        (2025, 11, 10, "台積電月營收公告（10月）",  "每月10日前公布，是外資當日買賣超的重要參考", "台股事件", "#534AB7"),
        (2025, 12, 10, "台積電月營收公告（11月）",  "每月10日前公布，是外資當日買賣超的重要參考", "台股事件", "#534AB7"),
        (2026,  1, 10, "台積電月營收公告（12月）",  "每月10日前公布，是外資當日買賣超的重要參考", "台股事件", "#534AB7"),
        (2026,  2, 10, "台積電月營收公告（1月）",   "每月10日前公布，是外資當日買賣超的重要參考", "台股事件", "#534AB7"),
        (2026,  3, 10, "台積電月營收公告（2月）",   "每月10日前公布，是外資當日買賣超的重要參考", "台股事件", "#534AB7"),
        (2026,  4, 10, "台積電月營收公告（3月）",   "每月10日前公布，是外資當日買賣超的重要參考", "台股事件", "#534AB7"),
        (2026,  5, 11, "台積電月營收公告（4月）",   "每月10日前公布，是外資當日買賣超的重要參考", "台股事件", "#534AB7"),
        (2026,  6, 10, "台積電月營收公告（5月）",   "每月10日前公布，是外資當日買賣超的重要參考", "台股事件", "#534AB7"),
        # 台積電法說（每季）
        (2025,  7, 17, "台積電 Q2 法說會",          "CoWoS/3nm/2nm產能與ASP展望，台股最重要單一事件", "企業財報/法說", "#F86200"),
        (2025, 10, 16, "台積電 Q3 法說會",          "CoWoS/3nm/2nm產能與ASP展望，台股最重要單一事件", "企業財報/法說", "#F86200"),
        (2026,  1, 15, "台積電 Q4 法說會",          "CoWoS/3nm/2nm產能與ASP展望，台股最重要單一事件", "企業財報/法說", "#F86200"),
        (2026,  4, 16, "台積電 Q1 法說會",          "CoWoS/3nm/2nm產能與ASP展望，台股最重要單一事件", "企業財報/法說", "#F86200"),
        (2026,  7, 16, "台積電 Q2 法說會",          "CoWoS/3nm/2nm產能與ASP展望，台股最重要單一事件", "企業財報/法說", "#F86200"),
        # 輝達財報
        (2025,  8, 27, "輝達 NVDA 財報（預估）",    "GPU供給/AI需求能見度，直接影響台積電/廣達/鴻海訂單", "企業財報/法說", "#F86200"),
        (2025, 11, 20, "輝達 NVDA 財報（預估）",    "GPU供給/AI需求能見度，直接影響台積電/廣達/鴻海訂單", "企業財報/法說", "#F86200"),
        (2026,  2, 25, "輝達 NVDA 財報（預估）",    "GPU供給/AI需求能見度，直接影響台積電/廣達/鴻海訂單", "企業財報/法說", "#F86200"),
        (2026,  5, 27, "輝達 NVDA 財報（預估）",    "GPU供給/AI需求能見度，直接影響台積電/廣達/鴻海訂單", "企業財報/法說", "#F86200"),
        # 美光財報
        (2025,  9, 24, "美光 MU 財報（預估）",      "HBM/DRAM展望，影響南亞科/旺宏/台灣記憶體族群", "企業財報/法說", "#F86200"),
        (2025, 12, 17, "美光 MU 財報（預估）",      "HBM/DRAM展望，影響南亞科/旺宏/台灣記憶體族群", "企業財報/法說", "#F86200"),
        (2026,  3, 25, "美光 MU 財報（預估）",      "HBM/DRAM展望，影響南亞科/旺宏/台灣記憶體族群", "企業財報/法說", "#F86200"),
        (2026,  6, 24, "美光 MU 財報（預估）",      "HBM/DRAM展望，影響南亞科/旺宏/台灣記憶體族群", "企業財報/法說", "#F86200"),
        # 台股除息旺季
        (2025,  7,  1, "台股除息旺季開始",          "大量個股進入除息，股價除息前後波動加大，留意填息強度", "台股事件", "#534AB7"),
        (2025,  8,  1, "台股除息旺季（8月）",       "除息個股眾多，需關注填息速度與外資動向", "台股事件", "#534AB7"),
        # 聯準會 Jackson Hole 年會（每年8月）
        (2025,  8, 21, "Fed Jackson Hole 年會",     "Fed主席演講，往往釋放重大政策方向信號，市場波動大", "美國總經", "#185FA5"),
        (2026,  8, 20, "Fed Jackson Hole 年會",     "Fed主席演講，往往釋放重大政策方向信號，市場波動大", "美國總經", "#185FA5"),
    ]

    seen_ev = set()
    for yr, mo, dy, title, sub, cat, color in HARDCODED:
        try:
            dt = date(yr, mo, dy)
            if today <= dt <= horizon:
                key = "{}_{}".format(dt, title[:15])
                if key not in seen_ev:
                    seen_ev.add(key)
                    events.append({"date": dt, "title": title, "sub": sub,
                                   "category": cat, "cat_color": color})
        except Exception:
            pass

    # Yahoo Finance earnings_dates 補充實際財報日
    KEY_STOCKS = {
        "NVDA": ("輝達 NVDA 財報（確認日）", "GPU/AI需求能見度", "企業財報/法說", "#F86200"),
        "MU":   ("美光 MU 財報（確認日）",   "HBM/DRAM展望",   "企業財報/法說", "#F86200"),
        "AVGO": ("博通 AVGO 財報（確認日）", "ASIC/網路晶片",   "企業財報/法說", "#F86200"),
        "TSM":  ("台積電法說（確認日）",     "CoWoS/3nm產能展望","企業財報/法說", "#F86200"),
        "AAPL": ("蘋果 AAPL 財報（確認日）", "iPhone組裝需求",  "企業財報/法說", "#F86200"),
        "MSFT": ("微軟 MSFT 財報（確認日）", "AI雲端支出展望",  "企業財報/法說", "#F86200"),
        "GOOGL":("Google 財報（確認日）",    "AI/雲端業務展望", "企業財報/法說", "#F86200"),
        "META": ("Meta 財報（確認日）",      "廣告市場/AI投資", "企業財報/法說", "#F86200"),
    }
    for sym, (title, sub, cat, color) in KEY_STOCKS.items():
        try:
            t = yf.Ticker(sym)
            ed = t.earnings_dates
            if ed is None or ed.empty:
                continue
            for idx in ed.index:
                try:
                    dt = idx.date() if hasattr(idx, 'date') else idx
                    if today <= dt <= horizon:
                        key = "{}_{}".format(dt, title[:15])
                        if key not in seen_ev:
                            seen_ev.add(key)
                            events.append({"date": dt, "title": title, "sub": sub,
                                           "category": cat, "cat_color": color})
                except Exception:
                    pass
        except Exception:
            continue

    events.sort(key=lambda x: x["date"])
    return events


# ── Tab 主體 ──────────────────────────────────────────────

def _render_news_item(item):
    """渲染單一新聞卡片——分段 st.markdown 避免巢狀 HTML 解析問題"""
    import html as _html
    impact  = item.get("impact", "中性")
    bg      = item.get("bg",     "#f0f0f0")
    fg      = item.get("fg",     "#414141")
    title   = _html.escape(str(item.get("title",   "")))
    summary = _html.escape(str(item.get("summary", ""))).strip()
    source  = _html.escape(str(item.get("source",  "")))
    url     = item.get("url", "")
    link    = ' <a href="{}" target="_blank" style="color:#185FA5;font-size:13px">[原文]</a>'.format(url) if url else ""

    with st.container():
        st.markdown(
            '<div style="border-radius:8px;border:0.5px solid #e0e0e0;'
            'padding:12px 16px;margin-bottom:8px;background:#fff">',
            unsafe_allow_html=True)
        st.markdown(
            '<div style="display:flex;align-items:flex-start;gap:10px">'
            '<span style="flex-shrink:0;background:{bg};color:{fg};font-size:12px;'
            'font-weight:600;padding:3px 10px;border-radius:4px;margin-top:2px">{impact}</span>'
            '<span style="font-size:15px;font-weight:600;color:#003781;line-height:1.4">'
            '{title}{link}</span></div>'.format(
                bg=bg, fg=fg, impact=impact, title=title, link=link),
            unsafe_allow_html=True)
        if summary:
            st.markdown(
                '<div style="font-size:14px;color:#555;line-height:1.6;'
                'margin:6px 0 0 2px">{}</div>'.format(summary),
                unsafe_allow_html=True)
        st.markdown(
            '<div style="font-size:12px;color:#aaa;margin-top:6px">來源：{}</div>'
            '</div>'.format(source),
            unsafe_allow_html=True)


def _render_metric_card(col, data):
    """盤前快訊單格卡片"""
    name     = data.get("name", "—")
    val      = data.get("val")
    chg_pct  = data.get("chg_pct")
    signal   = data.get("signal", "—")
    sig_color= data.get("color", "#888")

    try:
        val_f   = float(val) if val not in (None, "", "—") else None
        val_str = "{:,.2f}".format(val_f) if val_f is not None else "—"
    except (TypeError, ValueError):
        val_str = str(val) if val else "—"

    try:
        chg_f   = float(chg_pct) if chg_pct not in (None, "", "—") else None
        if chg_f is not None:
            arrow   = "▲" if chg_f > 0 else ("▼" if chg_f < 0 else "●")
            chg_str = "{}{:.2f}%".format(arrow, abs(chg_f))
            chg_col = "#0F6E56" if chg_f > 0 else ("#A32D2D" if chg_f < 0 else "#888")
        else:
            chg_str = "—"; chg_col = "#888"
    except (TypeError, ValueError):
        chg_str = "—"; chg_col = "#888"

    col.markdown("""
<div style="background:#f8f9fa;border-radius:8px;border:0.5px solid #e0e0e0;padding:12px 14px">
  <div style="font-size:12px;color:#888;margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{name}</div>
  <div style="font-size:20px;font-weight:700;color:#003781">{val}</div>
  <div style="font-size:13px;color:{chgc};margin-top:2px">{chg}</div>
  <div style="font-size:12px;color:{sigc};margin-top:4px;line-height:1.4">{sig}</div>
</div>""".format(name=name, val=val_str, chgc=chg_col, chg=chg_str,
                sigc=sig_color, sig=signal), unsafe_allow_html=True)


with tab_mops:
    st.markdown(_tab_icon("icon-search", "個股風險查詢", "MOPS重大訊息 + 新聞搜尋雙層查證"), unsafe_allow_html=True)
    st.caption(
        "每日警示掃描裡的「風險偵測」欄只顯示摘要，這裡提供完整雙層查證：\n"
        "① **MOPS重大訊息**——公司法定揭露事項（資料源：TWSE OpenAPI t187ap04_L）\n"
        "② **新聞搜尋**——市場傳聞、治理危機、檢調動態等未必會發正式重訊但媒體已報導的事件（資料源：Google News）\n\n"
        "為什麼需要兩層：重大訊息只涵蓋公司主動揭露的法定事項，但像「董座無預警辭職」「經營權鬥爭」"
        "這類事件，公司不一定第一時間發重訊，新聞搜尋能補上這個盲區。"
    )

    col_mq1, col_mq2, col_mq3 = st.columns([1, 1, 2])
    with col_mq1:
        mops_query_code = st.text_input("股票代碼", placeholder="例：2233", key="mops_query_input")
    with col_mq2:
        mops_query_name = st.text_input("股票名稱（新聞搜尋用）", placeholder="例：宇隆", key="mops_query_name")
    mops_query_btn = st.button("🔍 查詢風險（MOPS + 新聞）", key="mops_query_btn", type="primary")

    if mops_query_btn and mops_query_code.strip():
        _code_q = mops_query_code.strip()
        _name_q = mops_query_name.strip() or _code_q

        with st.spinner("查詢中：MOPS重大訊息 + 新聞搜尋..."):
            mops_detail = query_mops_risk_detail(_code_q)
            news_detail = search_news_risk(_code_q, _name_q)

        st.markdown("---")

        # ── 綜合判斷橫幅 ──
        overall_danger = mops_detail["status"] == "danger" or news_detail["status"] == "danger"
        overall_warn   = mops_detail["status"] == "warning" or news_detail["status"] == "warning"
        both_failed    = mops_detail["status"] == "error" and news_detail["status"] == "error"

        if overall_danger:
            st.error("🚨 偵測到高風險訊號（MOPS和/或新聞）")
        elif overall_warn:
            st.warning("⚠️ 偵測到需留意的訊號")
        elif both_failed:
            st.error("❌ 兩個資料源都查詢失敗，本次無法判斷風險，請務必手動核實")
        else:
            st.success("✅ 兩層查詢均未偵測到風險訊號")

        # ── ① MOPS 重大訊息區塊 ──
        st.markdown("### ① MOPS 重大訊息（官方法定揭露）")
        if mops_detail["status"] == "error":
            st.warning("⚠️ {}".format(mops_detail["error"]))
            st.caption("資料源失敗，不代表「無異常」，請用下方官方連結手動核實。")
        elif mops_detail["status"] == "danger":
            st.markdown("**命中高風險關鍵字：** {}".format("、".join(mops_detail["danger_kw"])))
        elif mops_detail["status"] == "warning":
            st.markdown("**命中留意關鍵字：** {}".format("、".join(mops_detail["warn_kw"])))

        if mops_detail.get("matched_records"):
            st.markdown("**近期重大訊息記錄（共{}筆）：**".format(len(mops_detail["matched_records"])))
            for rec in mops_detail["matched_records"][:10]:
                st.markdown("- **{}** {}".format(
                    rec.get("發言日期", "—"), rec.get("主旨", "（無標題）")))
        elif mops_detail["status"] == "clean":
            st.caption("近期無重大訊息申報記錄。")

        if mops_detail.get("director_flags"):
            st.warning("📋 **董監事持股異動**：{}".format("；".join(mops_detail["director_flags"])))

        if mops_detail.get("shareholder_flags"):
            st.warning("📋 **大股東持股異動**：{}".format("；".join(mops_detail["shareholder_flags"])))

        st.markdown("🔗 [前往公開資訊觀測站查看完整記錄]({})".format(mops_detail["query_url"]))

        # ── ② 新聞搜尋區塊 ──
        st.markdown("---")
        st.markdown("### ② 新聞搜尋（市場傳聞 / 治理危機 / 檢調動態）")
        if news_detail["status"] == "error":
            st.warning("⚠️ {}".format(news_detail["error"]))
            st.caption("新聞搜尋失敗，建議自行 Google 搜尋「{} {}」核實。".format(_code_q, _name_q))
        elif news_detail["status"] == "danger":
            st.markdown("**命中高風險關鍵字：** {}".format("、".join(news_detail["danger_kw"])))
        elif news_detail["status"] == "warning":
            st.markdown("**命中留意關鍵字：** {}".format("、".join(news_detail["warn_kw"])))

        if news_detail.get("headlines"):
            st.markdown("**近期相關新聞（共{}則）：**".format(len(news_detail["headlines"])))
            for h in news_detail["headlines"][:10]:
                st.markdown("- [{}]({})　<span style='color:#888;font-size:12px'>{} · {}</span>".format(
                    h["title"], h["link"], h["source"], h["date"]), unsafe_allow_html=True)
        elif news_detail["status"] == "clean":
            st.caption("近期無相關新聞報導。")

        st.caption(
            "⚠️ **新聞搜尋為輔助線索**，關鍵字比對可能有誤判（例如新聞標題提到「跌停」但其實是利多消息），"
            "請務必點開原文確認內容，不要只看關鍵字命中就下結論。"
        )

        with st.expander("📖 本系統偵測的關鍵字清單（點擊展開）"):
            st.markdown("**MOPS 高風險關鍵字**：{}".format("、".join(MOPS_DANGER_KW)))
            st.markdown("**MOPS 留意關鍵字**：{}".format("、".join(MOPS_WARN_KW)))
            st.markdown("**新聞 高風險關鍵字**：{}".format("、".join(NEWS_DANGER_KW)))
            st.markdown("**新聞 留意關鍵字**：{}".format("、".join(NEWS_WARN_KW)))
            st.caption("命中關鍵字僅作為線索提醒，不代表自動判定公司有問題，請務必查證原文。")

    else:
        st.info("💡 輸入股票代碼（建議同時填名稱，新聞搜尋準確度較高），點擊查詢按鈕即可看到雙層風險偵測結果。")


with tab_brief:
    st.markdown(_tab_icon("icon-news", "每日市場簡報", "盤前快訊 · 財經事件解讀 · 重大事件日曆"), unsafe_allow_html=True)
    st.caption("📄 PDF說明：請用下方「下載HTML報告」按鈕，下載後在瀏覽器直接開啟，再按 Ctrl+P 存成PDF（完整輸出，不受 iframe 限制）")

    st.caption(
        "資料源：Yahoo Finance（盤前快訊）｜ Reuters/Yahoo RSS（新聞）｜ "
        "Fed.gov / BLS.gov（總經日曆）｜ TWSE MoPS（台股重大訊息）｜ 全部免費"
    )

    # ── 第一區：盤前快訊 ──────────────────────────────────
    st.markdown("---")
    st.markdown("""
<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">
  <div style="width:22px;height:22px;border-radius:6px;background:#003781;color:#fff;
       font-size:11px;font-weight:600;display:flex;align-items:center;justify-content:center">1</div>
  <span style="font-size:14px;font-weight:600;color:#003781">今日盤前快訊</span>
  <span style="font-size:13px;color:#888">每15分鐘自動更新 ｜ 資料源：Yahoo Finance</span>
</div>""", unsafe_allow_html=True)

    with st.spinner("抓取盤前數據中..."):
        premarket = _brief_get_premarket()

    # 第一列：4個半導體ADR
    st.markdown("**半導體 ADR**")
    c1, c2, c3, c4 = st.columns(4)
    for col, key in zip([c1, c2, c3, c4], ["tsm", "nvda", "amd", "avgo"]):
        _render_metric_card(col, premarket.get(key, {"name": key, "val": None, "chg_pct": None, "signal": "—", "color": "#888"}))

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # 第二列：指數 + 台股 + 總經
    st.markdown("**大盤指數 ｜ 台股 ｜ 總經**")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    for col, key in zip([c1, c2, c3, c4, c5, c6],
                        ["sox", "sp500", "txf", "dxy", "tnx", "vix"]):
        _render_metric_card(col, premarket.get(key, {"name": key, "val": None, "chg_pct": None, "signal": "—", "color": "#888"}))

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # 外資買賣超
    try:
        foreign = _brief_get_foreign_net()
        if foreign["net"] is not None:
            net_v = foreign["net"]
            direction = "買超" if net_v > 0 else "賣超"
            net_color = "#A32D2D" if net_v > 0 else "#0F6E56"
            st.markdown("""
<div style="background:#f8f9fa;border-radius:8px;border:0.5px solid #e0e0e0;
     padding:10px 16px;display:flex;align-items:center;gap:16px;margin-top:4px">
  <div style="font-size:13px;color:#888">外資買賣超（TWSE）</div>
  <div style="font-size:16px;font-weight:600;color:{c}">{dir} {val}{unit}</div>
  <div style="font-size:13px;color:#888">{date}</div>
</div>""".format(c=net_color, dir=direction,
                val=abs(round(net_v, 2)),
                unit=" " + foreign["unit"],
                date=foreign.get("date", "")), unsafe_allow_html=True)
    except Exception:
        pass

    # ── 第二區：重大財經新聞 ──────────────────────────────
    st.markdown("---")
    st.markdown("""
<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
  <div style="width:22px;height:22px;border-radius:6px;background:#003781;color:#fff;
       font-size:11px;font-weight:600;display:flex;align-items:center;justify-content:center">2</div>
  <span style="font-size:14px;font-weight:600;color:#003781">重大財經事件解讀</span>
  <span style="font-size:13px;color:#888">近72小時 ｜ Reuters RSS ＋ Yahoo Finance ＋ TWSE MoPS ｜ 自動中文化</span>
</div>""", unsafe_allow_html=True)
    st.caption("關鍵字涵蓋：台積電・輝達・美光・博通・AMD・蘋果・FOMC・CPI・半導體・AI晶片")

    col_news, col_refresh = st.columns([6, 1])
    with col_refresh:
        if st.button("🔄 重新整理", key="brief_news_refresh"):
            st.cache_data.clear()
            st.rerun()

    with st.spinner("抓取並翻譯新聞中（首次較慢，後續有快取）..."):
        news_items = _brief_get_news()

    if news_items:
        for item in news_items:
            _render_news_item(item)
    else:
        st.info(
            "目前無法抓到符合關鍵字的財經新聞。\n\n"
            "可能原因：網路連線限制（Streamlit Cloud部分RSS被封）。\n"
            "建議：點「重新整理」再試一次，或直接查閱 Reuters.com / Bloomberg.com。"
        )

    # ── 第三區：事件日曆 ──────────────────────────────────
    st.markdown("---")
    st.markdown("""
<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">
  <div style="width:22px;height:22px;border-radius:6px;background:#003781;color:#fff;
       font-size:11px;font-weight:600;display:flex;align-items:center;justify-content:center">3</div>
  <span style="font-size:14px;font-weight:600;color:#003781">未來180天重大事件日曆</span>
  <span style="font-size:13px;color:#888">Fed.gov ＋ BLS.gov ＋ Yahoo Finance ＋ 內建規則</span>
</div>""", unsafe_allow_html=True)

    CAT_BADGE = {
        "美國總經":    ("#E6F1FB", "#0C447C"),
        "企業財報/法說": ("#FEF0CC", "#633806"),
        "台股事件":    ("#EEEDFE", "#3C3489"),
    }
    CAT_DESC = {
        "美國總經":    "影響全球資金成本與風險偏好",
        "企業財報/法說": "台股供應鏈訂單能見度關鍵",
        "台股事件":    "台股市場結構性資金移動",
    }

    with st.spinner("載入事件日曆..."):
        events = _brief_get_calendar()

    if events:
        from datetime import date as _date
        today_d = __import__('datetime').datetime.now().date()

        for ev in events:
            ev_date = ev["date"]
            is_today = (ev_date == today_d)
            is_past  = (ev_date < today_d)

            date_str = ev_date.strftime("%-m/%-d") if hasattr(ev_date, 'strftime') else str(ev_date)
            weekday_map = ["一","二","三","四","五","六","日"]
            weekday_str = weekday_map[ev_date.weekday()] if hasattr(ev_date, 'weekday') else ""

            cat = ev["category"]
            badge_bg, badge_fg = CAT_BADGE.get(cat, ("#e0e0e0", "#414141"))
            row_bg = "#FEF0CC" if is_today else ("#f8f8f8" if is_past else "#ffffff")
            opacity = "0.55" if is_past else "1"

            st.markdown("""
<div style="border-radius:8px;border:0.5px solid #e0e0e0;padding:9px 14px;
     display:flex;align-items:center;gap:12px;margin-bottom:5px;
     background:{bg};opacity:{op}">
  <div style="width:52px;flex-shrink:0;text-align:center">
    <div style="font-size:17px;font-weight:700;color:#003781">{d}</div>
    <div style="font-size:13px;color:#888">週{wd}</div>
  </div>
  <div style="width:8px;height:8px;border-radius:50%;background:{cc};flex-shrink:0"></div>
  <div style="flex:1">
    <div style="font-size:13px;font-weight:600;color:#003781">{title}</div>
    <div style="font-size:13px;color:#888;margin-top:1px">{sub}</div>
  </div>
  <div style="flex-shrink:0;background:{bb};color:{bf};font-size:10px;
       font-weight:600;padding:2px 8px;border-radius:4px;white-space:nowrap">{cat}</div>
  {today_tag}
</div>""".format(
                bg=row_bg, op=opacity,
                d=date_str, wd=weekday_str,
                cc=ev["cat_color"],
                title=ev["title"], sub=ev["sub"],
                bb=badge_bg, bf=badge_fg, cat=cat,
                today_tag='<div style="flex-shrink:0;background:#003781;color:#fff;font-size:10px;padding:2px 6px;border-radius:3px">今天</div>' if is_today else ""
            ), unsafe_allow_html=True)

        # 圖例
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        legend_html = "<div style='display:flex;gap:16px;flex-wrap:wrap'>"
        for cat, (bb, bf) in CAT_BADGE.items():
            legend_html += """
<div style="display:flex;align-items:center;gap:5px">
  <div style="background:{bb};color:{bf};font-size:12px;font-weight:600;
       padding:2px 8px;border-radius:4px">{cat}</div>
  <span style="font-size:13px;color:#888">{desc}</span>
</div>""".format(bb=bb, bf=bf, cat=cat, desc=CAT_DESC.get(cat, ""))
        legend_html += "</div>"
        st.markdown(legend_html, unsafe_allow_html=True)

    else:
        st.info(
            "近35天內未找到已知重大事件。\n\n"
            "可能原因：Fed/BLS官網暫時無法連線（Streamlit Cloud境外IP有時受限）。\n"
            "建議：參考 federalreserve.gov 或 bls.gov 的官方日曆。"
        )

    st.markdown("---")
    st.caption(
        "⚡ 快取策略：盤前快訊15分鐘更新 ｜ 新聞12小時更新 ｜ 事件日曆24小時更新。"
        "若需立即刷新請點「重新整理」按鈕或重新整理頁面。"
        "本頁所有資料均來自公開免費資料源，不含任何付費API。"
    )
