import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="ETF 雲端儀表板", page_icon="☁️", layout="centered")
st.title("📱 ETF 雲端萬能儀表板")

# --- 2. 建立 Google Sheets 連線 ---
# 注意：在 Streamlit Cloud 部署時，需在 Secrets 設定 URL
conn = st.connection("gsheets", type=GSheetsConnection)

# 讀取現有資料
try:
    df = conn.read(ttl="10m") # 每 10 分鐘快取一次，避免頻繁抓取
except:
    # 如果是空表，建立初始格式
    df = pd.DataFrame(columns=["代號", "股數", "股價", "本次配息", "過去一年配息", "54C(%)"])

# --- 3. 新增 ETF 功能 (以自動抓取為例) ---
# --- 修正後的自動抓取區塊 ---
with st.expander("➕ 新增 ETF 到雲端清單", expanded=True):
    aid = st.text_input("ETF 代號 (例: 00878)", key="input_aid")
    ashares = st.number_input("持有股數", min_value=0, step=1000, key="input_shares")
    
    if st.button("🚀 執行自動抓取並同步雲端", use_container_width=True):
        if aid and ashares > 0:
            with st.spinner("正在連線 Yahoo 股市並同步至 Google Sheets..."):
                try:
                    # 1. 抓取資料
                    ticker_sym = f"{aid}.TW" if not aid.endswith(('.TW', '.TWO')) else aid
                    t = yf.Ticker(ticker_sym)
                    h = t.history(period="1d")
                    d = t.dividends
                    
                    if h.empty or d.empty:
                        t = yf.Ticker(f"{aid}.TWO")
                        h = t.history(period="1d")
                        d = t.dividends
                    
                    if not h.empty:
                        price = float(h['Close'].iloc[-1])
                        div = float(d.iloc[-1])
                        annual_div = float(d[d.index >= (datetime.now()-timedelta(days=365)).strftime('%Y-%m-%d')].sum())
                        
                        # 2. 準備新資料
                        new_row = pd.DataFrame([{
                            "代號": aid, 
                            "股數": int(ashares), 
                            "股價": price,
                            "本次配息": div, 
                            "過去一年配息": annual_div,
                            "54C(%)": 100.0
                        }])
                        
                        # 3. 讀取最新雲端資料並合併 (確保不會覆蓋掉現有的)
                        current_df = conn.read(ttl=0) # ttl=0 強制抓最新，不使用快取
                        updated_df = pd.concat([current_df, new_row], ignore_index=True)
                        
                        # 4. 寫回雲端
                        conn.update(data=updated_df)
                        
                        st.success(f"✅ {aid} 已成功同步至雲端！")
                        # 5. 強制重整頁面，讓下方表格抓到新資料
                        st.rerun()
                    else:
                        st.error("❌ 找不到該代號的配息資料，請檢查代號是否正確。")
                except Exception as e:
                    st.error(f"❌ 抓取或同步失敗: {e}")
        else:
            st.warning("⚠️ 請輸入代號與股數！")
# --- 4. 顯示與即時計算 ---
if not df.empty:
    st.subheader("📝 雲端庫存清單")
    # 使用資料編輯器，修改後可直接更新雲端
    edited_df = st.data_editor(df, hide_index=True, use_container_width=True)
    
    if st.button("💾 儲存修改內容"):
        conn.update(data=edited_df)
        st.success("☁️ 雲端資料已更新！")
        st.rerun()

    # 計算邏輯 (與先前一致)
    total_annual = 0
    calc_list = []
    for _, r in edited_df.iterrows():
        taxable = r["股數"] * r["本次配息"] * (r["54C(%)"]/100)
        annual = r["股數"] * r["過去一年配息"]
        total_annual += annual
        calc_list.append({
            "代號": r["代號"],
            "二代健保": "⚠️" if taxable >= 20000 else "✅ 免扣",
            "預估年領": f"${int(annual):,}"
        })
    
    st.table(pd.DataFrame(calc_list))
    st.metric("💰 預估年度總收益", f"${int(total_annual):,}")
