import asyncio
import base64
import re
from copy import deepcopy
from itertools import chain
from operator import itemgetter
from random import randint

import requests
from typing import NamedTuple, List, Dict, Tuple, Optional

from epics.auth import EAuth


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


class Goal(NamedTuple):
    id: int
    title: str
    min: int
    max: int
    available: bool

    @property
    def left(self) -> int:
        return self.max - self.min

    @property
    def completed(self) -> bool:
        return self.left > 0


Schedule = Dict[int, Dict[int, Dict[int, int]]]


class Trainer:
    circuits_url = base64.b64decode(
        'aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL3VsdGltYXRlLXRlYW0vY2lyY3VpdHM='.encode()).decode()
    game_url = base64.b64decode(
        'aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL3VsdGltYXRlLXRlYW0vcHZlL2dhbWVz'.encode()).decode()
    op_game_url = base64.b64decode(
        'aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL3VsdGltYXRlLXRlYW0vcHZwL2NoYWxsZW5nZXM='.encode()).decode()
    goals_url = base64.b64decode('aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL2FjaGlldmVtZW50cw=='.encode()).decode()
    tow_url = base64.b64decode('aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL3VsdGltYXRlLXRlYW0vcHZlL3Jvc3RlcnM/Y2F0Z'
                               'WdvcnlJZD0xJnRpZXI9dGVhbV9vZl90aGVfd2Vlaw=='.encode()).decode()
    rstrs_url = base64.b64decode('aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL3VsdGltYXRlLXRlYW0vcHZlL3Jvc3RlcnM/Y2F0'
                                 'ZWdvcnlJZD0x'.encode()).decode()
    ua = base64.b64decode('b2todHRwLzMuMTIuMQ=='.encode()).decode()
    h = {'user-agent': ua}

    def __init__(self, u_id: int, auth: EAuth) -> None:
        self.u_id = u_id
        self.auth = auth
        self.user_goals_url = f'{self.goals_url}/{self.u_id}/user?categoryId=1'
        self.usr_rstrs_url = base64.b64decode('aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL3VsdGltYXRlLXRlYW0vcm9zdGVycz9jYX'
                                              'RlZ29yeUlkPTE='.encode()).decode() + f'&userId={self.u_id}'

    async def run(self, op=None):
        usr_roster_id = self.get_usr_roster_id()

        main_s = self.get_circuits_schedule(self.get_circuits())
        if main_s:
            await self.play_schedule(usr_roster_id, main_s)
        else:
            print(f'[{self.u_id}] no main schedule')

        week_s = self.get_week_schedule(self.get_goals(), self.get_circuits())
        if week_s:
            await self.play_schedule(usr_roster_id, week_s)
        else:
            print(f'[{self.u_id}] no week schedule')

        g_amount = self.get_goal_amount(self.get_goals())
        if g_amount:
            tow_id = self.get_tow()
            await self.play_tow(usr_roster_id, tow_id, g_amount)
        else:
            print(f'[{self.u_id}] no goal amount')

        if op:
            op_amount = self.get_op_goal_amount(self.get_goals())
            if op_amount:
                op_roster_id = op.get_usr_roster_id()
                await self.play_op(op_amount, usr_roster_id, op_roster_id, op)
            else:
                print(f'[{self.u_id}] no op amount')

        for g in self.get_goals():
            if g.available:
                self.complete_goal(g)
                print(f'[{self.u_id}] claimed {g.title}')

    def get_goals(self) -> List[Goal]:
        res = requests.get(self.user_goals_url, auth=self.auth, headers=self.h)
        res.raise_for_status()

        return [
            Goal(a['id'], a['title'], a['progress']['min'], a['progress']['max'], a['progress']['claimAvailable'])
            for a in chain(res.json()['data']['daily'], res.json()['data']['weekly']) if not a['completed']
        ]

    def complete_goal(self, g: Goal):
        res = requests.post(f'{self.goals_url}/{g.id}/claim?categoryId=1', auth=self.auth, headers=self.h)
        res.raise_for_status()

        return True

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
    def get_circuits_schedule(circuits: List[Circuit]) -> Schedule:
        return {c.id: {
            s.id: {
                o.id: o.required_wins - o.wins for o in s.opponents if not o.completed
            } for s in c.stages if not s.completed
        } for c in circuits if not c.completed}

    def get_week_schedule(self, goals: List[Goal], circuits: List[Circuit]) -> Schedule:
        schedule = {}
        for g in goals:
            m = re.match('^Win.*times against (.+) \((.+)\)$', g.title)
            if m and len(m.groups()) == 2:
                tm_name = m.groups()[0].lower()
                stg_name = m.groups()[1]
                for c in circuits:
                    for s in c.stages:
                        if s.name == stg_name:
                            rosters = self.get_rosters([o.id for o in s.opponents])
                            if tm_name not in rosters:
                                raise AssertionError(f'Unknown roster {tm_name} from available {rosters}')
                            if c.id not in schedule:
                                schedule[c.id] = {}
                            if s.id not in schedule[c.id]:
                                schedule[c.id][s.id] = {}
                            schedule[c.id][s.id][rosters[tm_name]] = g.left
        return schedule

    @staticmethod
    def get_goal_amount(goals: List[Goal]) -> Optional[int]:
        g = next((g for g in goals if re.match('^Win \\d+ R.*atches$', g.title)), None)
        if not g:
            return None

        return g.left

    @staticmethod
    def get_op_goal_amount(goals: List[Goal]) -> Optional[int]:
        g = next((g for g in goals if re.match('^Win \\d+ PvP R.*atches$', g.title)), None)
        if not g:
            return None

        return g.left

    def get_rosters(self, ids: List[int]) -> Dict[str, int]:
        ids_param = ','.join((str(i) for i in ids))
        res = requests.get(f'{self.rstrs_url}&ids={ids_param}', auth=self.auth, headers=self.h)
        res.raise_for_status()

        return {r['name'].lower(): r['id'] for r in res.json()['data']['rosters']}

    def get_usr_roster_id(self) -> int:
        res = requests.get(f'{self.usr_rstrs_url}', auth=self.auth, headers=self.h)
        res.raise_for_status()

        return max(((r['id'], r['rating']) for r in res.json()['data']['rosters']), key=itemgetter(1))[0]

    def get_tow(self) -> int:
        res = requests.get(self.tow_url, auth=self.auth, headers=self.h)
        res.raise_for_status()

        return res.json()['data']['rosters'][0]['id']

    def create_op_game(self, op_id: int, user_roster_id: int, op_roster_id: int) -> int:
        res = requests.post(f'{self.op_game_url}', json={
            'categoryId': 1, 'userId': op_id, 'rosterId': user_roster_id, 'enemyRosterId': op_roster_id,
            'bannedMapIds': [4, 6], 'message': ''
        }, auth=self.auth, headers=self.h)
        res.raise_for_status()
        return res.json()['data']['id']

    async def play_tow(self, roster_id: int, tow_id: int, w_amount: int):
        if not w_amount:
            return True

        res = self.play_tow_game(roster_id, tow_id)
        print(f'[{self.u_id}] TOW {res} ({w_amount})')

        await asyncio.sleep(randint(5, 10))
        return await self.play_tow(roster_id, tow_id, w_amount - 1 if res else w_amount)

    def play_tow_game(self, roster_id: int, tow_id: int) -> bool:
        r = requests.post(f'{self.game_url}', auth=self.auth, headers=self.h, json={
            'rosterId': roster_id, 'enemyRosterId': tow_id, 'bannedMapIds': [2, 4], 'categoryId': 1
        })
        r.raise_for_status()
        return r.json()['data']['game']['user1']['winner']

    async def play_schedule(self, roster_id: int, s: Schedule):
        if s:
            c_id, c = list(s.items())[0]
            if c:
                st_id, st = list(c.items())[0]
                if st:
                    op_id, w = list(st.items())[0]
                    if w > 0:
                        res = self.play_crc_game(roster_id, op_id, c_id, st_id)
                        print(f'[{self.u_id}] {c_id} {st_id} {op_id} - {res}')
                        if res:
                            s = self.update_schedule(s, (c_id, st_id, op_id))
                        await asyncio.sleep(randint(5, 10))
                        return await self.play_schedule(roster_id, s)

    def play_crc_game(self, roster_id: int, op_id: int, crc_id: int, stage_id: int) -> bool:
        r = requests.post(f'{self.game_url}', auth=self.auth, headers=self.h, json={
            'rosterId': roster_id, 'enemyRosterId': op_id, 'bannedMapIds': [2, 4], 'circuit': {
                'id': crc_id, 'stageId': stage_id
            }, 'categoryId': 1
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

    async def play_op(self, op_amount: int, usr_roster_id: int, op_roster_id: int, op):
        if not op_amount:
            return True
        g_id = self.create_op_game(op.u_id, usr_roster_id, op_roster_id)
        op_w = op.accept_game(g_id, op_roster_id)
        print(f'[{self.u_id}] OP {not op_w} ({op_amount})')
        self.seen_game(g_id)

        await asyncio.sleep(randint(5, 10))
        return await self.play_op(op_amount if op_w else op_amount - 1, usr_roster_id, op_roster_id, op)

    def accept_game(self, game_id: int, usr_roster_id: int) -> bool:
        res = requests.post(f'{self.op_game_url}/{game_id}/accept',
                            json={'rosterId': usr_roster_id, 'bannedMapIds': [7, 5]}, auth=self.auth, headers=self.h)
        res.raise_for_status()
        return res.json()['data']['game']['user2']['winner']

    def seen_game(self, game_id: int) -> bool:
        res = requests.post(f'{self.op_game_url}/{game_id}/seen', auth=self.auth, headers=self.h)
        res.raise_for_status()
        return res.json()['success']
