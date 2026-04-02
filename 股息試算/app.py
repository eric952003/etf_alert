import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="ETF 雲端儀表板", page_icon="📈", layout="centered")
st.title("📱 ETF 雲端萬能儀表板")

# --- 2. 建立 Google Sheets 連線 ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    try:
        # 讀取資料並清掉全空的行列
        data = conn.read(ttl="0") 
        return data.dropna(how='all')
    except:
        return pd.DataFrame(columns=["代號", "股數", "股價", "本次配息", "過去一年配息", "54C(%)"])

df = get_data()

# --- 3. 新增 ETF 功能 ---
with st.expander("➕ 新增 ETF 到雲端清單"):
    aid = st.text_input("ETF 代號 (例: 00720B)")
    ashares = st.number_input("持有股數", min_value=0, step=100)
    if st.button("🚀 抓取並存入雲端"):
        with st.spinner("同步至 Google 雲端中..."):
            try:
                # 優先嘗試 .TW，不行就 .TWO
                ticker_sym = f"{aid}.TW"
                t = yf.Ticker(ticker_sym)
                h = t.history(period="1d")
                if h.empty:
                    ticker_sym = f"{aid}.TWO"
                    t = yf.Ticker(ticker_sym)
                    h = t.history(period="1d")
                
                d = t.dividends
                if not h.empty:
                    price = float(h['Close'].iloc[-1])
                    div = float(d.iloc[-1]) if not d.empty else 0.0
                    ann_div = float(d[d.index >= (datetime.now()-timedelta(days=365)).strftime('%Y-%m-%d')].sum()) if not d.empty else 0.0
                    
                    new_row = pd.DataFrame([{
                        "代號": aid.upper(), "股數": int(ashares), "股價": price,
                        "本次配息": div, "過去一年配息": ann_div, "54C(%)": 100.0
                    }])
                    updated_df = pd.concat([df, new_row], ignore_index=True)
                    conn.update(data=updated_df)
                    st.success(f"✅ {aid} 已同步至雲端！")
                    st.rerun()
            except Exception as e:
                st.error(f"抓取失敗: {e}")

# --- 4. 顯示與即時計算 ---
if not df.empty:
    st.subheader("📝 雲端庫存清單")
    # 強制轉換欄位型態，確保計算不會出錯
    df["股數"] = pd.to_numeric(df["股數"], errors='coerce').fillna(0)
    df["股價"] = pd.to_numeric(df["股價"], errors='coerce').fillna(0)
    df["本次配息"] = pd.to_numeric(df["本次配息"], errors='coerce').fillna(0)
    df["過去一年配息"] = pd.to_numeric(df["過去一年配息"], errors='coerce').fillna(0)
    df["54C(%)"] = pd.to_numeric(df["54C(%)"], errors='coerce').fillna(100)

    edited_df = st.data_editor(df, hide_index=True, use_container_width=True)
    
    col_btn1, col_btn2 = st.columns(2)
    if col_btn1.button("💾 儲存修改內容", use_container_width=True):
        conn.update(data=edited_df)
        st.success("☁️ 雲端資料已更新！")
        st.rerun()
    
    if col_btn2.button("🗑️ 清空所有庫存", use_container_width=True):
        empty_df = pd.DataFrame(columns=df.columns)
        conn.update(data=empty_df)
        st.rerun()

    # --- 計算指標 ---
    total_annual_income = 0
    total_tax_deduct = 0
    calc_list = []

    for _, r in edited_df.iterrows():
        # 債券 ETF 判斷 (代號結尾為 B 則不計入抵減稅額)
        is_bond = str(r["代號"]).upper().endswith('B')
        
        # 本次配息計算
        this_div_total = r["股數"] * r["本次配息"]
        taxable = this_div_total * (r["54C(%)"] / 100)
        
        # 年度收益計算
        annual_income = r["股數"] * r["過去一年配息"]
        total_annual_income += annual_income
        
        # 抵減稅額 (債券 ETF 歸零)
        if not is_bond:
            total_tax_deduct += taxable * 0.085
        
        calc_list.append({
            "代號": r["代號"],
            "二代健保": "⚠️ 扣費" if taxable >= 20000 else "✅ 免扣",
            "單次殖利率": f"{(r['本次配息']/r['股價']*100):.2f}%" if r['股價'] > 0 else "0%",
            "預估年領股息": f"${int(annual_income):,}"
        })
    
    st.divider()
    st.subheader("📊 收益統計")
    st.dataframe(pd.DataFrame(calc_list), hide_index=True, use_container_width=True)
    
    c1, c2 = st.columns(2)
    # 使用字串格式化後的變數，避免直接在 metric 裡做複雜運算
    income_val = f"${int(total_annual_income):,}"
    tax_val = f"${int(total_tax_deduct):,}"
    
    c1.metric("💰 預估年度總收益", income_val)
    c2.metric("🎁 預估可抵減稅額", tax_val)
    st.caption("註：若為債券 ETF (代號 B 結尾)，系統會自動將抵減稅額設為 $0。")
