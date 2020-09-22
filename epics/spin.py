import asyncio
import base64
from asyncio import AbstractEventLoop
from datetime import datetime
from random import randint

import requests
from dateutil.parser import parse

from epics.auth import EAuth
from epics.utils import fail_fast_handler


class Spinner:
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

    def get_spinner_id(self) -> int:
        r = requests.get(self.spnr_url, auth=self.auth)
        r.raise_for_status()
        return r.json()['data']['id']

    def get_next_time(self) -> datetime:
        r = requests.get(self.usr_spnr_url, auth=self.auth)
        r.raise_for_status()
        return parse(r.json()['data']['nextSpin'])

    def spin(self) -> int:
        s_id = self.get_spinner_id()
        r = requests.post(self.spin_url, json={'spinnerId': s_id}, auth=self.auth)
        r.raise_for_status()
        return r.json()['data']['id']

    def schedule_spin(self, loop: AbstractEventLoop):
        r_id = self.spin()
        print(f'Got {r_id}')
        if r_id in [7544, 7543, 7539, 7538, 7537, 7535]:
            self.buy_round(amount=1)
            return loop.call_later(2, self.schedule_spin, loop)

        return loop.call_later(randint(1815, 1830), self.schedule_spin, loop)

    def start(self):
        next_time = self.get_next_time().utcnow()

        loop = asyncio.get_event_loop()
        loop.set_exception_handler(fail_fast_handler)

        loop.call_later(3500, self.auth.refresh_token)
        if next_time > datetime.utcnow():
            loop.call_at(next_time.timestamp() + 3, self.schedule_spin, loop)
        else:
            loop.call_soon(self.schedule_spin, loop)

        loop.run_forever()
        loop.close()


spinner = Spinner()
