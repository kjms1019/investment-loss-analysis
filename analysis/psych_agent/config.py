"""에이전트 임계값·경로 설정.

모든 임계값은 문헌 기준을 기본값으로 두되, 인스턴스에서 덮어쓸 수 있다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# analysis/ 디렉터리 (이 파일 기준 한 단계 위)
ANALYSIS_DIR = Path(__file__).resolve().parents[1]
MIN1_DIR = ANALYSIS_DIR / "data" / "min1"


@dataclass
class Config:
    # ── 데이터 경로 ──────────────────────────────────────────────
    min1_dir: Path = MIN1_DIR

    # ── 리벤지 트레이딩 ─────────────────────────────────────────
    # 직전 사이클이 손실일 때, 다음 진입까지 이 간격 미만이면 시간조건 충족.
    revenge_window_min: int = 30
    # 점수: 시간조건(1) → +포지션확대(2) → +재손실(3). 이 점수 이상이면 '강'.
    revenge_strong_score: int = 3

    # ── 과매매 (Barber & Odean 2000) ────────────────────────────
    # 논문상 상위 과매매 그룹의 연 회전율 ≈ 258%. 절대 임계로 차용.
    overtrade_annual_turnover: float = 2.5  # 250%
    # 개인 월 거래빈도 중앙값 대비 이 배수를 넘는 달이 있으면 '집중 과매매월'.
    overtrade_freq_multiple: float = 2.0

    # ── 처분효과 (Odean 1998) ───────────────────────────────────
    # PGR - PLR 가 이 값보다 크면 처분효과 양(+)으로 본다.
    disposition_min_gap: float = 0.05

    # ── LLM 진단 문장화 ─────────────────────────────────────────
    # 공용 창구(analysis.llm)가 호출 가능하면 LLM 사용, 아니면 템플릿 폴백.
    # 모델은 환경변수 PSYCH_LLM_MODEL 로도 덮어쓸 수 있다.
    llm_model: str = "qwen/qwen3-32b"
    use_llm: bool = True  # False 면 무조건 템플릿

    # 거래 1건당 가정 수수료+세금률 (더미/팩트 계산용, 매도 기준 0.2%)
    fee_rate: float = 0.002

    def min1_path(self, code: str) -> Path:
        return self.min1_dir / f"{code}.parquet"

    def has_min1(self, code: str) -> bool:
        return self.min1_path(code).exists()
