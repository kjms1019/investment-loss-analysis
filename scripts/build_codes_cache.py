"""종목코드 캐시(.cache/kospi_codes.csv) 생성 — 키움 API 키 없이.

`analysis/collector/universe.py` 는 키움 REST API로 이 파일을 만든다. 하지만 키움 키는
수집 담당자만 갖고 있고, min1 Release 에도 이 캐시는 들어있지 않다. 키가 없는 팀원·심사자·
배포 환경에서 KRX 상장목록으로 동일한 파일을 재구성하기 위한 스크립트다.

이 파일이 없으면 `load_name_to_code()` 가 빈 dict 를 돌려주고, 종목명을 코드로 바꾸지
못한 거래가 **에러 없이 조용히 스킵**된다 — /api/all-trades 와 /api/alerts 가 빈 배열이
되는 원인.

    python scripts/build_codes_cache.py

min1 parquet 이 있는 종목만 기록한다(있지도 않은 종목을 매핑해봐야 쓸모없음).
현재 상장목록에서 빠진 종목(상장폐지·이전상장)은 KRX 상폐목록에서 보강한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.common.paths import CACHE_DIR, CODES_CSV, MIN1_DIR  # noqa: E402


def _listing(market: str) -> pd.DataFrame:
    import FinanceDataReader as fdr

    df = fdr.StockListing(market)
    code_col = "Code" if "Code" in df.columns else "Symbol"
    out = df[[code_col, "Name"]].rename(columns={code_col: "code", "Name": "name"})
    out["code"] = out["code"].astype(str).str.zfill(6)
    return out.dropna()


def build() -> pd.DataFrame:
    have = {p.stem for p in MIN1_DIR.glob("*.parquet")}
    if not have:
        raise SystemExit(f"min1 parquet 이 없다: {MIN1_DIR}\nREADME 의 데이터 셋업 2번을 먼저 수행할 것.")

    listed = _listing("KOSPI")
    out = listed[listed["code"].isin(have)]

    # 상장폐지·이전상장 종목은 현재 상장목록에 없다. 수집 시점에는 살아있었으므로 보강한다.
    missing = have - set(out["code"])
    if missing:
        try:
            delisted = _listing("KRX-DELISTING")
            extra = delisted[delisted["code"].isin(missing)].drop_duplicates("code")
            out = pd.concat([out, extra], ignore_index=True)
            missing -= set(extra["code"])
        except Exception as e:  # noqa: BLE001 - 상폐목록 조회 실패해도 나머지는 살린다
            print(f"  경고: 상폐목록 조회 실패 ({e}) — 미매칭 {len(missing)}종목은 건너뜀")

    out = out.drop_duplicates("code").sort_values("code")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(CODES_CSV, index=False, encoding="utf-8")

    print(f"min1 종목 {len(have)} / 매핑 {len(out)} → {CODES_CSV}")
    if missing:
        print(f"  이름을 못 찾은 코드 {len(missing)}: {sorted(missing)}")
    return out


if __name__ == "__main__":
    build()
