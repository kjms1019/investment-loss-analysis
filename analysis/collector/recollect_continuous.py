"""이음새 오염 종목 단일 연속패스 재수집기 (ka10080).

문제: collect_min1 은 Phase A(base_dt="")·Phase B(base_dt=과거)·캐치업을 따로 받아,
그 사이 액면분할 등 corporate action 이 있던 종목은 청크마다 수정주가 기준일이 달라
이음새(2026-03-25 A/B경계, 2026-06-23 캐치업경계)에서 가짜 가격점프가 생긴다.

해결: 지정 종목을 [오늘-365, 오늘] 단일 연속조회(base_dt="")로 다시 받아 최신일 기준
일관 수정주가 스케일로 만들고, 기존 parquet 을 **덮어쓴다**(append+중복제거 아님 —
기존 혼합 스케일 봉을 버려야 하므로).

사용 예:
    python -m analysis.collector.recollect_continuous --codes 007460,134380
    python -m analysis.collector.recollect_continuous --codes-file affected.txt
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta

import pandas as pd

from . import config
from .collect_min1 import collect_window
from .kiwoom_client import KiwoomClient, KiwoomError

_MANIFEST = config.MIN1_DIR / "_manifest.json"


def _load_manifest() -> dict:
    return json.loads(_MANIFEST.read_text()) if _MANIFEST.exists() else {}


def _save_manifest(m: dict) -> None:
    _MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=2))


def run(codes: list[str], days: int) -> None:
    config.ensure_dirs()
    client = KiwoomClient()
    manifest = _load_manifest()
    end = datetime.now()
    start = end - timedelta(days=days)
    total = len(codes)
    t0 = time.time()
    print(f"단일 연속패스 재수집(덮어쓰기): {start:%Y-%m-%d} ~ {end:%Y-%m-%d} · {total}종목")

    for i, code in enumerate(codes, 1):
        try:
            rows, pages = collect_window(client, code, start, end)
            if not rows:
                print(f"[{i}/{total}] {code}  ⚠️ 봉 0개 — 건너뜀", file=sys.stderr)
                continue
            df = (
                pd.DataFrame(rows)
                .dropna(subset=["datetime"])
                .drop_duplicates(subset=["datetime"])
                .sort_values("datetime")
                .reset_index(drop=True)
            )
            df.to_parquet(config.MIN1_DIR / f"{code}.parquet", index=False)  # 덮어쓰기

            # 이음새 잔존 점검: 최대 일간 종가 점프
            daily = df.groupby(df["datetime"].dt.date)["close"].last()
            max_jump = (daily / daily.shift(1) - 1).abs().max()

            rec = manifest.get(code, {})
            rec.update({
                "n_rows": len(df),
                "first_dt": df["datetime"].iloc[0].isoformat(),
                "last_dt": df["datetime"].iloc[-1].isoformat(),
                "recollected_continuous_at": datetime.now().isoformat(timespec="seconds"),
                "max_daily_jump_after": round(float(max_jump), 4),
            })
            manifest[code] = rec
            _save_manifest(manifest)
            eta = (time.time() - t0) / i * (total - i) / 60
            print(f"[{i}/{total}] {code}  {len(df):>6}봉 ({pages}p)  "
                  f"최대일간점프 {max_jump*100:5.1f}%  ETA {eta:4.1f}분")
        except KiwoomError as e:
            print(f"[{i}/{total}] {code}  ❌ {e}", file=sys.stderr)
        time.sleep(config.SLEEP_PER_REQUEST)

    print(f"\n재수집 완료. manifest → {_MANIFEST}")


def main() -> None:
    ap = argparse.ArgumentParser(description="이음새 오염 종목 단일 연속패스 재수집기")
    ap.add_argument("--codes", help="쉼표구분 종목코드")
    ap.add_argument("--codes-file", help="줄/쉼표 구분 종목코드 파일")
    ap.add_argument("--days", type=int, default=365, help="수집 깊이(일), 기본 365")
    args = ap.parse_args()

    codes: list[str] = []
    if args.codes:
        codes += [c.strip() for c in args.codes.replace("\n", ",").split(",") if c.strip()]
    if args.codes_file:
        text = open(args.codes_file, encoding="utf-8").read()
        codes += [c.strip() for c in text.replace("\n", ",").split(",") if c.strip()]
    if not codes:
        ap.error("--codes 또는 --codes-file 이 필요합니다.")
    run(codes, args.days)


if __name__ == "__main__":
    main()
