import streamlit as st
from pykrx import stock
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go

# -------------------------------
# 📘 기본 설정
# -------------------------------
st.set_page_config(page_title="거래대금 종목 분석 대시보드", layout="wide")
st.title("📊 어제 거래대금 상위 종목 분석 및 3개월 차트")

# -------------------------------
# 📅 날짜 계산
# -------------------------------
today = datetime.today()
yesterday = today - timedelta(days=1)
yesterday_str = stock.get_nearest_business_day_in_a_week(yesterday.strftime("%Y%m%d"))
three_months_ago = (today - timedelta(days=90)).strftime("%Y%m%d")

# -------------------------------
# 📈 어제 종목별 거래대금 불러오기
# -------------------------------
st.info("어제 거래대금 데이터를 불러오는 중입니다...")
df_yesterday = stock.get_market_ohlcv_by_ticker(yesterday_str, market="ALL")

# -------------------------------
# 💰 거래대금 2,000억 이상 종목 필터링
# -------------------------------
df_filtered = df_yesterday[df_yesterday["거래대금"] > 200_000_000_000].copy()
df_filtered["종목명"] = df_filtered.index.map(lambda x: stock.get_market_ticker_name(x))
df_filtered = df_filtered[["종목명", "거래대금"]].sort_values("거래대금", ascending=False)

# -------------------------------
# 🔹 거래대금 표 출력 (콤마 적용)
# -------------------------------
st.subheader(f"💸 {yesterday.strftime('%Y-%m-%d')} 거래대금 2,000억 이상 종목")
st.dataframe(df_filtered.style.format({"거래대금": "{:,.0f}"}), use_container_width=True)

if len(df_filtered) == 0:
    st.warning("어제는 거래대금이 2,000억 원을 넘은 종목이 없습니다.")
    st.stop()

# -------------------------------
# 🧩 종목 선택 (selectbox)
# -------------------------------
selected_name = st.selectbox(
    "🔍 최근 3개월 거래대금 및 일봉 차트를 볼 종목을 선택하세요",
    df_filtered["종목명"]
)

# -------------------------------
# 📊 선택한 종목의 3개월 데이터
# -------------------------------
if selected_name:
    ticker_list = stock.get_market_ticker_list(market="ALL")
    ticker_dict = {stock.get_market_ticker_name(t): t for t in ticker_list}
    code = ticker_dict[selected_name]

    st.info(f"📈 {selected_name} ({code})의 최근 3개월 데이터를 불러오는 중입니다...")

    df_hist = stock.get_market_ohlcv_by_date(three_months_ago, yesterday_str, code)
    df_hist = df_hist.reset_index()

    # 거래대금 계산
    if "종가" in df_hist.columns and "거래량" in df_hist.columns:
        df_hist["거래대금(억 원)"] = (df_hist["종가"] * df_hist["거래량"]) / 100_000_000
    else:
        st.error(f"거래대금 계산에 필요한 컬럼이 없습니다. df_hist.columns={df_hist.columns}")
        st.stop()

    # -------------------------------
    # 🔹 거래대금 그래프
    # -------------------------------
    fig1 = px.line(
        df_hist,
        x="날짜",
        y="거래대금(억 원)",
        title=f"💰 {selected_name} 최근 3개월 거래대금 추이 (억 원)"
    )
    st.plotly_chart(fig1, use_container_width=True)

    # -------------------------------
    # 🔹 3개월 일봉 차트
    # -------------------------------
    fig2 = go.Figure(data=[go.Candlestick(
        x=df_hist['날짜'],
        open=df_hist['시가'],
        high=df_hist['고가'],
        low=df_hist['저가'],
        close=df_hist['종가'],
        name="일봉"
    )])
    fig2.update_layout(
        title=f"📈 {selected_name} 최근 3개월 일봉 차트",
        xaxis_title="날짜",
        yaxis_title="가격",
        xaxis_rangeslider_visible=False
    )
    st.plotly_chart(fig2, use_container_width=True)

