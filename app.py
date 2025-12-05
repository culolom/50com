import streamlit as st
import yfinance as yf
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

st.title("0050 vs 00631L 反應延遲檢驗")

# Sidebar inputs
start = st.sidebar.date_input("開始日", pd.to_datetime("2018-01-01"))
end = st.sidebar.date_input("結束日", pd.to_datetime("today"))
lag_min = st.sidebar.number_input("最小 lag", -5, 0, -2)
lag_max = st.sidebar.number_input("最大 lag", 0, 5, 2)
drop_thresh = st.sidebar.number_input("大跌閾值 (0050 日報酬%)", -20.0, 0.0, -5.0)

# Download data
tickers = ["0050.TW", "00631L.TW"]
df = yf.download(tickers, start=start, end=end)["Adj Close"].dropna()
ret = df.pct_change().dropna()
ret.columns = ["0050", "00631L"]

# Cross-correlation
lags = range(lag_min, lag_max + 1)
corrs = []
for lag in lags:
    shifted = ret["00631L"].shift(lag)
    corr = ret["0050"].corr(shifted)
    corrs.append(corr)
corr_df = pd.DataFrame({"lag": lags, "corr": corrs}).set_index("lag")

st.subheader("跨日相關性熱力圖")
fig, ax = plt.subplots()
sns.heatmap(corr_df.T, annot=True, cmap="coolwarm", center=0, ax=ax)
st.pyplot(fig)
st.write("解讀：如果 lag +1 相關係數高於 lag 0，代表 00631L 隔天才反應。")

# Big drop alignment
st.subheader("大跌事件對齊")
big_drop_dates = ret[ret["0050"] <= drop_thresh / 100].index
window = 2  # 事件前後天數，可做成 sidebar 控制
aligned = []
for d in big_drop_dates:
    slice_ = ret.loc[d - pd.Timedelta(days=window): d + pd.Timedelta(days=window), "00631L"]
    slice_.index = (slice_.index - d).days  # 將日期轉為相對天數
    aligned.append(slice_)
if aligned:
    aligned_df = pd.concat(aligned, axis=1)
    fig2, ax2 = plt.subplots()
    sns.lineplot(data=aligned_df, ci=None, ax=ax2)
    ax2.axvline(0, color="black", linestyle="--")
    ax2.set_xlabel("相對天數 (0 = 0050 大跌當日)")
    ax2.set_ylabel("00631L 日報酬")
    st.pyplot(fig2)
    st.write("觀察 00631L 是否在 +1 天出現補跌。")
else:
    st.info("無符合閾值的大跌事件，可調整閾值或日期範圍。")
