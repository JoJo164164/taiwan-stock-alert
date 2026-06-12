import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import requests

st.set_page_config(page_title="台股滾動10日跌幅警示", layout="wide")
st.title("📉 台股滾動10日跌幅警示系統")
st.caption(f"資料來源：Yahoo Finance（台灣證交所）｜更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}")

# ---- 取得上市股票清單 ----
@st.cache_data(ttl=86400)
def get_all_tw_stocks():
    stocks = []
    
    # 上市
    try:
        url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        res = requests.get(url, timeout=10)
        data = res.json()
        for d in data:
            code = d["Code"]
            name = d["Name"]
            if code.isdigit() and len(code) == 4:
                stocks.append({"code": code, "name": name, "market": "上市", "type": "個股"})
            elif not code.isdigit() or len(code) > 4:
                stocks.append({"code": code, "name": name, "market": "上市", "type": "ETF"})
    except:
        pass

    # 上櫃
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

# ---- 批次抓取歷史收盤價 ----
def get_prices_batch(codes, batch_size=50):
    all_prices = {}
    end = datetime.today()
    start = end - timedelta(days=30)
    
    # 轉換成yfinance格式 2330 -> 2330.TW
    tw_codes = [f"{c}.TW" for c in codes]
    
    for i in range(0, len(tw_codes), batch_size):
        batch = tw_codes[i:i+batch_size]
        try:
            df = yf.download(
                batch,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=True
            )
            if len(batch) == 1:
                if "Close" in df.columns:
                    code = codes[i]
                    all_prices[code] = df["Close"].dropna().to_dict()
            else:
                if "Close" in df.columns:
                    for j, tw_code in enumerate(batch):
                        code = codes[i+j]
                        try:
                            series = df["Close"][tw_code].dropna()
                            all_prices[code] = series.to_dict()
                        except:
                            pass
        except:
            pass
    
    return all_prices

# ---- 計算滾動10日報酬率 ----
def calc_rolling_return(prices_dict):
    if len(prices_dict) < 11:
        return None
    dates = sorted(prices_dict.keys())
