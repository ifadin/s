import asyncio
import base64
import re
from asyncio import AbstractEventLoop
from copy import deepcopy
from random import randint
from typing import NamedTuple, Iterable, List, Dict, Tuple

import requests

from epics.auth import EAuth
from epics.utils import fail_fast_handler


class Opponent(NamedTuple):
    id: int
    wins: int
    required_wins: int

    @property
    def completed(self) -> bool:
        return self.wins >= self.required_wins


class Stage(NamedTuple):
    id: int
    name: str
    completed: bool
    opponents: List[Opponent]


class Circuit(NamedTuple):
    id: int
    name: str
    stages: List[Stage]
    stages_done: int
    stages_total: int

    @property
    def completed(self) -> bool:
        return self.stages_done == self.stages_total


class Achievement(NamedTuple):
    id: int
    title: str
    min: int
    max: int

    @property
    def left(self) -> int:
        return self.max - self.min

    @property
    def completed(self) -> bool:
        return self.left > 0


Schedule = Dict[int, Dict[int, Dict[int, int]]]


class Fighter:
    circuits_url = base64.b64decode(
        'aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL3VsdGltYXRlLXRlYW0vY2lyY3VpdHM='.encode()).decode()
    game_url = base64.b64decode(
        'aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL3VsdGltYXRlLXRlYW0vcHZlL2dhbWVz'.encode()).decode()
    tow_url = base64.b64decode('aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL3VsdGltYXRlLXRlYW0vcHZlL3Jvc3RlcnM/Y2F0Z'
                               'WdvcnlJZD0xJnRpZXI9dGVhbV9vZl90aGVfd2Vlaw=='.encode()).decode()
    achvmnt_url = base64.b64decode('aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL2FjaGlldmVtZW50cy80MDU0MzYvdXNlcj9jYXRl'
                                   'Z29yeUlkPTE='.encode()).decode()
    rstrs_url = base64.b64decode('aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL3VsdGltYXRlLXRlYW0vcHZlL3Jvc3RlcnM/Y2F0'
                                 'ZWdvcnlJZD0x'.encode()).decode()
    ua = base64.b64decode('b2todHRwLzMuMTIuMQ=='.encode()).decode()
    h = {'user-agent': ua}

    def __init__(self, auth=EAuth()) -> None:
        self.auth = auth

    def get_circuits(self) -> List[Circuit]:
        res = requests.get(f'{self.circuits_url}?categoryId=1', auth=self.auth, headers=self.h)
        res.raise_for_status()
        circuits = []
        for crc in res.json()['data']['circuits']:
            c_res = requests.get(f"{self.circuits_url}/{crc['id']}", auth=self.auth, headers=self.h)
            c_res.raise_for_status()
            c = c_res.json()['data']['circuit']

            circuits.append(Circuit(c['id'], c['name'], [
                Stage(s['id'], s['name'], bool(s.get('completed', False)), [
                    Opponent(r['ut_pve_roster_id'],
                             next(filter(
                                 lambda p: p['ut_pve_roster_id'] == r['ut_pve_roster_id'], s['rosterProgress']
                             ), {}).get('wins', 0),
                             r['wins'])
                    for r in s['rosters']
                ]) for s in c['stages']
            ], c['stagesCompleted'], c['totalStages']))

        return circuits

    @staticmethod
    def get_circuits_schedule(circuits: Iterable[Circuit]) -> Schedule:
        return {c.id: {
            s.id: {
                o.id: o.required_wins - o.wins for o in s.opponents if not o.completed
            } for s in c.stages if not s.completed
        } for c in circuits if not c.completed}

    def get_achievements(self) -> List[Achievement]:
        res = requests.get(self.achvmnt_url, auth=self.auth, headers=self.h)
        res.raise_for_status()

        return [
            Achievement(a['id'], a['title'], a['progress']['min'], a['progress']['max'])
            for a in res.json()['data']['weekly'] if not a['completed']
        ]

    def get_rosters(self, ids: Iterable[int]) -> Dict[str, int]:
        ids_param = ','.join((str(i) for i in ids))
        res = requests.get(f'{self.rstrs_url}&ids={ids_param}', auth=self.auth, headers=self.h)
        res.raise_for_status()

        return {r['name']: r['id'] for r in res.json()['data']['rosters']}

    def get_week_schedule(self, circuits: Iterable[Circuit]) -> Schedule:
        schedule = {}
        for a in self.get_achievements():
            m = re.match('^Win.*times against (.+) \((.+)\)$', a.title)
            if m and len(m.groups()) == 2:
                tm_name, stg_name = m.groups()
                for c in circuits:
                    for s in c.stages:
                        if s.name == stg_name:
                            rosters = self.get_rosters((o.id for o in s.opponents))
                            if tm_name not in rosters:
                                raise AssertionError(f'Unknown roster {tm_name}')
                            if c.id not in schedule:
                                schedule[c.id] = {}
                            if s.id not in schedule[c.id]:
                                schedule[c.id][s.id] = {}
                            schedule[c.id][s.id][rosters[tm_name]] = a.left
        return schedule

    def play_crc_game(self, roster_id: int, op_id: int, crc_id: int, stage_id: int) -> bool:
        r = requests.post(f'{self.game_url}', auth=self.auth, headers=self.h, json={
            'rosterId': roster_id, 'enemyRosterId': op_id, 'bannedMapIds': [2, 4], 'circuit': {
                'id': crc_id, 'stageId': stage_id
            }, 'categoryId': 1
        })
        r.raise_for_status()
        return r.json()['data']['game']['user1']['winner']

    def play_tow_game(self, roster_id: int, tow_id: int) -> bool:
        r = requests.post(f'{self.game_url}', auth=self.auth, headers=self.h, json={
            'rosterId': roster_id, 'enemyRosterId': tow_id, 'bannedMapIds': [2, 4], 'categoryId': 1
        })
        r.raise_for_status()
        return r.json()['data']['game']['user1']['winner']

    @staticmethod
    def update_schedule(schedule: Schedule, game: Tuple[int, int, int]) -> Schedule:
        c_id, s_id, o_id = game
        s = deepcopy(schedule)
        w = s[c_id][s_id][o_id]
        if w > 1:
            s[c_id][s_id][o_id] = w - 1
        else:
            del s[c_id][s_id][o_id]
            if not s[c_id][s_id]:
                del s[c_id][s_id]
                if not s[c_id]:
                    del s[c_id]
        return s

    def get_tow(self) -> int:
        res = requests.get(self.tow_url, auth=self.auth, headers=self.h)
        res.raise_for_status()

        return res.json()['data']['rosters'][0]['id']

    def play_tow(self, roster_id: int, tow_id: int, l: AbstractEventLoop):
        res = self.play_tow_game(roster_id, tow_id)
        print(f'TOW {res}')

        return l.call_later(randint(5, 10), self.play_tow, roster_id, tow_id, l)

    def play_schedule(self, roster_id: int, s: Schedule, l: AbstractEventLoop):
        if s:
            c_id, c = list(s.items())[0]
            if c:
                st_id, st = list(c.items())[0]
                if st:
                    op_id, w = list(st.items())[0]
                    if w > 0:
                        res = self.play_crc_game(roster_id, op_id, c_id, st_id)
                        print(f'{c_id} {st_id} {op_id} - {res}')
                        if res:
                            s = self.update_schedule(s, (c_id, st_id, op_id))
                        return l.call_later(randint(5, 10), self.play_schedule, roster_id, s, l)

        print('[error] could not find any play')

    def start(self, roster_id: int = 57654, mode: int = 1):
        supported_modes = {1, 2, 3}
        if mode not in supported_modes:
            raise AssertionError(f'Mode parameter can only be one of {supported_modes}')

        loop = asyncio.get_event_loop()
        loop.set_exception_handler(fail_fast_handler)

        loop.call_later(3500, self.auth.refresh_token)
        if mode == 1:
            s = self.get_circuits_schedule(self.get_circuits())
            loop.call_soon(self.play_schedule, roster_id, s, loop)
        if mode == 2:
            s = self.get_week_schedule(self.get_circuits())
            loop.call_soon(self.play_schedule, roster_id, s, loop)
        if mode == 3:
            tow_id = self.get_tow()
            loop.call_soon(self.play_tow, roster_id, tow_id, loop)

        loop.run_forever()
        loop.close()


fighter = Fighter()
