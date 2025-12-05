###############################################################
# app.py — 0050 vs 00631L 延遲 + SMA 穿越統計 ALL-IN-ONE Dashboard
###############################################################

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta

# 設定頁面資訊 (必須是第一個 Streamlit 指令)
st.set_page_config(
    page_title="0050 vs 00631L 戰情室",
    layout="wide"
)

st.title("📊 0050 vs 00631L — 延遲 Dashboard + SMA 穿越統計")

st.markdown("""
本工具整合：

### ✔ 延遲分析（Delay）
- Cross-correlation（lag -5 至 +5）
- 同日/隔日散佈圖
- 大跌事件對齊

### ✔ 200SMA 穿越統計
- 誰先突破？
- 誰先跌破？
- 日差 Histogram
- 勝率統計
""")

###############################################################
# 頁面上方條件控制區（取代 Sidebar）
###############################################################
st.subheader("⚙️ 參數設定（Conditions）")

colA, colB, colC = st.columns(3)
with colA:
    start_date = st.date_input("開始日期", pd.to_datetime("2010-01-01"))
with colB:
    end_date = st.date_input("結束日期", pd.to_datetime("today"))
with colC:
    sma_window = st.slider("SMA 週期", 50, 250, 200)

colD, colE, colF = st.columns(3)
with colD:
    lag_min = st.number_input("最小 lag", -10, 0, -5)
with colE:
    lag_max = st.number_input("最大 lag", 0, 10, 5)
with colF:
    drop_thresh = st.number_input("大跌閾值 (%)", -20.0, 0.0, -5.0)

event_window = st.slider("事件前後天數", 1, 10, 3)
st.divider()

###############################################################
# 安全下載資料 — 處理 yfinance 格式變更與 MultiIndex
###############################################################
@st.cache_data
def load_price(start, end):
    # 下載資料，auto_adjust=False 確保我們可以明確選擇 Close 或 Adj Close
    raw = yf.download(["0050.TW", "00631L.TW"], start=start, end=end, auto_adjust=False)

    if raw.empty:
        st.error("yfinance 資料為空，請調整日期或檢查網路連線。")
        st.stop()

    df = pd.DataFrame()

    # 處理 yfinance 回傳資料結構 (可能是 MultiIndex 也可能是單層)
    if isinstance(raw.columns, pd.MultiIndex):
        # 優先使用 Adj Close，如果沒有則使用 Close
        if "Adj Close" in raw.columns.levels[0]:
            df = raw["Adj Close"].copy()
        elif "Close" in raw.columns.levels[0]:
            df = raw["Close"].copy()
        else:
            # 嘗試直接取 level 1
            try:
                df = raw.xs("Adj Close", axis=1, level=0, drop_level=True)
            except:
                df = raw.xs("Close", axis=1, level=0, drop_level=True)
    else:
        # 單層欄位處理
        if "Adj Close" in raw.columns:
            df = raw[["Adj Close"]].copy()
        elif "Close" in raw.columns:
            df = raw[["Close"]].copy()
        else:
            # 最後手段：假設只有這兩欄
            df = raw.copy()
    
    # 重新命名欄位以便後續處理
    cols_map = {}
    for col in df.columns:
        if "0050" in str(col):
            cols_map[col] = "0050"
        elif "00631L" in str(col):
            cols_map[col] = "00631L"
    
    df = df.rename(columns=cols_map).dropna()

    # 檢查是否兩個標的都有資料
    if not {"0050", "00631L"} <= set(df.columns):
        st.error(f"下載資料欄位不完整，目前欄位: {df.columns.tolist()}，請確認代碼是否正確。")
        st.stop()

    return df

# 載入資料
price = load_price(start_date, end_date)

st.success(f"資料下載成功！區間：**{price.index.min().date()}** ～ **{price.index.max().date()}**，共 {len(price)} 筆交易日資料。")
st.divider()

###############################################################
# 1. 價格走勢圖
###############################################################
st.subheader("📈 收盤價走勢")

fig_price = px.line(price, x=price.index, y=["0050", "00631L"], title="0050 vs 00631L 歷史價格")
st.plotly_chart(fig_price, use_container_width=True)

###############################################################
# 資料處理：報酬率計算
###############################################################
ret = price.pct_change().dropna()
ret["ret_50"] = ret["0050"]
ret["ret_L"] = ret["00631L"]
# 隔日報酬 (Shift -1 代表 t+1 的報酬對應到 t 的 index)
ret["ret_L_next"] = ret["ret_L"].shift(-1)

# 計算槓桿倍數 (避免除以 0)
ret["lev_same"] = np.where(ret["ret_50"] != 0, ret["ret_L"] / ret["ret_50"], np.nan)
ret["lev_next"] = np.where(ret["ret_50"] != 0, ret["ret_L_next"] / ret["ret_50"], np.nan)

###############################################################
# 2. 延遲 (Delay) Dashboard
###############################################################
st.header("⏱ 延遲 (Delay) 分析")

# 計算相關係數
valid_data = ret.dropna()
corr_same = valid_data["ret_50"].corr(valid_data["ret_L"])
corr_next = valid_data["ret_50"].corr(valid_data["ret_L_next"])

colA, colB, colC, colD = st.columns(4)
colA.metric("同日相關係數", f"{corr_same:.3f}")
colB.metric("隔日相關係數 (T+1)", f"{corr_next:.3f}")
colC.metric("同日槓桿倍數 (平均)", f"{valid_data['lev_same'].mean():.2f}x")
colD.metric("隔日槓桿倍數 (平均)", f"{valid_data['lev_next'].mean():.2f}x")

st.info("""
**解讀說明：**
* **同日相關係數**：代表 0050 當天漲跌與 00631L 當天漲跌的連動性。
* **隔日相關係數**：代表 0050 **今天**的漲跌與 00631L **明天**的漲跌連動性。
* 如果 **隔日相關係數 > 同日** 或數值很高，代表有明顯的延遲反應現象。
""")

###############################################################
# Cross-correlation Heatmap
###############################################################
st.subheader("🔁 Cross-correlation（跨日相關性熱力圖）")

lags = list(range(lag_min, lag_max + 1))
corrs = []
for lag in lags:
    # shift(-lag) 代表將未來的資料往前移，
    # 若 lag=1, 代表 ret_L(t+1) 與 ret_50(t) 比較 -> 00631L 晚一天
    # 若 lag=-1, 代表 ret_L(t-1) 與 ret_50(t) 比較 -> 00631L 早一天
    c = ret["ret_50"].corr(ret["ret_L"].shift(-lag))
    corrs.append(c)

fig_corr = go.Figure(data=go.Heatmap(
    z=[corrs],
    x=lags,
    y=["Correlation"],
    colorscale="RdBu",
    zmid=0,
    text=[[f"{c:.2f}" for c in corrs]],
    texttemplate="%{text}"
))
fig_corr.update_layout(
    height=260, 
    xaxis_title="Lag Days (+1 代表 00631L 晚一天反應)",
    yaxis_title="相關係數"
)
st.plotly_chart(fig_corr, use_container_width=True)

###############################################################
# Scatter Plots
###############################################################
st.subheader("📌 同日 vs 隔日散佈圖")

col1, col2 = st.columns(2)

with col1:
    fig_same = px.scatter(ret, x="ret_50", y="ret_L", opacity=0.6, title="同日報酬 (0050 vs 00631L)")
    fig_same.add_hline(y=0, line_width=1, line_color="black")
    fig_same.add_vline(x=0, line_width=1, line_color="black")
    st.plotly_chart(fig_same, use_container_width=True)

with col2:
    fig_next = px.scatter(ret, x="ret_50", y="ret_L_next", opacity=0.6, title="隔日報酬 (0050[t] vs 00631L[t+1])")
    fig_next.add_hline(y=0, line_width=1, line_color="black")
    fig_next.add_vline(x=0, line_width=1, line_color="black")
    st.plotly_chart(fig_next, use_container_width=True)

###############################################################
# Event Alignment for Big Drops
###############################################################
st.subheader("📉 大跌事件對齊（00631L 是否隔天補跌？）")

# 篩選大跌事件
mask_drop = ret["ret_50"] <= (drop_thresh / 100.0)
drop_dates = ret.index[mask_drop]

st.markdown(f"符合大跌條件（0050 當日跌幅 < {drop_thresh}%）的事件共：**{len(drop_dates)} 次**")

records = []
if len(drop_dates) > 0:
    for d in drop_dates:
        # 取前後 N 天的視窗
        win_start = d - timedelta(days=event_window)
        win_end = d + timedelta(days=event_window)
        
        # 使用索引切片，避免假日問題
        # 這裡簡單使用 date_range 會遇到假日沒有資料的問題，改用 index search
        try:
            loc_idx = ret.index.get_loc(d)
            # 確保索引不越界
            start_idx = max(0, loc_idx - event_window)
            end_idx = min(len(ret) - 1, loc_idx + event_window)
            
            subset = ret.iloc[start_idx : end_idx + 1]
            
            for t in subset.index:
                # 計算相對天數 (Trading days diff)
                offset = subset.index.get_loc(t) - subset.index.get_loc(d)
                records.append({
                    "offset": offset,
                    "ret_L": subset.loc[t, "ret_L"]
                })
        except KeyError:
            continue

if len(records) > 0:
    df_evt = pd.DataFrame(records).groupby("offset")["ret_L"].mean().reset_index()
    fig_evt = px.line(df_evt, x="offset", y="ret_L", markers=True,
                      title="00631L 在 0050 大跌日(Day 0)前後的平均報酬表現")
    fig_evt.add_vline(x=0, line_dash="dash", line_color="black", annotation_text="Event Day")
    fig_evt.add_vline(x=1, line_dash="dot", line_color="red", annotation_text="Next Day")
    fig_evt.update_layout(xaxis_title="Trading Days Offset", yaxis_title="Average Return (00631L)")
    st.plotly_chart(fig_evt, use_container_width=True)
else:
    st.info("事件太少或無資料，無法繪製對齊圖。")

st.divider()

###############################################################
# SMA 穿越統計
###############################################################
st.header("📈 200SMA 穿越統計 Dashboard")

sma = price.rolling(sma_window).mean()
above = price > sma  # 是否在 SMA 上方 (Boolean Series)

def detect_cross(series_bool):
    # True 代表在 SMA 上方，False 代表在下方
    # shift(1) 是昨天，所以：昨天 False 且 今天 True = 向上突破
    cross_up = (series_bool.shift(1) == False) & (series_bool == True)
    # 昨天 True 且 今天 False = 向下跌破
    cross_dn = (series_bool.shift(1) == True) & (series_bool == False)
    
    return cross_up[cross_up].index, cross_dn[cross_dn].index

up_50, dn_50 = detect_cross(above["0050"])
up_L2, dn_L2 = detect_cross(above["00631L"])

st.markdown(f"**統計結果 (SMA {sma_window})**：")
colS1, colS2 = st.columns(2)
colS1.info(f"0050 向上突破次數: {len(up_50)} | 向下跌破次數: {len(dn_50)}")
colS2.info(f"00631L 向上突破次數: {len(up_L2)} | 向下跌破次數: {len(dn_L2)}")

def match_cross(a_dates, b_dates, tolerance=10):
    """
    對每個 a 的發生日，找最近的一個 b 發生日，計算 (b - a) 的天數差。
    Tolerance: 只找前後 X 天內的配對
    """
    diffs = []
    # 為了避免重複配對，可以簡單做，也可以做複雜配對。這裡採用簡單：找最近的一個。
    for d in a_dates:
        # 篩選在容許範圍內的 b 日期
        candidates = [x for x in b_dates if abs((x - d).days) <= tolerance]
        if candidates:
            # 找絕對值最小的 (最近的)
            closest = min(candidates, key=lambda x: abs((x - d).days))
            diff = (closest - d).days
            diffs.append(diff)
    return diffs

# 這裡以 0050 為基準 (Day 0)，看 00631L 差幾天
diff_up = match_cross(up_50, up_L2, tolerance=15)
diff_dn = match_cross(dn_50, dn_L2, tolerance=15)

# 勝率統計 (這裡定義勝率為：誰先反應)
# 向上：0050 先突破 (diff > 0, 00631L 晚) vs 00631L 先突破 (diff < 0)
# 向下：00631L 先跌破 (diff > 0, 0050 晚 ? 不對，邏輯相反)
# 讓 diff = Date(L) - Date(50)
# 若 diff > 0: 00631L 比較晚 (Date L > Date 50) -> 0050 先
# 若 diff < 0: 00631L 比較早 (Date L < Date 50) -> 00631L 先

def calc_win_stats(diffs):
    if not diffs: return 0, 0, 0
    n = len(diffs)
    L_lead = sum(1 for d in diffs if d < 0) # L 日期比較小，L 先
    tie    = sum(1 for d in diffs if d == 0)
    Fifty_lead = sum(1 for d in diffs if d > 0) # L 日期比較大，50 先
    return (Fifty_lead/n)*100, (L_lead/n)*100, (tie/n)*100

u50_pct, uL_pct, uTie_pct = calc_win_stats(diff_up)
d50_pct, dL_pct, dTie_pct = calc_win_stats(diff_dn)

st.subheader("🏁 誰先反應？ (Win Rate Analysis)")

colW1, colW2 = st.columns(2)

with colW1:
    st.markdown("### 🚀 向上突破 SMA")
    st.write(f"**0050 先突破**: {u50_pct:.1f}%")
    st.write(f"**00631L 先突破**: {uL_pct:.1f}%")
    st.write(f"同步突破: {uTie_pct:.1f}%")
    if len(diff_up) > 0:
        fig_hist_up = px.histogram(x=diff_up, nbins=20, labels={'x': '日差 (天)'}, 
                                   title="突破日差 (正值=0050先, 負值=00631L先)")
        fig_hist_up.add_vline(x=0, line_color="black")
        st.plotly_chart(fig_hist_up, use_container_width=True)

with colW2:
    st.markdown("### 🔻 向下跌破 SMA")
    st.write(f"**0050 先跌破**: {d50_pct:.1f}%")
    st.write(f"**00631L 先跌破**: {dL_pct:.1f}%")
    st.write(f"同步跌破: {dTie_pct:.1f}%")
    if len(diff_dn) > 0:
        fig_hist_dn = px.histogram(x=diff_dn, nbins=20, labels={'x': '日差 (天)'},
                                   title="跌破日差 (正值=0050先, 負值=00631L先)")
        fig_hist_dn.add_vline(x=0, line_color="black")
        st.plotly_chart(fig_hist_dn, use_container_width=True)

st.markdown("""
---
### 🎯 **結論參考**

1.  **下跌時**：理論上 **00631L (2倍槓桿)** 因為波動放大，稍微下跌就會觸碰均線，應該會 **"先跌破"** (L先的比例較高)。
2.  **上漲時**：因為波動耗損 (Volatility Decay)，2倍槓桿在震盪後的淨值回復較慢，理論上 **0050** 應該會 **"先突破"**。
3.  **日差分佈**：觀察 Histogram，如果分佈重心偏左 (負值)，代表 00631L 動作快；偏右 (正值)，代表 0050 動作快。
""")
