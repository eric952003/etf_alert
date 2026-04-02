import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="ETF 存股儀表板", page_icon="📈", layout="centered")
st.title("📱 ETF 存股萬能儀表板")
st.markdown("隨時隨地監控你的**預估股息**與**二代健保**狀態！")

# --- 2. 初始化暫存資料 (Session State) ---
# 這樣網頁重新整理時，你的庫存才不會不見
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []

# --- 3. 上方區塊：新增 ETF ---
with st.expander("➕ 新增 ETF 到庫存清單", expanded=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        new_id = st.text_input("ETF 代號 (例: 00878)")
    with col2:
        new_shares = st.number_input("持有股數", min_value=0, step=1000)
    with col3:
        new_ratio = st.number_input("54C 比例 (%)", min_value=0.0, max_value=100.0, value=100.0)

    if st.button("🔍 自動抓取並新增", use_container_width=True):
        if new_id and new_shares > 0:
            with st.spinner('連線至 Yahoo 股市抓取資料中...'):
                try:
                    # 處理台股代號後綴
                    ticker_sym = f"{new_id}.TW" if not new_id.endswith(('.TW', '.TWO')) else new_id
                    ticker = yf.Ticker(ticker_sym)
                    hist = ticker.history(period="1d")
                    divs = ticker.dividends
                    
                    # 如果上市找不到，找上櫃
                    if hist.empty or divs.empty:
                        ticker = yf.Ticker(f"{new_id}.TWO")
                        hist = ticker.history(period="1d")
                        divs = ticker.dividends
                        
                    if not hist.empty and not divs.empty:
                        price = float(hist['Close'].iloc[-1])
                        div = float(divs.iloc[-1])
                        
                        # 計算過去一年的總配息 (TTM)
                        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
                        annual_div = float(divs[divs.index >= start_date].sum())
                        
                        # 存入清單
                        st.session_state.portfolio.append({
                            "代號": new_id,
                            "股數": int(new_shares),
                            "股價": price,
                            "本次配息": div,
                            "過去一年配息": annual_div,
                            "54C(%)": new_ratio
                        })
                        st.success(f"✅ 成功加入 {new_id}！")
                    else:
                        st.error("⚠️ 找不到此 ETF 的近期配息資料")
                except Exception as e:
                    st.error(f"❌ 發生錯誤: {e}")
        else:
            st.warning("⚠️ 請填寫正確的代號與股數！")

# --- 4. 核心區塊：資料呈現與計算 ---
if st.session_state.portfolio:
    st.divider()
    st.subheader("📝 你的庫存清單")
    st.caption("💡 提示：你可以直接點擊下方表格內的「股數」或「54C(%)」進行修改，系統會自動重新計算！")
    
    # 將資料轉為 Pandas 表格
    df = pd.DataFrame(st.session_state.portfolio)
    
    # 顯示可編輯的表格 (Streamlit 神功能)
    edited_df = st.data_editor(
        df,
        column_config={
            "代號": st.column_config.TextColumn("代號", disabled=True), # 鎖定不能改
            "股價": st.column_config.NumberColumn("股價", disabled=True, format="%.2f"),
            "本次配息": st.column_config.NumberColumn("本次配息", disabled=True, format="%.3f"),
            "過去一年配息": st.column_config.NumberColumn("過去一年配息", disabled=True, format="%.3f"),
        },
        hide_index=True,
        use_container_width=True
    )
    
    # 把修改後的資料存回記憶體
    st.session_state.portfolio = edited_df.to_dict('records')

    # --- 進行健保與收益的運算 ---
    calc_results = []
    total_annual_income = 0
    total_tax_deduct = 0
    alert_count = 0

    for row in st.session_state.portfolio:
        shares = row["股數"]
        price = row["股價"]
        div = row["本次配息"]
        ratio = row["54C(%)"] / 100
        annual_div = row["過去一年配息"]

        # 計算邏輯
        yield_pct = (div / price) * 100 if price > 0 else 0
        annual_income = shares * annual_div
        total_income = shares * div
        taxable = total_income * ratio
        
        nhi_fee = taxable * 0.0211 if taxable >= 20000 else 0
        if nhi_fee > 0:
            nhi_status = f"⚠️ 扣 {int(nhi_fee):,}"
            alert_count += 1
        else:
            nhi_status = "✅ 免扣"
            
        safe_limit = int(19999 / (div * ratio)) if (div * ratio) > 0 else "無上限"
        
        # 累加總額
        total_annual_income += annual_income
        total_tax_deduct += taxable * 0.085

        calc_results.append({
            "代號": row["代號"],
            "殖利率": f"{yield_pct:.2f}%",
            "應稅股利": f"{int(taxable):,}",
            "二代健保": nhi_status,
            "免扣上限(股)": f"{safe_limit:,}",
            "預估年領股息": f"${int(annual_income):,}"
        })

    st.subheader("📊 健檢與分析報告")
    st.dataframe(pd.DataFrame(calc_results), hide_index=True, use_container_width=True)

    # --- 最下方的「大字報」總結指標 ---
    st.divider()
    col_a, col_b, col_c = st.columns(3)
    col_a.metric(label="💰 預估全庫存年領股息", value=f"${int(total_annual_income):,}")
    col_b.metric(label="🎁 預估可抵減稅額", value=f"${int(total_tax_deduct):,}")
    
    if alert_count > 0:
        col_c.error(f"⚠️ {alert_count} 檔達健保門檻")
    else:
        col_c.success("✅ 全數免扣健保")

    # 清空按鈕
    if st.button("🗑️ 清空所有庫存"):
        st.session_state.portfolio = []
        st.rerun()