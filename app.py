"""
거래대금 종목 분석 대시보드

어제 거래대금 상위 종목을 필터링하고, 선택한 종목의 3개월 거래대금 추이와 일봉 차트를 표시합니다.
"""
import streamlit as st
from pykrx import stock
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


# -------------------------------
# 📘 기본 설정
# -------------------------------
st.set_page_config(page_title="거래대금 종목 분석 대시보드", layout="wide")
st.title("📊 어제 거래대금 상위 종목 분석 및 3개월 차트")


# -------------------------------
# 🔧 유틸리티 함수
# -------------------------------
@st.cache_data(ttl=3600)  # 1시간 캐싱
def get_ticker_name_mapping() -> Dict[str, str]:
    """
    종목명-티커 코드 매핑 딕셔너리를 생성합니다.
    
    Returns:
        Dict[str, str]: 종목명을 키로, 티커 코드를 값으로 하는 딕셔너리
        
    Raises:
        Exception: API 호출 실패 시 예외 발생
    """
    try:
        ticker_list = stock.get_market_ticker_list(market="ALL")
        ticker_dict = {
            stock.get_market_ticker_name(t): t 
            for t in ticker_list
        }
        return ticker_dict
    except Exception as e:
        st.error(f"종목 리스트 조회 실패: {str(e)}")
        raise


@st.cache_data(ttl=300)  # 5분 캐싱
def get_market_data(date_str: str) -> Optional[pd.DataFrame]:
    """
    지정된 날짜의 시장 OHLCV 데이터를 조회합니다.
    
    Args:
        date_str (str): 조회할 날짜 (YYYYMMDD 형식)
        
    Returns:
        Optional[pd.DataFrame]: OHLCV 데이터프레임, 실패 시 None
    """
    try:
        df = stock.get_market_ohlcv_by_ticker(date_str, market="ALL")
        if df is None or df.empty:
            return None
        return df
    except Exception as e:
        st.error(f"시장 데이터 조회 실패 ({date_str}): {str(e)}")
        return None


@st.cache_data(ttl=300)  # 5분 캐싱
def get_stock_history(
    start_date: str, 
    end_date: str, 
    ticker: str
) -> Optional[pd.DataFrame]:
    """
    지정된 기간의 종목 히스토리 데이터를 조회합니다.
    
    Args:
        start_date (str): 시작 날짜 (YYYYMMDD 형식)
        end_date (str): 종료 날짜 (YYYYMMDD 형식)
        ticker (str): 티커 코드
        
    Returns:
        Optional[pd.DataFrame]: 히스토리 데이터프레임, 실패 시 None
    """
    try:
        df = stock.get_market_ohlcv_by_date(start_date, end_date, ticker)
        if df is None or df.empty:
            return None
        return df.reset_index()
    except Exception as e:
        st.error(f"종목 히스토리 조회 실패 ({ticker}): {str(e)}")
        return None


def calculate_trading_value(df: pd.DataFrame) -> pd.DataFrame:
    """
    데이터프레임에 거래대금(억 원) 컬럼을 추가합니다.
    
    Args:
        df (pd.DataFrame): 종가와 거래량 컬럼이 포함된 데이터프레임
        
    Returns:
        pd.DataFrame: 거래대금 컬럼이 추가된 데이터프레임
        
    Raises:
        ValueError: 필요한 컬럼이 없을 경우
    """
    required_columns = ["종가", "거래량"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        raise ValueError(
            f"거래대금 계산에 필요한 컬럼이 없습니다: {missing_columns}. "
            f"현재 컬럼: {list(df.columns)}"
        )
    
    df = df.copy()
    df["거래대금(억 원)"] = (df["종가"] * df["거래량"]) / 100_000_000
    return df


def count_days_above_threshold(
    ticker: str,
    start_date: str,
    end_date: str,
    threshold: int
) -> int:
    """
    지정된 기간 동안 거래대금이 임계값 이상이었던 날의 횟수를 계산합니다.
    
    Args:
        ticker (str): 티커 코드
        start_date (str): 시작 날짜 (YYYYMMDD 형식)
        end_date (str): 종료 날짜 (YYYYMMDD 형식)
        threshold (int): 거래대금 임계값 (원 단위)
        
    Returns:
        int: 임계값 이상이었던 날의 횟수
    """
    try:
        df_hist = get_stock_history(start_date, end_date, ticker)
        if df_hist is None or df_hist.empty:
            return 0
        
        # 거래대금 계산
        if "종가" in df_hist.columns and "거래량" in df_hist.columns:
            trading_values = df_hist["종가"] * df_hist["거래량"]
            count = (trading_values >= threshold).sum()
            return int(count)
        else:
            return 0
    except Exception:
        return 0


def filter_by_trading_value(
    df: pd.DataFrame, 
    threshold: int
) -> pd.DataFrame:
    """
    거래대금 기준으로 데이터프레임을 필터링합니다.
    
    Args:
        df (pd.DataFrame): 필터링할 데이터프레임
        threshold (int): 거래대금 임계값 (원 단위)
        
    Returns:
        pd.DataFrame: 필터링된 데이터프레임
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    if "거래대금" not in df.columns:
        return pd.DataFrame()
    
    df_filtered = df[df["거래대금"] > threshold].copy()
    
    # 종목명 추가
    try:
        ticker_dict = get_ticker_name_mapping()
        reverse_dict = {v: k for k, v in ticker_dict.items()}
        df_filtered["종목명"] = df_filtered.index.map(
            lambda x: reverse_dict.get(x, f"Unknown_{x}")
        )
    except Exception:
        df_filtered["종목명"] = df_filtered.index.astype(str)
    
    df_filtered = df_filtered[["종목명", "거래대금"]].sort_values(
        "거래대금", 
        ascending=False
    )
    
    return df_filtered


def get_business_dates() -> Tuple[str, str]:
    """
    어제 날짜와 3개월 전 날짜를 계산합니다 (영업일 기준).
    
    Returns:
        Tuple[str, str]: (어제 날짜 문자열, 3개월 전 날짜 문자열) (YYYYMMDD 형식)
        
    Raises:
        Exception: 날짜 계산 실패 시
    """
    try:
        today = datetime.today()
        yesterday = today - timedelta(days=1)
        yesterday_str = stock.get_nearest_business_day_in_a_week(
            yesterday.strftime("%Y%m%d")
        )
        three_months_ago = (today - timedelta(days=90)).strftime("%Y%m%d")
        return yesterday_str, three_months_ago
    except Exception as e:
        st.error(f"날짜 계산 실패: {str(e)}")
        raise


def create_trading_value_chart(
    df: pd.DataFrame, 
    stock_name: str
) -> go.Figure:
    """
    거래대금 추이 라인 차트를 생성합니다.
    
    Args:
        df (pd.DataFrame): 날짜와 거래대금(억 원) 컬럼이 포함된 데이터프레임
        stock_name (str): 종목명
        
    Returns:
        go.Figure: Plotly Figure 객체
    """
    fig = px.line(
        df,
        x="날짜",
        y="거래대금(억 원)",
        title=f"💰 {stock_name} 최근 3개월 거래대금 추이 (억 원)"
    )
    return fig


def create_candlestick_chart(
    df: pd.DataFrame, 
    stock_name: str
) -> go.Figure:
    """
    일봉 캔들스틱 차트를 생성합니다.
    
    Args:
        df (pd.DataFrame): 날짜, 시가, 고가, 저가, 종가 컬럼이 포함된 데이터프레임
        stock_name (str): 종목명
        
    Returns:
        go.Figure: Plotly Figure 객체
    """
    fig = go.Figure(data=[go.Candlestick(
        x=df['날짜'],
        open=df['시가'],
        high=df['고가'],
        low=df['저가'],
        close=df['종가'],
        name="일봉"
    )])
    fig.update_layout(
        title=f"📈 {stock_name} 최근 3개월 일봉 차트",
        xaxis_title="날짜",
        yaxis_title="가격",
        xaxis_rangeslider_visible=False
    )
    return fig


# -------------------------------
# 📅 날짜 계산
# -------------------------------
try:
    yesterday_str, three_months_ago = get_business_dates()
    yesterday_display = datetime.strptime(yesterday_str, "%Y%m%d").strftime("%Y-%m-%d")
except Exception as e:
    st.error(f"날짜 계산 중 오류가 발생했습니다: {str(e)}")
    st.stop()

# -------------------------------
# ⚙️ 설정 사이드바
# -------------------------------
with st.sidebar:
    st.header("⚙️ 설정")
    threshold_billion = st.slider(
        "거래대금 임계값 (억 원)",
        min_value=100,
        max_value=10000,
        value=2000,
        step=100,
        help="이 값 이상의 거래대금을 기록한 종목만 표시됩니다."
    )
    threshold = threshold_billion * 100_000_000  # 억 원을 원으로 변환
    
    st.divider()
    st.header("🔍 필터 옵션")
    max_days_filter = st.number_input(
        "최근 3개월간 거래대금 임계값 이상 날짜 수 (최대)",
        min_value=0,
        max_value=100,
        value=5,
        step=1,
        help="이 값 이하인 종목만 표시됩니다. (0 입력 시 필터링 없음)"
    )

# -------------------------------
# 📈 어제 종목별 거래대금 불러오기
# -------------------------------
loading_placeholder = st.info(f"📅 {yesterday_display} 거래대금 데이터를 불러오는 중입니다...")

df_yesterday = get_market_data(yesterday_str)

if df_yesterday is None or df_yesterday.empty:
    loading_placeholder.empty()
    st.error("어제 거래대금 데이터를 불러올 수 없습니다. 시장이 휴장일일 수 있습니다.")
    st.stop()

# 데이터 로딩 완료 후 메시지 변경
loading_placeholder.empty()
st.success(f"✅ {yesterday_display} 거래대금 데이터를 성공적으로 불러왔습니다! ({len(df_yesterday):,}개 종목)")

# -------------------------------
# 💰 거래대금 필터링
# -------------------------------
df_filtered = filter_by_trading_value(df_yesterday, threshold)

# -------------------------------
# 🔹 거래대금 표 출력
# -------------------------------
st.subheader(f"💸 {yesterday_display} 거래대금 {threshold_billion:,}억 원 이상 종목")

if len(df_filtered) == 0:
    st.warning(
        f"어제는 거래대금이 {threshold_billion:,}억 원을 넘은 종목이 없습니다. "
        "임계값을 낮춰보세요."
    )
    st.stop()

# -------------------------------
# 📊 최근 3개월간 거래대금 임계값 이상 날짜 수 계산
# -------------------------------
stats_loading_placeholder = st.info("📊 최근 3개월간 거래대금 통계를 계산하는 중입니다...")

try:
    # df_filtered의 index가 티커 코드이므로 직접 사용
    df_filtered = df_filtered.copy()
    
    # 각 종목에 대해 3개월간 임계값 이상 날짜 수 계산
    days_above_threshold = []
    progress_bar = st.progress(0)
    total_stocks = len(df_filtered)
    
    for idx, ticker in enumerate(df_filtered.index):
        if ticker:
            count = count_days_above_threshold(
                ticker, 
                three_months_ago, 
                yesterday_str, 
                threshold
            )
            days_above_threshold.append(count)
        else:
            days_above_threshold.append(0)
        
        # 진행 상황 업데이트
        progress_bar.progress((idx + 1) / total_stocks)
    
    progress_bar.empty()
    
    # 컬럼 이름 동적 생성
    column_name = f"3개월간 {threshold_billion:,}억 이상 (일)"
    df_filtered[column_name] = days_above_threshold
    
    # 필터링: 최근 3개월간 횟수가 max_days_filter 이하인 종목만 표시
    if max_days_filter > 0:
        before_count = len(df_filtered)
        df_filtered = df_filtered[df_filtered[column_name] <= max_days_filter].copy()
        after_count = len(df_filtered)
        if before_count != after_count:
            st.info(f"📊 필터링: {before_count}개 종목 중 {after_count}개 종목이 {max_days_filter}회 이하입니다.")
    
    # 컬럼 순서 재정렬
    df_filtered = df_filtered[["종목명", "거래대금", column_name]]
    
    # 통계 계산 완료 후 메시지 변경
    stats_loading_placeholder.empty()
    st.success(f"✅ 최근 3개월간 거래대금 통계 계산이 완료되었습니다! ({len(df_filtered)}개 종목)")
    
except Exception as e:
    stats_loading_placeholder.empty()
    st.warning(f"3개월간 거래대금 통계 계산 중 오류가 발생했습니다: {str(e)}")
    # 오류 발생 시 기본 컬럼만 표시
    df_filtered = df_filtered[["종목명", "거래대금"]]
    column_name = None

# 필터링 후 종목이 없을 경우 처리
if len(df_filtered) == 0:
    st.warning(
        f"최근 3개월간 거래대금이 {threshold_billion:,}억 원 이상이었던 날이 "
        f"{max_days_filter}회 이하인 종목이 없습니다. 필터 조건을 완화해보세요."
    )
    st.stop()

# 데이터프레임 포맷팅
format_dict = {"거래대금": "{:,.0f}"}
if column_name and column_name in df_filtered.columns:
    format_dict[column_name] = "{:,.0f}"

st.dataframe(
    df_filtered.style.format(format_dict), 
    use_container_width=True
)

# -------------------------------
# 🧩 종목 선택
# -------------------------------
selected_name = st.selectbox(
    "🔍 최근 3개월 거래대금 및 일봉 차트를 볼 종목을 선택하세요",
    df_filtered["종목명"]
)

# -------------------------------
# 📊 선택한 종목의 3개월 데이터
# -------------------------------
if selected_name:
    try:
        # 티커 코드 조회
        ticker_dict = get_ticker_name_mapping()
        code = ticker_dict.get(selected_name)
        
        if not code:
            st.error(f"종목 '{selected_name}'의 티커 코드를 찾을 수 없습니다.")
            st.stop()
        
        loading_hist_placeholder = st.info(f"📈 {selected_name} ({code})의 최근 3개월 데이터를 불러오는 중입니다...")
        
        # 히스토리 데이터 조회
        df_hist = get_stock_history(three_months_ago, yesterday_str, code)
        
        if df_hist is None or df_hist.empty:
            loading_hist_placeholder.empty()
            st.warning(f"{selected_name}의 최근 3개월 데이터를 불러올 수 없습니다.")
            st.stop()
        
        # 데이터 로딩 완료 후 메시지 변경
        loading_hist_placeholder.empty()
        st.success(f"✅ {selected_name} ({code})의 최근 3개월 데이터를 성공적으로 불러왔습니다! ({len(df_hist)}개 일자)")
        
        # 거래대금 계산
        try:
            df_hist = calculate_trading_value(df_hist)
        except ValueError as e:
            st.error(str(e))
            st.stop()
        
        # -------------------------------
        # 🔹 거래대금 그래프
        # -------------------------------
        fig1 = create_trading_value_chart(df_hist, selected_name)
        st.plotly_chart(fig1, use_container_width=True)
        
        # -------------------------------
        # 🔹 3개월 일봉 차트
        # -------------------------------
        fig2 = create_candlestick_chart(df_hist, selected_name)
        st.plotly_chart(fig2, use_container_width=True)
        
    except Exception as e:
        st.error(f"데이터 처리 중 오류가 발생했습니다: {str(e)}")
        st.exception(e)
