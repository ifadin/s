import asyncio
import base64
from asyncio import AbstractEventLoop
from datetime import datetime, timezone
from random import randint
from time import time
from typing import NamedTuple, Dict, List

import requests
from dateutil.parser import parse

from epics.auth import EAuth
from epics.utils import fail_fast_handler


class SpinItem(NamedTuple):
    id: int
    name: int
    props: dict


class Spinner(NamedTuple):
    id: int
    items: Dict[int, SpinItem]

    def get_coin_items(self, value: int) -> List[SpinItem]:
        return [i for i in self.items.values() if i.props['coins'] >= value]


class SpinService:
    buy_url = base64.b64decode(
        'aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL3NwaW5uZXIvYnV5LXNwaW4/Y2F0ZWdvcnlJZD0x'.encode()).decode()
    spnr_url = base64.b64decode('aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL3NwaW5uZXI/Y2F0ZWdvcnlJZD0x'.encode()).decode()
    usr_spnr_url = base64.b64decode(
        'aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL3NwaW5uZXIvdXNlcj9jYXRlZ29yeUlkPTE='.encode()).decode()
    spin_url = base64.b64decode(
        'aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL3NwaW5uZXIvc3Bpbj9jYXRlZ29yeUlkPTE='.encode()).decode()

    def __init__(self, auth: EAuth = EAuth()) -> None:
        self.auth = auth

    def buy_round(self, amount: int = 1):
        r = requests.post(self.buy_url, json={'amount': amount}, auth=self.auth)
        r.raise_for_status()
        return r.json().get('success')

    def get_spinner(self) -> Spinner:
        r = requests.get(self.spnr_url, auth=self.auth)
        r.raise_for_status()
        d = r.json()['data']
        return Spinner(d['id'], {i['id']: SpinItem(i['id'], i['name'], i['properties']) for i in d['items']})

    def get_next_time(self) -> datetime:
        r = requests.get(self.usr_spnr_url, auth=self.auth)
        r.raise_for_status()
        return parse(r.json()['data']['nextSpin'])

    def spin(self, spinner_id: int) -> int:
        r = requests.post(self.spin_url, json={'spinnerId': spinner_id}, auth=self.auth)
        r.raise_for_status()
        return r.json()['data']['id']

    def schedule_spin(self, loop: AbstractEventLoop):
        try:
            s = self.get_spinner()
            r_id = self.spin(s.id)
            print(f'Got {s.items[r_id].name} ({r_id})')

            if r_id in (i.id for i in s.get_coin_items(10)):
                self.buy_round(amount=1)
                return loop.call_later(2, self.schedule_spin, loop)
        except Exception as e:
            print(e)
            print(f'Rescheduling due to error')
            return loop.call_later(5, self.schedule_spin, loop)

        return loop.call_later(randint(1815, 1830), self.schedule_spin, loop)

    def start(self):
        wait_time = self.get_next_time().replace(tzinfo=timezone.utc).timestamp() - time()

        loop = asyncio.get_event_loop()
        loop.set_exception_handler(fail_fast_handler)

        loop.call_later(3500, self.auth.refresh_token)
        if wait_time > 0:
            w = int(wait_time) + 1
            print(f'Will start in {w}')
            loop.call_at(loop.time() + w, self.schedule_spin, loop)
        else:
            loop.call_soon(self.schedule_spin, loop)

        loop.run_forever()
        loop.close()
