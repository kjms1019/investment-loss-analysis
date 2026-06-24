# 총괄 오케스트레이터

사용자 거래 CSV를 받아 3개 에이전트 중 적합한 에이전트로 라우팅하고 분석 결과를 저장한다.

## 파이프라인 흐름

```
CSV
 ↓ common/parser.py
RawTrade → TradeCycle (사이클 묶기)
 ↓
손실 사이클 필터링
 ↓
psych_agent/focus.py (계좌 전체 심리 귀속)
 ↓
router.py (규칙 기반 3단계 라우팅)
  1순위: 심리 패턴 dominant → psych 에이전트
  2순위: 손절선 이탈 + 2일 이상 버팀 → stop_loss_failure 에이전트
  3순위: 나머지 → entry_error 에이전트
 ↓
agent_registry.py (에이전트 실행)
 ↓
storage.py (SQLite 저장)
```

## 모듈

| 파일 | 역할 |
|---|---|
| `pipeline.py` | 파이프라인 진입점 (`run_pipeline`) |
| `router.py` | 사이클 단위 규칙 기반 라우터 |
| `agent_registry.py` | 에이전트 어댑터 + 레지스트리 |
| `schema.py` | 내부 데이터 계약 |
| `storage.py` | SQLite 결과 저장 |

## 사용법

```python
from analysis.orchestrator import run_pipeline

result = run_pipeline("my_trades.csv", broker="kiwoom")
print(result.to_dict())
```

## 입력 CSV 기본 컬럼 (generic)

```
datetime,code,name,side,qty,price
```

키움 증권 형식은 `broker="kiwoom"` 으로 지정.

## 저장 경로

```
analysis/data/orchestrator.sqlite3
```

`analysis/data/` 는 `.gitignore` 대상이므로 DB 파일은 커밋되지 않음.
