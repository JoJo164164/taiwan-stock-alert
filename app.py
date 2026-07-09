diff --git a/app.py b/app.py
index 2467632..5a7f172 100644
--- a/app.py
+++ b/app.py
@@ -484,8 +484,13 @@ def calc_all_rolling_returns(prices_dict):
     return results
 
 
-def run_full_backtest(prices_dict, threshold):
-    rolling = calc_all_rolling_returns(prices_dict)
+def run_full_backtest(prices_dict, threshold, precomputed_rolling=None):
+    # 效能重構（2026-07-09，perf/rolling-return-vectorize）：
+    # calc_all_rolling_returns(prices_dict) 完全不依賴 threshold，
+    # 舊版每呼叫一次 run_full_backtest 就重算一次，同一檔股票對 5 個門檻＝重複算 5 次。
+    # 新增 precomputed_rolling 參數：呼叫端可在門檻迴圈外算好一次、傳進來重複使用；
+    # 不傳（None）時行為與舊版完全一致，故所有既有呼叫點無需改動。
+    rolling = precomputed_rolling if precomputed_rolling is not None else calc_all_rolling_returns(prices_dict)
     if not rolling:
         return None
     dates = sorted(prices_dict.keys())
@@ -3562,20 +3567,30 @@ with tab5:
     if st.button("▶️ 執行系統檢核", type="primary", key="check"):
         checks = []
 
+        # 分類邏輯修復（2026-07-09，fix/tab5-check-severity）：
+        # 這份清單必須與下方 IMPACT_MAP 裡標記 "error" 的項目逐字同步（目前3項）。
+        # 只有這3項失敗代表程式本身算錯，或唯一資料源（Yahoo Finance）掛掉、無備援可切換；
+        # 其餘項目（新聞源5源、MOPS三層、TWSE/TPEX）開發者已在下方 IMPACT_MAP 設計為
+        # "warning"（有fallback鏈或靜態清單備援），失敗時系統仍可正常運作，不該被判定為
+        # 「❌ 程式錯誤，不可信」。
+        # 舊版用 is_transient 關鍵字比對猜測是否為「偶發性」，猜錯了就跟 IMPACT_MAP
+        # 的原始設計脫節——例如 HTTP403/HTTP404/非JSON回應 都不含那些關鍵字，
+        # 導致本來設計成「可容忍」的降級被誤報成「程式錯誤」。
+        CRITICAL_CHECKS = {
+            "Yahoo Finance API（2330）",
+            "滾動10日報酬計算邏輯",
+            "觸發計算驗證（2330 @-7%）",
+        }
+
         def run_check(name, fn):
             try:
                 ok, detail = fn()
-                # 偵測「偶發性網路問題」→ 用警告而非錯誤
-                is_transient = any(kw in detail for kw in [
-                    "偶發性", "稍後再試", "Expecting value", "Connection", "Timeout",
-                    "JSONDecodeError", "ConnectionError", "ReadTimeout"
-                ])
                 if ok:
                     status = "✅ 正常"
-                elif is_transient:
-                    status = "⚠️ 暫時異常"   # 橘色警告，不算系統失敗
-                else:
+                elif name in CRITICAL_CHECKS:
                     status = "❌ 異常"
+                else:
+                    status = "⚠️ 暫時異常"   # 有fallback/備援可用，不算系統失敗
                 checks.append({"項目": name, "狀態": status, "說明": detail})
             except Exception as e:
                 checks.append({"項目": name, "狀態": "❌ 失敗", "說明": str(e)[:120]})
@@ -7524,8 +7539,10 @@ with tab4:
 
             stock_data = {"代碼": code, "名稱": stock["name"], "產業別": industry_display}
             has_any = False
+            # 效能重構：rolling 與 threshold 無關，同一檔股票只算一次，5個門檻共用（原本每個門檻各重算一次）
+            rolling_r = calc_all_rolling_returns(prices_r)
             for thr in THRESHOLDS:
-                result_r = run_full_backtest(prices_r, thr)
+                result_r = run_full_backtest(prices_r, thr, precomputed_rolling=rolling_r)
                 if result_r is None:
                     stock_data[str(thr) + "%勝率"] = None
                     stock_data[str(thr) + "%次數"] = 0
