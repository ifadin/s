import base64
from copy import deepcopy
from typing import Set, NamedTuple, Optional, Dict

import requests

from epics.auth import EAuth
from epics.player import PlayerService
from epics.utils import raise_for_status, raise_http_error


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
    requirements = {
        'd': Requirement(301, 2500, 10), 'g': Requirement(300, 500, 4),
        's': Requirement(299, 500, 3), 'p': Requirement(298, 500, 2)
    }
    collections = {'d': 2967, 'g': 2968, 's': 2970, 'p': 2969}

    def __init__(self, auth: EAuth = EAuth()) -> None:
        self.auth = auth

    # https://api.epics.gg/api/v1/crafting/plans/300?categoryId=1
    # {"silvercoins":500,"requirements":[{"requirementId":300,"entityIds":[101970505,102058040,102087019,104068959]}]}
    # https://api.epics.gg/api/v1/crafting/slots/793508/open-instant?categoryId=1
    # {"craftingcoins":null}
    def request_craft(self, r: Requirement, entity_ids: Set[int]) -> int:
        if len(entity_ids) != r.amount:
            raise AssertionError(f'Required {r.amount} entities')
        res = requests.post(f'{self.craft_url}{r.id}?categoryId=1', auth=self.auth, json={
            'silvercoins': r.s_coins,
            'requirements': [{'requirementId': r.id, 'entityIds': list(entity_ids)}]

        })
        raise_for_status(res)
        slot = next((s['id'] for s in res.json()['data']['slots'] if s['readyToOpen']), None)
        if not slot:
            raise_http_error(res)
        return slot

    def request_slot(self, slot_id: int) -> Optional[Card]:
        res = requests.post(f'{self.slot_url}{slot_id}/open-instant?categoryId=1', auth=self.auth, json={
            'craftingcoins': None
        })
        raise_for_status(res)
        return next((Card(c['id'], c['mintBatch'], c['mintNumber'], c['cardTemplate']['id'], c['cardTemplate']['title'],
                          c['isNewCardTemplate']) for c in res.json()['data']['cards']), None)

    def craft_item(self, item_type: str, entity_ids: Set[int]) -> Card:
        r = self.requirements[item_type]
        slot_id = self.request_craft(r, entity_ids)
        return self.request_slot(slot_id)

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
                raise AssertionError(f'Risk of items loss for {c[i_id]} from {items}')
            c[i_id] = diff
        return c

    def craft(self, item_type: str, amount: int = None):
        p = PlayerService(auth=self.auth)
        r = self.requirements[item_type]
        col = p.get_card_ids(self.collections[item_type])

        available = self.get_duplicates_amount(col)
        amount = amount if amount else int(available / r.amount)
        if available < r.amount * amount:
            raise AssertionError(f'Not enough items of type \'{item_type}\' for amount {amount}')

        for i in range(0, amount):
            entities = self.get_duplicate_entities(col, r.amount)
            col = self.update_collection(col, entities)
            res = self.craft_item(item_type, set((i for v in entities.values() for i in v)))
            print(f'Got{" NEW " if res.is_new else " "}{res.mint} {res.template_title}')
