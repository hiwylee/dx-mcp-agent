# ---
# title: "Select AI Query Tool (Dynamic Schema v1.2.1)"
# description: "ADW Select AI → Vision SQL Executor (Thick Mode) for Open-WebUI"
# author: "opc"
# version: "1.2.1"
# requirements: ["oracledb", "python-dotenv"]
# ---

import os
import re
import oracledb
from dotenv import load_dotenv
from datetime import datetime


class Pipeline:
    def __init__(self):
        self.name = "Select AI Query Tool (Dynamic Schema v1.2.1)"

        # --- ADW (Select AI) ---
        self.AD_USER = os.getenv("ADW_USER", "HOL_AGENT_05")
        self.AD_PW = os.getenv("ADW_PASSWORD", "Welcome12###")
        self.AD_TNS = os.getenv("ADW_TNS_ALIAS", "adw23ai_medium")
        self.PROFILE = os.getenv("SELECTAI_PROFILE", "AP_HOLDS_PROFILE")

        # --- Vision DB ---
        self.V_USER = os.getenv("VISION_USER", "apps")
        self.V_PW = os.getenv("VISION_PASSWORD", "apps")
        self.V_DSN = os.getenv("VISION_DSN", "161.33.6.86:1521/ebsdb")
        self.V_SCHEMA = None  # Vision DB의 실제 스키마명 (자동 감지)

        # --- Meta ---
        self.META_TBL = "AP_HOLDS_ALL"
        self.REAL_TBL = os.getenv("REAL_TBL", "AP_HOLDS_ALL")
        self.HOLD_CODES = ("QTY ORD", "QTY REC", "PRICE", "AMT ORG")
        self.FORCE_RELEASE_NULL = True

        # --- Prompt ---
        self.PROMPT = (
            f"너는 Vision AP Holds SQL 비서야.\n"
            f"- 반드시 {self.META_TBL} 한 테이블만 사용\n"
            f"- WHERE 포함, 결과는 'FETCH FIRST 100 ROWS ONLY'\n"
            f"스키마: {self.META_TBL}(HOLD_ID,INVOICE_ID,LINE_LOCATION_ID,HOLD_LOOKUP_CODE,"
            f"HOLD_REASON,RELEASE_LOOKUP_CODE,HOLD_DATE,CREATION_DATE,LAST_UPDATE_DATE)\n"
            f"출력: 순수 Oracle SQL 한 문장(코드펜스/세미콜론 금지)\n"
            f"응답은 항상 정중하고 자연스러운 한국어 문장으로 표현\n"
        )

    # ---------------- Lifecycle ----------------
    async def on_startup(self):
        load_dotenv(override=True)

        self.AD_USER = os.getenv("ADW_USER", self.AD_USER)
        self.AD_PW = os.getenv("ADW_PASSWORD", self.AD_PW)
        self.AD_TNS = os.getenv("ADW_TNS_ALIAS", self.AD_TNS)
        self.PROFILE = os.getenv("SELECTAI_PROFILE", self.PROFILE)

        self.V_USER = os.getenv("VISION_USER", self.V_USER)
        self.V_PW = os.getenv("VISION_PASSWORD", self.V_PW)
        self.V_DSN = os.getenv("VISION_DSN", self.V_DSN)
        self.REAL_TBL = os.getenv("REAL_TBL", self.REAL_TBL)

        # Thick Mode Init
        ic_dir = os.getenv("ORACLE_CLIENT_LIB_DIR")
        wallet = os.getenv("ADW_WALLET_DIR")
        if not ic_dir or not os.path.isdir(ic_dir):
            raise RuntimeError(f"ORACLE_CLIENT_LIB_DIR invalid: {ic_dir}")
        if not wallet or not os.path.isdir(wallet):
            raise RuntimeError(f"ADW_WALLET_DIR invalid: {wallet}")

        oracledb.init_oracle_client(lib_dir=ic_dir, config_dir=wallet)
        os.environ.setdefault("TNS_ADMIN", wallet)
        print(f"[SelectAI] Thick mode initialized (lib={ic_dir}, wallet={wallet})")

        # Vision DB Schema 감지
        try:
            with self.conn_vision() as c, c.cursor() as cur:
                cur.execute("SELECT USER FROM DUAL")
                self.V_SCHEMA = (cur.fetchone()[0]).upper()
                print(f"[Vision] Connected schema detected → {self.V_SCHEMA}")
        except Exception as e:
            print(f"[Vision] ⚠️ 스키마 감지 실패 → 기본값 사용 ({self.V_USER}): {e}")
            self.V_SCHEMA = self.V_USER.upper()

    async def on_shutdown(self):
        print("[SelectAI] on_shutdown complete")

    # ---------------- Connections ----------------
    def conn_adw(self):
        return oracledb.connect(user=self.AD_USER, password=self.AD_PW, dsn=self.AD_TNS)

    def conn_vision(self):
        return oracledb.connect(user=self.V_USER, password=self.V_PW, dsn=self.V_DSN)

    # ---------------- Helpers ----------------
    @staticmethod
    def _escape_literal(s: str) -> str:
        return (s or "").replace("'", "''")

    # ---------------- Core Steps ----------------
    def adw_selectai(self, user_msg: str) -> str:
        """ADW에서 Select AI SHOWSQL을 사용하여 SQL 생성"""
        with self.conn_adw() as c, c.cursor() as cur:
            cur.execute("BEGIN DBMS_CLOUD_AI.SET_PROFILE(:1); END;", [self.PROFILE])
            text = self.PROMPT + "\n\n[질문]\n" + (user_msg or "")
            lit = self._escape_literal(text)
            cur.execute(f"SELECT AI SHOWSQL '{lit}' FROM DUAL")
            row = cur.fetchone()
            raw_sql = (row[0] if row else "").strip()
            print("[SelectAI] RAW SQL:", raw_sql)
            return raw_sql

    def clean_sql(self, sql: str) -> str:
        """Select AI가 생성한 SQL을 검증 및 정제"""
        if not sql or not sql.strip():
            raise ValueError("SQL이 비어 있습니다.")
        s = sql.strip()

        # 코드펜스 제거 및 세미콜론 제거
        s = re.sub(r"^```.*?\n|\n```$", "", s, flags=re.DOTALL).rstrip(";")

        # 🔧 스키마 자동 교정 (HOL_AGENT_05 → Vision 스키마)
        if self.V_SCHEMA:
            s = re.sub(r'"?HOL_AGENT_05"?\.', f'{self.V_SCHEMA}.', s, flags=re.IGNORECASE)
            print(f"[SelectAI] Schema auto-adjusted → {self.V_SCHEMA}.")

        # 🚫 DML/DDL 차단
        if re.search(r"\b(insert|update|delete|merge|create|alter|drop|grant|revoke|truncate)\b", s, re.I):
            raise ValueError("DML/DDL 문장은 허용되지 않습니다.")

        # ✅ FROM/JOIN 테이블 검증 (스키마명은 허용, 테이블명만 검사)
        for _, obj in re.findall(r"\b(from|join)\s+([A-Za-z0-9_\"\.]+)", s, re.I):
            parts = [p.strip('"') for p in obj.split(".")]
            table_name = parts[-1].upper()
            if table_name != self.META_TBL.upper():
                raise ValueError(f"허용되지 않은 테이블이 포함되어 있습니다: {obj}")

        # ✅ ORDER/FETCH 구문 분리
        fetch_part, order_part = "", ""
        fetch_match = re.search(r"(?i)\bFETCH\s+FIRST\b.*", s)
        if fetch_match:
            fetch_part = fetch_match.group(0).strip()
            s = s[:fetch_match.start()].strip()
        order_match = re.search(r"(?i)\bORDER\s+BY\b[^\n;]*", s)
        if order_match:
            order_part = order_match.group(0).strip()
            s = s[:order_match.start()].strip()

        # ✅ ORDER 컬럼 보정
        if order_part and not re.search(r"ORDER\s+BY\s+[A-Za-z0-9_\".]", order_part):
            order_part = 'ORDER BY "HOLD_DATE" ASC'

        # ✅ WHERE 조건 주입
        fixed = []
        if self.FORCE_RELEASE_NULL:
            fixed.append(f"RELEASE_LOOKUP_CODE IS NULL")
        if self.HOLD_CODES:
            codes = ", ".join(repr(x) for x in self.HOLD_CODES)
            fixed.append(f"HOLD_LOOKUP_CODE IN ({codes})")
        inject = " AND ".join(fixed)
        if re.search(r"\bwhere\b", s, re.I):
            s = re.sub(r"(?i)\bwhere\b", f"WHERE {inject} AND", s, count=1)
        else:
            s += f" WHERE {inject}"

        # ✅ FETCH 기본값 보정
        if not fetch_part:
            fetch_part = "FETCH FIRST 100 ROWS ONLY"

        final_sql = " ".join(p for p in [s.strip(), order_part, fetch_part] if p).strip()
        print("[SelectAI] CLEANED SQL:", final_sql)
        return final_sql

    def vision_execute(self, sql: str):
        """Vision DB에서 SQL 실행"""
        try:
            q = self.clean_sql(sql)
            print("\n[Vision] 실행 SQL:\n", q)

            with self.conn_vision() as c, c.cursor() as cur:
                cur.execute(q)
                cols = [d[0] for d in cur.description] if cur.description else []
                rows = cur.fetchall() or []
                result = [dict(zip(cols, r)) for r in rows]
                print(f"[Vision] 결과: {len(result)}건 조회됨")

                with open("vision_sql.log", "a") as f:
                    f.write(f"\n[{datetime.now()}] {q}\n결과: {len(result)}건\n")

                return result

        except oracledb.Error as e:
            err_msg = f"Oracle DB 오류 발생: {str(e)}"
            print("[Vision] ❌ Oracle Error:", err_msg)
            return [{"error": err_msg, "sql": sql}]
        except Exception as e:
            err_msg = f"일반 오류 발생: {str(e)}"
            print("[Vision] ❌ General Error:", err_msg)
            return [{"error": err_msg, "sql": sql}]

    # ---------------- Entrypoint ----------------
    async def run(self, user_message: str):
        try:
            sql = self.adw_selectai(user_message)
            data = self.vision_execute(sql)

            if not data:
                message = "조회된 결과가 없습니다."
            elif isinstance(data, list) and "error" in data[0]:
                message = f"쿼리 실행 중 오류가 발생했습니다: {data[0]['error']}"
            elif len(data) == 1 and len(data[0]) == 1:
                key, value = list(data[0].items())[0]
                message = f"{key}는 {value}개입니다."
            else:
                message = f"총 {len(data)}건이 조회되었습니다."

            return {"status": "success", "data": data, "message": message}

        except Exception as e:
            return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    import asyncio
    import sys

    load_dotenv(override=True)
    user_question = "홀딩된 인보이스 목록을 보여줘" if len(sys.argv) == 1 else " ".join(sys.argv[1:])

    try:
        pipeline = Pipeline()
        asyncio.run(pipeline.on_startup())
        result = asyncio.run(pipeline.run(user_question))
        print("\n=== PIPELINE RESULT ===")
        print(result)
    except Exception as e:
        print("\n!!! 실행 중 오류 발생:", e)
