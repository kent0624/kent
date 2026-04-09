# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import os

# --- 網頁配置 ---
st.set_page_config(page_title="台塑四寶七年期策略回測", layout="wide")
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei'] 
plt.rcParams['axes.unicode_minus'] = False 

@st.cache_data
def load_data():
    file_path = "kent/四家七年.csv" 
    if not os.path.exists(file_path): return None
    try:
        df = pd.read_csv(file_path, encoding='cp950', skiprows=1)
        df.columns = df.columns.str.strip()
        pivot_df = df.pivot(index='MDATE', columns='Name', values='CLOSE')
        pivot_df.index = pd.to_datetime(pivot_df.index, format='%Y%m%d')
        return pivot_df.sort_index().ffill()
    except: return None

data = load_data()

if data is not None:
    # 側邊選單
    stocks = data.columns.tolist()
    s1 = st.sidebar.selectbox("選擇股票 A", stocks, index=0)
    s2 = st.sidebar.selectbox("選擇股票 B", stocks, index=1)
    threshold = st.sidebar.slider("相關係數交易門檻", 0.0, 1.0, 0.5, 0.05)

    # --- 1. 時間切割 ---
    # 找到資料開始日，計算兩年後的日期
    start_date = data.index.min()
    split_date = start_date + pd.Timedelta(days=730) 
    
    # 樣本內 (前 2 年)：純計算初始相關係數用
    insample = data[data.index < split_date]
    # 樣本外 (後 5 年)：這段才是我們要顯示在網頁上的「交易期」
    outsample = data[data.index >= split_date]

    # --- 2. 計算【初始相關係數】(只用前 2 年) ---
    insample_ret = insample.pct_change().dropna()
    initial_corr = insample_ret[s1].corr(insample_ret[s2])

    # --- 3. 處理報酬率與月資料 ---
    daily_ret = data.pct_change()
    
    # 取得「全期」的每月最後一天資料，但後續會過濾掉前兩年
    m_first = data.resample('ME').first()
    m_last = data.resample('ME').last()
    m_ret = (m_last - m_first) / m_first

    results = []
    # 遍歷所有月份，但「只有」在 split_date 之後的月份才放入 results
    for j in range(len(m_ret)):
        curr_dt = m_ret.index[j]
        
        # 核心判斷：如果這個月還在前兩年內，直接跳過不處理
        if curr_dt < split_date:
            continue
            
        m_str = curr_dt.strftime('%Y-%m')
        m_corr = daily_ret.loc[m_str][s1].corr(daily_ret.loc[m_str][s2])
        r1, r2 = m_ret.loc[curr_dt, s1], m_ret.loc[curr_dt, s2]
        
        # 交易邏輯判斷 (根據「前一個月」的表現)
        # 這裡的 j-1 即使在分界點，也能抓到前兩年最後一個月的表現來做為交易依據
        last_m_dt = m_ret.index[j-1]
        last_m_str = last_m_dt.strftime('%Y-%m')
        prev_corr = daily_ret.loc[last_m_str][s1].corr(daily_ret.loc[last_m_str][s2])
        
        if prev_corr < threshold:
            action, strat_ret = f"相關低({prev_corr:.2f})不交易", 0.0
        else:
            if m_ret.iloc[j-1][s1] > m_ret.iloc[j-1][s2]:
                action, strat_ret = f"買{s2}/賣{s1}", r2 - r1
            else:
                action, strat_ret = f"買{s1}/賣{s2}", r1 - r2
        
        results.append({
            "月份": m_str,
            f"{s1}報酬%": round(r1 * 100, 2),
            f"{s2}報酬%": round(r2 * 100, 2),
            "當月相關係數": round(m_corr, 4),
            "交易動作": action,
            "策略獲利%": round(strat_ret * 100, 2)
        })

    # 將結果轉成 DataFrame
    res_df = pd.DataFrame(results)
    
    # 計算累積報酬 (圖表會從 0% 開始起跳)
    cum_ret = (1 + res_df['策略獲利%']/100).cumprod() - 1

    # --- 4. 網頁介面 ---
    st.title("🏛️ 台塑四寶：七年期策略查詢系統")
    st.info(f"📊 模式：前 2 年為參數觀察期（不交易），後 5 年為正式回測期。")
    
    col1, col2, col3 = st.columns(3)
    col1.metric(f"初始相關係數 (前 2 年)", f"{initial_corr:.4f}")
    col2.metric(f"後 5 年累積總報酬", f"{cum_ret.iloc[-1]*100:.2f}%")
    col3.write(f"**觀察期結束：** {insample.index.max().date()}")
    col3.write(f"**交易期開始：** {res_df['月份'].iloc[0]}")

    st.divider()

    # 繪製走勢圖 (這張圖只會顯示後 5 年的累積報酬)
    st.subheader("📈 後 5 年正式交易期累積報酬走勢 (Out-of-Sample)")
    st.line_chart(cum_ret * 100)

    # 顯示明細表 (這張表也會從後 5 年的第一個月開始顯示)
    st.subheader("📋 詳細交易明細 (後 5 年資料)")
    st.dataframe(res_df, use_container_width=True)

else:
    st.error("找不到檔案 '四家七年.csv'。")
