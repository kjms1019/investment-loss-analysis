"""배포 환경에서 데모 데이터 번들을 내려받아 analysis/data/ 에 푼다.

min1 parquet 은 gitignore 라 저장소에 없다. 배포 서버는 빌드 단계에서 이 스크립트로
GitHub Release 의 번들(zip)을 받아 제자리에 풀어야 한다. 풀리는 위치는
analysis/common.paths.DATA_DIR 이라, 코드 쪽 기본 경로를 그대로 쓴다.

    python scripts/fetch_demo_bundle.py

번들 주소는 DEMO_BUNDLE_URL 로 바꿀 수 있다(기본값은 아래 _DEFAULT_URL).

이미 min1 이 채워져 있으면 아무것도 하지 않는다 — 로컬에서 실수로 돌려도
1.1GB 전체 데이터를 172MB 데모본으로 덮어쓰지 않는다.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.common.paths import CODES_CSV, DATA_DIR, MIN1_DIR  # noqa: E402

_DEFAULT_URL = (
    "https://github.com/kjms1019/investment-loss-analysis/releases/download/"
    "demo-bundle-20260905/mirae_demo_bundle.zip"
)


def already_installed() -> bool:
    return MIN1_DIR.is_dir() and any(MIN1_DIR.glob("*.parquet")) and CODES_CSV.exists()


def fetch(url: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "bundle.zip"
        print(f"내려받는 중: {url}")
        with urllib.request.urlopen(url) as r, open(zip_path, "wb") as f:
            shutil.copyfileobj(r, f)
        size_mb = zip_path.stat().st_size / 1e6
        print(f"받음: {size_mb:.1f}MB — 푸는 중 → {DATA_DIR}")
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(DATA_DIR)


def verify() -> None:
    """푼 결과가 실제로 쓸 수 있는 상태인지 확인한다.

    kospi_codes.csv 가 없으면 종목명→코드 변환이 전부 실패해 모든 거래가
    조용히 스킵된다(화면은 에러 없이 비어 보인다). 배포 후에 발견하면 늦으므로
    여기서 실패시킨다.
    """
    problems = []
    if not MIN1_DIR.is_dir():
        problems.append(f"min1 폴더 없음: {MIN1_DIR}")
    else:
        n = len(list(MIN1_DIR.glob("*.parquet")))
        if n == 0:
            problems.append(f"min1 parquet 0개: {MIN1_DIR}")
        else:
            print(f"min1 parquet {n}개")
    if not CODES_CSV.exists():
        problems.append(f"종목코드 캐시 없음: {CODES_CSV}")
    for db in ("orchestrator.sqlite3", "user_profiles.sqlite3", "ui_trade_charts.sqlite3"):
        if not (DATA_DIR / db).exists():
            problems.append(f"DB 없음: {db}")

    if problems:
        for p in problems:
            print(f"  실패: {p}", file=sys.stderr)
        raise SystemExit(1)
    print(f"번들 정상: {DATA_DIR}")


def main() -> None:
    if already_installed():
        print(f"데이터가 이미 있음 — 건너뜀: {DATA_DIR}")
        return
    fetch(os.getenv("DEMO_BUNDLE_URL", _DEFAULT_URL))
    verify()


if __name__ == "__main__":
    main()
