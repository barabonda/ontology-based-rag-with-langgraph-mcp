# 🧠 Ontology-based RAG with LangGraph and MCP

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-green.svg)](https://github.com/langchain-ai/langgraph)
[![MCP](https://img.shields.io/badge/MCP-Protocol-orange.svg)](https://modelcontextprotocol.io/)

이 프로젝트는 **Ontology-based RAG (Retrieval-Augmented Generation)** 시스템을 **LangGraph**와 **MCP (Model Context Protocol)**를 사용하여 구현한 예제입니다. 다중 에이전트 시스템을 통해 지식 그래프 기반의 지능형 질의응답 시스템을 구축할 수 있습니다.

## 🌟 주요 특징

- **🤖 다중 에이전트 시스템**: LangGraph Supervisor를 사용한 계층적 에이전트 관리
- **🔗 MCP 통합**: 다양한 외부 서비스와의 표준화된 통신
- **🗄️ Neo4j 지식 그래프**: 온톨로지 기반 지식 저장 및 쿼리
- **🧮 도구 통합**: 수학 계산, 날씨 정보, 데이터베이스 쿼리 등
- **🔄 실시간 스트리밍**: LangGraph의 스트리밍 기능 지원
- **💾 메모리 관리**: 단기/장기 메모리 시스템

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 저장소 클론
git clone https://github.com/barabonda/ontology-based-rag-with-langgraph-mcp.git
cd ontology-based-rag-with-langgraph-mcp

# 가상환경 생성 및 활성화
python -m venv .venv-new
source .venv-new/bin/activate  # Windows: .venv-new\Scripts\activate

# 의존성 설치
pip install --upgrade pip
pip install -e .
pip install "langgraph-cli[inmem]" langchain-openai python-dotenv
pip install mcp langchain-mcp-adapters
```

### 2. 환경 변수 설정

```bash
# OpenAI API 키 설정
export OPENAI_API_KEY="your_openai_api_key_here"

# Neo4j 연결 정보 (선택사항)
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USERNAME="neo4j"
export NEO4J_PASSWORD="your_password"
```

### 3. 기본 예제 실행

```bash
# LangGraph 개발 서버 시작
langgraph dev
```

브라우저에서 [LangGraph Studio](https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2025)를 열어 에이전트와 상호작용하세요!

## 📚 사용 예제

### 기본 다중 에이전트 시스템

```python
from langchain_openai import ChatOpenAI
from langgraph_supervisor import create_supervisor
from langgraph.prebuilt import create_react_agent

# 모델 초기화
model = ChatOpenAI(model="gpt-4o-mini")

# 수학 전문 에이전트
def add(a: float, b: float) -> float:
    """두 숫자를 더합니다."""
    return a + b

def multiply(a: float, b: float) -> float:
    """두 숫자를 곱합니다."""
    return a * b

math_agent = create_react_agent(
    model=model,
    tools=[add, multiply],
    name="math_expert",
    prompt="당신은 수학 전문가입니다. 항상 한 번에 하나의 도구만 사용하세요."
)

# 연구 전문 에이전트
def web_search(query: str) -> str:
    """웹에서 정보를 검색합니다."""
    return "FAANG 회사들의 2024년 직원 수:\n1. Meta: 67,317명\n2. Apple: 164,000명\n3. Amazon: 1,551,000명\n4. Netflix: 14,000명\n5. Google: 181,269명"

research_agent = create_react_agent(
    model=model,
    tools=[web_search],
    name="research_expert",
    prompt="당신은 웹 검색에 접근할 수 있는 세계적인 연구 전문가입니다. 수학은 하지 마세요."
)

# 슈퍼바이저 워크플로우 생성
workflow = create_supervisor(
    [research_agent, math_agent],
    model=model,
    prompt=(
        "당신은 연구 전문가와 수학 전문가를 관리하는 팀 슈퍼바이저입니다. "
        "현재 이벤트에 대해서는 research_agent를 사용하세요. "
        "수학 문제에 대해서는 math_agent를 사용하세요."
    )
)

# 컴파일 및 실행
app = workflow.compile()
result = app.invoke({
    "messages": [
        {
            "role": "user",
            "content": "FAANG 회사들의 2024년 총 직원 수는 얼마인가요?"
        }
    ]
})
```

### MCP 서버와 통합

#### 수학 MCP 서버 실행

```bash
python math_server.py
```

#### 날씨 MCP 서버 실행 (포트 8000)

```bash
python weather_server.py
```

#### Neo4j MCP 서버 실행

```bash
python neo4j_mcp_server.py
```

### 다중 MCP 서버 연결

```python
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_openai import ChatOpenAI

async def main():
    model = ChatOpenAI(model="gpt-4o-mini")
    
    # 다중 MCP 서버 클라이언트 설정
    client = MultiServerMCPClient({
        "math": {
            "command": "python",
            "args": ["./math_server.py"],
            "transport": "stdio",
        },
        "weather": {
            "url": "http://localhost:8000/mcp/",
            "transport": "streamable_http",
        }
    })
    
    tools = await client.get_tools()
    
    # 모델 호출 함수
    def call_model(state: MessagesState):
        response = model.bind_tools(tools).invoke(state["messages"])
        return {"messages": response}
    
    # 그래프 구성
    builder = StateGraph(MessagesState)
    builder.add_node("call_model", call_model)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "call_model")
    builder.add_conditional_edges("call_model", tools_condition)
    builder.add_edge("tools", "call_model")
    graph = builder.compile()
    
    # 실행
    math_response = await graph.ainvoke({"messages": "what's (3 + 5) x 12?"})
    weather_response = await graph.ainvoke({"messages": "what is the weather in nyc?"})
    
    print("Math response:", math_response)
    print("Weather response:", weather_response)

if __name__ == "__main__":
    asyncio.run(main())
```

## 🗂️ 프로젝트 구조

```
ontology-based-rag-with-langgraph-mcp/
├── 📁 langgraph_supervisor/          # 핵심 라이브러리
│   ├── __init__.py
│   ├── supervisor.py                 # 슈퍼바이저 구현
│   ├── handoff.py                    # 에이전트 간 전환
│   ├── agent_name.py                 # 에이전트 이름 관리
│   ├── neo4j_manager.py              # Neo4j 관리자
│   └── neo4j_http_tools.py           # Neo4j HTTP 도구
├── 📁 mcp-neo4j/                     # MCP Neo4j 서버들
│   ├── servers/mcp-neo4j-cypher/     # Cypher 쿼리 서버
│   ├── servers/mcp-neo4j-memory/     # 메모리 서버
│   └── servers/mcp-neo4j-cloud-aura-api/  # Aura 클라우드 API
├── 📁 examples/                      # 예제 파일들
├── 📁 tests/                         # 테스트 파일들
├── 📁 static/                        # 정적 파일들 (이미지 등)
├── 📁 templates/                     # HTML 템플릿
├── example.py                        # 기본 예제
├── neo4j_mcp_server.py              # Neo4j MCP 서버
├── mcp_langgraph_test.py            # MCP LangGraph 테스트
├── math_server.py                    # 수학 MCP 서버
├── weather_server.py                 # 날씨 MCP 서버
├── mcp_server.py                     # 기본 MCP 서버
├── langgraph.json                    # LangGraph 설정
├── pyproject.toml                    # 프로젝트 설정
└── requirements.txt                  # 의존성 목록
```

## 🔧 주요 컴포넌트

### 1. LangGraph Supervisor
- **계층적 에이전트 관리**: 슈퍼바이저가 여러 전문 에이전트를 조율
- **도구 기반 전환**: 에이전트 간 안전한 작업 전환
- **메시지 히스토리 관리**: 대화 흐름 제어

### 2. MCP (Model Context Protocol)
- **표준화된 통신**: 다양한 외부 서비스와의 일관된 인터페이스
- **다중 서버 지원**: 수학, 날씨, 데이터베이스 등 다양한 서비스
- **실시간 스트리밍**: 효율적인 데이터 전송

### 3. Neo4j 통합
- **지식 그래프**: 온톨로지 기반 지식 저장
- **Cypher 쿼리**: 복잡한 그래프 쿼리 지원
- **실시간 업데이트**: 동적 지식 베이스

## 🎯 사용 사례

### 1. 지식 베이스 질의응답
```python
# Neo4j에서 Plant 1918의 Factory Issue 데이터 조회
query = """
MATCH (p:Plant {plant:1918})-[r:FACTORYISSUE]->(e:Event)
WHERE date(e.date) >= date('2023-01-01')
  AND date(e.date) <= date('2023-04-30')
RETURN date(e.date) AS date, sum(r.value) AS totalValue
ORDER BY date;
"""
```

### 2. 다단계 문제 해결
```python
# 1단계: 데이터 수집 (연구 에이전트)
# 2단계: 계산 수행 (수학 에이전트)
# 3단계: 결과 분석 (분석 에이전트)
```

### 3. 실시간 데이터 처리
```python
# 날씨 데이터 + 수학 계산 + 데이터베이스 저장
# 스트리밍 방식으로 실시간 처리
```

## 🛠️ 고급 기능

### 메모리 관리
```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

checkpointer = InMemorySaver()
store = InMemoryStore()

app = workflow.compile(
    checkpointer=checkpointer,
    store=store
)
```

### 커스텀 핸드오프 도구
```python
from langgraph_supervisor import create_handoff_tool

workflow = create_supervisor(
    [research_agent, math_agent],
    tools=[
        create_handoff_tool(
            agent_name="math_expert", 
            name="assign_to_math_expert", 
            description="수학 전문가에게 작업 할당"
        )
    ],
    model=model,
)
```

### 메시지 전달 도구
```python
from langgraph_supervisor.handoff import create_forward_message_tool

forwarding_tool = create_forward_message_tool("supervisor")
workflow = create_supervisor(
    [research_agent, math_agent],
    model=model,
    tools=[forwarding_tool]
)
```

## 🔍 문제 해결

### 일반적인 문제들

1. **MCP 서버 연결 실패**
   ```bash
   # 서버가 실행 중인지 확인
   python math_server.py
   python weather_server.py
   ```

2. **Neo4j 연결 오류**
   ```bash
   # 환경 변수 확인
   echo $NEO4J_URI
   echo $NEO4J_USERNAME
   echo $NEO4J_PASSWORD
   ```

3. **LangGraph Studio 접속 불가**
   ```bash
   # 개발 서버 재시작
   langgraph dev
   ```

## 🤝 기여하기

1. 이 저장소를 포크하세요
2. 기능 브랜치를 생성하세요 (`git checkout -b feature/amazing-feature`)
3. 변경사항을 커밋하세요 (`git commit -m 'Add amazing feature'`)
4. 브랜치에 푸시하세요 (`git push origin feature/amazing-feature`)
5. Pull Request를 생성하세요

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 🙏 감사의 말

- [LangGraph](https://github.com/langchain-ai/langgraph) - 강력한 에이전트 프레임워크
- [MCP](https://modelcontextprotocol.io/) - 모델 컨텍스트 프로토콜
- [Neo4j](https://neo4j.com/) - 그래프 데이터베이스
- [LangChain](https://langchain.com/) - LLM 애플리케이션 프레임워크

## 📞 문의

프로젝트에 대한 질문이나 제안사항이 있으시면 [Issues](https://github.com/barabonda/ontology-based-rag-with-langgraph-mcp/issues)를 통해 문의해 주세요.

---

**🚀 지금 바로 시작해보세요!** Ontology-based RAG 시스템으로 지능형 질의응답을 구현해보세요.