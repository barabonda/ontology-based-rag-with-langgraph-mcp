# 🧠 LinkBrain Prompt Engineering QA Studio v2.0

linkbrain.py에서 영감을 받은 고급 프롬프트 엔지니어링 QA 웹 스튜디오입니다. **Neo4j 연동**, **멀티 에이전트 워크플로우**, **배치 테스트**, **LinkBrain 스타일 질문 템플릿**을 지원합니다.

## ✨ 주요 기능

### 🔥 고급 기능 (v2.0)
- **🔗 Neo4j MCP 연동**: linkbrain.py와 동일한 Neo4j 데이터베이스 연결
- **🤖 멀티 에이전트 시스템**: linkbrain_agent, analysis_agent, supervisor 지원
- **🚀 배치 테스트**: 미리 정의된 질문들을 한 번에 실행
- **🧠 LinkBrain 템플릿**: linkbrain.py의 9가지 템플릿 질문 내장
- **📊 에이전트 추적**: 어떤 에이전트가 실행되었는지 시각적 표시
- **⚡ 실시간 Neo4j 상태**: 연결 상태 모니터링 및 수동 연결

### 🎨 UI/UX 특징  
- **🌌 Glass Morphism** 디자인 적용
- **📱 반응형 웹** 인터페이스  
- **🎭 부드러운 애니메이션** 효과
- **🎯 직관적인 카드 기반** 네비게이션
- **📈 배치 테스트 진행 표시기**
- **🔖 에이전트별 색상 코딩**

## 🚀 시작하기

### 1. 환경 설정

```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치 (새로운 의존성 포함)
pip install -r requirements_webapp.txt
```

### 2. 환경 변수 설정

`.env` 파일을 생성하고 필요한 키들을 설정하세요:

```env
OPENAI_API_KEY=your_openai_api_key_here
# Neo4j 연결을 위한 추가 환경변수가 필요할 수 있습니다
```

### 3. Neo4j MCP 서버 설정

LinkBrain 기능을 위해서는 `neo4j_mcp_server.py` 파일이 프로젝트 루트에 있어야 합니다. (linkbrain.py 프로젝트에서 복사)

### 4. 웹서버 실행

```bash
# 방법 1: 직접 실행
python prompt_qa_webapp.py

# 방법 2: uvicorn 명령어 (권장 - 자동 리로드 지원)
uvicorn prompt_qa_webapp:app --reload --host 0.0.0.0 --port 8001
```

웹브라우저에서 `http://localhost:8001`에 접속하세요.

## 📖 사용법

### 1️⃣ Neo4j 연결
1. 웹페이지 상단의 **Neo4j 연결 상태**를 확인
2. 🔴 상태일 경우 **"🔗 Neo4j 연결"** 버튼 클릭
3. 🟢 상태가 되면 LinkBrain 기능 사용 가능

### 2️⃣ 새 프롬프트 생성
1. **"➕ 새 프롬프트"** 버튼 클릭
2. 프롬프트 타입 선택:
   - **Simple**: 기본 OpenAI API 호출
   - **LinkBrain**: Neo4j + 멀티 에이전트 워크플로우
3. 프롬프트 이름, 설명, 내용 입력
4. **저장** 버튼으로 새 버전 생성

### 3️⃣ LinkBrain 템플릿 질문 사용
1. **"🧠 LinkBrain 템플릿"** 버튼 클릭
2. 9가지 미리 정의된 질문 중 선택:
   - AI 관련 링크 조회
   - 대분류별 링크 개수
   - 최근 저장된 링크와 키워드
   - 월별 링크 저장 통계 등
3. 원하는 질문들에 체크박스 선택
4. **"🚀 배치 테스트 실행"** 버튼으로 한 번에 실행

### 4️⃣ 단일 프롬프트 테스트
1. 프롬프트 카드에서 **"테스트"** 버튼 클릭
2. 실행 타입 선택 (Simple 또는 LinkBrain)
3. 테스트 질문 입력
4. AI 모델 선택 (GPT-4o, GPT-4o Mini, GPT-3.5 Turbo)
5. **"🚀 테스트 실행"** 버튼으로 실행

### 5️⃣ 결과 분석
- **에이전트 배지**: 사용된 에이전트를 색상으로 구분 표시
  - 🟣 linkbrain_agent: 보라색
  - 🔵 analysis_agent: 파란색  
  - 🟡 supervisor: 노란색
- **실행 지표**: 시간, 토큰 사용량, 모델 정보
- **Cypher 결과**: 표 형식 자동 감지 및 포맷팅

## 🏗️ 아키텍처 v2.0

### 백엔드 (FastAPI + LinkBrain)
- **Neo4j MCP 연동**: linkbrain.py와 동일한 Multi-Server MCP Client
- **멀티 에이전트 시스템**: create_supervisor로 구축된 워크플로우
- **배치 처리**: 여러 질문을 비동기로 순차 실행
- **상태 관리**: Neo4j 연결 상태 실시간 추적

### 데이터베이스 스키마 v2.0

```sql
-- 프롬프트 버전 테이블 (업데이트됨)
CREATE TABLE prompt_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    content TEXT NOT NULL,
    version TEXT NOT NULL,
    git_hash TEXT,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    description TEXT,
    prompt_type TEXT DEFAULT 'simple'  -- 신규: simple, linkbrain
);

-- 테스트 실행 결과 테이블 (업데이트됨)
CREATE TABLE test_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_version_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    response TEXT NOT NULL,
    model_used TEXT NOT NULL,
    execution_time REAL NOT NULL,
    tokens_used INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    execution_type TEXT DEFAULT 'simple',  -- 신규: simple, linkbrain, batch
    agents_used TEXT DEFAULT '',           -- 신규: 사용된 에이전트 추적
    FOREIGN KEY (prompt_version_id) REFERENCES prompt_versions (id)
);

-- 배치 테스트 결과 테이블 (신규)
CREATE TABLE batch_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_version_id INTEGER NOT NULL,
    questions TEXT NOT NULL,        -- JSON 배열
    responses TEXT NOT NULL,        -- JSON 배열
    total_execution_time REAL NOT NULL,
    created_at TEXT NOT NULL,
    agents_used TEXT DEFAULT '',
    FOREIGN KEY (prompt_version_id) REFERENCES prompt_versions (id)
);
```

## 🎯 linkbrain.py와의 통합

### ✅ 동일한 Neo4j MCP 연동
```python
# linkbrain.py와 동일한 MCP 클라이언트 설정
client = MultiServerMCPClient({
    "neo4j": {
        "command": "python",
        "args": [str(current_dir / "neo4j_mcp_server.py")],
        "transport": "stdio",
    }
})
```

### ✅ 동일한 멀티 에이전트 구조
- **linkbrain_agent**: Neo4j 전용 Cypher 쿼리 에이전트
- **analysis_agent**: 데이터 분석 전문가
- **supervisor**: 두 에이전트를 조율하는 슈퍼바이저

### ✅ 동일한 프롬프트 시스템
- linkbrain.py의 정확한 프롬프트를 웹에서 재사용
- 버전 관리 시스템 (git_hash + content_hash + timestamp)
- 동일한 Cypher 쿼리 결과 포맷팅

### ✅ 동일한 질문 템플릿
```python
LINKBRAIN_QUESTIONS = [
    "내가 저장한 AI 관련 링크들을 모두 보여주세요.",
    "과학 대분류 아래에 있는 링크 중 AI 태그가 붙은 것들을 찾아주세요.",
    "각 대분류별로 저장된 링크 개수를 알려주세요.",
    # ... linkbrain.py와 동일한 9개 질문
]
```

## 🆕 신기능 하이라이트

### 🔄 실시간 배치 테스트
- **진행 상황 시각화**: 프로그레스 바와 현재 질문 표시
- **실시간 결과 미리보기**: 각 질문의 응답을 즉시 확인
- **에이전트 추적**: 배치 실행에서 사용된 모든 에이전트 기록

### 🎨 고급 UI 컴포넌트
- **Neo4j 상태 인디케이터**: 실시간 연결 상태 표시
- **프롬프트 타입 배지**: Simple vs LinkBrain 시각적 구분
- **에이전트 배지**: 실행에 사용된 에이전트들을 색상으로 표시
- **Cypher 결과 자동 포맷팅**: 표 형식 결과 자동 감지

### ⚡ 성능 최적화
- **비동기 Neo4j 초기화**: 서버 시작 시 백그라운드에서 연결
- **에러 복구**: Neo4j 연결 실패 시 OpenAI 모드로 자동 전환
- **배치 처리 최적화**: 여러 질문을 효율적으로 순차 처리

## 🔮 향후 개선 사항

- [ ] **실시간 Cypher 쿼리 편집기**: 브라우저에서 직접 Neo4j 쿼리 실행
- [ ] **그래프 시각화**: Neo4j 결과를 노드-엣지 그래프로 표시
- [ ] **A/B 테스트 자동화**: 동일 질문에 대한 여러 프롬프트 자동 비교
- [ ] **성능 벤치마크**: linkbrain.py vs 웹 버전 성능 비교 대시보드
- [ ] **프롬프트 자동 최적화**: 실행 결과 기반 프롬프트 개선 제안
- [ ] **팀 협업**: 프롬프트 공유 및 버전 관리 시스템

## 🎨 새로운 UI 특징

### 🌟 Glass Morphism v2.0
- **Neo4j 연결 상태별 색상**: 연결됨(초록) vs 연결안됨(빨강)
- **프롬프트 타입별 테마**: LinkBrain(보라) vs Simple(파랑)
- **에이전트별 색상 코딩**: 각 에이전트를 고유 색상으로 구분

### ⚡ 실시간 상호작용
- **실시간 상태 모니터링**: Neo4j 연결, 배치 진행상황 등
- **즉시 피드백**: 모든 액션에 대한 즉각적인 UI 반응
- **스마트 추천**: 프롬프트 타입에 따른 실행 방식 자동 제안

---

**Made with ❤️ inspired by linkbrain.py v2.0**

linkbrain.py의 모든 기능을 웹으로 완벽 이식하고, 더 나은 사용자 경험을 제공하는 고급 프롬프트 엔지니어링 플랫폼! 🚀 