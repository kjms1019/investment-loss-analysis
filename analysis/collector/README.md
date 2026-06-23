# 코스피 1분봉 수집기 (키움 REST · ka10080)

코스피 종목의 1분봉을 안전하게(백오프·재시도·토큰 자동갱신·재개) 수집해
종목별 parquet 으로 저장합니다.

## 저장 구조
```
analysis/data/
├── min1/
│   ├── 005930.parquet      # 종목당 1파일 (datetime,open,high,low,close,volume,acc_volume,code)
│   ├── 000660.parquet
│   └── _manifest.json      # 종목·Phase별 완료 상태 (재개용)
└── .cache/
    ├── token.json          # 접근토큰 캐시 (만료 1h 전 자동 갱신)
    └── kospi_codes.csv      # 코스피 종목 리스트 캐시
```
`analysis/data/` 는 git 미추적이라 커밋되지 않습니다.

## 준비
```bash
cd analysis
source venv/bin/activate
pip install -r requirements.txt          # pyarrow, requests 추가됨
# 프로젝트 루트 .env 에 KIWOOM_APP_KEY / KIWOOM_APP_SECRET 입력
```

## 1) 먼저 실측 (필수 — 1종목으로 안전 점검)
키움이 실제로 몇 개월치를 주는지, 응답 스키마가 맞는지 확인:
```bash
cd ..                       # 프로젝트 루트에서 -m 실행
python -m analysis.collector.collect_min1 --self-test 005930
```
→ "가장 오래된 봉" 날짜로 실제 확보 가능한 기간을 확인하세요.
(키움 분봉은 과거 깊이에 제한이 있어 1년이 안 될 수 있습니다.)

## 2) 소수 종목 테스트
```bash
python -m analysis.collector.collect_min1 --phase a --limit 3
```

## 3) 본 수집 (3개월 먼저 → 9개월)
```bash
python -m analysis.collector.collect_min1 --phase a    # 최근 3개월, 전 종목
python -m analysis.collector.collect_min1 --phase b    # 이전 9개월, 전 종목
```
- 중단돼도 다시 실행하면 manifest 기준으로 **끝난 종목은 건너뛰고 이어서** 진행합니다.
- 차단(429)·실패는 자동 백오프 재시도. 종목 단위 에러는 manifest 에 기록하고 계속 진행.
- 차단이 잦으면 `.env` 의 `KIWOOM_SLEEP` 을 0.5~1.0 으로 올리세요.

## 옵션
| 플래그 | 설명 |
|---|---|
| `--phase a\|b` | a=최근3개월, b=이전9개월 |
| `--format parquet\|csv` | 저장 형식 (기본 parquet) |
| `--limit N` | 앞 N종목만 (테스트) |
| `--codes 005930,000660` | 특정 종목만 |
| `--force` | 완료 종목도 재수집 |
| `--self-test CODE` | 깊이/스키마 실측 |

## 검증 필요 지점 (환경에 따라 다를 수 있음)
- `ka10080` 응답 키 `stk_min_pole_chart_qry`, 항목 필드명(`cntr_tm`, `cur_prc` 등)
- `ka10099`(종목 리스트) 스키마 — 실패 시 `data/.cache/kospi_codes.csv`
  (`code,name` 헤더)를 직접 만들어 폴백 가능
- 토큰 발급 응답 필드(`token`, `expires_dt`)

위 3가지는 `--self-test` 와 `universe.py` 단독 실행으로 먼저 확인하세요.
