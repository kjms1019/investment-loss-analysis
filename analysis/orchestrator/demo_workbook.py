"""데모 사용자 xlsx(3시트: 종결거래/현재보유/투자계획) 로더.

데모 파일은 GitHub 릴리즈 kospi-min1-1y-20260623 의
demo_users_all_data.final_3sheets.xlsx (tests/fixtures/ 에 커밋됨).
시트 헤더가 곧 dict 키이므로, 현재보유 시트는 그대로
`CurrentHoldingInput.from_row()`에 투입 가능하다.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

import openpyxl

from analysis.common.min1_lookup import load_name_to_code

SHEET_CLOSED_TRADES = "종결거래"
SHEET_CURRENT_HOLDINGS = "현재보유"
SHEET_INVESTMENT_PLANS = "투자계획"

USER_KEY = "사용자명"


def _read_sheet_rows(xlsx_path: str, sheet_name: str) -> list[dict[str, Any]]:
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb[sheet_name]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    header, *body = rows
    return [
        dict(zip(header, row))
        for row in body
        if any(value is not None for value in row)
    ]


def _group_by_user(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[USER_KEY])].append(row)
    return dict(grouped)


def load_closed_trades(xlsx_path: str) -> dict[str, list[dict[str, Any]]]:
    """종결거래 시트 -> {사용자명: [row, ...]} (사용자명/거래ID/종목명/매수일시/매도일시/수량)."""
    return _group_by_user(_read_sheet_rows(xlsx_path, SHEET_CLOSED_TRADES))


def load_current_holdings(xlsx_path: str) -> dict[str, list[dict[str, Any]]]:
    """현재보유 시트 -> {사용자명: [row, ...]} (사용자명/보유ID/종목명/현재보유수량/매수일시)."""
    return _group_by_user(_read_sheet_rows(xlsx_path, SHEET_CURRENT_HOLDINGS))


def load_investment_plans(xlsx_path: str) -> dict[str, list[dict[str, Any]]]:
    """투자계획 시트 -> {사용자명: [row, ...]} (사용자명/계획ID/종목명/예정일시/예정수량)."""
    return _group_by_user(_read_sheet_rows(xlsx_path, SHEET_INVESTMENT_PLANS))


def resolve_code(name: str, name_to_code: Optional[dict] = None) -> Optional[str]:
    """종목명 -> 종목코드. 매핑 실패 시 None (호출 측에서 건너뛰고 사유를 남길 것)."""
    mapping = name_to_code if name_to_code is not None else load_name_to_code()
    return mapping.get(name)
