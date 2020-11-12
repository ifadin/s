import base64
from copy import deepcopy

import requests
from typing import Set, NamedTuple, Optional, Dict

from epics.auth import EAuth
from epics.player import PlayerService
from epics.utils import raise_for_status


class Requirement(NamedTuple):
    id: int
    s_coins: int
    amount: int


class Card(NamedTuple):
    id: int
    mint_c: str
    mint_n: int
    template_id: int
    template_title: str
    is_new: bool = False

    @property
    def mint(self) -> str:
        return self.mint_c + str(self.mint_n)


Collection = Dict[int, Set[int]]


class Crafter:
    craft_url = base64.b64decode('aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL2NyYWZ0aW5nL3BsYW5zLw=='.encode()).decode()
    slot_url = base64.b64decode('aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL2NyYWZ0aW5nL3Nsb3RzLw=='.encode()).decode()
    usr_slots_url = base64.b64decode('aHR0cHM6Ly9hcGkuZXBpY3MuZ2cvYXBpL3YxL2NyYWZ0aW5nL3VzZXI'
                                     'tc2xvdHM/Y2F0ZWdvcnlJZD0x'.encode()).decode()
    requirements = {
        'd': Requirement(301, 2500, 10), 'g': Requirement(300, 500, 4),
        's': Requirement(299, 500, 3), 'p': Requirement(298, 500, 2),
        't1': Requirement(302, 12500, 10)
    }
    collections = {
        'd': {2967}, 'g': {2968}, 's': {2970}, 'p': {2969},
        't1': {2971, 2972, 2973, 2974, 2975, 2977, 2978, 2979, 2980, 2981}
    }
    ua = base64.b64decode('b2todHRwLzMuMTIuMQ=='.encode()).decode()
    h = {'user-agent': ua}

    def __init__(self, u_id: int, auth: EAuth) -> None:
        self.u_id = u_id
        self.auth = auth
        self.p_service = PlayerService(u_id, self.auth)

    def request_craft(self, r: Requirement, entity_ids: Set[int]) -> int:
        if len(entity_ids) != r.amount:
            raise AssertionError(f'[{self.u_id}] Required {r.amount} entities')
        res = requests.post(f'{self.craft_url}{r.id}?categoryId=1', auth=self.auth, json={
            'silvercoins': r.s_coins,
            'requirements': [{'requirementId': r.id, 'entityIds': list(entity_ids)}]

        }, headers=self.h)
        raise_for_status(res)
        slots = self.get_user_slots()
        if all(not ready for ready in slots.values()):
            raise AssertionError(f'[{self.u_id}] No ready slots')

        return next((s for s, ready in slots.items() if ready))

    def get_user_slots(self) -> Dict[int, bool]:
        res = requests.get(f'{self.usr_slots_url}', auth=self.auth, headers=self.h)
        raise_for_status(res)
        return {s['id']: s['readyToOpen'] for s in res.json()['data']['slots']}

    def request_slot(self, slot_id: int) -> Optional[Card]:
        res = requests.post(f'{self.slot_url}{slot_id}/open-instant?categoryId=1', auth=self.auth, json={
            'craftingcoins': None
        }, headers=self.h)
        raise_for_status(res)
        return next((Card(c['id'], c['mintBatch'], c['mintNumber'], c['cardTemplate']['id'], c['cardTemplate']['title'],
                          c['isNewCardTemplate']) for c in res.json()['data']['cards']), None)

    def craft_item(self, item_type: str, entity_ids: Set[int]) -> Card:
        r = self.requirements[item_type]
        s = self.request_craft(r, entity_ids)
        return self.request_slot(s)

    @staticmethod
    def get_duplicates_amount(collection: Collection) -> int:
        return sum((len(v) - 1 for v in collection.values() if len(v) > 1))

    @staticmethod
    def get_duplicate_entities(collection: Collection, amount: int) -> Collection:
        added = 0
        col = {}
        for item_id, v in collection.items():
            for i in sorted(list(v))[1:]:
                col[item_id] = col.get(item_id, set()) | {i}
                added = added + 1
                if added == amount:
                    return col

        return col

    @staticmethod
    def update_collection(collection: Collection, entities: Collection) -> Collection:
        c = deepcopy(collection)
        for i_id, items in entities.items():
            diff = c[i_id] - items
            if not diff:
                raise AssertionError(f'[{self.u_id}] Risk of items loss for {c[i_id]} from {items}')
            c[i_id] = diff
        return c

    def craft(self, item_type: str, amount: int = None):
        if item_type not in self.requirements:
            raise AssertionError(f'[{self.u_id}] Supported item types are {self.requirements}')

        r = self.requirements[item_type]
        col = {
            t_id: c_ids
            for col_id in self.collections[item_type]
            for t_id, c_ids in self.p_service.get_card_ids(col_id).items()
        }

        available = self.get_duplicates_amount(col)
        amount = amount if amount else int(available / r.amount)
        if available < r.amount * amount:
            raise AssertionError(f'[{self.u_id}] Not enough items of type \'{item_type}\' for amount {amount}')
        if not amount:
            print(f'[{self.u_id}] Not enough items of type \'{item_type}\' {available}/{r.amount}')
            return
        for i in range(0, amount):
            entities = self.get_duplicate_entities(col, r.amount)
            col = self.update_collection(col, entities)
            res = self.craft_item(item_type, set((i for v in entities.values() for i in v)))
            print(f'[{self.u_id}] Got{" NEW " if res.is_new else " "}{res.mint} {res.template_title}')
