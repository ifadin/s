from asyncio import AbstractEventLoop

from requests import HTTPError, Response


def fail_fast_handler(l: AbstractEventLoop, context: dict):
    e = context.get('exception')
    if isinstance(e, HTTPError):
        print(f'[error]: {e.request.url}\n{e.request.body}')
    l.default_exception_handler(context)
    l.stop()


def raise_for_status(res: Response):
    if not res.ok:
        raise_http_error(res)


def raise_http_error(res: Response):
    raise HTTPError(f'[error]: {res.status_code} {res.request.url}\n{res.request.body}\n{res.text}')
