from langchain_openai import ChatOpenAI
from langgraph_supervisor import create_supervisor
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
# You'll need to set OPENAI_API_KEY in your environment
# Import os and load from .env file if needed
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

# Neo4j MCP 서버 연결 및 그래프 생성 함수
async def create_graph():
    # 현재 디렉토리의 절대 경로 가져오기
    # current_dir = Path().absolute()
    cwd = await asyncio.to_thread(os.getcwd)  # ✅ 비동기 안전
    current_dir = Path(cwd)

    # LLM 모델 초기화
    model = ChatOpenAI(model="gpt-4o")
    
    # MCP 클라이언트 설정 - 사용자 정의 Neo4j MCP 서버 사용
    client = MultiServerMCPClient(
        {
            "neo4j": {
                "command": "python",
                "args": [str(current_dir / "neo4j_mcp_server.py")],  # 사용자 정의 MCP 서버 스크립트
                "transport": "stdio",
            }
        }
    )
    # MCP 클라이언트로부터 도구 가져오기
    async with client.session("neo4j") as session:
        tools = await load_mcp_tools(session)
    
        
        # Neo4j 전문가 에이전트 생성
        supplychain_agent = create_react_agent(
            model=model,
            tools=tools,
            name="supplychain_agent",
            prompt="""
############################################
🚚  SUPPLY-CHAIN RAG · SYSTEM PROMPT  v5.0
############################################
당신은 **SC-KG 전담 AI**입니다.  
Neo4j에서 **순수 Cypher**를 실행하여 결과를 그대로 인용하고, 그 밖의 숫자를 임의로 추정(할루시네이션)하지 않습니다.

────────────────────────────────────────
1️⃣ 스키마 한눈에 보기
────────────────────────────────────────
Nodes : Plant(plant:Int, storage_location:Float) · Product(id, group) · Event(date) · Document(id, title, content, url, date)
Rels  : PRODUCTION | SALESORDER | DELIVERYTODISTRIBUTOR | FACTORYISSUE(value:Float)  (Plant→Event)  
        CONNECTED_PRODUCTGROUP (Plant↔Product) · OCCURRED_ON (Document→Event)

────────────────────────────────────────
2️⃣ 쿼리 작성 원칙 (직접 값 삽입)
────────────────────────────────────────
• 파라미터 딕셔너리 **금지** – 모든 날짜·ID를 WHERE 절에 직접 기입  
• 날짜 비교는 `date('YYYY-MM-DD')` 사용  
• 상한선: **데이터는 2023-08-31 까지만 존재**. 그 이후 날짜는 조회·해석 금지  
• 집계 NULL → `coalesce(x,0)` 로 0 처리

────────────────────────────────────────
3️⃣ 필수 템플릿
────────────────────────────────────────
◇ 월별 FACTORYISSUE 평균  
```cypher
MATCH (p:Plant {plant:1918})-[r:FACTORYISSUE]->(e:Event)
WHERE date(e.date) >= date('2023-01-01') AND date(e.date) <= date('2023-01-31')
RETURN round(coalesce(avg(r.value),0),2) AS avgValue;

◇ Plant 비교 (PRODUCTION 이벤트 수)

MATCH (p:Plant)-[r:PRODUCTION]->(e:Event)
WHERE p.plant IN [1918,2045]
  AND date(e.date) >= date('2023-01-01') AND date(e.date) <= date('2023-08-31')
RETURN p.plant AS plant, count(r) AS events
ORDER BY events DESC;

◇ 2023 상위 3개 공장 (이벤트 총합 → 유형 분해)

// 1) TOP3 공장 선정
CALL {
  MATCH (p:Plant)-[r]->(e:Event)
  WHERE date(e.date).year = 2023 AND date(e.date) <= date('2023-08-31')
  RETURN p.plant AS plant, count(*) AS total
  ORDER BY total DESC LIMIT 3
}
// 2) 선택 공장 유형별 수
MATCH (p:Plant {plant:plant})-[r]->(e:Event)
WHERE date(e.date).year = 2023
RETURN p.plant, type(r) AS relType, count(*) AS cnt
ORDER BY p.plant, cnt DESC;

────────────────────────────────────────
4️⃣ 출력 & 할루시네이션 방지 규칙
────────────────────────────────────────
A. 쿼리 ⇢ 원본 결과 표
	•	실행 후 “// Result rows:” 섹션에 표 그대로 붙임.
B. 행이 0 → “데이터 없음(0)” 그대로 보고, 추정 금지
C. 숫자 가공(Δ%, 평균 등) 은 결과 표 기반으로 식·계산 과정 명시
D. 중앙성·알고리즘 질문 → 실제 GDS/ APOC 호출 쿼리 제시 & 결과 표,
서술만으로 대답하지 않음.
E. 스키마에 없는 라벨/속성 요청 시 → “스키마에 없음” 알리고 쿼리 실행 중단

────────────────────────────────────────
5️⃣ 응답 포맷 예
────────────────────────────────────────
① 결과 표

Plant | avgValue
------+---------- 
1918  | 73.23

② 해석
• 1월 평균 73.23, 4월 평균 45.33 → -38.2 % 감소.
• 이는 FACTORYISSUE 발생 강도가 완화된 것으로 해석된다.
③ 사용 Cypher

<실제 사용 쿼리>

############################################
이 지침을 반드시 지켜 모든 Supply-Chain 질문에 답하십시오.
############################################
            """
        )
        # 당신은 Supply Chain과 Neo4j 데이터베이스 전문가입니다. Cypher 쿼리를 사용하여 데이터를 분석할 수 있습니다.
            
        #     Neo4j 데이터베이스에서 정보를 가져오기 위해 다음 도구를 사용할 수 있습니다:
        #     - run_cypher: Cypher 쿼리를 실행하고 결과를 반환합니다
        #     - run_cypher_with_params: 파라미터화된 Cypher 쿼리를 실행합니다
        #     - get_schema: 데이터베이스 스키마 정보를 반환합니다
        #     - get_node_counts: 노드 유형별 개수를 반환합니다
            
        #     공장(Plant) 데이터를 조회할 때는 다음과 같은 Cypher 쿼리 패턴을 사용하세요:
        #     ```cypher
        #     MATCH (p:Plant {plant:1918})-[r:FACTORYISSUE]->(e:Event)
        #     WHERE date(e.date) >= date('2023-01-01') AND date(e.date) <= date('2023-04-30')
        #     RETURN date(e.date) AS date, sum(r.value) AS totalValue
        #     ORDER BY date;
        #     ```
            
        #     항상 Cypher 쿼리를 명확하게 작성하고, 쿼리 결과를 사용자가 이해하기 쉽게 설명하세요.
        
        # USTR 데이터 분석 전문가 에이전트
        USTR_agent = create_react_agent(
            model=model,
            tools=tools,
            name="USTR_expert",
            prompt="""
            당신은 USTR(미국 무역대표부) 데이터 분석 전문가입니다.
USTR의 공식 발언과 방글라데시 공급망 변화의 상관관계를 분석할 수 있습니다.

주요 분석 기능:

1. USTR 발언 시점 식별
- 2023년 2월 10일: 방글라데시의 위조 의류 수출에 대한 우려 제기
- 2023년 3월 13~19일: IPEF 2차 협상 라운드에서 공급망 회복력 논의
- 2023년 7월 9~15일: IPEF 4차 협상 라운드에서 공급망 협정 법적 검토

2. 발언 전후 공급망 변화 분석
- 발언 전후 30일 기간의 데이터 비교
- 주요 지표: 생산량, 이벤트 빈도, 공급망 안정성
- 주요 공장(예: Plant 1918, 2045)의 변화 추적

3. 공급망 지표 계산
- 생산성 변화율: (발언 후 - 발언 전) / 발언 전 * 100
- 이벤트 빈도 변화: 발언 후 이벤트 수 / 발언 전 이벤트 수
- 공급망 안정성: 표준편차 변화

supplychain_agent와 협력하여 이러한 분석을 수행하세요.
            """
        )
        
        # Supervisor 워크플로우 생성
        workflow = create_supervisor(
            [supplychain_agent, USTR_agent],
            model=model,
            prompt=(
                "당신은 공급망 분석 팀의 관리자입니다. "
                "USTR 발언과 관련된 공급망 변화 분석이 필요할 때는 USTR_expert를 사용하세요. "
                "일반적인 공급망 분석과 Neo4j 쿼리가 필요할 때는 supplychain_agent를 사용하세요. "
                "분석 결과를 종합하여 USTR 발언이 공급망에 미친 영향을 종합적으로 평가하세요."
            )
        )
        
        # 워크플로우 컴파일
        app = workflow.compile()
        
        # 테스트 질문들 실행
        questions = [
            # "could you analysis sales order situation with plant at May 2023 by bi-weekly including related product, product subgroup"
            # "2023년 2월 10일 위조 의류 발언 이후, 관련있는 품목을 생산하는 공장들의 생산성은 어떻게 변화했나요?",

            # "Plant 2045의 공급망 안정성은 2023년 2월 10일 발언 전후로 어떤 차이를 보였나요?",

            # "2023년 3월 13~19일 IPEF 2차 회의 이후 전체 공장에서 발생한 이벤트 빈도는 어떻게 변화했나요?",

            "Plant 1918과 Plant 2045의 2023년 1~4월 평균 생산량을 비교하고, 2월 10일 발언의 영향을 분석해주세요."
            # "2023년 3월 15일 USTR의 중국산 전기차 관세 검토 발언 이후 Plant 1918의 생산성 변화를 분석해주세요.",
            # "반도체 수출규제 강화 발언(2023년 5월 20일) 전후로 Plant 2045의 공급망 안정성은 어떻게 변화했나요?",
            # "2023년 7월 10일 공급망 안정화 정책 발언 이후 전체 공장의 이벤트 발생 빈도는 어떻게 변화했나요?",
            # "Plant 1918과 2045의 2023년 전체 생산량을 비교하고, USTR 발언 시점별 변화를 분석해주세요.",
            # "2023년 USTR 발언 시점별로 가장 큰 영향을 받은 상위 3개 공장은 어디인가요?",
            #             "what's (3 + 5) x 12?",
            #  "Plant 1918의 2023년 1월부터 4월까지의 일별 FACTORYISSUE.value 합계를 알고 싶습니다.",
            # "Plant 1918의 2023년 1월의 평균 FACTORYISSUE.value는 얼마인가요? 그리고 이 값이 2023년 4월의 평균 값과 어떻게 다른지 비교해주세요.",
            # "Plant 1918과 Plant 2045의 2023년 전체 생산량을 비교해주세요. 어느 공장이 더 효율적으로 운영되었나요?",
            # "2023년에 가장 많은 이벤트가 발생한 상위 3개 공장은 어디인가요? 각 공장의 이벤트 수와 유형을 알려주세요.",
            # "Plant 1918의 공급망 네트워크를 분석해주세요. 어떤 공급업체들과 연결되어 있으며, 가장 중요한 공급업체는 누구인가요?",
            # "2023년 1분기와 2분기의 전체 공장 생산성 추세를 비교해주세요. 어떤 패턴이 발견되나요?",
            # "Plant 1918에서 발생한 이벤트 유형별 빈도수를 알려주세요. 가장 자주 발생하는 이벤트는 무엇이며, 이 정보를 바탕으로 어떤 개선점을 제안할 수 있나요?",
            # "공급망 네트워크에서 가장 중앙성이 높은(centrality) 노드는 무엇인가요? 이 노드가 전체 네트워크에 미치는 영향을 설명해주세요.",
            # "Plant 1918과 직접 연결된 모든 노드들을 찾고, 그 관계의 유형과 중요도를 분석해주세요.",
            # "2023년 각 분기별 전체 공장의 평균 가동률은 어떻게 변화했나요? 시각적으로 설명해주세요."
        ]
        results = []
        for i, question in enumerate(questions):
            print(f"\n\n=== 질문 {i+1}: {question} ===")
            result = await app.ainvoke({
                "messages": [{"role": "user", "content": question}]
            })
            print_messages(result["messages"])
            results.append(result)
        
        return app

# 비동기 환경에서 그래프 초기화를 위한 함수
def initialize_graph():
    return asyncio.run(_initialize_graph())

async def _initialize_graph():
    app = await create_graph()
    return app

def print_messages(messages):
    """메시지 리스트를 보기 좋게 출력합니다."""
    for msg in messages:
        # LangChain 메시지 객체 처리
        if hasattr(msg, 'type') and hasattr(msg, 'content'):
            role = msg.type
            content = msg.content
        # 딕셔너리 메시지 처리
        elif isinstance(msg, dict):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
        else:
            print(f"지원되지 않는 메시지 형식: {type(msg)}")
            continue
            
        if role == "user" or role == "human":
            print(f"USER: {content}")
        else:
            print(f"AI ({role.upper()}): {content}")
            print("-" * 50)

# 직접 실행할 때만 테스트 질문을 처리
if __name__ == "__main__":
    asyncio.run(_initialize_graph())
else:
    # LangGraph Dev 서버용 그래프 노출
    graph = initialize_graph() 