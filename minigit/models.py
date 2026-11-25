"""커밋 노드 자료구조."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Tuple

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass(frozen=True)
class Commit:
    """커밋 그래프의 노드.

    Attributes:
        hash: 세션 내에서 유일한 커밋 식별자.
        message: 커밋 메시지.
        author: 작성자 이름.
        timestamp: 생성 시각.
        parents: 부모 커밋 hash 목록 (0개 = 루트 커밋, 2개 이상 = 병합 커밋).
        seq: 생성 순번. 동률 처리 등 결정적(deterministic) 출력을 위해 사용한다.
    """

    hash: str
    message: str
    author: str
    timestamp: datetime
    parents: Tuple[str, ...]
    seq: int

    @property
    def time_str(self) -> str:
        """사람이 읽기 좋은 형식의 timestamp 문자열."""
        return self.timestamp.strftime(TIMESTAMP_FORMAT)
