import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="ETF 萬能儀表板", page_icon="📈", layout="centered")
st.title("📱 ETF 萬能儀表板")
st.markdown("自動判定**股票(8.5%抵稅)**與**債券(海外所得)**之稅務差異")

# --- 2. 初始化暫存資料 (Session State) ---
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []

# --- 3. 新增 ETF 區塊 ---
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
                        t = yf.Ticker(ticker_sym)
                        h = t.history(period="1d")
                        d = t.dividends
                        
                        if h.empty or d.empty:
                            t = yf.Ticker(f"{aid}.TWO"); h = t.history(period="1d"); d = t.dividends
                        
                        if not h.empty and not d.empty:
                            st.session_state.portfolio.append({
                                "代號": aid.upper(), "股數": int(ashares), "股價": float(h['Close'].iloc[-1]),
                                "本次配息": float(d.iloc[-1]), 
                                "過去一年配息": float(d[d.index >= (datetime.now()-timedelta(days=365)).strftime('%Y-%m-%d')].sum()),
                                "54C(%)": aratio
                            })
                            st.success(f"✅ {aid} 已加入清單！")
                            st.rerun()
                        elif not h.empty and d.empty:
                            st.warning(f"⚠️ 有抓到 {aid} 股價，但無配息資料，請改用「✍️ 手動輸入」。")
                        else:
                            st.error(f"❌ 找不到 {aid} 的資料。")
                    except Exception as e: 
                        st.error(f"❌ 抓取發生異常：{e}")

    with tab2:
        m1, m2, m3 = st.columns(3)
        mid = m1.text_input("代號", key="mid")
        mshares = m2.number_input("股數", min_value=0, step=1000, key="mshares")
        mprice = m1.number_input("股價", min_value=0.0, key="mprice")
        mdiv = m2.number_input("本次配息", min_value=0.0, key="mdiv")
        mannual = m3.number_input("全年配息", min_value=0.0, key="mannual")
        mratio = m3.number_input("手動54C%", 0.0, 100.0, 100.0, key="mratio")
        
        if st.button("✏️ 手動新增", use_container_width=True, type="primary"):
            if mid and mshares > 0:
                st.session_state.portfolio.append({
                    "代號": mid.upper(), "股數": int(mshares), "股價": float(mprice),
                    "本次配息": float(mdiv), "過去一年配息": float(mannual if mannual > 0 else mdiv),
                    "54C(%)": float(mratio)
                })
                st.success("✅ 手動資料已加入！")
                st.rerun()

# --- 4. 核心計算與顯示 ---
if st.session_state.portfolio:
    st.subheader("📝 庫存總覽")
    df = pd.DataFrame(st.session_state.portfolio)
    edited_df = st.data_editor(df, hide_index=True, use_container_width=True)
    
    # 若表格有修改，自動同步存回暫存區
    if not df.equals(edited_df):
        st.session_state.portfolio = edited_df.to_dict('records')
        st.rerun()

    if st.button("🗑️ 清空全庫存"):
        st.session_state.portfolio = []
        st.rerun()

    # --- 稅務與收益計算 ---
    total_annual_income = 0
    total_tax_deduct = 0
    calc_results = []

    for _, row in edited_df.iterrows():
        etf_id = str(row["代號"]).upper()
        shares = row["股數"]
        div = row["本次配息"]
        ratio = row["54C(%)"] / 100
        annual_div = row["過去一年配息"]

        annual_income = shares * annual_div
        total_annual_income += annual_income

        taxable_dividend = (shares * div) * ratio
        
        # 最聰明的稅務判斷：B結尾不計入抵稅
        if not etf_id.endswith('B'):
            total_tax_deduct += taxable_dividend * 0.085
        
        nhi_status = "⚠️ 需扣費" if taxable_dividend >= 20000 else "✅ 免扣"
        
        calc_results.append({
            "代號": etf_id,
            "單次應稅": f"{int(taxable_dividend):,}",
            "二代健保": nhi_status,
            "預估年領": f"${int(annual_income):,}"
        })

    st.divider()
    st.subheader("📊 稅務與收益試算結果")
    st.dataframe(pd.DataFrame(calc_results), hide_index=True, use_container_width=True)

    c_a, c_b = st.columns(2)
    c_a.metric("💰 預估年度總股息", f"${int(total_annual_income):,}")
    c_b.metric("🎁 預估可抵減稅額", f"${int(total_tax_deduct):,}")
    
    st.caption("💡 提示：此版本使用網頁暫存，關閉網頁後資料會重置，適合快速試算當前配置。")
