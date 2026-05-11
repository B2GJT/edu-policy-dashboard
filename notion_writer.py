"""
notion_writer.py
분석 결과를 Notion 데이터베이스에 자동 적재
Claude Code에서 실행: python notion_writer.py

사전 준비:
  1. https://www.notion.so/my-integrations 에서 Integration 생성
  2. 생성한 Integration을 대상 DB 페이지에 연결 (Share → Invite)
  3. 환경변수 설정:
       export NOTION_TOKEN="secret_xxxx"
       export NOTION_DATABASE_ID="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
"""

import os
import json
import urllib.request
import urllib.error
from datetime import date
from policy_crawler import run as crawl_and_analyze, load_history


# ── 설정 ─────────────────────────────────────────────────────────────────────

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
NOTION_DB_ID = os.environ.get("NOTION_DATABASE_ID", "")
NOTION_VERSION = "2022-06-28"

# Notion DB 컬럼 구조 (처음 실행 전에 Notion에서 이 컬럼들을 만들어야 함)
# 주차(title) | 수집일(date) | 출처(select) | 정책명(rich_text)
# 핵심키워드(multi_select) | 관련도(select) | 사업기회(rich_text)
# 액션(select) | 인사이트(rich_text) | URL(url)


# ── Notion API 헬퍼 ──────────────────────────────────────────────────────────

def notion_request(method: str, endpoint: str, data: dict = None) -> dict:
    """Notion API 요청 공통 함수"""
    url = f"https://api.notion.com/v1/{endpoint}"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise RuntimeError(f"Notion API 오류 {e.code}: {error_body}")


def check_week_exists(week: str) -> bool:
    """같은 주차 데이터가 이미 있는지 확인 (중복 방지)"""
    result = notion_request("POST", f"databases/{NOTION_DB_ID}/query", {
        "filter": {
            "property": "주차",
            "title": {"equals": week}
        }
    })
    return len(result.get("results", [])) > 0


def add_weekly_summary(result: dict) -> str:
    """주간 요약 행 추가 (상단 요약 레코드)"""
    week = result["week"]
    top_kws = [k["keyword"] for k in result["top_keywords"][:8]]

    page = notion_request("POST", "pages", {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "주차": {
                "title": [{"text": {"content": f"📋 {week} 주간 요약"}}]
            },
            "수집일": {
                "date": {"start": result["collected_date"]}
            },
            "출처": {
                "select": {"name": "전체"}
            },
            "정책명": {
                "rich_text": [{"text": {"content": result["weekly_insight"]}}]
            },
            "핵심키워드": {
                "multi_select": [{"name": kw} for kw in top_kws]
            },
            "관련도": {
                "select": {"name": "요약"}
            },
            "사업기회": {
                "rich_text": [{"text": {"content":
                    "\n".join(f"• {a}" for a in result["recommended_actions"])
                }}]
            },
            "액션": {
                "select": {"name": "즉시검토"}
            },
            "수집건수": {
                "number": result["relevant_count"]
            },
        }
    })
    return page["id"]


def add_policy_row(policy: dict, week: str, collected_date: str) -> str:
    """개별 정책 행 추가"""
    keywords = policy.get("keywords", [])[:8]  # Notion multi_select 최대 권장
    url = policy.get("url", "")

    props = {
        "주차": {
            "title": [{"text": {"content": week}}]
        },
        "수집일": {
            "date": {"start": collected_date}
        },
        "출처": {
            "select": {"name": policy.get("source", "기타")}
        },
        "정책명": {
            "rich_text": [{"text": {"content": policy.get("title", "")[:2000]}}]
        },
        "핵심키워드": {
            "multi_select": [{"name": kw} for kw in keywords]
        },
        "관련도": {
            "select": {"name": policy.get("relevance", "중간")}
        },
        "사업기회": {
            "rich_text": [{"text": {"content": policy.get("business_opportunity", "")[:2000]}}]
        },
        "액션": {
            "select": {"name": policy.get("action", "모니터링")}
        },
        "수집건수": {
            "number": 1
        },
    }

    if url:
        props["URL"] = {"url": url}

    page = notion_request("POST", "pages", {"parent": {"database_id": NOTION_DB_ID}, "properties": props})
    return page["id"]


def compare_with_history(result: dict, history: list[dict]) -> str:
    """이전 주 대비 키워드 증감 분석 텍스트 생성"""
    if not history:
        return "이번 주가 첫 수집입니다."

    prev = history[0]  # 바로 직전 주
    prev_kws = {k["keyword"] for k in prev.get("top_keywords", [])}
    curr_kws = {k["keyword"] for k in result.get("top_keywords", [])}

    new_kws = curr_kws - prev_kws
    dropped_kws = prev_kws - curr_kws

    lines = []
    if new_kws:
        lines.append(f"신규 등장: {', '.join(new_kws)}")
    if dropped_kws:
        lines.append(f"이번 주 제외: {', '.join(dropped_kws)}")
    if not lines:
        lines.append("전주 대비 키워드 구성 유사")

    return " | ".join(lines)


# ── 메인 실행 ─────────────────────────────────────────────────────────────────

def run():
    print("=" * 60)
    print("📤 Notion 데이터베이스 적재 시작")
    print("=" * 60 + "\n")

    # 환경변수 확인
    if not NOTION_TOKEN or not NOTION_DB_ID:
        print("❌ 환경변수가 설정되지 않았습니다.")
        print("   export NOTION_TOKEN='secret_xxxx'")
        print("   export NOTION_DATABASE_ID='xxxxxxxx...'")
        return

    # 1. 정책 수집 & 분석 실행
    result = crawl_and_analyze()
    if not result:
        return

    week = result["week"]

    # 2. 중복 체크
    if check_week_exists(week):
        print(f"⚠ {week} 데이터가 이미 존재합니다. 덮어쓰지 않고 종료합니다.")
        print("  강제 재실행 시: history/{week}.json 삭제 후 다시 실행")
        return

    # 3. 이전 주 히스토리 로드 & 비교
    history = load_history(weeks=4)
    comparison = compare_with_history(result, history)
    print(f"📈 전주 대비: {comparison}\n")

    # 4. Notion 적재
    print("📤 Notion에 데이터 추가 중...")

    # 주간 요약 행
    summary_id = add_weekly_summary(result)
    print(f"  ✓ 주간 요약 추가 (ID: {summary_id[:8]}...)")

    # 개별 정책 행
    success, fail = 0, 0
    for policy in result["policies"]:
        try:
            add_policy_row(policy, week, result["collected_date"])
            success += 1
            print(f"  ✓ {policy['source']} | {policy['title'][:30]}...")
        except Exception as e:
            fail += 1
            print(f"  ✗ 실패: {policy.get('title', '')[:30]}... → {e}")

    print(f"\n✅ 완료: 성공 {success}건 / 실패 {fail}건")
    print(f"📊 Notion DB에서 확인: https://notion.so/{NOTION_DB_ID.replace('-', '')}")


if __name__ == "__main__":
    run()
