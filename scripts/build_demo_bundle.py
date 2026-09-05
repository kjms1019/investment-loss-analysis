"""배포용 데모 데이터 번들 생성.

전체 min1 은 798종목 1.1GB 라 배포 이미지에 넣을 수 없다. 데모 사용자 10명이 실제로
참조하는 종목만 추려 배포 가능한 크기로 줄인다.

필요 종목의 출처는 두 곳이다. 둘 중 하나라도 빠지면 화면이 조용히 비므로 둘 다 모은다.
  1. 데모 픽스처(demo_users_all_data.final_3sheets.xlsx) 의 종결거래·현재보유·투자계획
  2. 분석 산출 DB(orchestrator.sqlite3) 가 들고 있는 손실거래 종목

    python scripts/build_demo_bundle.py --out dist/demo_data

만들어진 폴더를 MIRAE_DATA_ROOT 로 가리키면 그대로 구동된다.
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.common.paths import CODES_CSV, DATA_DIR, MIN1_DIR  # noqa: E402

_REPO = Path(__file__).resolve().parents[1]
_FIXTURE = _REPO / "tests" / "fixtures" / "demo_users_all_data.final_3sheets.xlsx"
_DBS = ["orchestrator.sqlite3", "user_profiles.sqlite3", "ui_trade_charts.sqlite3"]


def needed_codes() -> set[str]:
    codes = pd.read_csv(CODES_CSV, dtype=str)
    name_to_code = dict(zip(codes["name"], codes["code"]))

    need: set[str] = set()
    xl = pd.ExcelFile(_FIXTURE)
    for sheet in xl.sheet_names:
        df = xl.parse(sheet)
        if "종목명" not in df.columns:
            continue
        for name in df["종목명"].astype(str):
            if name in name_to_code:
                need.add(name_to_code[name])

    con = sqlite3.connect(DATA_DIR / "orchestrator.sqlite3")
    try:
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for t in tables:
            cols = [c[1] for c in con.execute(f"PRAGMA table_info({t})")]
            if "code" not in cols:
                continue
            for (code,) in con.execute(f"SELECT DISTINCT code FROM {t} WHERE code IS NOT NULL"):
                need.add(str(code).zfill(6))
    finally:
        con.close()
    return need


def build(out: Path) -> None:
    out_min1 = out / "min1"
    out_cache = out / ".cache"
    out_min1.mkdir(parents=True, exist_ok=True)
    out_cache.mkdir(parents=True, exist_ok=True)

    need = needed_codes()
    copied = missing = 0
    total = 0
    for code in sorted(need):
        src = MIN1_DIR / f"{code}.parquet"
        if not src.exists():
            missing += 1
            continue
        shutil.copy2(src, out_min1 / src.name)
        total += src.stat().st_size
        copied += 1

    shutil.copy2(CODES_CSV, out_cache / CODES_CSV.name)
    for db in _DBS:
        src = DATA_DIR / db
        if src.exists():
            shutil.copy2(src, out / db)

    print(f"필요 종목 {len(need)} → 복사 {copied} ({total / 1e6:.1f}MB), min1 없음 {missing}")
    print(f"번들: {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist/demo_data", type=Path)
    args = ap.parse_args()
    build(args.out if args.out.is_absolute() else _REPO / args.out)
