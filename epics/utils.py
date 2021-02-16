from asyncio import AbstractEventLoop
from time import sleep

from requests import HTTPError, Response, Session, PreparedRequest
from requests.adapters import HTTPAdapter
from typing import Iterator, List, Callable
from urllib3 import Retry


def get_http_session() -> Session:
    s = Session()
    s.mount('http://', HTTPAdapter(
        max_retries=Retry(10, status=10, backoff_factor=1, status_forcelist=Retry.RETRY_AFTER_STATUS_CODES)))
    return s


def with_retry(r: Response, session: Session, sleep_fc: Callable[[int], None] = sleep):
    if r.status_code == 429:
        print(f'429: sleeping...')
        sleep_fc(3)
        req: PreparedRequest = r.request
        return with_retry(session.send(req), session)

    return r


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
