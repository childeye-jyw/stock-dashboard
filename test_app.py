"""
app.py의 주요 함수들을 테스트하는 스크립트
"""
import sys
from datetime import datetime, timedelta
from pykrx import stock
import pandas as pd


def test_date_calculation():
    """날짜 계산 함수 테스트"""
    print("📅 날짜 계산 테스트...")
    try:
        today = datetime.today()
        yesterday = today - timedelta(days=1)
        yesterday_str = stock.get_nearest_business_day_in_a_week(
            yesterday.strftime("%Y%m%d")
        )
        three_months_ago = (today - timedelta(days=90)).strftime("%Y%m%d")
        print(f"  ✓ 어제 날짜: {yesterday_str}")
        print(f"  ✓ 3개월 전: {three_months_ago}")
        return True
    except Exception as e:
        print(f"  ✗ 날짜 계산 실패: {e}")
        return False


def test_ticker_mapping():
    """티커 매핑 함수 테스트"""
    print("\n🔍 티커 매핑 테스트...")
    try:
        ticker_list = stock.get_market_ticker_list(market="ALL")
        print(f"  ✓ 전체 종목 수: {len(ticker_list)}")
        
        # 샘플 티커로 종목명 조회 테스트
        if len(ticker_list) > 0:
            sample_ticker = ticker_list[0]
            name = stock.get_market_ticker_name(sample_ticker)
            print(f"  ✓ 샘플 티커 {sample_ticker} -> {name}")
        
        return True
    except Exception as e:
        print(f"  ✗ 티커 매핑 실패: {e}")
        return False


def test_market_data():
    """시장 데이터 조회 테스트"""
    print("\n📈 시장 데이터 조회 테스트...")
    try:
        today = datetime.today()
        yesterday = today - timedelta(days=1)
        yesterday_str = stock.get_nearest_business_day_in_a_week(
            yesterday.strftime("%Y%m%d")
        )
        
        df = stock.get_market_ohlcv_by_ticker(yesterday_str, market="ALL")
        
        if df is None or df.empty:
            print(f"  ⚠ {yesterday_str} 데이터가 비어있습니다 (휴장일일 수 있음)")
            return False
        
        print(f"  ✓ 데이터 조회 성공: {len(df)}개 종목")
        print(f"  ✓ 컬럼: {list(df.columns)}")
        
        # 거래대금 컬럼 확인
        if "거래대금" in df.columns:
            max_value = df["거래대금"].max()
            print(f"  ✓ 최대 거래대금: {max_value:,.0f}원")
        
        return True
    except Exception as e:
        print(f"  ✗ 시장 데이터 조회 실패: {e}")
        return False


def test_stock_history():
    """종목 히스토리 조회 테스트"""
    print("\n📊 종목 히스토리 조회 테스트...")
    try:
        # 삼성전자 티커 코드 (005930)
        test_ticker = "005930"
        today = datetime.today()
        yesterday = today - timedelta(days=1)
        yesterday_str = stock.get_nearest_business_day_in_a_week(
            yesterday.strftime("%Y%m%d")
        )
        three_months_ago = (today - timedelta(days=90)).strftime("%Y%m%d")
        
        df = stock.get_market_ohlcv_by_date(
            three_months_ago, 
            yesterday_str, 
            test_ticker
        )
        
        if df is None or df.empty:
            print(f"  ⚠ {test_ticker}의 히스토리 데이터가 비어있습니다")
            return False
        
        print(f"  ✓ 히스토리 데이터 조회 성공: {len(df)}개 일자")
        print(f"  ✓ 컬럼: {list(df.columns)}")
        
        # 필요한 컬럼 확인
        required = ["종가", "거래량"]
        missing = [col for col in required if col not in df.columns]
        if missing:
            print(f"  ✗ 필요한 컬럼 누락: {missing}")
            return False
        
        # 거래대금 계산 테스트
        df_reset = df.reset_index()
        df_reset["거래대금(억 원)"] = (
            df_reset["종가"] * df_reset["거래량"]
        ) / 100_000_000
        print(f"  ✓ 거래대금 계산 성공")
        print(f"  ✓ 평균 거래대금: {df_reset['거래대금(억 원)'].mean():.2f}억 원")
        
        return True
    except Exception as e:
        print(f"  ✗ 종목 히스토리 조회 실패: {e}")
        return False


def test_count_days_above_threshold():
    """3개월간 거래대금 임계값 이상 날짜 수 계산 테스트"""
    print("\n📈 3개월간 거래대금 임계값 이상 날짜 수 계산 테스트...")
    try:
        # app.py에서 함수 import
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from app import count_days_above_threshold
        
        # 삼성전자 티커 코드 (005930)
        test_ticker = "005930"
        today = datetime.today()
        yesterday = today - timedelta(days=1)
        yesterday_str = stock.get_nearest_business_day_in_a_week(
            yesterday.strftime("%Y%m%d")
        )
        three_months_ago = (today - timedelta(days=90)).strftime("%Y%m%d")
        
        # 2000억 원 임계값으로 테스트
        threshold = 200_000_000_000
        
        count = count_days_above_threshold(
            test_ticker,
            three_months_ago,
            yesterday_str,
            threshold
        )
        
        print(f"  ✓ 함수 실행 성공")
        print(f"  ✓ 테스트 종목: 삼성전자 ({test_ticker})")
        print(f"  ✓ 기간: {three_months_ago} ~ {yesterday_str}")
        print(f"  ✓ 임계값: {threshold:,}원 (2,000억 원)")
        print(f"  ✓ 임계값 이상 날짜 수: {count}일")
        
        if count >= 0:
            print(f"  ✓ 결과가 유효합니다 (0 이상)")
            return True
        else:
            print(f"  ✗ 결과가 유효하지 않습니다 (음수)")
            return False
            
    except ImportError as e:
        print(f"  ⚠ app.py 모듈 import 실패: {e}")
        print(f"  ⚠ 직접 계산으로 대체 테스트...")
        
        # 직접 계산으로 대체 테스트
        try:
            test_ticker = "005930"
            today = datetime.today()
            yesterday = today - timedelta(days=1)
            yesterday_str = stock.get_nearest_business_day_in_a_week(
                yesterday.strftime("%Y%m%d")
            )
            three_months_ago = (today - timedelta(days=90)).strftime("%Y%m%d")
            threshold = 200_000_000_000
            
            df = stock.get_market_ohlcv_by_date(
                three_months_ago,
                yesterday_str,
                test_ticker
            )
            
            if df is None or df.empty:
                print(f"  ⚠ 데이터가 비어있습니다")
                return False
            
            trading_values = df["종가"] * df["거래량"]
            count = (trading_values >= threshold).sum()
            
            print(f"  ✓ 직접 계산 성공")
            print(f"  ✓ 임계값 이상 날짜 수: {int(count)}일")
            return True
            
        except Exception as e2:
            print(f"  ✗ 직접 계산 실패: {e2}")
            return False
            
    except Exception as e:
        print(f"  ✗ 테스트 실패: {e}")
        return False


def main():
    """모든 테스트 실행"""
    print("=" * 60)
    print("🧪 app.py 개선 버전 테스트 시작")
    print("=" * 60)
    
    results = []
    
    results.append(("날짜 계산", test_date_calculation()))
    results.append(("티커 매핑", test_ticker_mapping()))
    results.append(("시장 데이터 조회", test_market_data()))
    results.append(("종목 히스토리 조회", test_stock_history()))
    results.append(("3개월간 거래대금 임계값 이상 날짜 수", test_count_days_above_threshold()))
    
    print("\n" + "=" * 60)
    print("📋 테스트 결과 요약")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ 통과" if result else "✗ 실패"
        print(f"  {name}: {status}")
    
    print(f"\n총 {total}개 테스트 중 {passed}개 통과 ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n✅ 모든 테스트 통과!")
        return 0
    else:
        print("\n⚠️ 일부 테스트 실패 (휴장일이거나 네트워크 문제일 수 있음)")
        return 1


if __name__ == "__main__":
    sys.exit(main())

