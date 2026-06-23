"""코스피 1분봉 수집기 (ka10080).

Phase A: 최근 3개월 → Phase B: 그 이전 9개월 순으로 전 종목 수집.
종목별 parquet 1파일에 append + 중복제거로 누적하며, manifest 로 재개 지원.

사용 예:
    python -m analysis.collector.collect_min1 --phase a            # 최근 3개월
    python -m analysis.collector.collect_min1 --phase b            # 이전 9개월
    python -m analysis.collector.collect_min1 --phase a --limit 3  # 3종목만 테스트
    python -m analysis.collector.collect_min1 --phase a --self-test 005930
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta

import pandas as pd

from . import config
from .kiwoom_client import KiwoomClient, KiwoomError
from .universe import get_kospi_codes

_MANIFEST = config.MIN1_DIR / "_manifest.json"
_NUM_RE = re.compile(r"-?\d+")

# Phase 윈도우 정의 (오늘 기준 일수)
PHASES = {
    "a": (90, 0),     # [오늘-90, 오늘]
    "b": (365, 90),   # [오늘-365, 오늘-90]
}


# ── 파싱 ────────────────────────────────────────────────────────────────────
def _to_int(v) -> int | None:
    if v is None:
        return None
    m = _NUM_RE.search(str(v))
    return abs(int(m.group())) if m else None


def _parse_ts(raw) -> datetime | None:
    """cntr_tm ('YYYYMMDDHHMMSS' 또는 'YYYYMMDDHHMM') → datetime."""
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) < 12:
        return None
    try:
        return datetime.strptime(digits[:12], "%Y%m%d%H%M")
    except ValueError:
        return None


def _parse_row(it: dict, code: str, ts: datetime) -> dict:
    return {
        "datetime": ts,
        "code": code,
        "open": _to_int(it.get("open_pric")),
        "high": _to_int(it.get("high_pric")),
        "low": _to_int(it.get("low_pric")),
        "close": _to_int(it.get("cur_prc")),
        "volume": _to_int(it.get("trde_qty")),
        "acc_volume": _to_int(it.get("acc_trde_qty")),
    }


# ── 윈도우 수집 ──────────────────────────────────────────────────────────────
def collect_window(client: KiwoomClient, code: str, start_dt: datetime,
                   end_dt: datetime) -> list[dict]:
    """[start_dt, end_dt) 구간 분봉을 연속조회로 수집.

    base_dt 지원 여부와 무관하게 동작:
      - end_dt 보다 최신 봉은 스킵
      - start_dt 보다 오래된 봉을 만나면 종료 (응답은 최신→과거 순서)
    """
    rows: list[dict] = []
    cont_yn, next_key = "N", ""
    base_dt = end_dt.strftime("%Y%m%d") if end_dt.date() < datetime.now().date() else ""
    pages = 0
    while True:
        items, rcont, rnext = client.fetch_min_page(
            code, base_dt=base_dt, cont_yn=cont_yn, next_key=next_key
        )
        base_dt = ""  # base_dt 는 첫 요청에만
        pages += 1
        if not items:
            break
        stop = False
        for it in items:
            ts = _parse_ts(it.get("cntr_tm"))
            if ts is None:
                continue
            if ts >= end_dt:        # 윈도우보다 최신 → 스킵
                continue
            if ts < start_dt:       # 윈도우보다 과거 → 종료
                stop = True
                break
            rows.append(_parse_row(it, code, ts))
        if stop:
            break
        if rcont == "Y" and rnext:
            cont_yn, next_key = "Y", rnext
            time.sleep(config.SLEEP_PER_REQUEST)
            continue
        break
    return rows, pages


# ── 저장 / manifest ──────────────────────────────────────────────────────────
def _stock_path(code: str):
    return config.MIN1_DIR / f"{code}.parquet"


def _save_rows(code: str, rows: list[dict], fmt: str) -> dict:
    """기존 parquet 와 병합, 중복(datetime) 제거 후 저장. 요약 통계 반환."""
    new_df = pd.DataFrame(rows)
    path = _stock_path(code)
    if path.exists():
        old = pd.read_parquet(path)
        df = pd.concat([old, new_df], ignore_index=True)
    else:
        df = new_df
    df = (
        df.dropna(subset=["datetime"])
        .drop_duplicates(subset=["datetime"])
        .sort_values("datetime")
        .reset_index(drop=True)
    )
    if fmt == "csv":
        df.to_csv(config.MIN1_DIR / f"{code}.csv", index=False)
    else:
        df.to_parquet(path, index=False)
    return {
        "n_rows": len(df),
        "first_dt": df["datetime"].iloc[0].isoformat() if len(df) else None,
        "last_dt": df["datetime"].iloc[-1].isoformat() if len(df) else None,
    }


def _load_manifest() -> dict:
    if _MANIFEST.exists():
        return json.loads(_MANIFEST.read_text())
    return {}


def _save_manifest(m: dict) -> None:
    _MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=2))


# ── 오케스트레이션 ───────────────────────────────────────────────────────────
def run(phase: str, codes: list[str], fmt: str, force: bool) -> None:
    config.ensure_dirs()
    back_start, back_end = PHASES[phase]
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_dt = today - timedelta(days=back_start)
    end_dt = today - timedelta(days=back_end) + timedelta(days=1)  # 끝 포함

    client = KiwoomClient()
    manifest = _load_manifest()
    total = len(codes)
    done_key = f"phase_{phase}_done"
    t0 = time.time()

    for i, code in enumerate(codes, 1):
        rec = manifest.get(code, {})
        if rec.get(done_key) and not force:
            print(f"[{i}/{total}] {code} 이미 완료 — 건너뜀")
            continue
        try:
            rows, pages = collect_window(client, code, start_dt, end_dt)
            stats = _save_rows(code, rows, fmt) if rows else rec
            rec.update(stats)
            rec[done_key] = True
            rec["updated_at"] = datetime.now().isoformat(timespec="seconds")
            manifest[code] = rec
            _save_manifest(manifest)
            elapsed = time.time() - t0
            eta = elapsed / i * (total - i) / 60
            print(f"[{i}/{total}] {code}  +{len(rows):>6}봉 ({pages}p)  "
                  f"누적 {rec.get('n_rows', 0):>7}  ETA {eta:5.1f}분")
        except KiwoomError as e:
            print(f"[{i}/{total}] {code}  ❌ {e}", file=sys.stderr)
            rec["error"] = str(e)[:200]
            manifest[code] = rec
            _save_manifest(manifest)
        time.sleep(config.SLEEP_PER_REQUEST)

    print(f"\nPhase {phase.upper()} 완료. manifest → {_MANIFEST}")


def self_test(code: str) -> None:
    """한 종목으로 키움이 실제로 몇 개월치를 주는지, 응답당 봉 개수를 실측."""
    client = KiwoomClient()
    print(f"토큰 OK (…{client.token()[-6:]})")
    items, rcont, rnext = client.fetch_min_page(code)
    print(f"첫 응답 봉 개수: {len(items)},  cont-yn={rcont}")
    if items:
        print("샘플 항목 키:", list(items[0].keys()))
        newest = _parse_ts(items[0].get("cntr_tm"))
        oldest = _parse_ts(items[-1].get("cntr_tm"))
        print(f"페이지 범위: {oldest}  ~  {newest}")
    # 끝까지 페이징해 가장 오래된 봉 날짜 확인
    print("\n전체 깊이 측정 중 (Ctrl+C 로 중단 가능)…")
    cont_yn, next_key, pages, oldest = "N", "", 0, None
    while True:
        items, rcont, rnext = client.fetch_min_page(code, cont_yn=cont_yn, next_key=next_key)
        pages += 1
        if items:
            oldest = _parse_ts(items[-1].get("cntr_tm")) or oldest
        if pages % 10 == 0:
            print(f"  {pages}페이지… 현재 최古 {oldest}")
        if rcont == "Y" and rnext:
            cont_yn, next_key = "Y", rnext
            time.sleep(config.SLEEP_PER_REQUEST)
            continue
        break
    print(f"\n총 {pages}페이지, 가장 오래된 봉: {oldest}")


def main() -> None:
    ap = argparse.ArgumentParser(description="코스피 1분봉 수집기 (ka10080)")
    ap.add_argument("--phase", choices=["a", "b"], help="a=최근3개월, b=이전9개월")
    ap.add_argument("--format", choices=["parquet", "csv"], default="parquet")
    ap.add_argument("--limit", type=int, help="앞에서 N종목만 (테스트용)")
    ap.add_argument("--codes", help="쉼표구분 종목코드 (지정 시 유니버스 무시)")
    ap.add_argument("--force", action="store_true", help="완료 종목도 다시 수집")
    ap.add_argument("--self-test", metavar="CODE", help="한 종목 깊이/스키마 실측")
    args = ap.parse_args()

    if args.self_test:
        self_test(args.self_test)
        return
    if not args.phase:
        ap.error("--phase a|b 또는 --self-test CODE 중 하나가 필요합니다.")

    if args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    else:
        codes = [c for c, _ in get_kospi_codes()]
    if args.limit:
        codes = codes[: args.limit]
    print(f"대상 종목 {len(codes)}개 · Phase {args.phase.upper()} · {args.format}")
    run(args.phase, codes, args.format, args.force)


if __name__ == "__main__":
    main()
