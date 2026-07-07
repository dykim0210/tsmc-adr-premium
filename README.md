# TSMC ADR 괴리율 대시보드

TSMC 본주(2330.TW)와 ADR(TSM, NYSE)의 괴리율을 매 영업일 자동 계산해 차트로 보여주는 대시보드.
`tw-revenue-dashboard`, `us-new-highs`와 동일한 GitHub Actions + Pages 구조.

- 괴리율 = TSM ADR(USD) ÷ [2330.TW 종가 × 5주 ÷ USD/TWD] − 1
- 1 ADR = 보통주 5주 (1997년 상장 이후 불변)
- 매 영업일 07:00 KST (뉴욕장 마감 후) 자동 갱신

## 설치 (브라우저만으로 5분, 파이썬 불필요)

### 1. 저장소 생성
github.com 로그인 → 우측 상단 **+** → **New repository**
- Repository name: `tsmc-adr-premium`
- **Public** 선택 (Pages 무료 사용 조건) → **Create repository**

### 2. 워크플로우 파일 생성
저장소 화면에서 **creating a new file** (또는 Add file → Create new file) 클릭
- 파일명 입력란에 정확히 입력: `.github/workflows/update.yml`
  (경로를 입력하면 폴더가 자동 생성됨)
- `update.yml` 내용 전체를 붙여넣기 → **Commit changes**

### 3. 나머지 파일 업로드
**Add file → Upload files** 클릭 → `fetch_data.py`, `index.html`, `README.md`
드래그 앤 드롭 → **Commit changes**

### 4. 첫 실행
**Actions** 탭 → 필요 시 "I understand my workflows, enable them" 클릭
→ 왼쪽 **Update TSMC ADR premium data** 선택 → **Run workflow** → Run workflow
→ 1~2분 후 초록색 체크 확인 (`data/` 폴더에 CSV와 JSON 생성됨)

### 5. Pages 활성화
**Settings → Pages** → Source: **Deploy from a branch**
→ Branch: `main`, 폴더: `/ (root)` → **Save**

몇 분 후 접속: `https://dykim0210.github.io/tsmc-adr-premium/`

## 파일 구성

| 파일 | 역할 |
|---|---|
| `.github/workflows/update.yml` | 매 영업일 07:00 KST 자동 실행 스케줄 |
| `fetch_data.py` | Yahoo Finance에서 3개 시계열 수집, 괴리율 계산 |
| `index.html` | Chart.js 대시보드 (기간 버튼: 전체/10년/5년/3년/1년) |
| `data/tsmc_adr_premium.csv` | 자동 생성 — 전체 일별 시계열 (분석용) |
| `data/premium.json` | 자동 생성 — 대시보드용 데이터 |

## 유의사항

- Yahoo 데이터 커버리지: TSM은 1997년 상장 시점부터, 2330.TW는 약 2000년,
  USD/TWD 환율은 약 2003년부터. 괴리율은 세 시계열이 모두 존재하는
  시점부터 계산되며, 실제 시작일은 대시보드 상단과 Actions 로그에 표시됨.
- 대만장(현지 13:30)과 뉴욕장 마감 시점 차이로 같은 날짜라도 ADR이
  최신 정보를 먼저 반영함. 단기 괴리율 해석 시 감안 필요.
- 결측 처리: 환율만 최대 5영업일 전일값 사용, 주가 결측은 채우지 않음.
  추정치 생성 없음. 괴리율이 −50%~+60% 범위를 벗어나면 로그에 경고 출력.
- 무료 GitHub Actions 사용량 기준으로 하루 1회 실행은 한도에 전혀 문제 없음.
