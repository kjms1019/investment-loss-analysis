"""최근 구간 캐치업 수집기 (ka10080).

기존 수집은 2026-06-23 오전 11:15경에 멈춰, 23일 오후장 + 24·25·26일이 누락됨.
이 스크립트는 [START, END) 구간만 좁게 재수집해 종목별 parquet 에 append + 중복제거.

collect_min1 의 함수(collect_window/_save_rows/manifest)를 그대로 재사용하므로
스키마·병합·중복제거 규칙이 기존 수집과 100% 동일하다.

사용 예:
    python -m analysis.collector.catchup_recent --limit 3      # 3종목 테스트
    python -m analysis.collector.catchup_recent --codes 005930 # 특정 종목
    python -m analysis.collector.catchup_recent                # 전 종목
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime

from . import config
from .collect_min1 import (
    _load_manifest,
    _save_manifest,
    _save_rows,
    collect_window,
)
from .kiwoom_client import KiwoomClient, KiwoomError
from .universe import get_kospi_codes

# 캐치업 윈도우: 23일 오후 백필을 위해 23일 00:00부터, 끝은 실행 시각까지.
START_DT = datetime(2026, 6, 23, 0, 0, 0)
END_DT = datetime.now()


def run(codes: list[str], fmt: str) -> None:
    config.ensure_dirs()
    client = KiwoomClient()
    manifest = _load_manifest()
    total = len(codes)
    t0 = time.time()
    print(f"캐치업 윈도우: {START_DT}  ~  {END_DT}")

    for i, code in enumerate(codes, 1):
        rec = manifest.get(code, {})
        try:
            rows, pages = collect_window(client, code, START_DT, END_DT)
            stats = _save_rows(code, rows, fmt) if rows else rec
            rec.update(stats)
            rec["catchup_recent_at"] = datetime.now().isoformat(timespec="seconds")
            manifest[code] = rec
            _save_manifest(manifest)
            elapsed = time.time() - t0
            eta = elapsed / i * (total - i) / 60
            print(f"[{i}/{total}] {code}  +{len(rows):>5}봉 ({pages}p)  "
                  f"누적 {rec.get('n_rows', 0):>7}  last {rec.get('last_dt')}  ETA {eta:5.1f}분")
        except KiwoomError as e:
            print(f"[{i}/{total}] {code}  ❌ {e}", file=sys.stderr)
            rec["error"] = str(e)[:200]
            manifest[code] = rec
            _save_manifest(manifest)
        time.sleep(config.SLEEP_PER_REQUEST)

    print(f"\n캐치업 완료. manifest → {config.MIN1_DIR / '_manifest.json'}")


def main() -> None:
    ap = argparse.ArgumentParser(description="최근 구간 캐치업 수집기 (ka10080)")
    ap.add_argument("--format", choices=["parquet", "csv"], default="parquet")
    ap.add_argument("--limit", type=int, help="앞에서 N종목만 (테스트용)")
    ap.add_argument("--codes", help="쉼표구분 종목코드 (지정 시 유니버스 무시)")
    args = ap.parse_args()

    if args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    else:
        codes = [c for c, _ in get_kospi_codes()]
    if args.limit:
        codes = codes[: args.limit]
    print(f"대상 종목 {len(codes)}개 · 캐치업 · {args.format}")
    run(codes, args.format)


if __name__ == "__main__":
    main()
