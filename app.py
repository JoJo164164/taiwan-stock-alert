---

### 📊 三張核心表格說明

| 表格 | 用途 |
|------|------|
| **勝率表** | 觸發後持有N天，收益為正的機率有多高 |
| **平均報酬表** | 平均每次觸發進場，持有N天的平均獲利 |
| **累積報酬表** | 假設每次觸發都跟進，總共累積的報酬 |

---

### ⚠️ 重要提醒

- 本系統為**輔助研究工具**，不構成投資建議
- 歷史回測不代表未來績效
- 建議搭配**基本面分析**與**產業趨勢**判斷後再做決策
- 連續觸發天數多代表跌勢持續，需特別謹慎評估是否為基本面惡化

---

### 🔑 觀察天數說明

| 天數 | 約等於 | 觀察意義 |
|------|--------|---------|
| 10天 | 2週 | 短期反彈 |
| 20天 | 1個月 | 月線修復 |
| 50天 | 2.5個月 | 季線修復 |
| 100天 | 5個月 | 半年趨勢 |
| 200天 | 1年 | 年線修復 |
    """)

# ==============================
# TAB 1: 每日警示
# ==============================
with tab1:
    threshold1 = st.slider("警示門檻（跌幅%）", min_value=-30, max_value=-3, value=-10, step=1, key="t1")
    st.markdown("**篩選範圍（可多選，不選代表全部）**")
    selected1 = group_selector("tab1")

    if st.button("🔍 開始掃描", type="primary", key="scan"):
        all_stocks = get_all_tw_stocks()
        scan_list = [s for s in all_stocks if s["group"] in selected1] if selected1 else all_stocks
        total = len(scan_list)
        st.info(f"共 {total} 檔，開始掃描...")
        results = []
        progress = st.progress(0)
        status = st.empty()

        for i, stock in enumerate(scan_list):
            code = stock["code"]
            status.text(f"掃描中：{code} {stock['name']}（{i+1}/{total}）")
            prices = get_yahoo_history(code, days=60)
            ret = calc_rolling_return_latest(prices)
            if ret is not None and ret <= threshold1:
                results.append({
                    "產業群組": stock["group"],
                    "產業別": stock["industry"],
                    "代碼": code,
                    "名稱": stock["name"],
                    "滾動10日報酬率": f"{ret:.2f}%",
                    "數值": ret
                })
            progress.progress((i+1)/total)
            time.sleep(0.15)

        progress.empty()
        status.empty()

        if results:
            df = pd.DataFrame(results).sort_values("數值").drop(columns=["數值"])
            st.error(f"⚠️ 共 {len(results)} 檔觸發（門檻：{threshold1}%）")
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button("📥 下載CSV", df.to_csv(index=False).encode("utf-8-sig"), "alert.csv", "text/csv")
        else:
            st.success(f"✅ 目前沒有標的觸發 {threshold1}% 警示")

# ==============================
# TAB 2: 批次回測
# ==============================
with tab2:
    st.subheader("批次回測（五年）")
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
        st.info(f"共 {total} 檔，開始回測（約需數分鐘）...")
        all_rows = []
        progress = st.progress(0)
        status = st.empty()

        for i, stock in enumerate(bt_list):
            code = stock["code"]
            status.text(f"回測中：{code} {stock['name']}（{i+1}/{total}）")
            prices = get_yahoo_history_5y(code)
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
                        if not rets:
                            row[f"{h}天平均報酬%"] = "待觀察"
                            row[f"{h}天累積報酬%"] = "待觀察"
                        else:
                            row[f"{h}天平均報酬%"] = round(sum(rets)/len(rets), 2)
                            cum = 1.0
                            for r in rets:
                                cum *= (1 + r/100)
                            row[f"{h}天累積報酬%"] = round((cum-1)*100, 2)
                    all_rows.append(row)

            progress.progress((i+1)/total)
            time.sleep(0.2)

        progress.empty()
        status.empty()

        if all_rows:
            df_bt = pd.DataFrame(all_rows)
            ret_cols = [c for c in df_bt.columns if "報酬%" in c]
            st.success("✅ 回測完成！")
            st.dataframe(
                df_bt.style.map(color_ret, subset=ret_cols),
                use_container_width=True, hide_index=True
            )
            st.download_button("📥 下載CSV", df_bt.to_csv(index=False).encode("utf-8-sig"), "backtest.csv", "text/csv")
            st.markdown(NOTES)
        else:
            st.warning("沒有找到任何觸發紀錄")

# ==============================
# TAB 3: 個股回測
# ==============================
with tab3:
    st.subheader("個股／ETF 回測＋線圖")
    col1, col2 = st.columns([2, 1])
    with col1:
        single_code = st.text_input("輸入股票／ETF代碼", value="2330", key="single")
    with col2:
        ref_threshold = st.selectbox("線圖顯示門檻", [f"{t}%" for t in THRESHOLDS], index=2, key="ref_thr")

    if st.button("🔬 開始分析", type="primary", key="single_bt"):
        with st.spinner(f"抓取 {single_code} 五年資料中..."):
            prices = get_yahoo_history_5y(single_code)

        if not prices:
            st.error("抓取失敗，請確認代碼是否正確")
        else:
            st.success(f"成功抓取 {len(prices)} 個交易日（{min(prices.keys())} ~ {max(prices.keys())}）")

            # 三張總覽表
            with st.spinner("計算各門檻回測中..."):
                df_win, df_avg, df_cum = build_summary_tables(prices)

            ret_cols_avg = [c for c in df_avg.columns if "報酬%" in c]
            ret_cols_cum = [c for c in df_cum.columns if "報酬%" in c]

            st.write("### 📊 表A：各門檻 × 觀察天數 勝率")
            st.dataframe(df_win, use_container_width=True, hide_index=True)

            st.write("### 📊 表B：各門檻 × 觀察天數 平均單次報酬%")
            st.dataframe(df_avg.style.map(color_ret, subset=ret_cols_avg), use_container_width=True, hide_index=True)

            st.write("### 📊 表C：各門檻 × 觀察天數 累積報酬%")
            st.dataframe(df_cum.style.map(color_ret, subset=ret_cols_cum), use_container_width=True, hide_index=True)

            st.markdown(NOTES)

            # 年度明細表
            thr_val = int(ref_threshold.replace("%", ""))
            df_yearly, result = build_yearly_table(prices, thr_val)
            if df_yearly is not None:
                st.write(f"### 📅 年度明細（門檻 {ref_threshold}）")
                yearly_ret_cols = [c for c in df_yearly.columns if "報酬%" in c]
                st.dataframe(
                    df_yearly.style.map(color_ret, subset=yearly_ret_cols),
                    use_container_width=True, hide_index=True
                )

            # 線圖
            if result:
                st.write(f"### 📈 股價走勢＋觸發標記（門檻 {ref_threshold}）")
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
                    name=f"觸發日（{ref_threshold}）",
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
                        "滾動10日報酬率": f"{t['return']}%"
                    } for t in triggered])
                    st.dataframe(df_trig, use_container_width=True, hide_index=True)
