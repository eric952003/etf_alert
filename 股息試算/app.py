import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="ETF 雲端萬能儀表板", page_icon="📈", layout="centered")
st.title("📱 ETF 雲端萬能儀表板")
st.markdown("自動判定**股票(8.5%抵稅)**與**債券(海外所得)**之稅務差異")

# --- 2. 建立 Google Sheets 連線 ---
# 記得在 Streamlit Cloud 的 Secrets 中設定好 URL
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    try:
        # 讀取雲端資料，設定 ttl=0 確保每次拿到的都是最新資料
        return conn.read(ttl=0)
    except:
        return pd.DataFrame(columns=["代號", "股數", "股價", "本次配息", "過去一年配息", "54C(%)"])

df = get_data()

# --- 3. 新增 ETF 區塊 ---
with st.expander("➕ 新增 ETF 到雲端清單", expanded=df.empty):
    tab1, tab2 = st.tabs(["🔍 自動抓取 (推薦)", "✍️ 手動輸入"])

    # -----------------------------------------
    # 分頁 1：自動抓取 (具備升級版防呆機制)
    # -----------------------------------------
    with tab1:
        c1, c2, c3 = st.columns(3)
        aid = c1.text_input("ETF 代號", key="aid")
        ashares = c2.number_input("持有股數", min_value=0, step=1000, key="ashares")
        aratio = c3.number_input("54C 比例(%)", 0.0, 100.0, 100.0, key="aratio")
        
        if st.button("🔍 抓取並存入雲端", use_container_width=True):
            if aid and ashares > 0:
                with st.spinner("連線 Yahoo 股市中..."):
                    try:
                        ticker_sym = f"{aid}.TW" if not aid.endswith(('.TW', '.TWO')) else aid
                        t = yf.Ticker(ticker_sym)
                        h = t.history(period="1d")
                        d = t.dividends
                        
                        if h.empty or d.empty:
                            t = yf.Ticker(f"{aid}.TWO")
                            h = t.history(period="1d")
                            d = t.dividends
                        
                        # 情況 A：股價和配息都有抓到 -> 正常寫入
                        if not h.empty and not d.empty:
                            new_row = pd.DataFrame([{
                                "代號": aid.upper(), "股數": int(ashares), "股價": float(h['Close'].iloc[-1]),
                                "本次配息": float(d.iloc[-1]), 
                                "過去一年配息": float(d[d.index >= (datetime.now()-timedelta(days=365)).strftime('%Y-%m-%d')].sum()),
                                "54C(%)": aratio
                            }])
                            updated_df = pd.concat([df, new_row], ignore_index=True)
                            conn.update(data=updated_df)
                            st.success(f"✅ {aid} 已同步至雲端！")
                            st.rerun()
                            
                        # 情況 B：有股價，但 Yahoo 沒給配息資料 -> 提示手動輸入
                        elif not h.empty and d.empty:
                            st.warning(f"⚠️ 有抓到 {aid} 的股價，但 Yahoo 暫時無法提供配息資料！請切換至「✍️ 手動輸入」。")
                            
                        # 情況 C：什麼都沒抓到
                        else:
                            st.error(f"❌ 找不到 {aid} 的資料，請確認代號是否正確。")
                            
                    except Exception as e: 
                        # 把真實的錯誤訊息印出來
                        st.error(f"❌ 抓取過程發生異常，系統錯誤訊息：{e}")

    # -----------------------------------------
    # 分頁 2：全手動輸入
    # -----------------------------------------
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
                new_row = pd.DataFrame([{
                    "代號": mid.upper(), "股數": int(mshares), "股價": float(mprice),
                    "本次配息": float(mdiv), "過去一年配息": float(mannual if mannual > 0 else mdiv),
                    "54C(%)": float(mratio)
                }])
                updated_df = pd.concat([df, new_row], ignore_index=True)
                conn.update(data=updated_df)
                st.success("✅ 手動資料已存入雲端！")
                st.rerun()

# --- 4. 核心計算與顯示 ---
if not df.empty:
    st.subheader("📝 雲端庫存總覽")
    edited_df = st.data_editor(df, hide_index=True, use_container_width=True)
    
    col_save, col_refresh, col_clear = st.columns(3)
    if col_save.button("💾 儲存表格修改", use_container_width=True):
        conn.update(data=edited_df)
        st.success("☁️ 雲端修改已儲存")
        st.rerun()
    if col_refresh.button("🔄 刷新頁面", use_container_width=True):
        st.rerun()
    if col_clear.button("🗑️ 清空全庫存", use_container_width=True):
        conn.update(data=pd.DataFrame(columns=df.columns))
        st.rerun()

    # --- 稅務與收益計算 ---
    total_annual_income = 0
    total_tax_deduct = 0
    calc_results = []

    for _, row in edited_df.iterrows():
        etf_id = str(row["代號"]).upper()
        shares = row["股數"]
        price = row["股價"]
        div = row["本次配息"]
        ratio = row["54C(%)"] / 100
        annual_div = row["過去一年配息"]

        # 年度預估總額
        annual_income = shares * annual_div
        total_annual_income += annual_income

        # 稅務計算
        taxable_dividend = (shares * div) * ratio
        
        # 關鍵判斷：如果代號結尾不是 'B'，才計算抵減稅額
        current_deduct = 0
        if not etf_id.endswith('B'):
            current_deduct = taxable_dividend * 0.085
            total_tax_deduct += current_deduct
        
        # 健保判斷
        nhi_status = "⚠️ 需扣費" if taxable_dividend >= 20000 else "✅ 免扣"
        
        calc_results.append({
            "代號": etf_id,
            "單次應稅": f"{int(taxable_dividend):,}",
            "二代健保": nhi_status,
            "預估年領": f"${int(annual_income):,}"
        })

    # --- 顯示總結數據 ---
    st.divider()
    st.subheader("📊 稅務與收益試算結果")
    st.dataframe(pd.DataFrame(calc_results), hide_index=True, use_container_width=True)

    c_a, c_b = st.columns(2)
    c_a.metric("💰 預估年度總股息", f"${int(total_annual_income):,}")
    c_b.metric("🎁 預估可抵減稅額", f"${int(total_tax_deduct):,}")

    st.caption("註：抵減稅額僅針對國內股票型 ETF 計算，債券 ETF (代號 B 結尾) 視為海外所得不計入。")
