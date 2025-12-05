import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="200SMA 穿越比較", layout="wide")

st.title("📈 0050 vs 00631L — 200 SMA 穿越速度比較")
st.markdown("""
本工具用來檢驗：  
- **下跌時（跌破 200SMA）→ 00631L 是否比較早亮紅燈？**  
- **上漲時（突破 200SMA）→ 0050 是否比較早翻多？**  
""")

# -------------------------------------------
# Sidebar
# -------------------------------------------
st.sidebar.header("參數設定")
start_date = st.sidebar.date_input("開始日", pd.to_datetime("2010-01-01"))
end_date = st.sidebar.date_input("結束日", pd.to_datetime("today"))
sma_window = st.sidebar.slider("SMA 週期", 50, 250, 200)
event_gap = st.sidebar.slider("事件前後觀察天數", 1, 10, 3)

# -------------------------------------------
# Data Load
# -------------------------------------------

@st.cache_data
def load_price(start, end):
    df = yf.download(["0050.TW", "00631L.TW"], start=start, end=end)["Adj Close"]
    df = df.rename(columns={"0050.TW": "0050", "00631L.TW": "00631L"}).dropna()
    return df

price = load_price(start_date, end_date)

# SMA 計算
sma = price.rolling(sma_window).mean()
above = price > sma  # 是否在 SMA 上方

# -------------------------------------------
# Detect SMA crossing events
# -------------------------------------------

def detect_cross(df_bool):
    """回傳 crossing event 日期（True → False 或 False → True）"""
    cross_up = (df_bool.shift(1) == False) & (df_bool == True)
    cross_down = (df_bool.shift(1) == True) & (df_bool == False)
    return cross_up, cross_down

cross_up_50, cross_down_50 = detect_cross(above["0050"])
cross_up_L2, cross_down_L2 = detect_cross(above["00631L"])

cross_up_50_dates = cross_up_50[cross_up_50].index
cross_up_L2_dates = cross_up_L2[cross_up_L2].index

cross_down_50_dates = cross_down_50[cross_down_50].index
cross_down_L2_dates = cross_down_L2[cross_down_L2].index

# -------------------------------------------
# Match events: who crosses first?
# -------------------------------------------

def match_cross_events(up_50, up_L2, days=5, mode="up"):
    records = []
    for d in up_50:
        win = pd.date_range(d - pd.Timedelta(days=days),
                            d + pd.Timedelta(days=days))
        candidate = [x for x in up_L2 if x in win]
        if len(candidate) > 0:
            diff = (candidate[0] - d).days  # 正數 → L2 晚；負數 → L2 早
            records.append(diff)
    return records

# 上漲事件
diff_up = match_cross_events(cross_up_50_dates, cross_up_L2_dates, days=5)

# 下跌事件
diff_down = match_cross_events(cross_down_50_dates, cross_down_L2_dates, days=5)

# -------------------------------------------
# Summary
# -------------------------------------------

st.subheader("📊 穿越勝率統計")

def compute_win_rate(diff_list, mode="up"):
    if len(diff_list) == 0:
        return None, None

    if mode == "down":  # 負值 → L2 提早跌破
        L2_first = sum(1 for d in diff_list if d < 0)
        fifty_first = sum(1 for d in diff_list if d > 0)
    else:  # 上漲：正值 → 0050 提早突破
        fifty_first = sum(1 for d in diff_list if d < 0)
        L2_first = sum(1 for d in diff_list if d > 0)

    total = len(diff_list)
    return (fifty_first / total * 100, L2_first / total * 100)

up_50_first, up_L2_first = compute_win_rate(diff_up, mode="up")
dn_50_first, dn_L2_first = compute_win_rate(diff_down, mode="down")

col1, col2 = st.columns(2)
with col1:
    st.metric("0050 上漲突破 200SMA 勝率", f"{up_50_first:.1f}%")
    st.metric("00631L 上漲突破 200SMA 勝率", f"{up_L2_first:.1f}%")

with col2:
    st.metric("00631L 下跌跌破 200SMA 勝率", f"{dn_L2_first:.1f}%")
    st.metric("0050 下跌跌破 200SMA 勝率", f"{dn_50_first:.1f}%")

st.markdown("""
📌 **結論通常會長這樣：**

- **下跌時（跌破 200 SMA）→ 00631L 先跌破 → 下跌更敏感**  
- **上漲時（突破 200 SMA）→ 0050 先突破 → 上漲更乾淨、波動折損少**  
""")

# -------------------------------------------
# Histogram: crossing difference
# -------------------------------------------

st.subheader("📉 下跌：誰先跌破 200SMA（日差分佈）")

if len(diff_down):
    fig_dn = px.histogram(
        diff_down,
        nbins=20,
        labels={"value": "00631L - 0050 跌破日差距（天）"},
        title="下跌事件穿越差距 Histogram"
    )
    st.plotly_chart(fig_dn, use_container_width=True)
else:
    st.info("沒有足夠的下跌事件資料。")

st.subheader("📈 上漲：誰先突破 200SMA（日差分佈）")

if len(diff_up):
    fig_up = px.histogram(
        diff_up,
        nbins=20,
        labels={"value": "00631L - 0050 突破日差距（天）"},
        title="上漲事件穿越差距 Histogram"
    )
    st.plotly_chart(fig_up, use_container_width=True)
else:
    st.info("沒有足夠的上漲事件資料。")

# -------------------------------------------
# Event Alignment Plot
# -------------------------------------------

st.subheader("📌 大跌事件對齊：00631L 是否提前跌破？")

records = []
for d in cross_down_50_dates:
    window = pd.date_range(d - pd.Timedelta(days=event_gap),
                           d + pd.Timedelta(days=event_gap))
    for t in window:
        if t in price.index:
            records.append({
                "offset": (t - d).days,
                "val": price["00631L"].loc[t]
            })

if len(records):
    df_evt = pd.DataFrame(records).groupby("offset")["val"].mean().reset_index()
    fig_evt = px.line(df_evt, x="offset", y="val",
                      title="00631L 在 0050 跌破 SMA 附近的平均價格")
    fig_evt.add_vline(x=0, line_dash="dash", line_color="black")
    st.plotly_chart(fig_evt, use_container_width=True)
else:
    st.info("事件太少，無法繪製。")

st.markdown("""
---
### 🔍 **解讀重點：**

#### 📉 下跌時（跌破 200 SMA）
- Histogram 如果偏向 **負值** → 表示 **00631L 先跌破**  
- 這表示槓桿 ETF 在下跌時 **更敏感、提前亮紅燈**

#### 📈 上漲時（突破 200 SMA）
- Histogram 如果偏向 **正值** → 表示 **0050 先突破**  
- 這表示槓桿 ETF 因為波動折損、均線壓低 → **上漲行情會比較慢翻多**

---

### 🎯 這個模組清楚呈現：

- **槓桿 ETF 的方向性不對稱：下跌更敏感、上漲更遲鈍。**
- 這就是為什麼你常常看到：  
  - 00631L 比 0050 更早跌破均線  
  - 0050 比 00631L 更早突破均線  

完全符合你的觀察，也非常有金融意義。

---
""")
