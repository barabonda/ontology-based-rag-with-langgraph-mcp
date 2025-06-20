# Neo4j MCP HTTP Server for LangGraph

이 저장소는 Neo4j 데이터베이스를 LangGraph와 연결하기 위한 HTTP 기반 MCP(Model Context Protocol) 서버를 구현합니다. 
HTTP 서버를 사용하여 Neo4j 세션 관리 문제를 해결하고 리소스 누수 없이 안정적으로 연결할 수 있습니다.

## 문제 배경

LangGraph에서 Neo4j MCP 서버를 subprocess로 실행할 때 발생하는 주요 문제점:

1. **리소스 관리 이슈**: 일반적인 stdin/stdout 기반 MCP 서버는 세션을 공유하고 리소스를 누수시킬 수 있음
2. **ClosedResourceError**: 세션이 이미 닫힌 상태에서 결과를 사용하려고 할 때 발생
3. **결과 소비 불완전**: Neo4j 세션이 적절하게 닫히기 전에 결과가 완전히 소비되지 않는 경우 발생

## 해결 방법

1. **HTTP 기반 MCP 서버**: 각 요청마다 별도의 Neo4j 세션을 생성하고 안전하게 종료
2. **공식 Neo4j MCP 모듈 사용**: 공식 `mcp-neo4j-cypher` 모듈의 소스를 직접 활용
3. **분리된 프로세스**: LangGraph와 Neo4j MCP 서버를 분리된 프로세스로 실행
4. **적응형 구현**: 다양한 FastMCP 버전과 호환되도록 여러 실행 방식 지원

## 시작하기

### 준비 사항

* Python 3.8 이상
* Neo4j 데이터베이스 (로컬 또는 원격)
* 필요한 패키지: `langchain-openai`, `langgraph`, `langgraph-supervisor`, `neo4j`, `fastmcp`, `mcp-core`

### 환경 변수 설정

`.env` 파일을 생성하고 다음 변수를 설정하세요:

```
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
NEO4J_DATABASE=neo4j
OPENAI_API_KEY=your_openai_api_key
MCP_PORT=8765
```

### 설치 및 실행

1. **저장소 클론**

```bash
git clone https://github.com/neo4j-contrib/mcp-neo4j.git
```

2. **Neo4j MCP HTTP 서버 실행**

```bash
python run_neo4j_mcp_server.py
```

서버가 시작되면 `http://localhost:8765/mcp`에서 사용 가능합니다.
스크립트는 자동으로 설치된 FastMCP 버전을 감지하여 적합한 방식으로 실행합니다:
- FastMCP v0.2.0 이상: 직접 HTTP 모드 사용
- 이전 버전 또는 기타 환경: MCP CLI를 통한 HTTP 프록시 사용

3. **테스트 실행**

```bash
python test_neo4j_mcp_http.py
```

4. **LangGraph 예제 실행**

```bash
python neo4j_langgraph_http_example.py
```

## 주요 파일 설명

* `run_neo4j_mcp_server.py`: 공식 Neo4j MCP 서버를 HTTP 모드로 실행하는 스크립트 (여러 모드 지원)
* `neo4j_langgraph_http_example.py`: HTTP MCP 서버를 이용한 LangGraph 예제
* `test_neo4j_mcp_http.py`: HTTP MCP 서버의 기능을 테스트하는 스크립트

## LangGraph와 연동하기

LangGraph에서 HTTP MCP 서버를 사용하는 방법:

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "neo4j": {
        "url": "http://localhost:8765/mcp",
        "transport": "streamable-http",
    }
})
tools = await client.get_tools()
```

## 도구 이름 호환성

서로 다른 MCP 서버 구현에서는 도구 이름이 다를 수 있습니다:

| 기능 | 공식 패키지 도구명 | 커스텀 구현 도구명 |
|------|-------------------|-------------------|
| Cypher 실행 | `read-neo4j-cypher` | `run_cypher` |
| 스키마 조회 | `get-neo4j-schema` | `get_schema` |
| 쓰기 쿼리 | `write-neo4j-cypher` | `run_cypher_with_params` |

예제 코드는 자동으로 사용 가능한 도구 이름을 찾아 사용합니다.

## 주의사항

1. 항상 Neo4j 서버가 실행 중인지 확인하세요.
2. MCP 서버는 LangGraph를 실행하기 전에 시작해야 합니다.
3. 환경 변수가 제대로 설정되었는지 확인하세요.

## 문제 해결

1. **연결 오류**: Neo4j 서버가 실행 중인지, 자격 증명이 올바른지 확인
2. **MCP 서버 오류**: 로그를 확인하고 필요한 패키지가 설치되었는지 확인
3. **HTTP 실행 오류**: `mcp-core` 패키지가 설치되어 있는지 확인하세요 (`pip install mcp-core`)
4. **LangGraph 오류**: MCP 클라이언트 설정과 URL이 올바른지 확인 