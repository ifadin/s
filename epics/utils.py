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


def with_retry(r: Response, session: Session,
               raise_status: bool = True,
               sleep_fc: Callable[[int], None] = sleep) -> Response:
    if r.status_code in Retry.RETRY_AFTER_STATUS_CODES:
        print(f'{r.status_code} sleeping...')
        sleep_fc(5)
        req: PreparedRequest = r.request
        return with_retry(session.send(req), session, raise_status=raise_status, sleep_fc=sleep_fc)

    if not r.ok:
        raise_http_error(r) if raise_status else log_http_error(r)

    return r


def fail_fast_handler(l: AbstractEventLoop, context: dict):
    e = context.get('exception')
    if isinstance(e, HTTPError):
        print(f'[error]: {e.response.status_code} {e.request.url}\n{e.request.body}\n{e.response.text}')
    l.default_exception_handler(context)
    l.stop()


def get_error_msg(r: Response) -> str:
    return f'[error]: {r.status_code} {r.request.method} {r.request.url}\n{r.request.body}\n{r.text}'


def log_http_error(r: Response):
    print(get_error_msg(r))


def raise_for_status(res: Response):
    if not res.ok:
        raise_http_error(res)


def raise_http_error(r: Response):
    raise HTTPError(get_error_msg(r))


def get_batches(items_to_process: list, size: int = None) -> Iterator[List]:
    size = size if size else len(items_to_process)
    for i in range(0, len(items_to_process), size):
        yield items_to_process[i:i + size]
