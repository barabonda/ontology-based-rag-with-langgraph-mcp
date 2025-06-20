import requests
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class Neo4jHttpTools:
    """HTTP를 통해 Neo4j API 서버와 통신하는 도구"""
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        logger.info(f"Neo4j HTTP Tools initialized with API URL: {api_base_url}")
    
    def read_neo4j(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Neo4j 읽기 쿼리 실행"""
        if params is None:
            params = {}
        
        endpoint = f"{self.api_base_url}/api/read"
        payload = {"query": query, "params": params}
        
        try:
            response = requests.post(endpoint, json=payload)
            response.raise_for_status()  # HTTP 오류 발생 시 예외 발생
            
            result = response.json()
            if not result.get("success", False):
                logger.error(f"Neo4j read query failed: {result.get('error')}")
                return []
            
            return result.get("results", [])
        except Exception as e:
            logger.error(f"Error executing Neo4j read query via HTTP: {e}")
            return []
    
    def write_neo4j(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Neo4j 쓰기 쿼리 실행"""
        if params is None:
            params = {}
        
        endpoint = f"{self.api_base_url}/api/write"
        payload = {"query": query, "params": params}
        
        try:
            response = requests.post(endpoint, json=payload)
            response.raise_for_status()  # HTTP 오류 발생 시 예외 발생
            
            result = response.json()
            if not result.get("success", False):
                logger.error(f"Neo4j write query failed: {result.get('error')}")
                return []
            
            return result.get("results", [])
        except Exception as e:
            logger.error(f"Error executing Neo4j write query via HTTP: {e}")
            return []

def create_neo4j_http_tools(api_base_url: str = "http://localhost:8000"):
    """Neo4j HTTP 도구 생성"""
    tools = Neo4jHttpTools(api_base_url)
    
    # 동기 함수 래퍼 (LangGraph용)
    def read_neo4j_sync(query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """읽기 전용 Neo4j Cypher 쿼리 실행"""
        return tools.read_neo4j(query, params or {})
    
    def write_neo4j_sync(query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """쓰기 Neo4j Cypher 쿼리 실행"""
        return tools.write_neo4j(query, params or {})
    
    return [read_neo4j_sync, write_neo4j_sync], tools 