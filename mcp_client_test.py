
"""
MCP(config.json) → MultiServerMCPClient → LangGraph ReAct Agent
로컬 CSV·Notion 등 모든 툴을 LLM-ReAct 루프에서 직접 호출합니다.
"""
import asyncio, json, os, sys, traceback
from dotenv import load_dotenv

from langchain_openai           import ChatOpenAI
from langchain_core.messages    import SystemMessage, HumanMessage
from langgraph.prebuilt         import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

# ── 환경 변수 ──────────────────────────────────────────────────
load_dotenv()
if not os.getenv("OPENAI_API_KEY"):
    print("💥 OPENAI_API_KEY 가 설정되지 않았습니다"); sys.exit(1)

# ── 설정 -----------------------------------------------------------------
CONFIG_FILE   = "config.json"

SYSTEM_PROMPT = """<ROLE>
You are a smart agent with an ability to use tools. 
You will be given a question and you will use the tools to answer the question.
Pick the most relevant tool to answer the question. 
If you are failed to answer the question, try different tools to get context.
Your answer should be very polite and professional.
Tools run on the same machine and CAN read local file paths
</ROLE>

----

<INSTRUCTIONS>
Step 1: Analyze the question
- Analyze user's question and final goal.
- If the user's question is consist of multiple sub-questions, split them into smaller sub-questions.

Step 2: Pick the most relevant tool
- Pick the most relevant tool to answer the question.
- If you are failed to answer the question, try different tools to get context.

Step 3: Answer the question
- Answer the question in the same language as the question.
- Your answer should be very polite and professional.

Step 4: Provide the source of the answer(if applicable)
- If you've used the tool, provide the source of the answer.
- Valid sources are either a website(URL) or a document(PDF, etc).

Guidelines:
- If you've used the tool, your answer should be based on the tool's output(tool's output is more important than your own knowledge).
- If you've used the tool, and the source is valid URL, provide the source(URL) of the answer.
- Skip providing the source if the source is not URL.
- Answer in the same language as the question.
- Answer should be concise and to the point.
- Avoid response your output with any other information than the answer and the source.  
- Always consider variations of spacing when interpreting keywords. Treat joined words and separated words as equivalent (e.g., 'lunchmenu' and 'lunch menu', '점심메뉴' and '점심 메뉴'). Automatically account for both forms when extracting or matching keywords.

</INSTRUCTIONS>

----

<OUTPUT_FORMAT>
(concise answer to the question)

**Source**(if applicable)
- (source1: valid URL)
- (source2: valid URL)
- ...
</OUTPUT_FORMAT>
"""

# ── config.json 로드 ────────────────────────────────────────────
def load_config() -> dict:
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️ {CONFIG_FILE} 가 없습니다."); return {}
    except Exception as e:
        print("config.json 로드 오류:", e); return {}

# ── 메인 async 루프 ─────────────────────────────────────────────
async def main():
    cfg = load_config()
    if not cfg:
        print("🚫 연결할 MCP 서버가 없습니다."); return
    client = MultiServerMCPClient(cfg)
    try:
        # 1) MCP 클라이언트 / 툴 로드
        
            tools = await client.get_tools()
            print(f"🔗 MCP 서버 {len(cfg)} 개, 로드된 툴 {len(tools)} 개")

            # 2) LLM & 에이전트
            model  = ChatOpenAI(model="gpt-4o", temperature=0.1)
            agent  = create_react_agent(
                model,
                tools,
                prompt=SYSTEM_PROMPT,
                verbose=True      # Thought / Action / Observation & JSON 인자 출력
            )

            # 3) 대화 히스토리
            history = [SystemMessage(content=SYSTEM_PROMPT)]

            # 4) 콘솔 입력 루프
            print("💬 무엇이든 물어보세요. (exit / quit 로 종료)")
            while True:
                try:
                    q = input("질문> ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if q.lower() in {"exit", "quit"}:
                    break
                if not q:
                    continue

                history.append(HumanMessage(content=q))
                try:
                    result  = await agent.ainvoke({"messages": history})
                    answer  = result["messages"][-1].content
                    print("\n🤖", answer, "\n")
                    history.append(result["messages"][-1])
                except Exception as e:
                    print("⚠️ 오류:", e)
                    traceback.print_exc()

    finally:
        await client.aclose()
    

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass