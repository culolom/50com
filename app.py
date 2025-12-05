###############################################################
# app.py — 0050 vs 00631L SMA 策略機率統計
###############################################################

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 頁面設定
st.set_page_config(
    page_title="0050 vs 00631L SMA 戰情室",
    layout="wide",
    initial_sidebar_state="collapsed" # 預設隱藏側邊欄
)

st.title("📊 0050 vs 00631L — SMA 趨勢與機率統計")

# 2. 上方控制面板 (使用 Form 避免更改參數就直接重跑，需按按鈕)
with st.form("param_form"):
    st.subheader("🛠️ 參數設定")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        start_date = st.date_input("開始日期", pd.to_datetime("2015-01-01"))
    with c2:
        end_date = st.date_input("結束日期", pd.to_datetime("today"))
    with c3:
        sma_window = st.number_input("SMA 均線週期 (日)", min_value=10, max_value=500, value=200, step=10)
    
    # 提交按鈕
    submitted = st.form_submit_button("🚀 開始回測", use_container_width=True)

###############################################################
# 資料下載函數
###############################################################
@st.cache_data
def load_data(start, end):
    tickers = ["0050.TW", "00631L.TW"]
    try:
        raw = yf.download(tickers, start=start, end=end, auto_adjust=False)
    except Exception as e:
        return None

    if raw.empty:
        return None

    df = pd.DataFrame()
    # 處理 yfinance 多層索引
    if isinstance(raw.columns, pd.MultiIndex):
        try:
            # 優先嘗試抓取 Adj Close
            if "Adj Close" in raw.columns.levels[0]:
                df = raw["Adj Close"].copy()
            elif "Close" in raw.columns.levels[0]:
                df = raw["Close"].copy()
            else:
                # 備用：嘗試用 xs
                df = raw.xs("Adj Close", axis=1, level=0, drop_level=True)
        except:
            # 最後手段
            try:
                df = raw.xs("Close", axis=1, level=0, drop_level=True)
            except:
                return None
    else:
        # 單層索引處理
        if "Adj Close" in raw.columns:
            df = raw[["Adj Close"]]
        elif "Close" in raw.columns:
            df = raw[["Close"]]
        else:
            df = raw
            
    # 重新命名與清理
    cols_map = {}
    for col in df.columns:
        if "0050" in str(col): cols_map[col] = "0050"
        elif "00631L" in str(col): cols_map[col] = "00631L"
    
    df = df.rename(columns=cols_map).dropna()
    
    # 確保兩欄都有
    if "0050" not in df.columns or "00631L" not in df.columns:
        return None
        
    return df

###############################################################
# 主邏輯 (只有在按下按鈕後執行)
###############################################################
if submitted:
    with st.spinner("正在下載資料並進行運算..."):
        price = load_data(start_date, end_date)
        
        if price is None or price.empty:
            st.error("❌ 無法下載資料，請檢查日期區間或網路連線。")
        else:
            # ---------------------------
            # 1. 計算 SMA
            # ---------------------------
            price["SMA_50"] = price["0050"].rolling(sma_window).mean()
            price["SMA_L"]  = price["00631L"].rolling(sma_window).mean()
            
            # 移除 SMA 計算前的空值
            df = price.dropna().copy()
            
            st.success(f"✅ 資料載入成功！區間: {df.index.min().date()} ~ {df.index.max().date()} (共 {len(df)} 個交易日)")

            # ---------------------------
            # 2. 繪製比較圖 (雙 Y 軸)
            # ---------------------------
            st.subheader(f"📈 0050 vs 00631L 價格與 {sma_window}SMA 比較")
            
            fig = make_subplots(specs=[[{"secondary_y": True}]])

            # 0050 (左軸) - 藍色系
            fig.add_trace(go.Scatter(x=df.index, y=df["0050"], name="0050 收盤價", 
                                     line=dict(color='rgba(0, 0, 255, 0.3)', width=1)), secondary_y=False)
            fig.add_trace(go.Scatter(x=df.index, y=df["SMA_50"], name=f"0050 {sma_window}SMA", 
                                     line=dict(color='blue', width=2)), secondary_y=False)

            # 00631L (右軸) - 紅色系
            fig.add_trace(go.Scatter(x=df.index, y=df["00631L"], name="00631L 收盤價", 
                                     line=dict(color='rgba(255, 0, 0, 0.3)', width=1)), secondary_y=True)
            fig.add_trace(go.Scatter(x=df.index, y=df["SMA_L"], name=f"00631L {sma_window}SMA", 
                                     line=dict(color='red', width=2)), secondary_y=True)

            fig.update_layout(
                title_text="雙軸對照圖 (左軸: 0050 / 右軸: 00631L)",
                hovermode="x unified",
                height=500,
                legend=dict(orientation="h", y=1.1)
            )
            
            # 設定 Y 軸標題
            fig.update_yaxes(title_text="0050 價格", secondary_y=False, title_font=dict(color="blue"))
            fig.update_yaxes(title_text="00631L 價格", secondary_y=True, title_font=dict(color="red"))
            
            st.plotly_chart(fig, use_container_width=True)

            # ---------------------------
            # 3. 統計機率
            # ---------------------------
            st.subheader(f"🎲 機率統計 (基於 {sma_window}SMA)")
            
            # 判斷條件
            # True = 在 SMA 上方 (多), False = 在 SMA 下方 (空)
            cond_L_bear = df["00631L"] < df["SMA_L"]  
            cond_L_bull = df["00631L"] > df["SMA_L"]
            cond_50_bear = df["0050"] < df["SMA_50"]
            cond_50_bull = df["0050"] > df["SMA_50"]
            
            total_days = len(df)
            
            # 計算四種情境的天數
            n1 = len(df[cond_L_bear & cond_50_bear]) # 雙空: L < SMA, 50 < SMA
            n2 = len(df[cond_L_bear & cond_50_bull]) # L空 50多: L < SMA, 50 > SMA
            n3 = len(df[cond_L_bull & cond_50_bear]) # L多 50空: L > SMA, 50 < SMA
            n4 = len(df[cond_L_bull & cond_50_bull]) # 雙多: L > SMA, 50 > SMA

            # 計算百分比
            p1 = (n1 / total_days) * 100
            p2 = (n2 / total_days) * 100
            p3 = (n3 / total_days) * 100
            p4 = (n4 / total_days) * 100

            # ---------------------------
            # 4. 顯示結果 Metrics (2x2 Grid)
            # ---------------------------
            
            # 第一列：00631L 在 SMA 下方
            st.markdown(f"#### 🐻 當 00631L < {sma_window}SMA 時 (空頭/修正)")
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric(
                    label=f"情境 1: 0050 也是 < {sma_window}SMA (雙空)",
                    value=f"{p1:.1f}%",
                    delta=f"{n1} 天",
                    delta_color="off" # 灰色
                )
            
            with col2:
                st.metric(
                    label=f"情境 2: 0050 卻是 > {sma_window}SMA (L弱50強)",
                    value=f"{p2:.1f}%",
                    delta=f"{n2} 天",
                    delta_color="off"
                )
            
            st.divider()

            # 第二列：00631L 在 SMA 上方
            st.markdown(f"#### 🐮 當 00631L > {sma_window}SMA 時 (多頭/強勢)")
            col3, col4 = st.columns(2)
            
            with col3:
                st.metric(
                    label=f"情境 3: 0050 卻是 < {sma_window}SMA (L強50弱)",
                    value=f"{p3:.1f}%",
                    delta=f"{n3} 天",
                    delta_color="off"
                )
            
            with col4:
                st.metric(
                    label=f"情境 4: 0050 也是 > {sma_window}SMA (雙多)",
                    value=f"{p4:.1f}%",
                    delta=f"{n4} 天",
                    delta_color="off"
                )

            # ---------------------------
            # 簡單總結
            # ---------------------------
            st.markdown("---")
            st.info(f"""
            **📊 統計解讀：**
            - **雙多 ({p4:.1f}%)** 與 **雙空 ({p1:.1f}%)** 是市場最常出現的一致性狀態 (合計 {p1+p4:.1f}%)。
            - **不一致狀態 ({p2+p3:.1f}%)** 通常發生在趨勢轉折處。
              - 如果 **情境 2 (L弱50強)** 比例高，可能代表槓桿 ETF 在震盪盤整中被耗損，而原型 0050 撐在線上。
              - 如果 **情境 3 (L強50弱)** 比例高，可能代表槓桿 ETF 對反彈反應較大，提早站上均線。
            """)

else:
    # 尚未按下按鈕時的提示
    st.info("👆 請在上方設定參數，並點擊「開始回測」按鈕以查看報告。")
