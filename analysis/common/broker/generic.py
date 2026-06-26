"""범용 CSV 컬럼 매핑.

증권사가 명시되지 않았을 때 사용.
공통 RawTrade 필드명과 동일한 컬럼을 그대로 사용한다고 가정.
"""

COLUMN_MAP = {
    "datetime": "datetime",
    "code":     "code",
    "name":     "name",
    "side":     "side",
    "qty":      "qty",
    "price":    "price",
    "fee":      "fee",
}

SIDE_MAP = {
    "BUY":  "BUY",
    "SELL": "SELL",
    "buy":  "BUY",
    "sell": "SELL",
}

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
