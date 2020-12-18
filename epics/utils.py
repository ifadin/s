from asyncio import AbstractEventLoop

from requests import HTTPError, Response
from typing import Iterator, List


def fail_fast_handler(l: AbstractEventLoop, context: dict):
    e = context.get('exception')
    if isinstance(e, HTTPError):
        print(f'[error]: {e.response.status_code} {e.request.url}\n{e.request.body}\n{e.response.text}')
    l.default_exception_handler(context)
    l.stop()


def raise_for_status(res: Response):
    if not res.ok:
        raise_http_error(res)


def raise_http_error(res: Response):
    raise HTTPError(f'[error]: {res.status_code} {res.request.url}\n{res.request.body}\n{res.text}')


def get_batches(items_to_process: list, size: int = None) -> Iterator[List]:
    size = size if size else len(items_to_process)
    for i in range(0, len(items_to_process), size):
        yield items_to_process[i:i + size]
