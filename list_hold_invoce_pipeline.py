"""
title: list holding invoice pipeline
author: WY
date: 2025-10-20
version: 1.0
license: MIT
description: A list holding invoice pipeline
requirements: oracledb
"""
import os
import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
import oracledb
from typing import Union, Generator, Iterator

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 환경 변수 설정
ORACLE_DB_USER ="apps"
ORACLE_DB_PASSWORD = "apps"
ORACLE_DB_DSN = "161.33.6.86:1521/ebsdb"

# ORACLE_DB_USER = os.getenv("ORACLE_DB_USER", "apps")
# ORACLE_DB_PASSWORD = os.getenv("ORACLE_DB_PASSWORD", "apps")
# ORACLE_DB_DSN = os.getenv("ORACLE_DB_DSN", "161.33.6.86:1521/ebsdb")


# Oracle Client 초기화 상태 추적
_oracle_client_initialized = False

# SQL 쿼리 - 상위 20개 레코드만 조회
HOLD_LIST_SQL = """
SELECT
    aha.INVOICE_ID,
    aha.LINE_LOCATION_ID,
    aha.HOLD_ID,
    aha.HOLD_LOOKUP_CODE,
    aha.HOLD_REASON
FROM ap_holds_all aha
WHERE 1 = 1
    AND aha.RELEASE_LOOKUP_CODE IS NULL
    AND aha.HOLD_LOOKUP_CODE IN ('QTY ORD', 'QTY REC', 'PRICE', 'AMT ORG')
ORDER BY aha.HOLD_ID DESC
FETCH FIRST 20 ROWS ONLY
"""

# 통계 SQL 쿼리
STATS_SQL = """
SELECT 
    HOLD_LOOKUP_CODE,
    COUNT(*) as hold_count
FROM ap_holds_all
WHERE RELEASE_LOOKUP_CODE IS NULL
    AND HOLD_LOOKUP_CODE IN ('QTY ORD', 'QTY REC', 'PRICE', 'AMT ORG')
GROUP BY HOLD_LOOKUP_CODE
ORDER BY COUNT(*) DESC
"""

# Pydantic 모델 정의 (Pydantic v2 호환)
class HoldingInvoice(BaseModel):
    """홀딩된 인보이스 정보"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "invoice_id": 12345,
                "line_location_id": 67890,
                "hold_id": 88285,
                "hold_lookup_code": "QTY ORD",
                "hold_reason": "Quantity billed exceeds quantity ordered"
            }
        }
    )
    
    invoice_id: Optional[int] = Field(None, description="인보이스 ID")
    line_location_id: Optional[int] = Field(None, description="라인 위치 ID")
    hold_id: Optional[int] = Field(None, description="홀드 ID")
    hold_lookup_code: Optional[str] = Field(None, description="홀드 룩업 코드")
    hold_reason: Optional[str] = Field(None, description="홀드 사유")

class DatabaseConnectionError(Exception):
    """데이터베이스 연결 오류"""
    pass

class DatabaseQueryError(Exception):
    """데이터베이스 쿼리 오류"""
    pass

def init_oracle_client():
    """Oracle Client 초기화 (한 번만 실행)"""
    global _oracle_client_initialized
    if not _oracle_client_initialized:
        try:
            # Oracle Instant Client가 설치되어 있는 경우에만 초기화
            #oracledb.init_oracle_client(lib_dir="/usr/lib/oracle/23/client64/lib")
            oracledb.init_oracle_client()
            _
            _oracle_client_initialized = True
            logger.info("Oracle Client 초기화 완료")
        except Exception as e:
            # 이미 초기화되었거나 Thick mode가 불가능한 경우
            # Thin mode로 동작 (기본값)
            logger.info(f"Oracle Client Thin mode 사용: {e}")
            _oracle_client_initialized = True

def get_oracle_connection():
    """Oracle 데이터베이스 연결을 생성합니다."""
    try:
        # Oracle Client 초기화 (선택사항 - Thin mode가 기본)
        init_oracle_client()
        
        logger.info(f"Oracle DB 연결 시도: {ORACLE_DB_USER}@{ORACLE_DB_DSN}")
        
        # 연결 생성 (Oracle 19c+ 기본 UTF-8 지원)
        connection = oracledb.connect(
            user=ORACLE_DB_USER,
            password=ORACLE_DB_PASSWORD,
            dsn=ORACLE_DB_DSN
        )
        
        # 연결 테스트
        # cursor = connection.cursor()
        # cursor.execute("SELECT 1 FROM DUAL")
        # cursor.fetchone()
        # cursor.close()
        
        logger.info("Oracle DB 연결 성공")
        return connection
        
    except oracledb.Error as e:
        error_msg = str(e)
        logger.error(f"Oracle DB 연결 실패: {error_msg}")
        raise DatabaseConnectionError(f"Oracle DB 연결 실패: {error_msg}")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"데이터베이스 연결 중 예상치 못한 오류: {error_msg}")
        raise DatabaseConnectionError(f"데이터베이스 연결 중 예상치 못한 오류: {error_msg}")

def format_date(date_value):
    """날짜 포맷팅"""
    if date_value is None:
        return None
    if isinstance(date_value, datetime):
        return date_value.strftime('%Y-%m-%d %H:%M:%S')
    return str(date_value)

def safe_close_connection(connection):
    """안전한 연결 종료"""
    if connection:
        try:
            connection.close()
            logger.debug("DB 연결 종료됨")
        except Exception as e:
            logger.warning(f"연결 종료 중 오류: {e}")

from typing import Generator

def list_holding_invoices(sql: str = HOLD_LIST_SQL, limit: int = 20) -> Generator[HoldingInvoice, None, None]:
    """
    홀딩된 인보이스 목록을 Generator 형태로 반환합니다 (상위 20개).

    Oracle 데이터베이스에서 현재 홀딩 상태인 인보이스의 상위 20개를 조회합니다.
    홀딩 ID 기준으로 최신순으로 정렬되어 반환됩니다.
    각 레코드는 지연 평가(lazy evaluation) 방식으로 하나씩 yield 됩니다.

    Returns:
        Generator[HoldingInvoice, None, None]: 홀딩된 인보이스를 하나씩 반환하는 generator

    Raises:
        DatabaseConnectionError: 데이터베이스 연결 실패시
        DatabaseQueryError: 쿼리 실행 실패시
    """
    connection = None
    try:
        logger.info("홀딩된 인보이스 목록 조회 시작")
        
        # DB 연결
        connection = get_oracle_connection()
        cursor = connection.cursor()
        
        logger.debug(f"SQL 실행: {sql}")
        cursor.execute(HOLD_LIST_SQL)
        
        # 컬럼명 가져오기
        column_names = [desc[0].lower() for desc in cursor.description]
        logger.debug(f"컬럼명: {column_names}")
        
        # 한 행씩 처리 (fetchone 기반 streaming)
        count = 0
        while True:
            row = cursor.fetchone()
            if not row:
                break  # 더 이상 결과 없음
            
            try:
                row_dict = dict(zip(column_names, row))

                # 날짜 필드 포맷팅
                if 'last_update_date' in row_dict:
                    row_dict['last_update_date'] = format_date(row_dict['last_update_date'])
                if 'hold_date' in row_dict:
                    row_dict['hold_date'] = format_date(row_dict['hold_date'])

                holding_invoice = HoldingInvoice(**row_dict)
                count += 1
                yield holding_invoice  # ✅ lazy 반환

            except Exception as e:
                logger.warning(f"행 {count} 처리 중 오류: {e}, 데이터: {row}")
                continue
        
        logger.info(f"총 {count}개의 인보이스를 생성했습니다.")

    except DatabaseConnectionError:
        raise
    except oracledb.Error as e:
        error_msg = str(e)
        logger.error(f"쿼리 실행 실패: {error_msg}")
        raise DatabaseQueryError(f"쿼리 실행 실패: {error_msg}")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"데이터 조회 중 예상치 못한 오류: {error_msg}")
        raise DatabaseQueryError(f"데이터 조회 중 예상치 못한 오류: {error_msg}")
    finally:
        safe_close_connection(connection)

class Pipeline:
    def __init__(self):
        self.name = "List Holing Invoice Pipeline"

    async def on_startup(self):
        pass

    async def on_shutdown(self):
        pass
    
    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:
        """
        ⚠️ This tool requires function_calling = "default" for proper event emission
        """

        try:

            # sql = get_list_holding_invoices_sql(user_message)
            sql = HOLD_LIST_SQL
            return json.dumps([inv.dict() for inv in list(list_holding_invoices(sql=HOLD_LIST_SQL))], indent=2, ensure_ascii=False)

        except DatabaseConnectionError as e:
            return f"DB 연결 실패: {e}"
        except Exception as e:
            return f"오류 발생: {e}"
         

async def tool_call():
    """비동기 메인 엔트리"""
    tool = Pipeline()
    result =  tool.pipe(user_message="홀딩된 인보이스 목록 보여줘", model_id="gpt-3.5-turbo", messages=[], body={})
    print(result)


if __name__ == "__main__":
    # 🚀 여기서 비동기 함수 실행
    #asyncio.run(tool_call())
    import json

    print(json.dumps([inv.dict() for inv in list(list_holding_invoices())], indent=2, ensure_ascii=False))

