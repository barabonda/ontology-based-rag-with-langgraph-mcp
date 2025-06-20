# Neo4j HTTP API 통합 for LangGraph

이 구현은 Neo4j와 LangGraph 간에 직접 연결하는 대신 중간 API 서버를 사용하는 방법을 보여줍니다.

## 문제점

Neo4j를 LangGraph와 직접 통합할 때 다음과 같은 문제가 발생할 수 있습니다:

1. **ClosedResourceError**: Neo4j 연결 라이프사이클 관리 문제
2. **네트워크 연결 문제**: 컨테이너화된 환경 또는 클라우드 환경에서 localhost 접근 제한
3. **비동기 코드 충돌**: LangGraph와 Neo4j 비동기 인터페이스 간의 충돌

## 해결책: HTTP API 서버

이 문제를 해결하기 위해 다음과 같은 아키텍처를 구현합니다:

```
LangGraph Supervisor --> HTTP API 요청 --> Neo4j API 서버 --> Neo4j 데이터베이스
```

## 구성 요소

1. **neo4j_api_server.py**: Neo4j 데이터베이스에 연결하고 HTTP API를 제공하는 FastAPI 서버
2. **langgraph_supervisor/neo4j_http_tools.py**: LangGraph에서 사용할 수 있는 HTTP 기반 Neo4j 도구
3. **examples/neo4j_http_example.py**: HTTP 기반 Neo4j 도구를 사용하는 LangGraph 예제

## 설정 방법

1. 환경 변수 설정:
   ```bash
   cp neo4j.env.example .env
   # 필요에 따라 .env 파일 편집
   ```

2. API 서버 실행:
   ```bash
   python neo4j_api_server.py
   ```
   
3. 새 터미널에서 LangGraph 예제 실행:
   ```bash
   python examples/neo4j_http_example.py
   ```

## 장점

1. **연결 관리 간소화**: API 서버가 Neo4j 연결 라이프사이클을 관리
2. **네트워크 격리 해결**: HTTP를 통해 다른 네트워크 또는 컨테이너에 있는 Neo4j에 접근 가능
3. **비동기 처리 방지**: HTTP 요청은 동기식으로 처리되므로 비동기 문제 해결
4. **쉬운 디버깅**: API 서버 로그를 통해 쿼리 문제 추적 용이
5. **스케일링 가능**: API 서버를 수평 확장하여 부하 분산 가능 