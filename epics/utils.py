from asyncio import AbstractEventLoop

from requests import HTTPError


def fail_fast_handler(l: AbstractEventLoop, context: dict):
    e = context.get('exception')
    if isinstance(e, HTTPError):
        print(f'[error]: {e.request.url}\n{e.request.body}')
    l.default_exception_handler(context)
    l.stop()
