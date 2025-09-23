#!/usr/bin/env python3
import json
import os
from datetime import datetime
from typing import Dict, Any

def save_openapi_schema() -> str:
    """
    Invoice Holding Management API의 OpenAPI 3.0 스키마를 생성하고 파일로 저장합니다.
    
    Returns:
        str: 저장된 파일 경로
    """
    
    openapi_schema: Dict[str, Any] = {
        "openapi": "3.0.3",
        "info": {
            "title": "Invoice Holding Management API",
            "description": "Oracle EBS 시스템의 홀딩된 인보이스를 관리하는 API입니다. 홀딩된 인보이스 조회, 통계, 데이터베이스 연결 테스트 기능을 제공합니다.",
            "version": "1.0.0",
            "contact": {
                "name": "Invoice Holding Management Team",
                "email": "support@company.com"
            },
            "license": {
                "name": "MIT",
                "url": "https://opensource.org/licenses/MIT"
            }
        },
        "servers": [
            {
                "url": f"http://localhost:{os.getenv('MCP_SERVER_PORT', '8000')}",
                "description": "Local development server"
            }
        ],
        "paths": {
            "/tools/list_holding_invoices": {
                "post": {
                    "summary": "홀딩된 인보이스 목록 조회",
                    "description": "Oracle 데이터베이스에서 현재 홀딩 상태인 인보이스의 상위 20개를 조회합니다. 홀딩 날짜 기준으로 최신순으로 정렬되어 반환됩니다.",
                    "operationId": "listHoldingInvoices",
                    "tags": ["Invoice Management"],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "arguments": {
                                            "type": "object",
                                            "properties": {},
                                            "additionalProperties": False
                                        }
                                    },
                                    "required": ["arguments"]
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "홀딩된 인보이스 목록 조회 성공",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "content": {
                                                "type": "array",
                                                "items": {
                                                    "$ref": "#/components/schemas/HoldingInvoice"
                                                },
                                                "maxItems": 20,
                                                "description": "홀딩된 인보이스 목록 (최대 20개)"
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "500": {
                            "$ref": "#/components/responses/DatabaseError"
                        }
                    }
                }
            },
            "/tools/get_hold_statistics": {
                "post": {
                    "summary": "홀딩 통계 정보 조회",
                    "description": "각 홀드 타입별 건수와 전체 홀딩 건수를 조회합니다.",
                    "operationId": "getHoldStatistics",
                    "tags": ["Statistics"],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "arguments": {
                                            "type": "object",
                                            "properties": {},
                                            "additionalProperties": False
                                        }
                                    },
                                    "required": ["arguments"]
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "홀딩 통계 정보 조회 성공",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "content": {
                                                "$ref": "#/components/schemas/HoldStatistics"
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "500": {
                            "$ref": "#/components/responses/DatabaseError"
                        }
                    }
                }
            },
            "/tools/test_database_connection": {
                "post": {
                    "summary": "데이터베이스 연결 테스트",
                    "description": "Oracle 데이터베이스 연결 상태를 테스트하고 결과를 반환합니다.",
                    "operationId": "testDatabaseConnection",
                    "tags": ["Health Check"],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "arguments": {
                                            "type": "object",
                                            "properties": {},
                                            "additionalProperties": False
                                        }
                                    },
                                    "required": ["arguments"]
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "연결 테스트 결과",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "content": {
                                                "$ref": "#/components/schemas/ConnectionTestResult"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "HoldingInvoice": {
                    "type": "object",
                    "description": "홀딩된 인보이스 정보",
                    "properties": {
                        "invoice_id": {
                            "type": "integer",
                            "nullable": True,
                            "description": "인보이스 ID",
                            "example": 12345
                        },
                        "line_location_id": {
                            "type": "integer",
                            "nullable": True,
                            "description": "라인 위치 ID",
                            "example": 67890
                        },
                        "hold_id": {
                            "type": "integer",
                            "nullable": True,
                            "description": "홀드 ID",
                            "example": 88285
                        },
                        "hold_lookup_code": {
                            "type": "string",
                            "nullable": True,
                            "description": "홀드 룩업 코드",
                            "enum": ["QTY ORD", "QTY REC", "PRICE", "AMT ORG"],
                            "example": "QTY ORD"
                        },
                        "hold_reason": {
                            "type": "string",
                            "nullable": True,
                            "description": "홀드 사유",
                            "example": "Quantity billed exceeds quantity ordered"
                        }
                    },
                    "example": {
                        "invoice_id": 12345,
                        "line_location_id": 67890,
                        "hold_id": 88285,
                        "hold_lookup_code": "QTY ORD",
                        "hold_reason": "Quantity billed exceeds quantity ordered"
                    }
                },
                "HoldStatistics": {
                    "type": "object",
                    "description": "홀딩 통계 정보",
                    "properties": {
                        "total_holds": {
                            "type": "integer",
                            "description": "전체 홀딩 건수",
                            "example": 156
                        },
                        "hold_type_counts": {
                            "type": "object",
                            "description": "홀드 타입별 건수",
                            "additionalProperties": {
                                "type": "integer"
                            },
                            "example": {
                                "PRICE": 45,
                                "QTY ORD": 32,
                                "QTY REC": 28,
                                "AMT ORG": 21
                            }
                        }
                    },
                    "required": ["total_holds", "hold_type_counts"],
                    "example": {
                        "total_holds": 156,
                        "hold_type_counts": {
                            "PRICE": 45,
                            "QTY ORD": 32,
                            "QTY REC": 28,
                            "AMT ORG": 21
                        }
                    }
                },
                "ConnectionTestResult": {
                    "type": "object",
                    "description": "데이터베이스 연결 테스트 결과",
                    "properties": {
                        "status": {
                            "type": "string",
                            "description": "연결 상태",
                            "enum": ["success", "error"],
                            "example": "success"
                        },
                        "message": {
                            "type": "string",
                            "description": "상태 메시지",
                            "example": "데이터베이스 연결 성공"
                        },
                        "timestamp": {
                            "type": "string",
                            "nullable": True,
                            "description": "테스트 실행 시간",
                            "format": "date-time",
                            "example": "2024-01-15 10:30:00"
                        }
                    },
                    "required": ["status", "message"],
                    "example": {
                        "status": "success",
                        "message": "데이터베이스 연결 성공",
                        "timestamp": "2024-01-15 10:30:00"
                    }
                },
                "Error": {
                    "type": "object",
                    "description": "오류 정보",
                    "properties": {
                        "error": {
                            "type": "string",
                            "description": "오류 메시지"
                        },
                        "code": {
                            "type": "string",
                            "description": "오류 코드"
                        }
                    },
                    "required": ["error"],
                    "example": {
                        "error": "데이터베이스 연결 실패",
                        "code": "DB_CONNECTION_ERROR"
                    }
                }
            },
            "responses": {
                "DatabaseError": {
                    "description": "데이터베이스 오류",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/Error"
                            }
                        }
                    }
                }
            },
            "securitySchemes": {
                "ApiKey": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key",
                    "description": "API 키 인증"
                }
            }
        },
        "tags": [
            {
                "name": "Invoice Management",
                "description": "홀딩된 인보이스 관리 관련 API"
            },
            {
                "name": "Statistics",
                "description": "홀딩 통계 관련 API"
            },
            {
                "name": "Health Check",
                "description": "시스템 상태 확인 관련 API"
            }
        ]
    }
    
    # 스키마를 JSON 파일로 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"invoice_holding_management_openapi_{timestamp}.json"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(openapi_schema, f, indent=2, ensure_ascii=False)
        
        print(f"✅ OpenAPI 스키마가 저장되었습니다: {filename}")
        print(f"📄 파일 크기: {os.path.getsize(filename)} bytes")
        
        # 스키마 요약 정보 출력
        print("\n📊 API 요약:")
        print(f"  - API 제목: {openapi_schema['info']['title']}")
        print(f"  - 버전: {openapi_schema['info']['version']}")
        print(f"  - 엔드포인트 수: {len(openapi_schema['paths'])}")
        print(f"  - 스키마 수: {len(openapi_schema['components']['schemas'])}")
        
        return filename
        
    except Exception as e:
        print(f"❌ 파일 저장 중 오류 발생: {str(e)}")
        raise

if __name__ == "__main__":
    # 함수 실행 예제
    print("🚀 OpenAPI 스키마 생성 시작...")
    try:
        saved_file = save_openapi_schema()
        print(f"\n🎉 완료! 생성된 파일: {saved_file}")
    except Exception as e:
        print(f"💥 오류: {str(e)}")