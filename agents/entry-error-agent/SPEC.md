# 요약 명세

## 에이전트 역할

진입오류 분석 에이전트는 종료된 거래를 대상으로 진입 당시의 시장 상태와 가격 맥락을 분석해, 진입이 불리했을 가능성과 그 이유를 복기 리포트로 설명한다.

## 입력 데이터 스키마

거래 데이터 표준 컬럼 예시:

- `trade_id`, `user_id`, `symbol`, `market_type`, `asset_class`, `side`
- `entry_timestamp`, `exit_timestamp`, `entry_price`, `exit_price`
- `quantity`, `realized_pnl`, `realized_pnl_pct`, `fees`
- `strategy_tag`, `memo`

OHLCV 시세 데이터 표준 컬럼 예시:

- `symbol`, `trade_date`, `open`, `high`, `low`, `close`
- `volume`, `turnover`, `adjusted`

계산 보조 지표 예시:

- 이동평균, 수익률, 최근 고가/저가, 평균 거래량, 갭, 진입가 위치

## 전처리 및 피처

초기 MVP에서 고려할 피처 후보:

- `ma_5`, `ma_20`, `ma_20_slope`, `rsi_14`
- `ret_1d`, `ret_3d`, `ret_5d`, `ret_20d`
- `high_20d`, `low_20d`
- `avg_volume_20d`, `avg_turnover_20d`
- `gap_pct`, `entry_vs_open_pct`, `entry_vs_ma20_pct`
- `entry_vs_high20_ratio`, `range_position_20d`

## 시장/가격 상태 4분류

- 상승/돌파
- 눌림목 조정
- 하락/급락
- 횡보/박스권

## 진입오류 라벨 후보

- 정상 진입
- 과도한 가격 상승 후 추격 진입
- 전일 수급 확인 부족 상태의 고점 접근 진입
- 단기 과열 연장 구간 진입
- 지지 확인 없는 눌림목 조기 진입
- 수급 안정 없는 눌림목 진입
- 하락 추세 중 급등 기대 매수
- 반등 확인 없는 하락 추세 진입
- 박스권 상단 추격 진입
- 저유동성 박스권 추격 진입
- 판단 보류

## 다중 라벨 방식

하나의 거래에는 여러 라벨이 동시에 부여될 수 있다. 각 라벨은 적용 여부, 근거 피처, 신뢰도, 제외 사유를 함께 기록한다.

## 위험 점수

`entry_error_risk_score`는 0~100 범위의 진입오류 위험 점수로 정의한다. 점수는 수익률이 아니라 진입 당시의 가격 위치, 추세, 변동성, 거래량 조건을 기준으로 계산해야 한다.

## 출력 JSON 주요 필드

- `trade_id`
- `symbol`
- `analysis_version`
- `analyzable`
- `analysis_status`
- `insufficient_reasons`
- `data_quality`
- `input_snapshot`
- `derived_features`
- `state_classification`
- `label_results`
- `rejected_labels_with_reason`
- `entry_error_risk_score`
- `severity`
- `summary`
- `review_rules`
- `disclaimers`

## 자연어 복기 리포트 방향

리포트는 사용자의 다음 매매를 지시하지 않는다. 대신 해당 거래가 어떤 시장 상태에서 이루어졌고, 어떤 진입 리스크가 있었는지를 사후 복기 관점에서 설명한다.

## 주의사항

- 손익 결과만으로 진입 품질을 판단하지 않는다.
- 진입 이후 데이터로 진입 당시 판단을 평가하지 않는다.
- 데이터가 부족하면 판단 보류를 명시한다.
- 실제 분석 로직은 이 명세 이후 단계에서 구현한다.
