"""'내 성향' 리포트 문장화 (룰+LLM 하이브리드의 LLM 단).

psych_agent/diagnose.py 와 같은 원칙:
  · PatternFact(숫자·종목명)는 그대로 두고, 여기서는 '문장'만 입힌다.
  · 공용 LLM 창구(analysis.llm)로 Qwen 호출, 실패하면 결정적 템플릿 폴백
    → 키 없이도 그대로 구동된다.
  · LLM은 새 수치를 만들지 않는다. JSON만 출력하도록 강하게 제약한다.

이 모듈이 받는 입력(TendencyReportInput)과 돌려주는 출력(TendencyReportText)의
JSON 형태가 곧 "DB → LLM" 사이의 파일 계약이다. 분류기가 최종본이 아니어도
이 계약은 안 바뀐다 — tendency_builder.py 가 PatternFact 를 어떻게 채우든
여기는 그 구조만 알면 된다.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from .schema import LossReportSummary
from .tendency_builder import build_pattern_facts
from .tendency_schema import (
    PatternFact,
    TendencyCard,
    TendencyCardText,
    TendencyReport,
    TendencyReportInput,
    TendencyReportText,
)


@dataclass
class Config:
    llm_model: str = "claude-sonnet-4-6"
    use_llm: bool = True
    max_cards: int = 6  # 화면에 한 번에 보여줄 카드 수 상한 (matched_count 내림차순 상위 N)


_SEVERITY_KR = {"none": "해당 없음", "weak": "약", "moderate": "중", "strong": "강"}


# ─────────────────────────────────────────────────────────────────
# 입력(JSON) 빌드 — "DB → LLM" 파일 계약
# ─────────────────────────────────────────────────────────────────
def build_input(
    summary: LossReportSummary,
    *,
    period_from: str | None = None,
    period_to: str | None = None,
    config: Config | None = None,
) -> TendencyReportInput:
    config = config or Config()
    facts = build_pattern_facts(summary)[: config.max_cards]
    dominant = max(summary.count_by_agent, key=summary.count_by_agent.get) if summary.count_by_agent else "unknown"
    return TendencyReportInput(
        user_id=summary.scope_id,
        generated_at=summary.generated_at,
        period_from=period_from,
        period_to=period_to,
        dominant_problem_type=dominant,
        total_loss_trades=summary.total_loss_trades,
        patterns=facts,
    )


# ─────────────────────────────────────────────────────────────────
# 템플릿 폴백
# ─────────────────────────────────────────────────────────────────
def _template_generate(report_input: TendencyReportInput) -> TendencyReportText:
    cards = []
    for fact in report_input.patterns:
        tip = fact.correction_hint or f"{fact.title_hint} 패턴이 반복되고 있어요."
        cohort_sentence = None
        if fact.cohort:
            cohort_sentence = f"비슷한 패턴은 다른 사용자의 {fact.cohort['match_rate_pct']}%에서도 나타나요."
        cards.append(
            TendencyCardText(
                pattern_key=fact.pattern_key,
                title=fact.title_hint,
                tip=tip,
                cohort_sentence=cohort_sentence,
            )
        )

    if report_input.patterns:
        top = report_input.patterns[0]
        headline = "당신은 이런 패턴을 반복하고 있어요"
        subheadline = (
            f"이번 기간 손실의 상당 부분은 '{top.title_hint}' 같은 습관에서 나왔어요. "
            "비난하려는 게 아니라, 다음 거래에서 한 가지만 바꿔보자는 거예요."
        )
    else:
        headline = "아직 뚜렷한 반복 패턴이 보이지 않아요"
        subheadline = "거래가 더 쌓이면 패턴 분석이 더 정확해져요."

    return TendencyReportText(
        headline=headline,
        subheadline=subheadline,
        insight_banner="이 패턴들이 곧 실시간 알림(예측기)의 학습 근거가 돼요.",
        cards=cards,
        engine="template",
    )


# ─────────────────────────────────────────────────────────────────
# LLM (Anthropic)
# ─────────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """\
너는 국내주식 거래 복기 서비스 '왜 잃었지?'의 "내 성향" 리포트 작성 에이전트다.
입력은 룰/통계 엔진이 이미 계산한 사실(JSON, patterns 배열)이다.

절대 원칙:
1. 입력에 없는 숫자·비율·종목명을 절대 새로 만들지 않는다. 있는 값만 문장으로 옮긴다.
2. 비난 금지: "당신이 잘못했다"가 아니라 "이런 행동 패턴이 관찰된다"는 관찰자 시점으로 쓴다.
3. 정규화 프레이밍: 각 pattern의 cohort.match_rate_pct 값이 주어지면, "다른 OO%의
   사용자도 같은 패턴을 반복하고 있다"는 문장을 cohort_sentence에 자연스럽게 담아
   사용자가 유독 못해서가 아니라 흔한 습관임을 알게 한다. cohort 가 null이면
   cohort_sentence는 null로 둔다 (지어내지 않는다).
4. 각 카드의 title은 12~20자 명사형 패턴명(title_hint를 자연스럽게 다듬되 의미는 유지),
   tip은 40자 내외 행동 교정 문장 1개(correction_hint의 취지를 유지하며 다듬기만 함).
5. headline은 한 줄 요약, subheadline은 2문장 이내로 비난 없이 따뜻하게.
6. 아래 JSON 스키마와 정확히 같은 키만 가진 JSON 객체 하나만 출력한다.
   다른 텍스트, 마크다운, 설명을 절대 덧붙이지 않는다.

출력 스키마:
{
  "headline": string,
  "subheadline": string,
  "insight_banner": string,
  "cards": [
    {"pattern_key": string, "title": string, "tip": string, "cohort_sentence": string | null}
  ]
}
cards 배열의 pattern_key는 입력 patterns 배열의 pattern_key와 1:1로 정확히 일치해야 한다.\
"""


def _llm_generate(report_input: TendencyReportInput, config: Config) -> TendencyReportText | None:
    if not config.use_llm or not report_input.patterns:
        return None

    # 공용 LLM 창구(.env 로딩·키/엔드포인트/폴백 일원화) 사용
    from analysis.llm import engine_tag, generate, model_for, strip_code_fence
    model = os.environ.get("TENDENCY_LLM_MODEL") or model_for("default")
    user_payload = json.dumps(report_input.to_dict(), ensure_ascii=False, indent=2)

    text = generate(_SYSTEM_PROMPT, user_payload, kind="default", model=model,
                    max_tokens=1500, fallback="")
    if not text:
        return None  # 키 없음/차단 스위치/호출 실패 → 템플릿 폴백

    try:
        parsed = json.loads(strip_code_fence(text))
        cards = [
            TendencyCardText(
                pattern_key=c["pattern_key"],
                title=c["title"],
                tip=c["tip"],
                cohort_sentence=c.get("cohort_sentence"),
            )
            for c in parsed["cards"]
        ]
        return TendencyReportText(
            headline=parsed["headline"],
            subheadline=parsed["subheadline"],
            insight_banner=parsed["insight_banner"],
            cards=cards,
            engine=engine_tag(model=model),
        )
    except Exception as e:  # noqa: BLE001 - 폴백을 위해 광범위 캐치 (파싱 실패 포함)
        return TendencyReportText(headline="", subheadline="", insight_banner="", engine="llm_error", llm_error=str(e))


def generate_text(report_input: TendencyReportInput, config: Config | None = None) -> TendencyReportText:
    config = config or Config()
    result = _llm_generate(report_input, config)
    if result and result.engine.startswith("llm:"):
        return result
    fallback = _template_generate(report_input)
    if result and result.engine == "llm_error":
        fallback.llm_error = result.llm_error
    return fallback


# ─────────────────────────────────────────────────────────────────
# 병합: PatternFact(사실) + TendencyCardText(문장) → TendencyCard(렌더용)
# ─────────────────────────────────────────────────────────────────
def _merge(fact: PatternFact, text_by_key: dict[str, TendencyCardText]) -> TendencyCard:
    text = text_by_key.get(fact.pattern_key)
    title = text.title if text else fact.title_hint
    tip = text.tip if text else fact.correction_hint
    cohort_sentence = text.cohort_sentence if text else None
    return TendencyCard(
        pattern_key=fact.pattern_key,
        category=fact.category,
        tag=fact.tag,
        title=title,
        matched_count=fact.matched_count,
        total_eligible_count=fact.total_eligible_count,
        severity=fact.severity,
        representative_trades=fact.representative_trades,
        tip=tip,
        cohort_sentence=cohort_sentence,
    )


def generate_tendency_report(
    summary: LossReportSummary,
    *,
    period_from: str | None = None,
    period_to: str | None = None,
    config: Config | None = None,
) -> TendencyReport:
    config = config or Config()
    report_input = build_input(summary, period_from=period_from, period_to=period_to, config=config)
    text = generate_text(report_input, config)
    text_by_key = {c.pattern_key: c for c in text.cards}
    cards = [_merge(fact, text_by_key) for fact in report_input.patterns]

    return TendencyReport(
        user_id=report_input.user_id,
        generated_at=report_input.generated_at,
        headline=text.headline,
        subheadline=text.subheadline,
        insight_banner=text.insight_banner,
        cards=cards,
        engine=text.engine,
    )
