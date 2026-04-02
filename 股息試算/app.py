import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="ETF 雲端儀表板", page_icon="☁️", layout="centered")
st.title("📱 ETF 雲端萬能儀表板")

# --- 2. 建立 Google Sheets 連線 ---
conn = st.connection("gsheets", type=GSheetsConnection)

# 讀取現有雲端資料 (設定 ttl=0 確保每次重新整理都是最新的)
try:
    df = conn.read(ttl=0)
except:
    # 如果讀取失敗或表單是空的，建立初始格式
    df = pd.DataFrame(columns=["代號", "股數", "股價", "本次配息", "過去一年配息", "54C(%)"])

# --- 3. 新增 ETF 區塊 (包含自動與手動分頁) ---
with st.expander("➕ 新增 ETF 到雲端清單", expanded=df.empty):
    tab1, tab2 = st.tabs(["🔍 自動抓取", "✍️ 全手動輸入"])

    # --- 分頁 1：自動抓取 ---
    with tab1:
        col1, col2 = st.columns(2)
        auto_id = col1.text_input("ETF 代號 (例: 00878)", key="auto_id")
        auto_shares = col2.number_input("持有股數", min_value=0, step=1000, key="auto_shares")
        
        if st.button("🚀 自動抓取並同步雲端", use_container_width=True):
            if auto_id and auto_shares > 0:
                with st.spinner("連線 Yahoo 股市中..."):
                    try:
                        ticker_sym = f"{auto_id}.TW" if not auto_id.endswith(('.TW', '.TWO')) else auto_id
                        t = yf.Ticker(ticker_sym)
                        h = t.history(period="1d")
                        d = t.dividends
                        if h.empty: # 嘗試上櫃
                            t = yf.Ticker(f"{auto_id}.TWO"); h = t.history(period="1d"); d = t.dividends
                        
                        if not h.empty:
                            new_row = pd.DataFrame([{
                                "代號": auto_id, 
                                "股數": int(auto_shares), 
                                "股價": float(h['Close'].iloc[-1]),
                                "本次配息": float(d.iloc[-1]) if not d.empty else 0.0, 
                                "過去一年配息": float(d[d.index >= (datetime.now()-timedelta(days=365)).strftime('%Y-%m-%d')].sum()) if not d.empty else 0.0,
                                "54C(%)": 100.0
                            }])
                            updated_df = pd.concat([df, new_row], ignore_index=True)
                            conn.update(data=updated_df)
                            st.success(f"✅ {auto_id} 已同步至雲端！")
                            st.rerun()
                        else:
                            st.error("❌ 找不到資料，請嘗試手動輸入。")
                    except Exception as e:
                        st.error(f"❌ 錯誤: {e}")

    # --- 分頁 2：全手動輸入 ---
    with tab2:
        m_col1, m_col2 = st.columns(2)
        with m_col1:
            m_id = st.text_input("代號/名稱", key="m_id")
            m_price = st.number_input("最新股價", min_value=0.0, key="m_price")
            m_ratio = st.number_input("54C 比例 (%)", 0.0, 100.0, 100.0, key="m_ratio")
        with m_col2:
            m_shares = st.number_input("持有股數", min_value=0, step=1000, key="m_shares")
            m_div = st.number_input("本次配息金額", min_value=0.0, key="m_div")
            m_annual = st.number_input("全年預估配息", min_value=0.0, key="m_annual")
            
        if st.button("✏️ 手動存入雲端", use_container_width=True, type="primary"):
            if m_id and m_shares > 0:
                new_row = pd.DataFrame([{
                    "代號": m_id, "股數": int(m_shares), "股價": m_price,
                    "本次配息": m_div, "過去一年配息": m_annual if m_annual > 0 else m_div,
                    "54C(%)": m_ratio
                }])
                updated_df = pd.concat([df, new_row], ignore_index=True)
                conn.update(data=updated_df)
                st.success(f"✅ {m_id} 已手動存入雲端！")
                st.rerun()
            else:
                st.warning("⚠️ 請填寫代號與股數！")

# --- 4. 顯示與即時計算 ---
if not df.empty:
    st.divider()
    st.subheader("📝 雲端庫存清單")
    st.caption("💡 提示：修改表格後請點擊下方「儲存修改」按鈕同步雲端。")
    
    # 讓表格寬度自適應
    edited_df = st.data_editor(df, hide_index=True, use_container_width=True)
    
    col_save, col_clear = st.columns([1, 1])
    if col_save.button("💾 儲存修改內容", use_container_width=True):
        conn.update(data=edited_df)
        st.success("☁️ 雲端資料已更新！")
        st.rerun()
        
    if col_clear.button("🗑️ 清空所有庫存", use_container_width=True):
        empty_df = pd.DataFrame(columns=["代號", "股數", "股價", "本次配息", "過去一年配息", "54C(%)"])
        conn.update(data=empty_df)
        st.rerun()

    # --- 計算報表 ---
    calc_results = []
    total_annual = 0
    total_tax_deduct = 0
    alert_count = 0

    for _, row in edited_df.iterrows():
        shares = int(row["股數"])
        div = float(row["本次配息"])
        ratio = float(row["54C(%)"]) / 100
        annual_div = float(row["過去一年配息"])

        taxable = shares * div * ratio
        annual_income = shares * annual_div
        
        total_annual += annual_income
        total_tax_deduct += taxable * 0.085
        
        nhi_status = f"⚠️ 扣 {int(taxable*0.0211):,}" if taxable >= 20000 else "✅ 免扣"
        if taxable >= 20000: alert_count += 1
            
        calc_results.append({
            "代號": row["代號"],
            "二代健保": nhi_status,
            "預估年領股息": f"${int(annual_income):,}",
            "免扣上限(股)": f"{int(19999/(div*ratio)):,}" if (div*ratio) > 0 else "無上限"
        })

    st.subheader("📊 健檢與收益分析")
    st.dataframe(pd.DataFrame(calc_results), hide_index=True, use_container_width=True)

    # 指標顯示
    c_a, c_b, c_c = st.columns(3)
    c_a.metric("💰 預估年領股息", f"${int(total_annual):,}")
    c_b.metric("🎁 預估抵減稅額", f"${int(total_tax_deduct):,}")
    if alert_count > 0:
        c_c.error(f"⚠️ {alert_count} 檔超標")
    else:
        c_c.success("✅ 全數安全")
