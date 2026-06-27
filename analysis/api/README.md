# API 레이어 (`analysis/api`)

분석단/예측단 결과를 프론트(`web/`)가 소비할 JSON으로 노출하는 읽기 전용 HTTP 레이어.
새 분석 로직은 만들지 않고, 기존 모듈(`report.builder` / `user_profile` /
`demo_alert_runner`)을 그대로 읽어 화면 모양으로 매핑한다.

## 실행

```bash
pip install -r analysis/requirements.txt
uvicorn analysis.api.main:app --reload --port 8000
# http://127.0.0.1:8000/docs (자동 문서)
```

전제: 데모 DB 백필이 끝나 있어야 함.
```bash
python -c "from analysis.orchestrator.demo_alert_runner import backfill_user_profiles; \
backfill_user_profiles('tests/fixtures/demo_users_all_data.final_3sheets.xlsx')"
```

## 엔드포인트 (화면 매핑)

| 메서드 | 경로 | 화면 | 소스 |
|---|---|---|---|
| GET | `/api/users` | 공통 | user_profiles |
| GET | `/api/dashboard/{user}` | ③ 진단 대시보드 | report.build_user_summary |
| GET | `/api/trades/{user}` | ④ 거래별 설명 | report items (분류기 점수·손절신호·narrative) |
| GET | `/api/profile/{user}` | ⑤ 내 성향 | user_profile patterns |
| GET | `/api/alerts/{user}` | ⑥ 실시간 알림 | demo_alert_runner B·C (캐시) |
| POST | `/api/analyze` | ① 업로드 | (데모: 백필 결과) — **TODO: 실 CSV 업로드** |

`user` 는 데모에서 사용자명(예: `방상운`). URL 인코딩 필요.

## 미구현 (TODO)
- `POST /api/analyze` 실제 CSV 업로드 → `run_pipeline` 트리거 → run_id 반환
- 로그인/인증, 동의 저장 엔드포인트
- 분석 진행률 스트리밍(SSE) — 현재 파이프라인은 동기 실행
- α 3분해(시장/선택/타이밍) 정확 분리 — 현재 dashboard 는 도메인 카운트 위주
- `/api/alerts` 는 데모 fixture 기준(프로세스 캐시). 실서비스는 보유/계획 실데이터 연동 필요
