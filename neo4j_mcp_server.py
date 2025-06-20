"""
Neo4j MCP 서버 구현
-----------------
실제 Neo4j 데이터베이스에 연결하여 쿼리를 수행하는 MCP 서버입니다.
"""

import os
import json
import time
from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, DriverError
from mcp.server.fastmcp import FastMCP

# 환경 변수 로드
load_dotenv()

# Neo4j 연결 정보
NEO4J_URI = os.environ.get("NEO4J_URI", "neo4j://localhost:7687")
NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")

print(f"Neo4j 연결 정보: URI={NEO4J_URI}, 사용자={NEO4J_USERNAME}")

# MCP 서버 초기화
mcp = FastMCP("Neo4j")

# Neo4j 연결 클래스
class Neo4jConnector:
    def __init__(self, uri, username, password, max_retry=3):
        self._uri = uri
        self._username = username
        self._password = password
        self._max_retry = max_retry
        self._driver = None
        self._connect()
        
    def _connect(self):
        """데이터베이스에 연결합니다."""
        retry_count = 0
        while retry_count < self._max_retry:
            try:
                if self._driver:
                    try:
                        self._driver.close()
                    except Exception:
                        pass
                    
                self._driver = GraphDatabase.driver(
                    self._uri, 
                    auth=(self._username, self._password),
                    max_connection_lifetime=300  # 연결 수명 설정 (5분)
                )
                # 연결 확인
                with self._driver.session() as session:
                    result = session.run("RETURN 1 as test")
                    # 결과를 완전히 소비 (중요)
                    result.consume()
                print(f"Neo4j 데이터베이스에 성공적으로 연결됨: {self._uri}")
                return
            except Exception as e:
                retry_count += 1
                print(f"Neo4j 연결 시도 {retry_count}/{self._max_retry} 실패: {str(e)}")
                if retry_count < self._max_retry:
                    time.sleep(1)  # 재시도 전 1초 대기
        
        print(f"Neo4j 데이터베이스 연결 실패: {self._uri}")
        
    def close(self):
        """연결을 종료합니다."""
        if self._driver:
            self._driver.close()
            self._driver = None
    
    def ensure_connection(self):
        """연결이 활성 상태인지 확인하고, 필요하면 재연결합니다."""
        try:
            if not self._driver:
                self._connect()
                return
                
            # 간단한 쿼리로 연결 확인
            with self._driver.session() as session:
                result = session.run("RETURN 1 as test")
                # 결과를 완전히 소비 (중요)
                result.consume()
        except Exception as e:
            print(f"연결 재설정 중: {str(e)}")
            self._connect()
        
    def run_cypher(self, query, params=None):
        """Cypher 쿼리를 실행합니다."""
        self.ensure_connection()
        
        try:
            with self._driver.session() as session:
                result = session.run(query, params or {})
                
                # 중요: 세션이 닫히기 전에 모든 결과를 리스트로 변환
                # 이렇게 하면 세션이 닫혀도 결과를 계속 사용할 수 있음
                records = []
                for record in result:
                    # Neo4j 결과를 Python 딕셔너리로 변환
                    record_dict = {}
                    for key, value in record.items():
                        # Neo4j 객체를 기본 Python 타입으로 변환
                        if hasattr(value, '__str__') and not isinstance(value, (str, int, float, bool, list, dict)):
                            record_dict[key] = str(value)
                        else:
                            record_dict[key] = value
                    records.append(record_dict)
                
                # 결과 리스트 반환
                return records
        except ServiceUnavailable as e:
            print(f"Neo4j 서비스 사용 불가: {str(e)}")
            self._connect()  # 재연결 시도
            return {"error": f"데이터베이스 서비스 사용 불가: {str(e)}"}
        except DriverError as e:
            print(f"Neo4j 드라이버 오류: {str(e)}")
            self._connect()  # 재연결 시도
            return {"error": f"데이터베이스 드라이버 오류: {str(e)}"}
        except Exception as e:
            print(f"쿼리 실행 중 오류: {str(e)}")
            return {"error": f"쿼리 실행 중 오류: {str(e)}"}
    
    def get_schema(self):
        """데이터베이스 스키마 정보를 가져옵니다."""
        self.ensure_connection()
        
        try:
            node_labels_query = "CALL db.labels()"
            rel_types_query = "CALL db.relationshipTypes()"
            properties_query = "CALL db.propertyKeys()"
            
            with self._driver.session() as session:
                # 각 쿼리 실행 시 결과를 즉시 리스트로 변환
                node_labels_result = session.run(node_labels_query)
                node_labels = [record["label"] for record in node_labels_result]
                
                rel_types_result = session.run(rel_types_query)
                rel_types = [record["relationshipType"] for record in rel_types_result]
                
                properties_result = session.run(properties_query)
                properties = [record["propertyKey"] for record in properties_result]
                
                # 노드별 속성 가져오기
                node_schema = {}
                for label in node_labels:
                    properties_query = f"""
                    MATCH (n:{label}) 
                    UNWIND keys(n) AS prop 
                    RETURN DISTINCT prop
                    LIMIT 20
                    """
                    node_props_result = session.run(properties_query)
                    node_props = [record["prop"] for record in node_props_result]
                    node_schema[label] = node_props
                    
                return {
                    "node_labels": node_labels,
                    "relationship_types": rel_types,
                    "properties": properties,
                    "node_schema": node_schema
                }
        except Exception as e:
            print(f"스키마 정보 조회 중 오류: {str(e)}")
            return {"error": f"스키마 정보 조회 중 오류: {str(e)}"}

# Neo4j 커넥터 초기화
connector = Neo4jConnector(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)

@mcp.tool()
def run_cypher(query: str) -> str:
    """Neo4j 쿼리 실행 도구"""
    session = None
    try:
        # 1. 연결 확인
        connector.ensure_connection()
        
        # 2. 새 세션 열기
        session = connector._driver.session()
        
        # 3. 쿼리 실행
        result = session.run(query)
        
        # 4. 결과 완전히 메모리로 변환
        records = [{k: v for k, v in record.items()} for record in result]
        
        # 5. 결과 소비 확인
        result.consume()
        
        # 6. 변환된 결과 반환
        return json.dumps(records, default=str, ensure_ascii=False)
    finally:
        # 7. 항상 세션 닫기
        if session:
            session.close()

@mcp.tool()
def run_cypher_with_params(query: str, params: str) -> str:
    """파라미터를 사용하여 Neo4j 데이터베이스에 Cypher 쿼리를 실행합니다.
    
    Args:
        query (str): 파라미터화된 Cypher 쿼리 문자열
        params (str): JSON 형식의 파라미터 딕셔너리
        
    Returns:
        str: 쿼리 결과를 JSON 형식으로 반환
        
    예제 사용:
    쿼리: MATCH (p:Plant {plant:$plant_id})-[r:FACTORYISSUE]->(e:Event)
          WHERE date(e.date) >= date($start_date) AND date(e.date) <= date($end_date)
          RETURN date(e.date) AS date, sum(r.value) AS totalValue ORDER BY date
    파라미터: {"plant_id": 1918, "start_date": "2023-01-01", "end_date": "2023-04-30"}
    """
    try:
        connector.ensure_connection()  # 연결 상태 확인
        # 문자열 파라미터를 딕셔너리로 변환
        param_dict = json.loads(params)
        results = connector.run_cypher(query, param_dict)
        
        if isinstance(results, dict) and 'error' in results:
            return f"쿼리 실행 중 오류 발생: {results['error']}"
            
        return json.dumps(results, default=str, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        return "파라미터 JSON 형식이 올바르지 않습니다."
    except Exception as e:
        return f"쿼리 실행 중 오류 발생: {str(e)}"

@mcp.tool()
def get_schema() -> str:
    """Neo4j 데이터베이스의 스키마 정보를 반환합니다.
    
    Returns:
        str: 노드 라벨, 관계 유형, 속성 등의 스키마 정보를 JSON 형식으로 반환
    """
    try:
        connector.ensure_connection()  # 연결 상태 확인
        schema = connector.get_schema()
        
        if isinstance(schema, dict) and 'error' in schema:
            return f"스키마 정보 조회 중 오류 발생: {schema['error']}"
            
        return json.dumps(schema, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"스키마 정보 조회 중 오류 발생: {str(e)}"

@mcp.tool()
def get_node_counts() -> str:
    """Neo4j 데이터베이스의 노드 유형별 개수를 반환합니다.
    
    Returns:
        str: 각 노드 라벨별 개수를 JSON 형식으로 반환
    """
    try:
        connector.ensure_connection()  # 연결 상태 확인
        query = "MATCH (n) RETURN labels(n) AS labels, count(n) AS count"
        results = connector.run_cypher(query)
        
        if isinstance(results, dict) and 'error' in results:
            return f"노드 개수 조회 중 오류 발생: {results['error']}"
        
        # 결과 가공
        counts = {}
        for result in results:
            label = ', '.join(result["labels"]) if result["labels"] else "unlabeled"
            counts[label] = result["count"]
        return json.dumps(counts, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"노드 개수 조회 중 오류 발생: {str(e)}"

@mcp.tool()
def check_connection() -> str:
    """Neo4j 데이터베이스 연결을 확인합니다.
    
    Returns:
        str: 연결 상태 정보
    """
    try:
        connector.ensure_connection()
        return "Neo4j 데이터베이스에 성공적으로 연결됨"
    except Exception as e:
        return f"Neo4j 데이터베이스 연결 오류: {str(e)}"

if __name__ == "__main__":
    print("Neo4j MCP 서버 시작 중...")
    print(f"Neo4j URI: {NEO4J_URI}")
    print("다른 터미널에서 LangGraph를 사용하여 이 서버에 연결하세요.")
    try:
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        print("서버 종료 중...")
    finally:
        connector.close()
        print("Neo4j 연결 닫힘") 

