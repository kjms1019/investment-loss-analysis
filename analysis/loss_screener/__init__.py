"""오케스트레이션 상단: 시장 제거 손실 거래 선별기.

'왜 잃었지?' 시스템에서 사용자의 1년치 거래를 받자마자 가장 먼저 도는 단계.
절대손익이 아니라 '시장 영향을 제거한 초과손실(abnormal return)'로 복기 대상을
고른다 → 이후 다중분류기 → 진입/손절/심리 에이전트로 라우팅.

벤치마크 = 보유 종목 유니버스의 동일가중 합성지수(추가 수집 불필요).
"""

from .market_index import build_market_index, load_market_index
from .screener import screen_trades, ScreenResult

__all__ = [
    "build_market_index",
    "load_market_index",
    "screen_trades",
    "ScreenResult",
]
