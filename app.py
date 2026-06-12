import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import time

st.set_page_config(page_title="台股滾動10日跌幅警示", layout="wide")
st.title("📉 台股滾動10日跌幅警示系統")
st.caption(f"資料來源：Yahoo Finance（台灣證交所）｜更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}")

def get_yahoo_history(code, days=60):
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
        timestamps = data["chart"]["result"][0]["timestamp"]
        closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        prices = {}
        for ts, cl in zip(timestamps, closes):
            if cl is not None:
                date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                prices[date] = round(cl, 2)
        return prices
    except:
        return {}

def calc_all_rolling_returns(prices_dict):
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
                "計算日": curr_date,
                "基準日（第1天）": base_date,
                "基準價": base_price,
                "當日收盤": curr_price,
                "滾動10日報酬率": round(ret, 2)
            })
    return results

# ---- 主掃描區 ----
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
            if code.isdigit() and len(code) == 4:
                stocks.append({"code": code, "name": name, "market": "上市", "type": "個股"})
            else:
                stocks.append({"code": code, "name": name, "market": "上市", "type": "ETF"})
    except:
        pass
    try:
        url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
        res = requests.get(url, timeout=10)
        data = res.json()
        for d in data:
            code = d["SecuritiesCompanyCode"]
            name = d["CompanyName"]
            if code.isdigit() and len(code) == 4:
                stocks.append({"code": code, "name": name, "market": "上櫃", "type": "個股"})
            else:
                stocks.append({"code": code, "name": name, "market": "上櫃", "type": "ETF"})
    except:
        pass
    return stocks

def calc_rolling_return_latest(prices_dict):
    if len(prices_dict) < 11:
        return None
    dates = sorted(prices_dict.keys())
    latest_price = prices_dict[dates[-1]]
    base_price = prices_dict[dates[-11]]
    if base_price == 0:
        return None
    return (latest_price - base_price) / base_price * 100

tab1, tab2 = st.tabs(["🔍 每日警示掃描", "🔬 單股Debug檢核"])

with tab2:
    st.subheader("單股資料檢核")
    debug_code = st.text_input("輸入股票代碼（例如 2317）", value="2317")
    if st.button("檢核", key="debug"):
        with st.spinner(f"抓取 {debug_code} 資料中..."):
            prices = get_yahoo_history(debug_code, days=60)
        
        if not prices:
            st.error("抓取失敗，請確認代碼是否正確")
        else:
            st.success(f"成功抓取 {len(prices)} 個交易日資料")
            
            # 原始資料
            st.write("**原始收盤價（最近60天）**")
            df_raw = pd.DataFrame([
                {"日期": d, "收盤價": p} for d, p in sorted(prices.items())
            ])
            st.dataframe(df_raw, use_container_width=True, hide_index=True)
            
            # 滾動10日報酬率
            st.write("**所有滾動10日報酬率計算**")
            rolling = calc_all_rolling_returns(prices)
            if rolling:
                df_roll = pd.DataFrame(rolling)
                # 標記觸發的行
                def highlight_trigger(row):
                    if row["滾動10日報酬率"] <= -10:
                        return ["background-color: #ffcccc"] * len(row)
                    elif row["滾動10日報酬率"] <= -5:
                        return ["background-color: #fff3cc"] * len(row)
                    else:
                        return [""] * len(row)
                st.dataframe(
                    df_roll.style.apply(highlight_trigger, axis=1),
                    use_container_width=True,
                    hide_index=True
                )
                
                latest = rolling[-1]
                st.info(f"**最新一筆（{latest['計算日']}）**：基準日 {latest['基準日（第1天）']}，基準價 {latest['基準價']}，當日收盤 {latest['當日收盤']}，滾動10日報酬率 **{latest['滾動10日報酬率']}%**")

with tab1:
    threshold = st.slider("設定警示門檻（跌幅%）", min_value=-30, max_value=-3, value=-10, step=1)
    filter_type = st.radio("篩選範圍", ["全部", "僅ETF", "僅個股"], horizontal=True)

    if st.button("🔍 開始掃描", type="primary"):
        with st.spinner("正在抓取股票清單..."):
            all_stocks = get_all_tw_stocks()

        if filter_type == "僅ETF":
            all_stocks = [s for s in all_stocks if s["type"] == "ETF"]
        elif filter_type == "僅個股":
            all_stocks = [s for s in all_stocks if s["type"] == "個股"]

        total = len(all_stocks)
        st.info(f"共 {total} 檔標的，開始掃描...")

        results = []
        progress = st.progress(0, text="掃描中...")
        status = st.empty()

        for i, stock in enumerate(all_stocks):
            code = stock["code"]
            name = stock["name"]
            status.text(f"掃描中：{code} {name}（{i+1}/{total}）")
            prices = get_yahoo_history(code, days=60)
            ret = calc_rolling_return_latest(prices)

            if ret is not None and ret <= threshold:
                results.append({
                    "市場": stock["market"],
                    "類型": stock["type"],
                    "代碼": code,
                    "名稱": name,
                    "滾動10日報酬率": f"{ret:.2f}%",
                    "數值": ret
                })

            progress.progress((i+1)/total, text=f"掃描進度：{i+1}/{total}")
            time.sleep(0.2)

        progress.empty()
        status.empty()

        if results:
            df = pd.DataFrame(results).sort_values("數值").drop(columns=["數值"])
            st.error(f"⚠️ 共發現 {len(results)} 檔觸發警示（門檻：{threshold}%）")
            st.dataframe(df, use_container_width=True, hide_index=True)
            csv = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button("📥 下載警示清單CSV", csv, "alert.csv", "text/csv")
        else:
            st.success(f"✅ 目前沒有標的觸發 {threshold}% 警示")
