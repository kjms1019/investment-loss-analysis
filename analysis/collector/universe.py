"""코스피 종목 유니버스 확보.

우선 ka10099(종목정보 리스트)로 코스피 전 종목을 받아 캐싱한다.
스키마가 환경에 따라 다를 수 있으므로, 실패 시 사용자가 직접 만든
data/.cache/kospi_codes.csv (code,name 헤더) 를 폴백으로 사용한다.
"""
from __future__ import annotations

import csv

from . import config
from .kiwoom_client import KiwoomClient

_CACHE = config.CACHE_DIR / "kospi_codes.csv"


def _fetch_via_api(client: KiwoomClient) -> list[tuple[str, str]]:
    """ka10099 — 시장별 종목 리스트 (mrkt_tp '0' = 코스피)."""
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "cont-yn": "N",
        "next-key": "",
        "api-id": "ka10099",
    }
    resp = client._safe_post("/api/dostk/stkinfo", headers, {"mrkt_tp": "0"})
    body = resp.json()
    # 응답 리스트 키 후보 (환경에 따라 'list' 등) 자동 탐색
    items = None
    for k, v in body.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            items = v
            break
    if not items:
        raise RuntimeError(f"ka10099 응답에서 종목 리스트를 못 찾음: keys={list(body)}")

    out: list[tuple[str, str]] = []
    for it in items:
        code = (it.get("code") or it.get("stk_cd") or "").strip()
        name = (it.get("name") or it.get("stk_nm") or "").strip()
        if _is_common(code, name, it):
            out.append((code, name))
    return out


def _is_common(code: str, name: str, it: dict) -> bool:
    """코스피 보통주만 통과 (우선주/ETF/ETN/스팩 제외)."""
    if len(code) != 6 or not code.isdigit():
        return False
    if not code.endswith("0"):           # 우선주(끝자리 5/7/9 등) 제외
        return False
    if str(it.get("marketCode", "")) != "0":  # ETF(8)/ETN 등 제외, 거래소(0)만
        return False
    if "스팩" in name:                    # 스팩 제외
        return False
    return True


def get_kospi_codes(client: KiwoomClient | None = None, refresh: bool = False) -> list[tuple[str, str]]:
    config.ensure_dirs()
    if _CACHE.exists() and not refresh:
        with _CACHE.open() as f:
            return [(r["code"], r.get("name", "")) for r in csv.DictReader(f)]

    if client is None:
        client = KiwoomClient()
    codes = _fetch_via_api(client)
    with _CACHE.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["code", "name"])
        w.writeheader()
        for code, name in codes:
            w.writerow({"code": code, "name": name})
    return codes


if __name__ == "__main__":
    codes = get_kospi_codes(refresh=True)
    print(f"코스피 종목 {len(codes)}개 캐싱 완료 → {_CACHE}")
    for c, n in codes[:10]:
        print(f"  {c} {n}")
