from typing import Iterator, List


def get_batches(items_to_process: list, size: int = None) -> Iterator[List]:
    size = size if size else len(items_to_process)
    for i in range(0, len(items_to_process), size):
        yield items_to_process[i:i + size]
