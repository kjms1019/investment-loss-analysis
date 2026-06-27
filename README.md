# mirae_asset_agent — "왜 잃었지?" 복기 + 예측 시스템

완결된 국내주식 거래내역을 분석해 **손실 원인(진입오류 / 손절실패)** 을 진단하고,
같은 실수를 반복하려는 순간 **실시간으로 예측·경고**하는 멀티에이전트 시스템.

손실을 2대 도메인으로 분류하고(심리 패턴은 별도 유형이 아니라 두 도메인의 **해석**에 흡수), 분석으로 만든 라벨을
예측기의 정답으로 삼아 "분석 → 예측"으로 이어진다.

---

## 두 단계: 분석단 · 예측단

```
[분석단]  과거~오늘 전체 거래를 보고, 끝난 손실거래를 진단
[예측단]  오늘 일어나는 이벤트를, 그 순간 정보만으로 예측·경고
```

분석단은 **전체경로 정보**(거래가 끝난 뒤라 다 안다)로 분류한다.
예측단은 **현시점 정보만**(미래는 모른다)으로 예측한다. 정답은 분석단 분류 결과.

---

## 분석단 파이프라인 (`analysis/orchestrator/pipeline.py`)

| 단계 | 코드 | 역할 |
|---|---|---|
| 1. 파싱 | `common/parser.py` | CSV 체결 → 매수·매도 **사이클** 묶기 |
| 2. 손실 선별 | `filter_loss_cycles` / `loss_screener/` | 손실 사이클만. (α 시장제거 선별은 `loss_screener`에 있음) |
| 3. **분류** | `analysis/classifier` + `orchestrator/router.py` | **전체경로 피처 ML 분류기**가 손실거래마다 **entry_error / stop_loss_failure** 두 점수(합 1) 산출 → router가 **분류기 점수만으로** 라우팅 |
| 4. 보조 신호 | `psych_agent/` + `손절실패 엔진` | 심리 귀속(리벤지·처분효과)·손절선(ATR) 신호 계산 — **라우팅엔 미반영**. 도메인 에이전트의 *해석/분석*에만 쓰임(6단계) |
| 5. 총괄 질문 | `orchestrator/interaction.py` | 유형별 **빈도·손실금** 집계 → "자주 반복 vs 손실 큰 것, 뭘 먼저?" 사용자에게 질문 |
| 6. 도메인 분석 | `agents/entry-error-agent` / `agents/손절실패` | 고른 유형의 거래를 심층 분석·설명. 분류와 **같은 피처** 사용 + **심리 피처(리벤지/처분효과)로 설명 보강**, 손절은 ATR·breach·MAE로 분석 |
| 7. 반복/저장 | `interaction` + `user_profile/` | "다른 유형도 볼까?" (최대 2회) → 성향·반복패턴 리포트 DB 저장 |

> **라우팅 = 분류기 단독** (설계 의도). `pipeline`이 손실거래마다 `classifier_features_for_trade()`로
> min1에서 진입맥락 + 사후경로 피처를 계산해 분류기에 넣고, 그 **두 점수만으로** router가 라우팅한다.
> 심리귀속·손절엔진 신호는 **라우팅에 가산하지 않는다** — 심리는 도메인 에이전트 *해석*으로,
> 손절엔진(breach/delay)은 손절 에이전트 *분석*으로만 들어간다. (라벨축 `loss_early_ratio` 0.7
> 고정컷 룰도 제거 — 데이터 미지지 + 자기참조.)
> 모델은 **실 KOSPI min1 랜덤샘플 + 군집라벨**로 학습(아키텍처 기준, AUC≈0.85). 설계합성은
> 검증·참고용일 뿐 배포 기준 아님. 실 사용자 거래로그 확보 시 갱신.

---

## 예측단 (`analysis/predictor/`)

분석단이 만든 라벨을 **정답(teacher)** 으로, 예측기(student)가 **그 순간 정보만**으로 따라 예측한다.

| 예측기 | 이벤트(오늘) | 피처 | 계약 |
|---|---|---|---|
| **진입오류 예측기** | 매수하려는 순간 | 진입맥락(RSI·추격·범위위치…) | `EntryContext` → `predict_entry_risk` |
| **손절실패 예측기** | 보유종목 폭락해 손절선 접근하는 순간 | 현재 포지션(미실현손실·손절선돌파·낙폭·보유시간) | `PositionSnapshot` → `monitor_live_position` |

둘 다 look-ahead 없음(미래 미사용). 설계·검증은 `label_validation`의 step4·step5 참조.

---

## 피처 단일화 (분류 근거 = 분석 근거)

분류기와 **진입오류 에이전트**는 진입맥락 피처를 **단일 캐노니컬 함수**로 공유한다:
`analysis/label_validation/label_pipeline.entry_features_window()`.
→ "분류기가 range_position 0.9로 진입오류 판정" ↔ "에이전트가 같은 0.9로 추격매수 설명"이 항상 일치.
손절실패 에이전트는 보유경로 피처(ATR손절선·breach·MAE)를 쓴다(다른 영역).

---

## 폴더 구조

| 폴더 | 역할 |
|---|---|
| `analysis/common/` | 공통 스키마·파서(사이클)·어댑터 |
| `analysis/loss_screener/` | 시장제거 손실 선별 (α 기준) |
| `analysis/psych_agent/` | 심리패턴 귀속 (리벤지/처분효과/과매매) |
| `analysis/orchestrator/` | 총괄 — 라우팅·총괄질문·결과저장 |
| `analysis/label_validation/` | **분류기·예측기 설계·검증** (step1~5, 공유 피처 코어) |
| `analysis/classifier/` | **런타임 분류기** — 서비스가 import해 호출 |
| `analysis/predictor/` | **런타임 예측기** — 진입/보유 두 이벤트 모드 |
| `analysis/user_profile/` | 성향·반복패턴 프로파일 저장 |
| `analysis/collector/` | 키움 REST API 1분봉 수집기 |
| `agents/entry-error-agent/` | 진입오류 도메인 에이전트 |
| `agents/손절실패/` | 손절실패 도메인 에이전트 (ATR 손절선) |
| `web/` | Next.js 대시보드 |

---

## 빠른 시작

```bash
# 분석단 파이프라인
python -c "
from analysis.orchestrator import run_pipeline
print(run_pipeline('my_trades.csv', broker='kiwoom').to_dict())
"

# 분류기 학습/호출 (분석단 — 입력은 CLASSIFIER_FEATURES 전체경로 dict)
python -m analysis.classifier.train
python -c "from analysis.classifier import classify_entry; from analysis.label_validation.label_pipeline import CLASSIFIER_FEATURES; print(classify_entry({k: 0.0 for k in CLASSIFIER_FEATURES}))"

# 설계·검증 재현 (step1~5)
python analysis/label_validation/step1_threshold_check.py --sweep
python analysis/label_validation/step4_predictor.py

# 웹 대시보드
cd web && npm install && npm run dev
```

---

## 상세 문서

| 문서 | 내용 |
|---|---|
| [analysis/label_validation/README.md](analysis/label_validation/README.md) | **분류기·예측기 설계·검증 + 전체 결과 숫자** |
| [analysis/classifier/README.md](analysis/classifier/README.md) | 런타임 분류기 API·연동 |
| [analysis/predictor/README.md](analysis/predictor/README.md) | 런타임 예측기 두 모드 |
| [analysis/orchestrator/README.md](analysis/orchestrator/README.md) | 오케스트레이터 구조 |
| [agents/entry-error-agent/SPEC.md](agents/entry-error-agent/SPEC.md) | 진입오류 에이전트 명세 |
| [agents/손절실패/DESIGN.md](agents/손절실패/DESIGN.md) | 손절실패 에이전트 설계 |

---

## 데이터

KOSPI 약 800종목, 1분봉 약 1년치. **GitHub Release**로 배포(`analysis/data/`는 gitignore).
Release zip을 `analysis/data/`에 풀면 `analysis/data/min1/{code}.parquet` 구조가 된다.

데이터를 저장소 밖(공유 드라이브 등)에 두려면 `.env`의 `MIRAE_DATA_ROOT`로 상위 폴더를
지정한다(미지정 시 `analysis/data`). 그 폴더 아래 `min1/`·`.cache/`가 있어야 한다.

## 검증/오프라인 (LLM 토큰 0)

`MIRAE_DISABLE_LLM=1`이면 키가 있어도 모든 LLM 문장 생성(리포트·총괄 대화·알림·심리)이
룰/템플릿 폴백으로 떨어진다. 유저플로우/데이터 검증 시 토큰을 쓰지 않고 돌릴 수 있다.
(리포트 본문만 막으려면 `build_*_summary(..., llm=False)`.)
