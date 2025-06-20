# Neo4j Integration with LangGraph Supervisor

This example shows how to integrate Neo4j with LangGraph Supervisor using the Model Context Protocol (MCP).

## Setup

1. Create a virtual environment and install the required dependencies:

```bash
cd examples
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r neo4j_requirements.txt
```

2. Set up your Neo4j environment variables:

```bash
export NEO4J_URL="bolt://localhost:7687"
export NEO4J_USERNAME="neo4j"
export NEO4J_PASSWORD="your_password"
```

On Windows:
```cmd
set NEO4J_URL=bolt://localhost:7687
set NEO4J_USERNAME=neo4j
set NEO4J_PASSWORD=your_password
```

3. Make sure you have a Neo4j database running at the specified URL.

## Running the Examples

### Running the Neo4j MCP Server

This example starts a standalone MCP server providing Neo4j database access:

```bash
python examples/neo4j_supervisor_example.py mcp
```

### Testing the Neo4j MCP Server

This example connects to the MCP server as a client and executes a Neo4j query:

```bash
python examples/test_neo4j_server.py
```

### LangGraph Supervisor with Neo4j

This example shows how to use Neo4j with LangGraph Supervisor for multi-agent workflows:

```bash
python examples/neo4j_supervisor_example.py
```

## Implementation Details

### Neo4j Manager

The Neo4j manager (`neo4j_manager.py`) provides:

1. Asynchronous connection to Neo4j databases
2. Methods for executing read and write queries
3. Integration with MCP for exposing Neo4j capabilities via a server

### Using with LangGraph Supervisor

There are two approaches for Neo4j integration:

1. **Direct Integration**: Using Neo4j database methods directly with LangGraph agents
2. **MCP Server Integration**: Running a separate Neo4j MCP server that can be called by any MCP client

## Troubleshooting

If you encounter errors like "Cannot import name 'Server' from...", make sure you're using the correct MCP package version:

```bash
pip install "mcp[cli]"
```

For Neo4j connection issues, verify:
1. Neo4j database is running
2. Connection URL, username, and password are correct
3. Neo4j driver is properly installed with `pip install neo4j>=5.14.0` 