# Analysis 환경 설정 가이드

Python 3.13 + JupyterLab 기반의 탐색적 분석 환경입니다.

## 폴더 구조

```
analysis/
├── notebooks/   # 탐색용 .ipynb 파일
├── data/        # 로컬 데이터 (git 미추적 — 절대 커밋 금지)
├── requirements.txt
└── .python-version
```

---

## 초기 설정 (최초 1회)

### 1. 가상환경 생성

```bash
# analysis/ 폴더에서 실행
cd analysis
python -m venv venv
```

### 2. 가상환경 활성화

```bash
# macOS / Linux
source venv/bin/activate

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Windows (Command Prompt)
venv\Scripts\activate.bat
```

> 이후 터미널 프롬프트에 `(venv)` 가 붙으면 활성화된 상태입니다.

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. Jupyter 커널 등록

```bash
python -m ipykernel install --user --name mirae-analysis --display-name "Python (mirae)"
```

### 5. nbstripout 설치 (최초 1회, 각 팀원이 직접 실행)

커밋 시 노트북 출력(output)이 자동으로 제거되도록 git 필터를 등록합니다.

```bash
# 프로젝트 루트로 이동 후 실행
cd ..
nbstripout --install
```

> `.gitattributes` 파일이 이미 설정되어 있으므로 이 명령어 한 번으로 완료됩니다.  
> `.git/config`(로컬)에 필터가 등록되며 커밋되지 않습니다. **팀원 각자가 실행해야 합니다.**

### 6. JupyterLab 실행

```bash
jupyter lab
```

브라우저에서 `http://localhost:8888` 이 자동으로 열립니다.  
커널 선택 시 **"Python (mirae)"** 를 선택하세요.

---

## Supabase 연결

프로젝트 루트의 `.env.example`을 복사해 `.env` 파일을 만들고 실제 키를 입력합니다.

```bash
cp ../.env.example ../.env
```

노트북에서 환경변수 로드:

```python
from dotenv import load_dotenv
import os
from supabase import create_client

load_dotenv("../.env")

url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_KEY"]
client = create_client(url, key)
```

---

## 일상적인 사용

```bash
# 가상환경 활성화 후 JupyterLab 실행
source venv/bin/activate   # (또는 Windows: .\venv\Scripts\Activate.ps1)
jupyter lab
```

## 의존성 추가 시

```bash
pip install 새패키지==버전
pip freeze | grep 새패키지   # 버전 확인
# requirements.txt 에 수동으로 추가
```
