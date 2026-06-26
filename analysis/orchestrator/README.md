# 총괄 오케스트레이터

사용자 거래 CSV를 받아 3개 에이전트 중 적합한 에이전트로 라우팅하고 분석 결과를 저장한다.

## 파이프라인 흐름

```
CSV
 ↓ analysis/common/parser.py
RawTrade → TradeCycle (사이클 묶기)
 ↓
손실 사이클 필터링
 ↓
analysis/classifier (진입오류/손절실패 학습 분류기)
 ↓
psych_agent/focus.py (계좌 전체 심리 귀속)
 ↓
router.py (규칙 기반 2-way 라우팅)
  심리 패턴을 두 도메인에 흡수: 리벤지→진입오류, 처분효과→손절실패, 과매매→제외
  손절실패 신호 = (손절선 이탈 ∧ 2일 이상 버팀) ∨ 처분효과 dominant
  진입오류 신호 = 리벤지 dominant ∨ 보유 초반 손실 집중
 ↓
agent_registry.py (도메인 에이전트 실행 + 흡수된 심리 evidence 첨부)
 ↓
storage.py (SQLite 저장)
```

## 모듈

| 파일 | 역할 |
|---|---|
| `pipeline.py` | 파이프라인 진입점 (`run_pipeline`) |
| `analysis/classifier/` | 진입오류/손절실패 런타임 분류기 |
| `router.py` | 사이클 단위 규칙 기반 라우터 |
| `agent_registry.py` | 에이전트 어댑터 + 레지스트리 |
| `schema.py` | 내부 데이터 계약 |
| `storage.py` | SQLite 결과 저장 |
| `INTERACTION_POLICY.md` | 빈도/손실금액 집계 기반 사용자 선택 흐름 |

## 사용자 상호작용 정책

거래별 라우팅이 끝난 뒤 총괄은 문제 도메인별 빈도와 손실금액을 집계한다.
빈도 1위와 손실금액 1위가 다르면 웹에서 사용자에게 아래 질문을 띄운다.

```
어떤 문제를 중심으로 분석해볼까요?
[자주 반복된 문제] [손실 금액이 컸던 문제]
```

상세 정책은 [`INTERACTION_POLICY.md`](INTERACTION_POLICY.md)에 정리한다.

주의: `analysis/loss_screener`의 `selected`는 1순위 손실 거래뿐 아니라 2순위 기회손실 거래도
포함할 수 있다. 오케스트레이터가 손실 거래만 대상으로 삼을 때는 현재처럼
`filter_loss_cycles()`를 쓰거나, loss screener 결과에서 `tier == 1`만 사용해야 한다.

## 분류기 연결

`analysis/classifier/`는 오케스트레이터가 import해서 바로 호출하는 런타임 분류기다.
`pipeline.py`는 사이클별 진입맥락 피처를 `classify_entry()`에 넘기고,
반환된 `entry_error_score`와 `stop_loss_failure_score`를 `router.py`에 전달한다.

현재 피처 입력 경로:

```text
1. classifier_features_by_trade_id 인자로 전달된 실제 피처 우선 사용
2. 없으면 CSV 체결 경로에서 만들 수 있는 sparse fallback 피처 사용
3. 누락 피처는 analysis/classifier 모델 내부 median 대치로 처리
```

따라서 팀원이 실제 데이터 기반 피처 생성기를 붙이면 `run_pipeline(..., classifier_features_by_trade_id=...)`
형태로 주입하거나, `pipeline.py`의 fallback 어댑터만 교체하면 된다. 피처 주입 키는
`trade_id` 또는 `{code}@{entry_dt.isoformat()}` 둘 다 지원한다.

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
