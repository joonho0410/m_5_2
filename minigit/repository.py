"""저장소: 커밋 저장소(해시맵), 브랜치, HEAD, 역색인을 관리한다."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Callable, Dict, List, Optional, Sequence

from . import graph
from .index import CommitSearchIndex
from .models import Commit
from .sorting import merge_sort

DEFAULT_BRANCH = "main"
HASH_LENGTH = 7
MIN_PREFIX_LENGTH = 4
SORT_KEYS = ("date", "author")


class MiniGitError(Exception):
    """사용자에게 그대로 보여줄 에러 메시지를 담는 예외."""


class Repository:
    """메모리 위에서 동작하는 Mini Git 저장소.

    - commits: hash -> Commit 해시맵. hash 로 O(1) 조회.
    - branches: 브랜치 이름 -> 가리키는 커밋 hash (아직 커밋이 없으면 None).
    - head: 현재 브랜치 이름.
    """

    def __init__(self, clock: Callable[[], datetime] = datetime.now) -> None:
        self._clock = clock
        self._reset()
        self.initialized = False

    def _reset(self) -> None:
        self.commits: Dict[str, Commit] = {}
        self.branches: Dict[str, Optional[str]] = {}
        self.head: str = DEFAULT_BRANCH
        self.user: str = ""
        self.index = CommitSearchIndex()
        self._counter = 0

    # ------------------------------------------------------------------ 저장소 / 브랜치
    def init(self, user_name: str) -> bool:
        """저장소를 초기화한다: main 브랜치 생성, HEAD 설정, 현재 사용자 설정.

        Returns:
            이미 초기화된 저장소를 다시 초기화했다면 True.
        """
        user_name = " ".join(user_name.split())
        if not user_name:
            raise MiniGitError("Invalid args")
        was_initialized = self.initialized
        self._reset()
        self.user = user_name
        self.branches[DEFAULT_BRANCH] = None
        self.head = DEFAULT_BRANCH
        self.initialized = True
        return was_initialized

    def create_branch(self, name: str) -> None:
        """현재 HEAD 가 가리키는 커밋을 가리키는 새 브랜치를 만든다."""
        self._require_init()
        if not name or any(ch.isspace() for ch in name):
            raise MiniGitError("Invalid args")
        if name in self.branches:
            raise MiniGitError(f"Branch already exists: {name}")
        self.branches[name] = self.head_commit_hash

    def switch(self, name: str) -> None:
        """HEAD 를 지정한 브랜치로 옮긴다."""
        self._require_init()
        if name not in self.branches:
            raise MiniGitError(f"Unknown branch: {name}")
        self.head = name

    @property
    def head_commit_hash(self) -> Optional[str]:
        """HEAD(현재 브랜치)가 가리키는 커밋 hash. 커밋이 없으면 None."""
        return self.branches.get(self.head)

    # ------------------------------------------------------------------ 커밋
    def commit(self, message: str) -> Commit:
        """현재 HEAD 를 부모로 하는 새 커밋을 만들고 브랜치/역색인을 갱신한다."""
        self._require_init()
        if not message.strip():
            raise MiniGitError("Invalid args")
        parent = self.head_commit_hash
        parents = (parent,) if parent is not None else ()
        new_commit = self._add_commit(message, parents)
        self.branches[self.head] = new_commit.hash
        return new_commit

    def _add_commit(self, message: str, parents: Sequence[str]) -> Commit:
        """커밋 노드를 만들어 저장소와 역색인에 추가한다.

        새 커밋은 이미 존재하는 커밋만 부모로 가질 수 있으므로 간선은 항상
        "새 노드 -> 기존 노드" 방향이다. 따라서 사이클이 생길 수 없고 그래프는 DAG 를 유지한다.
        """
        for parent in parents:
            if parent not in self.commits:
                raise MiniGitError(f"Unknown commit: {parent}")
        timestamp = self._clock()
        commit_hash = self._generate_hash(message, self.user, timestamp, parents)
        new_commit = Commit(
            hash=commit_hash,
            message=message,
            author=self.user,
            timestamp=timestamp,
            parents=tuple(parents),
            seq=self._counter,
        )
        self.commits[commit_hash] = new_commit
        self.index.add_commit(commit_hash, message, self.user)
        return new_commit

    def _generate_hash(
        self, message: str, author: str, timestamp: datetime, parents: Sequence[str]
    ) -> str:
        """세션 내에서 유일한 커밋 hash 를 만든다.

        증가 카운터 + 커밋 내용을 SHA-1 로 해시한 뒤 앞 7자리를 사용한다.
        카운터가 매번 달라 입력이 겹치지 않으며, 그래도 앞자리가 기존 hash 와 겹치면
        길이를 늘리고(최대 40자), 그래도 겹치면 카운터를 올려 다시 만든다.
        저장소에 없는 값만 반환하므로 중복이 발생하지 않는다.
        """
        while True:
            self._counter += 1
            raw = "\0".join(
                [str(self._counter), author, timestamp.isoformat(), ",".join(parents), message]
            )
            digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
            for length in range(HASH_LENGTH, len(digest) + 1):
                candidate = digest[:length]
                if candidate not in self.commits:
                    return candidate

    def resolve(self, ref: str) -> Commit:
        """전체 hash 또는 고유한 hash 접두사(4자 이상)로 커밋을 찾는다."""
        self._require_init()
        ref = ref.lower()
        if ref in self.commits:
            return self.commits[ref]
        if len(ref) >= MIN_PREFIX_LENGTH:
            matches = [h for h in self.commits if h.startswith(ref)]
            if len(matches) == 1:
                return self.commits[matches[0]]
            if len(matches) > 1:
                raise MiniGitError(f"Ambiguous commit: {ref}")
        raise MiniGitError(f"Unknown commit: {ref}")

    # ------------------------------------------------------------------ 로그 / 탐색
    def _parents_graph(self) -> Dict[str, Sequence[str]]:
        """그래프 알고리즘에 넘길 hash -> 부모 hash 목록 인접 리스트."""
        return {h: c.parents for h, c in self.commits.items()}

    def log(self, sort_by: Optional[str] = None) -> List[Commit]:
        """커밋 목록을 반환한다.

        sort_by 가 없으면 위상 정렬 순서(부모가 항상 자식보다 먼저)이며, 위상 순서를 지키는
        범위에서 오래된 커밋이 먼저 온다.
        sort_by="date": timestamp 오름차순, "author": 작성자 이름 오름차순(대소문자 무시).
        두 경우 모두 안정 정렬(병합 정렬)이므로 동률이면 생성 순서를 유지한다.
        """
        self._require_init()
        if sort_by is None:
            order = graph.topological_order(
                self._parents_graph(),
                priority=lambda h: (self.commits[h].timestamp, self.commits[h].seq),
            )
            return [self.commits[h] for h in order]

        in_creation_order = list(self.commits.values())
        if sort_by == "date":
            return merge_sort(in_creation_order, key=lambda c: c.timestamp)
        if sort_by == "author":
            return merge_sort(in_creation_order, key=lambda c: c.author.lower())
        raise MiniGitError("Invalid args")

    def path(self, ref1: str, ref2: str) -> Optional[List[Commit]]:
        """두 커밋 사이의 (무방향) 최단 경로. 없으면 None."""
        start, goal = self.resolve(ref1), self.resolve(ref2)
        found = graph.shortest_path(self._parents_graph(), start.hash, goal.hash)
        if found is None:
            return None
        return [self.commits[h] for h in found]

    def ancestors(self, ref: str) -> List[Commit]:
        """커밋에서 도달 가능한 모든 조상 커밋 (가까운 조상부터)."""
        target = self.resolve(ref)
        return [self.commits[h] for h in graph.ancestors(self._parents_graph(), target.hash)]

    # ------------------------------------------------------------------ 검색
    def search(self, keyword: str) -> List[Commit]:
        """메시지에 키워드가 포함된 커밋 목록 (역색인 기반, 생성 순)."""
        self._require_init()
        if not keyword.strip():
            raise MiniGitError("Invalid args")
        return [self.commits[h] for h in self.index.search_keyword(keyword)]

    def search_author(self, name: str) -> List[Commit]:
        """특정 작성자의 커밋 목록 (역색인 기반, 생성 순)."""
        self._require_init()
        if not name.strip():
            raise MiniGitError("Invalid args")
        return [self.commits[h] for h in self.index.search_author(name)]

    # ------------------------------------------------------------------ 기타
    def branches_at(self, commit_hash: str) -> List[str]:
        """해당 커밋을 가리키는 브랜치 이름 목록 (현재 브랜치가 맨 앞)."""
        names = [name for name, h in self.branches.items() if h == commit_hash]
        if self.head in names:
            names.remove(self.head)
            names.insert(0, self.head)
        return names

    def _require_init(self) -> None:
        if not self.initialized:
            raise MiniGitError("Not a repository. Run INIT <user_name> first.")
