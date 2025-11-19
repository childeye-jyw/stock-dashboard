import streamlit as st
from pykrx import stock
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import plotly.express as px

# ------------------------------------------------
# 🌏 한국 시간 기준 날짜 계산
# ------------------------------------------------
now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
today_str = now_kst.strftime("%Y%m%d")
yesterday = now_kst - timedelta(days=1)
yesterday_str = yesterday.strftime("%Y%m%d")
three_months_ago_str = (now_kst - timedelta(days=90)).strftime("%Y%m%d")

# ------------------------------------------------
# 📘 Streamlit 기본 UI 설정
# ------------------------------------------------
st.set_page_config(page_title="거래대금 종목 분석 대시보드", layout="wide")
st.title("📊 거래대금 분석 대시보드 (KST 기준)")

# ------------------------------------------------
# 📈 어제 종목별 거래대금 가져오기
# ------------------------------------------------
st.info(f"⏳ {yesterday.strftime('%Y-%m-%d')} 기준 거래대금 데이터를 불러오는 중...")

df_yesterday_raw = stock.get_market_ohlcv_by_ticker(yesterday_str, market="ALL")

# 거래대금 컬럼명 표준화
df_yesterday_raw.rename(columns={"Value": "거래대금"}, inplace=True)

# 종목명 추가
df_yesterday_raw["종목명"] = df_yesterday_raw.index.map(stock.get_market_ticker_name)

# 필요한 컬럼만 정리
df_filtered = df_yesterday_raw[["종목명", "거래대금"]].copy()

# 2,000억 이상 필터링
df_filtered = df_filtered[df_filtered["거래대금"] > 200_000_000_000]

# 표시용 콤마 추가
df_filtered["거래대금(표시용)"] = df_filtered["거래대금"].apply(lambda x: f"{x:,}")

df_filtered = df_filtered.sort_values("거래대금", ascending=False)

st.subheader(f"💸 {yesterday.strftime('%Y-%m-%d')} 거래대금 2,000억 이상 종목")
st.caption("아래 표에서 종목명을 클릭하면 3개월 거래대금 추이를 확인할 수 있습니다.")

# ------------------------------------------------
# 🧩 AgGrid로 표 출력 (행 클릭)
# ------------------------------------------------
gb = GridOptionsBuilder.from_dataframe(df_filtered[["종목명", "거래대금(표시용)"]])
gb.configure_selection("single")  # 단일 선택
grid_options = gb.build()

grid_response = AgGrid(
    df_filtered,
    gridOptions=grid_options,
    update_mode=GridUpdateMode.SELECTION_CHANGED,
    fit_columns_on_grid_load=True,
    height=350,
)

selected = grid_response["selected_rows"]
if selected:
    selected_name = selected[0]["종목명"]
    st.success(f"📌 선택된 종목: {selected_name}")

    # ------------------------------------------------
    # 🔍 티커 코드 찾기
    # ------------------------------------------------
    ticker_list = stock.get_market_ticker_list()
    name_to_code = {stock.get_market_ticker_name(t): t for t in ticker_list}
    code = name_to_code[selected_name]

    # ------------------------------------------------
    # 📉 최근 3개월 거래대금 데이터
    # ------------------------------------------------
    st.info(f"📈 {selected_name} ({code}) 최근 3개월 거래대금 데이터를 불러오는 중...")

    df_hist = stock.get_market_ohlcv_by_date(three_months_ago_str, yesterday_str, code)
    df_hist = df_hist.reset_index()

    # 거래대금 컬럼 추가 (Value 없음 → 직접 계산)
    df_hist["거래대금"] = df_hist["거래량"] * df_hist["종가"]
    df_hist["거래대금(억 원)"] = df_hist["거래대금"] / 100_000_000

    # ------------------------------------------------
    # 📊 3개월 거래대금 추이
    # ------------------------------------------------
    st.subheader(f"📊 {selected_name} 최근 3개월 거래대금 추이 (억 원)")
    fig1 = px.line(
        df_hist,
        x="날짜",
        y="거래대금(억 원)",
        title=f"{selected_name} 3개월 거래대금 변화",
    )
    st.plotly_chart(fig1, use_container_width=True)

    # ------------------------------------------------
    # 📈 3개월 일봉 차트
    # ------------------------------------------------
    st.subheader(f"📉 {selected_name} 최근 3개월 일봉 차트")

    fig2 = px.line(
        df_hist,
        x="날짜",
        y="종가",
        title=f"{selected_name} 일봉 종가 추이",
    )
    st.plotly_chart(fig2, use_container_width=True)

else:
    st.warning("👉 위 표에서 종목을 클릭하면 상세 데이터가 표시됩니다.")

