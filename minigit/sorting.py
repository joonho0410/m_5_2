"""정렬 알고리즘 직접 구현.

과제 제약상 sorted(), list.sort() 를 사용하지 않는다.

- merge_sort: 안정(stable) 정렬. LOG --sort-by 에 사용한다.
- MinHeap: 이진 최소 힙. 위상 정렬(Kahn)에서 "다음에 출력할 커밋"을 고를 때 사용한다.
"""

from __future__ import annotations

from typing import Any, Callable, Generic, List, Optional, Sequence, Tuple, TypeVar

T = TypeVar("T")
KeyFunc = Callable[[T], Any]


def merge_sort(items: Sequence[T], key: Optional[KeyFunc] = None) -> List[T]:
    """병합 정렬로 정렬된 새 리스트를 반환한다 (원본은 변경하지 않음).

    비교 기준은 ``key`` 함수로 바꿀 수 있다. (예: 날짜 기준, 작성자 기준)

    시간복잡도: 평균 O(n log n), 최악 O(n log n)
        - 매 단계 리스트를 절반으로 나누므로 깊이는 log n,
          각 깊이에서 병합에 드는 비용의 합은 n 이다.
    공간복잡도: O(n) (병합 시 보조 리스트)
    안정 정렬: 예. key 가 같으면 원래 순서를 유지한다.
        - 병합 시 왼쪽 원소가 오른쪽 원소보다 "엄격히 클 때만" 오른쪽을 먼저 넣기 때문.

    Args:
        items: 정렬할 원소들.
        key: 각 원소에서 비교 키를 뽑는 함수. 생략하면 원소 자체를 비교한다.
    """
    key_fn: KeyFunc = key if key is not None else (lambda x: x)
    # key 를 원소마다 한 번만 계산해 둔다 (decorate-sort-undecorate).
    decorated: List[Tuple[Any, T]] = [(key_fn(item), item) for item in items]
    return [item for _, item in _merge_sort(decorated)]


def _merge_sort(arr: List[Tuple[Any, T]]) -> List[Tuple[Any, T]]:
    """(key, item) 리스트를 key 기준으로 재귀적으로 병합 정렬한다."""
    if len(arr) <= 1:
        return arr[:]
    mid = len(arr) // 2
    return _merge(_merge_sort(arr[:mid]), _merge_sort(arr[mid:]))


def _merge(left: List[Tuple[Any, T]], right: List[Tuple[Any, T]]) -> List[Tuple[Any, T]]:
    """정렬된 두 리스트를 하나로 합친다. key 만 비교하며, 동률이면 왼쪽을 먼저 둔다(안정성)."""
    merged: List[Tuple[Any, T]] = []
    i = j = 0
    while i < len(left) and j < len(right):
        if right[j][0] < left[i][0]:
            merged.append(right[j])
            j += 1
        else:
            merged.append(left[i])
            i += 1
    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged


class MinHeap(Generic[T]):
    """(key, item) 쌍을 저장하는 이진 최소 힙.

    push / pop: O(log n), peek / len: O(1).
    key 끼리만 비교하므로 item 은 비교 불가능한 객체여도 된다.
    """

    def __init__(self) -> None:
        self._data: List[Tuple[Any, T]] = []

    def __len__(self) -> int:
        return len(self._data)

    def push(self, key: Any, item: T) -> None:
        """원소를 넣고 위로 올리며(sift-up) 힙 속성을 복구한다."""
        self._data.append((key, item))
        idx = len(self._data) - 1
        while idx > 0:
            parent = (idx - 1) // 2
            if self._data[idx][0] < self._data[parent][0]:
                self._data[idx], self._data[parent] = self._data[parent], self._data[idx]
                idx = parent
            else:
                break

    def pop(self) -> T:
        """key 가 가장 작은 원소를 꺼낸다. 비어 있으면 IndexError."""
        if not self._data:
            raise IndexError("pop from empty heap")
        last = self._data.pop()
        if not self._data:
            return last[1]
        top = self._data[0]
        self._data[0] = last
        self._sift_down(0)
        return top[1]

    def _sift_down(self, idx: int) -> None:
        """idx 위치의 원소를 아래로 내리며(sift-down) 힙 속성을 복구한다."""
        n = len(self._data)
        while True:
            smallest = idx
            left, right = 2 * idx + 1, 2 * idx + 2
            if left < n and self._data[left][0] < self._data[smallest][0]:
                smallest = left
            if right < n and self._data[right][0] < self._data[smallest][0]:
                smallest = right
            if smallest == idx:
                return
            self._data[idx], self._data[smallest] = self._data[smallest], self._data[idx]
            idx = smallest
