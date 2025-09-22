#!/usr/bin/env python3
# oracle-instantclient-23.9.0.25.07-1.el9.x86_64.rpm
# wget https://download.oracle.com/otn_software/linux/instantclient/2390000/oracle-instantclient-basic-23.9.0.25.07-1.el9.x86_64.rpm
# sudo dnf install  oracle-instantclient-basic-23.9.0.25.07-1.el9.x86_64.rpm
import os
import asyncio
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
import oracledb
from fastmcp import FastMCP

# 환경 변수 설정
ORACLE_DB_USER = os.getenv("ORACLE_DB_USER", "apps")
ORACLE_DB_PASSWORD = os.getenv("ORACLE_DB_PASSWORD", "apps")
ORACLE_DB_DSN = os.getenv("ORACLE_DB_DSN", "161.33.6.86:1521/ebsdb")

AGENT_ENDPOINT_ID=os.getenv("AGENT_ENDPOINT_ID", "ocid1.genaiagentendpoint.oc1.ap-osaka-1.amaaaaaarykjadqah2zw7mxczrxoa6o3ebdneenum4s5g5mqfk2urommiytq")
MCP_SERVER_PORT=os.getenv("MCP_SERVER_PORT", "8000")
REGION=os.getenv("REGION", "ap-osaka-1")
PROFILE=os.getenv("PROFILE", "osaka")
IS_AGENT_SETUP=os.getenv("IS_AGENT_SETUP", "False")

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
    AND RELEASE_LOOKUP_CODE is NULL
    AND aha.HOLD_LOOKUP_CODE IN ('QTY ORD', 'QTY REC', 'PRICE', 'AMT ORG')
FETCH FIRST 20 ROWS ONLY
"""

# Pydantic 모델 정의
class HoldingInvoice(BaseModel):
    """홀딩된 인보이스 정보"""
    model_config = {"json_schema_extra": {"example": {
        "invoice_id": "12345",
        "line_location_id": "67890",
        "hold_id": "88285",
        "hold_lookup_code": "QTY ORD",
        "hold_reason": "Quantity billed exceeds quantity ordered "
    }}}
    
    invoice_id: Optional[int] = Field(None, description="인보이스 ID")
    line_location_id: Optional[int] = Field(None, description="라인 위치 ID")
    hold_id: Optional[int] = Field(None, description="홀드 ID")
    hold_lookup_code: Optional[str] = Field(None, description="홀드 룩업 코드")
    hold_reason: Optional[str] = Field(None, description="홀드 사유")

    # last_update_date: Optional[str] = Field(None, description="최종 업데이트 날짜")
    # last_updated_by: Optional[int] = Field(None, description="최종 업데이트 사용자")
    # held_by: Optional[int] = Field(None, description="홀딩 처리자")
    # hold_date: Optional[str] = Field(None, description="홀딩 날짜")
    # hold_reason: Optional[str] = Field(None, description="홀딩 사유")
    # release_lookup_code: Optional[str] = Field(None, description="릴리스 룩업 코드")
    # release_reason: Optional[str] = Field(None, description="릴리스 사유")
    # org_id: Optional[int] = Field(None, description="조직 ID")
    # responsibility_id: Optional[int] = Field(None, description="책임 ID")
    # rcv_transaction_id: Optional[int] = Field(None, description="수령 트랜잭션 ID")
    # hold_details: Optional[str] = Field(None, description="홀딩 상세내용")
    # line_number: Optional[int] = Field(None, description="라인 번호")
    # wf_status: Optional[str] = Field(None, description="워크플로우 상태")
    # validation_request_id: Optional[int] = Field(None, description="검증 요청 ID")

class DatabaseConnectionError(Exception):
    """데이터베이스 연결 오류"""
    pass

class DatabaseQueryError(Exception):
    """데이터베이스 쿼리 오류"""
    pass

def get_oracle_connection():
    """Oracle 데이터베이스 연결을 생성합니다."""
    try:
        # 지갑 설정
        oracledb.init_oracle_client()
        
        # 연결 생성
        connection = oracledb.connect(
            user=ORACLE_DB_USER,
            password=ORACLE_DB_PASSWORD,
            dsn=ORACLE_DB_DSN
        )
        
        return connection
        
    except oracledb.Error as e:
        error, = e.args
        raise DatabaseConnectionError(f"Oracle DB 연결 실패: {error.message}")
    except Exception as e:
        raise DatabaseConnectionError(f"데이터베이스 연결 중 예상치 못한 오류: {str(e)}")

def format_date(date_value):
    """날짜 포맷팅"""
    if date_value is None:
        return None
    if isinstance(date_value, datetime):
        return date_value.strftime('%Y-%m-%d %H:%M:%S')
    return str(date_value)

@mcp.tool()
def list_holding_invoices() -> List[HoldingInvoice]:
    """
    홀딩된 인보이스 목록을 반환합니다 (상위 20개).

    Oracle 데이터베이스에서 현재 홀딩 상태인 인보이스의 상위 20개를 조회합니다.
    홀딩 날짜 기준으로 최신순으로 정렬되어 반환됩니다.

    Returns:
        List[HoldingInvoice]: 홀딩된 인보이스 목록 (최대 20개)

    Raises:
        DatabaseConnectionError: 데이터베이스 연결 실패시
        DatabaseQueryError: 쿼리 실행 실패시

    Example:
        ```json
        [
            {
                "invoice_id": "12345",
                "line_location_id": "67890",
                "hold_id": "88285",
                "hold_lookup_code": "QTY ORD",
                "hold_reason": "Quantity billed exceeds quantity ordered "
            }
        ]
        ```
    """
    connection = None
    try:
        # 데이터베이스 연결
        connection = get_oracle_connection()
        cursor = connection.cursor()
        
        # 쿼리 실행
        cursor.execute(HOLD_LIST_SQL)
        rows = cursor.fetchall()
        
        # 컬럼명 가져오기
        column_names = [desc[0].lower() for desc in cursor.description]
        
        # 결과 변환
        holding_invoices = []
        for row in rows:
            row_dict = dict(zip(column_names, row))
            
            # 날짜 필드 포맷팅
            if 'last_update_date' in row_dict:
                row_dict['last_update_date'] = format_date(row_dict['last_update_date'])
            if 'hold_date' in row_dict:
                row_dict['hold_date'] = format_date(row_dict['hold_date'])
            
            holding_invoice = HoldingInvoice(**row_dict)
            holding_invoices.append(holding_invoice)
        
        return holding_invoices
        
    except DatabaseConnectionError:
        raise
    except oracledb.Error as e:
        error, = e.args
        raise DatabaseQueryError(f"쿼리 실행 실패: {error.message}")
    except Exception as e:
        raise DatabaseQueryError(f"데이터 조회 중 예상치 못한 오류: {str(e)}")
    finally:
        if connection:
            try:
                connection.close()
            except:
                pass

@mcp.tool()
def get_hold_statistics() -> dict:
    """
    홀딩 통계 정보를 반환합니다.

    각 홀드 타입별 건수와 전체 홀딩 건수를 조회합니다.

    Returns:
        dict: 홀딩 통계 정보

    Example:
        ```json
        {
            "total_holds": 156,
            "hold_type_counts": {
                "PRICE": 45,
                "QTY ORD": 32,
                "QTY REC": 28,
                "AMT ORG": 21
            }
        }
        ```
    """
    connection = None
    try:
        connection = get_oracle_connection()
        cursor = connection.cursor()
        
        # 통계 쿼리
        stats_sql = """
        SELECT 
            HOLD_LOOKUP_CODE,
            COUNT(*) as hold_count
        FROM ap_holds_all
        WHERE HOLD_LOOKUP_CODE IN ('QTY ORD', 'QTY REC', 'PRICE', 'AMT ORG')
        GROUP BY HOLD_LOOKUP_CODE
        ORDER BY COUNT(*) DESC
        """
        
        cursor.execute(stats_sql)
        rows = cursor.fetchall()
        
        hold_type_counts = {}
        total_holds = 0
        
        for row in rows:
            hold_type = row[0]
            count = row[1]
            hold_type_counts[hold_type] = count
            total_holds += count
        
        return {
            "total_holds": total_holds,
            "hold_type_counts": hold_type_counts
        }
        
    except Exception as e:
        raise DatabaseQueryError(f"통계 조회 중 오류: {str(e)}")
    finally:
        if connection:
            try:
                connection.close()
            except:
                pass

@mcp.tool()
def test_database_connection() -> dict:
    """
    데이터베이스 연결 상태를 테스트합니다.

    Returns:
        dict: 연결 테스트 결과

    Example:
        ```json
        {
            "status": "success",
            "message": "데이터베이스 연결 성공",
            "timestamp": "2024-01-15 10:30:00"
        }
        ```
    """
    try:
        connection = get_oracle_connection()
        cursor = connection.cursor()
        
        # 간단한 테스트 쿼리
        cursor.execute("SELECT SYSDATE FROM DUAL")
        result = cursor.fetchone()
        
        connection.close()
        
        return {
            "status": "success",
            "message": "데이터베이스 연결 성공",
            "timestamp": format_date(result[0]) if result else None
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"데이터베이스 연결 실패: {str(e)}",
            "timestamp": format_date(datetime.now())
        }

if __name__ == "__main__":
    print("🚀 Invoice Holding Management Server 시작")
    print("🔗 Oracle DB 연결 정보:")
    print(f"   - 사용자: {ORACLE_DB_USER}")
    print(f"   - DSN: {ORACLE_DB_DSN}")
    print(f"🌐 MCP Server: http://localhost:{MCP_SERVER_PORT}")
    print("\n🎯 MCP 서버 시작 중...")
    
    # 연결 테스트
    try:
        test_result = test_database_connection()
        if test_result["status"] == "success":
            print("✅ 데이터베이스 연결 테스트 성공")
        else:
            print(f"❌ 데이터베이스 연결 테스트 실패: {test_result['message']}")
    except Exception as e:
        print(f"⚠️ 연결 테스트 중 오류: {str(e)}")
    
    mcp.run(transport="streamable-http", port=int(MCP_SERVER_PORT))