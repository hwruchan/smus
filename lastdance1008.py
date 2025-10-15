from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts import base
import os
import pandas as pd
import pymysql
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pymysql.cursors import DictCursor

# ---- DB 설정 (가능하면 환경변수로 관리 권장) ----
DB_HOST = os.getenv("DB_HOST", "oneteam-db.chigywqq0qt3.ap-northeast-2.rds.amazonaws.com")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Oneteam2025!")
DB_NAME = os.getenv("DB_NAME", "oneteam_DB")
DB_PORT = int(os.getenv("DB_PORT", "3306"))

def _query_meals_by_date_category(date_iso: str, category: str) -> list[dict]:
    """
    내부 헬퍼: YYYY-MM-DD(iso) 날짜와 카테고리(breakfast/lunch/dinner)로 smu_meals 조회
    - date 컬럼이 DATE/DATETIME이거나 문자열(텍스트)인 경우 모두 대응
    """
    conn = pymysql.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, port=DB_PORT, cursorclass=DictCursor, charset="utf8mb4"
    )
    try:
        with conn.cursor() as cur:
            # DATE 타입이면 DATE(`date`) = %s 로 맞음
            # 문자열일 가능성도 있어 COALESCE(STR_TO_DATE(...)) 로 보조
            sql = """
                SELECT *
                FROM smu_meals
                WHERE LOWER(category) = LOWER(%s)
                  AND (
                        DATE(`date`) = %s
                     OR COALESCE(
                            STR_TO_DATE(`date`, '%%Y-%%m-%%d'),
                            STR_TO_DATE(`date`, '%%Y.%%m.%%d'),
                            STR_TO_DATE(`date`, '%%Y/%%m/%%d')
                        ) = %s
                  )
                ORDER BY `date` ASC
            """
            cur.execute(sql, (category, date_iso, date_iso))
            rows = cur.fetchall()
            return rows
    finally:
        conn.close()

# FastMCP 서버
mcp = FastMCP("smuchat")

@mcp.tool()
def now_kr() -> dict:
    """Return current date/time info in Asia/Seoul (KST, UTC+9)."""
    tz = ZoneInfo("Asia/Seoul")
    dt = datetime.now(tz)
    return {
        "iso": dt.isoformat(),
        "date": dt.strftime("%Y-%m-%d"),
        "time": dt.strftime("%H:%M:%S"),
        "weekday": dt.strftime("%A"),
        "tz": "Asia/Seoul (KST, UTC+9)",
    }

@mcp.tool()
def query_smu_meals_by_date_category(date_iso: str, category: str = "lunch") -> dict:
    """
    YYYY-MM-DD 날짜와 카테고리로 smu_meals를 조회한다.
    Args:
        date_iso: '2025-08-27' 같은 ISO 날짜 문자열
        category: 'breakfast' | 'lunch' | 'dinner'
    Returns:
        dict: 레코드 리스트
    """
    rows = _query_meals_by_date_category(date_iso, category)
    return rows  # 이미 list[dict]

@mcp.tool()
def today_lunch() -> dict:
    """
    편의 도구: Asia/Seoul 기준 '오늘' + category='lunch'로 smu_meals 조회
    """
    tz = ZoneInfo("Asia/Seoul")
    today_iso = datetime.now(tz).strftime("%Y-%m-%d")
    rows = _query_meals_by_date_category(today_iso, "lunch")
    return rows

# (기존) 키워드 검색 도구가 필요하면 이 버전처럼 안전하게 수정
@mcp.tool()
def query_smu_meals_by_keyword(keyword: str) -> dict:
    """
    'meal' 텍스트 등에서 키워드 검색 (보조 용도)
    """
    conn = pymysql.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, port=DB_PORT, cursorclass=DictCursor, charset="utf8mb4"
    )
    try:
        with conn.cursor() as cur:
            sql = "SELECT * FROM smu_meals WHERE meal LIKE %s"
            cur.execute(sql, (f"%{keyword}%",))
            return cur.fetchall()
    finally:
        conn.close()

@mcp.tool()
def query_smu_notices_by_keyword(keyword: str) -> dict:
    """
    'smu_notices' 테이블에서 'title' 컬럼에 특정 키워드를 포함하는 행을 조회하여 결과를 반환하는 도구.
    
    Args:
        keyword (str): 'title' 컬럼에서 찾을 키워드.
        
        dict: 키워드가 포함된 'title' 컬럼을 가진 행들 반환.
    """

    # MySQL 연결
    conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT
        )
    cursor = conn.cursor()

        # 쿼리 작성: 'title' 컬럼에서 키워드를 포함하는 행을 찾는 쿼리
    query = f"SELECT * FROM smu_notices WHERE title LIKE %s"
    cursor.execute(query, ('%' + keyword + '%',))
        
        # 결과를 DataFrame으로 변환
    data = cursor.fetchall()
    column_names = [desc[0] for desc in cursor.description]
    df = pd.DataFrame(data, columns=column_names)

        # 결과 반환
    return df.to_dict(orient='records')
    
@mcp.tool()
def query_smu_exam_by_subject(keyword: str) -> dict:
    """
    'smu_exam' 테이블에서 'subject_name' 컬럼에 `keyword`를 포함하는 행을 조회해 반환.
    - 부분일치 검색: LIKE %keyword%
    - 반환: list[dict]
    """
    conn = pymysql.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, port=DB_PORT,
        cursorclass=DictCursor, charset="utf8mb4"
    )
    try:
        with conn.cursor() as cur:
            sql = """
                SELECT *
                FROM smu_exam
                WHERE subject_name IS NOT NULL
                  AND subject_name LIKE %s
                ORDER BY subject_name ASC
            """
            cur.execute(sql, (f"%{keyword}%",))
            return cur.fetchall()
    finally:
        conn.close()
        
# ---- 기본 프롬프트(어제/내일 계산 버그 수정) ----
@mcp.prompt()
def default_prompt(message: str) -> list[base.Message]:
    tz = ZoneInfo("Asia/Seoul")
    now = datetime.now(tz)
    today_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    weekday_str = now.strftime("%A")
    yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    return [
        base.AssistantMessage(
            "You are a smart agent with an ability to use tools.\n"
            "If you don't have any tools to use for what the user asked, please think and judge for yourself and answer.\n"
            "Before answering any question that depends on dates or times, call the `now_kr` tool to confirm the current date/time in Asia/Seoul.\n"
            "When reasoning about any dates or times, you MUST anchor to the following clock:\n"
            f"- Today: {today_str} ({weekday_str}), Current time: {time_str}, Timezone: Asia/Seoul (KST, UTC+9).\n"
            "Interpret relative terms strictly as:\n"
            f"- 'today/오늘' = {today_str}\n"
            f"- 'yesterday/어제' = {yesterday_str}\n"
            f"- 'tomorrow/내일' = {tomorrow_str}\n"
            "If the user asks for SMU meals for today or a specific date, prefer:\n"
            "1) Call `now_kr` (get date)\n"
            "2) Then call `query_smu_meals_by_date_category(date_iso, category)`\n"
            "When data includes URLs, always include them in the answer."
        ),
        base.UserMessage(message),
    ]

if __name__ == "__main__":
    mcp.run(transport="stdio")
