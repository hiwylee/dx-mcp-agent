import asyncio
import os
from dotenv import load_dotenv
from oci.addons.adk import Agent, AgentClient,tool

from oci.addons.adk.run.types import InlineInputLocation, ObjectStorageInputLocation
from oci.addons.adk.tool.prebuilt.agentic_sql_tool import AgenticSqlTool, SqlDialect, ModelSize

# Load environment variables from .env file
load_dotenv()


INLINE_TABLE_DESC = """
TABLE MCP_AP_HOLDS_ALL Column Description
--
"MCP_AP_HOLDS_ALL"."RNO"  Sequence no mapped to  INVOICE_ID, 일련번호 ';
"MCP_AP_HOLDS_ALL"."INVOICE_ID"  'Invoice identifier, 송장 ';
"MCP_AP_HOLDS_ALL"."LINE_LOCATION_ID"  'Purchase order line location identifier ';
"MCP_AP_HOLDS_ALL"."HOLD_LOOKUP_CODE"  'Name of hold code, 보류코드 ';
"MCP_AP_HOLDS_ALL"."HOLD_REASON"  'Reason for hold being placed on invoice, 보류이유 ';
"""

INLINE_ICL_EXAMPLES = """
Question: get invoice holding list
Oracle SQL: 
SELECT * FROM MCP_AP_HOLDS_ALL WHERE RNO <= 10;
"""

INLINE_DATABASE_SCHEMA = """
 CREATE TABLE APPS.MCP_AP_HOLDS_ALL
   (	
       "ROWNUM" RNO,
       "INVOICE_ID" NUMBER(15,0), 
	"LINE_LOCATION_ID" NUMBER(15,0), 
        "HOLD_ID" NUMBER(15,0), 
	"HOLD_LOOKUP_CODE" VARCHAR2(25 BYTE), 
	"HOLD_REASON" VARCHAR2(240 BYTE)
   )  ;
"""

INLINE_DATABASE_SCHEMA = """
 CREATE TABLE APPS.MCP_AP_HOLDS_ALL
   (	
       "ROWNUM" RNO,
       "INVOICE_ID" NUMBER(15,0), 
	"LINE_LOCATION_ID" NUMBER(15,0), 
        "HOLD_ID" NUMBER(15,0), 
	"HOLD_LOOKUP_CODE" VARCHAR2(25 BYTE), 
	"HOLD_REASON" VARCHAR2(240 BYTE)
   )  ;
"""

# AGENT_ENDPOINT_ID=ocid1.genaiagentendpoint.oc1.ap-osaka-1.amaaaaaarykjadqah2zw7mxczrxoa6o3ebdneenum4s5g5mqfk2urommiytq
# MCP_SERVER_PORT=8000
# REGION=ap-osaka-1
# PROFILE=osaka

async def main():
    agent_endpoint_id=os.getenv("AGENT_ENDPOINT_ID")
    region=os.getenv("REGION")
    profile=os.getenv("PROFILE")
    
    client = AgentClient(auth_type="api_key", profile=profile, region=region)

    sql_tool_with_inline_schema = AgenticSqlTool(
        name="get_invoice_holdings",
        description="Use this tool-InvoiceStatusChecker to answer questions about invoice holds.",
        database_schema=InlineInputLocation(content=INLINE_DATABASE_SCHEMA),
        model_size=ModelSize.LARGE,
        dialect=SqlDialect.ORACLE_SQL,
        db_tool_connection_id="ocid1.databasetoolsconnection.oc1.ap-osaka-1.amaaaaaarykjadqa7ni7qmam45tfm55omynvz5sxrakmy25w37nf7mdajfxq",
        enable_sql_execution=True,
        enable_self_correction=True,
        #icl_examples=ObjectStorageInputLocation(namespace_name="namespace", bucket_name="bucket", prefix="_sql.icl_examples.txt"),
        custom_instructions="Use this tool-InvoiceStatusChecker to answer questions about invoice holds. 건수가 명시 되지 않으면 10건만 보여준다."
    )

    agent = Agent(
        client=client,
        agent_endpoint_id=agent_endpoint_id,
        instructions="Use the tools : InvoiceStatusChecker to answer the questions.",

        tools=[sql_tool_with_inline_schema]
    )

    # 2개의 질문을 차례로 질의하고 답변받음
    # input_msg ="홀딩된 인보이스 목록을 보여줘, hold 이유도 포함하여  20건 만 보여주고 hold_date으로 descending 해줘" 
    input_msg ="list first 10 records in ap_holds_all where release_reason is null " 
    input_msg ="list first 10 records in ap_holds_all where release_reason is null and hold_loook_code in ('QTY ORD', 'QTY  REC', 'PRICE', 'AMT ORG');"
    input_msg =" 인보이스 보류 현황을 조회"
    print(f"Running: {input_msg}")
    response = await agent.run_async(input_msg)
    
    response.pretty_print()


if __name__ == "__main__":
    asyncio.run(main())