# Runtime Classifier — 진입오류 / 손절실패

오케스트레이터/서비스가 **import해서 바로 호출**하는 런타임 분류기.
손실 거래(또는 진입맥락)를 받아 `entry_error` / `stop_loss_failure` 점수를 돌려준다.

검증은 [`analysis/label_validation`](../label_validation/)이 끝냈고(①②③ 방법론),
이 모듈은 그 결과물인 **학습된 모델**을 fit/predict/save/load API로 노출한다.

## 사용 (서비스)

```python
from analysis.classifier import classify_entry

result = classify_entry(entry_features)   # entry_features: label_pipeline.FEATURES 키 dict
# → {"entry_error_score": 0.78, "stop_loss_failure_score": 0.22,
#    "label": "entry_error", "confidence": 0.78}
```

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
python -m analysis.classifier.train            # 기본: 설계 합성 검증셋으로 학습
python -m analysis.classifier.train --n 8000
```

학습 흐름(순환 방지): 결과신호 **군집**으로 라벨 생성 → **진입맥락 피처**로 학습.
산출물: `artifacts/entry_stop_clf.joblib` (+ `.meta.json` — AUC·계수·학습소스).

## ⚠️ 현재 모델은 placeholder

`artifacts/`의 모델은 **설계 합성 검증셋**으로 학습됐다(AUC≈0.97). 실거래 매매내역이 없어
임시로 둔 것이며, 파이프라인 배선·API 검증용이다. **실거래 라벨이 확보되면 재학습 필요.**
(설계셋은 파이프라인 작동 검증용 — 실제 시장 구조·임계값 증명엔 못 씀. label_validation README 참고.)

## 구조

```
model.py     EntryStopClassifier (fit/predict/predict_batch/save/load) + 헬퍼
train.py     학습 + 영속화 (소스=설계 합성, 실거래 생기면 --source real 추가)
artifacts/   학습된 모델(.joblib) + 메타(.meta.json)  ← placeholder
__init__.py  classify_entry / entry_min1_score / load_default / EntryStopClassifier
```
