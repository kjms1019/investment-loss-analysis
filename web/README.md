# 심리·과매매 복기 — 웹 데모 (Next.js)

파이프라인의 **실제 출력**을 시각화하는 대시보드.
Vercel에 그대로 배포되는 정적(SSG) Next.js 앱이다 — 서버에 Python 불필요.

> 📖 백엔드 총괄 흐름은 [../analysis/orchestrator/README.md](../analysis/orchestrator/README.md).

## 두 가지 뷰 (우상단 토글)

- **손실→라우팅** (기본): 손실 선별 funnel과 손실거래별 라우팅 카드를 보여준다.
  현재 웹 데이터는 `web/src/data/flow_*.json` 정적 JSON을 사용한다.
- **계좌 전체 경향**: 거래 전체에서 본 3패턴 강/중/약 + 진단(큰 그림).
  데이터: `*.json` ← `analysis/psych_agent/export_web.py`.

## 구조

```
web/
├── src/app/page.tsx     뷰 토글 + 시나리오 탭
├── src/components/       FlowView / PatternCards / Diagnosis / ui
├── src/lib/             flow.ts / data.ts / types.ts
└── src/data/            flow_*.json (라우팅) + *.json (계좌 전체) — 빌드 타임 포함
```

## 로컬 실행

```bash
cd web
npm install
npm run dev        # http://localhost:3000
# 시나리오 딥링크:  /#disposition  /#revenge  /#overtrading  /#all
```

## 데이터 갱신

계좌 전체 경향 JSON은 아래 명령으로 갱신한다.

```bash
cd analysis
./venv/bin/python -m psych_agent.export_web ../web/src/data
```

오케스트레이터의 최신 반환값은 `analysis/orchestrator/pipeline.py`의 `run_pipeline()`에서
확인한다. 웹의 손실→라우팅 정적 JSON 갱신기는 아직 최신 러프 오케스트레이터에 맞춰
다시 붙이지 않았다.

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
