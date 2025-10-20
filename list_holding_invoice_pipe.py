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
            oracledb.init_oracle_client(lib_dir="/usr/lib/oracle/23/client64/lib")
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

def list_holding_invoices() -> List[HoldingInvoice]:

    """
    홀딩된 인보이스 목록을 반환합니다 (상위 20개).

    Oracle 데이터베이스에서 현재 홀딩 상태인 인보이스의 상위 20개를 조회합니다.
    홀딩 ID 기준으로 최신순으로 정렬되어 반환됩니다.

    Returns:
        List[HoldingInvoice]: 홀딩된 인보이스 목록 (최대 20개)

    Raises:
        DatabaseConnectionError: 데이터베이스 연결 실패시
        DatabaseQueryError: 쿼리 실행 실패시
    """

    connection = None
    try:
        logger.info("홀딩된 인보이스 목록 조회 시작")
        
        # 데이터베이스 연결
        connection = get_oracle_connection()
        cursor = connection.cursor()
        
        # 쿼리 실행
        logger.debug(f"SQL 실행: {HOLD_LIST_SQL}")
        cursor.execute(HOLD_LIST_SQL)
        rows = cursor.fetchall()
        
        logger.info(f"조회된 레코드 수: {len(rows)}")
        
        # 컬럼명 가져오기
        column_names = [desc[0].lower() for desc in cursor.description]
        logger.debug(f"컬럼명: {column_names}")
        
        # 결과 변환
        holding_invoices = []
        for i, row in enumerate(rows):
            try:
                row_dict = dict(zip(column_names, row))
                
                # 날짜 필드 포맷팅
                if 'last_update_date' in row_dict:
                    row_dict['last_update_date'] = format_date(row_dict['last_update_date'])
                if 'hold_date' in row_dict:
                    row_dict['hold_date'] = format_date(row_dict['hold_date'])
                
                holding_invoice = HoldingInvoice(**row_dict)
                holding_invoices.append(holding_invoice)
                
            except Exception as e:
                logger.warning(f"행 {i} 처리 중 오류: {e}, 데이터: {row}")
                continue
        
        logger.info(f"성공적으로 처리된 레코드 수: {len(holding_invoices)}")
        return holding_invoices
        
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


import json
from typing import List

def holding_invoices_to_json(holding_invoices: List[HoldingInvoice]) -> str:
    """
    HoldingInvoice 객체 리스트를 JSON 문자열로 변환하는 함수

    Args:
        holding_invoices (List[HoldingInvoice]): HoldingInvoice 객체 리스트

    Returns:
        str: JSON 문자열
    """
    try:
        json_str = json.dumps(
            [invoice.model_dump() for invoice in holding_invoices],
            ensure_ascii=False,
            indent=2  # 보기 좋게 들여쓰기
        )
        return json_str
    except Exception as e:
        logger.error(f"HoldingInvoice 리스트를 JSON으로 변환 중 오류: {e}")
        raise

from typing import List

def holding_invoices_to_markdown(holding_invoices: List[HoldingInvoice]) -> str:
    """
    HoldingInvoice 객체 리스트를 Markdown 테이블로 변환

    Args:
        holding_invoices (List[HoldingInvoice]): HoldingInvoice 객체 리스트

    Returns:
        str: Markdown 테이블 문자열
    """
    if not holding_invoices:
        return "⚠️ No holding invoices found."

    # 첫 번째 객체 기준으로 헤더 추출
    headers = holding_invoices[0].model_dump().keys()

    # Markdown 헤더 라인
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"

    # 각 행을 Markdown으로 변환
    rows_md = []
    for invoice in holding_invoices:
        row_dict = invoice.model_dump()
        row_md = "| " + " | ".join(str(row_dict.get(h, "")) for h in headers) + " |"
        rows_md.append(row_md)

    markdown_result = "\n".join([header_line, separator_line] + rows_md)
    return markdown_result



class Tools:
    def __init__(self):
        # Add a note about function calling mode requirements
        self.description = "T홀딩된 인보이스 목록을 반환합니다 (상위 20개)."

    async def list_holding_invoices_tool(self, prompt: str, __event_emitter__=None) -> str:
        """
        ⚠️ This tool requires function_calling = "default" for proper event emission
        """
        # Safe to use message events in Default mode
        
        # await __event_emitter__({
        #     "type": "status",
        #     "data": {
        #         "description": f"list_holding_invoices processing ",
        #         "done": True
        #     }
        # })
        holdings = list_holding_invoices()
         
        # status update 

        # await __event_emitter__({
        #     "type": "status",
        #     "data": {
        #         "description": f"list_holding_invoices processing complete!",
        #         "done": True
        #     }
        # })
        resp = holding_invoices_to_json(holdings)
        # resp = holding_invoices_to_markdown(holdings)
        return resp
    
def direct_call():
    print("🚀 Invoice Holding Management Server 시작")
    print("🔗 Oracle DB 연결 정보:")
    print(f"   - 사용자: {ORACLE_DB_USER}")
    print(f"   - DSN: {ORACLE_DB_DSN}")
    print("\n🎯 MCP 서버 시작 중...")
    
    holdings = list_holding_invoices()
    print("   - list_holding_invoices: 홀딩된 인보이스 목록 조회")
    # json_output = holding_invoices_to_json(holdings)
    # print (json_output)
    # print(holding_invoices_to_json(holdings))
    print(holding_invoices_to_markdown(holdings))
 

async def tool_call():
    """비동기 메인 엔트리"""
    tool = Tools()
    result = await tool.list_holding_invoices_tool(prompt="홀딩된 인보이스 목록 보여줘")
    print(result)


if __name__ == "__main__":
    # 🚀 여기서 비동기 함수 실행
    asyncio.run(tool_call())

