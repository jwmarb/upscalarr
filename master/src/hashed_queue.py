from collections import deque
from typing import TypeVar, Generic

T = TypeVar('T')


class HashedQueue(Generic[T]):
    def __init__(self):
        self._q: deque[T] = deque()
        self._set: set[T] = set()

    def enqueue(self, item: T):
        if item in self._set:
            return

        self._set.add(item)
        self._q.appendleft(item)

    def dequeue(self) -> T:
        item = self._q.pop()
        self._set.remove(item)
        return item

    def __len__(self):
        return len(self._q)
