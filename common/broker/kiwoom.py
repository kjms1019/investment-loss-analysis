"""키움증권 CSV 컬럼 매핑.

키움 HTS 거래내역 내보내기 기준.
컬럼명이 바뀌면 여기만 수정하면 됨.
"""

# 키움 CSV 컬럼명 → 공통 RawTrade 필드명
COLUMN_MAP = {
    "체결일시":   "datetime",
    "종목코드":   "code",
    "종목명":     "name",
    "매매구분":   "side",     # "매수" | "매도"
    "체결수량":   "qty",
    "체결단가":   "price",
    "수수료":     "fee",
}

# 키움 매매구분 값 → 공통 side 값
SIDE_MAP = {
    "매수": "BUY",
    "매도": "SELL",
}

DATETIME_FORMAT = "%Y%m%d%H%M%S"   # 키움 체결일시 포맷
