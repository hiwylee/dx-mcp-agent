#!/usr/bin/env python3
"""
Oracle Invoice Holdings OCI Agent Client

OCI 설정 필요:
export OCI_CONFIG_FILE=~/.oci/config
export OCI_CONFIG_PROFILE=DEFAULT

필요한 패키지 설치:
pip install oci-addons-adk mcp python-dotenv
"""

import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv
from mcp.client.session_group import StreamableHttpParameters
from oci.addons.adk import Agent, AgentClient, tool
from oci.addons.adk.mcp import MCPClientStreamableHttp

# .env 파일 로드
load_dotenv()

# 환경 설정 (.env 파일에서 로드)
MCP_SERVER_PORT = os.getenv("MCP_SERVER_PORT", "3000")  # .env에서 포트 읽기
MCP_SERVER_URL = f"http://localhost:{MCP_SERVER_PORT}"  # FastMCP 서버 주소
OCI_REGION = os.getenv("REGION", "ap-osaka-1")  # .env에서 리전 읽기
OCI_PROFILE = os.getenv("PROFILE", "DEFAULT")  # .env에서 프로필 읽기
IS_AGENT_SETUP = os.getenv("IS_AGENT_SETUP", "False")  # .env에서 프로필 읽기

# Agent Endpoint ID (.env 파일에서 읽기)
AGENT_ENDPOINT_ID = os.getenv("AGENT_ENDPOINT_ID")

def print_header(title: str):
    """섹션 헤더를 출력합니다."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_test_case(case_num: int, description: str, query: str):
    """테스트 케이스 헤더를 출력합니다."""
    print(f"\n📋 테스트 케이스 {case_num}: {description}")
    print(f"🔍 실행: {query}")
    print("-" * 50)

async def main():
    """메인 함수"""
    print_header("Oracle Invoice Holdings OCI Agent Client 시작")
    print(f"📅 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🌐 MCP 서버: {MCP_SERVER_URL}")
    print(f"🔌 MCP 포트: {MCP_SERVER_PORT}")
    print(f"🏢 OCI 리전: {OCI_REGION}")
    print(f"👤 OCI 프로필: {OCI_PROFILE}")
    print(f"👤 IS_AGENT_SETUP: {IS_AGENT_SETUP}")
    print(f"🤖 Agent Endpoint: {AGENT_ENDPOINT_ID[:50]}...")

    # 필수 환경 변수 확인
    if not AGENT_ENDPOINT_ID:
        print("❌ AGENT_ENDPOINT_ID가 .env 파일에 설정되지 않았습니다.")
        print("💡 .env 파일에 다음 설정을 추가해주세요:")
        print(f"   AGENT_ENDPOINT_ID=ocid1.genaiagentendpoint.oc1.ap-osaka-1.amaaaaaary...")
        return

    try:
        # MCP 서버 연결 설정
        params = StreamableHttpParameters(
            url=f"{MCP_SERVER_URL}/mcp",  # FastMCP 서버 주소
        )

        async with MCPClientStreamableHttp(
            params=params,
            name="Oracle Invoice Holding MCP Server",
        ) as mcp_client:

            print("✅ MCP 서버에 연결되었습니다.")

            # OCI Agent Client 설정
            client = AgentClient(
                auth_type="api_key",  # 또는 auth_type="security_token"
                profile=OCI_PROFILE,  # OCI config profile 이름
                region=OCI_REGION     # 사용할 OCI 리전
            )


            # Agent 설정 - Oracle 인보이스 홀딩 관리를 위한 지시사항
            agent = Agent(
                client=client,
                agent_endpoint_id=AGENT_ENDPOINT_ID,
                instructions="""
                당신은 Oracle ERP 시스템의 인보이스 홀딩 관리 전문가입니다. 
                사용자의 질문에 따라 적절한 도구를 사용하여 다음과 같은 작업을 수행하세요:
                
                1. 홀딩된 인보이스 목록 조회 (최대 20개)
                2. 홀딩 통계 정보 제공 (홀드 타입별 건수)
                3. 데이터베이스 연결 상태 확인
                4. 특정 홀드 타입에 대한 설명 제공
                
                홀드 타입 설명:
                - QTY ORD: 발주 수량 불일치
                - QTY REC: 수령 수량 불일치  
                - PRICE: 가격 불일치
                - AMT ORG: 조직별 금액 불일치
                
                한국어로 친절하고 상세하게 답변해주세요.
                데이터를 조회할 때는 먼저 데이터베이스 연결 상태를 확인하고,
                조회 결과를 표 형태로 정리하여 보기 좋게 제공해주세요.
                """,
                tools=[await mcp_client.as_toolkit()],
            )


            if IS_AGENT_SETUP.lower() == "false":
                agent.setup()
                print("✅ OCI Agent가 설정되었습니다.")
            else:
                print("OCI Agent가 이미 설정되었습니다.")
            # 자동 테스트 케이스 실행
            await run_automated_tests(agent)
            
            # 대화형 모드 시작
            await run_interactive_mode(agent)

    except Exception as e:
        print(f"❌ 클라이언트 초기화 중 오류 발생: {str(e)}")
        print("다음 사항을 확인해주세요:")
        print("1. MCP 서버가 실행 중인지 확인 (python mcp_server.py)")
        print("2. OCI 설정이 올바른지 확인 (~/.oci/config)")
        print("3. Agent Endpoint ID가 올바른지 확인")
        return

async def run_automated_tests(agent):
    """자동화된 테스트 케이스들을 실행합니다."""
    print_header("자동화된 테스트 케이스 실행")

    test_cases = [
        # {
        #     "num": 1,
        #     "description": "데이터베이스 연결 상태 확인",
        #     "query": "데이터베이스 연결 상태를 확인해주세요."
        # },
        {
            "num": 2, 
            "description": "홀딩된 인보이스 목록 조회",
            "query": "현재 홀딩된 인보이스 목록을 보여주세요."
        },
        {
            "num": 3,
            "description": "홀딩 통계 정보 조회", 
            "query": "홀드 타입별 통계 정보를 알려주세요."
        },
        {
            "num": 4,
            "description": "특정 홀드 타입 설명",
            "query": "PRICE 홀드 타입에 대해 자세히 설명해주세요."
        },
        {
            "num": 5,
            "description": "종합 분석 요청",
            "query": "전체 홀딩 현황을 분석하고 주요 이슈를 알려주세요."
        }
    ]

    for test_case in test_cases:
        try:
            print_test_case(
                test_case["num"], 
                test_case["description"], 
                test_case["query"]
            )
            
            response = await agent.run_async(test_case["query"])
            response.pretty_print()
            
            print("\n" + "="*60 + "\n")
            
            # 테스트 간 잠시 대기
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"❌ 테스트 케이스 {test_case['num']} 실행 중 오류: {str(e)}")
            continue

async def run_interactive_mode(agent):
    """대화형 모드를 실행합니다."""
    print_header("대화형 모드")
    print("💬 대화형 모드를 시작합니다.")
    print("📝 다음과 같은 질문을 해보세요:")
    print("   • '홀딩된 인보이스 목록을 보여주세요'")
    #print("   • 'QTY REC 홀드가 무엇인가요?'")
    print("   • '가장 많이 발생하는 홀드 타입은 무엇인가요?'")
    print("   • '데이터베이스 연결 상태를 확인해주세요'")
    print("🚪 종료하려면 'quit', 'exit', '종료', '나가기'를 입력하세요.\n")
    
    while True:
        try:
            user_input = input("❓ 질문: ").strip()
            
            if user_input.lower() in ['quit', 'exit', '종료', '나가기', 'q']:
                print("👋 클라이언트를 종료합니다.")
                break
            
            if not user_input:
                print("💡 질문을 입력해주세요.")
                continue
            
            print(f"\n🔍 처리 중: {user_input}")
            print("-" * 50)
            
            response = await agent.run_async(user_input)
            response.pretty_print()
            
            print("\n" + "-"*50 + "\n")
            
        except KeyboardInterrupt:
            print("\n\n👋 클라이언트를 종료합니다.")
            break
        except Exception as e:
            print(f"❌ 오류 발생: {str(e)}")
            print("💡 다시 시도해주세요.\n")
            continue

def check_environment():
    """환경 설정을 확인합니다."""
    print("🔍 환경 설정 확인 중...")
    
    # .env 파일 확인
    env_file = ".env"
    if not os.path.exists(env_file):
        print(f"⚠️ .env 파일을 찾을 수 없습니다: {env_file}")
        print("   .env 파일을 생성하고 필요한 설정값들을 추가해주세요.")
        return False
    
    print(f"✅ .env 파일 확인: {env_file}")
    
    # 필수 환경 변수 확인
    required_vars = {
        "AGENT_ENDPOINT_ID": AGENT_ENDPOINT_ID,
        "MCP_SERVER_PORT": MCP_SERVER_PORT,
        "REGION": OCI_REGION,
        "PROFILE": OCI_PROFILE
    }
    
    missing_vars = []
    for var_name, var_value in required_vars.items():
        if var_value:
            if var_name == "AGENT_ENDPOINT_ID":
                print(f"✅ {var_name}: {var_value[:50]}...")
            else:
                print(f"✅ {var_name}: {var_value}")
        else:
            print(f"❌ {var_name}: 설정되지 않음")
            missing_vars.append(var_name)
    
    if missing_vars:
        print(f"\n⚠️ 다음 환경 변수들이 .env 파일에 설정되지 않았습니다:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n💡 .env 파일 예시:")
        print("   AGENT_ENDPOINT_ID=ocid1.genaiagentendpoint.oc1...")
        print("   MCP_SERVER_PORT=8000")
        print("   REGION=ap-osaka-1")
        print("   PROFILE=osaka")
        return False
    
    # OCI 설정 파일 확인
    oci_config_file = os.path.expanduser("~/.oci/config")
    if not os.path.exists(oci_config_file):
        print(f"⚠️ OCI 설정 파일을 찾을 수 없습니다: {oci_config_file}")
        print("   OCI CLI를 설정하거나 설정 파일을 생성해주세요.")
        return False
    
    print(f"✅ OCI 설정 파일 확인: {oci_config_file}")
    
    return True

def print_usage():
    """사용법을 출력합니다."""
    print("""
📖 Oracle Invoice Holdings OCI Agent Client 사용법

📁 .env 파일 설정:
   AGENT_ENDPOINT_ID=ocid1.genaiagentendpoint.oc1.ap-osaka-1.amaaaaaar...
   MCP_SERVER_PORT=8000
   REGION=ap-osaka-1
   PROFILE=osaka

🔧 OCI 설정:
   ~/.oci/config 파일이 존재해야 합니다.

📦 필요한 패키지:
   pip install oci-addons-adk mcp python-dotenv

🚀 실행:
   python oci_agent_client.py

📋 사용 가능한 질문:
   • 홀딩된 인보이스 목록 조회
   • 홀딩 통계 정보 조회
   • 데이터베이스 연결 상태 확인
   • 특정 홀드 타입에 대한 설명
    """)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help", "help"]:
        print_usage()
        sys.exit(0)
    
    # 환경 설정 확인
    if not check_environment():
        print("\n❌ 환경 설정을 확인하고 다시 실행해주세요.")
        sys.exit(1)
    
    print("🚀 Oracle Invoice Holdings OCI Agent Client 시작...")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️ 클라이언트가 중단되었습니다.")
    except Exception as e:
        print(f"\n💥 예상치 못한 오류: {str(e)}")
        print("\n🔍 문제 해결 방법:")
        print("1. MCP 서버가 실행 중인지 확인: python mcp_server.py")
        print("2. OCI 설정이 올바른지 확인: ~/.oci/config")
        print("3. Agent Endpoint ID가 올바른지 확인")
        print("4. 네트워크 연결 상태 확인")
        sys.exit(1)