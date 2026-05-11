#!/bin/bash
# run_weekly.sh
# 매주 월요일 09:00 자동 실행 스크립트
#
# 【 최초 1회 설정 방법 】
#
# 1. 환경변수 등록 (~/.zshrc 또는 ~/.bashrc에 추가)
#    export ANTHROPIC_API_KEY="sk-ant-xxxx"
#    export NOTION_TOKEN="secret_xxxx"
#    export NOTION_DATABASE_ID="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
#
# 2. Notion DB 컬럼 생성 (Notion에서 직접)
#    주차        → Title
#    수집일      → Date
#    출처        → Select  (정책브리핑 / 고용노동부 / 과기정통부 / 중기부 / 전체)
#    정책명      → Text
#    핵심키워드  → Multi-select
#    관련도      → Select  (높음 / 중간 / 요약)
#    사업기회    → Text
#    액션        → Select  (즉시검토 / 참고 / 모니터링)
#    수집건수    → Number
#    URL         → URL
#
# 3. 이 스크립트에 실행 권한 부여
#    chmod +x run_weekly.sh
#
# 4. cron 등록 (터미널에서 실행)
#    crontab -e
#    → 아래 줄 추가 (매주 월요일 오전 9시):
#    0 9 * * 1 /bin/bash /path/to/run_weekly.sh >> /path/to/logs/weekly.log 2>&1
#
# 5. 수동 테스트 실행
#    ./run_weekly.sh
#
# ─────────────────────────────────────────────────────────────────────────────

set -e  # 오류 발생 시 즉시 종료

# ── 경로 설정 ─────────────────────────────────────────────────────────────────

# 이 스크립트가 있는 폴더를 기준으로 절대경로 설정
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
VENV_DIR="$SCRIPT_DIR/.venv"

mkdir -p "$LOG_DIR"

# ── 로그 헤더 ─────────────────────────────────────────────────────────────────

echo ""
echo "============================================================"
echo "  교육/HR 정책 트렌드 수집 자동 실행"
echo "  시각: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"

# ── 환경변수 로드 ─────────────────────────────────────────────────────────────

# cron은 쉘 환경변수를 상속하지 않으므로 직접 로드
if [ -f "$HOME/.zshrc" ]; then
    source "$HOME/.zshrc" 2>/dev/null || true
elif [ -f "$HOME/.bashrc" ]; then
    source "$HOME/.bashrc" 2>/dev/null || true
fi

# 필수 환경변수 확인
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "❌ ANTHROPIC_API_KEY가 설정되지 않았습니다."
    exit 1
fi

if [ -z "$NOTION_TOKEN" ] || [ -z "$NOTION_DATABASE_ID" ]; then
    echo "❌ NOTION_TOKEN 또는 NOTION_DATABASE_ID가 설정되지 않았습니다."
    exit 1
fi

echo "✓ 환경변수 확인 완료"

# ── Python 가상환경 설정 ──────────────────────────────────────────────────────

cd "$SCRIPT_DIR"

# 가상환경이 없으면 생성
if [ ! -d "$VENV_DIR" ]; then
    echo "🔧 Python 가상환경 생성 중..."
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

# 패키지 설치 (없을 경우에만)
pip install anthropic --quiet --upgrade

echo "✓ Python 환경 준비 완료"

# ── 메인 실행 ─────────────────────────────────────────────────────────────────

echo ""
echo "🚀 정책 수집 및 Notion 적재 시작..."
echo ""

python3 notion_writer.py

EXIT_CODE=$?

# ── 완료 처리 ─────────────────────────────────────────────────────────────────

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ 완료: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "📁 히스토리: $SCRIPT_DIR/history/"
    echo "📋 로그: $LOG_DIR/weekly.log"
else
    echo "❌ 오류 발생 (exit code: $EXIT_CODE)"
    echo "   로그를 확인하세요: $LOG_DIR/weekly.log"
fi

echo "============================================================"
echo ""

exit $EXIT_CODE
