"""키움 REST API 클라이언트.

- 접근토큰 자동 발급/캐싱/만료 전 갱신 (토큰 유효 24h)
- 안전한 POST: 지수 백오프 재시도 + 429/네트워크 에러 대응
- ka10080 분봉 조회 + 연속조회(next-key)
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

import requests

from . import config


class KiwoomError(Exception):
    pass


@dataclass
class _Token:
    value: str
    expires_at: datetime  # 안전 마진 적용된 만료 시각


class KiwoomClient:
    def __init__(self, app_key: str | None = None, app_secret: str | None = None,
                 base_url: str | None = None):
        self.app_key = app_key or config.APP_KEY
        self.app_secret = app_secret or config.APP_SECRET
        self.base_url = (base_url or config.BASE_URL).rstrip("/")
        if not self.app_key or not self.app_secret:
            raise KiwoomError(
                "KIWOOM_APP_KEY / KIWOOM_APP_SECRET 가 .env 에 없습니다. "
                ".env.example 참고."
            )
        self._token: _Token | None = None
        config.ensure_dirs()
        self._token_cache = config.CACHE_DIR / "token.json"
        self.session = requests.Session()

    # ── 토큰 ────────────────────────────────────────────────────────────────
    def _load_cached_token(self) -> _Token | None:
        if not self._token_cache.exists():
            return None
        try:
            raw = json.loads(self._token_cache.read_text())
            exp = datetime.fromisoformat(raw["expires_at"])
            if exp > datetime.now() + timedelta(minutes=10):
                return _Token(raw["value"], exp)
        except Exception:
            pass
        return None

    def _issue_token(self) -> _Token:
        """au10001 — 접근토큰 발급."""
        url = f"{self.base_url}/oauth2/token"
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "secretkey": self.app_secret,
        }
        resp = self.session.post(
            url,
            headers={"Content-Type": "application/json;charset=UTF-8"},
            json=payload,
            timeout=config.REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            raise KiwoomError(f"토큰 발급 실패 HTTP {resp.status_code}: {resp.text}")
        body = resp.json()
        token = body.get("token")
        if not token:
            raise KiwoomError(f"토큰 응답에 token 없음: {body}")
        # expires_dt: 'YYYYMMDDHHMMSS' (없으면 24h 가정), 1h 안전마진
        exp_raw = str(body.get("expires_dt", ""))
        try:
            exp = datetime.strptime(exp_raw, "%Y%m%d%H%M%S")
        except ValueError:
            exp = datetime.now() + timedelta(hours=24)
        exp -= timedelta(hours=1)
        self._token_cache.write_text(
            json.dumps({"value": token, "expires_at": exp.isoformat()})
        )
        return _Token(token, exp)

    def token(self) -> str:
        if self._token is None or self._token.expires_at <= datetime.now():
            self._token = self._load_cached_token() or self._issue_token()
        return self._token.value

    # ── 저수준 안전 POST ────────────────────────────────────────────────────
    def _safe_post(self, endpoint: str, headers: dict, data: dict) -> requests.Response:
        url = f"{self.base_url}{endpoint}"
        last_exc: Exception | None = None
        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                headers = {**headers, "authorization": f"Bearer {self.token()}"}
                resp = self.session.post(
                    url, headers=headers, json=data, timeout=config.REQUEST_TIMEOUT
                )
                if resp.status_code == 200:
                    return resp
                if resp.status_code == 401:          # 토큰 만료 → 재발급 후 재시도
                    self._token = self._issue_token()
                elif resp.status_code == 429:        # 과호출 → 백오프
                    wait = config.RETRY_BACKOFF ** attempt
                    time.sleep(wait)
                    continue
                else:
                    last_exc = KiwoomError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            except requests.RequestException as e:
                last_exc = e
            time.sleep(config.RETRY_BACKOFF ** (attempt - 1))
        raise KiwoomError(f"{endpoint} 요청 실패 ({config.MAX_RETRIES}회): {last_exc}")

    # ── ka10080 분봉 조회 ───────────────────────────────────────────────────
    def fetch_min_page(self, stk_cd: str, tic_scope: str = "1", upd_stkpc_tp: str = "1",
                       base_dt: str = "", cont_yn: str = "N", next_key: str = "") -> tuple[list, str, str]:
        """분봉 1페이지 조회. (items, resp_cont_yn, resp_next_key) 반환."""
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "cont-yn": cont_yn,
            "next-key": next_key,
            "api-id": "ka10080",
        }
        data = {"stk_cd": stk_cd, "tic_scope": tic_scope, "upd_stkpc_tp": upd_stkpc_tp}
        if base_dt:
            data["base_dt"] = base_dt
        resp = self._safe_post("/api/dostk/chart", headers, data)
        body = resp.json()
        items = body.get("stk_min_pole_chart_qry", []) or []
        return items, resp.headers.get("cont-yn", "N"), resp.headers.get("next-key", "")
