import streamlit as st
import pandas as pd
import yfinance as yf
import feedparser
import datetime
import urllib.parse
import json
import os
import plotly.express as px

# --- 1. 設定頁面樣式 ---
st.set_page_config(page_title="全家股票看板", layout="wide", page_icon="📈")

# 自定義 CSS 優化視覺
st.markdown("""
    <style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 10px;
    }
    .stDataFrame {
        font-size: 1.1rem;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📈 全家股票看板")
st.markdown("---")

# --- 2. 定義全家人投資組合 (使用 JSON 檔案儲存) ---
DATA_FILE = "portfolios.json"
HISTORY_FILE = "history.json"

def load_portfolios():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_portfolios(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError, IOError):
            return {}
    return {}

def save_history(data):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if 'family_portfolios' not in st.session_state:
    st.session_state['family_portfolios'] = load_portfolios()

family_portfolios = st.session_state['family_portfolios']

# --- 3. 函數定義 ---

@st.cache_data(ttl=300)
def get_market_data(all_codes):
    """獲取即時股價"""
    if not all_codes:
        return {}
    unique_tickers = list(set(all_codes))
    try:
        tickers = yf.Tickers(" ".join(unique_tickers))
        prices = {}
        for code in unique_tickers:
            try:
                ticker = tickers.tickers[code]
                price = ticker.fast_info.last_price
                if price is None:
                     hist = ticker.history(period="1d")
                     if not hist.empty:
                         price = hist['Close'].iloc[-1]
                prices[code] = price
            except Exception:
                prices[code] = None
        return prices
    except Exception as e:
        st.error(f"獲取股價失敗: {e}")
        return {}

@st.cache_data(ttl=3600)
def get_dividends(all_codes, year):
    """獲取指定年份的股利總和 (每股)"""
    if not all_codes:
        return {}
    unique_tickers = list(set(all_codes))
    dividends_map = {}
    
    for code in unique_tickers:
        try:
            ticker = yf.Ticker(code)
            divs = ticker.dividends
            if not divs.empty:
                # 安全處理時區
                try:
                    divs.index = divs.index.tz_localize(None)
                except TypeError:
                    pass  # 已經是 naive datetime
                year_divs = divs[divs.index.year == year]
                dividends_map[code] = year_divs.sum()
            else:
                dividends_map[code] = 0.0
        except Exception:
            dividends_map[code] = 0.0
    
    return dividends_map

@st.cache_data(ttl=1800)
def get_news(query="台股"):
    """獲取 Google News RSS"""
    encoded_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    feed = feedparser.parse(rss_url)
    return feed.entries[:5] # 只回傳前5則

def color_pl(val):
    color = '#ff4b4b' if val > 0 else '#2dc937' if val < 0 else 'white'
    return f'color: {color}'

def _normalize_portfolio(portfolio):
    """將 portfolio 正規化以便比較"""
    normalized = []
    for stock in portfolio:
        normalized_stock = {
            'code': str(stock.get('code', '')).strip(),
            'name': str(stock.get('name', '')).strip(),
            'shares': int(stock.get('shares', 0)) if pd.notna(stock.get('shares')) else 0,
            'cost': round(float(stock.get('cost', 0)), 2) if pd.notna(stock.get('cost')) else 0.0
        }
        normalized.append(normalized_stock)
    return normalized

# --- 4. 數據處理 ---

# 收集所有代碼
all_codes_list = []
for member, stocks in family_portfolios.items():
    for stock in stocks:
        all_codes_list.append(stock['code'])

# 獲取數據
if all_codes_list:
    with st.spinner('更新股價中...'):
        current_prices = get_market_data(all_codes_list)
else:
    current_prices = {}

# 獲取今年股利
current_year = datetime.datetime.now().year
if all_codes_list:
    with st.spinner(f'計算 {current_year} 年股利中...'):
        dividend_data = get_dividends(all_codes_list, current_year)
        
        # 如果今年總股利為 0 (年初可能還沒發)，則改抓去年
        if sum(dividend_data.values()) == 0:
            st.toast(f"⚠️ {current_year} 年尚無配息資料，已自動切換顯示 {current_year-1} 年股利。", icon="ℹ️")
            current_year = current_year - 1
            dividend_data = get_dividends(all_codes_list, current_year)
else:
    dividend_data = {}

# 計算邏輯
family_summary = []
total_family_assets = 0
total_family_pl = 0
total_family_cost = 0
total_family_div = 0

processed_data = {}

for member, stocks in family_portfolios.items():
    member_data = []
    member_assets = 0
    member_cost = 0
    member_pl = 0
    member_div = 0
    
    for item in stocks:
        code = item['code']
        shares = item['shares']
        cost_price = item['cost'] if item['cost'] else 0
        
        # 股價
        current_price = current_prices.get(code)
        if current_price is None or pd.isna(current_price):
            current_price = cost_price # 獲取失敗時用成本價暫代
            
        # 股利
        div_per_share = dividend_data.get(code, 0.0)
        total_div = div_per_share * shares

        market_value = float(current_price * shares)
        cost_value = float(cost_price * shares)
        unrealized_pl = market_value - cost_value
        pl_ratio = (unrealized_pl / cost_value * 100) if cost_value > 0 else 0

        # 累計
        member_assets += market_value
        member_div += total_div
        if cost_price > 0:
            member_cost += cost_value
            member_pl += unrealized_pl
        
        member_data.append({
            "代號": code.replace(".TW", ""),
            "名稱": item['name'],
            "股數": shares,
            "成本": cost_price,
            "現價": round(current_price, 2) if pd.notna(current_price) else 0,
            "市值": int(market_value) if pd.notna(market_value) else 0,
            "損益": int(unrealized_pl) if pd.notna(unrealized_pl) else 0,
            "報酬率(%)": round(pl_ratio, 2) if pd.notna(pl_ratio) else 0,
            f"{current_year}股利": int(total_div) if pd.notna(total_div) else 0
        })
    
    df_member = pd.DataFrame(member_data)
    processed_data[member] = {
        "df": df_member,
        "total_assets": member_assets,
        "total_pl": member_pl,
        "total_cost": member_cost,
        "total_div": member_div
    }
    
    total_family_assets += member_assets
    total_family_cost += member_cost
    total_family_pl += member_pl
    total_family_div += member_div
    
    family_summary.append({
        "成員": member,
        "總資產": int(member_assets),
        "總獲利": int(member_pl),
        f"{current_year}已領股利": int(member_div)
    })

# 記錄歷史資料
today_str = datetime.datetime.now().strftime('%Y-%m-%d')
history_data = load_history()

# 建構今日資料
daily_record = {
    "Total": int(total_family_assets)
}
for member, data in processed_data.items():
    daily_record[member] = int(data['total_assets'])

# 更新今日資料 (覆寫)
history_data[today_str] = daily_record
save_history(history_data)

# --- 5. 顯示儀表板 ---

# 總覽區塊
st.header("📊 全家資產總覽")
col1, col2, col3, col4 = st.columns(4)
col1.metric("💰 全家總資產", f"NT${int(total_family_assets):,}")
col2.metric(
    "📈 全家總獲利", 
    f"NT${int(total_family_pl):,}", 
    f"{round(total_family_pl/total_family_cost*100, 2)}%" if total_family_cost > 0 else "0%"
)
col3.metric(f"💵 {current_year} 總股利", f"NT${int(total_family_div):,}")
col4.metric("👥 成員數", f"{len(family_portfolios)} 人")

# 圖表區塊
df_summary = pd.DataFrame(family_summary)
c1, c2 = st.columns([2, 1])
with c1:
    st.subheader("資產分佈")
    st.bar_chart(df_summary, x="成員", y=["總資產", "總獲利"], color=["#36a2eb", "#ff6384"])

with c2:
    st.subheader("資產佔比")
    if total_family_assets > 0:
        fig = px.pie(
            df_summary, values="總資產", names="成員",
            hole=0.4, color_discrete_sequence=px.colors.qualitative.Set2
        )
        fig.update_layout(
            showlegend=True, margin=dict(t=20, b=20, l=20, r=20),
            height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(size=13)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("尚無資產資料")

st.markdown("---")

# 成員詳細資訊
st.subheader("👤 成員持股詳情")
tabs = st.tabs(list(family_portfolios.keys()))

for i, (member, data) in enumerate(processed_data.items()):
    with tabs[i]:
        # 成員概況
        m1, m2, m3 = st.columns(3)
        m1.metric("個人總資產", f"NT${int(data['total_assets']):,}")
        m2.metric(
            "個人總獲利", 
            f"NT${int(data['total_pl']):,}", 
            f"{round(data['total_pl']/data['total_cost']*100, 2)}%" if data['total_cost'] > 0 else "0%"
        )
        m3.metric(f"{current_year} 已領股利", f"NT${int(data['total_div']):,}")
        
        # 持股表格
        st.dataframe(
            data['df'].style.map(color_pl, subset=['損益', '報酬率(%)'])
              .format({
                  "成本": "{:.2f}", 
                  "現價": "{:.2f}", 
                  "市值": "{:,}", 
                  "損益": "{:+,.0f}",
                  f"{current_year}股利": "{:,}"
              }),
            use_container_width=True,
            height=400,
            hide_index=True
        )

        # 編輯持股區塊
        with st.expander("✏️ 編輯持股 (新增/修改/刪除)"):
            st.info("💡 直接在表格中修改，完成後系統會自動儲存並更新。如需新增，請在最後一行輸入。如需刪除，請選取行並按 Delete 鍵。")
            
            # 準備編輯器的資料
            # 為了讓 data_editor 正常運作，我們需要將 list of dicts 轉為 DataFrame，但為了方便回寫，我們直接操作 list 也可以
            # 這裡我們用 DataFrame 來做編輯介面，比較直觀
            df_edit = pd.DataFrame(st.session_state['family_portfolios'][member])
            
            # 設定 Column Config
            column_config = {
                "code": st.column_config.TextColumn("股票代碼", help="例如 2330.TW", required=True),
                "name": st.column_config.TextColumn("股票名稱", help="例如 台積電"),
                "shares": st.column_config.NumberColumn("股數", min_value=1, step=1, required=True),
                "cost": st.column_config.NumberColumn("平均成本", min_value=0.0, step=0.1, format="$%.2f")
            }
            
            edited_df = st.data_editor(
                df_edit,
                key=f"editor_{i}",
                num_rows="dynamic",
                column_config=column_config,
                use_container_width=True,
                hide_index=True
            )
            
            # 檢查是否有變更
            # 轉換回 list of dicts
            new_portfolio = edited_df.to_dict('records')
            
            # 正規化比較：處理浮點數精度和 NaN 問題
            current_portfolio = st.session_state['family_portfolios'][member]
            normalized_new = _normalize_portfolio(new_portfolio)
            normalized_current = _normalize_portfolio(current_portfolio)
            
            if normalized_new != normalized_current:
                # 檢查是否有新增的股票且沒有名稱，嘗試自動補全
                for stock in new_portfolio:
                    if stock['code'] and (not stock.get('name') or stock['name'] == ""):
                        code = stock['code']
                        # 自動補 .TW
                        if not code.endswith(".TW") and not code.endswith(".TWO"):
                             code = f"{code}.TW"
                             stock['code'] = code
                        
                        try:
                            t = yf.Ticker(code)
                            name = t.info.get('shortName', code)
                            if not name or name == code:
                                name = code.replace(".TW", "")
                            stock['name'] = name
                        except Exception:
                            stock['name'] = code

                # 更新 Session State
                st.session_state['family_portfolios'][member] = new_portfolio
                # 儲存到檔案
                save_portfolios(st.session_state['family_portfolios'])
                st.success("已儲存變更！")
                st.rerun()

st.markdown("---")

# --- 6. 歷史趨勢 ---
st.header("📜 資產歷史趨勢")
if history_data:
    # 轉為 DataFrame
    df_history = pd.DataFrame.from_dict(history_data, orient='index')
    # index 是日期字串，轉為 datetime 以便顯示
    df_history.index = pd.to_datetime(df_history.index)
    df_history.sort_index(inplace=True)
    
    # 區間選擇
    st.write("### 📅 選擇時間區間")
    range_options = ["1個月", "3個月", "1年", "2年", "全部"]
    # 使用 horizontal radio
    selected_range = st.radio("區間", range_options, index=4, horizontal=True, label_visibility="collapsed")
    
    # 計算過濾日期
    end_date = df_history.index.max()
    start_date = df_history.index.min()
    
    if selected_range == "1個月":
        start_date = end_date - pd.DateOffset(months=1)
    elif selected_range == "3個月":
        start_date = end_date - pd.DateOffset(months=3)
    elif selected_range == "1年":
        start_date = end_date - pd.DateOffset(years=1)
    elif selected_range == "2年":
        start_date = end_date - pd.DateOffset(years=2)
    
    # 過濾資料
    df_filtered = df_history[df_history.index >= start_date]

    h_tab1, h_tab2 = st.tabs(["📈 趨勢圖", "📋 詳細數據"])
    
    with h_tab1:
        st.subheader(f"資產成長趨勢 ({selected_range})")
        # 顯示全家總資產趨勢
        st.line_chart(df_filtered['Total'])
        
        st.subheader("成員資產比較")
        # 顯示各成員資產 (排除 Total)
        members_cols = [c for c in df_filtered.columns if c != 'Total']
        st.line_chart(df_filtered[members_cols])
        
    with h_tab2:
        st.dataframe(df_filtered.style.format("{:,}"), use_container_width=True)
else:
    st.info("尚無歷史資料，請持續使用本看板以累積數據。")

st.markdown("---")

# --- 7. 重要新聞 ---
st.header("📰 重要財經新聞")

# 獲取新聞
news_items = get_news("台股 財經")

if news_items:
    for item in news_items:
        pub_date = getattr(item, 'published', '')[:16] if hasattr(item, 'published') else ''
        source_name = ''
        if hasattr(item, 'source') and hasattr(item.source, 'title'):
            source_name = item.source.title
        with st.expander(f"{item.title} - {pub_date}"):
            if source_name:
                st.markdown(f"**來源**: {source_name}")
            st.markdown(f"[閱讀全文]({item.link})")
            if 'summary' in item:
                st.markdown(item.summary, unsafe_allow_html=True)
else:
    st.info("暫時無法獲取新聞")

# 頁尾
st.caption(f"最後更新時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
