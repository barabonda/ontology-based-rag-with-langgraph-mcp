#!/usr/bin/env python3
import os
import sys
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional

# Try to import from mcp package with fallback options
try:
    from mcp.server import create_server, MCPTool, MCPServer, MCPToolType
except ImportError:
    try:
        # Try FastMCP as alternative
        from fastmcp import FastMCP
        from fastmcp.types import ToolSchema
        # Create compatibility layer for old MCP API
        class MCPTool:
            """Compatibility class for FastMCP"""
            def __call__(self, params):
                pass
            def schema(self):
                pass
                
        class MCPToolType:
            """Compatibility enum for FastMCP"""
            FUNCTION = "function"
            
        # Define create_server function to maintain compatibility
        async def create_server(tools, port=8765):
            mcp = FastMCP(name="Neo4j MCP Server")
            for tool in tools:
                schema = tool.schema()
                @mcp.tool(schema=schema)
                async def wrapper(params):
                    return await tool(params)
                    
            # Return compatibility object with start/stop methods
            class CompatServer:
                async def start(self):
                    await mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
                async def stop(self):
                    # FastMCP doesn't have explicit stop, but we'd handle cleanup
                    pass
            return CompatServer()
        
        logging.info("Using FastMCP instead of standard MCP")
    except ImportError:
        logging.error("Neither 'mcp' nor 'fastmcp' packages are available. Please install one of them.")
        raise

from neo4j import AsyncGraphDatabase, Driver, Result, Record
from neo4j.exceptions import ServiceUnavailable, AuthError
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('mcp_server.log')
    ]
)
logger = logging.getLogger("mcp_neo4j_server")

# 환경 변수 로드
load_dotenv()

# Neo4j 연결 정보
NEO4J_URI = os.environ.get("NEO4J_URI", "neo4j://34.203.212.188:7687")
NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "ossca2727")

# Neo4j 연결 관리 클래스
class Neo4jConnection:
    """Neo4j 데이터베이스 연결 관리"""
    
    def __init__(self, 
                 uri: str, 
                 username: str, 
                 password: str, 
                 max_retry: int = 3,
                 connection_timeout: int = 10):
        self._uri = uri
        self._username = username
        self._password = password
        self._max_retry = max_retry
        self._connection_timeout = connection_timeout
        self._driver: Optional[Driver] = None
        self._is_connected = False
        
    async def connect(self) -> bool:
        """데이터베이스에 연결"""
        if self._is_connected and self._driver:
            return True
            
        try:
            # 드라이버 생성
            self._driver = AsyncGraphDatabase.driver(
                self._uri,
                auth=(self._username, self._password),
                max_connection_lifetime=300,
                connection_timeout=self._connection_timeout
            )
            
            # 연결 테스트
            async with self._driver.session() as session:
                result = await session.run("RETURN 1 as test")
                record = await result.single()
                if record and record.get("test") == 1:
                    self._is_connected = True
                    logger.info("Neo4j 연결 테스트 성공")
                    return True
                else:
                    raise Exception("Neo4j 연결 테스트 실패: 예상된 결과를 받지 못했습니다.")
                    
        except Exception as e:
            logger.error(f"Neo4j 연결 중 오류: {str(e)}")
            if self._driver:
                await self.disconnect()
            return False
    
    async def disconnect(self) -> None:
        """데이터베이스 연결 해제"""
        if self._driver:
            try:
                await self._driver.close()
            except Exception as e:
                logger.error(f"Neo4j 연결 해제 중 오류: {str(e)}")
            finally:
                self._driver = None
                self._is_connected = False
    
    async def run_cypher(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Cypher 쿼리 실행"""
        if not self._is_connected or not self._driver:
            success = await self.connect()
            if not success:
                return [{"error": "데이터베이스 연결 실패"}]
        
        try:
            async with self._driver.session() as session:
                result = await session.run(query, params or {})
                
                # 결과를 JSON 직렬화 가능한 형태로 변환
                records = []
                async for record in result:
                    record_dict = {}
                    for key, value in record.items():
                        try:
                            # 날짜, 시간 등 특별한 타입 처리
                            if hasattr(value, '__str__'):
                                record_dict[key] = str(value)
                            else:
                                record_dict[key] = value
                        except:
                            record_dict[key] = f"{type(value).__name__}"
                    
                    records.append(record_dict)
                
                return records
                
        except Exception as e:
            logger.error(f"쿼리 실행 중 오류: {str(e)}")
            
            # 네트워크 오류 등의 경우 재연결 시도
            if isinstance(e, (ServiceUnavailable, AuthError)):
                self._is_connected = False
                await self.disconnect()
                return await self.run_cypher(query, params)
                
            return [{"error": f"쿼리 실행 중 오류: {str(e)}"}]
    
    async def get_schema(self) -> Dict[str, Any]:
        """데이터베이스 스키마 정보 조회"""
        if not self._is_connected or not self._driver:
            success = await self.connect()
            if not success:
                return {"error": "데이터베이스 연결 실패"}
        
        try:
            schema = {}
            
            # 노드 레이블 조회
            node_query = """
            CALL db.labels() YIELD label
            RETURN collect(label) AS labels
            """
            
            # 관계 타입 조회
            rel_query = """
            CALL db.relationshipTypes() YIELD relationshipType
            RETURN collect(relationshipType) AS relationshipTypes
            """
            
            # 속성 키 조회
            prop_query = """
            CALL db.propertyKeys() YIELD propertyKey
            RETURN collect(propertyKey) AS propertyKeys
            """
            
            async with self._driver.session() as session:
                # 노드 레이블
                result = await session.run(node_query)
                record = await result.single()
                schema["labels"] = record["labels"] if record else []
                
                # 관계 타입
                result = await session.run(rel_query)
                record = await result.single()
                schema["relationshipTypes"] = record["relationshipTypes"] if record else []
                
                # 속성 키
                result = await session.run(prop_query)
                record = await result.single()
                schema["propertyKeys"] = record["propertyKeys"] if record else []
            
            return schema
            
        except Exception as e:
            logger.error(f"스키마 조회 중 오류: {str(e)}")
            return {"error": f"스키마 조회 중 오류: {str(e)}"}

# Neo4j MCP 도구 정의
class RunCypherTool(MCPTool):
    """Cypher 쿼리 실행 도구"""
    
    def __init__(self, neo4j_connection: Neo4jConnection):
        self.neo4j = neo4j_connection
        
    async def __call__(self, params: Dict[str, Any]) -> Any:
        """도구 실행"""
        query = params.get("query")
        if not query:
            return {"error": "쿼리가 제공되지 않았습니다."}
            
        query_params = params.get("params", {})
        return await self.neo4j.run_cypher(query, query_params)
    
    def schema(self) -> Dict[str, Any]:
        """도구 스키마 정의"""
        return {
            "name": "run_cypher",
            "description": "Neo4j 데이터베이스에 대해 Cypher 쿼리를 실행합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "실행할 Cypher 쿼리"
                    },
                    "params": {
                        "type": "object",
                        "description": "쿼리에 사용할 매개변수"
                    }
                },
                "required": ["query"]
            },
            "returns": {
                "type": "array",
                "items": {
                    "type": "object"
                }
            },
            "tool_type": MCPToolType.FUNCTION
        }

class GetSchemaTool(MCPTool):
    """데이터베이스 스키마 조회 도구"""
    
    def __init__(self, neo4j_connection: Neo4jConnection):
        self.neo4j = neo4j_connection
        
    async def __call__(self, params: Dict[str, Any]) -> Any:
        """도구 실행"""
        return await self.neo4j.get_schema()
    
    def schema(self) -> Dict[str, Any]:
        """도구 스키마 정의"""
        return {
            "name": "get_schema",
            "description": "Neo4j 데이터베이스의 스키마 정보를 조회합니다.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            },
            "returns": {
                "type": "object",
                "properties": {
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "relationshipTypes": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "propertyKeys": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            },
            "tool_type": MCPToolType.FUNCTION
        }

class ConnectionStatusTool(MCPTool):
    """연결 상태 확인 도구"""
    
    def __init__(self, neo4j_connection: Neo4jConnection):
        self.neo4j = neo4j_connection
    
    async def __call__(self, params: Dict[str, Any]) -> Any:
        """도구 실행"""
        connected = await self.neo4j.connect()
        return {
            "connected": connected,
            "uri": self.neo4j._uri
        }
    
    def schema(self) -> Dict[str, Any]:
        """도구 스키마 정의"""
        return {
            "name": "connection_status",
            "description": "Neo4j 데이터베이스 연결 상태를 확인합니다.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            },
            "returns": {
                "type": "object",
                "properties": {
                    "connected": {"type": "boolean"},
                    "uri": {"type": "string"}
                }
            },
            "tool_type": MCPToolType.FUNCTION
        }

# MCP 서버 생성 및 실행 함수
async def run_server():
    """MCP 서버 실행"""
    # Neo4j 연결 생성
    neo4j_connection = Neo4jConnection(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)
    
    # 도구 초기화
    run_cypher_tool = RunCypherTool(neo4j_connection)
    get_schema_tool = GetSchemaTool(neo4j_connection)
    connection_status_tool = ConnectionStatusTool(neo4j_connection)
    
    # 서버 생성
    server = await create_server(
        tools=[run_cypher_tool, get_schema_tool, connection_status_tool],
        port=8765,  # 고정 포트 사용
    )
    
    logger.info(f"Neo4j MCP 서버가 http://localhost:8765 에서 실행 중입니다.")
    
    # 서버 시작
    await server.start()
    
    # 종료 신호 대기
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("서버 종료 중...")
    finally:
        # 리소스 정리
        await neo4j_connection.disconnect()
        await server.stop()
        logger.info("서버가 정상적으로 종료되었습니다.")

# 메인 실행
if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("서버가 중단되었습니다.")
    except Exception as e:
        logger.error(f"서버 실행 중 오류 발생: {str(e)}")
        sys.exit(1) 