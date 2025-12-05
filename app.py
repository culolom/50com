###############################################################
# app.py — 0050 vs 00631L 延遲（Delay）檢測儀表板
###############################################################

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import date

st.set_page_config(
    page_title="0050 vs 00631L Delay Dashboard",
    layout="wide"
)

st.title("📉 0050 vs 00631L 槓桿反應延遲（Delay）檢測")

st.markdown(
    """
用日收盤價來觀察：

- 00631L 的漲跌，比較貼近 **當天 0050**，還是 **隔天 00631L**？
- 在 0050 大跌時，00631L 有沒有出現 **隔天才補跌** 的現象？
"""
)

###############################################################
# Sidebar 參數
###############################################################

today = date.today()
default_start = date(2015, 1, 1)

st.sidebar.header("參數設定")

start = st.sidebar.date_input("開始日", default_start)
end = st.sidebar.date_input("結束日", today)

if start >= end:
    st.sidebar.error("開始日必須早於結束日")
    st.stop()

lag_min = st.sidebar.number_input("最小 lag", -10, 0, -5)
lag_max = st.sidebar.number_input("最大 lag", 0, 10, 5)

if lag_min > lag_max:
    st.sidebar.error("最小 lag 不能大於最大 lag")
    st.stop()

drop_thresh = st.sidebar.number_input("0050 單日大跌閾值（%）", -20.0, 0.0, -5.0)
event_window = st.sidebar.slider("大跌事件前後天數", 1, 5, 2)

st.sidebar.markdown(
    """
- **lag = 0**：00631L 與同一天 0050 的相關性  
- **lag = +1**：00631L **隔天** 對應 0050 的相關性  
- 大跌閾值例如 **-5%** = 0050 單日跌 5% 以上才算大跌
"""
)

###############################################################
# 安全抓資料
###############################################################

TICKERS = ["0050.TW", "00631L.TW"]

@st.cache_data(ttl=3600)
def safe_download(tickers, start_date, end_date):
    raw = yf.download(tickers, start=start_date, end=end_date, auto_adjust=False)

    if raw.empty:
        raise ValueError("yfinance 回傳空資料，請調整日期或稍後再試。")

    # MultiIndex 欄位（正常抓多檔時）
    if isinstance(raw.columns, pd.MultiIndex):
        level0 = raw.columns.levels[0]

        if "Adj Close" in level0:
            df = raw["Adj Close"].copy()
        elif "Close" in level0:
            df = raw["Close"].copy()
        else:
            raise KeyError("找不到 Adj Close 或 Close 欄位。")
    else:
        # 單檔情況（這裡理論上用不到，但保險）
        if "Adj Close" in raw.columns:
            df = raw[["Adj Close"]].copy()
        elif "Close" in raw.columns:
            df = raw[["Close"]].copy()
        else:
            raise KeyError("找不到 Adj Close 或 Close 欄位。")
        df.columns = tickers[:1]

    # 只保留我們要的 ticker，並依序排好
    cols = [c for c in df.columns if c in tickers]
    df = df[cols].dropna()

    return df

try:
    price_raw = safe_download(TICKERS, start, end)
except Exception as e:
    st.error(f"下載資料失敗：{e}")
    st.stop()

# rename 成簡短名字
rename_map = {TICKERS[0]: "0050", TICKERS[1]: "00631L"}
price = price_raw.rename(columns=rename_map)

st.markdown(
    f"資料期間：**{price.index.min().date()}** ～ **{price.index.max().date()}**"
)

###############################################################
# 價格走勢圖
###############################################################

st.subheader("價格走勢（收盤價）")

fig_price = px.line(
    price,
    x=price.index,
    y=["0050", "00631L"],
    labels={"value": "價格", "variable": "標的", "x": "日期"},
    title="0050 vs 00631L 價格"
)
st.plotly_chart(fig_price, use_container_width=True)

###############################################################
# 日報酬 & 槓桿計算
###############################################################

ret = price.pct_change().dropna()
ret["ret_50"] = ret["0050"]
ret["ret_631L"] = ret["00631L"]

# 隔天報酬
ret["ret_631L_next"] = ret["ret_631L"].shift(-1)

# 槓桿倍數（同日 / 隔日）
ret["lev_same"] = np.where(
    ret["ret_50"] != 0, ret["ret_631L"] / ret["ret_50"], np.nan
)
ret["lev_next"] = np.where(
    ret["ret_50"] != 0, ret["ret_631L_next"] / ret["ret_50"], np.nan
)

###############################################################
# 延遲摘要 Dashboard
###############################################################

st.subheader("📊 延遲（Delay）統計摘要")

corr_same = ret["ret_50"].corr(ret["ret_631L"])
corr_next = ret["ret_50"].corr(ret["ret_631L_next"])

lev_same_mean = ret["lev_same"].mean()
lev_next_mean = ret["lev_next"].mean()

col1, col2, col3, col4 = st.columns(4)
col1.metric("同日相關係數", f"{corr_same:.3f}")
col2.metric("隔日相關係數", f"{corr_next:.3f}")
col3.metric("同日槓桿倍數（平均）", f"{lev_same_mean:.2f} x")
col4.metric("隔日槓桿倍數（平均）", f"{lev_next_mean:.2f} x")

st.markdown(
    """
- 理論上，**同日槓桿倍數** 應該接近 2 倍  
- 如果 **隔日相關係數 / 槓桿倍數** 明顯更高，代表有「隔天補跌 / 補漲」的味道
"""
)

###############################################################
# Cross-correlation 熱力圖
###############################################################

st.subheader("🔁 0050 vs 00631L 跨日相關性（Cross-correlation）")

lags = list(range(lag_min, lag_max + 1))
corrs = []
for lag in lags:
    shifted = ret["ret_631L"].shift(lag)
    corr = ret["ret_50"].corr(shifted)
    corrs.append(corr)

corr_df = pd.DataFrame({"lag": lags, "corr": corrs})

fig_corr = go.Figure(
    data=go.Heatmap(
        z=[corr_df["corr"].values],
        x=corr_df["lag"].values,
        y=["相關係數"],
        colorscale="RdBu",
        zmid=0,
        text=[[f"{c:.2f}" for c in corrs]],
        texttemplate="%{text}",
        hovertemplate="lag = %{x}<br>corr = %{z:.3f}<extra></extra>",
    )
)
fig_corr.update_layout(
    xaxis_title="lag（正數 = 00631L 晚幾天）",
    yaxis_title="",
    height=250,
)

st.plotly_chart(fig_corr, use_container_width=True)

st.markdown(
    """
👉 **解讀：**

- **lag = 0**：00631L 與同一天 0050 的相關性  
- **lag = +1**：00631L 與「前一天的 0050」的相關性（也就是 00631L 晚一天反應）  

如果 **lag +1 的相關係數 > lag 0**，就有延遲一天補跌 / 補漲的味道。
"""
)

###############################################################
# 同日 / 隔日散佈圖
###############################################################

st.subheader("📈 同日 vs 隔日報酬散佈圖")

scatter_df = ret.copy()
scatter_df["date"] = scatter_df.index

col_a, col_b = st.columns(2)

with col_a:
    fig_same = px.scatter(
        scatter_df,
        x="ret_50",
        y="ret_631L",
        hover_name="date",
        labels={"ret_50": "0050 日報酬", "ret_631L": "00631L 日報酬"},
        title="同日報酬關係",
        opacity=0.6,
    )
    fig_same.add_hline(y=0, line_width=1, line_color="gray")
    fig_same.add_vline(x=0, line_width=1, line_color="gray")
    st.plotly_chart(fig_same, use_container_width=True)

with col_b:
    fig_next = px.scatter(
        scatter_df,
        x="ret_50",
        y="ret_631L_next",
        hover_name="date",
        labels={"ret_50": "0050 日報酬", "ret_631L_next": "00631L 隔日報酬"},
        title="隔日報酬關係",
        opacity=0.6,
    )
    fig_next.add_hline(y=0, line_width=1, line_color="gray")
    fig_next.add_vline(x=0, line_width=1, line_color="gray")
    st.plotly_chart(fig_next, use_container_width=True)

st.markdown(
    """
理論上，如果完全貼 2 倍：

- 同日圖上的點，應該大致落在斜率 2 的對角線附近  
- 如果反而是「隔日圖」比較貼近 2 倍，代表有延遲反應
"""
)

###############################################################
# 大跌事件對齊圖（Event Study）
###############################################################

st.subheader("📉 0050 大跌事件 — 00631L 是否隔天補跌？")

# 0050 單日大跌
big_drop_mask = ret["ret_50"] <= (drop_thresh / 100.0)
big_drop_dates = ret.index[big_drop_mask]

st.markdown(
    f"篩選條件：0050 單日報酬 ≤ **{drop_thresh:.1f}%**，共 **{len(big_drop_dates)}** 天"
)

if len(big_drop_dates) == 0:
    st.info("這段期間沒有符合條件的大跌日，可以放寬閾值或調整日期區間。")
else:
    records = []
    for d in big_drop_dates:
        # 事件前後 window 天（用曆日，實際會跳過週末）
        start_evt = d - pd.Timedelta(days=event_window)
        end_evt = d + pd.Timedelta(days=event_window)
        slice_ = ret.loc[start_evt:end_evt, "ret_631L"].copy()

        for idx, val in slice_.items():
            offset = (idx - d).days
            records.append(
                {
                    "event_date": d,
                    "offset": offset,
                    "ret_631L": val,
                }
            )

    evt_df = pd.DataFrame(records)
    mean_curve = (
        evt_df.groupby("offset")["ret_631L"]
        .mean()
        .reset_index()
        .sort_values("offset")
    )

    fig_evt = px.line(
        mean_curve,
        x="offset",
        y="ret_631L",
        markers=True,
        labels={"offset": "相對天數（0 = 0050 大跌當日）", "ret_631L": "00631L 平均日報酬"},
        title="0050 大跌事件附近，00631L 平均日報酬",
    )
    fig_evt.add_vline(x=0, line_color="black", line_dash="dash", annotation_text="事件日")
    fig_evt.add_vline(x=1, line_color="red", line_dash="dot", annotation_text="+1 日")

    st.plotly_chart(fig_evt, use_container_width=True)

    st.markdown(
        """
👉 **解讀方式：**

- 如果 offset = 0（事件當日）跌得不深，但 offset = +1（隔天）平均跌更多  
  → 代表 00631L 有 **隔天補跌** 的傾向  

這張圖就是把所有大跌事件「疊在一起」，看 00631L 在事件前後的平均反應。
"""
)

###############################################################
# 結尾說明
###############################################################

st.markdown(
    """
---

### 小結

1. 看上面的 **Cross-correlation 熱力圖**：  
   - 如果 **lag = 0** 最高 → 代表 00631L 大多數是「當天就反應」。  
   - 如果 **lag = +1** 比較高 → 代表更像「隔天才跟上 0050 的波動」。

2. 再配合 **散佈圖** 和 **大跌事件對齊圖**：  
   - 可以確認在極端行情時，有沒有「當天沒跌滿、隔天再補刀」的情況。

你之後如果想再加：
- 其他正 2（00675L、00663L…）切換  
- 多檔一起比較延遲程度  
- 或接到「倉鼠量化戰情室」裡當一頁工具  

都可以在這個架構上直接擴充。
"""
)
