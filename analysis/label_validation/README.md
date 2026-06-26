# 진입오류 / 손절실패 분류기 — 라벨 검증 파이프라인

손실 거래를 **진입오류(entry_error)** / **손절실패(stop_loss_failure)** 로 가르는 분류기의
**라벨 정의 + 검증** 코드. 핵심 질문 4개(라벨링·모델식·임계값·자기반복)를 실데이터로 답한다.

## 핵심 설계

- **라벨 = 결과(사후) 신호**, **피처 = 진입시점 맥락** → 둘을 분리해 **자기반복(순환) 방지**.
- 임계값은 손으로 안 박는다. **군집화가 경계를 결정** (단일 고정컷 0.7은 ①에서 기각).
- 도구: 비지도(군집) = 라벨 생성·축 정당화 / 지도(로지스틱·RF) = 진입맥락→유형 예측.

## 방법론 체인 (①②③)

| 단계 | 스크립트 | 무엇을 증명 | 결과 |
|---|---|---|---|
| **①** | `step1_threshold_check.py` | 단일 고정컷(0.7) 적절한가 | ❌ 경계가 보유기간 따라 0→0.44 미끄러짐, 0.7은 모든 구간 CI 밖 |
| **②** | `step2_cluster_axes.py` | 왜 이 두 축으로 설계하나 | ✅ 실데이터서 2축 군집 → BIC 2성분 우세 + 실루엣 0.56 = 구조 실재 |
| **③** | `step3_classifier_real.py` | 랜덤데이터로 분류 되나 | ❌ AUC≈0.5 (피처15·RF로도) = **데이터 한계** (인과 없음) |
| **③'** | `step3b_classifier_designed.py` | 구조 있으면 파이프라인 작동하나 | ✅ 설계 검증셋서 군집정확도 0.98·AUC 0.96 |

**한 줄 서사**: 단일컷은 실데이터서 부적절(①) → 두 축에 구조 실재 확인(②) →
그 축으로 라벨/분류 시도하나 랜덤데이터엔 인과 없어 AUC 0.5(③) →
구조 주입한 설계셋에선 같은 코드가 AUC 0.96(③') = **막힌 건 데이터지 파이프라인 아님.**
실전 적용엔 실거래 매매내역 필요.

## 정직성 경계 (발표 시 필수)

- **③'는 '설계된 검증셋'이라 명시.** 랜덤 아님. 파이프라인 작동 검증까지만.
- ③'로 **임계값(0.7 등)·실제 시장 구조는 증명 불가**(순환). 축 정당성은 ②(실데이터)가 제공.
- **데이터 = 축 정당성 / 이론(design-brief·논문) = 축 의미(진입오류/손절실패 명명).**

## 구조

```
label_pipeline.py   공유 코어 — 신호/피처/샘플러/군집/설계합성
step1_threshold_check.py     ① 고정컷 검증 + 보유기간 sweep(--sweep)
step2_cluster_axes.py        ② 실데이터 2축 군집 (축 선택 근거)
step3_classifier_real.py     ③ 실/랜덤 분류기 (데이터 한계)
step3b_classifier_designed.py ③' 설계 검증셋 (파이프라인 작동)
```

빌딩블록(코어):
- `outcome_signals()` — loss_early_ratio, trough_time_frac, post_breach_run (라벨용)
- `entry_features()` — rsi/range_position/momentum/vol/volume 등 15개 (분류기용)
- `sample_signals_only()` / `sample_with_features()` — 실 min1 손실거래 샘플러
- `cluster_labels()` — 다중신호 GMM(K=2) → entry_error/stop_loss_failure + 품질지표
- `generate_designed()` — 정답 구조 주입 합성 생성기

## 데이터 준비 (다른 브랜치/PC에서 돌릴 때)

분봉 데이터(~1GB)는 **git에 안 올라간다**(`.gitignore: /analysis/data/`). 배포처는 **GitHub Release**.
아무 브랜치에서든 아래로 데이터를 갖춘다:

**A. Release zip 받아서 풀기 (권장)**
1. 저장소 **Releases** 에서 `kospi_min1_1y_YYYYMMDD.zip` 다운로드 (private라 로그인 필요).
2. `analysis/data/` 에 압축 해제 → `analysis/data/min1/{code}.parquet` 구조가 됨.
   ```bash
   # 예 (Git Bash / PowerShell Expand-Archive 등 무엇이든)
   unzip kospi_min1_1y_20260623.zip -d analysis/data/
   ```
3. 확인: `ls analysis/data/min1/*.parquet | wc -l`  → 798개.

**B. 직접 재수집** — 키움 REST API로 다시 모은다(`.env`에 키 필요):
```bash
python analysis/collector/collect_min1.py   # → analysis/data/min1/ 에 저장
```

> 즉 코드는 git, 데이터는 Release. 브랜치를 바꿔도 `analysis/data/`는 로컬에 그대로 남아 재사용된다.

## 실행

```bash
# 데이터: analysis/data/min1/{code}.parquet (위 '데이터 준비' 참고)
python analysis/label_validation/step1_threshold_check.py --sweep
python analysis/label_validation/step2_cluster_axes.py
python analysis/label_validation/step3_classifier_real.py
python analysis/label_validation/step3b_classifier_designed.py
```

산출물(JSON)은 `analysis/data/_label_validation/` (gitignored).
의존성: numpy, pandas, scikit-learn, scipy (analysis/requirements.txt).
```
