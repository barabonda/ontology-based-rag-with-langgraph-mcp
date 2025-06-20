import os
import logging
import requests
from typing import Dict, List, Any, TypedDict, Optional
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 상태 타입 정의
class GraphState(TypedDict):
    """그래프 상태 타입"""
    messages: List[Dict[str, Any]]
    cypher_query: str

# Neo4j API 연결 정보
NEO4J_API_URL = os.getenv("NEO4J_API_URL", "http://localhost:8000")

# Neo4j HTTP 도구
class Neo4jHttpClient:
    """HTTP를 통해 Neo4j API 서버와 통신하는 클라이언트"""
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        logger.info(f"Neo4j HTTP Client initialized with API URL: {api_base_url}")
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Neo4j 쿼리 실행"""
        if params is None:
            params = {}
        
        endpoint = f"{self.api_base_url}/api/read"
        payload = {"query": query, "params": params}
        
        try:
            logger.info(f"Sending request to {endpoint} with query: {query}")
            response = requests.post(endpoint, json=payload, timeout=10)
            logger.info(f"Received response with status: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"API error: {response.status_code} - {response.text}")
                return []
            
            result = response.json()
            if not result.get("success", False):
                logger.error(f"Query failed: {result.get('error')}")
                return []
            
            return result.get("results", [])
        except requests.RequestException as e:
            logger.error(f"HTTP request error: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return []

# Neo4j HTTP 클라이언트 초기화
neo4j_client = Neo4jHttpClient(NEO4J_API_URL)

# 노드 정의
def query_handler(state: GraphState) -> GraphState:
    """Neo4j 쿼리를 실행하고 결과를 상태에 추가하는 노드"""
    query = state.get("cypher_query", "")
    if not query:
        return {
            **state,
            "messages": state["messages"] + [
                {"role": "assistant", "content": "쿼리가 제공되지 않았습니다. 유효한 Cypher 쿼리를 입력해주세요."}
            ]
        }
    
    try:
        # 쿼리 실행
        logger.info(f"Executing query: {query}")
        results = neo4j_client.execute_query(query)
        
        # 결과 형식화
        if results:
            result_str = f"쿼리 결과: {results}"
            logger.info(f"Query succeeded with results: {results}")
        else:
            result_str = "쿼리 결과가 없습니다."
            logger.warning("Query returned no results")
        
        # 상태 업데이트
        return {
            **state,
            "messages": state["messages"] + [
                {"role": "assistant", "content": result_str}
            ]
        }
    except Exception as e:
        logger.error(f"Neo4j 쿼리 실행 중 오류 발생: {e}", exc_info=True)
        return {
            **state,
            "messages": state["messages"] + [
                {"role": "assistant", "content": f"쿼리 실행 중 오류가 발생했습니다: {str(e)}"}
            ]
        }

# LLM 노드
llm = ChatOpenAI(model="gpt-4o", temperature=0)

def process_message(state: GraphState) -> Dict[str, Any]:
    """사용자 메시지 처리 및 Neo4j 쿼리 생성"""
    messages = state["messages"]
    
    # LLM에 전달할 메시지 형식 구성
    chat_messages = [
        {"role": "system", "content": "당신은 Neo4j 데이터베이스 전문가입니다. 사용자의 질문을 분석하고 적절한 Cypher 쿼리를 생성해주세요."},
        *messages
    ]
    
    # LLM 호출
    response = llm.invoke(chat_messages)
    
    # Cypher 쿼리 추출
    cypher_query = extract_cypher_query(response.content)
    logger.info(f"Generated Cypher query: {cypher_query}")
    
    # 응답 메시지 추가
    new_messages = messages + [
        {"role": "assistant", "content": response.content}
    ]
    
    return {
        "messages": new_messages,
        "cypher_query": cypher_query
    }

def extract_cypher_query(text: str) -> str:
    """텍스트에서 Cypher 쿼리 추출"""
    lines = text.split("\n")
    query_lines = []
    in_cypher_block = False
    
    for line in lines:
        line_lower = line.lower().strip()
        if line.strip().startswith("```"):
            if "cypher" in line_lower or in_cypher_block:
                in_cypher_block = not in_cypher_block
            continue
        if in_cypher_block:
            query_lines.append(line)
    
    if not query_lines:
        # 코드 블록이 없는 경우 MATCH 또는 RETURN 키워드 포함된 줄 찾기
        for line in lines:
            if "MATCH" in line.upper() or "RETURN" in line.upper():
                query_lines.append(line)
    
    query = "\n".join(query_lines).strip()
    logger.info(f"Extracted query: {query}")
    return query

def should_continue(state: GraphState) -> str:
    """추가 쿼리가 필요한지 결정"""
    # 마지막 메시지가 사용자 메시지이면 계속
    if state["messages"] and state["messages"][-1]["role"] == "user":
        return "process"
    return "end"

# 그래프 구성
workflow = StateGraph(GraphState)
workflow.add_node("process", process_message)
workflow.add_node("query_node", query_handler)

# 조건부 엣지 추가
workflow.add_conditional_edges(
    "query_node",
    should_continue,
    {
        "process": "process",
        "end": END,
    }
)

# 기본 엣지 추가
workflow.add_edge(START, "process")
workflow.add_edge("process", "query_node")

# 그래프 컴파일
graph = workflow.compile()

# 테스트 함수
def test_neo4j_query():
    """Neo4j API 서버에 직접 테스트 쿼리 실행"""
    client = Neo4jHttpClient(NEO4J_API_URL)
    query = "MATCH (n) RETURN count(n) as count LIMIT 1"
    result = client.execute_query(query)
    logger.info(f"Test query result: {result}")
    return result

# LangGraph Dev 서버에서 실행할 준비 완료
if __name__ == "__main__":
    # 테스트 실행
    test_result = test_neo4j_query()
    if test_result:
        print(f"Neo4j API 연결 테스트 성공: {test_result}")
        print("Neo4j HTTP Graph 준비 완료 - langgraph dev로 실행하세요")
    else:
        print(f"Neo4j API 연결 테스트 실패. API 서버가 {NEO4J_API_URL}에서 실행 중인지 확인하세요.") 