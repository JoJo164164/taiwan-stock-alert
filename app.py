import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time

st.set_page_config(page_title="台股滾動10日跌幅系統", layout="wide")
st.title("📉 台股滾動10日跌幅系統")
st.caption(f"資料來源：Yahoo Finance（台灣證交所）｜更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}")

# ==============================
# 工具函數
# ==============================

def classify_code(code):
    """分類股票代碼"""
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
    """抓取Yahoo Finance歷史資料"""
    end = datetime.today()
    start = end - timedelta(days=days)
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{code}.TW"
        f"?interval=1d&period1={int(start.timestamp())}&period2={int(end.timestamp())}"
    )
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

def get_yahoo_history_5y(code):
    """抓取五年歷史資料"""
    end = datetime.today()
    start = end - timedelta(days=365*5+30)
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{code}.TW"
        f"?interval=1d&period1={int(start.timestamp())}&period2={int(end.timestamp())}"
    )
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=15)
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

def calc_rolling_return_latest(prices_dict):
    """計算最新滾動10日報酬率"""
    if len(prices_dict) < 11:
        return None
    dates = sorted(prices_dict.keys())
    latest_price = prices_dict[dates[-1]]
    base_price = prices_dict[dates[-11]]
    if base_price == 0:
        return None
    return (latest_price - base_price) / base_price * 100

def calc_all_rolling_returns(prices_dict):
    """計算所有滾動10日報酬率"""
    if len(prices_dict) < 11:
        return []
    dates = sorted(prices_dict.keys())
    results = []
    for i in range(10, len(dates)):
        base_date = dates[i-10]
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

def run_backtest(prices_dict, threshold=-10):
    """執行回測，回傳觸發統計與進場績效"""
    rolling = calc_all_rolling_returns(prices_dict)
    if not rolling:
        return None

    dates = sorted(prices_dict.keys())
    date_to_idx = {d: i for i, d in enumerate(dates)}

    triggers = [r for r in rolling if r["return"] <= threshold]
    if not triggers:
        return None

    # 計算連續觸發
    trigger_dates = set(t["date"] for t in triggers)
    max_consecutive = 0
    current_consecutive = 0
    for r in rolling:
        if r["date"] in trigger_dates:
            current_consecutive += 1
            max_consecutive = max(max_consecutive, current_consecutive)
        else:
            current_consecutive = 0

    # 按年度統計
    yearly = {}
    for t in triggers:
        year = t["date"][:4]
        if year not in yearly:
            yearly[year] = {"triggers": [], "ret10": [], "ret50": [], "ret100": []}
        yearly[year]["triggers"].append(t)

        idx = date_to_idx.get(t["date"])
        if idx is not None:
            entry_price = t["curr_price"]
            for horizon, key in [(10, "ret10"), (50, "ret50"), (100, "ret100")]:
                future_idx = idx + horizon
                if future_idx < len(dates):
                    future_price = prices_dict[dates[future_idx]]
                    ret = (future_price - entry_price) / entry_price * 100
                    yearly[year][key].append(round(ret, 2))

    rows = []
    total_triggers = len(triggers)
    all_ret10, all_ret50, all_ret100 = [], [], []

    for year in sorted(yearly.keys()):
        y = yearly[year]
        r10 = round(sum(y["ret10"])/len(y["ret10"]), 2) if y["ret10"] else None
        r50 = round(sum(y["ret50"])/len(y["ret50"]), 2) if y["ret50"] else None
        r100 = round(sum(y["ret100"])/len(y["ret100"]), 2) if y["ret100"] else None
        rows.append({
            "年度": year,
            "觸發次數": len(y["triggers"]),
            "進場後10天平均報酬%": r10,
            "進場後50天平均報酬%": r50,
            "進場後100天平均報酬%": r100,
        })
        if r10 is not None: all_ret10.append(r10)
        if r50 is not None: all_ret50.append(r50)
        if r100 is not None: all_ret100.append(r100)

    rows.append({
        "年度": "合計/平均",
        "觸發次數": total_triggers,
        "進場後10天平均報酬%": round(sum(all_ret10)/len(all_ret10), 2) if all_ret10 else None,
        "進場後50天平均報酬%": round(sum(all_ret50)/len(all_ret50), 2) if all_ret50 else None,
        "進場後100天平均報酬%": round(sum(all_ret100)/len(all_ret100), 2) if all_ret100 else None,
    })

    return {
        "yearly_rows": rows,
        "max_consecutive": max_consecutive,
        "trigger_dates": list(trigger_dates),
        "total_triggers": total_triggers
    }

# ==============================
# 股票清單
# ==============================

@st.cache_data(ttl=86400)
def get_all_tw_stocks():
    stocks = []
    try:
        url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        res = requests.get(url, timeout=10)
        data = res.json()
        for d in data:
            code = d["Code"]
            name = d["Name"]
            t = classify_code(code)
            stocks.append({"code": code, "name": name, "market": "上市", "type": t})
    except:
        pass
    try:
        url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
        res = requests.get(url, timeout=10)
        data = res.json()
        for d in data:
            code = d["SecuritiesCompanyCode"]
            name = d["CompanyName"]
            t = classify_code(code)
            stocks.append({"code": code, "name": name, "market": "上櫃", "type": t})
    except:
        pass
    return stocks

# 台灣50成分股
TW50 = [
    "2330","2317","2454","2382","2308","2303","2412","1301","1303","1326",
    "2002","2886","2891","2882","2884","2885","2892","2880","2881","2883",
    "2887","5880","2357","2379","3711","2395","3034","4938","2408","3008",
    "2327","2337","2376","2301","6505","1216","2105","2207","2912","1101",
    "2603","2609","2615","2618","5871","9904","9910","1590","2354","3045"
]

# 中型100成分股（部分代表性）
MID100 = [
    "1402","1408","1434","1476","1504","1513","1519","1527","1560","1605",
    "1722","1723","1736","1737","1762","1773","1786","1789","2006","2014",
    "2015","2023","2038","2049","2059","2062","2065","2066","2067","2068",
    "2069","2070","2071","2072","2073","2074","2075","2076","2077","2078",
    "2079","2080","2081","2082","2083","2084","2085","2086","2087","2088"
]

# ==============================
# 頁籤
# ==============================

tab1, tab2, tab3 = st.tabs(["🔍 每日警示掃描", "📊 批次回測", "🔬 個股回測"])

# ==============================
# TAB 1: 每日警示
# ==============================
with tab1:
    threshold1 = st.slider("設定警示門檻（跌幅%）", min_value=-30, max_value=-3, value=-10, step=1)
    filter_type1 = st.radio(
        "篩選範圍",
        ["全部", "被動ETF", "主動ETF", "台灣50", "中型100", "僅個股"],
        horizontal=True
    )

    if st.button("🔍 開始掃描", type="primary", key="scan"):
        with st.spinner("正在抓取股票清單..."):
            all_stocks = get_all_tw_stocks()

        if filter_type1 == "被動ETF":
            scan_list = [s for s in all_stocks if s["type"] == "被動ETF"]
        elif filter_type1 == "主動ETF":
            scan_list = [s for s in all_stocks if s["type"] == "主動ETF"]
        elif filter_type1 == "台灣50":
            scan_list = [s for s in all_stocks if s["code"] in TW50]
        elif filter_type1 == "中型100":
            scan_list = [s for s in all_stocks if s["code"] in MID100]
        elif filter_type1 == "僅個股":
            scan_list = [s for s in all_stocks if s["type"] == "個股"]
        else:
            scan_list = all_stocks

        total = len(scan_list)
        st.info(f"共 {total} 檔標的，開始掃描...")
        results = []
        progress = st.progress(0)
        status = st.empty()

        for i, stock in enumerate(scan_list):
            code = stock["code"]
            name = stock["name"]
            status.text(f"掃描中：{code} {name}（{i+1}/{total}）")
            prices = get_yahoo_history(code, days=60)
            ret = calc_rolling_return_latest(prices)
            if ret is not None and ret <= threshold1:
                results.append({
                    "市場": stock["market"],
                    "類型": stock["type"],
                    "代碼": code,
                    "名稱": name,
                    "滾動10日報酬率": f"{ret:.2f}%",
                    "數值": ret
                })
            progress.progress((i+1)/total)
            time.sleep(0.15)

        progress.empty()
        status.empty()

        if results:
            df = pd.DataFrame(results).sort_values("數值").drop(columns=["數值"])
            st.error(f"⚠️ 共發現 {len(results)} 檔觸發警示（門檻：{threshold1}%）")
            st.dataframe(df, use_container_width=True, hide_index=True)
            csv = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button("📥 下載CSV", csv, "alert.csv", "text/csv")
        else:
            st.success(f"✅ 目前沒有標的觸發 {threshold1}% 警示")

# ==============================
# TAB 2: 批次回測
# ==============================
with tab2:
    st.subheader("批次回測（五年）")
    threshold2 = st.slider("觸發門檻（跌幅%）", min_value=-30, max_value=-3, value=-10, step=1, key="t2")
    batch_type = st.radio(
        "回測標的範圍",
        ["被動ETF", "主動ETF", "台灣50", "中型100"],
        horizontal=True
    )

    if st.button("🚀 開始回測", type="primary", key="backtest"):
        with st.spinner("抓取股票清單..."):
            all_stocks = get_all_tw_stocks()

        if batch_type == "被動ETF":
            bt_list = [s for s in all_stocks if s["type"] == "被動ETF"]
        elif batch_type == "主動ETF":
            bt_list = [s for s in all_stocks if s["type"] == "主動ETF"]
        elif batch_type == "台灣50":
            bt_list = [s for s in all_stocks if s["code"] in TW50]
        else:
            bt_list = [s for s in all_stocks if s["code"] in MID100]

        total = len(bt_list)
        st.info(f"共 {total} 檔，開始抓取五年資料並回測（約需數分鐘）...")

        all_rows = []
        progress = st.progress(0)
        status = st.empty()

        for i, stock in enumerate(bt_list):
            code = stock["code"]
            name = stock["name"]
            status.text(f"回測中：{code} {name}（{i+1}/{total}）")

            prices = get_yahoo_history_5y(code)
            result = run_backtest(prices, threshold=threshold2)

            if result:
                for row in result["yearly_rows"]:
                    all_rows.append({
                        "類型": stock["type"],
                        "代碼": code,
                        "名稱": name,
                        "最長連續觸發天數": result["max_consecutive"] if row["年度"] == "合計/平均" else "",
                        **row
                    })

            progress.progress((i+1)/total)
            time.sleep(0.2)

        progress.empty()
        status.empty()

        if all_rows:
            df_bt = pd.DataFrame(all_rows)

            def color_return(val):
                if val is None or val == "":
                    return ""
                try:
                    v = float(val)
                    if v > 0:
                        return "color: green"
                    elif v < 0:
                        return "color: red"
                except:
                    return ""
                return ""

            st.success(f"✅ 回測完成！")
            st.dataframe(
                df_bt.style.applymap(color_return, subset=["進場後10天平均報酬%", "進場後50天平均報酬%", "進場後100天平均報酬%"]),
                use_container_width=True,
                hide_index=True
            )
            csv2 = df_bt.to_csv(index=False).encode("utf-8-sig")
            st.download_button("📥 下載回測結果CSV", csv2, "backtest.csv", "text/csv")
        else:
            st.warning("沒有找到任何觸發紀錄")

# ==============================
# TAB 3: 個股回測
# ==============================
with tab3:
    st.subheader("個股回測＋線圖")
    col1, col2 = st.columns([2, 1])
    with col1:
        single_code = st.text_input("輸入股票/ETF代碼", value="2330", key="single")
    with col2:
        threshold3 = st.slider("觸發門檻（跌幅%）", min_value=-30, max_value=-3, value=-10, step=1, key="t3")

    if st.button("🔬 開始分析", type="primary", key="single_bt"):
        with st.spinner(f"抓取 {single_code} 五年資料中..."):
            prices = get_yahoo_history_5y(single_code)

        if not prices:
            st.error("抓取失敗，請確認代碼是否正確")
        else:
            st.success(f"成功抓取 {len(prices)} 個交易日資料（{min(prices.keys())} ~ {max(prices.keys())}）")

            result = run_backtest(prices, threshold=threshold3)

            if not result:
                st.warning(f"五年內沒有觸發 {threshold3}% 的紀錄")
            else:
                # 統計表格
                st.write(f"### 📊 統計結果（最長連續觸發：{result['max_consecutive']} 天）")
                df_single = pd.DataFrame(result["yearly_rows"])

                def color_return(val):
                    if val is None:
                        return ""
                    try:
                        v = float(val)
                        return "color: green" if v > 0 else "color: red"
                    except:
                        return ""

                st.dataframe(
                    df_single.style.applymap(color_return, subset=["進場後10天平均報酬%", "進場後50天平均報酬%", "進場後100天平均報酬%"]),
                    use_container_width=True,
                    hide_index=True
                )

                # 線圖
                st.write("### 📈 股價走勢＋觸發標記")
                dates = sorted(prices.keys())
                price_values = [prices[d] for d in dates]
                trigger_dates = set(result["trigger_dates"])
                trigger_x = [d for d in dates if d in trigger_dates]
                trigger_y = [prices[d] for d in trigger_x]

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=dates, y=price_values,
                    mode="lines",
                    name="收盤價",
                    line=dict(color="#2196F3", width=1.5)
                ))
                fig.add_trace(go.Scatter(
                    x=trigger_x, y=trigger_y,
                    mode="markers",
                    name=f"觸發日（{threshold3}%）",
                    marker=dict(color="red", size=8, symbol="circle")
                ))
                fig.update_layout(
                    height=500,
                    xaxis_title="日期",
                    yaxis_title="收盤價",
                    hovermode="x unified",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02)
                )
                st.plotly_chart(fig, use_container_width=True)

                # 原始觸發清單
                with st.expander("查看所有觸發日明細"):
                    rolling = calc_all_rolling_returns(prices)
                    triggered = [r for r in rolling if r["return"] <= threshold3]
                    df_trig = pd.DataFrame([{
                        "觸發日": t["date"],
                        "基準日": t["base_date"],
                        "基準價": t["base_price"],
                        "觸發當日收盤": t["curr_price"],
                        "滾動10日報酬率": f"{t['return']}%"
                    } for t in triggered])
                    st.dataframe(df_trig, use_container_width=True, hide_index=True)
