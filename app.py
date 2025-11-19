import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pykrx import stock
from datetime import datetime, timedelta, timezone

# -------------------------------
# 🕒 한국 시간 함수
# -------------------------------
def now_kst():
    return datetime.now(timezone(timedelta(hours=9)))

def today_kst():
    return now_kst().date()


# -------------------------------
# 📘 기본 설정
# -------------------------------
st.set_page_config(
    page_title="KOSPI Top 거래대금 Dashboard",
    page_icon="📈",
    layout="wide"
)

st.title("📈 KOSPI 거래대금 Dashboard")
st.write("한국 시간 기준으로 데이터를 조회합니다.")


# -------------------------------
# ⏱ 날짜 계산 (영업일 보정)
# -------------------------------
def get_recent_business_day():
    today = today_kst()

    # 토요일(5) / 일요일(6) 보정
    if today.weekday() == 5:  # 토요일
        return today - timedelta(days=1)
    elif today.weekday() == 6:  # 일요일
        return today - timedelta(days=2)

    return today


# -------------------------------
# 📥 데이터 불러오기
# -------------------------------
def load_data():
    target_day = get_recent_business_day().strftime("%Y%m%d")

    df = stock.get_market_trading_value_by_date(
        fromdate=target_day,
        todate=target_day,
        market="KOSPI"
    )

    df = df.reset_index()
    df = df.rename(columns={
        "TRD_VAL": "거래대금"
    })

    # 표시용 천단위 콤마 추가
    df["거래대금(표시용)"] = df["거래대금"].apply(lambda x: f"{x:,} 원")

    # 상위 30 종목
    df_sorted = df.sort_values(by="거래대금", ascending=False).head(30)

    return df_sorted


df_filtered = load_data()


# -------------------------------
# 📊 데이터 테이블
# -------------------------------
st.subheader("📊 오늘의 거래대금 상위 종목")

st.dataframe(
    df_filtered[["종목명", "거래대금(표시용)"]],
    use_container_width=True
)


# -------------------------------
# 📈 차트 시각화
# -------------------------------
fig = go.Figure()

fig.add_trace(
    go.Bar(
        x=df_filtered["종목명"],
        y=df_filtered["거래대금"],
    )
)

fig.update_layout(
    title="거래대금 TOP 30",
    xaxis_title="종목명",
    yaxis_title="거래대금",
    height=500
)

st.plotly_chart(fig, use_container_width=True)


# -------------------------------
# 🔍 개별 종목 상세 데이터 (선택)
# -------------------------------
st.subheader("🔍 개별 종목 거래대금 추이 조회")

stock_name = st.selectbox(
    "종목을 선택하세요",
    df_filtered["종목명"].tolist()
)

if stock_name:
    code = df_filtered[df_filtered["종목명"] == stock_name]["종목코드"].iloc[0]
    end_date = today_kst()
    start_date = end_date - timedelta(days=30)

    df_trend = stock.get_market_trading_value_by_date(
        fromdate=start_date.strftime("%Y%m%d"),
        todate=end_date.strftime("%Y%m%d"),
        market="KOSPI"
    )

    df_trend = df_trend.reset_index()
    df_trend = df_trend[df_trend["티커"] == code]

    if not df_trend.empty:
        fig2 = px.line(
            df_trend,
            x="날짜",
            y="TRD_VAL",
            title=f"{stock_name} 최근 30일 거래대금"
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("데이터가 없습니다.")

