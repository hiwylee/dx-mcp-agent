# CHAT UI / ADW Vector Search 접속 정보 및 운영 가이드

## Chat UI (OPEN-WEBUI)

### 관련 프로세스
- **open-webui** (포트: 8080) - LLM Chat UI
- **gateway #1** (포트: 8088) - OCI Generative AI G/W
- **gateway #2** (포트: 9000) - OCI Generative Agent G/W
- **mcpo &  mcp** (포트: 9999) - MCP G/W and (9999) mcp server(8000)

## 프로세스 기동 방법

### 기동 순서
**ADW → OPEN-WEBUI**

OPEN-WEBUI 기동 순서: `[gateway #1, #2]` → `[mcpo & sqlcl mcp]` → `[open-webui]`

### 1. Gateway #1 기동
```bash
cd ~/OCI_GenAI_access_gateway
source .venv/bin/activate  # python env setup
cd app
nohup ./run.sh &
deactivate
```

### 2. Gateway #2 기동
```bash
cd ~/agentsOCI-OpenAI-gateway
source .venv/bin/activate  # python env setup
nohup ./run.sh &
deactivate
```

### 3. MCPO & SQLCL MCP 기동
```bash
cd ~/mcpo
source .venv/bin/activate  # python env setup
nohup mcpo --port 7000 --api-key "top-secret" -- sql -mcp &
deactivate
```

### 4. Open-WebUI 기동
```bash
cd ~/open-webui/
source .venv/bin/activate  # python env setup
cd backend/
nohup ./start.sh &
deactivate
```

## MCP Server
```
cd ~/dx-mcp-agent
nohup  uv run mcp_invoice_holds.py  > mcp_invoice_hold.log 2>&1 &

nohup mcpo --port 9999 --api-key "top-secret" --server-type streamable-http -- http://127.0.0.1:8000/mcp   > mcpo_mcp_invoice_hold.log 2>&1 &

kill -9 $(lsof -i :9999 | awk 'NR>1 {print $2}')
kill -9 $(lsof -i :8000 | awk 'NR>1 {print $2}')
```

```
hot-reload enabled:

```bash
mcpo --port 9999 --api-key "top-secret" --config /home/opc/dx-mcp-agent/mcpo_config.json --hot-reload
```

## TO-DO

### Free DNS 설정
- [ ] VIS
- [ ] open-webui

### SSL 설정 (필요시)
- [ ] open-webui
