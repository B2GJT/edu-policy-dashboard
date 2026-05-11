# 교육/HR 정책 트렌드 대시보드

정부 정책을 매주 자동 수집하고, AI가 교육/HR 사업 관점에서 분석한 결과를 웹 대시보드와 이메일로 제공하는 시스템입니다.

## 주요 기능

- 연합뉴스·한겨레 RSS 5개 소스에서 매주 최신 정책/뉴스 200건+ 자동 수집
- 키워드 1차 필터링(40건) → Groq AI가 교육/HR 관련 정책 분석 및 사업 기회 추출
- 고용노동부 / 교육부 / 중소벤처기업부 담당 부처별 분류
- 주차별 이전/다음 탐색이 가능한 웹 대시보드 자동 생성
- GitHub Pages에 자동 배포
- 팀원 이메일 자동 발송

## 기술 스택

- Python 3.14
- Groq API (llama-3.3-70b-versatile) — 무료 플랜 사용
- GitHub Pages (정적 호스팅, 자동 배포)
- Gmail SMTP (이메일 발송)
- Windows 작업 스케줄러 (`run_weekly.bat`, 매주 자동 실행)

## 파일 구조

```
정부 정책 스크래핑/
├── policy_crawler.py   # 핵심 스크립트 (수집 + 분석 + 배포 + 이메일)
├── run_weekly.bat      # Windows 자동 실행 파일
├── dashboard.html      # 웹 대시보드 (자동 생성)
├── README.md           # 이 파일
├── 가이드.md           # 운영 가이드 (API 키 교체, 수신자 관리 등)
├── CLAUDE_CODE_GUIDE_v2.md  # Claude Code 명령어 모음
└── history/            # 주차별 분석 결과 JSON (자동 생성)
    ├── 2026-W14.json
    └── 2026-W17.json
```

## 대시보드

https://b2gjt.github.io/edu-policy-dashboard

## 실행 방법

```bash
python policy_crawler.py
```

실행 시 자동으로 **수집 → 분석 → 대시보드 생성 → GitHub 업로드 → 이메일 발송**까지 진행됩니다.

## 자동 실행 설정

`run_weekly.bat`을 Windows 작업 스케줄러에 등록하면 매주 월요일 오전 9시에 자동 실행됩니다.
설정 방법은 `가이드.md`를 참고하세요.

## 설정 변경

`policy_crawler.py` 상단의 설정값을 수정하여 이메일 수신자, API 키, GitHub 토큰 등을 변경할 수 있습니다.
자세한 내용은 `가이드.md`를 참고하세요.

---

## 변경 이력

| 날짜 | 내용 |
|---|---|
| 2026-04-09 | 최초 구축 (정책브리핑 RSS, Groq AI, GitHub Pages, 이메일 연동) |
| 2026-04-27 | RSS 소스 교체 — korea.kr 서버 차단으로 연합뉴스·한겨레 5개 피드로 변경, 키워드 사전 필터링 추가, 부처별 분류(고용노동부/교육부/중기부) 추가 |
| 2026-05-11 | GitHub 팀 계정(B2GJT)으로 이전, 민감 정보 .env 분리 |

*마지막 업데이트: 2026-05-11*
