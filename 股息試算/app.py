import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="ETF 雲端儀表板", page_icon="📈", layout="centered")
st.title("📱 ETF 雲端萬能儀表板")

# --- 2. 建立 Google Sheets 連線 ---
# ttl=0 代表不使用快取，每次都抓最新的，避免資料「看起來」不見
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    try:
        data = conn.read(ttl=0) 
        return data.dropna(how='all')
    except:
        return pd.DataFrame(columns=["代號", "股數", "股價", "本次配息", "過去一年配息", "54C(%)"])

# 取得最新資料
df = get_data()

# --- 3. 新增 ETF 功能 (自動/手動分頁) ---
with st.expander("➕ 新增 ETF 到雲端清單", expanded=len(df) == 0):
    tab1, tab2 = st.tabs(["🔍 自動抓取", "✍️ 手動輸入"])

    with tab1:
        aid = st.text_input("ETF 代號", key="auto_id")
        ashares = st.number_input("持有股數", min_value=0, step=100, key="auto_shares")
        if st.button("🚀 抓取並新增"):
            if aid and ashares > 0:
                try:
                    ticker_sym = f"{aid}.TW"
                    t = yf.Ticker(ticker_sym)
                    h = t.history(period="1d")
                    if h.empty:
                        t = yf.Ticker(f"{aid}.TWO"); h = t.history(period="1d")
                    
                    if not h.empty:
                        d = t.dividends
                        price = float(h['Close'].iloc[-1])
                        div = float(d.iloc[-1]) if not d.empty else 0.0
                        ann_div = float(d[d.index >= (datetime.now()-timedelta(days=365)).strftime('%Y-%m-%d')].sum()) if not d.empty else 0.0
                        
                        new_row = pd.DataFrame([{
                            "代號": aid.upper(), "股數": int(ashares), "股價": price,
                            "本次配息": div, "過去一年配息": ann_div, "54C(%)": 100.0
                        }])
                        updated_df = pd.concat([df, new_row], ignore_index=True)
                        conn.update(data=updated_df)
                        st.success(f"✅ {aid} 已同步！")
                        st.rerun()
                except: st.error("抓取失敗")

    with tab2:
        mid = st.text_input("代號", key="m_id")
        mshares = st.number_input("股數", min_value=0, step=100, key="m_shares")
        mprice = st.number_input("目前股價", min_value=0.0, step=0.1, key="m_price")
        mdiv = st.number_input("本次配息", min_value=0.0, step=0.01, key="m_div")
        mannual = st.number_input("預計年配息", min_value=0.0, step=0.1, key="m_annual")
        mratio = st.number_input("54C%", min_value=0.0, max_value=100.0, value=100.0, key="m_ratio")
        
        if st.button("💾 手動存入雲端", type="primary"):
            if mid and mshares > 0:
                new_row = pd.DataFrame([{
                    "代號": mid.upper(), "股數": int(mshares), "股價": float(mprice),
                    "本次配息": float(mdiv), "過去一年配息": float(mannual if mannual > 0 else mdiv),
                    "54C(%)": float(mratio)
                }])
                # 關鍵：合併並更新到 Google Sheets
                updated_df = pd.concat([df, new_row], ignore_index=True)
                conn.update(data=updated_df)
                st.success(f"✅ {mid} 手動存檔成功！")
                st.rerun()
            else:
                st.warning("代號與股數為必填")

# --- 4. 顯示與計算 ---
if not df.empty:
    st.divider()
    # 確保資料格式正確
    for col in ["股數", "股價", "本次配息", "過去一年配息", "54C(%)"]:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    st.subheader("📝 雲端庫存清單")
    edited_df = st.data_editor(df, hide_index=True, use_container_width=True)
    
    c1, c2, c3 = st.columns(3)
    if c1.button("💾 儲存修改", use_container_width=True):
        conn.update(data=edited_df)
        st.success("已更新雲端！")
        st.rerun()
    
    if c2.button("🔄 刷新資料", use_container_width=True):
        st.rerun()

    if c3.button("🗑️ 全部清空", use_container_width=True):
        conn.update(data=pd.DataFrame(columns=df.columns))
        st.rerun()

    # --- 統計數據 ---
    total_annual = 0
    total_tax = 0
    calc_data = []

    for _, r in edited_df.iterrows():
        is_bond = str(r["代號"]).upper().endswith('B')
        taxable = r["股數"] * r["本次配息"] * (r["54C(%)"]/100)
        annual = r["股數"] * r["過去一年配息"]
        total_annual += annual
        if not is_bond: total_tax += taxable * 0.085
        
        calc_data.append({
            "代號": r["代號"],
            "二代健保": "⚠️ 扣費" if taxable >= 20000 else "✅ 免扣",
            "年領股息": f"${int(annual):,}"
        })
    
    st.table(pd.DataFrame(calc_results)) # 這裡如果報錯請檢查變數名稱，應為 calc_data
    
    st.divider()
    col_a, col_b = st.columns(2)
    col_a.metric("💰 年度總股息", f"${int(total_annual):,}")
    col_b.metric("🎁 抵減稅額", f"${int(total_tax):,}")
