# mirae_asset_agent — "왜 잃었지?" 복기 시스템

완결된 국내주식 거래내역을 분석해 손실 원인을 3가지 에이전트로 진단하고, 같은 실수 반복 시 알림을 제공하는 멀티에이전트 시스템.

---

## 전체 구조

```
사용자 거래 CSV
      ↓
analysis/common/parser.py (CSV → 사이클 묶기)
      ↓
analysis/orchestrator/pipeline.py (손실 필터 → 심리귀속 → 라우팅)
      ↓
  ┌───────────────────────────────────┐
  │  agents/entry-error-agent/ (진입오류) │
  │  agents/손절실패/          (손절실패) │
  │  analysis/psych_agent/ (심리패턴) │
  └───────────────────────────────────┘
      ↓
analysis/data/orchestrator.sqlite3 (결과 저장)
      ↓
[예측기 - 다음 실수 예측 알림] (개발 예정)
      ↓
web/ (Next.js 대시보드)
```

---

## 폴더 구조

| 폴더 | 역할 |
|---|---|
| `analysis/common/` | 공통 스키마·파서·어댑터 |
| `analysis/loss_screener/` | 시장제거 손실 선별 (α 기준) |
| `analysis/psych_agent/` | 심리패턴 분석 (리벤지/과매매/처분효과) |
| `analysis/orchestrator/` | 총괄 오케스트레이터 |
| `analysis/collector/` | 키움 REST API 1분봉 수집기 |
| `agents/entry-error-agent/` | 진입오류 에이전트 |
| `agents/손절실패/` | 손절실패 에이전트 |
| `web/` | Next.js 대시보드 (Vercel 배포) |

---

## 빠른 시작

```bash
# Python 환경 (analysis/)
cd analysis && source venv/bin/activate

# 오케스트레이터 실행
python -c "
from orchestrator import run_pipeline
result = run_pipeline('my_trades.csv', broker='kiwoom')
print(result.to_dict())
"

# 웹 대시보드
cd web && npm install && npm run dev   # http://localhost:3000
```

---

## 상세 문서

| 문서 | 내용 |
|---|---|
| [analysis/orchestrator/README.md](analysis/orchestrator/README.md) | 오케스트레이터 구조 |
| [analysis/psych_agent/README.md](analysis/psych_agent/README.md) | 심리 에이전트 |
| [agents/entry-error-agent/SPEC.md](agents/entry-error-agent/SPEC.md) | 진입오류 에이전트 명세 |
| [agents/손절실패/DESIGN.md](agents/손절실패/DESIGN.md) | 손절실패 에이전트 설계 |
| [web/README.md](web/README.md) | 웹 대시보드 |
| [analysis/README.md](analysis/README.md) | Python 환경 설정 |

---

## 데이터

KOSPI 808종목, 1분봉 245거래일분 (약 1년). `analysis/data/` 는 gitignore.
