from collections import deque

from typing import Iterable, Tuple


class MinMaxQueue:

    def __init__(self, arr: Iterable[int] = None) -> None:
        self.q = deque()
        self.index = 0
        self.min = deque()
        self.max = deque()

        for v in (arr or []):
            self.append(v)

    def __bool__(self) -> bool:
        return bool(self.q)

    def append(self, v: int) -> None:
        el = (v, self.index)
        self.q.append(el)
        self._update_min(el)
        self._update_max(el)

        self.index += 1

    def _update_min(self, el: Tuple[int, int]):
        while self.min and el[0] < self.min[-1][0]:
            self.min.pop()
        self.min.append(el)

    def _update_max(self, el: Tuple[int, int]):
        while self.max and el[0] > self.max[-1][0]:
            self.max.pop()
        self.max.append(el)

    def pop(self) -> int:
        el, index = self.q.popleft()
        if index == self.min[0][1]:
            self.min.popleft()
        if index == self.max[0][1]:
            self.max.popleft()
        return el

    def get_min(self) -> int:
        return self.min[0][0]

    def get_max(self) -> int:
        return self.max[0][0]
