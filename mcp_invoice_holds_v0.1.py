#!/usr/bin/env python3
# oracle-instantclient-23.9.0.25.07-1.el9.x86_64.rpm
# wget https://download.oracle.com/otn_software/linux/instantclient/2390000/oracle-instantclient-basic-23.9.0.25.07-1.el9.x86_64.rpm
# sudo dnf install  oracle-instantclient-basic-23.9.0.25.07-1.el9.x86_64.rpm

import os
import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
import oracledb
from fastmcp import FastMCP

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 환경 변수 설정
ORACLE_DB_USER = os.getenv("ORACLE_DB_USER", "apps")
ORACLE_DB_PASSWORD = os.getenv("ORACLE_DB_PASSWORD", "apps")
ORACLE_DB_DSN = os.getenv("ORACLE_DB_DSN", "161.33.6.86:1521/ebsdb")

AGENT_ENDPOINT_ID = os.getenv("AGENT_ENDPOINT_ID", "ocid1.genaiagentendpoint.oc1.ap-osaka-1.amaaaaaarykjadqah2zw7mxczrxoa6o3ebdneenum4s5g5mqfk2urommiytq")
MCP_SERVER_PORT = os.getenv("MCP_SERVER_PORT", "8000")
REGION = os.getenv("REGION", "ap-osaka-1")
PROFILE = os.getenv("PROFILE", "osaka")
IS_AGENT_SETUP = os.getenv("IS_AGENT_SETUP", "False")

# Oracle Client 초기화 상태 추적
_oracle_client_initialized = False

# FastMCP 서버 초기화
mcp = FastMCP("Invoice Holding Management")

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

class HoldStatistics(BaseModel):
    """홀딩 통계 정보"""
    total_holds: int = Field(description="전체 홀딩 건수")
    hold_type_counts: Dict[str, int] = Field(description="홀드 타입별 건수")

class ConnectionTestResult(BaseModel):
    """연결 테스트 결과"""
    status: str = Field(description="연결 상태")
    message: str = Field(description="상태 메시지")
    timestamp: Optional[str] = Field(None, description="테스트 실행 시간")

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
            oracledb.init_oracle_client()
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
        cursor = connection.cursor()
        cursor.execute("SELECT 1 FROM DUAL")
        cursor.fetchone()
        cursor.close()
        
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

@mcp.tool()
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

@mcp.tool()
def get_hold_statistics() -> HoldStatistics:
    """
    홀딩 통계 정보를 반환합니다.

    각 홀드 타입별 건수와 전체 홀딩 건수를 조회합니다.

    Returns:
        HoldStatistics: 홀딩 통계 정보

    Raises:
        DatabaseConnectionError: 데이터베이스 연결 실패시
        DatabaseQueryError: 쿼리 실행 실패시
    """
    connection = None
    try:
        logger.info("홀딩 통계 정보 조회 시작")
        
        connection = get_oracle_connection()
        cursor = connection.cursor()
        
        # 통계 쿼리 실행
        logger.debug(f"통계 SQL 실행: {STATS_SQL}")
        cursor.execute(STATS_SQL)
        rows = cursor.fetchall()
        
        logger.info(f"통계 조회 결과 수: {len(rows)}")
        
        hold_type_counts = {}
        total_holds = 0
        
        for row in rows:
            hold_type = row[0]
            count = int(row[1])
            hold_type_counts[hold_type] = count
            total_holds += count
            logger.debug(f"홀드 타입 {hold_type}: {count}건")
        
        result = HoldStatistics(
            total_holds=total_holds,
            hold_type_counts=hold_type_counts
        )
        
        logger.info(f"통계 조회 완료 - 전체: {total_holds}건")
        return result
        
    except DatabaseConnectionError:
        raise
    except oracledb.Error as e:
        error_msg = str(e)
        logger.error(f"통계 쿼리 실행 실패: {error_msg}")
        raise DatabaseQueryError(f"통계 쿼리 실행 실패: {error_msg}")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"통계 조회 중 오류: {error_msg}")
        raise DatabaseQueryError(f"통계 조회 중 오류: {error_msg}")
    finally:
        safe_close_connection(connection)

@mcp.tool()
def test_database_connection() -> ConnectionTestResult:
    """
    데이터베이스 연결 상태를 테스트합니다.

    Returns:
        ConnectionTestResult: 연결 테스트 결과
    """
    try:
        logger.info("데이터베이스 연결 테스트 시작")
        
        connection = get_oracle_connection()
        cursor = connection.cursor()
        
        # 간단한 테스트 쿼리
        cursor.execute("SELECT SYSDATE FROM DUAL")
        result = cursor.fetchone()
        
        safe_close_connection(connection)
        
        timestamp = format_date(result[0]) if result else format_date(datetime.now())
        
        logger.info("데이터베이스 연결 테스트 성공")
        return ConnectionTestResult(
            status="success",
            message="데이터베이스 연결 성공",
            timestamp=timestamp
        )
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"데이터베이스 연결 테스트 실패: {error_msg}")
        return ConnectionTestResult(
            status="error",
            message=f"데이터베이스 연결 실패: {error_msg}",
            timestamp=format_date(datetime.now())
        )

async def startup_checks():
    """서버 시작시 초기 점검"""
    try:
        logger.info("=== 서버 시작 전 점검 ===")
        
        # 환경변수 점검
        logger.info("환경변수 점검:")
        logger.info(f"  ORACLE_DB_USER: {ORACLE_DB_USER}")
        logger.info(f"  ORACLE_DB_DSN: {ORACLE_DB_DSN}")
        logger.info(f"  MCP_SERVER_PORT: {MCP_SERVER_PORT}")
        
        # 데이터베이스 연결 테스트
        test_result = test_database_connection()
        if test_result.status == "success":
            logger.info("✅ 초기 데이터베이스 연결 테스트 성공")
        else:
            logger.error(f"❌ 초기 데이터베이스 연결 테스트 실패: {test_result.message}")
            
        # 간단한 데이터 조회 테스트
        try:
            invoices = list_holding_invoices()
            logger.info(f"✅ 초기 데이터 조회 테스트 성공 - {len(invoices)}건 조회됨")
        except Exception as e:
            logger.error(f"❌ 초기 데이터 조회 테스트 실패: {e}")
            
    except Exception as e:
        logger.error(f"⚠️ 서버 시작 전 점검 중 오류: {e}")

if __name__ == "__main__":
    print("🚀 Invoice Holding Management Server 시작")
    print("🔗 Oracle DB 연결 정보:")
    print(f"   - 사용자: {ORACLE_DB_USER}")
    print(f"   - DSN: {ORACLE_DB_DSN}")
    print(f"🌐 MCP Server: http://localhost:{MCP_SERVER_PORT}")
    print("\n🎯 MCP 서버 시작 중...")
    
    # 비동기 초기화 실행
    asyncio.run(startup_checks())
    
    print("\n🎉 MCP 서버 시작 준비 완료!")
    print("📊 사용 가능한 도구:")
    print("   - list_holding_invoices: 홀딩된 인보이스 목록 조회")
    print("   - get_hold_statistics: 홀딩 통계 정보 조회")
    print("   - test_database_connection: DB 연결 상태 테스트")
    
    # MCP 서버 시작
    mcp.run(transport="streamable-http", port=int(MCP_SERVER_PORT), host="0.0.0.0")