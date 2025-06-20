import asyncio
import logging
from typing import Any, Dict, List, Optional

from neo4j import AsyncGraphDatabase, AsyncDriver
from neo4j.exceptions import Neo4jError

# Import the Server and types from mcp.server module
from mcp.server import Server
import mcp.types as types

logger = logging.getLogger(__name__)

class Neo4jDatabase:
    def __init__(self, uri: str, username: str, password: str):
        self.uri = uri
        self.username = username
        self.password = password
        self.driver: Optional[AsyncDriver] = None
    
    async def __aenter__(self):
        """Async context manager enter method."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit method."""
        await self.close()
        
    async def connect(self):
        """Connect to the Neo4j database."""
        if self.driver is None:
            self.driver = AsyncGraphDatabase.driver(
                self.uri, auth=(self.username, self.password)
            )
            # Verify connection
            try:
                await self.driver.verify_connectivity()
                logger.info("Successfully connected to Neo4j database")
            except Neo4jError as e:
                logger.error(f"Failed to connect to Neo4j: {e}")
                raise
        return self.driver
    
    async def close(self):
        """Close the database connection."""
        if self.driver:
            await self.driver.close()
            self.driver = None
            logger.info("Neo4j connection closed")
    
    async def execute_read(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a read-only Cypher query."""
        if not self.driver:
            await self.connect()
        
        try:    
            async with self.driver.session() as session:
                result = await session.run(query, params or {})
                records = await result.values()
                return [dict(zip(result.keys(), record)) for record in records]
        except Exception as e:
            logger.error(f"Error executing read query: {e}")
            # Try reconnecting once on error
            await self.close()
            await self.connect()
            async with self.driver.session() as session:
                result = await session.run(query, params or {})
                records = await result.values()
                return [dict(zip(result.keys(), record)) for record in records]
    
    async def execute_write(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a write Cypher query."""
        if not self.driver:
            await self.connect()
        
        try:
            async with self.driver.session() as session:
                result = await session.run(query, params or {})
                records = await result.values()
                return [dict(zip(result.keys(), record)) for record in records]
        except Exception as e:
            logger.error(f"Error executing write query: {e}")
            # Try reconnecting once on error
            await self.close()
            await self.connect()
            async with self.driver.session() as session:
                result = await session.run(query, params or {})
                records = await result.values()
                return [dict(zip(result.keys(), record)) for record in records]

async def setup_neo4j_server(neo4j_url: str, neo4j_username: str, neo4j_password: str):
    """Set up a Neo4j MCP server with async handlers."""
    logger.info(f"Connecting to Neo4j MCP Server with DB URL: {neo4j_url}")
    
    db = Neo4jDatabase(neo4j_url, neo4j_username, neo4j_password)
    await db.connect()  # Ensure connection is established
    
    # Create an MCP server
    server = Server("neo4j-manager")
    
    # Register handlers
    logger.debug("Registering handlers")
    
    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        """List available tools"""
        return [
            types.Tool(
                name="read-neo4j-cypher",
                description="Execute a Cypher query on the neo4j database",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Cypher read query to execute"},
                        "params": {"type": "object", "description": "Parameters for the query"}
                    },
                    "required": ["query"],
                },
            ),
            types.Tool(
                name="write-neo4j-cypher",
                description="Execute a write Cypher query on the neo4j database",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Cypher write query to execute"},
                        "params": {"type": "object", "description": "Parameters for the query"}
                    },
                    "required": ["query"],
                },
            ),
        ]
    
    @server.call_tool()
    async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tool calls to execute Cypher queries."""
        if name == "read-neo4j-cypher":
            query = arguments.get("query")
            params = arguments.get("params", {})
            
            try:
                results = await db.execute_read(query, params)
                return {"results": results, "success": True}
            except Exception as e:
                logger.error(f"Error executing read query: {e}")
                return {"error": str(e), "success": False}
        
        elif name == "write-neo4j-cypher":
            query = arguments.get("query")
            params = arguments.get("params", {})
            
            try:
                results = await db.execute_write(query, params)
                return {"results": results, "success": True}
            except Exception as e:
                logger.error(f"Error executing write query: {e}")
                return {"error": str(e), "success": False}
        
        return {"error": f"Unknown tool: {name}", "success": False}
    
    # Instead of using on_shutdown decorator, we'll ensure the db connection is 
    # properly closed in the mcp_example function in neo4j_supervisor_example.py
    
    return server, db 