# 개발 환경 설정 가이드

이 문서는 프로젝트를 처음 클론한 팀원이 개발 환경을 세팅하는 절차를 안내합니다.

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| 프론트엔드 | React 19 + Next.js 16 (App Router) |
| 스타일링 | Tailwind CSS 4 |
| 백엔드 / DB | Supabase |
| 데이터 분석 | Python 3.13 + JupyterLab |
| 배포 | Vercel |

---

## 1. 저장소 클론

```bash
git clone https://github.com/kjms1019/mirae_asset_agent.git
cd mirae_asset_agent
```

---

## 2. 환경변수 설정

```bash
cp .env.example .env.local
```

`.env.local`을 열어 Supabase 값을 입력합니다.  
키는 **Supabase 대시보드 → Settings → API** 에서 확인할 수 있습니다.  
`.env.local`은 `.gitignore`에 포함되어 있으므로 **절대 커밋되지 않습니다.**

---

## 3. JS / Next.js 환경

### 3-1. Node.js 버전 맞추기

이 프로젝트는 **Node.js 24.15.0 LTS** 를 사용합니다.  
[nvm](https://github.com/nvm-sh/nvm) (macOS/Linux) 또는 [nvm-windows](https://github.com/coreybutler/nvm-windows) 를 권장합니다.

```bash
# nvm 사용 시 — .nvmrc를 읽어 자동으로 버전 맞춤
nvm install
nvm use
```

nvm 없이 직접 설치하는 경우 Node.js 24.x LTS 버전을 [nodejs.org](https://nodejs.org)에서 받아주세요.

### 3-2. 의존성 설치

```bash
npm install
```

### 3-3. 개발 서버 실행

```bash
npm run dev
```

브라우저에서 `http://localhost:3000` 을 열면 확인할 수 있습니다.

| 명령어 | 설명 |
|--------|------|
| `npm run dev` | 개발 서버 실행 |
| `npm run build` | 프로덕션 빌드 |
| `npm run start` | 빌드된 앱 실행 |
| `npm run lint` | ESLint 검사 |

---

## 4. Python / Jupyter 분석 환경

데이터 분석 코드는 `/analysis` 폴더에서 독립적으로 관리됩니다.  
자세한 내용은 [analysis/README.md](analysis/README.md) 를 참고하세요.

### 빠른 시작

```bash
cd analysis

# 가상환경 생성 및 활성화
python -m venv venv

# macOS / Linux
source venv/bin/activate
# Windows PowerShell
.\venv\Scripts\Activate.ps1

# 의존성 설치
pip install -r requirements.txt

# Jupyter 커널 등록
python -m ipykernel install --user --name mirae-analysis --display-name "Python (mirae)"

# JupyterLab 실행
jupyter lab
```

> Python 버전은 **3.13** 을 사용합니다.  
> [pyenv](https://github.com/pyenv/pyenv) 사용 시 `analysis/.python-version`을 자동으로 읽습니다.

---

## 5. nbstripout 설정 (최초 1회, 필수)

노트북 출력(output)이 git에 커밋되지 않도록 git 필터를 등록합니다.  
**팀원 각자가 직접 실행해야 합니다.** (`.git/config`에 로컬 저장, 커밋되지 않음)

```bash
# analysis/ 안에서 venv 활성화 후, 프로젝트 루트로 이동해서 실행
cd ..   # 프로젝트 루트
nbstripout --install
```

설치 후 `git config --list | grep filter`로 `filter.nbstripout` 항목이 보이면 완료입니다.

---

## 6. 폴더 구조

```
mirae_asset_agent/
├── app/                  # Next.js App Router 페이지 및 레이아웃
├── components/           # 재사용 가능한 React 컴포넌트
├── analysis/             # Python 데이터 분석 (JS 환경과 완전 분리)
│   ├── notebooks/        # Jupyter 노트북 (.ipynb)
│   ├── data/             # 로컬 데이터 (git 미추적)
│   ├── requirements.txt  # Python 의존성
│   └── README.md         # 분석 환경 상세 가이드
├── .env.example          # 환경변수 템플릿
├── .nvmrc                # Node.js 버전 고정 (24.15.0)
├── package.json          # JS 의존성
└── SETUP.md              # 이 문서
```

---

## 7. 브랜치 전략

| 브랜치 | 용도 |
|--------|------|
| `main` | 배포 브랜치 (Vercel 연동) |
| `develop` | 통합 개발 브랜치 |
| `{이름}` | 개인 작업 브랜치 (예: `junmo`, `younghyun`, `subin`) |

작업은 개인 브랜치에서 하고 → `develop` 으로 PR → 검토 후 `main` 으로 병합합니다.

---

## 문제 해결

| 증상 | 해결 방법 |
|------|-----------|
| `next: command not found` | `npm install` 재실행 |
| Supabase 연결 오류 | `.env.local` 키 값 확인 |
| Jupyter 커널이 목록에 없음 | `python -m ipykernel install --user --name mirae-analysis` 재실행 |
| 노트북 출력이 git diff에 보임 | `nbstripout --install` 실행 여부 확인 |
| `venv` 활성화 안 됨 (Windows) | PowerShell에서 `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` 실행 후 재시도 |
