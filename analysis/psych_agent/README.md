# 준모 · 심리/과매매 분석 에이전트

"왜 잃었지?" 복기 시스템의 **심리 매매** 갈래. 완결된 국내주식 거래내역을
사후 복기해 세 가지 손실 패턴을 진단하고 개인화 교정 규칙을 제시한다.
(매매 추천 아님 → 규제 리스크 낮음)

> 📖 **전체 파이프라인(손실 선별 → 심리 귀속 → 웹)을 한 문서로 보려면 [../PIPELINE.md](../PIPELINE.md).**
> 이 README는 심리 에이전트 모듈 자체를 다룬다.

## 두 가지 사용 모드

1. **계좌 전체 패턴** (`agent.py` `PsychAgent`): 거래 전체에서 3패턴의 강/중/약을 본다(큰 그림).
2. **손실거래 단위 귀속** (`focus.py` `attribute_losses`): 오케스트레이션이 선별한 손실 거래
   각각에 어떤 심리 유형이 원인인지 귀속한다. **이게 실제 라우팅에 쓰이는 핵심 경로.**
   원칙: 손실 거래 = 설명 anchor, 전체 거래 = 패턴 계산 context (→ [../PIPELINE.md](../PIPELINE.md) §3-4).
   psych_agent 는 선별기(loss_screener)에 의존하지 않는다 — 입력은 사이클 키 목록뿐.

## 진단하는 3가지 패턴

| 유형 | 측정 축 | 측정법 | 학술 근거 |
|------|---------|--------|-----------|
| **리벤지 트레이딩** | 결정/시간 | 직전 손실 → 임계시간(기본 30분) 내 재진입 + 포지션 확대 + 재손실 (1/2/3점) | 행동재무 문헌 |
| **과매매** | 결정/빈도 | 연 회전율 ≥ 250% (절대) + 월 거래빈도 개인 중앙값 대비 배수 | Barber & Odean (2000) |
| **처분효과** | 포지션/보유기간 | PGR vs PLR (실현이익률 vs 실현손실률) + 보유기간 격차 | Shefrin & Statman (1985), Odean (1998) |

처분효과의 평가손익(PGR/PLR 분모)은 **매도 시점의 실제 1분봉 종가**로 판정한다
(`analysis/data/min1/{code}.parquet`).

## 구조 (룰 + LLM 하이브리드)

```
거래내역(CSV) ─► preprocess ─► [포지션 사이클 / 매도 이벤트]
                                  │
                  ┌───────────────┼────────────────┐
              detect_revenge  detect_overtrading  detect_disposition   ← 룰/통계 = 팩트
                  └───────────────┼────────────────┘
                              diagnose ─► (LLM 문장화 / 없으면 템플릿 폴백)
```

- **매핑은 AI 판단이 아님**: 데이터 존재 여부 필터 + 조건부 실행(누락 방지).
- **LLM은 수치를 만들지 않음**: 룰 엔진이 계산한 팩트만 해석·문장화.
- LLM 키가 없어도 템플릿 폴백으로 **그대로 구동**된다.

## 실행

```bash
cd analysis
source venv/bin/activate     # pandas / numpy / pyarrow 만 필요

# 더미 데이터(실 min1 가격 기반) 생성 후 분석
python -m psych_agent.run --demo                       # 세 패턴 혼합(현실적)
python -m psych_agent.run --demo --scenario disposition # 처분효과만 깨끗하게
python -m psych_agent.run --demo --scenario revenge
python -m psych_agent.run --demo --scenario overtrading

# 실제 거래내역 CSV 분석 (컬럼: datetime,code,name,side,qty,price)
python -m psych_agent.run --trades my_trades.csv --json out.json
```

### LLM 진단 켜기 (선택)

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-...
export PSYCH_LLM_MODEL=claude-sonnet-4-6   # 선택
python -m psych_agent.run --demo            # 진단 엔진이 anthropic:... 로 표시됨
```

## 입력 거래내역 스키마

| 컬럼 | 설명 |
|------|------|
| `datetime` | 체결 시각 |
| `code` | 종목코드 6자리 |
| `name` | 종목명 |
| `side` | `BUY` / `SELL` |
| `qty` | 체결 수량 |
| `price` | 체결 단가 |

평균단가(이동평균법)로 사이클을 묶으며, 한 종목 보유수량이 0→양수→0 으로
돌아오면 한 사이클(라운드트립)로 본다. 기간 말 미청산 포지션은 평가 대상으로 남는다.

## 파일

- `config.py` — 임계값/경로
- `schema.py` — Trade / PositionCycle / SellEvent / TypeFinding
- `preprocess.py` — 거래 → 사이클·매도이벤트 (계좌 1회 리플레이)
- `prices.py` — min1 종가 조회(merge_asof)
- `detectors/` — revenge / overtrading / disposition (계좌 전체 패턴 검출)
- `focus.py` — **손실거래별 심리 귀속** `attribute_losses()` (라우팅 핵심, screener 비의존)
- `diagnose.py` — LLM 문장화 + 템플릿 폴백 + 유형별 교정 템플릿
- `agent.py` — 서브 오케스트레이터 (`PsychAgent`, 계좌 전체)
- `dummy_data.py` — 실 min1 기반 더미 거래 생성
- `run.py` — 계좌 전체 분석 CLI
- `export_web.py` — 계좌 전체 분석 → 웹 JSON

> 손실선별기와 묶은 전체 파이프라인은 `../pipeline.py`, 웹 익스포트는 `../web_export.py`.
