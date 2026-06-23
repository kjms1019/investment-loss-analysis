# 심리·과매매 복기 — 웹 데모 (Next.js)

준모 심리/과매매 분석 에이전트의 **실제 출력**을 시각화하는 대시보드.
Vercel에 그대로 배포되는 정적(SSG) Next.js 앱이다 — 서버에 Python 불필요.

## 구조

```
web/
├── src/app/         App Router (page.tsx = 클라이언트 대시보드)
├── src/components/  PatternCards / Diagnosis / ui
├── src/lib/         타입 + 데이터 로더
└── src/data/        ← 에이전트가 뽑은 시나리오별 리포트 JSON (빌드 타임 포함)
```

데이터는 `analysis/psych_agent/export_web.py` 가 4개 시나리오(혼합/리벤지/과매매/처분효과)
를 분석해 `src/data/*.json` 으로 떨군 결과다. 1분봉 실가격 기반 더미 거래내역의 진짜 분석 출력.

## 로컬 실행

```bash
cd web
npm install
npm run dev        # http://localhost:3000
# 시나리오 딥링크:  /#disposition  /#revenge  /#overtrading  /#all
```

## 데이터 갱신 (에이전트 로직/더미를 바꿨을 때)

```bash
cd analysis
./venv/bin/python -m psych_agent.export_web ../web/src/data
```

LLM 진단을 켜고 싶으면 익스포트 전에 `ANTHROPIC_API_KEY` 를 설정하면
JSON의 diagnosis 엔진이 `anthropic:...` 로 바뀐다(없으면 룰 템플릿).

## Vercel 배포

이 앱은 레포 루트가 아니라 `web/` 하위에 있으므로 **Root Directory = `web`** 로 설정한다.

- 대시보드: New Project → 이 레포 연결 → **Root Directory** 를 `web` 로 지정 → Deploy.
- CLI:
  ```bash
  cd web
  npx vercel          # 첫 배포(프리뷰)
  npx vercel --prod   # 프로덕션
  ```

프레임워크/빌드 명령은 Next.js 로 자동 감지된다(`next build`, output `.next`).
별도 환경변수는 필요 없다(데이터가 빌드에 정적으로 포함됨).
