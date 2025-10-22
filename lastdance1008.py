from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts import base
import os
import pandas as pd
import pymysql
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pymysql.cursors import DictCursor
from typing import Optional

# ---- DB 설정 (가능하면 환경변수로 관리 권장) ----
# Smithery에서 URL 파라미터로 전달되는 설정을 환경변수로 변환
def get_db_config():
    """Smithery 설정을 환경변수에서 읽어오는 함수"""
    return {
        "host": os.getenv("DB_HOST", "oneteam-db.chigywqq0qt3.ap-northeast-2.rds.amazonaws.com"),
        "user": os.getenv("DB_USER", "admin"),
        "password": os.getenv("DB_PASSWORD", "Oneteam2025!"),
        "database": os.getenv("DB_NAME", "oneteam_DB"),
        "port": int(os.getenv("DB_PORT", "3306"))
    }

# 전역 DB 설정
DB_CONFIG = get_db_config()
DB_HOST = DB_CONFIG["host"]
DB_USER = DB_CONFIG["user"]
DB_PASSWORD = DB_CONFIG["password"]
DB_NAME = DB_CONFIG["database"]
DB_PORT = DB_CONFIG["port"]

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

# FastMCP 서버 (HTTP/STDIO 겸용)
mcp = FastMCP(name="smus")


KST = ZoneInfo("Asia/Seoul")

def _get_conn():
    host = os.getenv("DB_HOST")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    database = os.getenv("DB_NAME")
    port = int(os.getenv("DB_PORT", "3306"))
    if not all([host, user, password, database]):
        raise RuntimeError("DB env vars not set: DB_HOST/DB_USER/DB_PASSWORD/DB_NAME")
    return pymysql.connect(host=host, user=user, password=password,
                           database=database, port=port, autocommit=True)

def _coerce_to_kst(dt_str: str) -> datetime:
    """
    문자열을 KST datetime으로 엄격 변환.
    허용 예: '2025-10-21', '2025-10-21 13:30', '2025-10-21T13:30:00'
    (날짜만 오면 00:00:00으로 보정)
    """
    s = dt_str.strip()
    # ISO-like
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        # tz 없는 경우 KST 부여, tz 있는 경우 KST로 변환
        if dt.tzinfo is None:
            return dt.replace(tzinfo=KST)
        return dt.astimezone(KST)
    except Exception:
        pass

    # 'YYYY-MM-DD HH:MM'
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            if fmt == "%Y-%m-%d":
                dt = dt.replace(hour=0, minute=0, second=0)
            return dt.replace(tzinfo=KST)
        except Exception:
            continue

    raise ValueError(f"Invalid datetime format: {dt_str}. Use 'YYYY-MM-DD' or ISO-like strings.")



    
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
    sql = f"SELECT * FROM smu_notices WHERE title LIKE %s"
    cursor.execute(sql, (f"%{keyword}%",))
        
    return cursor.fetchall()
    
@mcp.tool()
def query_smu_exam(keyword: str, professor: str | None = None) -> list[dict]:
    """
    smu_exam 테이블에서 subject_name, professor 조건을 조합해 검색.
    - professor 인자가 주어지면 AND 조건으로 subject_name + professor 검색
    - professor가 없으면 subject_name만 검색
    - 반환: list[dict]
    """
    conn = pymysql.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, port=DB_PORT,
        cursorclass=DictCursor, charset="utf8mb4"
    )
    try:
        with conn.cursor() as cur:
            if professor:
                sql = """
                    SELECT *
                    FROM smu_exam
                    WHERE subject_name IS NOT NULL
                      AND subject_name LIKE %s
                      AND professor IS NOT NULL
                      AND professor LIKE %s
                    ORDER BY subject_name ASC
                """
                cur.execute(sql, (f"%{keyword}%", f"%{professor}%"))
            else:
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
        
@mcp.tool()
def query_smu_schedule_by_keyword(keyword: str, user_id: Optional[str] = None) -> list[dict]:
    """
    'smu_schedule' 테이블에서 'content' 컬럼에 특정 키워드를 포함하는 행을 조회하여 결과를 반환하는 도구.
    type에 따라 필터링: 'common'은 모든 사용자에게, 'personal'은 해당 user_id에게만 제공.
    
    Args:
        keyword (str): 'content' 컬럼에서 찾을 키워드.
        user_id (str, optional): student ID (학번). 제공되면 해당 사용자의 개인 일정도 포함.
        
    Returns:
        list[dict]: 키워드가 포함된 일정들 (type='common' + user_id가 일치하는 type='personal')
    """
    conn = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT,
        cursorclass=DictCursor,
        charset="utf8mb4"
    )
    try:
        with conn.cursor() as cur:
            if user_id:
                # user_id가 있으면: common + 해당 user_id의 personal 일정
                sql = """
                    SELECT * FROM smu_schedule 
                    WHERE content LIKE %s 
                    AND (type = 'common' OR (type = 'personal' AND user_id = %s))
                    ORDER BY start_date ASC
                """
                cur.execute(sql, (f"%{keyword}%", user_id))
            else:
                # user_id가 없으면: common 일정만
                sql = """
                    SELECT * FROM smu_schedule 
                    WHERE content LIKE %s AND type = 'common'
                    ORDER BY start_date ASC
                """
                cur.execute(sql, (f"%{keyword}%",))
            
            return cur.fetchall()
    finally:
        conn.close()

@mcp.tool()
def query_smu_schedule_by_date(date_keyword: str, user_id: Optional[str] = None) -> list[dict]:
    """
    'smu_schedule' 테이블에서 날짜를 키워드로 찾아 해당하는 content를 반환하는 도구.
    start_date 또는 end_date 컬럼에서 날짜를 검색하여 일치하는 스케줄의 content를 반환합니다.
    type에 따라 필터링: 'common'은 모든 사용자에게, 'personal'은 해당 user_id에게만 제공.
    
    Args:
        date_keyword (str): 검색할 날짜 키워드 (예: '2025-10-21', '10-21', '10월 21일' 등)
        user_id (str, optional): student ID (학번). 제공되면 해당 사용자의 개인 일정도 포함.
        
    Returns:
        list[dict]: 날짜와 일치하는 스케줄들 (type='common' + user_id가 일치하는 type='personal')
    """
    conn = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT,
        cursorclass=DictCursor,
        charset="utf8mb4"
    )
    try:
        with conn.cursor() as cur:
            date_pattern = f"%{date_keyword}%"
            
            if user_id:
                # user_id가 있으면: common + 해당 user_id의 personal 일정
                sql = """
                    SELECT id, start_date, end_date, content, type, user_id, created_at
                    FROM smu_schedule 
                    WHERE (DATE(start_date) LIKE %s 
                       OR DATE(end_date) LIKE %s
                       OR start_date LIKE %s 
                       OR end_date LIKE %s)
                    AND (type = 'common' OR (type = 'personal' AND user_id = %s))
                    ORDER BY start_date ASC
                """
                cur.execute(sql, (date_pattern, date_pattern, date_pattern, date_pattern, user_id))
            else:
                # user_id가 없으면: common 일정만
                sql = """
                    SELECT id, start_date, end_date, content, type, user_id, created_at
                    FROM smu_schedule 
                    WHERE (DATE(start_date) LIKE %s 
                       OR DATE(end_date) LIKE %s
                       OR start_date LIKE %s 
                       OR end_date LIKE %s)
                    AND type = 'common'
                    ORDER BY start_date ASC
                """
                cur.execute(sql, (date_pattern, date_pattern, date_pattern, date_pattern))
            
            return cur.fetchall()
    finally:
        conn.close()

@mcp.tool()
def query_special_keywords(keyword: str) -> dict:
    """
    특정 키워드에 대해 미리 정의된 응답을 반환하는 도구.
    
    Args:
        keyword (str): 사용자가 입력한 키워드.
    
    Returns:
        dict: 미리 정의된 응답.
    """
    responses = {
        "김진석": "군인이 될 사람이다.",
        "맹의현": "잘 먹고 다닐 사람이다.",
        "염다인": "빵집 사장이 될 사람이다.",
        "김재관": "약간 신동엽이나 성시경 같은 사람이다.",
        "김정찬": "해적왕이 될 사람이다."
    }

    return responses[keyword]

@mcp.tool()
def add_smu_schedule_structured(
    start_datetime: str,
    content: str,
    user_id: str,
    end_datetime: Optional[str] = None
) -> dict:
    """
    Insert a schedule row into `smu_schedule` with structured inputs.

    Args:
        start_datetime (str): e.g., '2025-10-21', '2025-10-21 13:30', or ISO-like.
        content (str): schedule text/content.
        user_id (str): student ID (학번). Required parameter.
        end_datetime (str, optional): same formats as start. If omitted, equals start.

    Returns:
        dict: { ok, id, start_date_iso, end_date_iso, content, type, user_id, created_at_iso }
    """
    # 1) Parse/validate datetimes
    start_dt = _coerce_to_kst(start_datetime)
    end_dt = _coerce_to_kst(end_datetime) if end_datetime else start_dt
    if end_dt < start_dt:
        raise ValueError("end_datetime must be equal to or later than start_datetime.")

    created_at = datetime.now(KST)
    
    # 2) Set type and user_id (always personal)
    schedule_type = "personal"
    final_user_id = user_id

    # 3) DB insert
    conn = pymysql.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, port=DB_PORT, cursorclass=DictCursor, charset="utf8mb4"
    )
    try:
        with conn.cursor() as cur:
            sql = """
                INSERT INTO smu_schedule (start_date, end_date, content, type, user_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cur.execute(
                sql,
                (
                    start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    content,
                    schedule_type,
                    final_user_id,
                    created_at.strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            conn.commit()  # autocommit이 없으므로 명시적으로 commit
            inserted_id = cur.lastrowid
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"Failed to insert schedule: {e}")
    finally:
        conn.close()

    return {
        "ok": True,
        "id": inserted_id,
        "start_date_iso": start_dt.isoformat(),
        "end_date_iso": end_dt.isoformat(),
        "content": content,
        "type": schedule_type,
        "user_id": final_user_id,
        "created_at_iso": created_at.isoformat(),
    }


@mcp.tool()
def delete_smu_schedule_by_content(content_keyword: str, user_id: str) -> dict:
    """
    내용 키워드로 개인 일정을 삭제하는 도구. (type='personal'인 일정만 삭제 가능)
    
    Args:
        content_keyword (str): 삭제할 일정의 내용에 포함된 키워드
        user_id (str): student ID (학번). 해당 사용자의 개인 일정만 삭제 가능
        
    Returns:
        dict: { ok, deleted_count, deleted_ids, message }
    """
    conn = pymysql.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, port=DB_PORT, cursorclass=DictCursor, charset="utf8mb4"
    )
    try:
        with conn.cursor() as cur:
            # 먼저 해당 키워드와 일치하는 개인 일정들을 조회 (type='personal'이고 user_id가 일치하는 것만)
            select_sql = """
                SELECT id, content, type, user_id 
                FROM smu_schedule 
                WHERE content LIKE %s AND type = 'personal' AND user_id = %s
            """
            cur.execute(select_sql, (f"%{content_keyword}%", user_id))
            matching_records = cur.fetchall()
            
            if not matching_records:
                return {
                    "ok": False,
                    "deleted_count": 0,
                    "deleted_ids": [],
                    "message": f"No personal schedules found with keyword: {content_keyword} for user_id: {user_id}"
                }
            
            # 개인 일정들만 삭제 (type='personal'이고 user_id가 일치하는 것만)
            delete_sql = """
                DELETE FROM smu_schedule 
                WHERE content LIKE %s AND type = 'personal' AND user_id = %s
            """
            cur.execute(delete_sql, (f"%{content_keyword}%", user_id))
            conn.commit()
            
            deleted_ids = [record['id'] for record in matching_records]
            deleted_contents = [record['content'] for record in matching_records]
            
            return {
                "ok": True,
                "deleted_count": len(deleted_ids),
                "deleted_ids": deleted_ids,
                "message": f"Successfully deleted {len(deleted_ids)} personal schedules: {', '.join(deleted_contents[:3])}{'...' if len(deleted_contents) > 3 else ''}"
            }
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"Failed to delete schedules: {e}")
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
            "Always consider variations of spacing when interpreting keywords. Treat joined words and separated words as equivalent (e.g., 'lunchmenu' and 'lunch menu', '점심메뉴' and '점심 메뉴'). Automatically account for both forms when extracting or matching keywords.\n"
            "When reasoning about any dates or times, you MUST anchor to the following clock:\n"
            f"- Today: {today_str} ({weekday_str}), Current time: {time_str}, Timezone: Asia/Seoul (KST, UTC+9).\n"
            "Interpret relative terms strictly as:\n"
            f"- 'today/오늘' = {today_str}\n"
            f"- 'yesterday/어제' = {yesterday_str}\n"
            f"- 'tomorrow/내일' = {tomorrow_str}\n"
            "If the user asks for SMU meals for today or a specific date, prefer:\n"
            "1) Call `now_kr` (get date)\n"
            "2) Then call `query_smu_meals_by_date_category(date_iso, category)`\n"
            "When data includes URLs, always include them in the answer.\n"
            "Convert the user's natural language into structured inputs for the tool:\n"
            "start_datetime and optional end_datetime must be absolute KST datetimes (YYYY-MM-DD or ISO-like), and content must be a concise title/description. If only one datetime is present, set end_datetime = start_datetime.\n"
            "\n"
            "IMPORTANT: User-specific data handling:\n"
            "- When using MCP tools that query tables containing user_id (학번), extract the user's student ID (학번) from their message or context if available.\n"
            "- For tables like smu_schedule, and other user-specific tables, include the user_id parameter in your queries when available.\n"
            "- If the user mentions their student ID (학번) in their message, use that exact value as user_id.\n"
            "- If no student ID is provided, proceed without user_id - do NOT ask the user to provide their student ID.\n"
            "- For smu_schedule table: Handle data based on 'type' field:\n"
            "  * 'common' type: Provide data to all users regardless of user_id\n"
            "  * 'personal' type: Only provide data when user_id matches the record's user_id\n"
            "  * When user_id is not available, only return 'common' type records\n"
            "- When adding new schedules or personal data, include the user_id if available to ensure proper data association.\n"
            "- Remember: user_id represents the student's 학번 (student ID number) and is used for personal data filtering.\n"
        ),
        base.UserMessage(message),
    ]
if __name__ == "__main__":
    # Smithery Python custom container 가이드에 따라 PORT 사용, streamable-http로 실행
    # 참고: https://smithery.ai/docs/migrations/python-custom-container
    from starlette.middleware.cors import CORSMiddleware
    import uvicorn
    
    app = mcp.streamable_http_app()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["mcp-session-id", "mcp-protocol-version"],
        max_age=86400,
    )
    import os
    port = int(os.environ.get("PORT", 8081))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
