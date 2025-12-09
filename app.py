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

# 한국 시간대 지원
try:
    from zoneinfo import ZoneInfo
    USE_ZONEINFO = True
except ImportError:
    # Python 3.8 이하 또는 zoneinfo가 없는 경우 pytz 사용
    import pytz
    USE_ZONEINFO = False


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
        ticker_dict = {}
        
        for t in ticker_list:
            try:
                name = stock.get_market_ticker_name(t)
                # 문자열인지 확인 (DataFrame이 반환될 수 있음)
                if isinstance(name, str):
                    ticker_dict[name] = t
                elif hasattr(name, 'iloc'):  # DataFrame인 경우
                    # DataFrame의 첫 번째 값을 사용하거나 티커 코드를 그대로 사용
                    ticker_dict[str(t)] = t
                else:
                    # 기타 타입인 경우 문자열로 변환
                    ticker_dict[str(name)] = t
            except Exception:
                # 개별 티커 조회 실패 시 티커 코드를 그대로 사용
                ticker_dict[str(t)] = t
                continue
        
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
        
        # 데이터가 None이거나 비어있는 경우
        if df is None or df.empty:
            return None
        
        # 실제 컬럼 확인 (디버깅용)
        actual_columns = list(df.columns) if df is not None else []
        
        # 필요한 컬럼이 있는지 확인
        required_columns = ["거래대금"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            # 휴장일이거나 데이터가 없는 경우
            return None
        
        return df
    except KeyError as e:
        # pykrx 내부에서 컬럼 접근 실패 (휴장일 또는 데이터 없음)
        # get_market_ohlcv_by_ticker 내부에서 df[['시가', '고가', '저가', '종가']] 접근 시 발생
        return None
    except Exception as e:
        # 기타 오류는 로그만 남기고 None 반환
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


@st.cache_data(ttl=3600)  # 1시간 캐싱
def get_business_dates() -> Tuple[str, str, int]:
    """
    어제 날짜와 3개월 전 날짜를 계산합니다 (영업일 기준, 한국 시간대).
    실제로 데이터가 있는 날짜를 찾습니다.
    
    Returns:
        Tuple[str, str, int]: (어제 날짜 문자열, 3개월 전 날짜 문자열, 날짜 차이 일수) (YYYYMMDD 형식)
        - 날짜 차이 일수: 계산된 어제 날짜와 찾은 날짜의 차이 (0이면 정상)
        
    Raises:
        Exception: 날짜 계산 실패 시
    """
    try:
        # 한국 시간대(KST, UTC+9) 기준으로 현재 시간 가져오기
        if USE_ZONEINFO:
            kst = ZoneInfo("Asia/Seoul")
            today = datetime.now(kst)
        else:
            kst = pytz.timezone("Asia/Seoul")
            today = datetime.now(kst)
        
        # 어제 날짜 계산 및 영업일 조정
        yesterday = today - timedelta(days=1)
        
        # 최근 영업일 찾기 (최대 60일 전까지 시도 - 장기 휴장 대비)
        yesterday_str = None
        
        # 방법 1: 주말 제외하고 최근 영업일 직접 찾기 (데이터 확인 포함)
        # 최대 60일 전까지 시도하여 실제로 데이터가 있는 날짜 찾기
        for days_back in range(0, 61):
            test_date = yesterday - timedelta(days=days_back)
            weekday = test_date.weekday()  # 0=월요일, 6=일요일
            if weekday < 5:  # 월~금
                test_date_str = test_date.strftime("%Y%m%d")
                # 실제로 데이터가 있는지 확인
                try:
                    test_df = stock.get_market_ohlcv_by_ticker(test_date_str, market="ALL")
                    if test_df is not None and not test_df.empty and "거래대금" in test_df.columns:
                        yesterday_str = test_date_str
                        break
                except KeyError:
                    # pykrx 내부에서 컬럼 접근 실패 (휴장일)
                    continue
                except Exception:
                    # 기타 오류 (네트워크 문제 등)
                    continue
        
        # 방법 2: get_nearest_business_day_in_a_week 사용 (방법 1이 실패한 경우)
        if not yesterday_str:
            for days_back in range(0, 61):
                try:
                    test_date = yesterday - timedelta(days=days_back)
                    test_date_str = test_date.strftime("%Y%m%d")
                    result = stock.get_nearest_business_day_in_a_week(test_date_str)
                    
                    # 결과가 유효한지 확인
                    if result and isinstance(result, str) and len(result) == 8:
                        # 실제로 데이터가 있는지 확인
                        try:
                            test_df = stock.get_market_ohlcv_by_ticker(result, market="ALL")
                            if test_df is not None and not test_df.empty and "거래대금" in test_df.columns:
                                yesterday_str = result
                                break
                        except KeyError:
                            # pykrx 내부에서 컬럼 접근 실패 (휴장일)
                            continue
                        except Exception:
                            continue
                except Exception:
                    continue
        
        if not yesterday_str:
            # 최후의 수단: 주말만 제외한 날짜 사용 (데이터 확인 없이)
            for days_back in range(0, 61):
                test_date = yesterday - timedelta(days=days_back)
                weekday = test_date.weekday()
                if weekday < 5:  # 월~금
                    yesterday_str = test_date.strftime("%Y%m%d")
                    break
        
        if not yesterday_str:
            raise ValueError("영업일을 찾을 수 없습니다.")
        
        # 찾은 날짜가 계산된 어제 날짜와 얼마나 차이가 나는지 확인
        found_date_obj = datetime.strptime(yesterday_str, "%Y%m%d")
        days_diff = (yesterday.date() - found_date_obj.date()).days
        
        # 3개월 전 날짜 계산
        three_months_ago = (today - timedelta(days=90)).strftime("%Y%m%d")
        
        # 날짜 차이 정보를 반환값에 포함 (경고 표시용)
        return yesterday_str, three_months_ago, days_diff
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
        name="일봉",
        increasing_line_color='red',      # 양봉: 빨간색
        increasing_fillcolor='red',
        decreasing_line_color='blue',      # 음봉: 파란색
        decreasing_fillcolor='blue'
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
# 디버깅: 환경 정보 및 시간대 정보 출력
with st.expander("🔍 디버깅 정보 (환경 및 시간대)", expanded=False):
    try:
        import sys
        import platform
        import time
        import os
        
        st.write("**Python 환경 정보:**")
        st.write(f"- Python 버전: {sys.version}")
        st.write(f"- Python 실행 경로: {sys.executable}")
        st.write(f"- 플랫폼: {platform.platform()}")
        st.write(f"- 시스템: {platform.system()}")
        
        st.write(f"\n**패키지 버전 정보:**")
        try:
            import pykrx
            st.write(f"- pykrx 버전: {pykrx.__version__ if hasattr(pykrx, '__version__') else '버전 정보 없음'}")
        except Exception as e:
            st.write(f"- pykrx 버전 확인 실패: {str(e)}")
        
        try:
            import pandas as pd
            st.write(f"- pandas 버전: {pd.__version__}")
        except Exception:
            st.write(f"- pandas 버전: 확인 불가")
        
        try:
            import requests
            st.write(f"- requests 버전: {requests.__version__}")
        except Exception:
            st.write(f"- requests 버전: 확인 불가")
        
        st.write(f"\n**네트워크 환경:**")
        try:
            import socket
            hostname = socket.gethostname()
            st.write(f"- 호스트명: {hostname}")
        except Exception:
            st.write(f"- 호스트명: 확인 불가")
        
        # 환경 변수 확인
        st.write(f"\n**환경 변수:**")
        env_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'NO_PROXY', 'no_proxy']
        for var in env_vars:
            value = os.environ.get(var, '설정되지 않음')
            if value != '설정되지 않음':
                st.write(f"- {var}: {value}")
        
        st.write(f"\n**시간대 정보:**")
        # UTC 시간
        utc_now = datetime.utcnow()
        
        # 로컬 시간
        local_now = datetime.now()
        
        # 한국 시간대 시간
        if USE_ZONEINFO:
            kst = ZoneInfo("Asia/Seoul")
            kst_now = datetime.now(kst)
        else:
            kst = pytz.timezone("Asia/Seoul")
            kst_now = datetime.now(kst)
        
        st.write("**시스템 시간 정보:**")
        st.write(f"- UTC 시간: {utc_now.strftime('%Y-%m-%d %H:%M:%S')}")
        st.write(f"- 로컬 시간: {local_now.strftime('%Y-%m-%d %H:%M:%S')} (시스템 timezone 기준)")
        st.write(f"- 한국 시간(KST): {kst_now.strftime('%Y-%m-%d %H:%M:%S')} (명시적 KST)")
        st.write(f"- KST와 UTC 차이: {kst_now.hour - utc_now.hour}시간 (예상: 9시간)")
        st.write(f"- 시스템 timezone: {time.tzname}")
        st.write(f"- TZ 환경변수: {os.environ.get('TZ', '설정되지 않음')}")
        
        # 시간대 정보 상세
        st.write(f"\n**시간대 상세 정보:**")
        if USE_ZONEINFO:
            st.write(f"- zoneinfo 사용 중")
            st.write(f"- KST timezone 객체: {kst}")
            st.write(f"- KST 시간 타임존 정보: {kst_now.tzinfo}")
        else:
            st.write(f"- pytz 사용 중")
            st.write(f"- KST timezone 객체: {kst}")
            st.write(f"- KST 시간 타임존 정보: {kst_now.tzinfo}")
        
        # 계산된 날짜들
        yesterday_calc = kst_now - timedelta(days=1)
        st.write(f"\n**계산된 날짜 (KST 기준):**")
        st.write(f"- 어제 날짜: {yesterday_calc.strftime('%Y-%m-%d (%A)')}")
        st.write(f"- 어제 날짜 문자열: {yesterday_calc.strftime('%Y%m%d')}")
        st.write(f"- 어제 날짜 요일: {yesterday_calc.weekday()} (0=월요일, 6=일요일)")
        
        # UTC 기준으로도 계산
        yesterday_utc = utc_now - timedelta(days=1)
        st.write(f"\n**비교: UTC 기준 계산:**")
        st.write(f"- UTC 어제 날짜: {yesterday_utc.strftime('%Y-%m-%d (%A)')}")
        st.write(f"- UTC 어제 날짜 문자열: {yesterday_utc.strftime('%Y%m%d')}")
        st.write(f"- ⚠️ 차이: KST와 UTC 기준 날짜가 다를 수 있습니다!")
        
        # pykrx API 연결 테스트
        st.write(f"\n**pykrx API 연결 테스트:**")
        try:
            # 간단한 API 호출 테스트
            test_ticker_list = stock.get_market_ticker_list(market="ALL")
            if test_ticker_list:
                st.write(f"- ✅ get_market_ticker_list() 성공: {len(test_ticker_list)}개 종목")
            else:
                st.write(f"- ⚠️ get_market_ticker_list() 결과: 빈 리스트")
        except Exception as api_test_e:
            st.write(f"- ❌ API 연결 테스트 실패: {str(api_test_e)}")
            st.write(f"- 오류 타입: {type(api_test_e).__name__}")
            import traceback
            st.write(f"- 상세 오류:")
            st.code(traceback.format_exc())
            
    except Exception as debug_e:
        st.write(f"디버깅 정보 수집 중 오류: {str(debug_e)}")
        import traceback
        st.code(traceback.format_exc())

try:
    yesterday_str, three_months_ago, days_diff = get_business_dates()
    yesterday_display = datetime.strptime(yesterday_str, "%Y%m%d").strftime("%Y-%m-%d")
    
    # 찾은 날짜가 계산된 날짜와 차이가 나는 경우 경고
    if days_diff > 7:
        st.warning(
            f"⚠️ **주의**: 계산된 어제 날짜로부터 {days_diff}일 전 날짜({yesterday_display})를 사용합니다.\n\n"
            f"**가능한 원인:**\n"
            f"- 최근 {days_diff}일간 모든 날짜에서 데이터 조회 실패\n"
            f"- pykrx API 서버 문제 또는 네트워크 문제\n"
            f"- 장기 휴장 기간\n\n"
            f"실제 데이터가 있는 가장 최근 날짜를 사용합니다."
        )
    
    # 디버깅: 찾은 날짜 정보
    with st.expander("🔍 디버깅 정보 (시간대 및 날짜)", expanded=False):
        st.write(f"**찾은 날짜:**")
        st.write(f"- 어제 날짜 (조회용): {yesterday_str} ({yesterday_display})")
        st.write(f"- 3개월 전 날짜: {three_months_ago}")
        st.write(f"- 날짜 차이: 계산된 어제 날짜로부터 {days_diff}일 전")
        if days_diff > 0:
            # 계산된 어제 날짜 재계산
            if USE_ZONEINFO:
                kst = ZoneInfo("Asia/Seoul")
            else:
                kst = pytz.timezone("Asia/Seoul")
            calculated_yesterday = (datetime.now(kst) - timedelta(days=1)).strftime("%Y-%m-%d")
            st.write(f"- 계산된 어제 날짜: {calculated_yesterday}")
            st.write(f"- ⚠️ {days_diff}일 차이가 있습니다. 최근 날짜에서 데이터를 찾지 못했습니다.")
        
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
    st.warning(
        f"⚠️ {yesterday_display} 거래대금 데이터를 불러올 수 없습니다.\n\n"
        f"**가능한 원인:**\n"
        f"- 시장이 휴장일일 수 있습니다 (주말, 공휴일 등)\n"
        f"- 데이터 서버에 일시적인 문제가 있을 수 있습니다\n"
        f"- 날짜가 미래일 수 있습니다\n\n"
        f"다른 날짜를 선택하거나 잠시 후 다시 시도해주세요."
    )
    
    # 디버깅: 데이터 조회 시도 정보
    with st.expander("🔍 디버깅 정보 (데이터 조회)", expanded=True):
        st.write(f"**조회 시도한 날짜:** {yesterday_str}")
        st.write(f"**조회 시도한 날짜 (표시용):** {yesterday_display}")
        
        # 직접 API 호출 시도 (raw 데이터 확인)
        st.write(f"\n**직접 API 호출 테스트 (raw 데이터 확인):**")
        try:
            # pykrx의 내부 함수를 직접 호출하여 raw 데이터 확인
            from pykrx import stock
            import requests
            from datetime import datetime as dt
            
            # 날짜를 datetime으로 변환
            date_obj = dt.strptime(yesterday_str, "%Y%m%d")
            
            # pykrx의 실제 API 호출 방식 확인
            st.write(f"- 날짜: {yesterday_str} ({date_obj.strftime('%Y-%m-%d')})")
            
            # 직접 API 호출 시도
            test_df = stock.get_market_ohlcv_by_ticker(yesterday_str, market="ALL")
            if test_df is not None:
                st.write(f"- ✅ API 호출 성공")
                st.write(f"- 데이터프레임 크기: {test_df.shape}")
                st.write(f"- 실제 컬럼: {list(test_df.columns)}")
                st.write(f"- 데이터프레임 타입: {type(test_df)}")
                if not test_df.empty:
                    st.write(f"- 데이터 행 수: {len(test_df)}")
                    st.write(f"- 인덱스 샘플: {list(test_df.index[:5]) if len(test_df) > 0 else '없음'}")
                    # 첫 번째 행 데이터 샘플
                    if len(test_df) > 0:
                        st.write(f"- 첫 번째 행 데이터:")
                        st.json(test_df.iloc[0].to_dict())
                else:
                    st.write(f"- ⚠️ 데이터프레임이 비어있습니다")
            else:
                st.write(f"- ⚠️ API 호출 결과: None")
        except KeyError as key_e:
            st.write(f"- ❌ KeyError 발생: {str(key_e)}")
            st.write(f"- ⚠️ pykrx 내부에서 컬럼 접근 실패 (휴장일 또는 데이터 없음)")
            st.write(f"- 이 오류는 pykrx 라이브러리 내부에서 발생합니다.")
            st.write(f"- 해결 방법: 더 이전 날짜를 시도하거나 다른 API 사용")
        except Exception as api_e:
            st.write(f"- ❌ API 호출 실패: {str(api_e)}")
            st.write(f"- 오류 타입: {type(api_e).__name__}")
            import traceback
            st.write(f"- 상세 오류:")
            st.code(traceback.format_exc())
        
        # 다른 날짜들도 시도
        st.write(f"\n**다른 날짜 시도 (최대 30일 전까지):**")
        found_date = None
        for days_back in range(0, 31):
            try:
                test_date = datetime.strptime(yesterday_str, "%Y%m%d") - timedelta(days=days_back)
                test_date_str = test_date.strftime("%Y%m%d")
                test_df = stock.get_market_ohlcv_by_ticker(test_date_str, market="ALL")
                if test_df is not None:
                    st.write(f"- {test_date_str}:")
                    st.write(f"  - 크기: {test_df.shape}")
                    st.write(f"  - 컬럼: {list(test_df.columns)}")
                    if not test_df.empty and "거래대금" in test_df.columns:
                        st.write(f"  - ✅ 데이터 있음 ({len(test_df)}개 종목)")
                        found_date = test_date_str
                        break
                    else:
                        st.write(f"  - ❌ 데이터 없음 또는 컬럼 누락")
                else:
                    st.write(f"- ❌ {test_date_str}: API 호출 결과 None")
            except KeyError as key_e:
                # pykrx 내부 KeyError (휴장일)
                st.write(f"- ⚠️ {test_date_str}: 휴장일 또는 데이터 없음 (KeyError)")
                continue
            except Exception as test_e:
                st.write(f"- ❌ {test_date_str}: 오류 - {str(test_e)}")
                st.write(f"  - 오류 타입: {type(test_e).__name__}")
        
        if found_date:
            st.write(f"\n**✅ 사용 가능한 날짜 발견: {found_date}**")
        else:
            st.write(f"\n**❌ 30일 내 사용 가능한 날짜를 찾을 수 없습니다.**")
            st.write(f"**가능한 원인:**")
            st.write(f"- 장기 휴장 기간 (연말연시 등)")
            st.write(f"- pykrx API 서버 문제")
            st.write(f"- 날짜 형식 문제")
    
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
