# -*- coding: utf-8 -*-
"""
檔案名稱: pages/record_trade.py
功能描述: 股票交易紀錄輸入介面，可將資料寫入 Google Sheets。
開發環境: Python 3.13, Streamlit
"""

# 修改歷程
# 2025-11-24 16:05: 建立交易紀錄頁面，實作輸入表單、自動計算金額與寫入 Google Sheet 功能。

import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# 設定頁面配置 (若主程式已有設定，這行可視情況移除)
st.set_page_config(page_title="交易紀錄", page_icon="📝")

def calculate_amounts(price, quantity, action, fee_rate=0.001425, tax_rate=0.003, discount=0.6):
    """
    計算交易相關費用與總金額
    
    Args:
        price (float): 成交價格
        quantity (int): 成交股數
        action (str): 買入 或 賣出
        fee_rate (float): 手續費率 (預設 0.1425%)
        tax_rate (float): 交易稅率 (預設 0.3%)
        discount (float): 手續費折讓 (預設 6折)
    
    Returns:
        tuple: (手續費, 交易稅, 總金額)
    """
    # 基礎手續費計算 (未滿 20 元以 20 元計，這是台股常見規則，這裡先做簡單計算，可依需求調整)
    raw_fee = price * quantity * fee_rate * discount
    fee = max(int(raw_fee), 20) # 假設最低手續費 20
    
    tax = 0
    total_amount = 0
    
    if action == "賣出":
        tax = int(price * quantity * tax_rate)
        # 賣出收入 = 價金 - 手續費 - 交易稅
        total_amount = int(price * quantity - fee - tax)
    else:
        # 買入成本 = 價金 + 手續費
        total_amount = int(price * quantity + fee)
        
    return fee, tax, total_amount

def main():
    st.title("📝 股票交易紀錄")
    st.markdown("---")

    # 建立與 Google Sheets 的連線
    # 使用 st.connection 快取連線物件
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
    except Exception as e:
        st.error(f"無法連接 Google Sheets，請檢查 secrets.toml 設定。\n錯誤訊息: {e}")
        return

    # --- 輸入表單區域 ---
    with st.form("trade_input_form", clear_on_submit=False):
        st.subheader("新增交易資料")
        
        col1, col2 = st.columns(2)
        
        with col1:
            trade_date = st.date_input("交易日期", datetime.now())
            stock_code = st.text_input("股票代號", placeholder="例如: 2330")
            action = st.selectbox("交易類別", ["買入", "賣出"])
            price = st.number_input("成交價格", min_value=0.0, step=0.1, format="%.2f")
        
        with col2:
            trade_time = st.time_input("交易時間", datetime.now())
            stock_name = st.text_input("股票名稱", placeholder="例如: 台積電")
            quantity = st.number_input("成交股數", min_value=1, step=1000, value=1000)
            # 預設手續費折數與稅率，可讓使用者微調
            fee_discount = st.number_input("手續費折數 (例如 0.6)", min_value=0.0, max_value=1.0, value=0.6, step=0.05)

        note = st.text_area("策略 / 筆記", placeholder="紀錄進出場理由...")

        # 自動試算顯示 (這部分在 Form 裡面不會即時更新，若要即時更新需移出 Form 或使用 st.session_state)
        # 為了簡化 MVP，我們在按下提交時進行最終計算與確認
        
        submitted = st.form_submit_button("💾 儲存交易紀錄")

    if submitted:
        # 1. 驗證資料
        if not stock_code or not stock_name:
            st.warning("請填寫完整的股票代號與名稱。")
            return
        
        if price <= 0 or quantity <= 0:
            st.warning("價格與股數必須大於 0。")
            return

        # 2. 執行計算
        fee, tax, total = calculate_amounts(
            price=price, 
            quantity=quantity, 
            action=action, 
            discount=fee_discount
        )

        # 3. 準備寫入的資料
        # 格式化時間字串
        timestamp_str = datetime.combine(trade_date, trade_time).strftime("%Y-%m-%d %H:%M:%S")
        date_str = trade_date.strftime("%Y-%m-%d")

        new_data = pd.DataFrame([
            {
                "日期": date_str,
                "時間": timestamp_str,
                "代號": stock_code,
                "名稱": stock_name,
                "交易別": action,
                "價格": price,
                "股數": quantity,
                "手續費": fee,
                "交易稅": tax,
                "總金額": total,
                "策略/筆記": note
            }
        ])

        # 4. 寫入 Google Sheets
        # 注意: st-gsheets 的 read() 預設會讀取第一張工作表，若指定 worksheet 需確認名稱
        # 這裡假設工作表名稱為 'trade_log'，若不存在建議先在 Sheet 中建立
        target_worksheet = "trade_log" 
        
        try:
            with st.spinner("正在寫入資料庫..."):
                # 讀取現有資料
                existing_data = conn.read(worksheet=target_worksheet, usecols=list(new_data.columns), ttl=0)
                
                # 合併新舊資料
                updated_data = pd.concat([existing_data, new_data], ignore_index=True)
                
                # 寫回 Google Sheets
                conn.update(worksheet=target_worksheet, data=updated_data)
                
                st.success(f"成功新增一筆 {stock_name} ({stock_code}) 的 {action} 紀錄！")
                st.info(f"試算結果：手續費 {fee} 元, 交易稅 {tax} 元, 總金額 {total} 元")
                
                # 顯示最新的幾筆資料供確認
                st.write("### 目前最新的交易紀錄")
                st.dataframe(updated_data.tail(3))

        except Exception as e:
            st.error(f"寫入資料失敗: {e}")
            st.markdown("請確認 Google Sheet 中是否存在名為 `trade_log` 的工作表。")

if __name__ == "__main__":
    main()
