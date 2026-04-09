# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import os

# --- 1. 網頁基礎配置 ---
st.set_page_config(page_title="台塑四寶七年策略分析系統", layout="wide")

# 設定中文字體（避免圖表亂碼）
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei'] 
plt.rcParams['axes.unicode_minus'] = False 

# --- 2. 萬能資料讀取函數 ---
@st.cache_data
def load_data():
    # 自動偵測所有可能的檔案路徑 (解決資料夾層級問題)
    possible_paths = [
        "四家七年.csv",
        "kent/四家七年.csv",
        "kent/kent/四家七年.csv"
    ]
    
    target_path = None
    for path in possible_paths:
        if os.path.exists(path):
            target_path = path
            break
            
    if target_path is None:
        # 如果真的找不到，顯示目前環境下的檔案清單供除錯
        st.error(f"❌ 找不到 CSV 檔案。目前目錄內容為：{os.listdir('.')}")
        return None

    # 自動處理編碼問題 (Big5 或 UTF-8)
    try:
        df = pd.read_csv(target_path, encoding='cp950', skiprows=1)
    except:
        try:
            df = pd.read_csv(target_path, encoding='utf-8-sig', skiprows=1)
        except Exception as e:
            st.error(f"❌ 檔案讀取失敗：{e}")
            return None

    # 整理資料格式
    df.columns = df.columns.str.strip()
    pivot_df = df.pivot(index='MDATE', columns='Name', values='CLOSE')
    pivot_df.index = pd.to_datetime(pivot_df.index, format='%Y%m%d')
    return pivot_df.sort_index().ffill()

# --- 3. 執行主程式 ---
data = load_data()

if data is not None:
    # 側邊選單設定
    st.sidebar.header("⚙️ 參數設定")
    stocks = data.columns.tolist()
    s1 = st.sidebar.selectbox("選擇股票 A", stocks, index=0)
    s2 = st.sidebar.selectbox("選擇股票 B", stocks, index=1)
    threshold = st.sidebar.slider("相關係數交易門檻", 0.0, 1.0, 0.5, 0.05)

    # --- 4. 時間切割邏輯 ---
    # 找到資料開始日，計算兩年（730天）後的分界點
    start_date = data.index.min()
    split_date = start_date + pd.Timedelta(days=730) 
    
    # 樣本內 (前 2 年)：純計算初始相關係數用，不進行交易
    insample = data[data.index < split_date]
    # 樣本外 (後 5 年)：正式顯示在網頁上的交易回測期
    outsample = data[data.index >= split_date]

    # 計算初始相關係數
    insample_ret = insample.pct_change().dropna()
    initial_corr = insample_ret[s1].corr(insample_ret[s2])

    # --- 5. 計算交易數據 (後 5 年) ---
    daily_ret = data.pct_change()
    m_first = data.resample('ME').first()
    m_last = data.resample('ME').last()
    m_ret = (m_last - m_first) / m_first

    results = []
    # 遍歷月份，僅處理分界點之後的月份
    for j in range(len(m_ret)):
        curr_dt = m_ret.index[j]
        
        # 排除前 2 年的資料，不顯示在表格與圖表
        if curr_dt < split_date:
            continue
            
        m_str = curr_dt.strftime('%Y-%m')
        m_corr = daily_ret.loc[m_str][s1].corr(daily_ret.loc[m_str][s2])
        r1, r2 = m_ret.loc[curr_dt, s1], m_ret.loc[curr_dt, s2]
        
        # 交易邏輯判斷 (參考前一個月的相關係數與表現)
        last_m_dt = m_ret.index[j-1]
        last_m_str = last_m_dt.strftime('%Y-%m')
        prev_corr = daily_ret.loc[last_m_str][s1].corr(daily_ret.loc[last_m_str][s2])
        
        if prev_corr < threshold:
            action, strat_ret = f"相關低({prev_corr:.2f})不交易", 0.0
        else:
            # 買弱賣強策略
            if m_ret.iloc[j-1][s1] > m_ret.iloc[j-1][s2]:
                action, strat_ret = f"買{s2}/賣{s1}", r2 - r1
            else:
                action, strat_ret = f"買{s1}/賣{s2}", r1 - r2
        
        results.append({
            "月份": m_str,
            f"{s1}月報酬%": round(r1 * 100, 2),
            f"{s2}月報酬%": round(r2 * 100, 2),
            "當月相關係數": round(m_corr, 4),
            "交易動作": action,
            "策略獲利%": round(strat_ret * 100, 2)
        })

    res_df = pd.DataFrame(results)
    cum_ret = (1 + res_df['策略獲利%']/100).cumprod() - 1

    # --- 6. 網頁顯示介面 ---
    st.title("🏛️ 台塑四寶：七年期配對交易分析系統")
    st.markdown(f"**模式說明**：前 2 年為參數觀察期（不交易），後 5 年為正式回測期。")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("初始相關係數 (前 2 年)", f"{initial_corr:.4f}")
    c2.metric("正式交易累積報酬 (後 5 年)", f"{cum_ret.iloc[-1]*100:.2f}%")
    c3.success(f"交易回測啟動日：{res_df['月份'].iloc[0]}")

    st.divider()

    st.subheader("📈 後 5 年正式交易期累積報酬走勢")
    st.line_chart(cum_ret * 100)

    st.subheader("📋 詳細交易明細 (後 5 年)")
    st.dataframe(res_df, use_container_width=True)

    # 提供報表下載
    csv_download = res_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 下載交易明細報表", csv_download, "backtest_report.csv", "text/csv")

else:
    # 這裡會因為前面 load_data 的錯誤處理而顯示具體訊息
    pass
