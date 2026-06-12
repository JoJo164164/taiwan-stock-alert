import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import time

st.set_page_config(page_title="台股滾動10日跌幅警示", layout="wide")
st.title("📉 台股滾動10日跌幅警示系統")
st.caption(f"資料來源：台灣證交所 / 櫃買中心｜更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}")

@st.cache_data(ttl=86400)
def get_twse_stocks():
    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        return [{"code": d["Code"], "name": d["Name"], "market": "上市"} for d in data if d["Code"].isdigit()]
    except:
        return []

@st.cache_data(ttl=86400)
def get_otc_stocks():
    url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        return [{"code": d["SecuritiesCompanyCode"], "name": d["CompanyName"], "market": "上櫃"} for d in data]
    except:
        return []

def get_twse_history(code):
    prices = {}
    today = datetime.today()
    for i in range(2):
        d = today - timedelta(days=30*i)
        ym = d.strftime("%Y%m01")
        url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={ym}&stockNo={code}"
        try:
            res = requests.get(url, timeout=10)
            data = res.json()
            if data.get("stat") == "OK":
                for row in data["data"]:
                    date_str = row[0].replace("/", "-")
                    parts = date_str.split("-")
                    date = f"{int(parts[0])+1911}-{parts[1]}-{parts[2]}"
                    close = float(row[6].replace(",", ""))
                    prices[date] = close
        except:
            pass
        time.sleep(0.3)
    return prices

def get_otc_history(code):
    prices = {}
    today = datetime.today()
    for i in range(2):
        d = today - timedelta(days=30*i)
        ym = f"{d.year-1911}/{d.month:02d}"
        url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?l=zh-tw&d={ym}&stkno={code}&s=0,asc"
        try:
            res = requests.get(url, timeout=10)
            data = res.json()
            if data.get("iTotalRecords", 0) > 0:
                for row in data["aaData"]:
                    date_str = row[0]
                    parts = date_str.split("/")
                    date = f"{int(parts[0])+1911}-{parts[1]}-{parts[2]}"
                    try:
                        close = float(row[2].replace(",", ""))
                        prices[date] = close
                    except:
                        pass
        except:
            pass
        time.sleep(0.3)
    return prices

def calc_rolling_return(prices_dict):
    if len(prices_dict) < 11:
        return None
    dates = sorted(prices_dict.keys())
    latest_date = dates[-1]
    base_date = dates[-11]
    latest_price = prices_dict[latest_date]
    base_price = prices_dict[base_date]
    if base_price == 0:
        return None
    return (latest_price - base_price) / base_price * 100

threshold = st.slider("設定警示門檻（跌幅%）", min_value=-30, max_value=-5, value=-10, step=1)
filter_type = st.radio("篩選範圍", ["全部", "僅ETF", "僅個股"], horizontal=True)

if st.button("🔍 開始掃描", type="primary"):

    with st.spinner("正在抓取股票清單..."):
        twse_stocks = get_twse_stocks()
        otc_stocks = get_otc_stocks()

    twse_codes = set(s["code"] for s in twse_stocks)
    all_stocks = twse_stocks + otc_stocks

    if filter_type == "僅ETF":
        all_stocks = [s for s in all_stocks if len(s["code"]) >= 6 or not s["code"].isdigit()]
    elif filter_type == "僅個股":
        all_stocks = [s for s in all_stocks if len(s["code"]) == 4 and s["code"].isdigit()]

    total = len(all_stocks)
    st.info(f"共 {total} 檔標的，開始掃描（約需數分鐘）...")

    results = []
    progress = st.progress(0, text="掃描中...")
    status = st.empty()

    for i, stock in enumerate(all_stocks):
        code = stock["code"]
        name = stock["name"]
        market = stock["market"]

        status.text(f"正在掃描：{code} {name}（{i+1}/{total}）")

        if code in twse_codes:
            prices = get_twse_history(code)
        else:
            prices = get_otc_history(code)

        ret = calc_rolling_return(prices)

        if ret is not None and ret <= threshold:
            results.append({
                "市場": market,
                "代碼": code,
                "名稱": name,
                "滾動10日報酬率": f"{ret:.2f}%",
                "數值": ret
            })

        progress.progress((i+1)/total, text=f"掃描進度：{i+1}/{total}")
        time.sleep(0.25)

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
