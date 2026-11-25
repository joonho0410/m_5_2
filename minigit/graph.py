"""커밋 그래프 탐색 알고리즘.

모든 함수는 Commit 클래스에 의존하지 않고 ``parents_of: {node: [parent, ...]}`` 형태의
일반 그래프(인접 리스트)를 입력으로 받는다. 간선 방향은 "자식 -> 부모" 이다.
그래프 전용 라이브러리는 사용하지 않는다.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set

from .sorting import MinHeap

Graph = Mapping[str, Sequence[str]]


def topological_order(parents_of: Graph, priority: Callable[[str], Any]) -> List[str]:
    """부모가 항상 자식보다 먼저 오도록 노드를 나열한다 (Kahn 알고리즘).

    1. 각 노드의 진입 차수 = 부모 수.
    2. 진입 차수가 0인 노드(루트 커밋)를 후보로 넣는다.
    3. 후보 중 priority 가 가장 작은 노드를 꺼내 출력하고,
       그 자식들의 진입 차수를 1씩 줄여 0이 되면 후보에 넣는다.

    후보 집합을 최소 힙으로 관리하므로, 위상 순서를 지키는 범위 안에서
    priority(예: 생성 시각)가 작은 커밋이 먼저 나온다.

    시간복잡도: O((V + E) log V)

    Raises:
        ValueError: 사이클이 있어 DAG 가 아닌 경우.
    """
    children_of: Dict[str, List[str]] = {node: [] for node in parents_of}
    indegree: Dict[str, int] = {}
    for node, parents in parents_of.items():
        unique_parents = set(parents)
        indegree[node] = len(unique_parents)
        for parent in unique_parents:
            children_of[parent].append(node)

    ready: MinHeap[str] = MinHeap()
    for node, degree in indegree.items():
        if degree == 0:
            ready.push(priority(node), node)

    order: List[str] = []
    while len(ready) > 0:
        node = ready.pop()
        order.append(node)
        for child in children_of[node]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.push(priority(child), child)

    if len(order) != len(parents_of):
        raise ValueError("commit graph has a cycle (not a DAG)")
    return order


def build_undirected(parents_of: Graph) -> Dict[str, Set[str]]:
    """자식-부모 간선을 양방향으로 간주한 인접 집합을 만든다. O(V + E)."""
    adjacency: Dict[str, Set[str]] = {node: set() for node in parents_of}
    for node, parents in parents_of.items():
        for parent in parents:
            adjacency[node].add(parent)
            adjacency[parent].add(node)
    return adjacency


def shortest_path(parents_of: Graph, start: str, goal: str) -> Optional[List[str]]:
    """간선을 무방향으로 볼 때 start 에서 goal 까지의 최단 경로(간선 수 최소)를 구한다.

    최단 경로가 여러 개라면 "h1->h2->..." 문자열이 사전순으로 가장 작은 경로를 고른다.

    방법:
        1. goal 에서 BFS 를 돌려 모든 노드의 goal 까지 거리 dist 를 구한다.
        2. start 부터 한 칸씩 이동하되, dist 가 정확히 1 줄어드는 이웃 중
           hash 가 사전순으로 가장 작은 이웃을 탐욕적으로 고른다.

    2번 탐욕 선택이 옳은 이유: 모든 후보 경로는 같은 노드에서 시작하므로, 두 경로 문자열의
    대소는 처음으로 달라지는 hash 에서 결정된다. 또한 hash 는 16진수 문자로만 이루어져
    있고 구분자 '-'(0x2D)는 어떤 16진수 문자보다 작으므로, hash 길이가 서로 달라도
    "hash 끼리의 사전순 비교" 결과가 "경로 문자열의 사전순 비교" 결과와 같다.
    dist 가 1 씩 줄어드는 이웃만 고르므로 경로 길이는 항상 최단이다.

    시간복잡도: O(V + E) (BFS) + O(경로 길이 x 차수) (복원)

    Returns:
        노드 목록(start, ..., goal). 연결되어 있지 않으면 None.
    """
    adjacency = build_undirected(parents_of)

    dist: Dict[str, int] = {goal: 0}
    queue = deque([goal])
    while queue:
        node = queue.popleft()
        for neighbor in adjacency[node]:
            if neighbor not in dist:
                dist[neighbor] = dist[node] + 1
                queue.append(neighbor)

    if start not in dist:
        return None

    path = [start]
    current = start
    while current != goal:
        best: Optional[str] = None
        for neighbor in adjacency[current]:
            if dist.get(neighbor) == dist[current] - 1 and (best is None or neighbor < best):
                best = neighbor
        assert best is not None  # dist 가 정의된 노드는 반드시 goal 쪽 이웃이 있다.
        path.append(best)
        current = best
    return path


def ancestors(parents_of: Graph, start: str) -> List[str]:
    """start 에서 부모 방향으로 도달 가능한 모든 조상을 BFS 로 빠짐없이 찾는다.

    visited 집합으로 병합 구조(다이아몬드 모양)에서 같은 조상이 중복 출력되지 않게 한다.
    결과는 가까운 조상부터(BFS 순서) 나열되며 start 자신은 포함하지 않는다.

    시간복잡도: O(V + E)
    """
    visited: Set[str] = {start}
    order: List[str] = []
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for parent in parents_of[node]:
            if parent not in visited:
                visited.add(parent)
                order.append(parent)
                queue.append(parent)
    return order
