"""
policy_crawler.py - Groq API 버전
교육/HR 정책 트렌드 수집 및 AI 분석 스크립트
실행: python policy_crawler.py
"""

import os
import sys
import json
import time
import urllib.request
import requests

# Windows 터미널 이모지 출력 오류 방지
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import urllib.parse
import re
import xml.etree.ElementTree as ET
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, date
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# ── 설정 ──────────────────────────────────────────────────────────────────────

# 이메일 설정 (변경 필요 시 .env 파일에서 수정)
EMAIL_SENDER   = "kyeongmin.lim@day1company.co.kr"
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")   # Gmail 앱 비밀번호 (.env에서 관리)
EMAIL_RECIPIENTS = [
    "kyeongmin.lim@day1company.co.kr",
    "jinho.kim@day1company.co.kr",
    "yunho.kim@day1company.co.kr",
    "hanna.jang@day1company.co.kr",
    "chanhyeok.joo@day1company.co.kr"
]
EMAIL_SUBJECT  = "[주간] 교육 정책 트렌드 리포트"
DASHBOARD_URL  = "https://b2gjt.github.io/edu-policy-dashboard"

# GitHub 설정 (재발급 시 .env 파일의 GITHUB_TOKEN 교체)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO  = "B2GJT/edu-policy-dashboard"
GITHUB_FILE  = "index.html"

# 뉴스 RSS 피드 목록 (연합뉴스 등 - 정부 부처 보도자료 포함)
# 고용노동부·교육부·중소벤처기업부 직접 RSS는 봇 차단으로 접근 불가,
# 연합뉴스·한겨레가 각 부처 보도자료를 즉시 보도하므로 대체 소스로 활용
RSS_SOURCES = [
    {
        "name": "연합뉴스(사회)",
        "url": "https://www.yna.co.kr/rss/society.xml",
        "max_items": 50,
    },
    {
        "name": "연합뉴스(경제)",
        "url": "https://www.yna.co.kr/rss/economy.xml",
        "max_items": 50,
    },
    {
        "name": "연합뉴스(산업)",
        "url": "https://www.yna.co.kr/rss/industry.xml",
        "max_items": 50,
    },
    {
        "name": "한겨레(사회)",
        "url": "https://www.hani.co.kr/rss/society/",
        "max_items": 30,
    },
    {
        "name": "한겨레(경제)",
        "url": "https://www.hani.co.kr/rss/economy/",
        "max_items": 30,
    },
]

EDU_HR_KEYWORDS = [
    # 훈련/교육
    "직업훈련", "인재개발", "에듀테크", "AI교육", "디지털전환",
    "역량개발", "LMS", "비대면훈련", "HRD", "교육데이터",
    "인적자원", "스킬업", "재직자훈련", "교육바우처", "국비지원",
    "훈련비지원", "능력개발", "직무교육", "K-디지털", "직업능력",
    # 고용노동부 관련
    "고용노동부", "고용장려금", "청년일자리", "일자리창출", "취업지원",
    "실업급여", "고용보험", "고용촉진", "근로자지원", "고용서비스",
    "내일배움카드", "사업주훈련", "고용24",
    # 교육부 관련
    "교육부", "대학지원", "평생교육", "직업교육", "특성화고",
    "전문대학", "교육과정", "입시제도",
    # 중소벤처기업부 관련
    "중소벤처기업부", "중소기업지원", "스타트업", "창업지원",
    "벤처기업", "소상공인", "중기부", "창업교육",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ── Groq API 초기화 ───────────────────────────────────────────────────────────

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
client = Groq(api_key=GROQ_API_KEY)


# ── 핵심 함수 ─────────────────────────────────────────────────────────────────

def fetch_rss(source: dict, max_items: int = 30) -> list[dict]:
    """RSS 피드에서 최신 정책 목록 가져오기"""
    try:
        resp = requests.get(source["url"], headers=HEADERS, timeout=15)
        resp.raise_for_status()
        xml_data = resp.content
    except Exception as e:
        print(f"     ⚠ RSS 요청 실패: {e}")
        return []

    results = []
    try:
        root = ET.fromstring(xml_data)
        # RSS 네임스페이스 처리
        ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        items = root.findall(".//item")
        for item in items[:max_items]:
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            date_el = item.find("pubDate") or item.find("dc:date", ns)

            title = title_el.text.strip() if title_el is not None and title_el.text else ""
            link = link_el.text.strip() if link_el is not None and link_el.text else ""
            desc = re.sub(r'<[^>]+>', '', desc_el.text or "").strip() if desc_el is not None else ""
            pub_date = date_el.text.strip() if date_el is not None and date_el.text else date.today().isoformat()

            if title:
                results.append({
                    "title":   title,
                    "summary": desc[:200],
                    "date":    pub_date,
                    "url":     link,
                    "source":  source["name"],
                })
    except ET.ParseError as e:
        print(f"     ⚠ XML 파싱 실패: {e}")

    return results


def collect_policies() -> list[dict]:
    """RSS 피드로 4개 정부 사이트 최신 정책 수집"""
    print("🔍 정책 사이트 수집 시작...")
    all_policies = []

    for source in RSS_SOURCES:
        print(f"  → {source['name']} 수집 중...")
        results = fetch_rss(source, max_items=source.get("max_items", 30))

        all_policies.extend(results)
        print(f"     ✓ {len(results)}건 수집")
        time.sleep(1.0)  # 서버 과부하 방지

    print(f"\n  총 {len(all_policies)}건 수집 완료\n")
    return all_policies


BROAD_FILTER_KEYWORDS = [
    # 교육/훈련 (넓게)
    "교육", "훈련", "학습", "역량", "기술", "자격", "에듀",
    # 고용/일자리
    "고용", "일자리", "취업", "채용", "실업", "근로", "노동", "인력",
    # 지원/정책
    "지원금", "장려금", "보조금", "바우처", "국비", "정부지원",
    # 부처명
    "고용노동부", "교육부", "중소벤처기업부", "중기부", "고용부", "노동부",
    # 사업명
    "내일배움카드", "K-디지털", "HRD", "직업능력", "능력개발",
    # 중소기업/스타트업
    "중소기업", "소상공인", "스타트업", "벤처", "창업",
    # 청년
    "청년", "대학생", "신입", "취준",
]


def prefilter_policies(policies: list[dict], max_count: int = 40) -> list[dict]:
    """AI 전달 전 1차 필터링 (광범위 키워드 사용, 토큰 절약)"""
    scored = []
    for p in policies:
        text = p.get("title", "") + " " + p.get("summary", "")
        score = sum(1 for k in BROAD_FILTER_KEYWORDS if k in text)
        if score > 0:
            scored.append((score, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    combined = [p for _, p in scored[:max_count]]
    print(f"  → 전체 {len(policies)}건 → 키워드 필터 후 {len(combined)}건 AI 분석 대상")
    return combined


def analyze_and_classify(policies: list[dict]) -> dict:
    """수집된 정책을 Groq AI가 교육/HR 관점에서 분석 및 분류"""
    print("🤖 AI 분석 및 키워드 추출 중...")

    policies = prefilter_policies(policies, max_count=40)
    policies_text = json.dumps(policies, ensure_ascii=False, indent=2)
    today = date.today()

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        temperature=0.2,
        max_tokens=3000,
        messages=[{
            "role": "user",
            "content": f"""다음은 이번 주 뉴스 RSS에서 수집된 기사 목록이야.
우리 회사는 고용노동부·교육부·중소벤처기업부 관련 교육/HR 사업(직업훈련, 내일배움카드, K-디지털, 사업주훈련 등)을 하고 있어.
각 기사를 분석해서 정부 정책·지원사업 관련 사업 기회를 찾아줘.

기사 목록:
{policies_text}

참고할 교육/HR 키워드: {', '.join(EDU_HR_KEYWORDS)}

아래 JSON 형식으로만 응답해줘 (다른 텍스트 없이):
{{
  "week": "{today.strftime('%Y-W%U')}",
  "collected_date": "{today.isoformat()}",
  "total_count": <전체 기사 수>,
  "relevant_count": <교육/HR/정부지원 관련 기사 수>,
  "top_keywords": [
    {{"keyword": "키워드", "count": <빈도수>, "trend": "상승/유지/신규"}}
  ],
  "policies": [
    {{
      "title": "기사 제목",
      "source": "출처",
      "date": "날짜",
      "url": "URL",
      "ministry": "고용노동부/교육부/중소벤처기업부/기타",
      "relevance": "높음/중간/낮음",
      "keywords": ["키워드1", "키워드2"],
      "business_opportunity": "우리 사업에 적용 가능한 포인트 (2문장 이내)",
      "action": "즉시검토/참고/모니터링"
    }}
  ],
  "weekly_insight": "이번 주 고용노동부·교육부·중소벤처기업부 정책 트렌드 요약 (3문장 이내)",
  "recommended_actions": ["권장 액션1", "권장 액션2", "권장 액션3"]
}}

relevance가 '높음' 또는 '중간'인 것만 policies에 포함해줘.
정부 정책·지원사업·예산·제도 변화와 직접 관련 없는 일반 사건사고 기사는 제외해줘."""
        }],
    )

    text = response.choices[0].message.content
    start = text.find("{")
    end = text.rfind("}") + 1
    result = json.loads(text[start:end])

    print(f"  ✓ 관련 정책 {result['relevant_count']}건 / 전체 {result['total_count']}건")
    print(f"  ✓ 핵심 키워드 {len(result['top_keywords'])}개 추출\n")
    return result


def save_result(result: dict) -> str:
    """분석 결과를 로컬 JSON으로 저장"""
    os.makedirs("history", exist_ok=True)
    filename = f"history/{result['week']}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"💾 로컬 저장 완료: {filename}")
    return filename


def load_history(weeks: int = 8) -> list[dict]:
    """최근 N주 히스토리 로드 (트렌드 비교용)"""
    if not os.path.exists("history"):
        return []
    files = sorted(os.listdir("history"), reverse=True)[:weeks]
    history = []
    for f in files:
        if f.endswith(".json"):
            with open(f"history/{f}", encoding="utf-8") as fp:
                history.append(json.load(fp))
    return history


def generate_dashboard(history: list[dict]) -> None:
    """수집된 히스토리를 바탕으로 dashboard.html 생성 (JS 기반 주차 전환)"""
    history_json = json.dumps(history, ensure_ascii=False)
    updated = datetime.now().strftime('%Y-%m-%d %H:%M')

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>교육/HR 정책 트렌드 대시보드</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Pretendard', 'Noto Sans KR', sans-serif;
    background: #f8fafc;
    color: #1e293b;
    font-size: 15px;
    line-height: 1.6;
  }}

  /* 헤더 */
  header {{
    background: linear-gradient(135deg, #1e3a8a 0%, #1d4ed8 100%);
    color: white;
    padding: 28px 40px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  header h1 {{ font-size: 1.35rem; font-weight: 700; letter-spacing: -0.3px; }}
  header .subtitle {{ font-size: 0.8rem; opacity: 0.75; margin-top: 5px; font-weight: 400; }}
  .updated-info {{ font-size: 0.75rem; opacity: 0.65; text-align: right; }}

  /* 주차 네비게이터 */
  .week-nav {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 16px;
    padding: 20px;
    background: white;
    border-bottom: 1px solid #e2e8f0;
    position: sticky;
    top: 0;
    z-index: 10;
    box-shadow: 0 1px 6px rgba(0,0,0,0.06);
  }}
  .week-nav button {{
    background: #f1f5f9;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 7px 18px;
    font-family: inherit;
    font-size: 0.85rem;
    font-weight: 600;
    color: #475569;
    cursor: pointer;
    transition: all 0.15s;
  }}
  .week-nav button:hover:not(:disabled) {{
    background: #1d4ed8;
    color: white;
    border-color: #1d4ed8;
  }}
  .week-nav button:disabled {{ opacity: 0.3; cursor: default; }}
  .week-label {{
    font-size: 1rem;
    font-weight: 700;
    color: #1e293b;
    min-width: 120px;
    text-align: center;
  }}
  .week-sub {{ font-size: 0.75rem; color: #94a3b8; text-align: center; margin-top: 2px; }}

  /* 컨테이너 */
  .container {{ max-width: 1060px; margin: 0 auto; padding: 28px 20px; }}

  /* 스탯 카드 */
  .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 24px; }}
  @media (max-width: 700px) {{ .stats {{ grid-template-columns: repeat(2, 1fr); }} }}
  .stat-box {{
    background: white;
    border-radius: 14px;
    padding: 20px 18px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.07);
    border: 1px solid #f1f5f9;
  }}
  .stat-label {{ font-size: 0.72rem; color: #94a3b8; font-weight: 600; letter-spacing: 0.3px; text-transform: uppercase; margin-bottom: 8px; }}
  .stat-value {{ font-size: 2rem; font-weight: 700; color: #1d4ed8; line-height: 1; }}
  .stat-value.red {{ color: #ef4444; }}
  .stat-value.sm {{ font-size: 1.25rem; }}
  .stat-sub {{ font-size: 0.75rem; color: #cbd5e1; margin-top: 6px; }}

  /* 섹션 */
  .section {{
    background: white;
    border-radius: 14px;
    padding: 22px 26px;
    margin-bottom: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.07);
    border: 1px solid #f1f5f9;
  }}
  .section-title {{
    font-size: 0.82rem;
    font-weight: 700;
    color: #64748b;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    margin-bottom: 14px;
    padding-bottom: 12px;
    border-bottom: 1px solid #f1f5f9;
  }}

  /* 인사이트 */
  .insight-box {{
    background: #eff6ff;
    border-left: 3px solid #1d4ed8;
    border-radius: 0 10px 10px 0;
    padding: 16px 20px;
    font-size: 0.92rem;
    line-height: 1.75;
    color: #1e3a8a;
    font-weight: 500;
  }}

  /* 키워드 칩 */
  .kw-chips {{ display: flex; flex-wrap: wrap; gap: 10px; }}
  .kw-chip {{
    display: flex;
    align-items: center;
    gap: 6px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 20px;
    padding: 6px 14px;
    font-size: 0.83rem;
    font-weight: 600;
    color: #334155;
  }}
  .kw-trend {{
    font-size: 0.75rem;
    padding: 1px 7px;
    border-radius: 10px;
    font-weight: 700;
  }}
  .trend-up {{ background: #dcfce7; color: #16a34a; }}
  .trend-new {{ background: #fef9c3; color: #ca8a04; }}
  .trend-keep {{ background: #f1f5f9; color: #64748b; }}

  /* 액션 리스트 */
  .action-list {{ list-style: none; }}
  .action-list li {{
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 11px 0;
    border-bottom: 1px solid #f8fafc;
    font-size: 0.88rem;
    color: #334155;
  }}
  .action-list li:last-child {{ border-bottom: none; }}
  .action-icon {{
    width: 22px;
    height: 22px;
    background: #1d4ed8;
    color: white;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.7rem;
    font-weight: 700;
    flex-shrink: 0;
    margin-top: 1px;
  }}

  /* 정책 카드 */
  .policy-card {{
    border: 1px solid #f1f5f9;
    border-radius: 12px;
    padding: 18px;
    margin-bottom: 10px;
    transition: box-shadow 0.2s, border-color 0.2s;
    background: #fafbfc;
  }}
  .policy-card:hover {{ box-shadow: 0 4px 16px rgba(0,0,0,0.08); border-color: #e2e8f0; background: white; }}
  .policy-card-header {{ display: flex; align-items: flex-start; gap: 10px; margin-bottom: 8px; }}
  .rel-dot {{ width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; margin-top: 7px; }}
  .policy-title {{ flex: 1; font-size: 0.93rem; font-weight: 600; line-height: 1.5; }}
  .policy-title a {{ color: #1e293b; text-decoration: none; }}
  .policy-title a:hover {{ color: #1d4ed8; }}
  .action-badge {{
    font-size: 0.68rem;
    padding: 3px 9px;
    border-radius: 10px;
    white-space: nowrap;
    flex-shrink: 0;
    font-weight: 700;
    margin-top: 2px;
  }}
  .badge-red {{ background: #fee2e2; color: #dc2626; }}
  .badge-orange {{ background: #ffedd5; color: #c2410c; }}
  .badge-gray {{ background: #f1f5f9; color: #64748b; }}
  .policy-meta {{ font-size: 0.74rem; color: #94a3b8; margin-bottom: 8px; padding-left: 18px; }}
  .policy-opp {{ font-size: 0.85rem; color: #475569; padding-left: 18px; margin-bottom: 10px; line-height: 1.65; }}
  .policy-tags {{ display: flex; flex-wrap: wrap; gap: 5px; padding-left: 18px; }}
  .tag {{
    background: #eff6ff;
    color: #1d4ed8;
    font-size: 0.71rem;
    padding: 2px 9px;
    border-radius: 8px;
    font-weight: 500;
  }}
  .empty-msg {{ text-align: center; color: #94a3b8; padding: 32px; font-size: 0.88rem; }}
  .footer {{ text-align: center; color: #cbd5e1; font-size: 0.73rem; margin-top: 32px; padding-bottom: 40px; }}
</style>
</head>
<body>

<header>
  <div>
    <h1>교육/HR 정책 트렌드 대시보드</h1>
    <div class="subtitle">정부 정책 자동 수집 · AI 분석 · 매주 업데이트</div>
  </div>
  <div class="updated-info">마지막 업데이트<br>{updated}</div>
</header>

<!-- 주차 네비게이터 -->
<div class="week-nav">
  <button id="btn-prev" onclick="changeWeek(1)">← 이전 주</button>
  <div>
    <div class="week-label" id="week-label">—</div>
    <div class="week-sub" id="week-sub">—</div>
  </div>
  <button id="btn-next" onclick="changeWeek(-1)">다음 주 →</button>
</div>

<div class="container">
  <div class="stats" id="stats"></div>
  <div class="section" id="section-insight">
    <div class="section-title">주간 인사이트</div>
    <div class="insight-box" id="insight-text"></div>
  </div>
  <div class="section" id="section-kw">
    <div class="section-title">핵심 키워드</div>
    <div class="kw-chips" id="kw-chips"></div>
  </div>
  <div class="section" id="section-actions">
    <div class="section-title">권장 액션</div>
    <ul class="action-list" id="action-list"></ul>
  </div>
  <div class="section" id="section-policies">
    <div class="section-title">관련 정책 목록</div>
    <div id="policy-cards"></div>
  </div>
  <div class="footer">정부 정책 자동 수집 시스템 · policy_crawler.py</div>
</div>

<script>
const HISTORY = {history_json};
let currentIdx = 0;  // 0 = 최신 (history[0])

function changeWeek(dir) {{
  currentIdx += dir;
  render();
}}

function render() {{
  const d = HISTORY[currentIdx];
  if (!d) return;

  // 네비게이터 업데이트
  document.getElementById('week-label').textContent = d.week || '—';
  document.getElementById('week-sub').textContent = '수집일: ' + (d.collected_date || '—') + '  (' + (currentIdx + 1) + ' / ' + HISTORY.length + '주)';
  document.getElementById('btn-prev').disabled = currentIdx >= HISTORY.length - 1;
  document.getElementById('btn-next').disabled = currentIdx <= 0;

  // 스탯
  const topKw = (d.top_keywords || [])[0];
  document.getElementById('stats').innerHTML = `
    <div class="stat-box">
      <div class="stat-label">전체 수집</div>
      <div class="stat-value">${{d.total_count || 0}}</div>
      <div class="stat-sub">건</div>
    </div>
    <div class="stat-box">
      <div class="stat-label">교육/HR 관련</div>
      <div class="stat-value red">${{d.relevant_count || 0}}</div>
      <div class="stat-sub">건 (높음+중간)</div>
    </div>
    <div class="stat-box">
      <div class="stat-label">핵심 키워드 수</div>
      <div class="stat-value">${{(d.top_keywords || []).length}}</div>
      <div class="stat-sub">개 추출</div>
    </div>
    <div class="stat-box">
      <div class="stat-label">Top 키워드</div>
      <div class="stat-value sm">${{topKw ? topKw.keyword : '—'}}</div>
      <div class="stat-sub">${{topKw ? topKw.trend || '' : ''}}</div>
    </div>
  `;

  // 인사이트
  document.getElementById('insight-text').textContent = d.weekly_insight || '분석 결과가 없습니다.';

  // 키워드 칩
  const trendClass = {{ '상승': 'trend-up', '신규': 'trend-new', '유지': 'trend-keep' }};
  document.getElementById('kw-chips').innerHTML = (d.top_keywords || []).map(kw => `
    <div class="kw-chip">
      ${{kw.keyword}}
      <span class="kw-trend ${{trendClass[kw.trend] || 'trend-keep'}}">${{kw.trend || ''}}</span>
    </div>
  `).join('') || '<span style="color:#94a3b8">키워드 없음</span>';

  // 권장 액션
  document.getElementById('action-list').innerHTML = (d.recommended_actions || []).map((a, i) => `
    <li><span class="action-icon">${{i+1}}</span>${{a}}</li>
  `).join('') || '<li><span class="action-icon">-</span>권장 액션 없음</li>';

  // 정책 카드
  const relColor = {{ '높음': '#ef4444', '중간': '#f97316', '낮음': '#94a3b8' }};
  const badgeCls = {{ '즉시검토': 'badge-red', '참고': 'badge-orange', '모니터링': 'badge-gray' }};
  const policies = d.policies || [];
  document.getElementById('policy-cards').innerHTML = policies.length ? policies.map(p => `
    <div class="policy-card">
      <div class="policy-card-header">
        <span class="rel-dot" style="background:${{relColor[p.relevance] || '#94a3b8'}}"></span>
        <span class="policy-title"><a href="${{p.url || '#'}}" target="_blank">${{p.title || ''}}</a></span>
        <span class="action-badge ${{badgeCls[p.action] || 'badge-gray'}}">${{p.action || ''}}</span>
      </div>
      <div class="policy-meta">${{p.ministry ? '['+p.ministry+'] ' : ''}}&nbsp;${{p.source || ''}} &nbsp;·&nbsp; ${{p.date || ''}}</div>
      <div class="policy-opp">${{p.business_opportunity || ''}}</div>
      <div class="policy-tags">${{(p.keywords || []).map(k => `<span class="tag">${{k}}</span>`).join('')}}</div>
    </div>
  `).join('') : '<div class="empty-msg">관련 정책이 없습니다.</div>';
}}

render();
</script>
</body>
</html>"""

    with open("dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("🌐 대시보드 생성 완료: dashboard.html")


def send_email(result: dict) -> None:
    """주간 분석 결과를 이메일로 발송"""
    top_keywords = ", ".join(k["keyword"] for k in result.get("top_keywords", [])[:5])
    policies = result.get("policies", [])

    # 정책 카드 HTML
    policy_rows = ""
    for p in policies:
        color = {"높음": "#ef4444", "중간": "#f97316"}.get(p.get("relevance", ""), "#94a3b8")
        policy_rows += f"""
        <tr>
          <td style="padding:12px 8px; border-bottom:1px solid #f1f5f9; vertical-align:top;">
            <a href="{p.get('url','#')}" style="color:#1d4ed8;font-weight:600;text-decoration:none;">{p.get('title','')}</a><br>
            <span style="font-size:12px;color:#94a3b8;">{p.get('source','')} · {p.get('date','')}</span>
          </td>
          <td style="padding:12px 8px; border-bottom:1px solid #f1f5f9; vertical-align:top; font-size:13px; color:#475569;">
            {p.get('business_opportunity','')}
          </td>
          <td style="padding:12px 8px; border-bottom:1px solid #f1f5f9; text-align:center; vertical-align:top;">
            <span style="background:{color};color:white;padding:2px 8px;border-radius:8px;font-size:11px;font-weight:700;">{p.get('relevance','')}</span>
          </td>
        </tr>"""

    actions_html = "".join(
        f'<li style="margin-bottom:8px;color:#334155;">{a}</li>'
        for a in result.get("recommended_actions", [])
    )

    body = f"""
<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;">
<div style="max-width:640px;margin:32px auto;background:white;border-radius:16px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);">

  <!-- 헤더 -->
  <div style="background:linear-gradient(135deg,#1e3a8a,#1d4ed8);padding:28px 32px;color:white;">
    <div style="font-size:11px;opacity:0.7;margin-bottom:6px;letter-spacing:1px;">WEEKLY REPORT</div>
    <div style="font-size:20px;font-weight:700;">교육 정책 트렌드 리포트</div>
    <div style="font-size:13px;opacity:0.75;margin-top:6px;">{result.get('week','')} · 수집일 {result.get('collected_date','')}</div>
  </div>

  <div style="padding:28px 32px;">

    <!-- 수치 요약 -->
    <div style="display:flex;gap:12px;margin-bottom:24px;">
      <div style="flex:1;background:#f8fafc;border-radius:10px;padding:16px;text-align:center;">
        <div style="font-size:11px;color:#94a3b8;margin-bottom:4px;">전체 수집</div>
        <div style="font-size:28px;font-weight:700;color:#1d4ed8;">{result.get('total_count',0)}</div>
        <div style="font-size:11px;color:#cbd5e1;">건</div>
      </div>
      <div style="flex:1;background:#f8fafc;border-radius:10px;padding:16px;text-align:center;">
        <div style="font-size:11px;color:#94a3b8;margin-bottom:4px;">교육/HR 관련</div>
        <div style="font-size:28px;font-weight:700;color:#ef4444;">{result.get('relevant_count',0)}</div>
        <div style="font-size:11px;color:#cbd5e1;">건</div>
      </div>
      <div style="flex:1;background:#f8fafc;border-radius:10px;padding:16px;text-align:center;">
        <div style="font-size:11px;color:#94a3b8;margin-bottom:4px;">핵심 키워드</div>
        <div style="font-size:13px;font-weight:700;color:#1e293b;margin-top:6px;">{top_keywords or '—'}</div>
      </div>
    </div>

    <!-- 인사이트 -->
    <div style="margin-bottom:24px;">
      <div style="font-size:11px;font-weight:700;color:#94a3b8;letter-spacing:0.5px;margin-bottom:10px;">주간 인사이트</div>
      <div style="background:#eff6ff;border-left:3px solid #1d4ed8;border-radius:0 10px 10px 0;padding:14px 18px;font-size:14px;line-height:1.7;color:#1e3a8a;">
        {result.get('weekly_insight','')}
      </div>
    </div>

    <!-- 정책 목록 -->
    <div style="margin-bottom:24px;">
      <div style="font-size:11px;font-weight:700;color:#94a3b8;letter-spacing:0.5px;margin-bottom:10px;">관련 정책 목록</div>
      <table style="width:100%;border-collapse:collapse;font-size:13px;">
        <thead>
          <tr style="background:#f8fafc;">
            <th style="padding:10px 8px;text-align:left;font-size:11px;color:#64748b;font-weight:600;">정책명</th>
            <th style="padding:10px 8px;text-align:left;font-size:11px;color:#64748b;font-weight:600;">사업 기회</th>
            <th style="padding:10px 8px;text-align:center;font-size:11px;color:#64748b;font-weight:600;">관련도</th>
          </tr>
        </thead>
        <tbody>{policy_rows or '<tr><td colspan="3" style="padding:20px;text-align:center;color:#94a3b8;">관련 정책 없음</td></tr>'}</tbody>
      </table>
    </div>

    <!-- 권장 액션 -->
    <div style="margin-bottom:28px;">
      <div style="font-size:11px;font-weight:700;color:#94a3b8;letter-spacing:0.5px;margin-bottom:10px;">권장 액션</div>
      <ul style="margin:0;padding-left:20px;">{actions_html}</ul>
    </div>

    <!-- 대시보드 링크 -->
    <div style="text-align:center;">
      <a href="{DASHBOARD_URL}" style="display:inline-block;background:#1d4ed8;color:white;padding:12px 28px;border-radius:10px;text-decoration:none;font-weight:700;font-size:14px;">
        전체 대시보드 보기
      </a>
    </div>

  </div>

  <div style="padding:16px 32px;background:#f8fafc;text-align:center;font-size:11px;color:#cbd5e1;">
    정부 정책 자동 수집 시스템 · policy_crawler.py
  </div>
</div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{EMAIL_SUBJECT} ({result.get('week','')})"
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = ", ".join(EMAIL_RECIPIENTS)
    msg.attach(MIMEText(body, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENTS, msg.as_string())
        print(f"📧 이메일 발송 완료 → {', '.join(EMAIL_RECIPIENTS)}")
    except Exception as e:
        print(f"⚠ 이메일 발송 실패: {e}")


def upload_to_github() -> None:
    """dashboard.html을 GitHub Pages에 자동 업로드 (index.html로 저장)"""
    import base64

    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }

    # 현재 파일의 SHA 가져오기 (업데이트에 필요)
    req = urllib.request.Request(api_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            current = json.loads(resp.read())
            sha = current.get("sha", "")
    except Exception:
        sha = ""

    # dashboard.html 읽어서 base64 인코딩
    with open("dashboard.html", "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode("utf-8")

    body = json.dumps({
        "message": f"update: {date.today().isoformat()} 주간 리포트",
        "content": content_b64,
        "sha": sha,
    }).encode("utf-8")

    req = urllib.request.Request(api_url, data=body, headers=headers, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
        print(f"🚀 GitHub Pages 업로드 완료 → {DASHBOARD_URL}")
    except Exception as e:
        print(f"⚠ GitHub 업로드 실패: {e}")


# ── 메인 실행 ─────────────────────────────────────────────────────────────────

def run():
    print("=" * 60)
    print(f"📋 교육/HR 정책 트렌드 수집 시작")
    print(f"   실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60 + "\n")

    # 1. 정책 수집
    policies = collect_policies()
    if not policies:
        print("❌ 수집된 정책이 없습니다. 종료.")
        return None

    # 2. AI 분석
    result = analyze_and_classify(policies)

    # 3. 로컬 저장
    save_result(result)

    # 4. 대시보드 생성
    history = load_history()
    generate_dashboard(history)

    # 5. GitHub Pages 업로드
    upload_to_github()

    # 6. 이메일 발송
    send_email(result)

    # 5. 결과 미리보기
    print("\n📊 이번 주 분석 결과 미리보기")
    print("-" * 40)
    print(f"주차: {result['week']}")
    print(f"관련 정책: {result['relevant_count']}건")
    if result['top_keywords']:
        print(f"핵심 키워드: {', '.join(k['keyword'] for k in result['top_keywords'][:5])}")
    print(f"\n인사이트: {result['weekly_insight']}")
    print("\n권장 액션:")
    for action in result["recommended_actions"]:
        print(f"  • {action}")

    return result


if __name__ == "__main__":
    run()
