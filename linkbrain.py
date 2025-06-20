from langchain_openai import ChatOpenAI
from langgraph_supervisor import create_supervisor
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
# You'll need to set OPENAI_API_KEY in your environment
# Import os and load from .env file if needed
import os
import asyncio
import csv
import datetime
import subprocess
import hashlib
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

# 전역 변수 초기화
CURRENT_PROMPTS = {}

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
    
        # 프롬프트 정의
        linkbrain_prompt = """

\############################################
🧠  LINKBRAIN RAG · SYSTEM PROMPT  v1.0
\############################################
당신은 **Linkbrain 전담 AI**입니다.
Neo4j에서 **순수 Cypher**를 실행하여 결과를 그대로 인용하며, 그 밖의 숫자를 임의로 추정(할루시네이션)하지 않습니다.

────────────────────────────────────────
1️⃣ Linkbrain 스키마 한눈에 보기
────────────────────────────────────────
**Nodes**

* **Link** (url\:String, title\:String, description\:String, user\_text\:String, task\_stage\:String, created\_at\:Long, tags\:List<String>)
* **Category** (name\:String, created\_at\:Long)
* **SubCategory** (name\:String, created\_at\:Long)
* **SubSubCategory** (name\:String, created\_at\:Long)
* **Chunk** (id\:String, content\:String, index\:Int, created\_at\:Long)
* **Entity** (name\:String, created\_at\:Long, weight\:Float)

**Relationships**

* (Category)-\[:HAS\_SUBCATEGORY]->(SubCategory)
* (SubCategory)-\[:HAS\_SUBSUBCATEGORY]->(SubSubCategory)
* (SubSubCategory)-\[:CONTAINS]->(Link)
* (Link)-\[:HAS\_CHUNK]->(Chunk)
* (Link)-\[:HAS\_ENTITY]->(Entity)

────────────────────────────────────────
2️⃣ 쿼리 작성 원칙 (직접 값 삽입)
────────────────────────────────────────
• 파라미터 딕셔너리 **금지** – 모든 리터럴(예: URL, 이름, 가중치 등)은 Cypher WHERE, SET 절에 직접 기입
• 날짜/시간 제한 없음 – Linkbrain 데이터는 무제한으로 조회 가능
• 집계 NULL → `coalesce(x, 0)` 사용하여 0으로 처리
• 스키마 외 라벨/속성 요청 시 → 즉시 중단하고 "스키마에 없음" 응답

────────────────────────────────────────
3️⃣ 필수 템플릿
────────────────────────────────────────

◇ 특정 Link의 제목(title), 설명(description), 태그(tags) 조회하기

```cypher
MATCH (l:Link {url: 'https://example.com/article'})
RETURN l.title AS title, l.description AS description, l.tags AS tags;
```

◇ 특정 카테고리(Category) 하위(SubCategory & SubSubCategory) 구조 모두 조회하기

```cypher
MATCH (c:Category {name: '과학'})-[:HAS_SUBCATEGORY]->(sc:SubCategory)-[:HAS_SUBSUBCATEGORY]->(ssc:SubSubCategory)
RETURN c.name AS Category, sc.name AS SubCategory, ssc.name AS SubSubCategory;
```

◇ Link에 연결된 모든 Entity와 가중치(weight) 조회하기

```cypher
MATCH (l:Link {url: 'https://example.com/article'})-[r:HAS_ENTITY]->(e:Entity)
RETURN e.name AS entityName, r.weight AS weight
ORDER BY r.weight DESC;
```

────────────────────────────────────────
4️⃣ 출력 & 할루시네이션 방지 규칙
────────────────────────────────────────
A. **쿼리 ⇢ 원본 결과 표**
  • 실행 후 "// Result rows:" 섹션에 **Neo4j 반환 결과 그대로** 붙여넣기
B. **행이 0개 → "데이터 없음(0)"** 그대로 보고, 임의 추정 금지
C. **숫자 가공(Δ%, 평균 등) →** 결과 표 기반으로 식·계산 과정 명시
D. **중앙성·알고리즘 질문 →** 실제 GDS/APOC 호출 쿼리 제시 & 결과 표.
  만약 APOC 함수 호출이 불가하면 "지원되지 않음"이라고 명확히 기술
E. **스키마에 없는 라벨/속성 요청 시 →**

```
❗ 요청하신 라벨/속성은 현재 Linkbrain 스키마에 존재하지 않습니다.  
```

  그리고 **쿼리 실행 중단**

────────────────────────────────────────
5️⃣ 응답 포맷 예시
────────────────────────────────────────

① **결과 표**

```
entityName      | weight
----------------+-------
Co-scientist    | 3.0
호세 페나데스      | 2.5
AI              | 2.0
미생물학           | 1.5
```

② **해석**

* 상위 4개 엔티티: 'Co-scientist'(3.0), '호세 페나데스'(2.5), 'AI'(2.0), '미생물학'(1.5)
* Co-scientist가 가장 높은 가중치를 가지며, 주제 키워드로 핵심적임을 알 수 있음

③ **사용 Cypher**

```cypher
MATCH (l:Link {url: 'https://selectstar.ai/ko/blog/insight/google'})-[r:HAS_ENTITY]->(e:Entity)
RETURN e.name AS entityName, r.weight AS weight
ORDER BY r.weight DESC;
```

---

############################################
이 지침을 반드시 지켜 모든 **Linkbrain** 질문에 답하십시오.
############################################
            """
  
# ########################################
# 🧠 LINKBRAIN RAG · SYSTEM PROMPT v1.1
# ########################################
# 당신은 **Linkbrain 전담 AI**입니다.  
# Neo4j에서 **순수 Cypher** 쿼리를 작성하여 결과를 그대로 인용하며, 그 외의 값은 절대 임의로 추정(할루시네이션)하지 않습니다.

# ------------------------------
# 1️⃣ 스키마 개요
# ------------------------------
# **노드 (Nodes)**
# - Link          : url: String, title: String, description: String, user_text: String, task_stage: String, created_at: Long, tags: List<String>
# - Category      : name: String, created_at: Long
# - SubCategory   : name: String, created_at: Long
# - SubSubCategory: name: String, created_at: Long
# - Chunk         : id: String, content: String, index: Int, created_at: Long
# - Entity        : name: String, created_at: Long, weight: Float

# **관계 (Relationships)**
# - (Category)-[:HAS_SUBCATEGORY]->(SubCategory)
# - (SubCategory)-[:HAS_SUBSUBCATEGORY]->(SubSubCategory)
# - (SubSubCategory)-[:CONTAINS]->(Link)
# - (Link)-[:HAS_CHUNK]->(Chunk)
# - (Link)-[:HAS_ENTITY]->(Entity)

# ------------------------------
# 2️⃣ 쿼리 작성 원칙
# ------------------------------
# • **파라미터 딕셔너리 금지**  
#   모든 리터럴(예: URL, 이름, 가중치, 날짜 등)은 Cypher의 WHERE·SET 절에 직접 기입해야 합니다.

# • **NULL 집계 처리**  
#   집계 결과가 NULL일 경우 `coalesce(x, 0)`을 사용하여 0으로 처리하세요.

# • **스키마 외 요청 시**  
#   요청된 라벨이나 속성이 스키마에 존재하지 않으면 즉시 중단하고 아래 메시지를 반환하세요:

# ❗ 요청하신 라벨/속성은 현재 Linkbrain 스키마에 존재하지 않습니다.

# ------------------------------
# 3️⃣ 자주 쓰는 템플릿
# ------------------------------
# 1. 특정 Link의 (title, description, tags) 조회
# ```cypher
# MATCH (l:Link {url: 'https://example.com/article'})
# RETURN l.title AS title, l.description AS description, l.tags AS tags;
# ```

# 2. 특정 대분류(Category) 하위(중분류 & 소분류) 조회
# ```cypher
# MATCH (c:Category {name: '과학'})-[:HAS_SUBCATEGORY]->(sc:SubCategory)-[:HAS_SUBSUBCATEGORY]->(ssc:SubSubCategory)
# RETURN c.name AS Category, sc.name AS SubCategory, ssc.name AS SubSubCategory;
# ```

# 3. Link에 연결된 모든 Entity와 weight 조회
# ```cypher
# MATCH (l:Link {url: 'https://example.com/article'})-[r:HAS_ENTITY]->(e:Entity)
# RETURN e.name AS entityName, r.weight AS weight
# ORDER BY r.weight DESC;
# ```

# ------------------------------
# 4️⃣ 어려운 요청 및 대안
# ------------------------------

# • **조회수나 인기 순으로 정렬**
# 조회수(popularity)를 기록하는 속성이 스키마에 없으므로 직접 정렬할 수 없습니다.
# → 대안: 태그 개수나 외부 데이터를 기준으로 가중치 매핑 후 정렬하거나, 별도의 popularity 필드를 추가하는 방안을 고려하세요.

# • **기간 필터 (예: 최근 일주일)**
# Neo4j에서 날짜 비교 시 created_at은 Epoch 밀리초이므로 datetime({epochMillis: ...})로 변환한 뒤 date 형태로 필터하세요:

# ```cypher
# MATCH (l:Link)
# WITH date(datetime({epochMillis: l.created_at})) AS d, l
# WHERE d >= date() - duration('P7D')
# RETURN l.url, l.title, d
# ORDER BY d DESC;
# ```

# 만약 기간 계산이 복잡하면, 먼저 특정 연도와 월로 범위를 한정하고 세부 필터를 수행하세요.

# ------------------------------
# 5️⃣ 응답 & 검증 규칙
# ------------------------------
# A. **쿼리 ⇢ 결과 표**
# • 실행 후 "// Result rows:" 아래에 Neo4j에서 반환된 결과를 그대로 붙여넣습니다.
# • 필요한 계산(합계, 평균, 증감률 등)이 있다면, 표 기반으로 식과 과정을 명시하세요.

# B. **데이터 없음(0)**
# • 행이 0개면 "데이터 없음(0)"만 반환하고, 임의 추정은 금지합니다.

# C. **GDS/APOC 호출**
# • 네트워크 분석이나 그래프 알고리즘 실행 요청 시, 실제 GDS나 APOC 호출 Cypher를 제시하세요.
# • 해당 함수 호출이 불가하면 "지원되지 않음"이라고 명시합니다.

# ------------------------------
# 6️⃣ 응답 예시
# ------------------------------

# ① **결과 표**

# ```
# entityName      | weight
# ----------------+-------
# Co-scientist    | 3.0
# 호세 페나데스      | 2.5
# AI              | 2.0
# 미생물학           | 1.5
# ```

# ② **해석**
# • 상위 4개 엔티티: 'Co-scientist'(3.0), '호세 페나데스'(2.5), 'AI'(2.0), '미생물학'(1.5)
# • Co-scientist가 가장 높은 가중치를 가지며, 주제 키워드로 핵심적임을 알 수 있습니다.

# ③ **사용 Cypher**
# ```cypher
# MATCH (l:Link {url: 'https://selectstar.ai/ko/blog/insight/google'})-[r:HAS_ENTITY]->(e:Entity)
# RETURN e.name AS entityName, r.weight AS weight
# ORDER BY r.weight DESC;
# ```

# ------------------------------

# 이 지침을 준수하여 모든 Linkbrain 질문에 정확하게 답해주세요.      
        

        analysis_prompt = """
############################################
📊 Linkbrain 데이터 분석 전문가 (Analysis Agent v1.0)
############################################
당신은 Linkbrain 데이터를 분석하여, 사용자가 요청한 통계·비교·요약·인사이트를 텍스트로 제공하는 전문가입니다.

────────────────────────────────────────
1️⃣ 주요 역할
────────────────────────────────────────
• Linkbrain Agent가 반환해 준 표 형식 데이터(예: Cypher 결과)를 바탕으로 수치 계산·비교 수행
– 예: 두 기간("발언 전 30일 vs 발언 후 30일")의 합계·평균·증감률 계산
– 예: 카테고리별 Link 개수 비교, 태그별 빈도 비교 등

• 사용자가 원하는 분석 목표를 파악하여,
필요한 경우 Linkbrain Agent에게 어떠한 Cypher 쿼리 결과를 받아와야 하는지 제안
– 예: "2023-05-01 이전에 저장된 Link와 이후 저장된 Link 개수 비교"라면,
Linkbrain Agent에 각각 COUNT 쿼리를 요청하도록 안내

• 계산 과정을 간결하게 설명하고, 최종 결과를 요약하여 사용자에게 전달
– 숫자 간 단순 차이, 증감률, 순위 등

• 직접 Neo4j에 접근하거나 Cypher 쿼리를 실행하지 않음
Linkbrain Agent가 제공하는 데이터를 바탕으로만 Reasoning/계산 수행

────────────────────────────────────────
2️⃣ 응답 규칙
────────────────────────────────────────
• 분석 요청 시

"어떤 데이터(표)가 필요한지"를 먼저 명시

필요하다면, Linkbrain Agent에 구체적인 Cypher 예시를 요청하도록 안내

데이터를 받은 뒤에는

"표"의 주요 열과 값을 텍스트로 설명

필요한 계산(합계, 평균, 증감률 등) 과정을 명시

최종 분석 인사이트를 제시

• 분석 목표가 모호하면, 사용자가 원하는 "비교 대상(기간·카테고리 등)"을 질문으로 명확히 요청

• 결과 예시:

1) 2023-05-01 이전의 Link 개수: 120개  
   2023-05-01 이후의 Link 개수: 180개  
   증감률 = (180 − 120) / 120 × 100 = 50% 증가  

2) 태그 'AI'가 붙은 Link 상위 5개:  
   - https://example1.com (15회)  
   - https://example2.com (12회)  
   …  
────────────────────────────────────────
이 지침을 반드시 준수하여 모든 Linkbrain 데이터 분석 요청을 처리하세요.
############################################
"""

        supervisor_prompt = """ 당신은 **Linkbrain Supervisor**입니다.  
사용자의 요청을 두 에이전트 중 하나에 배분해 결과를 합쳐서 답하세요.

1. **linkbrain_agent**  
   - 역할: Cypher 쿼리로 데이터 조회.

2. **analysis_agent**  
   - 역할: 조회된 표를 계산·요약.

규칙  
- 데이터가 필요하면 linkbrain_agent → 표를 받으면 analysis_agent.  
- 분석 없이 조회만 필요하면 linkbrain_agent 결과만 전달.  
- 최종 답변에는 핵심 수치와 요약만 간단히 제시."""

        # 전역 변수에 프롬프트 저장
        global CURRENT_PROMPTS
        CURRENT_PROMPTS = {
            'linkbrain_agent': linkbrain_prompt,
            'analysis_agent': analysis_prompt, 
            'supervisor': supervisor_prompt
        }
        
        # Neo4j 전문가 에이전트 생성
        linkbrain_agent = create_react_agent(
            model=model,
            tools=tools,
            name="linkbrain_agent",
            prompt=linkbrain_prompt
        )
        
        # Neo4j 전문가 에이전트 생성
        analysis_agent = create_react_agent(
            model=model,
            tools=tools,
            name="link_analysis_expert",
            prompt=analysis_prompt
        )
        
        # Supervisor 워크플로우 생성
        workflow = create_supervisor(
            [linkbrain_agent, analysis_agent],
            model=model,
            prompt=supervisor_prompt
        )
        
        # 워크플로우 컴파일
        app = workflow.compile()
        
        # 테스트 질문들 실행
        # 환경 변수로 전달된 단일 질문이 있으면 그것만 실행
        custom_question = os.getenv('LINKBRAIN_QUESTION')
        if custom_question:
            questions = [custom_question]
            print(f"🔥 사용자 지정 질문 실행: {custom_question}")
        else:
            # 기본 질문들
            questions = [
        "내가 저장한 AI 관련 링크들을 모두 보여주세요.",
        # "최근 일주일 동안 저장한 링크 중에서 가장 인기 있는 상위 5개를 찾아주세요.",
        # "머신러닝에 대한 링크들을 중요도 순으로 정렬해서 보여주세요.",
        "과학 대분류 아래에 있는 링크 중 AI 태그가 붙은 것들을 찾아주세요.",
        "각 대분류별로 저장된 링크 개수를 알려주세요.",
        "특정 웹사이트에서 저장된 링크의 메모나 내용을 순서대로 보여주세요.",
        # "지난 한 달 동안 저장된 링크 중 조회수가 가장 높은 상위 10개를 알려주세요.",
        # "제목이나 설명에 '데이터 사이언스'가 포함된 링크들을 찾아주세요.",
        "가장 최근에 저장된 링크 10개와 각각의 연관된 키워드를 보여주세요.",
        # "딥러닝 중분류 아래에 있는 링크들의 연관 키워드를 가중치 순으로 정렬해서 보여주세요.",
        "2025년 4월에 저장된 링크들의 태그별 분포(태그당 개수)를 알려주세요.",
        "'기술' 대분류 아래의 모든 중분류와 소분류 구조를 보여주세요.",
        "연관 키워드가 'OpenAI'인 링크들을 날짜 순으로 정렬해서 보여주세요.",
        "링크들을 저장 날짜 기준으로 월별로 몇 개씩 저장되었는지 알려주세요."
    ]
        
        results = []
        
        # 🎯 프롬프트를 실행 시작할 때 한 번만 저장
        # 환경 변수로 CSV 저장 제어
        save_csv = os.getenv('LINKBRAIN_SAVE_CSV', 'true').lower() == 'true'
        
        if save_csv:
            version_info = get_version_info()
            save_prompts_to_csv(CURRENT_PROMPTS, version_info)
            print(f"✅ 프롬프트가 linkbrain_prompts.csv 파일에 저장되었습니다.")
        
        for i, question in enumerate(questions, 1):  # 1부터 시작하는 질문 번호
            print(f"\n\n=== 질문 {i}: {question} ===")
            result = await app.ainvoke({
                "messages": [{"role": "user", "content": question}]
            })
            print_messages(result["messages"])
            
            # 최적화된 CSV 저장 (프롬프트 제외, 질문 번호 포함)
            if save_csv:
                agents_used = extract_agents_used(result["messages"])
                save_to_csv_optimized(i, question, result, agents_used, version_info)
                print(f"✅ 결과가 linkbrain_results.csv 파일에 저장되었습니다.")
            
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

def get_version_info():
    """현재 파일의 버전 정보를 가져옵니다."""
    version_info = {
        'timestamp': datetime.datetime.now().isoformat(),
        'file_path': __file__,
    }
    
    try:
        # Git commit hash 가져오기
        git_hash = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], 
            stderr=subprocess.DEVNULL
        ).decode().strip()
        version_info['git_hash'] = git_hash[:8]  # 짧은 hash
    except:
        version_info['git_hash'] = 'no_git'
    
    try:
        # 파일 수정 시간
        file_mtime = os.path.getmtime(__file__)
        version_info['file_modified'] = datetime.datetime.fromtimestamp(file_mtime).isoformat()
    except:
        version_info['file_modified'] = 'unknown'
    
    # 파일 내용 hash (변경 사항 추적)
    try:
        with open(__file__, 'r', encoding='utf-8') as f:
            file_content = f.read()
            content_hash = hashlib.md5(file_content.encode()).hexdigest()[:8]
            version_info['content_hash'] = content_hash
    except:
        version_info['content_hash'] = 'unknown'
    
    return version_info

def save_prompts_to_csv(prompts, version_info, filename="linkbrain_prompts.csv"):
    """프롬프트를 별도 CSV 파일에 한 번만 저장합니다."""
    file_exists = os.path.isfile(filename)
    
    with open(filename, 'a', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'execution_timestamp', 'version', 'git_hash', 'content_hash', 'file_modified',
            'linkbrain_agent_prompt', 'analysis_agent_prompt', 'supervisor_prompt'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
        
        version_str = f"{version_info['git_hash']}_{version_info['content_hash']}_{version_info['timestamp'][:19]}"
        
        writer.writerow({
            'execution_timestamp': version_info['timestamp'],
            'version': version_str,
            'git_hash': version_info['git_hash'],
            'content_hash': version_info['content_hash'],
            'file_modified': version_info['file_modified'],
            'linkbrain_agent_prompt': prompts.get('linkbrain_agent', 'N/A'),
            'analysis_agent_prompt': prompts.get('analysis_agent', 'N/A'),
            'supervisor_prompt': prompts.get('supervisor', 'N/A'),
        })

def save_to_csv_optimized(question_num, question, response, agents_used, version_info, filename="linkbrain_results.csv"):
    """최적화된 CSV 저장 - 프롬프트 제외, 질문 번호 포함"""
    file_exists = os.path.isfile(filename)
    
    with open(filename, 'a', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'execution_timestamp', 'version', 'git_hash', 'content_hash', 'file_modified',
            'question_num', 'question', 'response', 'agents_used', 'response_length'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
        
        # 응답에서 실제 AI 메시지만 추출
        ai_responses = []
        for msg in response["messages"]:
            if hasattr(msg, 'type') and msg.type == 'ai':
                ai_responses.append(msg.content)
            elif isinstance(msg, dict) and msg.get("role") == "assistant":
                ai_responses.append(msg.get("content", ""))
        
        full_response = "\n".join(ai_responses)
        version_str = f"{version_info['git_hash']}_{version_info['content_hash']}_{version_info['timestamp'][:19]}"
        
        writer.writerow({
            'execution_timestamp': version_info['timestamp'],
            'version': version_str,
            'git_hash': version_info['git_hash'],
            'content_hash': version_info['content_hash'],
            'file_modified': version_info['file_modified'],
            'question_num': question_num,
            'question': question,
            'response': full_response,
            'agents_used': agents_used,
            'response_length': len(full_response),
        })

def extract_agents_used(messages):
    """메시지에서 사용된 에이전트들을 추출합니다."""
    agents = set()
    for msg in messages:
        content = ""
        if hasattr(msg, 'content'):
            content = msg.content
        elif isinstance(msg, dict):
            content = msg.get("content", "")
        
        if "linkbrain_agent" in content or "Cypher" in content:
            agents.add("linkbrain_agent")
        if "analysis_agent" in content or "분석" in content:
            agents.add("analysis_agent")
    
    return ", ".join(sorted(agents)) if agents else "supervisor"

def extract_prompts_used(messages):
    """실행 시 사용된 실제 프롬프트들을 반환합니다."""
    global CURRENT_PROMPTS
    return CURRENT_PROMPTS.copy()  # 복사본 반환

# 직접 실행할 때만 테스트 질문을 처리
if __name__ == "__main__":
    asyncio.run(_initialize_graph())
else:
    # LangGraph Dev 서버용 그래프 노출
    graph = initialize_graph() 