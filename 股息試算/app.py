import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import io

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="ETF 萬能儀表板", page_icon="📈", layout="centered")

# --- 2. 側邊欄：檔案讀取與存檔功能 ---
st.sidebar.header("📁 資料管理中心")

# 初始化暫存資料
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []

# 功能 A：匯入 CSV 檔案
uploaded_file = st.sidebar.file_uploader("匯入現有的存股清單 (.csv)", type="csv")
if uploaded_file is not None:
    uploaded_df = pd.read_csv(uploaded_file)
    st.session_state.portfolio = uploaded_df.to_dict('records')
    st.sidebar.success("✅ 資料讀取成功！")

st.sidebar.divider()

# --- 3. 主頁面標題 ---
st.title("📱 ETF 萬能儀表板")
st.markdown("自動判定**股票(8.5%抵稅)**與**債券(海外所得)**之稅務差異")

# --- 4. 新增 ETF 區塊 ---
with st.expander("➕ 新增 ETF 到清單", expanded=len(st.session_state.portfolio) == 0):
    tab1, tab2 = st.tabs(["🔍 自動抓取 (推薦)", "✍️ 手動輸入"])

    with tab1:
        c1, c2, c3 = st.columns(3)
        aid = c1.text_input("ETF 代號", key="aid")
        ashares = c2.number_input("持有股數", min_value=0, step=1000, key="ashares")
        aratio = c3.number_input("54C 比例(%)", 0.0, 100.0, 100.0, key="aratio")
        
        if st.button("🔍 抓取並加入", use_container_width=True):
            if aid and ashares > 0:
                with st.spinner("連線 Yahoo 股市中..."):
                    try:
                        ticker_sym = f"{aid}.TW" if not aid.endswith(('.TW', '.TWO')) else aid
                        t = yf.Ticker(ticker_sym); h = t.history(period="1d"); d = t.dividends
                        if h.empty or d.empty:
                            t = yf.Ticker(f"{aid}.TWO"); h = t.history(period="1d"); d = t.dividends
                        
                        if not h.empty and not d.empty:
                            st.session_state.portfolio.append({
                                "代號": aid.upper(), "股數": int(ashares), "股價": float(h['Close'].iloc[-1]),
                                "本次配息": float(d.iloc[-1]), 
                                "過去一年配息": float(d[d.index >= (datetime.now()-timedelta(days=365)).strftime('%Y-%m-%d')].sum()),
                                "54C(%)": aratio
                            })
                            st.success(f"✅ {aid} 已加入！記得去左側點擊下載備份喔。")
                            st.rerun()
                        else: st.error("找不到資料。")
                    except Exception as e: st.error(f"抓取異常：{e}")

    with tab2:
        m1, m2, m3 = st.columns(3)
        mid = m1.text_input("代號", key="mid")
        mshares = m2.number_input("股數", min_value=0, step=1000, key="mshares")
        mprice = m1.number_input("股價", 0.0, key="mprice")
        mdiv = m2.number_input("配息", 0.0, key="mdiv")
        mratio = m3.number_input("手動54C%", 0.0, 100.0, 100.0, key="mratio")
        
        if st.button("✏️ 手動新增", use_container_width=True, type="primary"):
            if mid and mshares > 0:
                st.session_state.portfolio.append({
                    "代號": mid.upper(), "股數": int(mshares), "股價": float(mprice),
                    "本次配息": float(mdiv), "過去一年配息": float(mdiv), "54C(%)": float(mratio)
                })
                st.rerun()

# --- 5. 核心顯示與計算 ---
if st.session_state.portfolio:
    st.subheader("📝 庫存總覽")
    df = pd.DataFrame(st.session_state.portfolio)
    edited_df = st.data_editor(df, hide_index=True, use_container_width=True)
    
    if not df.equals(edited_df):
        st.session_state.portfolio = edited_df.to_dict('records')
        st.rerun()

    # --- 功能 B：匯出 CSV 檔案 (放在表格下方) ---
    csv_buffer = io.StringIO()
    edited_df.to_csv(csv_buffer, index=False)
    st.download_button(
        label="💾 下載目前清單備份 (.csv)",
        data=csv_buffer.getvalue(),
        file_name=f"my_etf_portfolio_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True
    )

    if st.button("🗑️ 清空全庫存"):
        st.session_state.portfolio = []
        st.rerun()

    # --- 稅務計算與指標 ---
    total_annual = 0; total_tax_deduct = 0; calc_results = []
    for _, row in edited_df.iterrows():
        etf_id = str(row["代號"]).upper()
        taxable = (row["股數"] * row["本次配息"]) * (row["54C(%)"] / 100)
        annual = row["股數"] * row["過去一年配息"]
        total_annual += annual
        if not etf_id.endswith('B'): total_tax_deduct += taxable * 0.085
        calc_results.append({
            "代號": etf_id, "應稅": f"{int(taxable):,}",
            "二代健保": "⚠️" if taxable >= 20000 else "✅", "年領": f"${int(annual):,}"
        })

    st.divider()
    st.subheader("📊 試算結果")
    st.dataframe(pd.DataFrame(calc_results), hide_index=True, use_container_width=True)
    c_a, c_b = st.columns(2)
    c_a.metric("💰 年度總股息", f"${int(total_annual):,}")
    c_b.metric("🎁 抵減稅額", f"${int(total_tax_deduct):,}")
