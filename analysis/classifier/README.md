# Runtime Classifier — 진입오류 / 손절실패

오케스트레이터/서비스가 **import해서 바로 호출**하는 런타임 분류기.
손실 거래(또는 진입맥락)를 받아 `entry_error` / `stop_loss_failure` 점수를 돌려준다.

검증은 [`analysis/label_validation`](../label_validation/)이 끝냈고(①②③ 방법론),
이 모듈은 그 결과물인 **학습된 모델**을 fit/predict/save/load API로 노출한다.

## 사용 (서비스)

```python
from analysis.classifier import classify_entry

# 입력 = label_pipeline.CLASSIFIER_FEATURES (진입맥락 15 + 사후경로 3) 전체경로 dict
result = classify_entry(full_path_features)
# → {"entry_error_score": 0.78, "stop_loss_failure_score": 0.22,
#    "label": "entry_error", "confidence": 0.78}
```

> **용도 한정:** 이 분류기는 **분석단(청산된 손실거래 사후 분류)** 전용이다. 학습·추론
> 모두 전체경로 피처를 쓴다. **진입 전 예측(예정매수/현재보유)은 이 모델이 아니라
> predictor 의 룰 스코어러**가 담당한다 — 그 시점엔 사후경로 피처가 없기 때문.
> 진입맥락 피처(FEATURES, 15)만 넘기면 빠진 사후피처가 median 으로 조용히 대치돼
> 엉뚱한 점수가 나오니 그렇게 쓰지 말 것.

- 누락 피처는 NaN→median 대치로 처리된다(부분 피처도 호출 가능).
- 모델은 1회 로드 후 캐시(`load_default`)되어 반복 호출이 가볍다.
- 배치: `EntryStopClassifier.load().predict_batch(df)` → DataFrame.

## 오케스트레이터 연동

`router.score_cycle_candidates(...)`는 이미 `entry_min1_score`(0~1) 슬롯을 비워뒀다.
거기에 분류기의 `entry_error_score`를 넣으면 규칙 점수에 학습 점수가 합쳐진다:

```python
from analysis.classifier import entry_min1_score
scores = score_cycle_candidates(
    trade_id, ...,
    entry_min1_score=entry_min1_score(entry_features),   # ← 학습 분류기 기여
)
```

또는 두 점수를 그대로 `classifier_scores`로 부착해 라우팅 근거로 노출할 수 있다.

## 학습 / 재학습

```bash
python -m analysis.classifier.train            # 기본: 실 KOSPI min1 랜덤샘플(--source random)
python -m analysis.classifier.train --n 8000
python -m analysis.classifier.train --source designed   # 참고·검증용 설계 합성셋
```

학습 흐름(순환 방지): 결과신호 **군집**으로 라벨 생성 → **전체경로 피처**로 학습.
산출물: `artifacts/entry_stop_clf.joblib` (+ `.meta.json` — AUC·계수·학습소스).

## 모델 기준 = 랜덤 실데이터

`artifacts/`의 모델은 **실 KOSPI min1 랜덤샘플 + 군집라벨**로 학습된다(전체경로 피처, **AUC≈0.85**).
이게 아키텍처 기준이다. **설계 합성(`--source designed`, AUC≈0.97)은 "구조 있으면 작동한다"는
참고·검증용일 뿐 배포 기준이 아니다.** 실 사용자 거래로그가 확보되면 그걸로 갱신한다.

## 구조

```
model.py     EntryStopClassifier (fit/predict/predict_batch/save/load) + 헬퍼
train.py     학습 + 영속화 (--source random=실 min1 랜덤샘플[기본] / designed=참고용)
artifacts/   학습된 모델(.joblib) + 메타(.meta.json)  ← 랜덤 실데이터 기준
__init__.py  classify_entry / entry_min1_score / load_default / EntryStopClassifier
```
