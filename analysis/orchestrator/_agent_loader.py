"""Vendored 에이전트 격리 로더.

`손절실패/`, `entry-error-agent/` 등은 패키지가 아니라 폴더 안에서 최상위
절대 import(`from schema import ...`, `from agent import ...`)를 쓴다.
여러 에이전트가 동시에 `schema` / `config` / `agent` 같은 동일한 최상위
모듈명을 점유하면 sys.modules 캐시가 충돌해 엉뚱한 모듈을 잡는다.

이 컨텍스트 매니저는 한 에이전트를 실행하는 동안만 해당 폴더를 sys.path 맨
앞에 올리고, 빠져나올 때 그 폴더가 새로 로드한 모듈을 sys.modules 에서
제거한 뒤 이전 상태를 복원한다 — 에이전트 간 격리를 보장한다.
"""

from __future__ import annotations

import contextlib
import importlib
import sys
from pathlib import Path
from typing import Iterator


@contextlib.contextmanager
def vendored_agent(folder: Path, owned_modules: list[str]) -> Iterator[None]:
    """`folder` 를 sys.path 최상단에 두고, 종료 시 격리 정리.

    Args:
        folder        : 에이전트 소스 폴더 (절대 경로)
        owned_modules : 이 폴더가 점유하는 최상위 모듈명들
                        (충돌 가능성이 있어 진입 전 백업, 종료 시 제거/복원)
    """
    folder_str = str(folder)

    # 충돌 가능한 모듈을 미리 치워 두고(백업), 종료 시 되돌린다.
    saved = {name: sys.modules.pop(name) for name in owned_modules if name in sys.modules}
    sys.path.insert(0, folder_str)
    try:
        yield
    finally:
        if folder_str in sys.path:
            sys.path.remove(folder_str)
        # 이번 컨텍스트에서 새로 로드된 owned 모듈 제거
        for name in owned_modules:
            sys.modules.pop(name, None)
        # 원래 점유하던 모듈 복원
        sys.modules.update(saved)


def import_from(folder: Path, owned_modules: list[str], module_name: str):
    """격리 컨텍스트 안에서 `module_name` 을 import 해 반환.

    반환된 모듈 객체는 컨텍스트 종료 후에도 사용 가능하지만, 이후 다른
    에이전트를 로드하면 같은 최상위 이름이 재정의될 수 있으므로 즉시 필요한
    심볼만 뽑아 쓰는 것을 권장한다.
    """
    with vendored_agent(folder, owned_modules):
        return importlib.import_module(module_name)
