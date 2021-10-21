from typing import List


def merge_sort_and_count(arr: List[int]) -> int:
    if len(arr) < 2:
        return 0

    count = 0
    m = len(arr) // 2
    left, right = arr[:m], arr[m:]
    count += merge_sort_and_count(left)
    count += merge_sort_and_count(right)

    l, r = 0, 0
    while l < len(left) and r < len(right):
        if left[l] <= right[r]:
            arr[l + r] = left[l]
            l += 1
        else:
            arr[l + r] = right[r]
            r += 1
            count += len(left) - l

    while l < len(left):
        arr[l + r] = left[l]
        l += 1
    while r < len(right):
        arr[l + r] = right[r]
        r += 1

    return count